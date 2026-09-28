# 🤖 ChatBot API

<p align="center">
<strong>Production-oriented asynchronous ChatBot backend built with FastAPI</strong>
</p>

<p align="center">
<a href="#-features">Features</a> • <a href="#-architecture">Architecture</a> • <a href="#-tech-stack">Tech Stack</a> • <a href="#-development">Development</a> • <a href="#-roadmap">Roadmap</a>
</p>

---

## 📖 Overview

**ChatBot API** is an asynchronous, production-oriented backend for a ChatGPT-like conversational application.

The project is designed around clear architectural boundaries between:

- HTTP/API handling
- Authentication and authorization
- Business logic
- Persistence
- Infrastructure
- LLM providers
- Tool execution
- Usage accounting
- Rate limiting

The architecture is intentionally modular so that new LLM providers and application capabilities can be added without coupling the core conversation workflow to vendor-specific implementations.

> [!NOTE]
> The project is under active development. The current roadmap is progressing through **Phase 8 — Advanced Features**.

---

## ✨ Features

### 🔐 Authentication

- User registration
- User login
- Password hashing
- JWT-based authentication
- Authentication dependencies
- Authorization logic

### 💬 Conversations

- Conversation management
- Message persistence
- Conversation history
- Context building
- Conversation orchestration
- Conversation summarization

### 🧠 LLM Integration

The application uses an internal provider abstraction instead of coupling business logic directly to a vendor SDK.

Current providers:

- **Ollama**
- **Google Gemini**

Provider responsibilities are intentionally limited to:

1. Converting internal requests into provider-specific requests
2. Calling the external LLM SDK
3. Converting provider responses into internal schemas

### 🛠️ Tool Calling

Tool execution is orchestrated by the conversation service rather than the provider.

```text
┌──────────────────────────────┐
│ Conversation Orchestrator    │
└──────────────┬───────────────┘
               │
               ▼
       ┌───────────────┐
       │  LLM Provider │
       └───────┬───────┘
               │
               ▼
          Tool Call
               │
               ▼
       ┌───────────────┐
       │  ToolRegistry │
       └───────┬───────┘
               │
               ▼
        Tool Execution
               │
               ▼
       ┌───────────────┐
       │  LLM Provider │
       └───────────────┘
```

The orchestrator controls the tool loop and its iteration limits.

### 🌊 Streaming

The application supports streaming LLM responses through Server-Sent Events (SSE).

```text
Client
  │
  ▼
FastAPI
  │
  ▼
ConversationOrchestratorService
  │
  ▼
LLMProvider.generate_stream()
  │
  ▼
LLMStreamChunk
  │
  ▼
SSE Response
```

Streaming is integrated with:

- Provider usage tracking
- Reservation lifecycle
- Settlement
- Persistence ordering
- Provider error handling
- Retry behavior

### 📊 Usage Accounting

Provider usage is treated as application state.

The lifecycle is:

```text
Request
   │
   ▼
Reservation
   │
   ▼
Provider Call
   │
   ▼
Actual Usage
   │
   ▼
Settlement
   │
   ▼
Persistence
```

Reservations and actual provider usage are intentionally separate concepts:

> **Reservation ≠ Actual Usage**

### 🚦 Rate Limiting

Rate limiting is backed by shared Redis state.

The application does not rely on process-local counters for shared rate-limit state.

### 🔴 Redis Failure Handling

Redis-specific failures remain inside the infrastructure boundary.

```text
RedisError
    │
    ▼
RateLimitStoreUnavailableError
    │
    ▼
RateLimitServiceUnavailableError
    │
    ▼
HTTP 503
```

This keeps infrastructure implementation details out of the application service layer.

---

# 🏗️ Architecture

The project follows a layered architecture with explicit dependency boundaries.

## High-Level Architecture

```text
                         ┌─────────────────────┐
                         │       Client        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     FastAPI API     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Service Layer    │
                         │                     │
                         │  Business Logic     │
                         │  Orchestration      │
                         └──────┬────────┬─────┘
                                │        │
                    ┌───────────┘        └────────────┐
                    ▼                                 ▼
          ┌─────────────────┐                ┌─────────────────┐
          │ Repository      │                │ LLM Providers   │
          │ Layer           │                │                 │
          └────────┬────────┘                │ Ollama / Gemini │
                   │                         └─────────────────┘
                   ▼
          ┌─────────────────┐
          │ SQLAlchemy 2.0  │
          │ AsyncSession    │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │   PostgreSQL    │
          └─────────────────┘
```

---

## 🤖 Conversation Architecture

```text
┌──────────────────────────────────────────┐
│          Conversation API                │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│     ConversationOrchestratorService     │
│                                          │
│  • Context building                      │
│  • Summary handling                      │
│  • Provider orchestration                │
│  • Tool loop                             │
│  • Usage lifecycle                       │
└───────────────┬──────────────────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
┌───────────────┐  ┌────────────────────┐
│ Context /     │  │ RateLimitService   │
│ Summary       │  │                    │
└───────────────┘  └─────────┬──────────┘
                             │
                             ▼
                     ┌───────────────┐
                     │ RateLimitStore│
                     └───────┬───────┘
                             │
                             ▼
                     ┌───────────────┐
                     │     Redis     │
                     └───────────────┘
```

---

## 🧩 LLM Provider Architecture

Application services depend on the internal provider contract rather than a vendor SDK.

```text
                 ┌──────────────────┐
                 │    LLMProvider   │
                 │    Abstraction   │
                 └────────┬─────────┘
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
      ┌───────────────┐        ┌───────────────┐
      │ OllamaProvider│        │ GeminiProvider│
      └───────┬───────┘        └───────┬───────┘
              │                        │
              ▼                        ▼
          Ollama API              Gemini API
```

This allows additional providers to be introduced without changing the core conversation workflow.

---

# 🧱 Project Structure

```text
.
├── app/
│   ├── api/
│   ├── core/
│   ├── database/
│   ├── dependencies/
│   ├── exceptions/
│   ├── infrastructure/
│   ├── models/
│   ├── providers/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── tools/
│   └── main.py
│
├── tests/
│
├── alembic/
│
├── .env
├── .env.example
├── .pre-commit-config.yaml
├── pyproject.toml
├── uv.lock
└── README.md
```

### Layer Responsibilities

| Layer          | Responsibility                            |
| -------------- | ----------------------------------------- |
| `api`          | HTTP endpoints, request/response handling |
| `services`     | Business logic and application workflows  |
| `repositories` | Database access                           |
| `providers`    | External LLM SDK adapters                 |
| `schemas`      | Pydantic models                           |
| `dependencies` | Dependency injection                      |
| `exceptions`   | Application exceptions and handlers       |
| `core`         | Shared application infrastructure         |
| `database`     | Database engine/session configuration     |
| `models`       | SQLAlchemy persistence models             |
| `middleware`   | HTTP/application middleware               |
| `utils`        | Small reusable utilities                  |

---

# 🛠️ Tech Stack

| Category             | Technology        |
| -------------------- | ----------------- |
| Language             | Python 3.11       |
| API                  | FastAPI           |
| Validation           | Pydantic v2       |
| Configuration        | pydantic-settings |
| Database             | PostgreSQL 17     |
| ORM                  | SQLAlchemy 2.0    |
| Async Driver         | asyncpg           |
| Migrations           | Alembic           |
| Authentication       | JWT / PyJWT       |
| Password Hashing     | pwdlib            |
| Cache / Shared State | Redis             |
| LLM                  | Ollama            |
| LLM                  | Google Gemini     |
| Package Manager      | uv                |
| Testing              | Pytest            |
| Linting              | Ruff              |
| Formatting           | Ruff              |
| Git Hooks            | pre-commit        |

---

# ⚡ Async-First Design

The application is designed around asynchronous I/O.

Database access follows:

```text
AsyncEngine
     │
     ▼
AsyncSession
     │
     ▼
asyncpg
     │
     ▼
PostgreSQL
```

The application uses SQLAlchemy 2.0 style APIs and avoids legacy patterns such as:

```python
db.query(...)
```

---

# 🔄 Usage Lifecycle

A provider operation follows a controlled usage lifecycle.

## Successful request

```text
┌─────────────┐
│ Reservation │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Provider  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Actual Usage│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Settlement │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Persistence │
└─────────────┘
```

## Provider failure

```text
Reservation
    │
    ▼
Provider
    │
    ✕
    │
    ▼
Release Reservation
```

## Retry

Retries do not create additional reservations for the same logical provider operation.

```text
              ┌───────────────┐
              │  Reservation  │
              └───────┬───────┘
                      │
             ┌────────┴────────┐
             ▼                 ▼
         Attempt 1          Attempt 2
             │                 │
             └────────┬────────┘
                      ▼
                  Settlement
```

---

# 💾 Persistence Ordering

A critical application invariant is:

```text
Provider
   ↓
Settlement
   ↓
Persistence
```

The assistant message must not be persisted before successful usage settlement.

This keeps message persistence and provider usage accounting consistent.

---

# 🔐 Configuration

Environment-specific configuration is kept outside the source code.

The project provides:

```text
.env
.env.example
```

Create your local environment from `.env.example` and provide the values required by your environment.

> [!WARNING]
> Never commit real credentials, API keys, JWT secrets, database passwords, or other sensitive configuration to Git.

---

# 🚀 Getting Started

## Prerequisites

Install:

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 17
- Redis
- A configured LLM provider

---

## Install Dependencies

The project uses `uv` for dependency and environment management.

```bash
uv sync
```

The lockfile is:

```text
uv.lock
```

Keep the lockfile committed and synchronized with `pyproject.toml`.

---

## Configure Environment

Copy the example configuration:

```bash
cp .env.example .env
```

Then configure the required database, Redis, authentication, and provider settings.

> Windows users can create/copy `.env` using their preferred shell or file manager.

---

## Database Migrations

The project uses Alembic for schema migrations.

Run migrations with:

```bash
uv run alembic upgrade head
```

Check the current migration state with:

```bash
uv run alembic current
```

---

## Run the Application

Start the FastAPI application using the project's configured entry point.

For local development, a typical command is:

```bash
uv run uvicorn app.main:app --reload
```

> Verify the application entry point in the current repository before changing this command if the project structure has evolved.

---

# 🧪 Testing

Run the complete test suite:

```bash
uv run pytest -q
```

Run service tests:

```bash
uv run pytest tests/services -q
```

Run provider tests:

```bash
uv run pytest tests/providers -q
```

Run integration tests:

```bash
uv run pytest tests/integration -q
```

The test suite covers areas including:

- Authentication
- Services
- Providers
- Streaming
- Tool calling
- Conversation orchestration
- Usage accounting
- Rate limiting
- Redis failure handling
- Integration behavior
- Regression scenarios

---

# 🧹 Code Quality

## Ruff

Run linting:

```bash
uv run ruff check .
```

Check formatting:

```bash
uv run ruff format --check .
```

Apply formatting:

```bash
uv run ruff format .
```

## Pre-commit

Run all configured hooks:

```bash
uv run pre-commit run --all-files
```

---

# 🧪 Testing Philosophy

Tests should validate application behavior and architectural contracts.

The project favors:

- Unit tests for isolated business rules
- Integration tests for service interactions
- Provider tests
- Streaming tests
- Failure-path tests
- Regression tests
- Contract-oriented test doubles

When a production service depends on an abstraction, tests should preferably provide a test implementation of that abstraction instead of bypassing the production architecture.

For example:

```text
Real Conversation Service
        │
        ▼
Real RateLimitService
        │
        ▼
Test RateLimitStore
```

rather than replacing the entire `RateLimitService` with a mock.

---

# 📋 Development Principles

### 1. Separation of Concerns

Each layer has a clear responsibility.

### 2. Dependency Inversion

Application services depend on abstractions rather than concrete infrastructure implementations.

### 3. Async by Default

I/O-bound application operations should use asynchronous APIs.

### 4. Provider Independence

Conversation business logic should not depend on a specific LLM vendor.

### 5. Explicit Usage Lifecycle

Reservation, actual usage, settlement, and release are separate concepts.

### 6. Deterministic Persistence

Settlement happens before assistant-message persistence.

### 7. No Unnecessary Abstractions

New abstractions should solve a concrete problem rather than exist only for theoretical flexibility.

### 8. No Duplicate Tests

Before adding a test, verify that the behavior is not already covered by the existing suite.

### 9. Minimal Changes

Prefer the smallest change that correctly satisfies the requirement.

### 10. Production Mindset

Security, consistency, observability, failure handling, and maintainability should be considered throughout development.

---

# 🗺️ Roadmap

```text
Phase 1   Project Foundation             ✅
Phase 2   PostgreSQL                     ✅
Phase 3   Authentication                 ✅
Phase 4   Chat                           ✅
Phase 5   Messages                       ✅
Phase 6   LLM Integration                ✅
Phase 7   Redis / Rate Limiting          ✅
Phase 8   Advanced Features              🚧
Phase 9   Docker                         ⏳
Phase 10  Testing & Quality              ⏳
Phase 11  CI/CD                          ⏳
Phase 12  Deployment                     ⏳
```

## Phase 8 — Advanced Features

Current development focus:

- 🌊 Streaming improvements
- 🔎 Search
- 📄 Pagination
- 📎 File Upload
- ⚙️ Background Tasks
- 📈 Monitoring

> [!IMPORTANT]
> Streaming already exists in the current application. Phase 8 should improve or complete the existing streaming capabilities rather than rebuild the existing architecture.

---

# 🔭 Production Readiness

The project is being developed toward production deployment with emphasis on:

- ✅ Layered architecture
- ✅ Async I/O
- ✅ PostgreSQL persistence
- ✅ Redis-backed shared state
- ✅ JWT authentication
- ✅ LLM provider abstraction
- ✅ Tool calling
- ✅ Streaming
- ✅ Usage accounting
- ✅ Rate limiting
- ✅ Failure handling
- 🚧 Advanced features
- ⏳ Containerization
- ⏳ CI/CD
- ⏳ Deployment

Production readiness is an ongoing engineering target. Features marked as `⏳` are planned roadmap items and should not be interpreted as already completed.

---

# 🤝 Development Workflow

A typical feature follows this workflow:

```text
Requirement
    │
    ▼
Existing Architecture Review
    │
    ▼
Smallest Justified Change
    │
    ▼
Implementation
    │
    ▼
Focused Tests
    │
    ▼
Regression Tests
    │
    ▼
Architecture Review
    │
    ▼
Focused Git Commit
```

Before changing architecture, ask:

> **Is this change required by a real functional, correctness, security, performance, or maintainability need?**

If not, prefer the existing architecture.

---

# 📝 Commit Convention

Commits should be focused and describe the actual change.

Examples:

```text
feat(auth): add JWT authentication
feat(llm): add Gemini provider
feat(streaming): add provider streaming support
feat(rate-limit): add Redis-backed usage lifecycle
fix(rate-limit): map Redis failures to service unavailable
test(conversation): add streaming integration coverage
refactor(repository): simplify message persistence
```

Avoid mixing unrelated refactors with feature work.

---

# 🔒 Security Guidelines

Never commit:

- API keys
- Database passwords
- JWT secrets
- Redis credentials
- Provider credentials
- Private certificates
- Production environment files

Use environment variables or the project's configuration system for secrets.

When implementing file uploads, search, or other user-controlled input:

- Validate input
- Enforce size limits
- Avoid path traversal
- Avoid trusting client-provided filenames
- Validate supported content types
- Keep infrastructure boundaries explicit

---

# 📊 Observability

Monitoring is part of the Phase 8 roadmap.

Future observability should cover areas such as:

- Request latency
- Provider latency
- Provider failures
- Streaming failures
- Token usage
- Rate-limit events
- Background task failures
- Database performance

Metrics should avoid unnecessary high-cardinality labels such as arbitrary user IDs or chat IDs.

---

# 📚 Architecture Invariants

The following invariants should remain stable unless a deliberate architectural change is made.

### Provider boundary

```text
Service → LLMProvider → External SDK
```

### Persistence boundary

```text
Service → Repository → SQLAlchemy → PostgreSQL
```

### Rate-limit boundary

```text
Service → RateLimitService → RateLimitStore → Redis
```

### Usage lifecycle

```text
Reservation
    ↓
Provider
    ↓
Actual Usage
    ↓
Settlement
    ↓
Persistence
```

### Failure lifecycle

```text
Provider Failure
      ↓
Release Reservation
```

These boundaries are part of the application's architecture and should not be bypassed for convenience.

---

# 📄 License

License information will be added when the project's distribution license is finalized.

---

<p align="center">
<sub>Built with FastAPI · PostgreSQL · Redis · SQLAlchemy · Ollama · Gemini</sub>
</p>

from app.services.jwt import create_access_token, decode_token

token = create_access_token(
    subject="123e4567-e89b-12d3-a456-426614174000",
)

print(token)

payload = decode_token(token)

print(payload)

local token_limit = tonumber(ARGV[1])
local requested_tokens = tonumber(ARGV[2])

local cost_limit = tonumber(ARGV[3])
local requested_cost = tonumber(ARGV[4])

local ttl = tonumber(ARGV[5])

local current_tokens = redis.call("GET", KEYS[1])
local reserved_tokens = redis.call("GET", KEYS[2])

local current_cost = redis.call("GET", KEYS[3])
local reserved_cost = redis.call("GET", KEYS[4])

if not current_tokens then
    current_tokens = 0
else
    current_tokens = tonumber(current_tokens)
end

if not reserved_tokens then
    reserved_tokens = 0
else
    reserved_tokens = tonumber(reserved_tokens)
end

if not current_cost then
    current_cost = 0
else
    current_cost = tonumber(current_cost)
end

if not reserved_cost then
    reserved_cost = 0
else
    reserved_cost = tonumber(reserved_cost)
end

local effective_tokens = current_tokens + reserved_tokens
local effective_cost = current_cost + reserved_cost

if effective_tokens + requested_tokens > token_limit then
    return {0, effective_tokens, effective_cost}
end

if cost_limit > 0 and effective_cost + requested_cost > cost_limit then
    return {0, effective_tokens, effective_cost}
end

if reserved_tokens == 0 then
    redis.call("SET", KEYS[2], requested_tokens, "EX", ttl)
else
    redis.call("INCRBY", KEYS[2], requested_tokens)
end

if reserved_cost == 0 then
    redis.call("SET", KEYS[4], requested_cost, "EX", ttl)
else
    redis.call("INCRBY", KEYS[4], requested_cost)
end

return {
    1,
    effective_tokens + requested_tokens,
    effective_cost + requested_cost
}
local actual_tokens = tonumber(ARGV[1])
local actual_cost = tonumber(ARGV[2])

local reserved_tokens = tonumber(ARGV[3])
local reserved_cost = tonumber(ARGV[4])

local current_tokens = redis.call("GET", KEYS[1])
local current_reserved_tokens = redis.call("GET", KEYS[2])

local current_cost = redis.call("GET", KEYS[3])
local currrent_reserved_cost = redis.call("GET", KEYS[4])

if not current_tokens then
    current_tokens = 0
else
    current_tokens = tonumber(current_tokens)
end

if not current_reserved_tokens then
    current_reserved_tokens = 0
else
    current_reserved_tokens = tonumber(current_reserved_tokens)
end

if not current_cost then
    current_cost = 0
else
    current_cost = tonumber(current_cost)
end

if not currrent_reserved_cost then
    currrent_reserved_cost = 0
else
    currrent_reserved_cost = tonumber(currrent_reserved_cost)
end

local new_reserved_tokens = current_reserved_tokens - reserved_tokens
local new_reserved_cost = currrent_reserved_cost - reserved_cost

if new_reserved_tokens < 0 then
    new_reserved_tokens = 0
end

if new_reserved_cost < 0 then
    new_reserved_cost = 0
end

local new_tokens = current_tokens + actual_tokens
local new_cost = current_cost + actual_cost

redis.call("SET", KEYS[1], new_tokens, "EX", ARGV[5])

if new_reserved_tokens == 0 then
    redis.call("DEL", KEYS[2])
else
    redis.call("SET", KEYS[2], new_reserved_tokens, "EX", ARGV[5])
end

redis.call("SET", KEYS[3], new_cost, "EX", ARGV[5])

if new_reserved_cost == 0 then
    redis.call("DEL", KEYS[4])
else
    redis.call("SET", KEYS[4], new_reserved_cost, "EX", ARGV[5])
end

return {new_tokens, new_cost, new_reserved_tokens, new_reserved_cost}
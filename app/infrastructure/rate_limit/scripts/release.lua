local reserved_tokens = tonumber(ARGV[1])
local reserved_cost = tonumber(ARGV[2])

local current_reserved_tokens = redis.call("GET", KEYS[1])
local current_reserved_cost = redis.call("GET", KEYS[2])

if not current_reserved_tokens then
    current_reserved_tokens = 0
else
    current_reserved_tokens = tonumber(current_reserved_tokens)
end

if not current_reserved_cost then
    current_reserved_cost = 0
else
    current_reserved_cost = tonumber(current_reserved_cost)
end

local new_reserved_tokens = current_reserved_tokens - reserved_tokens
local new_reserved_cost = current_reserved_cost - reserved_cost

if new_reserved_tokens < 0 then
    new_reserved_tokens = 0
end

if new_reserved_cost < 0 then
    new_reserved_cost = 0
end

if new_reserved_tokens == 0 then
    redis.call("DEL", KEYS[1])
else
    redis.call("SET", KEYS[1], new_reserved_tokens, "EX", ARGV[3])
end

if new_reserved_cost == 0 then
    redis.call("DEL", KEYS[2])
else
    redis.call("SET", KEYS[2], new_reserved_cost, "EX", ARGV[3])
end

return {new_reserved_tokens, new_reserved_cost}
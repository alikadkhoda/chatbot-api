local requested = tonumber(ARGV[2])
local limit = tonumber(ARGV[1])

if requested > limit then
    return {0, 0}
end

local current = redis.call("GET", KEYS[1])

if not current then
    redis.call("SET", KEYS[1], ARGV[2], "EX", ARGV[3])
    return {1, ARGV[2]}
end

current = tonumber(current)

if current + tonumber(ARGV[2]) > limit then
    return {0, current}
end

current = redis.call("INCRBY", KEYS[1], ARGV[2])

return {1, current}
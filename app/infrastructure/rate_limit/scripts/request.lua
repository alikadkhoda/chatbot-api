local minute_limit = tonumber(ARGV[1])
local daily_limit = tonumber(ARGV[2])

local minute_current = redis.call("GET", KEYS[1])
local daily_current = redis.call("GET", KEYS[2])

if not minute_current then
    minute_current = 0
else
    minute_current = tonumber(minute_current)
end

if not daily_current then
    daily_current = 0
else
    daily_current = tonumber(daily_current)
end

if minute_current >= minute_limit then
    return {0, minute_current, daily_current}
end

if daily_current >= daily_limit then
    return {0, minute_current, daily_current}
end

if minute_current == 0 then
    redis.call("SET", KEYS[1], 1, "EX", ARGV[3])
else
    redis.call("INCR", KEYS[1])
end

if daily_current == 0 then
    redis.call("SET", KEYS[2], 1, "EX", ARGV[4])
else
    redis.call("INCR", KEYS[2])
end

return {1, minute_current + 1, daily_current + 1}
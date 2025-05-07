
import redis

try:
    r = redis.Redis(host='localhost', port=6379)
    r.delete("backend_servers")
    r.rpush("backend_servers", "http://localhost:6001")
    r.rpush("backend_servers", "http://localhost:6002")
    r.rpush("backend_servers", "http://localhost:6003")
    print(" Backend servers registered in Redis.")
except Exception as e:
    print("Redis Error:", e)

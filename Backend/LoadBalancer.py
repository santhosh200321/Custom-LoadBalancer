import asyncio
import aiohttp
import redis.asyncio as redis
from aiohttp import web
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Redis client
redis_client = redis.Redis()

# Strategy options: round_robin or least_conn
STRATEGY = "round_robin"

# Redis keys
REDIS_KEY_SERVERS = "backend_servers"
REDIS_CONN_PREFIX = "conn_count:"
REDIS_RR_COUNTER = "rr_counter"

# Round-robin load balancing
async def round_robin():
    servers = await redis_client.lrange(REDIS_KEY_SERVERS, 0, -1)
    if not servers:
        logging.error("No servers found in Redis")
        return None

    total_servers = len(servers)
    counter = await redis_client.incr(REDIS_RR_COUNTER)
    index = (counter - 1) % total_servers
    selected = servers[index].decode()
    logging.info(f"[Round Robin] Selected: {selected}")
    return selected

# Least-connections load balancing
async def least_conn():
    servers = await redis_client.lrange(REDIS_KEY_SERVERS, 0, -1)
    if not servers:
        logging.error("No servers found in Redis")
        return None

    min_conn = float('inf')
    selected_server = None

    for server_bytes in servers:
        server = server_bytes.decode()
        key = f"{REDIS_CONN_PREFIX}{server}"
        try:
            conn_count = await redis_client.get(key)
            conn_count = int(conn_count) if conn_count else 0
        except Exception as e:
            logging.warning(f"Failed to get connection count for {server}: {e}")
            conn_count = 0

        if conn_count < min_conn:
            min_conn = conn_count
            selected_server = server

    logging.info(f"[Least Conn] Selected: {selected_server} (Connections: {min_conn})")
    return selected_server

# Increment and decrement connection counts
async def increment_conn(server):
    key = f"{REDIS_CONN_PREFIX}{server}"
    await redis_client.incr(key)

async def decrement_conn(server):
    key = f"{REDIS_CONN_PREFIX}{server}"
    await redis_client.decr(key)

# Proxy handler
async def handle_proxy(request):
    logging.info("Incoming request to /proxy")

    strategy = request.query.get("strategy", STRATEGY)

    try:
        if strategy == "round_robin":
            server = await round_robin()
        elif strategy == "least_conn":
            server = await least_conn()
        else:
            return web.Response(text="Unsupported strategy", status=400)

        if not server:
            return web.Response(text="No backend servers available", status=500)

        logging.info(f"Forwarding request to: {server}")

        try:
            await increment_conn(server)
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{server}/process") as resp:
                    data = await resp.text()
                    return web.Response(text=f"Response from: {server}\n\n{data}")
        except Exception as e:
            logging.error(f"Error forwarding to backend: {e}")
            return web.Response(text=f"Error forwarding to backend: {e}", status=500)
        finally:
            await decrement_conn(server)

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return web.Response(text=f"Internal Server Error: {e}", status=500)

# Aiohttp web app
app = web.Application()
app.add_routes([web.post('/proxy', handle_proxy)])

# Run server
if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=5000)

from flask import Flask, request, jsonify
import redis.asyncio as redis
import httpx
import asyncio

app = Flask(__name__)
redis_client = redis.Redis()

REDIS_KEY_SERVERS = "backend_servers"
REDIS_CONN_PREFIX = "conn_count:"
REDIS_RR_COUNTER = "rr_counter"
DEFAULT_STRATEGY = "round_robin"

# Async Redis logic
async def round_robin():
    servers = await redis_client.lrange(REDIS_KEY_SERVERS, 0, -1)
    if not servers:
        return None
    index = (await redis_client.incr(REDIS_RR_COUNTER) - 1) % len(servers)
    return servers[index].decode()

async def least_conn():
    servers = await redis_client.lrange(REDIS_KEY_SERVERS, 0, -1)
    min_conn, selected = float('inf'), None
    for s in servers:
        server = s.decode()
        conn = await redis_client.get(f"{REDIS_CONN_PREFIX}{server}") or 0
        conn = int(conn)
        if conn < min_conn:
            min_conn = conn
            selected = server
    return selected

async def increment_conn(server):
    await redis_client.incr(f"{REDIS_CONN_PREFIX}{server}")

async def decrement_conn(server):
    await redis_client.decr(f"{REDIS_CONN_PREFIX}{server}")

# Async route handler
@app.route('/proxy', methods=['POST'])
async def proxy():
    strategy = request.args.get('strategy', DEFAULT_STRATEGY)

    if strategy == 'round_robin':
        server = await round_robin()
    elif strategy == 'least_conn':
        server = await least_conn()
    else:
        return jsonify({"error": "Invalid strategy"}), 400

    if not server:
        return jsonify({"error": "No backend servers available"}), 500

    backend_url = f"{server}/process"

    try:
        await increment_conn(server)
        async with httpx.AsyncClient() as client:
            response = await client.post(backend_url)
            return f"Response from {server}:\n\n{response.text}"
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        await decrement_conn(server)


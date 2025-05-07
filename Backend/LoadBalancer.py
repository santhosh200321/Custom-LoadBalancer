import asyncio
import aiohttp
import redis.asyncio as redis
from aiohttp import web
import logging
from prometheus_client import Counter, Histogram, start_http_server
from prometheus_client import Gauge, Summary, REGISTRY

# Redis client
redis_client = redis.Redis()

# Load balancing strategy: Options: round_robin, least_conn
STRATEGY = "round_robin"

# Logging config
logging.basicConfig(level=logging.DEBUG)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'load_balancer_request_count',
    'Total number of requests received by the load balancer',
    ['method', 'endpoint', 'http_status']
)

REQUEST_LATENCY = Histogram(
    'load_balancer_request_latency_seconds',
    'Latency of requests processed by the load balancer',
    ['method', 'endpoint']
)

BACKEND_CONNECTION_COUNT = Gauge(
    'load_balancer_backend_connections',
    'Current number of connections to backend servers',
    ['backend_server']
)

BACKEND_REQUEST_COUNT = Counter(
    'load_balancer_backend_request_count',
    'Total number of requests forwarded to each backend server',
    ['backend_server']
)

BACKEND_ERROR_COUNT = Counter(
    'load_balancer_backend_error_count',
    'Total number of errors when communicating with backend servers',
    ['backend_server']
)

STRATEGY_USAGE = Counter(
    'load_balancer_strategy_usage',
    'Count of load balancing strategy usage',
    ['strategy']
)

REDIS_KEY_SERVERS = "backend_servers"
REDIS_CONN_PREFIX = "conn_count:"
REDIS_RR_COUNTER = "rr_counter"

# Round Robin strategy
async def round_robin():
    STRATEGY_USAGE.labels(strategy='round_robin').inc()
    servers = await redis_client.lrange(REDIS_KEY_SERVERS, 0, -1)
    if not servers:
        logging.error("No servers found in Redis")
        return None
    total_servers = len(servers)
    counter = await redis_client.incr(REDIS_RR_COUNTER)
    index = (counter - 1) % total_servers
    selected = servers[index].decode()
    logging.debug(f"Round-robin selected: {selected}")
    return selected

# Least Connections strategy
async def least_conn():
    STRATEGY_USAGE.labels(strategy='least_conn').inc()
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
            logging.warning(f"Error getting conn count for {server}: {e}")
            conn_count = 0

        if conn_count < min_conn:
            min_conn = conn_count
            selected_server = server

    logging.debug(f"Least connection selected: {selected_server} with {min_conn} connections")
    return selected_server

# Update connection count in Redis
async def increment_conn(server):
    key = f"{REDIS_CONN_PREFIX}{server}"
    await redis_client.incr(key)
    BACKEND_CONNECTION_COUNT.labels(backend_server=server).inc()

async def decrement_conn(server):
    key = f"{REDIS_CONN_PREFIX}{server}"
    await redis_client.decr(key)
    BACKEND_CONNECTION_COUNT.labels(backend_server=server).dec()

# Proxy handler
async def handle_proxy(request):
    logging.info("Received request to load balancer")
    REQUEST_COUNT.labels(method=request.method, endpoint='/proxy', http_status='200').inc()
    request_start_time = asyncio.get_event_loop().time()

    STRATEGY = request.query.get("strategy", STRATEGY)

    try:
        if STRATEGY == "round_robin":
            server = await round_robin()
        elif STRATEGY == "least_conn":
            server = await least_conn()
        else:
            REQUEST_COUNT.labels(method=request.method, endpoint='/proxy', http_status='400').inc()
            return web.Response(text="Unsupported strategy", status=400)

        if not server:
            REQUEST_COUNT.labels(method=request.method, endpoint='/proxy', http_status='500').inc()
            return web.Response(text="No backend servers available", status=500)

        logging.info(f"Forwarding request to: {server}")
        BACKEND_REQUEST_COUNT.labels(backend_server=server).inc()
        
        try:
            await increment_conn(server)
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{server}/process") as resp:
                    data = await resp.text()
                    logging.info(f"Received response from: {server}")
                    REQUEST_LATENCY.labels(
                        method=request.method,
                        endpoint='/proxy'
                    ).observe(asyncio.get_event_loop().time() - request_start_time)
                    return web.Response(text=f"Response from: {server}\n\n{data}")
        except Exception as e:
            BACKEND_ERROR_COUNT.labels(backend_server=server).inc()
            logging.error(f"Failed to connect to backend: {e}")
            REQUEST_COUNT.labels(method=request.method, endpoint='/proxy', http_status='500').inc()
            return web.Response(text=f"Failed to connect to backend: {e}", status=500)
        finally:
            await decrement_conn(server)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        REQUEST_COUNT.labels(method=request.method, endpoint='/proxy', http_status='500').inc()
        return web.Response(text=f"Internal server error: {e}", status=500)

# Set up web app
app = web.Application()
app.add_routes([web.post('/proxy', handle_proxy)])

# Run app
async def start_background_tasks(app):
    # Start Prometheus metrics server on port 8000
    start_http_server(8000)
    logging.info("Prometheus metrics server started on port 8000")

app.on_startup.append(start_background_tasks)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=5000)
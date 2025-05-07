# 🔄 Working Flow of the Asynchronous Load Balancer with Redis & Prometheus

This document explains how the system components interact in a step-by-step manner, highlighting both **functional behavior** and **monitoring flow**.

---

## 📦 System Components

1. **Client** – Sends POST requests to the load balancer.
2. **Load Balancer (Python app using aiohttp)** – Forwards requests to backend servers based on the selected strategy.
3. **Redis** – Stores:
   - List of backend server URLs
   - Active connection count per server
   - Round-robin counter
4. **Backend Servers** – Respond to `/process` endpoint.
5. **Prometheus** – Monitors and scrapes metrics from the load balancer at `localhost:8000/metrics`.

---

## 🔁 Step-by-Step Working Flow

### 1. 🔗 Client Request

- The client sends a `POST` request to:

```
POST http://localhost:5000/proxy?strategy=round_robin
```

- Query Parameter `strategy` can be:
  - `round_robin`
  - `least_conn`
- If not provided, default strategy is `round_robin`.

---

### 2. ⚖️ Load Balancer Receives the Request

- The `aiohttp` app receives the request at the `/proxy` route.
- Based on the `strategy` param, the handler function:
  - Calls either `round_robin()` or `least_conn()`

---

### 3. 🔁 Round Robin Logic

- Load balancer gets list of backend servers from Redis using:
  ```python
  redis_client.lrange("backend_servers", 0, -1)
  ```
- It increments a Redis counter (`rr_counter`) and selects the server at:
  ```python
  index = (counter - 1) % total_servers
  ```

---

### 4. 📊 Least Connections Logic

- Load balancer gets the list of servers.
- It then iterates through each server and checks the connection count stored at:
  ```
  conn_count:<server>
  ```
- Selects the server with the **minimum active connections**.

---

### 5. 📡 Proxy Forwarding

- Once a server is selected, the load balancer:
  - Increments its connection count in Redis
  - Sends a `POST` request to the server’s `/process` endpoint using `aiohttp.ClientSession()`
  - Waits for response

---

### 6. 📤 Backend Server Response

- Backend server receives the forwarded request at `/process`.
- It processes the request and returns a response (e.g., "Processed by backend!").

---

### 7. 🔄 Load Balancer Post-Response

- Load balancer:
  - Decrements the backend's connection count in Redis
  - Returns a `web.Response` to the client including:
    - Server used
    - Actual response from backend

---

## 🔍 Monitoring with Prometheus

### 🔧 Metrics Endpoint

- Load balancer exposes Prometheus metrics at:
  ```
  http://localhost:8000/metrics
  ```

### 📈 Metrics Tracked

- **Request count**:
  ```python
  http_requests_total
  ```

- **Request duration**:
  ```python
  request_duration_seconds
  ```

- **Active connections**: Indirectly monitored from Redis `conn_count:<server>`

---

### 🔧 Prometheus Setup

- `prometheus.yml` configuration:

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'loadbalancer'
    static_configs:
      - targets: ['host.docker.internal:8000']
```

> For Linux, use `localhost:8000` instead.

---

## 🧪 Example Execution

### Redis Setup

```bash
docker run -d --name redis-lb -p 6379:6379 redis
redis-cli
> LPUSH backend_servers http://localhost:6001
> LPUSH backend_servers http://localhost:6002
```

### Backend Servers (Flask Example)

```python
from flask import Flask
app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process():
    return "Processed by Backend"

app.run(port=6001)
```

---

## ⚙️ Prometheus Metrics Testing

1. Start Prometheus:
```bash
docker run -d -p 9090:9090 -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus
```

2. Visit: `http://localhost:9090`
3. Try queries:
   - `http_requests_total`
   - `rate(request_duration_seconds_bucket[1m])`

---

## 🔁 Summary of Request Lifecycle

```text
Client Request
      ↓
Load Balancer (/proxy) ← strategy param
      ↓
Fetch server list from Redis
      ↓
Select Server (RR or LC)
      ↓
POST → selected_backend/process
      ↓
Backend processes and responds
      ↓
Return response to client
      ↓
Update connection counts in Redis
      ↓
Expose metrics at /metrics → scraped by Prometheus
```

---

## 🔐 Optional: Authentication, Logging & Health Checks

You can extend this system by:

- Adding JWT authentication to incoming requests
- Implementing health checks for backend availability
- Integrating Grafana for visualizing Prometheus metrics
- Setting timeout and retry logic for backend failure

---

## 📞 Contact

Maintained by **Santhosh**  
[GitHub](https://github.com/santhosh200321)

---
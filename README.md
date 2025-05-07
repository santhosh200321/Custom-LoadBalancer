# Custom-LoadBalancer
#  Custom Load Balancer with Redis & Prometheus

A high-performance asynchronous load balancer written in Python . This project supports static and  dynamic load balancing strategies 
like **Round-Robin** and **Least Connections**, with backend server lists managed via **Redis**, and monitoring enabled using **Prometheus** and **docker**

---

##  Features

-  Asynchronous load balancing using `aiohttp`
-  Supports **Round-Robin** and **Least Connections** strategies
-  Backend server list stored in **Redis**
-  Prometheus metrics for monitoring
-  Dockerized Prometheus setup
-  Simple, lightweight, and extensible architecture

---

##  Technologies Used

- Python 3.11+
- aiohttp
- redis.asyncio
- prometheus_client
- Redis 
- Prometheus (Docker)
- Docker Compose (optional)


"""Production Gunicorn configuration for RIA Backend API (VM 1).

Usage:
    gunicorn -c gunicorn_conf.py server:app
"""
import multiprocessing
import os

# Server socket
bind = f"{os.getenv('API_HOST', '0.0.0.0')}:{os.getenv('PORT', '5001')}"
backlog = 2048

# Worker processes & threading
# For IO-bound Flask API handling dashboard requests & batch imports
workers = int(os.getenv("WEB_CONCURRENCY", "4"))
threads = int(os.getenv("PYTHON_THREADS", "4"))
worker_class = "gthread"
worker_connections = 1000
timeout = int(os.getenv("WEB_TIMEOUT", "60"))
keepalive = 5

# Process naming
proc_name = "ria-api"

# Logging: stdout / stderr (captured by systemd journalctl)
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Lifecycle hooks
def on_starting(server):
    server.log.info("Starting RIA API under Gunicorn (workers=%s, threads=%s)", workers, threads)

def worker_exit(server, worker):
    server.log.info("Worker exited: pid=%s", worker.pid)

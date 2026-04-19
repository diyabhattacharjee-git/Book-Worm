import os

# Bind to Render port
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Use small worker count (important for Render free tier)
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))

# Worker settings
worker_class = "sync"
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# Max requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Hooks
def on_starting(server):
    print("🚀 Starting BookBot API server...")

def when_ready(server):
    print(f"✅ Server is ready. Workers: {workers}")

def on_exit(server):
    print("👋 Shutting down BookBot API server...")

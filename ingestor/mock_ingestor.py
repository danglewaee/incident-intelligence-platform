import os
import random
import time
import requests

API_URL = os.getenv("API_URL", "http://api:8000")
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "4"))

SERVICES = ["auth-service", "billing-service", "search-service", "feed-service"]
ERROR_CODES = ["DB_TIMEOUT", "RATE_LIMIT", "NULL_POINTER", "PAYMENT_502", "CACHE_MISS_STORM"]
MESSAGES = [
    "Upstream timeout while fetching profile",
    "Unhandled exception in request handler",
    "Database connection pool exhausted",
    "Payment provider returned 502",
    "Cache stampede detected on hot key",
]



def generate_event() -> dict:
    service = random.choice(SERVICES)
    level = random.choices(["warn", "error", "critical"], weights=[0.25, 0.62, 0.13])[0]
    deploy_tag = None
    if random.random() < 0.22:
        deploy_tag = f"{service}-deploy-{random.randint(101, 132)}"

    return {
        "service": service,
        "environment": "prod",
        "level": level,
        "message": random.choice(MESSAGES),
        "error_code": random.choice(ERROR_CODES),
        "latency_ms": round(random.uniform(40, 1300), 2),
        "deploy_tag": deploy_tag,
    }



def wait_for_api():
    while True:
        try:
            r = requests.get(f"{API_URL}/health", timeout=3)
            if r.ok:
                return
        except Exception:
            pass
        time.sleep(2)


if __name__ == "__main__":
    wait_for_api()
    while True:
        evt = generate_event()
        try:
            requests.post(f"{API_URL}/events", json=evt, timeout=5)
        except Exception:
            pass
        time.sleep(INTERVAL_SECONDS)
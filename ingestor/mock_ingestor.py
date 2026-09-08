import os
import random
import time
from datetime import datetime

import requests

COLLECTOR_HOSTPORT = os.getenv("COLLECTOR_HOSTPORT")
API_URL = os.getenv("API_URL") or (
    f"http://{COLLECTOR_HOSTPORT}" if COLLECTOR_HOSTPORT else "http://collector:8000"
)
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "3"))

SERVICES = [
    "api-gateway",
    "auth-service",
    "payment-service",
    "notification-service",
    "db-primary",
    "cache-layer",
]

NORMAL_MESSAGES = {
    "auth-service": [
        ("AUTH_TIMEOUT", "Auth token validation timeout"),
        ("AUTH_500", "Unhandled exception in auth middleware"),
    ],
    "payment-service": [
        ("PAYMENT_502", "Upstream provider 502 while capturing payment"),
        ("DB_TIMEOUT", "Transaction commit timeout on payment ledger"),
    ],
    "notification-service": [
        ("QUEUE_BACKPRESSURE", "Notification queue lag exceeded threshold"),
        ("SMTP_RETRY", "SMTP endpoint retries exhausted"),
    ],
    "api-gateway": [
        ("UPSTREAM_TIMEOUT", "Gateway upstream timeout for /checkout"),
        ("RATE_LIMIT", "Rate limiter saturation near edge nodes"),
    ],
    "db-primary": [
        ("DB_CONN_POOL", "Database connection pool exhausted"),
        ("LOCK_CONTENTION", "Hot row lock contention detected"),
    ],
    "cache-layer": [
        ("CACHE_MISS_STORM", "Cache miss storm on session key prefix"),
        ("EVICTION_SPIKE", "Unexpected eviction spike in cache cluster"),
    ],
}

SCENARIOS = [
    {
        "name": "latency-spike",
        "service": "payment-service",
        "level": "error",
        "latency_ms": (1200, 2600),
        "error_code": "PAYMENT_502",
        "message": "Injected latency spike after downstream provider slowdown",
        "deploy_tag_chance": 0.15,
    },
    {
        "name": "db-timeout",
        "service": "db-primary",
        "level": "critical",
        "latency_ms": (900, 2000),
        "error_code": "DB_TIMEOUT",
        "message": "Injected DB timeout under simulated write contention",
        "deploy_tag_chance": 0.1,
    },
    {
        "name": "failed-deploy",
        "service": "auth-service",
        "level": "critical",
        "latency_ms": (500, 1700),
        "error_code": "AUTH_500",
        "message": "Injected failed deployment causing startup exception loop",
        "deploy_tag_chance": 0.9,
    },
    {
        "name": "cascading-error",
        "service": "api-gateway",
        "level": "critical",
        "latency_ms": (1000, 2500),
        "error_code": "UPSTREAM_TIMEOUT",
        "message": "Injected cascading gateway errors due to auth/payment degradation",
        "deploy_tag_chance": 0.2,
    },
]


def _deploy_tag(service: str) -> str:
    stamp = datetime.utcnow().strftime("%m%d%H%M")
    return f"{service}-deploy-{stamp}-{random.randint(1, 9)}"


def normal_event() -> dict:
    service = random.choice(SERVICES)
    code, message = random.choice(NORMAL_MESSAGES[service])
    level = random.choices(["warn", "error", "critical"], weights=[0.3, 0.58, 0.12])[0]
    deploy_tag = _deploy_tag(service) if random.random() < 0.18 else None
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": service,
        "environment": "prod",
        "event_type": "log",
        "level": level,
        "message": message,
        "error_code": code,
        "latency_ms": round(random.uniform(50, 1100), 2),
        "deploy_tag": deploy_tag,
        "deployment_id": deploy_tag,
    }


def scenario_event() -> dict:
    scenario = random.choice(SCENARIOS)
    deploy_tag = None
    if random.random() < scenario["deploy_tag_chance"]:
        deploy_tag = _deploy_tag(scenario["service"])

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": scenario["service"],
        "environment": "prod",
        "event_type": "alert",
        "level": scenario["level"],
        "message": f"{scenario['name']}: {scenario['message']}",
        "error_code": scenario["error_code"],
        "latency_ms": round(random.uniform(*scenario["latency_ms"]), 2),
        "deploy_tag": deploy_tag,
        "deployment_id": deploy_tag,
    }


def generate_event() -> dict:
    if random.random() < 0.28:
        return scenario_event()
    return normal_event()


def wait_for_collector():
    while True:
        try:
            r = requests.get(f"{API_URL}/health", timeout=3)
            if r.ok:
                return
        except Exception:
            pass
        time.sleep(2)


if __name__ == "__main__":
    wait_for_collector()
    while True:
        evt = generate_event()
        try:
            requests.post(f"{API_URL}/events", json=evt, timeout=5)
        except Exception:
            pass
        time.sleep(INTERVAL_SECONDS)

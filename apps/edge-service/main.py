from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi.responses import PlainTextResponse
from datetime import datetime

app = FastAPI(title="MEL Edge Service", version="1.0.0")

# ──────────────────────────────────────────────
# Prometheus Metrics
# These are what Grafana will visualize.
# Each metric type serves a different purpose:
#   Counter = only goes up (total requests, total readings)
#   Gauge   = goes up and down (current temperature, current vibration)
#   Histogram = tracks distribution (processing time buckets)
# ──────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "edge_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint"]
)
TEMPERATURE = Gauge(
    "machine_temperature_celsius",
    "Current machine temperature"
)
VIBRATION = Gauge(
    "machine_vibration_mm_s",
    "Current machine vibration in mm/s"
)
MACHINE_STATUS = Gauge(
    "machine_status",
    "Machine status: 0=ERROR, 1=WARNING, 2=RUNNING"
)
SENSOR_READINGS = Counter(
    "sensor_readings_total",
    "Total sensor readings received"
)
PROCESSING_TIME = Histogram(
    "sensor_processing_seconds",
    "Time to process sensor reading"
)

# ──────────────────────────────────────────────
# In-memory state (latest reading from the simulator)
# In production this would be a database or message queue.
# For a demo, in-memory is fine.
# ──────────────────────────────────────────────
latest_reading = {
    "temperature": 0.0,
    "vibration": 0.0,
    "status": "UNKNOWN",
    "timestamp": None
}

STATUS_MAP = {"RUNNING": 2, "WARNING": 1, "ERROR": 0, "UNKNOWN": -1}


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get("/health")
def health():
    """Kubernetes uses this for liveness/readiness probes.
    If this endpoint fails, K8s restarts the pod."""
    REQUEST_COUNT.labels(method="GET", endpoint="/health").inc()
    return {
        "status": "healthy",
        "service": "mel-edge-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/status")
def status():
    """Returns the latest sensor reading. 
    Useful for quick manual checks."""
    REQUEST_COUNT.labels(method="GET", endpoint="/status").inc()
    return {"latest_reading": latest_reading}


@app.post("/sensor-data")
def receive_sensor_data(data: dict):
    """Receives sensor data from the simulator.
    Updates both the in-memory state AND the Prometheus metrics."""
    REQUEST_COUNT.labels(method="POST", endpoint="/sensor-data").inc()
    SENSOR_READINGS.inc()

    with PROCESSING_TIME.time():
        latest_reading["temperature"] = data.get("temperature", 0.0)
        latest_reading["vibration"] = data.get("vibration", 0.0)
        latest_reading["status"] = data.get("status", "UNKNOWN")
        latest_reading["timestamp"] = datetime.utcnow().isoformat()

        # Update Prometheus gauges so Grafana sees current values
        TEMPERATURE.set(latest_reading["temperature"])
        VIBRATION.set(latest_reading["vibration"])
        MACHINE_STATUS.set(STATUS_MAP.get(latest_reading["status"], -1))

    return {"received": True}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    """Prometheus scrapes this endpoint every few seconds.
    It returns all metrics in Prometheus text format."""
    return generate_latest()
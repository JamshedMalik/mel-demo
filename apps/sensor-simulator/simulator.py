import requests
import time
import random
import os
import math

# ──────────────────────────────────────────────
# Configuration via environment variables.
# In Kubernetes, these come from the ConfigMap.
# This is a platform engineering best practice:
# "Configure workloads externally, never hardcode."
# ──────────────────────────────────────────────
EDGE_SERVICE_URL = os.environ.get("EDGE_SERVICE_URL", "http://edge-service:8000")
INTERVAL = int(os.environ.get("INTERVAL", "5"))


def generate_reading(tick):
    """Generates realistic-looking sensor data.
    
    Uses sine waves + random noise to create patterns
    that look good on Grafana dashboards:
    - Temperature oscillates around 65°C (realistic for a machine)
    - Vibration oscillates around 2.5 mm/s
    - Status changes based on temperature thresholds
    - 5% chance of a random anomaly (spike) per reading
    """
    # Base temperature with sine wave pattern + noise
    base_temp = 65.0
    temp = base_temp + 10 * math.sin(tick / 20) + random.uniform(-3, 3)

    # Base vibration with different frequency + noise
    base_vib = 2.5
    vibration = base_vib + 1.5 * math.sin(tick / 15) + random.uniform(-0.5, 0.5)

    # Status based on thresholds
    if temp > 90:
        status = "ERROR"
    elif temp > 80:
        status = "WARNING"
    else:
        status = "RUNNING"

    # Random anomaly — creates interesting spikes on the dashboard
    if random.random() < 0.05:
        temp += random.uniform(15, 30)
        vibration += random.uniform(3, 6)
        status = "ERROR"

    return {
        "temperature": round(temp, 2),
        "vibration": round(vibration, 2),
        "status": status
    }


if __name__ == "__main__":
    print(f"Sensor simulator starting.")
    print(f"Target: {EDGE_SERVICE_URL}")
    print(f"Interval: {INTERVAL}s")

    tick = 0
    while True:
        reading = generate_reading(tick)
        try:
            r = requests.post(
                f"{EDGE_SERVICE_URL}/sensor-data",
                json=reading,
                timeout=5
            )
            print(f"[tick={tick}] Sent: {reading} -> {r.status_code}")
        except Exception as e:
            print(f"[tick={tick}] Error sending: {e}")

        tick += 1
        time.sleep(INTERVAL)
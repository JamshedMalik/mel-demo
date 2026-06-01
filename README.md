# Machine Edge Layer (MEL) — Platform Engineering Demo

A lightweight simulation of a Machine Edge Layer, demonstrating Platform Engineering
concepts on a single-node k3s cluster. Covers Kubernetes, Helm, observability with
Prometheus + Grafana, and edge computing architecture.

---

## What This Project Does

A Python **Sensor Simulator** mimics a factory machine, generating temperature, vibration,
and status readings every **5 seconds**. It sends this data to a **FastAPI Edge Service**
running inside Kubernetes (k3s). The edge service exposes metrics in Prometheus format,
which are scraped automatically and visualized on a **Grafana dashboard**.

**In one sentence:** Fake machine → sends data → API stores it → Prometheus collects it → Grafana shows it.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         k3s Cluster (Single Node)                    │
│                                                                      │
│   Namespace: mel-demo                    Namespace: monitoring        │
│  ┌────────────────────────────┐         ┌─────────────────────────┐  │
│  │                            │         │                         │  │
│  │  ┌──────────────────────┐  │         │  ┌───────────────────┐  │  │
│  │  │   Sensor Simulator   │  │         │  │    Prometheus     │  │  │
│  │  │   (Python Pod)       │  │         │  │    :30090         │  │  │
│  │  └──────────┬───────────┘  │    ┌───►│  │                   │  │  │
│  │             │               │    │    │  └─────────┬─────────┘  │  │
│  │    POST /sensor-data        │    │    │            │            │  │
│  │        every 5s             │    │    │      PromQL queries     │  │
│  │             │               │    │    │            │            │  │
│  │             ▼               │    │    │            ▼            │  │
│  │  ┌──────────────────────┐  │    │    │  ┌───────────────────┐  │  │
│  │  │    Edge Service      │  │    │    │  │     Grafana       │  │  │
│  │  │    FastAPI :8000     ├──┼────┘    │  │     :30300        │  │  │
│  │  │                      │  │ scrapes │  │                   │  │  │
│  │  │  /health             │  │ /metrics│  │  8 dashboard      │  │  │
│  │  │  /status             │  │ every   │  │  panels showing   │  │  │
│  │  │  /sensor-data        │  │ 10s     │  │  real-time data   │  │  │
│  │  │  /metrics            │  │         │  │                   │  │  │
│  │  │  NodePort :30080     │  │         │  └───────────────────┘  │  │
│  │  └──────────────────────┘  │         │                         │  │
│  │                            │         │                         │  │
│  └────────────────────────────┘         └─────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow (Step by Step)

```
Step 1          Step 2               Step 3              Step 4            Step 5
────────        ─────────            ─────────           ─────────         ─────────
Simulator       HTTP POST            Edge Service        Prometheus        Grafana
generates  ───► to /sensor-data ───► updates metrics ──► scrapes      ──► displays
fake data       every 5 seconds      (Gauges,            /metrics         dashboards
(temp,                               Counters,           every 10s        (8 panels)
vibration,                           Histograms)
status)
```

**Step 1 — Sensor Simulator** generates realistic data using sine waves + random noise:
- Temperature oscillates around 65°C (range ~55–85°C)
- Vibration oscillates around 2.5 mm/s
- 5% chance of a random anomaly (temperature spike) per reading

**Step 2 — HTTP POST** sends JSON to Edge Service:
```json
{"temperature": 72.13, "vibration": 3.75, "status": "RUNNING"}
```

**Step 3 — Edge Service** receives data and updates Prometheus metrics:
- Sets `machine_temperature_celsius` gauge to current value
- Sets `machine_vibration_mm_s` gauge to current value
- Sets `machine_status` gauge (0=ERROR, 1=WARNING, 2=RUNNING)
- Increments `sensor_readings_total` counter
- Records processing time in `sensor_processing_seconds` histogram

**Step 4 — Prometheus** scrapes the `/metrics` endpoint every 10 seconds,
stores all values as time-series data.

**Step 5 — Grafana** queries Prometheus using PromQL and displays:
- Temperature line chart with threshold colors (green/yellow/red)
- Vibration line chart
- Machine status indicator (RUNNING / WARNING / ERROR)
- Temperature gauge (0–120°C range)
- Total sensor readings counter
- HTTP requests per second by endpoint
- P95 processing latency
- Readings per minute

---

## Project Structure

```
mel-demo/
├── README.md                              ← You are here
│
├── apps/
│   ├── edge-service/
│   │   ├── main.py                        ← FastAPI app (4 endpoints, 6 Prometheus metrics)
│   │   ├── Dockerfile                     ← python:3.11-slim based image
│   │   └── requirements.txt               ← fastapi, uvicorn, prometheus-client
│   │
│   └── sensor-simulator/
│       ├── simulator.py                   ← Generates fake sensor data in a loop
│       ├── Dockerfile                     ← python:3.11-slim based image
│       └── requirements.txt               ← requests
│
├── helm/
│   └── mel-platform/
│       ├── Chart.yaml                     ← Chart metadata (name, version)
│       ├── values.yaml                    ← All configurable values in one place
│       └── templates/
│           ├── _helpers.tpl               ← Reusable label templates
│           ├── configmap.yaml             ← EDGE_SERVICE_URL + INTERVAL config
│           ├── edge-service-deployment.yaml     ← Deployment with probes + resource limits
│           ├── edge-service-service.yaml        ← NodePort service (30080 → 8000)
│           ├── sensor-simulator-deployment.yaml ← Conditional deployment (toggleable)
│           └── servicemonitor.yaml              ← Prometheus scrape target auto-discovery
│
├── monitoring/
│   ├── prometheus-values.yaml             ← Lightweight Prometheus Helm config
│   ├── grafana-values.yaml                ← Grafana Helm config with datasource
│   └── grafana-dashboard.json             ← Pre-built 8-panel dashboard (importable)
│
├── scripts/
│   └── cleanup.sh                         ← Full teardown: app → monitoring → k3s → images
│
└── docs/
    └── architecture.md                    ← Deep dive into K8s concepts and design decisions
```

---

## Technology Stack

| Component | Technology | Why This Choice |
|-----------|-----------|-----------------|
| Kubernetes | **k3s** | Lightweight (~512MB RAM), single binary, designed for edge. Same kubectl API as full K8s. |
| Application | **Python FastAPI** | Fast to develop, built-in OpenAPI docs, native Prometheus integration via prometheus-client. |
| Metrics Library | **prometheus-client** | Creates metrics in Prometheus text format. Zero-config, 3 lines to add a metric. |
| Deployment | **Helm 3** | Deployment-as-code. One values.yaml configures everything. Same pattern ArgoCD/GitOps uses. |
| Monitoring | **Prometheus** | Pull-based metrics (firewall-friendly for edge). De facto Kubernetes monitoring standard. |
| Dashboards | **Grafana** | Rich visualization, auto-refresh, threshold alerting. Queries Prometheus via PromQL. |

---

## Design Decisions

### Why k3s instead of full Kubernetes?
k3s is purpose-built for edge and IoT. It's a **single binary (~60MB)**, uses **~512MB RAM**,
and ships with containerd. This is exactly what you'd run on a real factory machine or
industrial edge device. Full K8s would need 2–4GB RAM — unacceptable at the edge.

### Why FastAPI?
Lightweight ASGI framework that starts in under 1 second. The `prometheus-client` library
integrates in 3 lines of code — no middleware or adapters needed. Built-in `/docs` endpoint
gives you free Swagger UI for testing.

### Why Helm instead of plain kubectl apply?
Helm makes deployments **configurable and reproducible**. The same chart deploys to dev,
staging, and production by swapping `values.yaml`. Components are toggleable:
set `sensorSimulator.enabled: false` and the simulator disappears. This is how real
platform teams package their services.

### Why Prometheus + Grafana?
Industry standard for Kubernetes observability. Prometheus's **pull model** means the edge
service doesn't need outbound internet access — Prometheus reaches in, not out. This is
critical for factory environments behind firewalls.

### Why NodePort instead of Ingress?
On a single-node edge deployment, NodePort is appropriate and honest. Adding Ingress
(Traefik, certs, DNS) adds complexity without value for a single service. In production
with multiple services, you'd add an Ingress controller.

### Why images built locally instead of a registry?
With `imagePullPolicy: Never`, k3s uses images already on the node. No registry
infrastructure needed. On a real edge device, you'd pre-load images during provisioning.

---

## Kubernetes Concepts Demonstrated

| Concept | Where | What It Proves |
|---------|-------|----------------|
| **Deployment** | edge-service, sensor-simulator | Declarative pod management. Pod dies → Deployment recreates it. |
| **Service (NodePort)** | edge-service-service.yaml | Makes pods reachable from outside the cluster on port 30080. |
| **ConfigMap** | mel-config | Configuration injected as env vars. Change config without rebuilding images. |
| **Namespace** | mel-demo, monitoring | Logical isolation. `kubectl delete ns mel-demo` cleanly removes everything. |
| **Labels & Selectors** | All resources | How K8s connects Services to Pods and Prometheus to scrape targets. |
| **Liveness Probe** | edge-service → GET /health | If /health fails 3x, K8s kills and restarts the pod. Self-healing. |
| **Readiness Probe** | edge-service → GET /health | Holds traffic until the pod is ready. Prevents routing to a starting container. |
| **Resource Requests/Limits** | All deployments | Requests = guaranteed minimum. Limits = hard cap. Critical on resource-constrained edge. |
| **Helm Values** | values.yaml → templates/ | One config file drives all Kubernetes manifests. Environment-specific overrides. |
| **Conditional Templates** | sensor-simulator | `{{- if .Values.sensorSimulator.enabled }}` — platform teams provide toggleable components. |

---

## Prometheus Metrics Reference

| Type | Metric | What It Measures |
|------|--------|-----------------|
| **Counter** | `edge_http_requests_total` | Total HTTP requests, labeled by method and endpoint. Only goes up. |
| **Counter** | `sensor_readings_total` | Total sensor readings received from the simulator. |
| **Gauge** | `machine_temperature_celsius` | Current machine temperature. Goes up and down. |
| **Gauge** | `machine_vibration_mm_s` | Current vibration level in mm/s. |
| **Gauge** | `machine_status` | Current status: 0=ERROR, 1=WARNING, 2=RUNNING. |
| **Histogram** | `sensor_processing_seconds` | Processing time distribution. Enables P50/P95/P99 latency calculation. |

**Why these types matter:**
- **Counter** → use `rate()` in PromQL to get requests/second
- **Gauge** → direct value, shows current state
- **Histogram** → use `histogram_quantile()` to get percentile latencies

---

## Quick Commands

```bash
# ── Cluster Status ──
kubectl get nodes                    # Is the node Ready?
kubectl get pods -A                  # Everything running across all namespaces

# ── Application ──
kubectl get pods -n mel-demo         # Are edge-service and simulator running?
kubectl logs -f deploy/edge-service -n mel-demo       # Live API logs
kubectl logs -f deploy/sensor-simulator -n mel-demo   # Live simulator logs
kubectl describe pod -l app=edge-service -n mel-demo  # Detailed pod info

# ── Monitoring ──
kubectl get pods -n monitoring       # Prometheus and Grafana running?

# ── Test API Endpoints ──
curl http://localhost:30080/health   # Should return {"status": "healthy", ...}
curl http://localhost:30080/status   # Latest sensor reading
curl http://localhost:30080/metrics  # Raw Prometheus metrics

# Post a manual reading:
curl -X POST http://localhost:30080/sensor-data \
  -H "Content-Type: application/json" \
  -d '{"temperature": 95.0, "vibration": 8.5, "status": "ERROR"}'

# ── Helm ──
helm list -A                                          # All releases
helm upgrade mel helm/mel-platform -n mel-demo        # Apply changes
helm rollback mel 1 -n mel-demo                       # Rollback to revision 1
helm template mel helm/mel-platform -n mel-demo       # Render without installing
```

---

## Access the UIs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Grafana** | `http://<VPS-IP>:30300` | admin / mel-demo-2026 |
| **Prometheus** | `http://<VPS-IP>:30090` | — |
| **Edge Service API** | `http://<VPS-IP>:30080` | — |
| **Swagger Docs** | `http://<VPS-IP>:30080/docs` | — |

---

## Cleanup

Remove everything and restore the VPS to its pre-demo state:

```bash
chmod +x scripts/cleanup.sh
./scripts/cleanup.sh
```

This removes: Helm releases → Kubernetes namespaces → k3s → Helm binary → Docker images.
Your existing services (n8n, etc.) are not touched.

---

## What Would Change for Production

| Concern | This Demo | Production |
|---------|-----------|------------|
| **Security** | No auth, no RBAC | RBAC, Network Policies, Sealed Secrets, TLS |
| **High Availability** | Single node, single replica | Multi-node cluster, pod anti-affinity, 3+ replicas |
| **Storage** | In-memory, ephemeral | PersistentVolumeClaims for Prometheus TSDB |
| **CI/CD** | Manual `helm install` | GitHub Actions → build → push → deploy pipeline |
| **GitOps** | Manual deployment | ArgoCD watching Git repo, auto-sync on push |
| **Alerting** | None | Alertmanager → PagerDuty / Slack / email |
| **Logging** | `kubectl logs` only | Loki + Promtail, or EFK stack |
| **Service Mesh** | None | Istio / Linkerd for mTLS and traffic management |
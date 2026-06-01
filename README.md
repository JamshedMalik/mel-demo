# MEL Platform Engineering Demo

A hands-on demo of **Machine Edge Layer (MEL)** platform engineering — simulating a factory machine sending sensor data to a FastAPI edge service running on k3s, monitored by Prometheus and Grafana.

---

## What This Demo Does

A Python **Sensor Simulator** mimics a factory machine generating temperature, vibration, and status readings. It POSTs that data every 2 seconds to a **FastAPI Edge Service** running in Kubernetes (k3s). The edge service exposes Prometheus metrics, which are scraped and visualized in **Grafana**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        k3s Cluster                              │
│                                                                 │
│   Namespace: mel-demo                Namespace: monitoring      │
│  ┌──────────────────────────┐       ┌───────────────────────┐  │
│  │  ┌────────────────────┐  │       │  ┌─────────────────┐  │  │
│  │  │  Sensor Simulator  │  │       │  │   Prometheus    │  │  │
│  │  │  (Python / Pod)    │  │  ┌───►│  │  :30090         │  │  │
│  │  └────────┬───────────┘  │  │   │  └────────┬────────┘  │  │
│  │           │ POST /data   │  │   │           │ query     │  │
│  │           ▼              │  │   │           ▼           │  │
│  │  ┌────────────────────┐  │  │   │  ┌─────────────────┐  │  │
│  │  │   Edge Service     │  │  │   │  │     Grafana     │  │  │
│  │  │   FastAPI :8000    ├──┼──┘   │  │  :30300         │  │  │
│  │  │   /metrics         │  │scrape│  └─────────────────┘  │  │
│  │  │   NodePort :30080  │  │      └───────────────────────┘  │
│  │  └────────────────────┘  │                                  │
│  └──────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

1. **Simulator generates data** — random temperature (60–100°C), vibration (0–10 mm/s), and machine status (0=ERROR, 1=WARNING, 2=RUNNING)
2. **POSTs to edge service** — HTTP POST to `http://edge-service:8000/sensor-data` every 5 seconds
3. **Edge service updates Prometheus metrics** — increments counters, sets gauges, records histogram observations
4. **Prometheus scrapes `/metrics`** — every 10 seconds via ServiceMonitor CRD
5. **Grafana visualizes** — dashboards query Prometheus for real-time and historical views

---

## Project Structure

```
mel-demo/
├── apps/
│   ├── edge-service/
│   │   ├── main.py              # FastAPI app with Prometheus instrumentation
│   │   ├── Dockerfile           # Multi-stage build for edge service
│   │   └── requirements.txt     # FastAPI, uvicorn, prometheus-client
│   └── sensor-simulator/
│       ├── simulator.py         # Generates and POSTs fake sensor readings
│       ├── Dockerfile           # Lightweight Python image
│       └── requirements.txt     # requests library
├── helm/
│   └── mel-platform/
│       ├── Chart.yaml           # Helm chart metadata
│       ├── values.yaml          # Configurable defaults (image tags, replicas, ports)
│       └── templates/
│           ├── _helpers.tpl     # Reusable name/label helpers
│           ├── configmap.yaml   # Injects EDGE_SERVICE_URL into simulator pod
│           ├── edge-service-deployment.yaml    # Deployment with probes + limits
│           ├── edge-service-service.yaml       # NodePort service on 30080
│           ├── sensor-simulator-deployment.yaml # Simulator deployment
│           └── servicemonitor.yaml             # Tells Prometheus to scrape edge service
├── monitoring/
│   ├── prometheus-values.yaml   # Helm values for kube-prometheus-stack
│   ├── grafana-values.yaml      # Grafana admin credentials, NodePort config
│   └── grafana-dashboard.json   # Pre-built dashboard for sensor metrics
├── docs/
│   └── architecture.md          # Deep-dive into K8s concepts and design
├── scripts/
│   └── cleanup.sh               # Tears down everything cleanly
└── README.md
```

---

## Technology Stack

| Technology | Version | Role |
|---|---|---|
| k3s | v1.28+ | Lightweight Kubernetes for edge/single-node |
| FastAPI | 0.104+ | Edge service HTTP API |
| prometheus-client | 0.19+ | Exposes `/metrics` from Python |
| Helm 3 | v3.13+ | Package and deploy K8s manifests |
| Prometheus | 2.47+ | Metrics scraping and storage |
| Grafana | 10.x | Metrics visualization and dashboards |

---

## Design Decisions

### Why k3s?
Edge-native Kubernetes distribution. Runs in **512MB RAM**, single binary, ships with containerd. Perfect for factory-floor hardware, Raspberry Pi, or demo VMs. Same `kubectl` API as full K8s.

### Why FastAPI?
Lightweight ASGI framework with **native async support** and automatic OpenAPI docs. `prometheus-client` integrates in 3 lines. Starts in under 1 second — critical for edge responsiveness.

### Why Helm?
**Deployment-as-code.** A single `helm install` with `values.yaml` overrides deploys the full platform. Enables environment-specific configs (dev/staging/prod) without duplicating manifests. The pattern that GitOps tools like ArgoCD consume.

### Why Prometheus + Grafana?
**Industry standard** for Kubernetes observability. Prometheus's pull model is firewall-friendly (edge service doesn't need outbound internet). Grafana's PromQL support enables powerful dashboards with zero code.

### Why NodePort?
**Single-node edge deployment** — no external load balancer needed. NodePort exposes services directly on the host IP, which is how you'd access services on an air-gapped factory machine. In a multi-node cluster you'd use LoadBalancer or Ingress.

---

## Kubernetes Concepts Demonstrated

| Concept | Where Used | What It Shows |
|---|---|---|
| Deployment | edge-service, sensor-simulator | Self-healing pods, rolling updates |
| Service (NodePort) | edge-service-service.yaml | Exposes pod to host network |
| ConfigMap | mel-config | Injects config into pods as env vars |
| Namespace | mel-demo, monitoring | Resource isolation between app and infra |
| Labels & Selectors | All resources | How Services find Pods |
| Liveness Probe | edge-service | K8s restarts pod if app hangs |
| Readiness Probe | edge-service | K8s holds traffic until app is ready |
| Resource Requests/Limits | Both deployments | Prevents noisy-neighbour resource exhaustion |
| Helm Values/Templates | helm/mel-platform/ | Parameterised, reusable manifests |

---

## Prometheus Metric Types

| Type | Metric Name | Description |
|---|---|---|
| Counter | `edge_http_requests_total` | Total HTTP requests received by edge service |
| Counter | `sensor_readings_total` | Total sensor data points processed |
| Gauge | `machine_temperature_celsius` | Current machine temperature reading |
| Gauge | `machine_vibration_mm_s` | Current vibration level in mm/s |
| Gauge | `machine_status` | Machine state: 0=ERROR, 1=WARNING, 2=RUNNING |
| Histogram | `sensor_processing_seconds` | Time taken to process each sensor reading |

---

## Quick Commands

### Check running pods
```bash
kubectl get pods -n mel-demo
kubectl get pods -n monitoring
```

### View edge service logs
```bash
kubectl logs -n mel-demo deployment/edge-service -f
```

### View simulator logs
```bash
kubectl logs -n mel-demo deployment/sensor-simulator -f
```

### Hit the API manually
```bash
curl http://localhost:30080/health
curl http://localhost:30080/status
curl http://localhost:30080/metrics
curl -X POST http://localhost:30080/sensor-data \
  -H "Content-Type: application/json" \
  -d '{"temperature": 75.5, "vibration": 3.2, "status": "RUNNING"}'
```

### Helm operations
```bash
# See deployed releases
helm list -A

# Upgrade with new values
helm upgrade mel ./helm/mel-platform -n mel-demo

# Render templates without installing
helm template mel ./helm/mel-platform -n mel-demo
```

### Access UIs
| Service | URL | Credentials |
|---|---|---|
| Grafana | http://\<NODE-IP\>:30300 | admin / mel-demo-2026 |
| Prometheus | http://\<NODE-IP\>:30090 | — |
| Edge Service API | http://\<NODE-IP\>:30080 | — |
| API Docs (Swagger) | http://\<NODE-IP\>:30080/docs | — |

---

## Cleanup

To tear down everything:
```bash
chmod +x scripts/cleanup.sh
./scripts/cleanup.sh
```

See [scripts/cleanup.sh](scripts/cleanup.sh) for what it does step by step.

---

## What Would Change for Production

| Concern | Demo Approach | Production Approach |
|---|---|---|
| Security | No auth | RBAC, Network Policies, mTLS via service mesh |
| High Availability | Single replica | Multi-replica Deployments, multi-node cluster |
| Storage | Ephemeral | PersistentVolumeClaims for Prometheus TSDB |
| CI/CD | Manual `helm install` | GitHub Actions / GitLab CI pipeline |
| GitOps | None | ArgoCD syncing from Git to cluster |
| Alerting | None | Alertmanager rules → PagerDuty / Slack |
| Logging | `kubectl logs` | Loki + Promtail stack, or EFK |
| Service Mesh | None | Istio / Linkerd for observability + mTLS |

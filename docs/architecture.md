# MEL Platform — Architecture Deep Dive

This document explains every component and how they connect.
Use it to prepare for interview questions.

---

## Component Interaction Flow

```
                      SENSOR SIMULATOR
                      ┌──────────────────┐
                      │  Python script    │
                      │                   │
                      │  Generates:       │
                      │  • temperature    │
                      │  • vibration      │
                      │  • status         │
                      │                   │
                      │  Using:           │
                      │  sine waves +     │
                      │  random noise +   │
                      │  5% anomaly chance│
                      └────────┬─────────┘
                               │
                      POST /sensor-data
                      JSON body, every 5s
                               │
                               ▼
                      EDGE SERVICE (FastAPI)
                      ┌──────────────────────────────────┐
                      │                                   │
                      │  POST /sensor-data                │
                      │    → receives JSON                │
                      │    → stores in memory             │
                      │    → updates Prometheus metrics   │
                      │                                   │
                      │  GET /health                      │
                      │    → K8s liveness/readiness probe │
                      │    → returns {"status":"healthy"} │
                      │                                   │
                      │  GET /status                      │
                      │    → returns latest sensor reading│
                      │                                   │
                      │  GET /metrics                     │
                      │    → Prometheus scrapes this      │
                      │    → returns all metrics in       │
                      │      Prometheus text format       │
                      └──────────────┬───────────────────┘
                                     │
                      Prometheus scrapes /metrics
                      every 10 seconds
                                     │
                                     ▼
                      PROMETHEUS
                      ┌──────────────────────────────────┐
                      │  Time-series database             │
                      │                                   │
                      │  Stores these metrics over time:  │
                      │  • machine_temperature_celsius    │
                      │  • machine_vibration_mm_s         │
                      │  • machine_status                 │
                      │  • sensor_readings_total          │
                      │  • edge_http_requests_total       │
                      │  • sensor_processing_seconds      │
                      │                                   │
                      │  Retention: 2 hours               │
                      │  Scrape interval: 10 seconds      │
                      └──────────────┬───────────────────┘
                                     │
                      Grafana queries Prometheus
                      using PromQL language
                                     │
                                     ▼
                      GRAFANA
                      ┌──────────────────────────────────┐
                      │  8 Dashboard Panels:              │
                      │                                   │
                      │  1. Temperature line chart        │
                      │  2. Vibration line chart          │
                      │  3. Machine status indicator      │
                      │  4. Temperature gauge             │
                      │  5. Total readings counter        │
                      │  6. HTTP requests/sec             │
                      │  7. P95 processing latency        │
                      │  8. Readings per minute           │
                      │                                   │
                      │  Auto-refreshes every 5 seconds   │
                      └──────────────────────────────────┘
```

---

## Kubernetes Resource Map

```
CLUSTER: k3s (single node)
│
├── Namespace: mel-demo
│   │
│   ├── Deployment: edge-service (1 replica)
│   │   └── Pod: edge-service-xxxxx
│   │       └── Container: edge-service
│   │           ├── Image: mel-edge-service:latest
│   │           ├── Port: 8000
│   │           ├── Liveness Probe:  GET /health every 15s
│   │           ├── Readiness Probe: GET /health every 10s
│   │           ├── CPU: 50m request / 200m limit
│   │           └── RAM: 64Mi request / 128Mi limit
│   │
│   ├── Deployment: sensor-simulator (1 replica, conditional)
│   │   └── Pod: sensor-simulator-xxxxx
│   │       └── Container: sensor-simulator
│   │           ├── Image: mel-sensor-simulator:latest
│   │           ├── Env from: ConfigMap/mel-config
│   │           ├── CPU: 25m request / 100m limit
│   │           └── RAM: 32Mi request / 64Mi limit
│   │
│   ├── Service: edge-service
│   │   ├── Type: NodePort
│   │   ├── Port: 8000
│   │   ├── NodePort: 30080
│   │   └── Selector: app=edge-service
│   │
│   ├── ConfigMap: mel-config
│   │   ├── EDGE_SERVICE_URL = http://edge-service:8000
│   │   └── INTERVAL = 5
│   │
│   └── ServiceMonitor: edge-service-monitor
│       ├── Selector: app=edge-service
│       ├── Path: /metrics
│       └── Interval: 10s
│
└── Namespace: monitoring
    │
    ├── Deployment: prometheus-server
    │   └── Pod: prometheus-server-xxxxx
    │       └── Scrapes: edge-service.mel-demo.svc.cluster.local:8000/metrics
    │
    └── Deployment: grafana
        └── Pod: grafana-xxxxx
            └── Datasource: http://prometheus-server.monitoring.svc.cluster.local
```

---

## How Each Kubernetes Concept Works Here

### Deployment → ReplicaSet → Pod

```
Deployment (edge-service)
  "I want 1 replica of this container"
       │
       ▼
ReplicaSet (edge-service-577748ffcd)
  "I maintain exactly 1 pod matching this template"
       │
       ▼
Pod (edge-service-577748ffcd-tsnfw)
  "I run the container"
```

If the Pod crashes, the ReplicaSet creates a new one. This is **self-healing**.
If you change the image tag, the Deployment creates a new ReplicaSet and
gradually shifts traffic. This is a **rolling update**.

### Service → Pod Connection

```
External request: http://VPS_IP:30080
       │
       ▼
Service: edge-service (NodePort 30080)
  selector: app=edge-service
       │
       │  finds all pods with label app=edge-service
       ▼
Pod: edge-service-xxxxx (port 8000)
```

The Service doesn't know the Pod's IP. It uses **label selectors** to find matching Pods.
If you scale to 3 replicas, the Service automatically load-balances across all 3.

### ConfigMap → Environment Variables

```
ConfigMap: mel-config                    Pod: sensor-simulator
┌────────────────────────────┐          ┌────────────────────────┐
│ EDGE_SERVICE_URL:          │          │ envFrom:               │
│   http://edge-service:8000 │ ────────►│   configMapRef:        │
│ INTERVAL: 5                │          │     name: mel-config   │
└────────────────────────────┘          └────────────────────────┘
                                         │
                                         ▼
                                        Inside the container:
                                        $ echo $EDGE_SERVICE_URL
                                        http://edge-service:8000
                                        $ echo $INTERVAL
                                        5
```

Change the ConfigMap → restart the pod → new config takes effect.
**No image rebuild needed.** This is externalized configuration.

### Liveness vs Readiness Probes

```
Liveness Probe:                         Readiness Probe:
"Is this container alive?"              "Can this container handle traffic?"

GET /health every 15s                   GET /health every 10s

If fails 3 times:                       If fails:
  → K8s KILLS the pod                     → K8s REMOVES pod from Service
  → ReplicaSet creates a new one          → No traffic routed to it
  → This is self-healing                  → Pod stays alive (not killed)
                                          → Once healthy again, traffic resumes
```

**Why both?** A pod can be alive but not ready. Example: the app is running but
still loading data. Liveness says "it's alive", readiness says "not yet, wait".

### Resource Requests vs Limits

```
Requests (guaranteed minimum):          Limits (hard maximum):
  cpu: 50m    (5% of one core)            cpu: 200m    (20% of one core)
  memory: 64Mi                            memory: 128Mi

Scheduler uses REQUESTS to place pods.  If pod exceeds LIMIT:
"Does this node have 50m CPU and          CPU: throttled (slowed down)
 64Mi RAM available?"                     Memory: OOMKilled (pod killed)
```

**Why this matters on edge:** Factory machines have limited resources. You share
hardware with the machine control system. Resource limits prevent your monitoring
stack from starving the actual machine software.

### Helm Values → Templates Flow

```
values.yaml                              templates/edge-service-deployment.yaml
┌──────────────────────────┐            ┌─────────────────────────────────────┐
│ edgeService:             │            │ apiVersion: apps/v1                 │
│   replicaCount: 1        │───────────►│ spec:                              │
│   image:                 │            │   replicas: {{ .Values.            │
│     repository: mel-...  │───────────►│     edgeService.replicaCount }}    │
│     tag: latest          │            │   containers:                      │
│   resources:             │            │     image: "{{ .Values.            │
│     requests:            │───────────►│       edgeService.image.repo }}:   │
│       cpu: 50m           │            │       {{ .Values...tag }}"        │
│       memory: 64Mi       │            │     resources:                     │
└──────────────────────────┘            │       {{ .Values...resources }}    │
                                        └─────────────────────────────────────┘

One values file → generates all Kubernetes manifests.
Different environment? Different values file. Same templates.
```

---

## Network Architecture

### External Access (Browser → Service)

```
Your Browser
    │
    │  http://62.84.187.124:30080
    │
    ▼
VPS Host Network
    │
    │  NodePort 30080
    ▼
k3s iptables rule
    │
    │  forwards to ClusterIP
    ▼
Service: edge-service (ClusterIP 10.43.x.x:8000)
    │
    │  label selector: app=edge-service
    ▼
Pod: edge-service-xxxxx (port 8000)
```

### Internal Access (Pod → Pod via DNS)

```
sensor-simulator pod
    │
    │  http://edge-service:8000/sensor-data
    │
    │  "edge-service" is resolved by CoreDNS:
    │  edge-service → edge-service.mel-demo.svc.cluster.local
    │  → ClusterIP 10.43.x.x
    ▼
Service: edge-service → Pod: edge-service-xxxxx
```

Kubernetes has built-in DNS. Any Service name is resolvable from any Pod in the cluster.
This is **service discovery** — pods don't need to know each other's IPs.

---

## What "Platform Engineering" Means in This Demo

Platform Engineering = building a self-service platform that application
developers deploy and operate their workloads on.

**What the platform provides (infrastructure team):**
1. Kubernetes cluster (k3s) — managed compute
2. Helm chart structure — standardized deployment method
3. Observability pipeline — Prometheus + Grafana, pre-configured
4. Health checks — liveness/readiness probes built into templates
5. Resource management — limits enforced, preventing runaway pods

**What the app developer provides:**
1. FastAPI application code (main.py)
2. Dockerfile
3. Prometheus metrics in the code

**Everything else is handled by the platform.** The developer doesn't configure
Prometheus, doesn't set up Grafana, doesn't write Kubernetes manifests from scratch.
They fill in `values.yaml` and the platform does the rest.

This separation of concerns is the core of Platform Engineering.
# NetWeaver: Self-Optimizing Autonomous Network Infrastructure Platform

<p align="center">
  <strong>Version</strong>: 2.0.0 &nbsp;|&nbsp;
  <strong>Status</strong>: Phase 2 Complete &nbsp;|&nbsp;
  <strong>License</strong>: MIT
</p>

---

## Overview

NetWeaver is a production-grade autonomous network infrastructure platform that transforms how enterprise networks are managed. It combines real-time telemetry collection, machine learning traffic prediction, intent-based policy management, autonomous self-healing, and security threat detection into a unified microservices architecture.

### Key Capabilities

| Capability | Description | Status |
|---|---|---|
| **Telemetry Collection** | NetFlow/sFlow/IPFIX at 1M+ flows/sec | Phase 1 ✅ |
| **ML Traffic Prediction** | LSTM & Transformer forecasting models | Phase 1 ✅ |
| **Routing Optimization** | Dijkstra, ECMP, K-shortest paths | Phase 1 ✅ |
| **Intent-Based Networking** | YAML policies → vendor configs | Phase 2 ✅ |
| **Multi-Vendor Device Mgmt** | Cisco, Juniper, Arista unified API | Phase 2 ✅ |
| **Self-Healing** | Auto failure detection & remediation | Phase 2 ✅ |
| **Security Agent** | DDoS detection, ML anomaly detection | Phase 2 ✅ |
| **API Gateway** | JWT auth, rate limiting, request routing | Phase 2 ✅ |
| **Web Dashboard** | React 18 + Material-UI monitoring UI | Phase 2 ✅ |
| **Kubernetes Deployment** | Production-ready K8s manifests | Phase 2 ✅ |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         NetWeaver Platform v2.0                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐                │
│   │   Web UI     │   │  API Gateway │   │  WebSocket   │                │
│   │  (React 18)  │──>│  (FastAPI)   │──>│  Real-time   │                │
│   │  Port 3000   │   │  Port 8080   │   │  Updates     │                │
│   └─────────────┘   └──────┬───────┘   └──────────────┘                │
│                             │                                            │
│              ┌──────────────┼──────────────┬──────────────┐              │
│              v              v              v              v              │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│   │Intent Engine │ │Device Manager│ │ Self-Healing  │ │Security Agent│  │
│   │   (Go/Gin)   │ │  (FastAPI)   │ │   (Go/Gin)   │ │  (FastAPI)   │  │
│   │  Port 8081   │ │  Port 8083   │ │  Port 8082   │ │  Port 8084   │  │
│   │              │ │              │ │              │ │              │  │
│   │- NLP Parser  │ │- Cisco IOS   │ │- Failure Det.│ │- DDoS Detect │  │
│   │- Translator  │ │- Juniper     │ │- Remediator  │ │- ML Anomaly  │  │
│   │- Compliance  │ │- Arista EOS  │ │- Auto-Heal   │ │- Mitigator   │  │
│   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘  │
│          │                │                │                │          │
│   ┌──────┴────────────────┴────────────────┴────────────────┴───────┐  │
│   │                    Infrastructure Layer                         │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │  │
│   │  │ TimescaleDB   │  │  RabbitMQ    │  │    Redis     │          │  │
│   │  │  Port 5432    │  │  Port 5672   │  │  Port 6379   │          │  │
│   │  │  12 tables    │  │  Event bus   │  │  Rate limit  │          │  │
│   │  │  7 hypertables│  │  Telemetry Q │  │  Caching     │          │  │
│   │  └──────────────┘  └──────────────┘  └──────────────┘          │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    Phase 1 Foundation                           │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │  │
│   │  │Telemetry Agent│  │ ML Predictor │  │  Optimizer   │          │  │
│   │  │  (Go)         │  │  (Python)    │  │  (Go)        │          │  │
│   │  │  NetFlow/sFlow│  │  LSTM/Transf.│  │  Dijkstra    │          │  │
│   │  │  LLDP/CDP     │  │  Forecasting │  │  K-paths     │          │  │
│   │  └──────────────┘  └──────────────┘  └──────────────┘          │  │
│   └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
NetWeaver/
├── cmd/                            # Phase 1 - Main Go applications
│   ├── telemetry-agent/            #   NetFlow/sFlow collector entry point
│   ├── predictor/                  #   ML prediction service
│   └── optimizer/                  #   Routing optimization service
│
├── pkg/                            # Phase 1 - Shared Go packages
│   ├── netflow/                    #   NetFlow v5/v9/IPFIX parser
│   ├── sflow/                      #   sFlow v5 parser
│   ├── topology/                   #   Network topology graph management
│   ├── database/                   #   TimescaleDB interface & schema
│   ├── routing/                    #   Dijkstra, ECMP, K-paths algorithms
│   └── config/                     #   Multi-vendor config generation
│
├── python/                         # Phase 1 - Python ML components
│   ├── models/                     #   LSTM & Transformer architectures
│   ├── training/                   #   Model training pipeline
│   └── inference/                  #   Real-time prediction service
│
├── services/                       # Phase 2 - Microservices
│   ├── api-gateway/                #   Unified API Gateway (FastAPI)
│   │   ├── main.py                 #     JWT auth, rate limiting, routing
│   │   ├── Dockerfile              #     Multi-stage Docker build
│   │   └── requirements.txt        #     Python dependencies
│   │
│   ├── intent-engine/              #   Intent-Based Networking (Go/Gin)
│   │   ├── main.go                 #     Server entry point
│   │   ├── internal/
│   │   │   ├── api/handlers.go     #     REST API handlers
│   │   │   ├── engine/
│   │   │   │   ├── intent_engine.go #    Core intent processing
│   │   │   │   ├── parser.go       #     YAML/NLP policy parser
│   │   │   │   └── translator.go   #     Multi-vendor config translator
│   │   │   └── storage/postgres.go #     PostgreSQL persistence
│   │   └── examples/               #     Sample intent YAML files
│   │
│   ├── device-manager/             #   Multi-Vendor Device Mgmt (FastAPI)
│   │   ├── main.py                 #     Device CRUD, config deployment
│   │   ├── connectors.py           #     SSH/NETCONF/eAPI connectors
│   │   └── Dockerfile
│   │
│   ├── self-healing/               #   Autonomous Self-Healing (Go/Gin)
│   │   ├── main.go                 #     Server & lifecycle management
│   │   ├── internal/
│   │   │   ├── detector/           #     Failure detection engine
│   │   │   ├── remediator/         #     Automated remediation
│   │   │   └── storage/            #     Incident persistence
│   │   └── Dockerfile
│   │
│   ├── security-agent/             #   Security & DDoS Detection (FastAPI)
│   │   ├── main.py                 #     Security service entry point
│   │   ├── detector/
│   │   │   ├── ddos_detector.py    #     Flow-based DDoS detection
│   │   │   └── anomaly_detector.py #     ML Isolation Forest anomaly detection
│   │   ├── mitigator/
│   │   │   └── mitigator.py        #     Threat mitigation (ACL, blackhole)
│   │   └── storage/
│   │       └── postgres.py         #     Threat/attack persistence
│   │
│   └── web-ui/                     #   Web Dashboard (React 18 + Vite)
│       ├── index.html              #     Vite entry point
│       ├── vite.config.ts          #     Vite configuration
│       ├── package.json            #     Dependencies (Material-UI, Recharts)
│       └── src/
│           ├── App.tsx             #     Main app with routing
│           ├── pages/              #     Dashboard, Intents, Devices, etc.
│           ├── components/         #     Reusable UI components
│           └── services/api.ts     #     API client service
│
├── k8s/                            # Kubernetes deployment manifests
│   ├── 00-namespace-and-config.yaml
│   ├── 01-timescaledb.yaml
│   ├── 02-rabbitmq.yaml
│   ├── 03-redis.yaml
│   ├── 04-intent-engine.yaml
│   ├── 05-device-manager.yaml
│   ├── 06-self-healing.yaml
│   ├── 07-security-agent.yaml
│   ├── 08-api-gateway.yaml
│   ├── 09-web-ui.yaml
│   └── 10-ingress.yaml
│
├── tests/                          # Integration test suite
│   └── integration/
│       └── test_api_gateway.py     #   18+ pytest integration tests
│
├── simulator/                      # Network simulator (100-node testbed)
├── configs/                        # Configuration files
├── deployments/                    # Docker Compose files
├── scripts/                        # Utility scripts
└── docker-compose-phase2.yml       # Full stack Docker Compose
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend (Go)** | Go 1.21, Gin, lib/pq | Telemetry, Intent Engine, Self-Healing |
| **Backend (Python)** | Python 3.11, FastAPI, Uvicorn | API Gateway, Device Manager, Security Agent |
| **ML/AI** | PyTorch, scikit-learn, NumPy | LSTM/Transformer prediction, Isolation Forest anomaly detection |
| **Frontend** | React 18, TypeScript, Vite, Material-UI 5 | Web dashboard with real-time monitoring |
| **Database** | TimescaleDB (PostgreSQL 15) | Time-series metrics, 12 tables, 7 hypertables |
| **Messaging** | RabbitMQ 3 | Event-driven telemetry & threat detection |
| **Caching** | Redis 7 | Rate limiting, session cache |
| **Containers** | Docker, Docker Compose | Development & production deployment |
| **Orchestration** | Kubernetes | Production deployment (11 manifest files) |
| **Auth** | JWT (PyJWT) | API authentication & authorization |

---

## Quick Start

### Prerequisites

- **Go** 1.21+
- **Python** 3.11+
- **Node.js** 18+
- **Docker** & **Docker Compose**

### 1. Clone & Start Infrastructure

```bash
git clone https://github.com/reshwanthmanupati/NetWeaver.git
cd NetWeaver

# Start all services with Docker Compose
docker-compose -f docker-compose-phase2.yml up -d
```

This starts:

| Service | Port | Description |
|---|---|---|
| TimescaleDB | 5432 | PostgreSQL with time-series extensions |
| RabbitMQ | 5672 / 15672 | Message broker (management UI on 15672) |
| Redis | 6379 | Rate limiting & caching |
| API Gateway | 8080 | Unified entry point with JWT auth |
| Intent Engine | 8081 | Intent-based networking (Go/Gin) |
| Self-Healing | 8082 | Autonomous failure detection (Go/Gin) |
| Device Manager | 8083 | Multi-vendor device management |
| Security Agent | 8084 | DDoS & anomaly detection |
| Web UI | 3000 | React dashboard |

### 2. Verify Services

```bash
# Check all services are healthy
curl http://localhost:8080/health

# Expected response:
# {
#   "status": "healthy",
#   "services": {
#     "intent_engine": "healthy",
#     "device_manager": "healthy",
#     "self_healing": "healthy",
#     "security_agent": "healthy"
#   }
# }
```

### 3. Authenticate

```bash
# Get JWT token
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' | jq -r '.access_token')

echo $TOKEN
```

### 4. Start Using the Platform

```bash
# Create an intent policy
curl -X POST http://localhost:8080/api/v1/intents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "video-low-latency",
    "description": "Ensure low latency for video traffic",
    "policy_type": "latency",
    "policy": "type: latency\nconstraints:\n  - metric: latency\n    operator: <\n    value: 50\n    unit: ms",
    "targets": ["router-edge-01"]
  }'

# Register a network device
curl -X POST http://localhost:8080/api/v1/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "router-edge-01",
    "vendor": "cisco_ios",
    "model": "ISR4451",
    "version": "16.12.4",
    "ip_address": "192.168.1.1",
    "username": "admin",
    "password": "password"
  }'

# View security threats
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/threats

# Get aggregated dashboard
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/dashboard
```

---

## Development Setup

### Web UI (Local Development)

```bash
cd services/web-ui
npm install
npm run dev
# Opens at http://localhost:3000 with hot-reload
```

### Run Integration Tests

```bash
# Start services first, then:
cd tests/integration
pip install pytest httpx
pytest test_api_gateway.py -v
```

### Individual Services

```bash
# Intent Engine (Go)
cd services/intent-engine
go run main.go

# Device Manager (Python)
cd services/device-manager
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8083

# Self-Healing (Go)
cd services/self-healing
go run main.go

# Security Agent (Python)
cd services/security-agent
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8084

# API Gateway (Python)
cd services/api-gateway
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## API Reference

### Authentication

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/auth/login` | POST | Login with username/password, returns JWT |
| `/api/v1/auth/me` | GET | Get current user info |
| `/api/v1/auth/refresh` | POST | Refresh JWT token |

### Intent Engine

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/intents` | GET | List all intents |
| `/api/v1/intents` | POST | Create new intent policy |
| `/api/v1/intents/:id` | GET | Get intent by ID |
| `/api/v1/intents/:id` | PUT | Update intent |
| `/api/v1/intents/:id` | DELETE | Delete intent |
| `/api/v1/intents/:id/validate` | POST | Validate intent policy |
| `/api/v1/intents/:id/deploy` | POST | Deploy intent to devices |
| `/api/v1/intents/:id/rollback` | POST | Rollback intent deployment |
| `/api/v1/intents/:id/compliance` | GET | Check compliance status |
| `/api/v1/intents/conflicts` | GET | Detect policy conflicts |
| `/api/v1/intents/compliance-report` | GET | Full compliance report |

### Device Manager

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/devices` | GET | List all devices |
| `/api/v1/devices` | POST | Register a new device |
| `/api/v1/devices/:id` | GET | Get device details |
| `/api/v1/devices/:id` | PUT | Update device |
| `/api/v1/devices/:id` | DELETE | Delete device |
| `/api/v1/devices/:id/config` | GET | Get running config |
| `/api/v1/devices/:id/config` | POST | Deploy configuration |
| `/api/v1/devices/:id/health` | GET | Check device health |
| `/api/v1/devices/:id/interfaces` | GET | Get interface status |
| `/api/v1/devices/:id/commands` | POST | Execute CLI commands |
| `/api/v1/devices/:id/rollback` | POST | Rollback config |
| `/api/v1/vendors` | GET | List supported vendors |

### Self-Healing

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/incidents` | GET | List incidents |
| `/api/v1/incidents/:id` | GET | Get incident details |
| `/api/v1/incidents/:id/resolve` | POST | Resolve incident |
| `/api/v1/stats` | GET | Get incident statistics |
| `/api/v1/stats/mttr` | GET | Mean Time To Resolution |

### Security Agent

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/threats` | GET | List security threats |
| `/api/v1/threats/:id` | GET | Get threat details |
| `/api/v1/threats/:id/resolve` | POST | Resolve a threat |
| `/api/v1/mitigate` | POST | Trigger mitigation |
| `/api/v1/rollback/:id` | POST | Rollback mitigation |
| `/api/v1/stats` | GET | Security statistics |
| `/api/v1/anomaly/analyze` | POST | Analyze traffic for anomalies |
| `/api/v1/config/thresholds` | PUT | Update detection thresholds |
| `/api/v1/patterns` | GET | Known attack patterns |

### Dashboard & System

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Gateway health + all service statuses |
| `/api/v1/dashboard` | GET | Aggregated dashboard from all services |
| `/ws` | WebSocket | Real-time event stream |
| `/docs` | GET | OpenAPI/Swagger documentation |

---

## Kubernetes Deployment

Deploy to a production Kubernetes cluster:

```bash
# Apply all manifests in order
kubectl apply -f k8s/00-namespace-and-config.yaml
kubectl apply -f k8s/01-timescaledb.yaml
kubectl apply -f k8s/02-rabbitmq.yaml
kubectl apply -f k8s/03-redis.yaml

# Wait for infrastructure to be ready
kubectl -n netweaver wait --for=condition=ready pod -l app=timescaledb --timeout=120s
kubectl -n netweaver wait --for=condition=ready pod -l app=rabbitmq --timeout=120s

# Deploy application services
kubectl apply -f k8s/04-intent-engine.yaml
kubectl apply -f k8s/05-device-manager.yaml
kubectl apply -f k8s/06-self-healing.yaml
kubectl apply -f k8s/07-security-agent.yaml
kubectl apply -f k8s/08-api-gateway.yaml
kubectl apply -f k8s/09-web-ui.yaml
kubectl apply -f k8s/10-ingress.yaml

# Verify deployment
kubectl -n netweaver get pods
```

### Resource Requirements

| Service | CPU Request | Memory Request | Replicas |
|---|---|---|---|
| TimescaleDB | 500m | 1Gi | 1 |
| RabbitMQ | 250m | 512Mi | 1 |
| Redis | 100m | 128Mi | 1 |
| Intent Engine | 250m | 256Mi | 2 |
| Device Manager | 250m | 256Mi | 2 |
| Self-Healing | 250m | 256Mi | 2 |
| Security Agent | 500m | 512Mi | 2 |
| API Gateway | 250m | 256Mi | 2 |
| Web UI | 50m | 64Mi | 2 |

---

## Development Phases

### Phase 1: Foundation ✅ COMPLETE

Built the core infrastructure for network telemetry and intelligent optimization:

| Component | Description | Metrics |
|---|---|---|
| **Telemetry Agent** (Go) | NetFlow v5/v9/IPFIX & sFlow v5 collector, LLDP/CDP topology discovery | 1M+ flows/sec throughput |
| **TimescaleDB Schema** | 12 tables, 7 hypertables for time-series metrics | 100K+ metrics/sec ingestion |
| **ML Prediction Models** (Python) | LSTM & Transformer traffic forecasters | <10ms prediction latency |
| **Routing Optimization** (Go) | Dijkstra shortest-path, K-paths, ECMP load balancing | <500ms for 1000-node network |
| **Network Simulator** | 100-node topology generator for testing | Configurable topology types |
| **Test Suite** | Comprehensive Go tests | 24 tests, all passing |

### Phase 2: Production MVP ✅ COMPLETE

Expanded into a full microservices platform:

| Component | Description | Technology |
|---|---|---|
| **Intent Engine** | YAML policy parsing, NLP intent extraction, multi-vendor config translation, conflict detection, compliance monitoring | Go/Gin, PostgreSQL |
| **Device Manager** | Cisco IOS, Juniper JunOS, Arista EOS unified API, config deployment & rollback, health monitoring | Python/FastAPI |
| **Self-Healing** | RabbitMQ telemetry consumption, failure detection (<5s), automated remediation, incident tracking with MTTR | Go/Gin, RabbitMQ, PostgreSQL |
| **Security Agent** | Flow-based DDoS detection (volumetric, protocol, application-layer), ML anomaly detection (Isolation Forest), automated mitigation (ACL, blackhole, rate-limit) | Python/FastAPI, scikit-learn |
| **API Gateway** | Unified REST API, JWT authentication, Redis rate limiting, parallel dashboard aggregation, WebSocket real-time events | Python/FastAPI, Redis |
| **Web Dashboard** | Dark-themed dashboard with network topology visualization (Cytoscape.js), intent management, device monitoring, incident tracking, threat analysis charts (Recharts) | React 18, TypeScript, Vite, MUI 5 |
| **Integration Tests** | Comprehensive pytest suite covering auth, CRUD, health checks, E2E workflows | pytest, httpx |
| **Kubernetes Manifests** | Production-ready deployment with namespaces, ConfigMaps, Services, HPA, Ingress | 11 YAML manifests |

---

## Supported Network Vendors

### Cisco IOS/IOS-XE
- **Protocols**: SSH, NETCONF, RESTCONF
- **Features**: QoS (policy-map), ACL, OSPF, BGP, VLAN
- **Config example**:
```
policy-map VIDEO-QOS
 class VIDEO-TRAFFIC
  priority percent 30
  set dscp ef
```

### Juniper JunOS
- **Protocols**: SSH, NETCONF
- **Features**: Class-of-Service, Firewall Filters, MPLS, BGP
- **Config example**:
```
set class-of-service forwarding-classes class video-realtime queue-num 5
set class-of-service scheduler-maps video-scheduler forwarding-class video-realtime
```

### Arista EOS
- **Protocols**: SSH, eAPI
- **Features**: Traffic Policies, QoS, ACL, VXLAN, BGP
- **Config example**:
```
traffic-policies
   traffic-policy VIDEO-QOS
      match video-traffic ipv4
         actions
            set traffic-class 5
```

---

## Performance Benchmarks

| Metric | Value |
|---|---|
| Telemetry throughput | 1M+ flows/sec per core |
| ML prediction latency | <10ms per forecast |
| Routing optimization | <500ms for 1000-node network |
| Database ingestion | 100K+ metrics/sec |
| API Gateway latency | <5ms overhead |
| Failure detection | <5 seconds |
| DDoS detection | <10 seconds |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | TimescaleDB host |
| `DB_PORT` | `5432` | TimescaleDB port |
| `DB_NAME` | `netweaver` | Database name |
| `DB_USER` | `netweaver` | Database user |
| `DB_PASSWORD` | *(required)* | Database password |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ host |
| `RABBITMQ_PORT` | `5672` | RabbitMQ AMQP port |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `JWT_SECRET_KEY` | *(change in prod)* | JWT signing secret |
| `PPS_THRESHOLD` | `10000` | DDoS packets/sec threshold |
| `BPS_THRESHOLD` | `100000000` | DDoS bits/sec threshold (100Mbps) |

### Telemetry Agent Config (`configs/telemetry-agent.yaml`)

```yaml
collectors:
  netflow:
    listen: "0.0.0.0:2055"
    workers: 16
  sflow:
    listen: "0.0.0.0:6343"
    workers: 16
database:
  host: "localhost"
  port: 5432
  database: "netweaver"
```

---

## Testing

### Run Integration Tests

```bash
# Ensure services are running
docker-compose -f docker-compose-phase2.yml up -d

# Run tests
cd tests/integration
pytest test_api_gateway.py -v

# Test coverage:
# - Authentication (login, token verification, refresh)
# - Health checks (gateway + all services)
# - Intent CRUD (create, list, get, delete)
# - Device management (register, list, health)
# - Security threats (list, resolve)
# - Dashboard aggregation
# - End-to-end workflow
```

### Run Phase 1 Go Tests

```bash
go test ./pkg/... -v -count=1
# 24 tests across netflow, sflow, topology, routing, database packages
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit changes (`git commit -m 'Add my feature'`)
4. Push to branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Contact

For questions or support, open an issue on [GitHub](https://github.com/reshwanthmanupati/NetWeaver/issues).

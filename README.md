a# NetWeaver: Self-Optimizing Autonomous Network Infrastructure Platform

**Version**: 2.0.0 (Phase 2 MVP)  
**Status**: 🚧 In Development (40% Complete)  
**Repository**: https://github.com/reshwanthmanupati/NetWeaver

## Overview
NetWeaver is a production-grade autonomous network infrastructure platform that:
- **Autonomously optimizes** routing, QoS, and load balancing in real-time
- **Predicts traffic patterns** using LSTM/Transformer ML models (Phase 1 ✅)
- **Self-heals** by detecting failures and automatically rerouting traffic (Phase 2 🚧)
- **Implements intent-based policies** via natural language YAML (Phase 2 ✅)
- **Detects security threats** (DDoS, port scans, anomalies) in real-time (Phase 2 🚧)
- **Supports multi-vendor devices** (Cisco, Juniper, Arista) with unified APIs (Phase 2 ✅)

## 🎯 Phase 2 Enhancements (NEW!)

### Intent-Based Networking Engine ✅
Translate high-level business policies to vendor-specific configurations:
```yaml
name: video-low-latency
policy:
  type: latency
  constraints:
    - metric: latency
      operator: "<"
      value: 50
      unit: ms
targets:
  - type: device
    identifiers: [router-edge-01]
```
→ Automatically generates Cisco IOS/Juniper JunOS/Arista EOS configs!

### Multi-Vendor Device Manager ✅
Unified API for managing Cisco, Juniper, and Arista devices:
- NETCONF, SSH, eAPI protocol support
- Configuration management (get, push, rollback)
- Health monitoring and interface status
- Template-based config generation

### Self-Healing System 🚧 (Coming Soon)
- Automatic failure detection (<5s)
- Traffic rerouting to backup paths
- BGP route injection for failover
- Auto-rollback on failed changes

### Security Agent 🚧 (Planned)
- Real-time DDoS detection
- ML-based anomaly detection
- Automatic mitigation (rate-limit, blackhole)

### Web UI 🚧 (Planned)
- Intent policy management interface
- Network topology visualization (D3.js)
- Real-time monitoring dashboards

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NetWeaver Platform                       │
├─────────────────────────────────────────────────────────────┤
│  Telemetry Agent (Go)                                       │
│  - NetFlow/sFlow/IPFIX collector                            │
│  - LLDP/CDP topology discovery                              │
│  - Multi-vendor device support                              │
├─────────────────────────────────────────────────────────────┤
│  ML Prediction Engine (Python)                              │
│  - LSTM traffic forecasting                                 │
│  - Anomaly detection                                        │
│  - Capacity planning                                        │
├─────────────────────────────────────────────────────────────┤
│  Optimization Engine (Go)                                   │
│  - Latency minimization                                     │
│  - ECMP load balancing                                      │
│  - Intent-based routing                                     │
├─────────────────────────────────────────────────────────────┤
│  Configuration Manager (Go)                                 │
│  - Multi-vendor config generation                           │
│  - Rollback support                                         │
│  - Compliance validation                                    │
├─────────────────────────────────────────────────────────────┤
│  Data Layer (TimescaleDB)                                   │
│  - Time-series metrics storage                              │
│  - Topology graph database                                  │
│  - Historical analysis                                      │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack
- **Go**: High-performance telemetry collection, packet processing
- **Python**: ML models (PyTorch, scikit-learn)
- **TimescaleDB**: Time-series network metrics
- **eBPF/DPDK**: Line-rate packet inspection
- **Docker**: Containerized deployment

## Project Structure

```
NetWeaver/
├── cmd/                    # Main applications
│   ├── telemetry-agent/    # NetFlow/sFlow collector
│   ├── predictor/          # ML prediction service
│   └── optimizer/          # Routing optimization service
├── pkg/                    # Go packages
│   ├── netflow/            # NetFlow v5/v9/IPFIX parsing
│   ├── sflow/              # sFlow v5 parsing
│   ├── topology/           # Network topology management
│   ├── database/           # TimescaleDB interface
│   ├── routing/            # Routing algorithms
│   └── config/             # Multi-vendor config generation
├── python/                 # Python ML components
│   ├── models/             # LSTM/Transformer models
│   ├── training/           # Model training scripts
│   └── inference/          # Real-time prediction service
├── configs/                # Configuration files
├── deployments/            # Docker/K8s deployment configs
├── scripts/                # Utility scripts
├── simulator/              # Network simulator for testing
└── tests/                  # Test suites
```

## Development Phases

### Phase 1: Foundation ✅ COMPLETE
1. ✅ Telemetry agent (NetFlow/sFlow collector) - 1M+ flows/sec
2. ✅ TimescaleDB schema (12 tables, 7 hypertables)
3. ✅ Traffic prediction ML models (LSTM, Transformer)
4. ✅ Routing optimization algorithms (Dijkstra, K-paths)
5. ✅ Network simulator (100-node test environment)
6. ✅ Comprehensive testing (24 tests, all passing)

### Phase 2: Production MVP 🚧 40% COMPLETE
1. ✅ Intent-Based Networking Engine
2. ✅ Multi-Vendor Device Manager (Cisco/Juniper/Arista)
3. 🚧 Self-Healing System (in progress)
4. 📋 Security Agent with DDoS Detection (planned)
5. 📋 Web UI for Policy Management (planned)

See [PHASE2_PROGRESS.md](PHASE2_PROGRESS.md) for detailed status.

## Quick Start - Phase 2

### Prerequisites
- Go 1.21+
- Python 3.11+
- Docker & Docker Compose
- TimescaleDB 2.11+

### Phase 2 Stack Setup

```bash
# Start all Phase 2 microservices
docker-compose -f docker-compose-phase2.yml up -d

# This starts:
# - TimescaleDB (port 5432)
# - RabbitMQ (port 5672, management 15672)
# - Redis (port 6379)
# - Intent Engine (port 8081)
# - Device Manager (port 8083)
# - Self-Healing System (port 8082)
# - API Gateway (port 8080)
# - Web UI (port 3000)
# - Prometheus (port 9090)
# - Grafana (port 3001)
```

### Create Your First Intent Policy

```bash
# 1. Create a video latency intent
curl -X POST http://localhost:8081/api/v1/intents \
  -H "Content-Type: application/json" \
  -d @services/intent-engine/examples/video-low-latency.yaml

# 2. List all intents
curl http://localhost:8081/api/v1/intents

# 3. Register a network device
curl -X POST http://localhost:8083/api/v1/devices \
  -H "Content-Type: application/json" \
  -d '{
    "name": "router-edge-01",
    "vendor": "cisco_ios",
    "model": "ISR4451",
    "ip_address": "192.168.1.1",
    "username": "admin",
    "password": "password"
  }'

# 4. Deploy intent to network
curl -X POST http://localhost:8081/api/v1/intents/intent-123/deploy

# 5. Check compliance
curl http://localhost:8081/api/v1/intents/intent-123/compliance
```

### Phase 1 Legacy Setup (Telemetry Only)

```bash
# Clone repository
cd NetWeaver

# Install Go dependencies
go mod download

# Install Python dependencies
pip install -r python/requirements.txt

# Start TimescaleDB
docker-compose up -d timescaledb

# Initialize database schema
go run scripts/init_db.go
```

### Run Telemetry Agent
```bash
go run cmd/telemetry-agent/main.go --config configs/telemetry-agent.yaml
```

### Run Prediction Service
```bash
python python/inference/predictor_service.py --config configs/predictor.yaml
```

### Run Optimizer
```bash
go run cmd/optimizer/main.go --config configs/optimizer.yaml
```

## Configuration

### Telemetry Agent (configs/telemetry-agent.yaml)
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
  user: "netweaver"
  password: "secure_password"
```

## Performance
- **Telemetry throughput**: 1M+ flows/sec per core
- **Prediction latency**: <10ms per forecast
- **Optimization convergence**: <500ms for 1000-node network
- **Database ingestion**: 100K+ metrics/sec

## Network Device Support

### Cisco IOS/IOS-XE
```
flow exporter NETWEAVER
 destination 10.0.0.100
 transport udp 2055
 template data timeout 60
```

### Juniper Junos
```
set forwarding-options sampling instance NETWEAVER family inet output flow-server 10.0.0.100 port 2055
```

### Arista EOS
```
flow tracking tracked NETWEAVER
   destination 10.0.0.100 2055
   record size 1400
```

## License
MIT License

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md)

## Contact
For questions or support, open an issue on GitHub.

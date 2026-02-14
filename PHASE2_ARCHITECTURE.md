# NetMind Phase 2 Architecture

**Target Scale**: 500 devices, 1M flows/sec  
**Timeline**: 6-12 months MVP  
**Status**: In Development

---

## Microservices Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web UI (React)                           │
│              Intent Management | Network Viz | Security          │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST API
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API Gateway (Go/Gin)                         │
│                   OpenAPI Docs | Auth | Rate Limiting            │
└───┬──────────────┬──────────────┬──────────────┬────────────┬───┘
    │              │              │              │            │
    ▼              ▼              ▼              ▼            ▼
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐
│ Intent  │  │  Self-   │  │  Device  │  │Security │  │Telemetry│
│ Engine  │  │ Healing  │  │ Manager  │  │  Agent  │  │  Agent  │
│         │  │  System  │  │ (Vendor) │  │  (DDoS) │  │ (Phase1)│
└────┬────┘  └────┬─────┘  └────┬─────┘  └────┬────┘  └────┬────┘
     │            │             │             │            │
     └────────────┴─────────────┴─────────────┴────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌──────────────┐    ┌─────────────┐
            │ TimescaleDB  │    │  RabbitMQ   │
            │  (Metrics)   │    │  (Events)   │
            └──────────────┘    └─────────────┘
```

---

## Microservices Details

### 1. Intent Engine (`services/intent-engine/`)
**Port**: 8081  
**Language**: Go  
**Purpose**: Parse, validate, and translate high-level policies to device configs

**Key Features**:
- YAML policy parser with natural language support
- Intent-to-config translator (routing, QoS, ACLs)
- Policy conflict detection
- Continuous compliance monitoring
- Policy version control (GitOps)

**API Endpoints**:
```
POST   /api/v1/intents          - Create new intent policy
GET    /api/v1/intents          - List all policies
GET    /api/v1/intents/:id      - Get policy details
PUT    /api/v1/intents/:id      - Update policy
DELETE /api/v1/intents/:id      - Delete policy
POST   /api/v1/intents/:id/deploy  - Deploy to network
GET    /api/v1/intents/:id/compliance - Check compliance
```

**Dependencies**: device-manager, telemetry-agent

---

### 2. Self-Healing System (`services/self-healing/`)
**Port**: 8082  
**Language**: Go + Python  
**Purpose**: Detect failures and automatically remediate

**Key Features**:
- Real-time failure detection (link down, device crash, latency spikes)
- Automatic traffic rerouting (ECMP, backup paths)
- BGP route injection/withdrawal
- VRRP/HSRP failover coordination
- Auto-rollback on failed changes
- Incident post-mortem generation

**Event Types**:
```yaml
- link_down: Reroute traffic to backup path
- device_unreachable: Failover to standby device
- high_latency: Traffic engineering adjustment
- packet_loss: Path quality degradation response
- config_failed: Automatic rollback
```

**Dependencies**: device-manager, telemetry-agent, rabbitmq

---

### 3. Device Manager (`services/device-manager/`)
**Port**: 8083  
**Language**: Python  
**Purpose**: Multi-vendor device abstraction and config management

**Vendor Support**:
- **Cisco IOS/IOS-XE**: NETCONF, SSH (netmiko)
- **Juniper JunOS**: NETCONF, SSH (junos-eznc)
- **Arista EOS**: eAPI, SSH (pyeapi)

**Key Features**:
- Vendor-agnostic config generation (Jinja2 templates)
- NETCONF/RESTCONF/gNMI protocol support
- Config diff, backup, and rollback
- Device inventory management
- Connection pooling and health checks

**API Endpoints**:
```
GET    /api/v1/devices          - List devices
POST   /api/v1/devices          - Add device
GET    /api/v1/devices/:id/config - Get running config
POST   /api/v1/devices/:id/config - Push config
POST   /api/v1/devices/:id/rollback - Rollback config
GET    /api/v1/devices/:id/health - Health check
```

**Config Templates**: `templates/cisco/`, `templates/juniper/`, `templates/arista/`

---

### 4. Security Agent (`services/security-agent/`)
**Port**: 8084  
**Language**: Python + PyTorch  
**Purpose**: Real-time threat detection and automated mitigation

**Detection Capabilities**:
- **DDoS Detection**: Volumetric, protocol, application layer
- **Port Scanning**: Flow pattern analysis
- **Anomaly Detection**: ML-based (Isolation Forest, Autoencoder)
- **Brute Force**: SSH/RDP login attempt monitoring

**Mitigation Actions**:
```yaml
- rate_limiting: Apply traffic shaping
- blackhole_routing: Null route malicious IPs
- acl_injection: Dynamic ACL deployment
- bgp_flowspec: Flowspec rule injection
- alerting: Email/Slack/PagerDuty notifications
```

**ML Models**:
- Traffic anomaly detector (Phase 1 model extended)
- DDoS classifier (Random Forest)
- Port scan detector (sequence analysis)

**Dependencies**: telemetry-agent, device-manager

---

### 5. Web UI (`services/web-ui/`)
**Port**: 3000 (dev), 80/443 (prod)  
**Stack**: React 18 + TypeScript + Vite  
**Purpose**: Network visualization and policy management

**Pages**:
1. **Dashboard**: Network health overview, active alerts
2. **Intent Policies**: Create/edit/deploy policies (priority)
3. **Network Topology**: D3.js interactive graph
4. **Security Dashboard**: DDoS events, threat timeline
5. **Device Manager**: Device list, config viewer
6. **Analytics**: Traffic heatmaps, bandwidth utilization

**State Management**: Redux Toolkit or Zustand  
**UI Library**: Material-UI or Ant Design  
**Network Graph**: Cytoscape.js or React Flow

---

### 6. API Gateway (`services/api-gateway/`)
**Port**: 8080  
**Language**: Go (Gin framework)  
**Purpose**: Unified API entry point, auth, rate limiting

**Features**:
- JWT authentication
- Rate limiting (per-user, per-endpoint)
- Request logging and tracing
- OpenAPI/Swagger documentation
- CORS configuration
- WebSocket support for real-time updates

---

## Data Flow Examples

### Example 1: Deploy Intent Policy
```
1. User creates policy in Web UI:
   - POST /api/v1/intents
   - Policy: "Video traffic should have latency <50ms"

2. Intent Engine processes:
   - Parse YAML policy
   - Validate against schema
   - Check for conflicts with existing policies
   - Translate to vendor configs (QoS, routing)

3. Device Manager deploys:
   - Generate Cisco IOS QoS config
   - Generate Juniper JunOS class-of-service config
   - Push via NETCONF to devices
   - Verify configuration applied

4. Telemetry monitors compliance:
   - Measure video traffic latency
   - Alert if latency exceeds 50ms
   - Trigger self-healing if policy violated
```

### Example 2: Self-Healing Failover
```
1. Telemetry detects link failure:
   - Interface down event on router R1
   - Publish to RabbitMQ: "link_down" event

2. Self-Healing responds:
   - Calculate backup path (Dijkstra on graph)
   - Generate config for rerouting
   - Call Device Manager to push config
   - Update routing table on affected devices

3. Verification:
   - Check traffic is flowing through backup path
   - Measure MTTR (Mean Time To Recovery)
   - Generate incident report

4. Post-recovery:
   - Monitor original link for return to service
   - Revert to primary path when stable
   - Archive incident for analysis
```

### Example 3: DDoS Mitigation
```
1. Security Agent detects attack:
   - Flow data shows 10× traffic spike to server
   - ML model flags as volumetric DDoS
   - Publish "ddos_detected" event

2. Automated mitigation:
   - Generate rate-limiting ACL
   - Deploy to edge routers via Device Manager
   - Optional: BGP Flowspec announcement
   - Blackhole attacking IP addresses

3. Monitoring:
   - Track attack duration and volume
   - Measure mitigation effectiveness
   - Alert security team via Slack
   - Log to SIEM system

4. Post-mitigation:
   - Remove rate limits after attack subsides
   - Update threat intelligence database
   - Analyze attack patterns for ML model retraining
```

---

## Technology Stack

### Backend
- **Go 1.21+**: Intent Engine, Self-Healing, API Gateway
- **Python 3.11+**: Device Manager, Security Agent
- **Gin**: Go web framework
- **gRPC**: Inter-service communication
- **NETCONF/SSH**: Device management (ncclient, netmiko, pyeapi)

### Frontend
- **React 18** + TypeScript
- **Vite**: Build tool
- **Cytoscape.js**: Network topology visualization
- **D3.js**: Traffic heatmaps and charts
- **Material-UI**: Component library
- **Redux Toolkit**: State management

### Infrastructure
- **TimescaleDB**: Time-series data (Phase 1)
- **RabbitMQ**: Event streaming and messaging
- **PostgreSQL**: Application data (devices, policies, incidents)
- **Redis**: Caching and session storage
- **Docker**: Container runtime
- **Kubernetes**: Orchestration (optional for prod)

### DevOps
- **GitHub Actions**: CI/CD pipeline
- **Docker Compose**: Local development
- **Prometheus**: Metrics collection
- **Grafana**: Monitoring dashboards
- **ELK Stack**: Centralized logging

---

## Security Considerations

1. **API Authentication**: JWT tokens, OAuth2 for SSO
2. **Device Credentials**: Vault for secret management
3. **Config Validation**: Schema validation before deployment
4. **Audit Logging**: All config changes logged
5. **RBAC**: Role-based access control (admin, operator, viewer)
6. **TLS**: All inter-service communication encrypted

---

## Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Policy Translation | <500ms | UX responsiveness |
| Config Deployment | <5s | Per device push |
| Failure Detection | <5s | From event to alert |
| Auto-Healing MTTR | <30s | From failure to recovery |
| DDoS Detection | <10s | From spike to alert |
| Mitigation Deployment | <15s | From detection to ACL push |
| UI Page Load | <2s | Network topology render |
| API Response Time | <200ms | p95 for CRUD operations |

---

## Development Phases

### Week 1-2: Foundation
- [x] Design architecture
- [ ] Set up microservices scaffolding
- [ ] Docker Compose dev environment
- [ ] RabbitMQ event bus
- [ ] API Gateway with auth

### Week 3-5: Intent Engine
- [ ] YAML policy parser
- [ ] Intent-to-config translator
- [ ] Conflict detection engine
- [ ] Compliance monitoring
- [ ] Unit tests for policy scenarios

### Week 6-8: Device Manager
- [ ] Cisco IOS config templates
- [ ] Juniper JunOS templates
- [ ] Arista EOS templates
- [ ] NETCONF client implementation
- [ ] Config diff and rollback
- [ ] Integration tests with vendor images

### Week 9-11: Self-Healing
- [ ] Failure detection from telemetry
- [ ] Backup path calculation
- [ ] BGP route injection
- [ ] Auto-rollback logic
- [ ] Incident report generation
- [ ] Chaos testing (simulate failures)

### Week 12-14: Security Agent
- [ ] DDoS detection ML model
- [ ] Port scan detector
- [ ] Anomaly baseline modeling
- [ ] Mitigation action engine
- [ ] Threat intelligence integration
- [ ] Performance benchmarks (detection time)

### Week 15-18: Web UI
- [ ] Intent policy management UI (priority)
- [ ] Network topology visualization
- [ ] Security dashboard
- [ ] Real-time WebSocket updates
- [ ] Config deployment interface
- [ ] Responsive design

### Week 19-20: Integration & Testing
- [ ] End-to-end integration tests
- [ ] Load testing (500 devices, 1M flows/sec)
- [ ] Security penetration testing
- [ ] Documentation and runbooks
- [ ] Performance optimization

---

## Success Metrics

1. **Network Downtime**: Reduce MTTR from 15min to <30s
2. **Bandwidth Utilization**: Improve link utilization by 20%
3. **Security**: Detect 95% of DDoS attacks within 10s
4. **Policy Compliance**: Maintain 99% compliance
5. **Config Accuracy**: 99.9% successful deployments without rollback

---

## Next Steps

1. **Immediate**: Build Intent Engine + Device Manager core
2. **Week 2**: Create multi-vendor config templates
3. **Week 3**: Integrate with Phase 1 telemetry data
4. **Week 4**: Deploy policy management UI
5. **Continuous**: Integration testing with real vendor devices

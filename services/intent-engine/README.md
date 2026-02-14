# Intent Engine Service

**Version**: 2.0.0  
**Port**: 8081  
**Language**: Go

## Overview

The Intent Engine is the core component of NetMind Phase 2 that translates high-level business policies into vendor-specific network configurations. It provides a declarative, intent-based approach to network management.

## Features

### ✅ Policy Management
- **YAML-based policies** with natural language constraints
- **Policy validation** with syntax and semantic checks
- **Conflict detection** between overlapping policies
- **Priority-based** policy resolution
- **Version control** for policy history

### ✅ Multi-Vendor Support
- **Cisco IOS/IOS-XE**: QoS, routing, ACLs
- **Juniper JunOS**: Class-of-Service, firewall filters
- **Arista EOS**: Traffic policies, routing

### ✅ Policy Types
- **Latency**: Ensure traffic meets latency SLAs
- **Bandwidth**: Guarantee minimum/maximum bandwidth
- **Security**: DDoS protection, firewall rules
- **Routing**: Path selection, traffic engineering
- **Availability**: High availability, failover

### ✅ Compliance Monitoring
- **Continuous validation** against deployed policies
- **Real-time alerts** for policy violations
- **Automated reports** on compliance status

## API Endpoints

### Intent CRUD
```
POST   /api/v1/intents          - Create new intent
GET    /api/v1/intents          - List all intents
GET    /api/v1/intents/:id      - Get intent details
PUT    /api/v1/intents/:id      - Update intent
DELETE /api/v1/intents/:id      - Delete intent
```

### Intent Operations
```
POST   /api/v1/intents/:id/validate   - Validate intent
POST   /api/v1/intents/:id/deploy     - Deploy to network
POST   /api/v1/intents/:id/rollback   - Rollback deployment
GET    /api/v1/intents/:id/compliance - Check compliance
GET    /api/v1/intents/:id/history    - Deployment history
```

### Policy Operations
```
POST   /api/v1/intents/validate-policy     - Validate policy syntax
GET    /api/v1/intents/conflicts           - Detect conflicts
GET    /api/v1/intents/compliance-report   - Full compliance report
```

## Quick Start

### 1. Build the Service
```bash
cd services/intent-engine
go build -o intent-engine main.go
```

### 2. Set Environment Variables
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=netweaver
export DB_USER=netweaver
export DB_PASSWORD=netweaver_secure_pass_2026
export PORT=8081
export ENV=development
```

### 3. Run the Service
```bash
./intent-engine
```

### 4. Health Check
```bash
curl http://localhost:8081/health
```

## Example Usage

### Create an Intent
```bash
curl -X POST http://localhost:8081/api/v1/intents \
  -H "Content-Type: application/json" \
  -d @examples/video-low-latency.yaml
```

### List All Intents
```bash
curl http://localhost:8081/api/v1/intents
```

### Deploy an Intent
```bash
curl -X POST http://localhost:8081/api/v1/intents/intent-123/deploy
```

### Check Compliance
```bash
curl http://localhost:8081/api/v1/intents/intent-123/compliance
```

## Policy Examples

See `examples/` directory for sample policies:
- `video-low-latency.yaml` - Low latency for video traffic
- `backup-guaranteed-bandwidth.yaml` - Guaranteed bandwidth for backups
- `security-ddos-protection.yaml` - DDoS protection
- `critical-services-ha.yaml` - High availability

## Policy YAML Format

```yaml
name: my-policy
description: Human-readable description
priority: 100  # Higher = more important
created_by: team-name

policy:
  type: latency|bandwidth|security|routing|availability
  
  constraints:
    - metric: latency|bandwidth|packet_loss|jitter
      operator: <|<=|>|>=|==
      value: 50
      unit: ms|Gbps|%
  
  actions:
    - type: qos|route|firewall|redundancy
      parameters:
        key: value
  
  conditions:  # Optional
    - type: traffic_type|source|destination
      parameters:
        key: value

targets:
  - type: device|interface|network
    identifiers: [device-01, device-02]

schedule:  # Optional
  start_time: "09:00"
  end_time: "17:00"
  days: [monday, tuesday]
  timezone: America/New_York

metadata:
  owner: team-name
  environment: production
```

## Constraint Metrics

| Metric | Unit | Operators | Description |
|--------|------|-----------|-------------|
| latency | ms, us, s | <, <=, >, >=, == | End-to-end latency |
| bandwidth | bps, Kbps, Mbps, Gbps | <, <=, >, >=, == | Link bandwidth |
| packet_loss | %, pct | <, <=, >, >= | Packet loss rate |
| jitter | ms, us | <, <= | Latency variation |
| availability | %, pct | >, >= | Service uptime |
| throughput | pps, Kpps, Mpps | >, >= | Packets per second |

## Action Types

### QoS Actions
```yaml
- type: qos
  parameters:
    class: ef|af31|best-effort
    priority: high|medium|low
    bandwidth_percent: 30
    guaranteed_bandwidth: 1000000000  # bps
```

### Routing Actions
```yaml
- type: route
  parameters:
    path_selection: lowest-latency|highest-bandwidth|primary
    backup_path: true
    ecmp: true  # Equal-Cost Multi-Path
    health_check: bfd
```

### Firewall Actions
```yaml
- type: firewall
  parameters:
    action: allow|deny|rate-limit|block
    rate: 10000  # pps
    threshold_pps: 50000
```

### Redundancy Actions
```yaml
- type: redundancy
  parameters:
    protocol: vrrp|hsrp|glbp
    priority: 200
    preempt: true
```

## Configuration Translation

The Intent Engine automatically translates policies to vendor-specific configurations:

### Example: Latency Policy

**Input (YAML)**:
```yaml
policy:
  type: latency
  constraints:
    - metric: latency
      operator: "<"
      value: 50
      unit: ms
```

**Output (Cisco IOS)**:
```
class-map match-any class-video
 match protocol video
!
policy-map video-policy
 class class-video
  priority percent 30
  set dscp ef
!
interface GigabitEthernet0/0/1
 service-policy output video-policy
!
```

**Output (Juniper JunOS)**:
```
set class-of-service schedulers video-sched transmit-rate percent 30
set class-of-service schedulers video-sched priority strict-high
set class-of-service scheduler-maps video-scheduler forwarding-class expedited-forwarding scheduler video-sched
```

## Conflict Detection

The Intent Engine detects three types of conflicts:

1. **Constraint Conflicts**: Incompatible metric requirements
   - Example: "latency < 50ms" vs "latency > 100ms"

2. **Action Conflicts**: Overlapping actions on same target
   - Example: Two QoS policies on same interface

3. **Priority Conflicts**: Same priority for overlapping policies
   - Warning: Policies may not execute in expected order

## Compliance Monitoring

The Intent Engine continuously monitors deployed policies:

- **Interval**: 30 seconds (configurable)
- **Metrics Source**: TimescaleDB telemetry data
- **Alerts**: Non-compliant policies trigger alerts
- **Self-Healing**: Can trigger automatic remediation

## Architecture

```
┌─────────────────────────────────────────────┐
│           Intent Engine Service             │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐      ┌──────────────┐   │
│  │    Parser    │─────▶│  Validator   │   │
│  │  (YAML)      │      │  (Syntax)    │   │
│  └──────────────┘      └──────────────┘   │
│         │                      │            │
│         ▼                      ▼            │
│  ┌──────────────┐      ┌──────────────┐   │
│  │  Translator  │◀────▶│   Conflict   │   │
│  │  (Multi-     │      │   Detector   │   │
│  │   Vendor)    │      └──────────────┘   │
│  └──────────────┘                          │
│         │                                   │
│         ▼                                   │
│  ┌──────────────┐      ┌──────────────┐   │
│  │ Compliance   │◀────▶│   Storage    │   │
│  │  Monitor     │      │ (PostgreSQL) │   │
│  └──────────────┘      └──────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

## Database Schema

```sql
CREATE TABLE intents (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 100,
    policy JSONB NOT NULL,
    targets JSONB NOT NULL,
    status VARCHAR(50),  -- draft, validated, deployed, failed
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deployed_at TIMESTAMP,
    created_by VARCHAR(255),
    metadata JSONB
);

CREATE TABLE deployments (
    id VARCHAR(255) PRIMARY KEY,
    intent_id VARCHAR(255) REFERENCES intents(id),
    device_id VARCHAR(255),
    vendor VARCHAR(100),
    configuration TEXT,
    status VARCHAR(50),  -- pending, success, failed
    deployed_at TIMESTAMP,
    error TEXT,
    metadata JSONB
);
```

## Integration

### With Device Manager
```
Intent Engine → [Translate] → Device Manager → [Push Config] → Network Devices
```

### With Telemetry Agent
```
Telemetry Agent → [Metrics] → TimescaleDB → [Query] → Intent Engine → [Compliance Check]
```

### With Self-Healing System
```
Intent Engine → [Policy Violation] → Self-Healing → [Auto-Remediate] → Device Manager
```

## Testing

### Unit Tests
```bash
go test ./internal/engine/... -v
```

### Integration Tests
```bash
go test ./test/integration/... -v
```

### Load Testing
```bash
# Create 1000 intents
for i in {1..1000}; do
  curl -X POST http://localhost:8081/api/v1/intents \
    -d @examples/video-low-latency.yaml
done
```

## Performance

| Operation | Target | Current |
|-----------|--------|---------|
| Policy Translation | <500ms | TBD |
| Validation | <100ms | TBD |
| Conflict Detection | <200ms | TBD |
| Compliance Check | <1s | TBD |
| Database Query | <50ms | TBD |

## Roadmap

### Phase 2.1 (Weeks 1-5)
- [x] Core intent engine
- [x] YAML policy parser
- [x] Multi-vendor translator
- [x] Conflict detection
- [ ] PostgreSQL storage
- [ ] Compliance monitoring

### Phase 2.2 (Weeks 6-10)
- [ ] REST API completion
- [ ] Integration with Device Manager
- [ ] Real telemetry data integration
- [ ] Performance optimization
- [ ] Comprehensive testing

### Phase 2.3 (Weeks 11-15)
- [ ] Web UI integration
- [ ] GitOps workflow (CI/CD for policies)
- [ ] Advanced conflict resolution
- [ ] Policy templates library
- [ ] Multi-tenant support

## Contributing

See main NetWeaver [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

## License

See main NetWeaver [LICENSE](../../LICENSE) for details.

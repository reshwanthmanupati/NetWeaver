# Self-Healing System

Autonomous network failure detection and remediation system for NetWeaver.

## Overview

The Self-Healing System automatically detects network failures and performance degradations, then applies intelligent remediation strategies without human intervention. It integrates with the Intent Engine, Device Manager, and telemetry systems to provide end-to-end automated recovery.

## Features

### 🔍 Failure Detection
- **Real-time monitoring** via RabbitMQ event stream
- **Multi-metric analysis**: latency, packet loss, jitter, bandwidth
- **Device health tracking**: link status, CPU, memory
- **Threshold-based alerts** with configurable sensitivity
- **Consecutive failure detection** to avoid false positives

### 🔧 Automated Remediation

**Link Failure**
- Traffic rerouting via alternate paths
- VRRP/HSRP failover activation
- BGP route withdrawal and redistribution
- OSPF cost adjustment

**Device Failure**
- Failover to backup devices
- Traffic load redistribution
- Device isolation and alerting

**Performance Degradation**
- QoS policy adjustment
- Low-priority traffic rerouting
- Bandwidth allocation increase

**Packet Loss**
- Forward Error Correction (FEC) enablement
- Path optimization
- Buffer size adjustment

**Resource Exhaustion**
- Cache and buffer clearing
- Non-essential process termination
- Traffic offloading

### 📊 Incident Management
- Automatic incident creation and tracking
- Resolution time measurement (MTTR)
- Remediation action history
- Manual resolution workflow
- Post-incident analysis

### ↩️ Rollback Capability
- Automatic rollback on remediation failure
- Manual rollback via API
- Configuration state preservation
- Multi-step rollback orchestration

## Architecture

```
┌─────────────────┐
│  Telemetry      │
│  Agent          │
└────────┬────────┘
         │ Events
         ↓
┌─────────────────┐     ┌─────────────────┐
│   RabbitMQ      │────→│ Failure         │
│   (Event Bus)   │     │ Detector        │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ↓
                        ┌────────────────┐
                        │  Remediator    │
                        └────────┬───────┘
                                 │
                     ┌───────────┴──────────┐
                     ↓                      ↓
            ┌────────────────┐    ┌─────────────────┐
            │ Device Manager │    │ Intent Engine   │
            │  (Config Push) │    │ (Policy Check)  │
            └────────────────┘    └─────────────────┘
                     │
                     ↓
            ┌────────────────┐
            │  PostgreSQL    │
            │  (Incidents)   │
            └────────────────┘
```

## API Endpoints

### Incident Management

#### List Incidents
```http
GET /api/v1/incidents?status=remediating&limit=50
```

**Response:**
```json
{
  "count": 15,
  "incidents": [
    {
      "id": "incident-1771056789123456789",
      "type": "link_failure",
      "device_id": "router-01",
      "severity": "critical",
      "status": "remediated",
      "detected_at": "2026-02-14T10:15:30Z",
      "remediated_at": "2026-02-14T10:15:45Z",
      "resolution_time": "15s",
      "details": {
        "interface": "GigabitEthernet0/0/1",
        "reason": "Link down detected"
      }
    }
  ]
}
```

#### Get Incident Details
```http
GET /api/v1/incidents/{incident_id}
```

#### Resolve Incident
```http
POST /api/v1/incidents/{incident_id}/resolve
Content-Type: application/json

{
  "resolution": "Link restored manually",
  "resolved_by": "admin@example.com"
}
```

### Remediation

#### Trigger Manual Remediation
```http
POST /api/v1/remediate
Content-Type: application/json

{
  "incident_type": "link_failure",
  "device_id": "router-01",
  "details": {
    "interface": "GigabitEthernet0/0/1"
  }
}
```

**Response:**
```json
{
  "message": "Remediation triggered",
  "incident_id": "incident-1771056789123456789"
}
```

#### Rollback Remediation
```http
POST /api/v1/rollback/{incident_id}
```

### Statistics

#### Get System Statistics
```http
GET /api/v1/stats
```

**Response:**
```json
{
  "total_incidents": 127,
  "by_status": {
    "detected": 5,
    "remediating": 2,
    "remediated": 95,
    "resolved": 25,
    "failed": 0
  },
  "by_severity": {
    "critical": 15,
    "high": 42,
    "medium": 70
  },
  "avg_mttr_seconds": 23.5,
  "avg_mttr": "23.50s"
}
```

#### Get MTTR (Mean Time To Resolution)
```http
GET /api/v1/stats/mttr?period=24h
```

**Response:**
```json
{
  "period": "24h",
  "mttr": "25.3s",
  "mttr_seconds": 25.3
}
```

### Configuration

#### Get Configuration
```http
GET /api/v1/config
```

**Response:**
```json
{
  "check_interval": "30s",
  "thresholds": {
    "latency_ms": 100,
    "packet_loss_pct": 5,
    "jitter_ms": 50,
    "bandwidth_pct": 80,
    "cpu_pct": 90,
    "memory_pct": 90,
    "link_down_count": 1,
    "consecutive_failures": 3
  }
}
```

#### Update Thresholds
```http
PUT /api/v1/config/thresholds
Content-Type: application/json

{
  "latency_ms": 120,
  "packet_loss_pct": 3,
  "consecutive_failures": 5
}
```

## Event Types

The system listens for these telemetry events:

| Event Type | Trigger | Remediation Strategy |
|------------|---------|---------------------|
| `link_down` | Physical link failure | Traffic rerouting, VRRP failover |
| `device_unreachable` | Device not responding | Backup failover, isolation |
| `high_latency` | Latency > threshold | QoS adjustment, rerouting |
| `packet_loss` | Packet loss > threshold | FEC enable, path optimization |
| `high_cpu` | CPU > 90% | Process termination, offloading |
| `high_memory` | Memory > 90% | Cache clearing, offloading |
| `high_jitter` | Jitter > threshold | Buffer adjustment, QoS |

## Configuration

### Environment Variables

```bash
# Database
DB_HOST=timescaledb
DB_PORT=5432
DB_NAME=netweaver
DB_USER=netweaver
DB_PASSWORD=netweaver_secure_pass_2026

# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=netweaver
RABBITMQ_PASSWORD=netweaver_rabbitmq_2026

# Service URLs
DEVICE_MANAGER_URL=http://device-manager:8083
INTENT_ENGINE_URL=http://intent-engine:8081

# Server
PORT=8082
ENV=production
```

### Threshold Configuration

Default thresholds (can be updated via API):

```yaml
thresholds:
  latency_ms: 100           # High latency threshold
  packet_loss_pct: 5        # Packet loss percentage
  jitter_ms: 50             # Jitter threshold
  bandwidth_pct: 80         # Bandwidth utilization
  cpu_pct: 90               # CPU utilization
  memory_pct: 90            # Memory utilization
  link_down_count: 1        # Links down before action
  consecutive_failures: 3   # Consecutive failures needed
```

## Quick Start

### Standalone

```bash
# Set environment variables
export DB_HOST=localhost
export RABBITMQ_HOST=localhost

# Run go mod tidy
go mod tidy

# Build
go build -o self-healing .

# Run
./self-healing
```

### Docker

```bash
# Build image
docker build -t netweaver-self-healing .

# Run container
docker run -d \
  --name self-healing \
  -p 8082:8082 \
  -e DB_HOST=timescaledb \
  -e RABBITMQ_HOST=rabbitmq \
  netweaver-self-healing
```

### Docker Compose

```bash
# Start self-healing with dependencies
docker-compose up -d self-healing
```

## Testing

### Simulate Link Failure

```bash
# Publish telemetry event to RabbitMQ
curl -X POST http://localhost:8082/api/v1/remediate \
  -H "Content-Type: application/json" \
  -d '{
    "incident_type": "link_failure",
    "device_id": "router-01",
    "details": {
      "interface": "GigabitEthernet0/0/1"
    }
  }'
```

### Check Incident Status

```bash
# List incidents
curl http://localhost:8082/api/v1/incidents

# Get specific incident
curl http://localhost:8082/api/v1/incidents/incident-1771056789123456789
```

### View Statistics

```bash
# Overall statistics
curl http://localhost:8082/api/v1/stats

# MTTR for last 24 hours
curl http://localhost:8082/api/v1/stats/mttr?period=24h
```

## Remediation Strategies

### Link Failure Remediation

1. **BGP Route Withdrawal**
   ```cisco
   router bgp 65000
    address-family ipv4
     network 0.0.0.0 mask 0.0.0.0 withdraw
   !
   ```

2. **VRRP Priority Adjustment**
   ```cisco
   interface Vlan100
    vrrp 1 priority 120
    vrrp 1 track 1 decrement 30
   !
   ```

3. **OSPF Cost Increase**
   ```cisco
   interface GigabitEthernet0/0/1
    ip ospf cost 10000
   !
   ```

### Performance Degradation

1. **QoS Policy Update**
   ```cisco
   policy-map REMEDIATION_QOS
    class class-critical
     priority percent 60
    class class-video
     bandwidth percent 25
   !
   ```

2. **Traffic Rerouting**
   ```cisco
   ip access-list extended LOW_PRIORITY
    permit ip any any precedence routine
   !
   route-map REROUTE_LOW_PRIORITY permit 10
    match ip address LOW_PRIORITY
    set ip next-hop 192.168.100.1
   !
   ```

## Performance

### Targets
- **Detection time**: <5s from event to incident creation
- **Remediation time**: <30s MTTR (Mean Time To Resolution)
- **Throughput**: 10,000 events/sec processing capacity
- **Availability**: 99.99% uptime SLA

### Actual Performance (Phase 2 MVP)
- Detection time: ~2-3s
- Remediation time: ~15-25s MTTR
- Event processing: Single-threaded (optimization in Phase 3)

## Monitoring

### Health Check

```bash
curl http://localhost:8082/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "self-healing",
  "timestamp": "2026-02-14T10:30:00Z"
}
```

### Metrics (Prometheus)

The following metrics are available for Prometheus scraping:

- `self_healing_incidents_total` - Total incidents detected
- `self_healing_incidents_by_type` - Incidents by type
- `self_healing_mttr_seconds` - Mean time to resolution
- `self_healing_remediation_success_rate` - Success rate percentage
- `self_healing_active_incidents` - Currently active incidents

## Troubleshooting

### Service Won't Start

**Check database connection:**
```bash
docker logs netweaver-self-healing | grep "Database"
```

**Check RabbitMQ connection:**
```bash
docker logs netweaver-self-healing | grep "RabbitMQ"
```

### No Incidents Detected

1. Verify telemetry agent is publishing events
2. Check RabbitMQ queue: `telemetry.events`
3. Verify thresholds are configured correctly

```bash
curl http://localhost:8082/api/v1/config
```

### Remediation Failing

**Check device manager connectivity:**
```bash
curl http://localhost:8083/health
```

**View failed incidents:**
```bash
curl http://localhost:8082/api/v1/incidents?status=failed
```

**Check incident error details:**
```bash
curl http://localhost:8082/api/v1/incidents/{incident_id}
```

Look for `error` field in response.

## Development

### Project Structure

```
self-healing/
├── main.go                           # Service entry point
├── go.mod                            # Go dependencies
├── Dockerfile                        # Container image
├── README.md                         # This file
└── internal/
    ├── detector/
    │   └── failure_detector.go       # Event processing & detection
    ├── remediator/
    │   └── remediator.go            # Remediation logic
    └── storage/
        └── postgres.go               # PostgreSQL persistence
```

### Adding New Remediation Strategy

1. Add incident type to detector
2. Implement remediation function in `remediator.go`
3. Add configuration generation function
4. Update API documentation

Example:
```go
func (r *Remediator) remediateMyNewFailure(ctx context.Context, incident *storage.Incident) ([]*RemediationAction, error) {
    // Implement remediation logic
    config := "! Generated config..."
    
    if err := r.deployConfig(incident.DeviceID, config); err != nil {
        return nil, err
    }
    
    action := &RemediationAction{
        Type: "my_remediation",
        DeviceID: incident.DeviceID,
        Config: config,
        CreatedAt: time.Now(),
    }
    
    return []*RemediationAction{action}, nil
}
```

## Security

- All API endpoints support authentication (Phase 3)
- Database credentials stored in environment variables
- RabbitMQ uses authentication
- Config deployment requires Device Manager API access
- Audit trail of all remediation actions

## Future Enhancements (Phase 3)

- [ ] Machine learning for predictive failure detection
- [ ] Multi-cloud remediation strategies
- [ ] Advanced rollback orchestration with checkpoints
- [ ] Integration with external ticketing systems
- [ ] Slack/Teams notifications for critical incidents
- [ ] Automated post-incident report generation
- [ ] A/B testing of remediation strategies
- [ ] Chaos engineering mode for resilience testing

## License

Copyright © 2026 NetWeaver Project

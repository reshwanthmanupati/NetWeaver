# Security Agent

DDoS Detection and Threat Mitigation service for NetWeaver Phase 2.

## Overview

The Security Agent protects the network against DDoS attacks and security threats using multi-layered detection and automated mitigation strategies.

## Features

### 🛡️ DDoS Detection

**Volumetric Attacks**
- High packets per second (PPS) detection
- High bandwidth utilization detection
- Threshold-based alerting

**Protocol Attacks**
- SYN flood detection
- UDP flood detection
- ICMP flood detection
- Connection exhaustion detection

**Application Attacks**
- Port scanning detection
- HTTP flood detection
- Slowloris detection

### 🤖 ML-Based Anomaly Detection

- **Isolation Forest**: Unsupervised outlier detection
- **Feature Engineering**: 10+ traffic features extracted
- **Real-time Analysis**: Sub-second anomaly detection
- **Continuous Learning**: Models retrain on new data

### 🔧 Automatic Mitigation

**Blackhole Routing**
- Null route malicious traffic
- Deploy to edge routers
- Instant traffic drop

**Rate Limiting**
- Limit packets per second from source
- Configurable thresholds
- Per-IP enforcement

**ACL Blocking**
- Block specific IP addresses
- Protocol-specific rules
- Port-based filtering

**WAF Rules**
- SQL injection protection
- XSS prevention
- Command injection blocking

### 📊 Threat Intelligence

- Attack pattern recognition
- Historical threat analysis
- Real-time statistics
- Integration with Self-Healing System

## Architecture

```
RabbitMQ (flow.records) → DDoS Detector → Threat Storage (PostgreSQL)
                               ↓
                        Anomaly Detector (ML)
                               ↓
                         Threat Mitigator
                               ↓
                    Device Manager (Config Push)
```

## API Endpoints

### Threat Management

#### List Threats
```http
GET /api/v1/threats?status=detected&severity=critical&limit=50
```

**Response:**
```json
{
  "count": 5,
  "threats": [
    {
      "id": "threat-1771056789123456",
      "threat_type": "ddos_volumetric",
      "severity": "critical",
      "status": "detected",
      "source_ips": ["192.168.1.100"],
      "target_ips": ["10.0.0.1"],
      "detected_at": "2026-02-14T10:15:30Z",
      "details": {
        "attack_type": "high_pps",
        "value": 25000,
        "threshold": 10000
      }
    }
  ]
}
```

#### Get Threat Details
```http
GET /api/v1/threats/{threat_id}
```

**Response:**
```json
{
  "threat": {
    "id": "threat-1771056789123456",
    "threat_type": "ddos_protocol",
    "severity": "high",
    "status": "mitigated",
    "source_ips": ["192.168.1.100"],
    "detected_at": "2026-02-14T10:15:30Z",
    "mitigated_at": "2026-02-14T10:15:45Z",
    "details": {
      "attack_type": "syn_flood",
      "syn_count": 5000,
      "syn_ratio": 0.95
    }
  },
  "attacks": [
    {
      "id": 1,
      "attack_type": "syn_flood",
      "source_ip": "192.168.1.100",
      "packets": 5000,
      "bytes": 300000,
      "timestamp": "2026-02-14T10:15:30Z"
    }
  ],
  "mitigations": [
    {
      "id": 1,
      "mitigation_type": "rate_limit",
      "target_ips": ["192.168.1.100"],
      "applied_at": "2026-02-14T10:15:45Z",
      "status": "active"
    }
  ]
}
```

#### Resolve Threat
```http
POST /api/v1/threats/{threat_id}/resolve
```

### Mitigation

#### Trigger Manual Mitigation
```http
POST /api/v1/mitigate
Content-Type: application/json

{
  "threat_id": "threat-1771056789123456",
  "mitigation_type": "blackhole",
  "target_ips": ["192.168.1.100"]
}
```

**Mitigation Types:**
- `blackhole` - Null route traffic
- `rate_limit` - Rate limit source
- `acl` - Block with ACL
- `waf` - Apply WAF rules

#### Rollback Mitigation
```http
POST /api/v1/rollback/{threat_id}
```

### Statistics

#### Get Security Statistics
```http
GET /api/v1/stats
```

**Response:**
```json
{
  "total_threats": 127,
  "active_threats": 5,
  "mitigated_threats": 95,
  "resolved_threats": 27,
  "critical_threats": 15,
  "high_threats": 42,
  "medium_threats": 70,
  "threats_24h": 23
}
```

#### Get Attack Statistics
```http
GET /api/v1/stats/attacks?hours=24
```

**Response:**
```json
{
  "period_hours": 24,
  "attack_types": [
    {
      "attack_type": "syn_flood",
      "count": 15,
      "total_packets": 750000,
      "total_bytes": 45000000
    },
    {
      "attack_type": "udp_flood",
      "count": 8,
      "total_packets": 500000,
      "total_bytes": 60000000
    }
  ]
}
```

### Anomaly Detection

#### Analyze Traffic
```http
POST /api/v1/anomaly/analyze
Content-Type: application/json

{
  "packets_per_second": 15000,
  "bytes_per_second": 120000000,
  "protocol_distribution": {"tcp": 100, "udp": 50},
  "connection_rate": 500,
  "unique_dst_ips": 100
}
```

**Response:**
```json
{
  "is_anomaly": true,
  "anomaly_score": -0.85,
  "timestamp": "2026-02-14T10:15:30Z"
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
  "thresholds": {
    "pps_threshold": 10000,
    "bps_threshold": 100000000,
    "connections_threshold": 1000,
    "syn_ratio_threshold": 0.8,
    "udp_ratio_threshold": 0.7,
    "icmp_ratio_threshold": 0.5
  },
  "detection_window": "60s",
  "mitigation_enabled": true
}
```

#### Update Thresholds
```http
PUT /api/v1/config/thresholds
Content-Type: application/json

{
  "pps_threshold": 15000,
  "syn_ratio_threshold": 0.85
}
```

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
RABBITMQ_PASS=netweaver_rabbitmq_2026

# Device Manager
DEVICE_MANAGER_URL=http://device-manager:8083

# Thresholds
PPS_THRESHOLD=10000
BPS_THRESHOLD=100000000
CONN_THRESHOLD=1000
SYN_RATIO_THRESHOLD=0.8
UDP_RATIO_THRESHOLD=0.7
ICMP_RATIO_THRESHOLD=0.5

# Server
PORT=8084
```

### Detection Thresholds

| Threshold | Default | Description |
|-----------|---------|-------------|
| pps_threshold | 10,000 | Packets per second |
| bps_threshold | 100 Mbps | Bits per second |
| connections_threshold | 1,000 | Concurrent connections |
| syn_ratio_threshold | 0.8 | SYN/(SYN+ACK) ratio |
| udp_ratio_threshold | 0.7 | UDP packet ratio |
| icmp_ratio_threshold | 0.5 | ICMP packet ratio |

## Quick Start

### Standalone

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DB_HOST=localhost
export RABBITMQ_HOST=localhost

# Run
python main.py
```

### Docker

```bash
# Build image
docker build -t netweaver-security-agent .

# Run container
docker run -d \
  --name security-agent \
  -p 8084:8084 \
  -e DB_HOST=timescaledb \
  -e RABBITMQ_HOST=rabbitmq \
  netweaver-security-agent
```

### Docker Compose

```bash
# Start security agent with all dependencies
docker-compose up -d security-agent
```

## Detection Algorithms

### Volumetric DDoS

**High PPS Detection**
```python
pps = total_packets / window_duration
if pps > pps_threshold:
    trigger_alert('high_pps', severity='critical')
```

**High Bandwidth Detection**
```python
bps = total_bytes * 8 / window_duration
if bps > bps_threshold:
    trigger_alert('high_bandwidth', severity='critical')
```

### Protocol DDoS

**SYN Flood Detection**
```python
syn_ratio = syn_count / (syn_count + ack_count)
if syn_ratio > 0.8 and syn_count > 100:
    trigger_alert('syn_flood', severity='high')
```

**UDP Flood Detection**
```python
udp_ratio = udp_packets / total_packets
if udp_ratio > 0.7 and udp_packets > 1000:
    trigger_alert('udp_flood', severity='high')
```

### ML Anomaly Detection

**Feature Extraction**
```python
features = [
    packets_per_second,
    bytes_per_second,
    avg_packet_size,
    protocol_entropy,
    port_entropy,
    connection_rate,
    syn_ack_ratio,
    unique_dst_ips,
    unique_src_ports,
    unique_dst_ports
]
```

**Isolation Forest**
```python
scaler = StandardScaler()
features_scaled = scaler.transform([features])
prediction = isolation_forest.predict(features_scaled)
score = isolation_forest.score_samples(features_scaled)

if prediction == -1:  # Anomaly detected
    trigger_alert('anomaly', score=score)
```

## Mitigation Strategies

### Blackhole Routing

**Cisco IOS:**
```cisco
ip route 192.168.1.100 255.255.255.255 Null0
```

**Effect:** All traffic to/from IP is dropped at edge router

### Rate Limiting

**Cisco IOS:**
```cisco
ip access-list extended RATE_LIMIT_192_168_1_100
 permit ip host 192.168.1.100 any

class-map match-all RATELIMIT-192_168_1_100
 match access-group name RATE_LIMIT_192_168_1_100

policy-map DDOS-RATELIMIT
 class RATELIMIT-192_168_1_100
  police 1000 pps conform-action transmit exceed-action drop
```

**Effect:** Limits traffic to 1000 packets/second

### ACL Blocking

**Cisco IOS:**
```cisco
ip access-list extended BLOCK_192_168_1_100
 deny ip host 192.168.1.100 any
 permit ip any any

interface GigabitEthernet0/0/0
 ip access-group BLOCK_192_168_1_100 in
```

**Effect:** Blocks all traffic from source IP

## Integration

### With Self-Healing System

Security Agent can trigger Self-Healing System for automated remediation:

```python
# When critical threat detected
if threat.severity == 'critical':
    create_incident_in_self_healing(threat)
```

### With Telemetry Agent (Phase 1)

Consumes flow records from Phase 1 telemetry:

```python
# Subscribe to flow.records queue
queue = await channel.declare_queue('flow.records', durable=True)
```

## Performance

### Detection Speed
- Flow processing: 10,000+ flows/second
- Anomaly detection: <100ms per sample
- Threat creation: <10ms

### Mitigation Speed
- Config generation: <50ms
- Config deployment: <2s (via Device Manager)
- Total MTTR: <30s from detection to mitigation

## Monitoring

### Health Check

```bash
curl http://localhost:8084/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "security-agent",
  "timestamp": "2026-02-14T10:30:00Z",
  "components": {
    "ddos_detector": true,
    "anomaly_detector": true,
    "mitigator": true,
    "storage": true
  }
}
```

### Metrics

- `threats_detected_total` - Total threats detected
- `threats_by_type` - Threats by type (volumetric, protocol, application)
- `mitigations_applied_total` - Total mitigations applied
- `anomalies_detected_total` - ML-based anomalies
- `detection_latency_ms` - Time from attack to detection

## Troubleshooting

### Service Won't Start

**Check RabbitMQ connection:**
```bash
docker logs netweaver-security-agent | grep "RabbitMQ"
```

**Check database:**
```bash
docker logs netweaver-security-agent | grep "PostgreSQL"
```

### No Threats Detected

1. Verify flow records are being published to `flow.records` queue
2. Check thresholds are not too high
3. Review logs for processing errors

```bash
docker logs --tail 100 netweaver-security-agent
```

### Mitigation Not Applied

**Check Device Manager connectivity:**
```bash
curl http://localhost:8083/health
```

**View failed mitigations:**
```bash
curl http://localhost:8084/api/v1/threats?status=mitigation_failed
```

## Future Enhancements

- [ ] Distributed DDoS detection across multiple collectors
- [ ] Deep learning models (LSTM, GRU) for sequence analysis
- [ ] Threat intelligence feed integration (MISP, OTX)
- [ ] Automatic tuning of detection thresholds
- [ ] Geolocation-based blocking
- [ ] Rate limiting by country/ASN
- [ ] Advanced WAF with OWASP ModSecurity rules
- [ ] BGP FlowSpec integration for upstream mitigation
- [ ] Incident response automation (SOAR integration)

## License

Copyright © 2026 NetWeaver Project

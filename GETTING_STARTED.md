# NetWeaver: Getting Started Guide

## Quick Start (5 Minutes)

### 1. Start the Infrastructure
```bash
# Start TimescaleDB, Redis, Prometheus, and Grafana
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 2. Run the Demo
```bash
# Install Python dependencies
pip install -r python/requirements.txt

# Run the integration demo
python scripts/demo.py
```

### 3. Run the Network Simulator
```bash
# Navigate to simulator directory
cd simulator

# Run simulator (demonstrates routing optimization on 100-node network)
go run network_simulator.go
```

---

## Full Setup Guide

### Prerequisites

#### Required Software
- **Go 1.21+**: For telemetry agent and routing optimizer
- **Python 3.10+**: For ML models
- **Docker & Docker Compose**: For infrastructure services
- **PostgreSQL/TimescaleDB 2.11+**: Time-series database

#### System Requirements
- **CPU**: 4+ cores recommended
- **RAM**: 8 GB minimum, 16 GB recommended
- **Storage**: 50 GB for database and logs
- **Network**: 1 Gbps NIC for production telemetry collection

---

## Step-by-Step Setup

### Step 1: Clone and Setup Project

```bash
# Navigate to NetWeaver directory
cd NetWeaver

# Install Go dependencies
go mod download

# Verify Go modules
go mod verify
```

### Step 2: Install Python Dependencies

```bash
# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r python/requirements.txt

# Verify installation
python -c "import torch; print(f'PyTorch version: {torch.__version__}')"
```

### Step 3: Start Infrastructure Services

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f timescaledb
```

**Services Started:**
- TimescaleDB: `localhost:5432`
- Redis: `localhost:6379`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin / netweaver2026)

### Step 4: Initialize Database

The database schema is automatically initialized when TimescaleDB starts. To manually initialize:

```bash
# Connect to database
docker exec -it netweaver-timescaledb psql -U netweaver -d netweaver

# Verify tables exist
\dt

# Check hypertables
SELECT hypertable_name FROM timescaledb_information.hypertables;

# Exit
\q
```

### Step 5: Configure Network Devices

Configure your network devices to export flow data to NetWeaver:

#### Cisco IOS/IOS-XE (NetFlow v5)
```
! Configure NetFlow exporter
ip flow-export version 5
ip flow-export destination 10.0.0.100 2055

! Enable NetFlow on interfaces
interface GigabitEthernet0/0
 ip flow ingress
 ip flow egress
```

#### Juniper Junos (sFlow)
```
set forwarding-options sampling instance NETWEAVER family inet output flow-server 10.0.0.100 port 6343
set forwarding-options sampling instance NETWEAVER input rate 1024
set interfaces ge-0/0/0 unit 0 family inet sampling input
```

#### Arista EOS (NetFlow v9)
```
flow tracking tracked NETWEAVER
   destination 10.0.0.100 2055
   record size 1400
   
interface Ethernet1
   flow tracker tracked NETWEAVER
```

### Step 6: Start Telemetry Agent

```bash
# Build telemetry agent
go build -o bin/telemetry-agent cmd/telemetry-agent/main.go

# Run agent
./bin/telemetry-agent --config configs/telemetry-agent.yaml
```

**Expected Output:**
```
INFO    Starting NetWeaver Telemetry Agent
INFO    NetFlow collector listening on 0.0.0.0:2055
INFO    sFlow collector listening on 0.0.0.0:6343
INFO    Telemetry Agent started successfully
```

### Step 7: Train ML Models

```bash
# Train LSTM model
python python/training/train_model.py \
  --model lstm \
  --epochs 50 \
  --output models/checkpoints

# Train Transformer model (requires more data)
python python/training/train_model.py \
  --model transformer \
  --epochs 100 \
  --output models/checkpoints/transformer
```

### Step 8: Run Network Simulator (Testing)

```bash
cd simulator
go run network_simulator.go
```

**Output includes:**
- Topology generation (100 nodes)
- Network statistics
- Routing benchmarks (Dijkstra, K-shortest paths)
- Performance metrics

---

## Testing the System

### Test 1: Verify Telemetry Collection

```bash
# Send test NetFlow packet using Python
python scripts/test_netflow.py

# Check database for received flows
docker exec -it netweaver-timescaledb psql -U netweaver -d netweaver -c \
  "SELECT COUNT(*) FROM flow_records;"
```

### Test 2: Run Unit Tests

```bash
# Go tests
go test ./pkg/netflow/... -v
go test ./pkg/routing/... -v

# Python tests (if implemented)
pytest python/tests/
```

### Test 3: Benchmark Performance

```bash
# Routing algorithm benchmark
cd simulator
go test -bench=. -benchmem

# Expected: <1ms per path computation for 100-node network
```

---

## Configuration

### Telemetry Agent Configuration

Edit `configs/telemetry-agent.yaml`:

```yaml
collectors:
  netflow:
    listen: "0.0.0.0:2055"
    workers: 16              # Increase for higher throughput
    enabled: true
  
  sflow:
    listen: "0.0.0.0:6343"
    workers: 16
    enabled: true

database:
  host: "localhost"
  port: 5432
  database: "netweaver"
  user: "netweaver"
  password: "netweaver_secure_pass_2026"
  pool_size: 50              # Connection pool size

performance:
  buffer_size: 10000         # Flows buffered before DB insert
  flush_interval: 5          # Seconds between forced flushes
  udp_buffer_size: 26214400  # 25 MB OS UDP buffer

monitoring:
  enabled: true
  stats_interval: 30         # Statistics logging interval
```

### ML Model Configuration

Create `configs/training.yaml`:

```yaml
model:
  type: "lstm"               # lstm, transformer, multi_horizon
  input_size: 10
  hidden_size: 128
  num_layers: 3
  dropout: 0.2

training:
  learning_rate: 0.001
  batch_size: 32
  epochs: 50
  weight_decay: 1e-5

data:
  sequence_length: 60        # 1 hour of 1-minute samples
  prediction_horizon: 5      # Predict 5 minutes ahead
  train_ratio: 0.7
  val_ratio: 0.15
```

---

## Monitoring and Visualization

### Grafana Dashboards

1. Open Grafana: `http://localhost:3000`
2. Login: admin / netweaver2026
3. Import dashboard: `deployments/grafana-dashboards/network-overview.json`

**Key Metrics:**
- Flow records per second
- Top talkers (bandwidth consumers)
- Protocol distribution
- Link utilization
- Latency trends

### Prometheus Metrics

View raw metrics: `http://localhost:9090`

**Example Queries:**
```promql
# Flows received per second
rate(netweaver_flows_received_total[5m])

# Database insert rate
rate(netweaver_db_inserts_total[5m])

# Parse errors
netweaver_parse_errors_total
```

---

## Troubleshooting

### Issue: Telemetry Agent Won't Start

**Symptoms:** Port already in use
```
Error: bind: address already in use
```

**Solution:**
```bash
# Check what's using port 2055
netstat -an | grep 2055

# Kill process or change port in config
```

### Issue: No Flow Records in Database

**Checklist:**
1. ✓ Telemetry agent running
2. ✓ Network devices configured to export flows
3. ✓ Firewall allows UDP 2055 (NetFlow) and 6343 (sFlow)
4. ✓ Database connection working

**Debug:**
```bash
# Check telemetry agent logs
journalctl -u telemetry-agent -f

# Capture packets to verify flows are arriving
tcpdump -i any udp port 2055 -w netflow.pcap
```

### Issue: ML Training Fails - Not Enough Data

**Solution:** Generate synthetic data for testing:
```python
python scripts/generate_test_data.py --days 7 --flows-per-minute 1000
```

### Issue: High CPU Usage

**Cause:** Too many worker threads

**Solution:** Reduce workers in `configs/telemetry-agent.yaml`:
```yaml
collectors:
  netflow:
    workers: 8  # Reduce from 16
  sflow:
    workers: 8
```

---

## Performance Tuning

### Database Optimization

```sql
-- Increase shared_buffers for better performance
ALTER SYSTEM SET shared_buffers = '4GB';

-- Increase max connections
ALTER SYSTEM SET max_connections = 200;

-- Reload configuration
SELECT pg_reload_conf();
```

### OS-Level Tuning (Linux)

```bash
# Increase UDP receive buffer
sudo sysctl -w net.core.rmem_max=26214400
sudo sysctl -w net.core.rmem_default=26214400

# Increase file descriptors
ulimit -n 65536

# Make permanent: Add to /etc/sysctl.conf
```

---

## Production Deployment

### Systemd Service (Linux)

Create `/etc/systemd/system/netweaver-telemetry.service`:

```ini
[Unit]
Description=NetWeaver Telemetry Agent
After=network.target

[Service]
Type=simple
User=netweaver
WorkingDirectory=/opt/netweaver
ExecStart=/opt/netweaver/bin/telemetry-agent --config /opt/netweaver/configs/telemetry-agent.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable netweaver-telemetry
sudo systemctl start netweaver-telemetry
sudo systemctl status netweaver-telemetry
```

---

## Next Steps

1. **Configure Real Devices**: Point your network devices to export flows
2. **Train Production Models**: Collect 7+ days of data for accurate ML models
3. **Setup Monitoring**: Configure alerts in Prometheus/Grafana
4. **Implement Optimization**: Deploy routing changes based on predictions
5. **Scale Up**: Add more telemetry agents for distributed collection

---

## Additional Resources

- [NetFlow RFC 3954](https://tools.ietf.org/html/rfc3954)
- [sFlow Specification](https://sflow.org/sflow_version_5.txt)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [PyTorch Tutorials](https://pytorch.org/tutorials/)

---

## Support

For issues and questions:
1. Check logs: `docker-compose logs -f`
2. Review documentation: `README.md`
3. Open an issue on GitHub

**Contact:** See README.md for contact information

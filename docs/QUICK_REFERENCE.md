# NetWeaver Quick Reference Card

## 🚀 Quick Start Commands

### Database
```bash
# Start TimescaleDB
docker-compose up -d timescaledb

# Initialize schema
psql -h localhost -U netweaver -d netweaver -f deployments/init-db.sql

# Check health
psql -h localhost -U netweaver -d netweaver -c "SELECT * FROM device_health;"
```

### Telemetry Agent
```bash
# Build
cd cmd/telemetry-agent
go build -o telemetry-agent.exe

# Run (listens on UDP 2055 for NetFlow, 6343 for sFlow)
./telemetry-agent.exe
```

### Machine Learning
```bash
# Install dependencies
pip install torch numpy scikit-learn psycopg2-binary

# Train LSTM model
python python/models/train_traffic_lstm.py

# Run predictions (requires trained model checkpoint)
python python/models/traffic_predictor.py
```

### Routing Optimization
```bash
# Run tests
cd pkg/routing
go test -v

# Run simulator
cd cmd/network-simulator
go build -o simulator.exe
./simulator.exe
```

---

## 🧪 Testing & Validation

### Unit Tests
```bash
# ML model tests (19 tests)
python python/tests/test_models.py
```

### Integration Tests
```bash
# End-to-end system test (5 tests)
python scripts/integration_test.py
```

### Performance Benchmarks
```bash
# Comprehensive performance benchmark
python scripts/benchmark_performance.py
```

---

## 📊 Common Queries

### Database Queries
```sql
-- Count total flows
SELECT COUNT(*) FROM flow_records;

-- Top talkers (last hour)
SELECT * FROM get_top_talkers(NOW() - INTERVAL '1 hour', NOW(), 10);

-- Interface utilization
SELECT * FROM interface_utilization ORDER BY timestamp DESC LIMIT 100;

-- Device health
SELECT * FROM device_health;

-- Traffic anomalies
SELECT * FROM traffic_anomalies WHERE timestamp > NOW() - INTERVAL '1 day';
```

### Python Database Client
```python
from database.enhanced_client import DatabaseClient
from datetime import datetime, timedelta

# Initialize client
client = DatabaseClient(
    host='localhost',
    port=5432,
    database='netweaver',
    user='netweaver',
    password='netweaver_secure_pass_2026'
)

# Get top talkers
end_time = datetime.now()
start_time = end_time - timedelta(hours=1)
results = client.get_top_talkers(start_time, end_time, limit=10)

# Get interface utilization
results = client.get_interface_utilization('192.168.1.1', start_time, end_time)

# Health check
is_healthy = client.health_check()

# Close connection
client.close()
```

---

## 🔧 Configuration

### Database Connection
```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'netweaver',
    'user': 'netweaver',
    'password': 'netweaver_secure_pass_2026',
    'min_connections': 5,
    'max_connections': 20,
}
```

### Telemetry Agent Ports
- **NetFlow**: UDP 2055
- **sFlow**: UDP 6343

### ML Model Hyperparameters
```python
# LSTM Model
input_size = 10      # Number of features
hidden_size = 128    # Hidden layer size (128 or 256)
num_layers = 2       # Number of LSTM layers
output_size = 1      # Prediction output
seq_length = 60      # Time steps to look back

# Training
batch_size = 32
learning_rate = 0.001
epochs = 10
```

---

## 📈 Performance Targets

| Component | Metric | Target | Current |
|-----------|--------|--------|---------|
| ML Inference | Latency | <10ms | 6.5ms |
| ML Inference | Throughput | >1K/sec | 5.7K/sec |
| Database | Simple Query | <10ms | 2-4ms |
| Database | Complex Query | <50ms | <7ms |
| Routing | Path Calc | <5ms | 0.057ms |
| Telemetry | Processing | >100K/sec | 1M+/sec |

---

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check if TimescaleDB is running
docker ps | grep timescaledb

# Check connection pool stats
python -c "from database.enhanced_client import DatabaseClient; \
           c = DatabaseClient(); print(c.get_pool_stats()); c.close()"

# Test connection
psql -h localhost -U netweaver -d netweaver
```

### Telemetry Agent Issues
```bash
# Check if ports are in use
netstat -an | findstr "2055"
netstat -an | findstr "6343"

# Send test NetFlow packet
python scripts/integration_test.py
```

### ML Model Issues
```bash
# Verify model checkpoint exists
dir checkpoints\traffic_lstm_*.pth

# Test model loading
python -c "from models.traffic_predictor import TrafficLSTM; \
           import torch; \
           model = TrafficLSTM(10, 128, 1); \
           checkpoint = torch.load('checkpoints/traffic_lstm_best.pth'); \
           model.load_state_dict(checkpoint['model_state_dict']); \
           print('Model loaded successfully')"
```

### Routing Tests Failing
```bash
# Clean and rebuild
cd pkg/routing
go clean -testcache
go test -v

# Check Go version
go version  # Should be 1.21+
```

---

## 📦 Dependencies

### Go Modules
- `github.com/google/gopacket` - Packet processing
- `github.com/lib/pq` - PostgreSQL driver

### Python Packages
- `torch>=2.0.0` - PyTorch ML framework
- `numpy>=1.24.0` - Numerical computing
- `scikit-learn>=1.3.0` - ML utilities
- `psycopg2-binary>=2.9.0` - PostgreSQL driver

### Infrastructure
- **TimescaleDB**: 2.x (PostgreSQL extension)
- **Docker**: For database deployment

---

## 🔐 Security Notes

### Database Password
Default password: `netweaver_secure_pass_2026`

**⚠️ IMPORTANT**: Change this before production deployment!

```sql
ALTER USER netweaver WITH PASSWORD 'your_secure_password_here';
```

### Network Exposure
- Telemetry agent binds to `0.0.0.0` (all interfaces)
- Consider firewall rules in production
- Use VLANs or network segmentation

---

## 📚 Documentation

- **[README.md](../docs/README.md)**: Project overview
- **[GETTING_STARTED.md](../docs/GETTING_STARTED.md)**: Detailed setup guide
- **[ARCHITECTURE.md](../docs/ARCHITECTURE.md)**: Technical architecture
- **[PROJECT_SUMMARY.md](../docs/PROJECT_SUMMARY.md)**: Complete summary
- **[SYSTEM_STATUS.md](../docs/SYSTEM_STATUS.md)**: Current system status

---

## 🎯 Key Files

```
NetWeaver/
├── cmd/
│   ├── telemetry-agent/main.go      # NetFlow/sFlow collector
│   └── network-simulator/main.go    # Network simulator
├── pkg/
│   └── routing/optimizer.go         # Routing algorithms
├── python/
│   ├── models/traffic_predictor.py  # ML models
│   ├── database/enhanced_client.py  # Database client
│   └── tests/test_models.py         # Unit tests
├── scripts/
│   ├── integration_test.py          # Integration tests
│   └── benchmark_performance.py     # Performance tests
└── deployments/
    └── init-db.sql                  # Database schema
```

---

## ✅ System Health Checks

```bash
# Complete system validation (recommended)
python scripts/integration_test.py

# Quick checks
echo "1. Database:" && psql -h localhost -U netweaver -d netweaver -c "SELECT COUNT(*) FROM flow_records;"
echo "2. ML Models:" && python python/tests/test_models.py
echo "3. Routing:" && cd pkg/routing && go test -v
echo "4. Performance:" && python scripts/benchmark_performance.py
```

---

Generated: 2025-01-19
Version: 1.0.0 (Phase 1 Complete)

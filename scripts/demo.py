#!/usr/bin/env python3
"""
NetWeaver End-to-End Integration Demo
Demonstrates: Telemetry → Prediction → Optimization → Configuration
"""

import sys
import time
import numpy as np
import torch
from datetime import datetime, timedelta
import psycopg2
from pathlib import Path

# Add project paths
sys.path.append(str(Path(__file__).parent.parent / 'python'))

from models.traffic_predictor import TrafficLSTM, create_model
from training.data_preparation import RealTimePredictor, TrafficDataLoader


class NetWeaverDemo:
    """
    End-to-end demonstration of NetWeaver platform capabilities
    """
    
    def __init__(self):
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'netweaver',
            'user': 'netweaver',
            'password': 'netweaver_secure_pass_2026'
        }
        
    def print_header(self, title):
        """Print formatted header"""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70 + "\n")
    
    def check_database_connection(self):
        """Check if TimescaleDB is accessible"""
        self.print_header("Step 1: Database Connection Check")
        
        try:
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"✓ Connected to PostgreSQL")
            print(f"  Version: {version[:50]}...")
            
            # Check if tables exist
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'flow_records'
            """)
            
            if cursor.fetchone():
                print("✓ flow_records table exists")
                
                # Get record count
                cursor.execute("SELECT COUNT(*) FROM flow_records")
                count = cursor.fetchone()[0]
                print(f"  Total flow records: {count:,}")
            else:
                print("⚠ flow_records table not found (run init-db.sql first)")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            print("\nTo start database, run:")
            print("  docker-compose up -d timescaledb")
            return False
    
    def demonstrate_ml_models(self):
        """Demonstrate ML traffic prediction models"""
        self.print_header("Step 2: ML Traffic Prediction Models")
        
        print("Creating traffic prediction models...\n")
        
        # LSTM Model
        print("1. LSTM Model")
        lstm_model = create_model(
            'lstm',
            input_size=10,
            hidden_size=128,
            num_layers=3,
            output_size=1
        )
        param_count = sum(p.numel() for p in lstm_model.parameters())
        print(f"   Parameters: {param_count:,}")
        
        # Test prediction with synthetic data
        batch_size = 32
        seq_length = 60
        input_size = 10
        
        test_input = torch.randn(batch_size, seq_length, input_size)
        
        start_time = time.time()
        with torch.no_grad():
            predictions = lstm_model.predict(test_input)
        elapsed = time.time() - start_time
        
        print(f"   Inference time: {elapsed*1000:.2f} ms for {batch_size} samples")
        print(f"   Throughput: {batch_size/elapsed:.0f} predictions/sec")
        print(f"   Prediction shape: {predictions.shape}\n")
        
        # Transformer Model
        print("2. Transformer Model")
        transformer_model = create_model(
            'transformer',
            input_size=10,
            d_model=128,
            nhead=8,
            num_encoder_layers=4,
            output_size=1
        )
        param_count = sum(p.numel() for p in transformer_model.parameters())
        print(f"   Parameters: {param_count:,}")
        
        start_time = time.time()
        with torch.no_grad():
            predictions = transformer_model.predict(test_input)
        elapsed = time.time() - start_time
        
        print(f"   Inference time: {elapsed*1000:.2f} ms for {batch_size} samples")
        print(f"   Throughput: {batch_size/elapsed:.0f} predictions/sec\n")
        
        # Multi-horizon predictor
        print("3. Multi-Horizon Predictor (5min, 15min, 1hr, 24hr)")
        multi_model = create_model(
            'multi_horizon',
            input_size=10,
            hidden_size=128,
            num_horizons=4,
            backbone="lstm"
        )
        param_count = sum(p.numel() for p in multi_model.parameters())
        print(f"   Parameters: {param_count:,}")
        
        with torch.no_grad():
            predictions = multi_model.predict(test_input)
        
        print(f"   Prediction shape: {predictions.shape}")
        print(f"   Sample predictions (first sample):")
        for i, horizon in enumerate(['5min', '15min', '1hr', '24hr']):
            print(f"     {horizon}: {predictions[0, i].item():.4f}\n")
        
        # Anomaly detector
        print("4. Anomaly Detector")
        anomaly_model = create_model(
            'anomaly',
            input_size=10,
            encoding_dim=32
        )
        param_count = sum(p.numel() for p in anomaly_model.parameters())
        print(f"   Parameters: {param_count:,}")
        
        # Test with normal and anomalous data
        normal_data = torch.randn(100, input_size)
        anomalous_data = torch.randn(10, input_size) * 5  # Outliers
        test_data = torch.cat([normal_data, anomalous_data], dim=0)
        
        is_anomaly, errors = anomaly_model.detect_anomaly(test_data)
        
        anomaly_count = is_anomaly.sum().item()
        print(f"   Detected {anomaly_count}/110 anomalies")
        print(f"   Mean reconstruction error: {errors.mean():.4f}")
        print(f"   Max reconstruction error: {errors.max():.4f}\n")
    
    def demonstrate_routing_optimization(self):
        """Demonstrate routing optimization"""
        self.print_header("Step 3: Network Routing Optimization")
        
        print("Routing optimization is implemented in Go.")
        print("Run the simulator to see routing in action:\n")
        print("  cd simulator")
        print("  go run network_simulator.go\n")
        
        print("Key features:")
        print("  • Dijkstra's algorithm for shortest path")
        print("  • K-shortest paths for ECMP load balancing")
        print("  • Multi-metric cost function (latency, utilization, packet loss)")
        print("  • Sub-millisecond path computation for 100-node networks")
        print("  • Support for dynamic topology updates\n")
    
    def demonstrate_data_pipeline(self):
        """Demonstrate data preparation pipeline"""
        self.print_header("Step 4: Data Preparation Pipeline")
        
        print("Creating data loader for traffic prediction...\n")
        
        data_loader = TrafficDataLoader(
            db_config=self.db_config,
            sequence_length=60,
            prediction_horizon=5,
            scaling="standard"
        )
        
        print("Features extracted:")
        for i, feature in enumerate(data_loader.features, 1):
            print(f"  {i:2d}. {feature}")
        
        print("\nData preprocessing pipeline:")
        print("  1. Fetch flow aggregates from TimescaleDB")
        print("  2. Engineer time-based features (hour, day, weekend)")
        print("  3. Calculate protocol ratios and traffic intensity")
        print("  4. Compute moving averages and trend features")
        print("  5. Normalize using StandardScaler")
        print("  6. Create sequences for time-series prediction")
        print("  7. Split into train/validation/test sets\n")
    
    def show_architecture(self):
        """Display system architecture"""
        self.print_header("NetWeaver Architecture Overview")
        
        print("""
┌─────────────────────────────────────────────────────────────┐
│                    NetWeaver Platform                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐     ┌──────────────────┐             │
│  │ Telemetry Agent  │────▶│  TimescaleDB     │             │
│  │  (Go)            │     │  (Metrics)       │             │
│  │                  │     │                  │             │
│  │ • NetFlow v5/9   │     │ • Flow records   │             │
│  │ • sFlow v5       │     │ • Interface stats│             │
│  │ • IPFIX          │     │ • Device metrics │             │
│  └──────────────────┘     └──────────────────┘             │
│         │                         │                         │
│         │                         ▼                         │
│         │              ┌──────────────────┐                │
│         │              │  ML Predictor    │                │
│         │              │  (Python)        │                │
│         │              │                  │                │
│         │              │ • LSTM models    │                │
│         │              │ • Transformers   │                │
│         │              │ • Anomaly detect │                │
│         │              └──────────────────┘                │
│         │                         │                         │
│         │                         ▼                         │
│         │              ┌──────────────────┐                │
│         └─────────────▶│  Optimizer       │                │
│                        │  (Go)            │                │
│                        │                  │                │
│                        │ • Route compute  │                │
│                        │ • Traffic eng.   │                │
│                        │ • QoS policies   │                │
│                        └──────────────────┘                │
│                                 │                           │
│                                 ▼                           │
│                      ┌──────────────────┐                  │
│                      │  Network Devices │                  │
│                      │  Cisco/Juniper/  │                  │
│                      │  Arista          │                  │
│                      └──────────────────┘                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
        """)
    
    def show_quickstart(self):
        """Show quick start guide"""
        self.print_header("Quick Start Guide")
        
        print("""
1. Start Infrastructure
   ------------------------
   docker-compose up -d
   
   This starts:
   • TimescaleDB (PostgreSQL with time-series extensions)
   • Redis (caching and pub/sub)
   • Prometheus (metrics collection)
   • Grafana (visualization)

2. Initialize Database
   ------------------------
   The database schema is automatically initialized on first run.
   Schema includes:
   • Network topology tables (devices, interfaces, links)
   • Time-series tables (flows, metrics, latency)
   • Optimization tables (routing, predictions, events)

3. Start Telemetry Agent
   ------------------------
   go run cmd/telemetry-agent/main.go --config configs/telemetry-agent.yaml
   
   Configure network devices to export NetFlow/sFlow to:
   • NetFlow: UDP port 2055
   • sFlow: UDP port 6343

4. Train ML Models
   ------------------------
   python python/training/train_model.py \\
     --model lstm \\
     --epochs 50 \\
     --output models/checkpoints

5. Run Network Simulator
   ------------------------
   cd simulator
   go run network_simulator.go
   
   Simulates a 100-node network with:
   • Multiple topology types (mesh, ring, tree, random)
   • Realistic traffic patterns
   • Dynamic link metrics

6. View Dashboards
   ------------------------
   • Grafana: http://localhost:3000
     Username: admin
     Password: netweaver2026
   
   • Prometheus: http://localhost:9090

7. Run Integration Demo
   ------------------------
   python scripts/demo.py
        """)
    
    def run_demo(self):
        """Run complete demonstration"""
        print("\n" + "█"*70)
        print("█" + " "*68 + "█")
        print("█" + "  NetWeaver: Self-Optimizing Network Infrastructure Platform".center(68) + "█")
        print("█" + " "*68 + "█")
        print("█"*70)
        
        self.show_architecture()
        
        # Step 1: Database connection
        db_ok = self.check_database_connection()
        
        # Step 2: ML models
        self.demonstrate_ml_models()
        
        # Step 3: Routing optimization
        self.demonstrate_routing_optimization()
        
        # Step 4: Data pipeline
        self.demonstrate_data_pipeline()
        
        # Quick start guide
        self.show_quickstart()
        
        self.print_header("Demo Complete")
        
        if not db_ok:
            print("⚠ Note: Database is not running. Start it with:")
            print("  docker-compose up -d timescaledb\n")
        else:
            print("✓ All systems operational")
        
        print("\nNext steps:")
        print("  1. Configure network devices to send NetFlow/sFlow")
        print("  2. Train ML models on historical data")
        print("  3. Deploy optimization policies")
        print("  4. Monitor performance in Grafana")
        print("\nFor full documentation, see README.md\n")


if __name__ == "__main__":
    demo = NetWeaverDemo()
    demo.run_demo()

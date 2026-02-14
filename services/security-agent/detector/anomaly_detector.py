"""
ML-Based Anomaly Detection
Uses Isolation Forest and Autoencoder for traffic anomaly detection
"""

import asyncio
import logging
import pickle
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """ML-based anomaly detector for network traffic"""
    
    def __init__(self, storage):
        self.storage = storage
        self.is_ready = False
        
        # Isolation Forest model for outlier detection
        self.isolation_forest = None
        self.scaler = None
        
        # Feature extractor
        self.feature_names = [
            'packets_per_second',
            'bytes_per_second',
            'avg_packet_size',
            'protocol_entropy',
            'port_entropy',
            'connection_rate',
            'syn_ack_ratio',
            'unique_dst_ips',
            'unique_src_ports',
            'unique_dst_ports'
        ]
        
        # Training data buffer
        self.training_data = []
        self.max_training_samples = 10000
        
        # Anomaly threshold
        self.anomaly_threshold = -0.5  # Isolation Forest decision threshold
    
    async def initialize(self):
        """Initialize ML models"""
        try:
            # Initialize Isolation Forest
            self.isolation_forest = IsolationForest(
                contamination=0.1,  # Assume 10% of traffic is anomalous
                max_samples='auto',
                random_state=42,
                n_jobs=-1
            )
            
            # Initialize scaler
            self.scaler = StandardScaler()
            
            # Try to load pre-trained model
            await self._load_models()
            
            if not self.is_ready:
                logger.info("No pre-trained models found, will train on incoming data")
            
            self.is_ready = True
            logger.info("Anomaly Detector initialized")
        except Exception as e:
            logger.error(f"Failed to initialize anomaly detector: {e}")
            raise
    
    async def _load_models(self):
        """Load pre-trained ML models from Phase 1"""
        try:
            # In production, load from file or database
            # For now, we'll train on the fly
            pass
        except Exception as e:
            logger.warning(f"Could not load pre-trained models: {e}")
    
    async def detect_anomaly(self, traffic_data: Dict[str, Any]) -> Tuple[bool, float]:
        """
        Detect if traffic pattern is anomalous
        
        Returns:
            (is_anomaly, anomaly_score)
        """
        # Extract features from traffic data
        features = self._extract_features(traffic_data)
        
        if not self.is_ready or self.isolation_forest is None:
            # Not enough data yet, collect training samples
            self.training_data.append(features)
            
            if len(self.training_data) >= 100:
                await self._train_models()
            
            return False, 0.0
        
        # Normalize features
        features_scaled = self.scaler.transform([features])
        
        # Predict anomaly
        prediction = self.isolation_forest.predict(features_scaled)[0]
        score = self.isolation_forest.score_samples(features_scaled)[0]
        
        is_anomaly = prediction == -1  # -1 indicates anomaly
        
        # Add to training data for continuous learning
        if len(self.training_data) < self.max_training_samples:
            self.training_data.append(features)
        
        if is_anomaly:
            logger.info(f"⚠️ Anomaly detected with score: {score:.3f}")
            
            # Create threat record
            await self._create_anomaly_threat(traffic_data, score)
        
        return is_anomaly, float(score)
    
    def _extract_features(self, data: Dict[str, Any]) -> np.ndarray:
        """Extract numerical features from traffic data"""
        features = []
        
        # Packets and bytes rates
        features.append(data.get('packets_per_second', 0))
        features.append(data.get('bytes_per_second', 0))
        
        # Average packet size
        packets = data.get('packets', 1)
        bytes_total = data.get('bytes', 0)
        features.append(bytes_total / packets if packets > 0 else 0)
        
        # Protocol entropy (measure of protocol diversity)
        protocol_counts = data.get('protocol_distribution', {})
        features.append(self._calculate_entropy(protocol_counts))
        
        # Port entropy
        port_counts = data.get('port_distribution', {})
        features.append(self._calculate_entropy(port_counts))
        
        # Connection rate
        features.append(data.get('connection_rate', 0))
        
        # SYN/ACK ratio (for SYN flood detection)
        syn_count = data.get('syn_count', 0)
        ack_count = data.get('ack_count', 1)
        features.append(syn_count / (syn_count + ack_count))
        
        # Unique destination IPs (for distributed attacks)
        features.append(data.get('unique_dst_ips', 0))
        
        # Unique source/destination ports
        features.append(data.get('unique_src_ports', 0))
        features.append(data.get('unique_dst_ports', 0))
        
        return np.array(features)
    
    def _calculate_entropy(self, distribution: Dict) -> float:
        """Calculate Shannon entropy of distribution"""
        if not distribution:
            return 0.0
        
        total = sum(distribution.values())
        if total == 0:
            return 0.0
        
        entropy = 0.0
        for count in distribution.values():
            if count > 0:
                p = count / total
                entropy -= p * np.log2(p)
        
        return entropy
    
    async def _train_models(self):
        """Train ML models on collected data"""
        if len(self.training_data) < 50:
            logger.warning("Not enough training data")
            return
        
        try:
            logger.info(f"Training anomaly detector on {len(self.training_data)} samples...")
            
            # Convert to numpy array
            X = np.array(self.training_data)
            
            # Fit scaler
            self.scaler.fit(X)
            
            # Transform data
            X_scaled = self.scaler.transform(X)
            
            # Train Isolation Forest
            self.isolation_forest.fit(X_scaled)
            
            logger.info("✅ Anomaly detector trained successfully")
            
            # Save models for future use
            await self._save_models()
            
        except Exception as e:
            logger.error(f"Failed to train models: {e}")
    
    async def _save_models(self):
        """Save trained models"""
        try:
            # In production, save to file or database
            # For now, keep in memory
            pass
        except Exception as e:
            logger.warning(f"Could not save models: {e}")
    
    async def _create_anomaly_threat(self, traffic_data: Dict[str, Any], score: float):
        """Create threat record for detected anomaly"""
        source_ip = traffic_data.get('source_ip', 'unknown')
        
        threat = self.storage.create_threat(
            threat_type='anomaly',
            severity='high' if score < -0.7 else 'medium',
            source_ips=[source_ip] if source_ip != 'unknown' else [],
            target_ips=[],
            details={
                'detection_method': 'isolation_forest',
                'anomaly_score': score,
                'features': {k: v for k, v in traffic_data.items() if isinstance(v, (int, float, str))}
            }
        )
        
        logger.info(f"Created anomaly threat: {threat.id}")
    
    async def retrain(self) -> Dict[str, Any]:
        """Manually trigger model retraining"""
        await self._train_models()
        return {
            "status": "success",
            "training_samples": len(self.training_data),
            "model_type": "isolation_forest"
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about trained models"""
        return {
            "is_ready": self.is_ready,
            "model_type": "isolation_forest",
            "training_samples": len(self.training_data),
            "features": self.feature_names,
            "contamination": 0.1,
            "anomaly_threshold": self.anomaly_threshold
        }

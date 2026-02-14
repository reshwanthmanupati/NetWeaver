"""
Security Agent - DDoS Detection and Mitigation
NetWeaver Phase 2 - Security Component
"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from detector.ddos_detector import DDoSDetector
from detector.anomaly_detector import AnomalyDetector
from mitigator.mitigator import ThreatMitigator
from storage.postgres import PostgresStorage, Threat, Attack, Mitigation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
ddos_detector = None
anomaly_detector = None
mitigator = None
storage = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global ddos_detector, anomaly_detector, mitigator, storage
    
    logger.info("🚀 Starting Security Agent...")
    
    # Initialize storage
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'netweaver'),
        'user': os.getenv('DB_USER', 'netweaver'),
        'password': os.getenv('DB_PASSWORD', 'netweaver_secure_pass_2026')
    }
    
    try:
        storage = PostgresStorage(db_config)
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        raise
    
    # Initialize DDoS detector
    rabbitmq_config = {
        'host': os.getenv('RABBITMQ_HOST', 'localhost'),
        'port': int(os.getenv('RABBITMQ_PORT', 5672)),
        'user': os.getenv('RABBITMQ_USER', 'netweaver'),
        'password': os.getenv('RABBITMQ_PASS', 'netweaver_rabbitmq_2026')
    }
    
    thresholds = {
        'pps_threshold': int(os.getenv('PPS_THRESHOLD', 10000)),  # packets per second
        'bps_threshold': int(os.getenv('BPS_THRESHOLD', 100000000)),  # 100 Mbps
        'connections_threshold': int(os.getenv('CONN_THRESHOLD', 1000)),
        'syn_ratio_threshold': float(os.getenv('SYN_RATIO_THRESHOLD', 0.8)),
        'udp_ratio_threshold': float(os.getenv('UDP_RATIO_THRESHOLD', 0.7)),
        'icmp_ratio_threshold': float(os.getenv('ICMP_RATIO_THRESHOLD', 0.5)),
    }
    
    ddos_detector = DDoSDetector(storage, rabbitmq_config, thresholds)
    await ddos_detector.start()
    logger.info("✅ DDoS Detector started")
    
    # Initialize ML-based anomaly detector
    anomaly_detector = AnomalyDetector(storage)
    await anomaly_detector.initialize()
    logger.info("✅ Anomaly Detector initialized")
    
    # Initialize threat mitigator
    device_manager_url = os.getenv('DEVICE_MANAGER_URL', 'http://localhost:8083')
    mitigator = ThreatMitigator(storage, device_manager_url)
    logger.info("✅ Threat Mitigator initialized")
    
    logger.info("🔒 Security Agent ready on port 8084")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down Security Agent...")
    if ddos_detector:
        await ddos_detector.stop()
    logger.info("✅ Security Agent stopped")


# Create FastAPI app
app = FastAPI(
    title="NetWeaver Security Agent",
    description="DDoS Detection and Threat Mitigation Service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class ThreatFilters(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    attack_type: Optional[str] = None
    limit: int = Field(default=100, le=1000)


class ManualMitigationRequest(BaseModel):
    threat_id: str
    mitigation_type: str  # blackhole, rate_limit, acl, waf
    target_ips: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None


class ThresholdUpdate(BaseModel):
    pps_threshold: Optional[int] = None
    bps_threshold: Optional[int] = None
    connections_threshold: Optional[int] = None
    syn_ratio_threshold: Optional[float] = None
    udp_ratio_threshold: Optional[float] = None
    icmp_ratio_threshold: Optional[float] = None


# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "security-agent",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "ddos_detector": ddos_detector.is_running if ddos_detector else False,
            "anomaly_detector": anomaly_detector.is_ready if anomaly_detector else False,
            "mitigator": mitigator is not None,
            "storage": storage is not None
        }
    }


# Threat Management
@app.get("/api/v1/threats")
async def get_threats(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    attack_type: Optional[str] = None,
    limit: int = 100
):
    """List threats with optional filters"""
    filters = {}
    if status:
        filters['status'] = status
    if severity:
        filters['severity'] = severity
    if attack_type:
        filters['attack_type'] = attack_type
    if limit:
        filters['limit'] = limit
    
    threats = storage.list_threats(filters)
    return {
        "count": len(threats),
        "threats": [t.to_dict() for t in threats]
    }


@app.get("/api/v1/threats/{threat_id}")
async def get_threat(threat_id: str):
    """Get threat details"""
    threat = storage.get_threat(threat_id)
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    attacks = storage.get_attacks_by_threat(threat_id)
    mitigations = storage.get_mitigations_by_threat(threat_id)
    
    return {
        "threat": threat.to_dict(),
        "attacks": [a.to_dict() for a in attacks],
        "mitigations": [m.to_dict() for m in mitigations]
    }


@app.post("/api/v1/threats/{threat_id}/resolve")
async def resolve_threat(threat_id: str):
    """Manually resolve a threat"""
    threat = storage.get_threat(threat_id)
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    storage.resolve_threat(threat_id)
    logger.info(f"Threat {threat_id} manually resolved")
    
    return {"message": "Threat resolved", "threat_id": threat_id}


# Mitigation
@app.post("/api/v1/mitigate")
async def trigger_mitigation(
    request: ManualMitigationRequest,
    background_tasks: BackgroundTasks
):
    """Manually trigger mitigation"""
    threat = storage.get_threat(request.threat_id)
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    # Trigger mitigation in background
    background_tasks.add_task(
        mitigator.mitigate,
        threat,
        request.mitigation_type,
        request.target_ips,
        request.parameters
    )
    
    return {
        "message": "Mitigation triggered",
        "threat_id": request.threat_id,
        "mitigation_type": request.mitigation_type
    }


@app.post("/api/v1/rollback/{threat_id}")
async def rollback_mitigation(threat_id: str):
    """Rollback mitigation actions"""
    threat = storage.get_threat(threat_id)
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    mitigations = storage.get_mitigations_by_threat(threat_id)
    if not mitigations:
        raise HTTPException(status_code=400, detail="No mitigations to rollback")
    
    try:
        await mitigator.rollback(threat_id, mitigations)
        storage.mark_threat_rolled_back(threat_id)
        return {"message": "Mitigation rolled back", "threat_id": threat_id}
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Statistics
@app.get("/api/v1/stats")
async def get_statistics():
    """Get security statistics"""
    stats = storage.get_statistics()
    return stats


@app.get("/api/v1/stats/attacks")
async def get_attack_statistics(hours: int = 24):
    """Get attack statistics for time period"""
    stats = storage.get_attack_statistics(hours)
    return stats


# Anomaly Detection
@app.post("/api/v1/anomaly/analyze")
async def analyze_traffic(data: Dict[str, Any]):
    """Analyze traffic for anomalies"""
    if not anomaly_detector.is_ready:
        raise HTTPException(status_code=503, detail="Anomaly detector not ready")
    
    is_anomaly, score = await anomaly_detector.detect_anomaly(data)
    
    return {
        "is_anomaly": is_anomaly,
        "anomaly_score": score,
        "timestamp": datetime.utcnow().isoformat()
    }


# Configuration
@app.get("/api/v1/config")
async def get_config():
    """Get current configuration"""
    return {
        "thresholds": ddos_detector.thresholds if ddos_detector else {},
        "detection_window": "60s",
        "mitigation_enabled": True
    }


@app.put("/api/v1/config/thresholds")
async def update_thresholds(thresholds: ThresholdUpdate):
    """Update detection thresholds"""
    if not ddos_detector:
        raise HTTPException(status_code=503, detail="DDoS detector not initialized")
    
    updated = {}
    for key, value in thresholds.dict(exclude_none=True).items():
        if value is not None:
            ddos_detector.thresholds[key] = value
            updated[key] = value
    
    logger.info(f"Thresholds updated: {updated}")
    return {"message": "Thresholds updated", "updated": updated}


# Threat Intelligence
@app.get("/api/v1/intel/sources")
async def get_intel_sources():
    """Get threat intelligence sources"""
    return {
        "sources": [
            {"name": "internal", "type": "flow_analysis", "status": "active"},
            {"name": "ml_anomaly", "type": "machine_learning", "status": "active"},
            {"name": "behavioral", "type": "pattern_analysis", "status": "active"}
        ]
    }


# Attack Patterns
@app.get("/api/v1/patterns")
async def get_attack_patterns():
    """Get known attack patterns"""
    patterns = storage.get_attack_patterns()
    return {"count": len(patterns), "patterns": patterns}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8084))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )

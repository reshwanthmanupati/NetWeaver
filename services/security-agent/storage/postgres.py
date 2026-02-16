"""
PostgreSQL Storage for Security Agent
Stores threats, attacks, and mitigation actions
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class Threat:
    """Threat model"""
    def __init__(self, id, threat_type, severity, status, source_ips, target_ips, 
                 detected_at, mitigated_at=None, resolved_at=None, details=None):
        self.id = id
        self.threat_type = threat_type
        self.severity = severity
        self.status = status
        self.source_ips = source_ips
        self.target_ips = target_ips
        self.detected_at = detected_at
        self.mitigated_at = mitigated_at
        self.resolved_at = resolved_at
        self.details = details or {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'threat_type': self.threat_type,
            'severity': self.severity,
            'status': self.status,
            'source_ips': self.source_ips,
            'target_ips': self.target_ips,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'mitigated_at': self.mitigated_at.isoformat() if self.mitigated_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'details': self.details
        }


class Attack:
    """Attack event model"""
    def __init__(self, id, threat_id, attack_type, source_ip, target_ip, 
                 packets, bytes_count, timestamp, details=None):
        self.id = id
        self.threat_id = threat_id
        self.attack_type = attack_type
        self.source_ip = source_ip
        self.target_ip = target_ip
        self.packets = packets
        self.bytes = bytes_count
        self.timestamp = timestamp
        self.details = details or {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'threat_id': self.threat_id,
            'attack_type': self.attack_type,
            'source_ip': self.source_ip,
            'target_ip': self.target_ip,
            'packets': self.packets,
            'bytes': self.bytes,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'details': self.details
        }


class Mitigation:
    """Mitigation action model"""
    def __init__(self, id, threat_id, mitigation_type, target_ips, config, 
                 parameters, applied_at, status):
        self.id = id
        self.threat_id = threat_id
        self.mitigation_type = mitigation_type
        self.target_ips = target_ips
        self.config = config
        self.parameters = parameters or {}
        self.applied_at = applied_at
        self.status = status
    
    def to_dict(self):
        return {
            'id': self.id,
            'threat_id': self.threat_id,
            'mitigation_type': self.mitigation_type,
            'target_ips': self.target_ips,
            'config': self.config,
            'parameters': self.parameters,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'status': self.status
        }


class PostgresStorage:
    """PostgreSQL storage for security data"""
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.conn = None
        self._connect()
        self._init_schema()
    
    def _connect(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=self.config['host'],
                port=self.config['port'],
                database=self.config['database'],
                user=self.config['user'],
                password=self.config['password']
            )
            logger.info("✅ Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            raise
    
    def _init_schema(self):
        """Initialize database schema"""
        schema = """
        -- Threats table
        CREATE TABLE IF NOT EXISTS threats (
            id VARCHAR(255) PRIMARY KEY,
            threat_type VARCHAR(100) NOT NULL,
            severity VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL,
            source_ips TEXT[] NOT NULL,
            target_ips TEXT[] NOT NULL,
            detected_at TIMESTAMP NOT NULL,
            mitigated_at TIMESTAMP,
            resolved_at TIMESTAMP,
            details JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_threats_type ON threats(threat_type);
        CREATE INDEX IF NOT EXISTS idx_threats_severity ON threats(severity);
        CREATE INDEX IF NOT EXISTS idx_threats_status ON threats(status);
        CREATE INDEX IF NOT EXISTS idx_threats_detected ON threats(detected_at DESC);
        
        -- Attacks table (individual attack events)
        CREATE TABLE IF NOT EXISTS attacks (
            id SERIAL PRIMARY KEY,
            threat_id VARCHAR(255) REFERENCES threats(id) ON DELETE CASCADE,
            attack_type VARCHAR(100) NOT NULL,
            source_ip VARCHAR(50) NOT NULL,
            target_ip VARCHAR(50),
            packets BIGINT DEFAULT 0,
            bytes BIGINT DEFAULT 0,
            timestamp TIMESTAMP NOT NULL,
            details JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_attacks_threat ON attacks(threat_id);
        CREATE INDEX IF NOT EXISTS idx_attacks_source ON attacks(source_ip);
        CREATE INDEX IF NOT EXISTS idx_attacks_timestamp ON attacks(timestamp DESC);
        
        -- Mitigations table
        CREATE TABLE IF NOT EXISTS mitigations (
            id SERIAL PRIMARY KEY,
            threat_id VARCHAR(255) REFERENCES threats(id) ON DELETE CASCADE,
            mitigation_type VARCHAR(100) NOT NULL,
            target_ips TEXT[] NOT NULL,
            config TEXT,
            parameters JSONB,
            applied_at TIMESTAMP NOT NULL,
            status VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_mitigations_threat ON mitigations(threat_id);
        CREATE INDEX IF NOT EXISTS idx_mitigations_type ON mitigations(mitigation_type);
        
        -- Attack patterns table (for pattern recognition)
        CREATE TABLE IF NOT EXISTS attack_patterns (
            id SERIAL PRIMARY KEY,
            pattern_name VARCHAR(255) NOT NULL,
            attack_type VARCHAR(100) NOT NULL,
            indicators JSONB NOT NULL,
            severity VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(pattern_name)
        );
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(schema)
                self.conn.commit()
            logger.info("✅ Database schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise
    
    def create_threat(self, threat_type: str, severity: str, source_ips: List[str],
                     target_ips: List[str], details: Dict) -> Threat:
        """Create new threat record"""
        threat_id = f"threat-{int(time.time() * 1000000)}"
        detected_at = datetime.utcnow()
        
        query = """
            INSERT INTO threats (id, threat_type, severity, status, source_ips, 
                               target_ips, detected_at, details)
            VALUES (%s, %s, %s, 'detected', %s, %s, %s, %s)
            RETURNING *
        """
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (
                    threat_id, threat_type, severity, source_ips, target_ips,
                    detected_at, json.dumps(details)
                ))
                self.conn.commit()
                row = cur.fetchone()
                
                return Threat(
                    id=row['id'],
                    threat_type=row['threat_type'],
                    severity=row['severity'],
                    status=row['status'],
                    source_ips=row['source_ips'],
                    target_ips=row['target_ips'],
                    detected_at=row['detected_at'],
                    details=row['details']
                )
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to create threat: {e}")
            raise
    
    def get_threat(self, threat_id: str) -> Optional[Threat]:
        """Get threat by ID"""
        query = "SELECT * FROM threats WHERE id = %s"
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (threat_id,))
                row = cur.fetchone()
                
                if not row:
                    return None
                
                return Threat(
                    id=row['id'],
                    threat_type=row['threat_type'],
                    severity=row['severity'],
                    status=row['status'],
                    source_ips=row['source_ips'],
                    target_ips=row['target_ips'],
                    detected_at=row['detected_at'],
                    mitigated_at=row['mitigated_at'],
                    resolved_at=row['resolved_at'],
                    details=row['details']
                )
        except Exception as e:
            logger.error(f"Failed to get threat: {e}")
            return None
    
    def list_threats(self, filters: Dict) -> List[Threat]:
        """List threats with filters"""
        query = "SELECT * FROM threats WHERE 1=1"
        params = []
        
        if filters.get('status'):
            query += " AND status = %s"
            params.append(filters['status'])
        
        if filters.get('severity'):
            query += " AND severity = %s"
            params.append(filters['severity'])
        
        if filters.get('attack_type'):
            query += " AND threat_type = %s"
            params.append(filters['attack_type'])
        
        query += " ORDER BY detected_at DESC"
        
        if filters.get('limit'):
            query += " LIMIT %s"
            params.append(int(filters['limit']))
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
                return [
                    Threat(
                        id=row['id'],
                        threat_type=row['threat_type'],
                        severity=row['severity'],
                        status=row['status'],
                        source_ips=row['source_ips'],
                        target_ips=row['target_ips'],
                        detected_at=row['detected_at'],
                        mitigated_at=row['mitigated_at'],
                        resolved_at=row['resolved_at'],
                        details=row['details']
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to list threats: {e}")
            return []
    
    def update_threat_status(self, threat_id: str, status: str):
        """Update threat status"""
        query = "UPDATE threats SET status = %s"
        params = [status]
        
        if status == 'mitigated':
            query += ", mitigated_at = %s"
            params.append(datetime.utcnow())
        elif status == 'resolved':
            query += ", resolved_at = %s"
            params.append(datetime.utcnow())
        
        query += " WHERE id = %s"
        params.append(threat_id)
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to update threat status: {e}")
    
    def resolve_threat(self, threat_id: str):
        """Mark threat as resolved"""
        self.update_threat_status(threat_id, 'resolved')
    
    def mark_threat_rolled_back(self, threat_id: str):
        """Mark threat as rolled back"""
        self.update_threat_status(threat_id, 'rolled_back')
    
    def create_attack(self, threat_id: str, attack_type: str, source_ip: str,
                     target_ip: str, packets: int, bytes_count: int, details: Dict) -> Attack:
        """Create attack event record"""
        query = """
            INSERT INTO attacks (threat_id, attack_type, source_ip, target_ip, 
                               packets, bytes, timestamp, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (
                    threat_id, attack_type, source_ip, target_ip,
                    packets, bytes_count, datetime.utcnow(), json.dumps(details)
                ))
                self.conn.commit()
                row = cur.fetchone()
                
                return Attack(
                    id=row['id'],
                    threat_id=row['threat_id'],
                    attack_type=row['attack_type'],
                    source_ip=row['source_ip'],
                    target_ip=row['target_ip'],
                    packets=row['packets'],
                    bytes_count=row['bytes'],
                    timestamp=row['timestamp'],
                    details=row['details']
                )
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to create attack: {e}")
            raise
    
    def get_attacks_by_threat(self, threat_id: str) -> List[Attack]:
        """Get all attacks for a threat"""
        query = "SELECT * FROM attacks WHERE threat_id = %s ORDER BY timestamp DESC"
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (threat_id,))
                rows = cur.fetchall()
                
                return [
                    Attack(
                        id=row['id'],
                        threat_id=row['threat_id'],
                        attack_type=row['attack_type'],
                        source_ip=row['source_ip'],
                        target_ip=row['target_ip'],
                        packets=row['packets'],
                        bytes_count=row['bytes'],
                        timestamp=row['timestamp'],
                        details=row['details']
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get attacks: {e}")
            return []
    
    def create_mitigation(self, threat_id: str, mitigation_type: str, target_ips: List[str],
                         config: str, parameters: Dict = None, status: str = 'active') -> Mitigation:
        """Create mitigation record"""
        query = """
            INSERT INTO mitigations (threat_id, mitigation_type, target_ips, config, 
                                   parameters, applied_at, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (
                    threat_id, mitigation_type, target_ips, config,
                    json.dumps(parameters) if parameters else None,
                    datetime.utcnow(), status
                ))
                self.conn.commit()
                row = cur.fetchone()
                
                return Mitigation(
                    id=row['id'],
                    threat_id=row['threat_id'],
                    mitigation_type=row['mitigation_type'],
                    target_ips=row['target_ips'],
                    config=row['config'],
                    parameters=row['parameters'],
                    applied_at=row['applied_at'],
                    status=row['status']
                )
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to create mitigation: {e}")
            raise
    
    def get_mitigations_by_threat(self, threat_id: str) -> List[Mitigation]:
        """Get all mitigations for a threat"""
        query = "SELECT * FROM mitigations WHERE threat_id = %s ORDER BY applied_at ASC"
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (threat_id,))
                rows = cur.fetchall()
                
                return [
                    Mitigation(
                        id=row['id'],
                        threat_id=row['threat_id'],
                        mitigation_type=row['mitigation_type'],
                        target_ips=row['target_ips'],
                        config=row['config'],
                        parameters=row['parameters'],
                        applied_at=row['applied_at'],
                        status=row['status']
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get mitigations: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get security statistics"""
        query = """
            SELECT 
                COUNT(*) as total_threats,
                COUNT(*) FILTER (WHERE status = 'detected') as active_threats,
                COUNT(*) FILTER (WHERE status = 'mitigated') as mitigated_threats,
                COUNT(*) FILTER (WHERE status = 'resolved') as resolved_threats,
                COUNT(*) FILTER (WHERE severity = 'critical') as critical_threats,
                COUNT(*) FILTER (WHERE severity = 'high') as high_threats,
                COUNT(*) FILTER (WHERE severity = 'medium') as medium_threats,
                COUNT(*) FILTER (WHERE detected_at > NOW() - INTERVAL '24 hours') as threats_24h
            FROM threats
        """
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                stats = cur.fetchone()
                return dict(stats)
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    def get_attack_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get attack statistics for time period"""
        query = """
            SELECT 
                attack_type,
                COUNT(*) as count,
                SUM(packets) as total_packets,
                SUM(bytes) as total_bytes
            FROM attacks
            WHERE timestamp > NOW() - make_interval(hours => %s)
            GROUP BY attack_type
            ORDER BY count DESC
        """
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (hours,))
                rows = cur.fetchall()
                
                return {
                    'period_hours': hours,
                    'attack_types': [dict(row) for row in rows]
                }
        except Exception as e:
            logger.error(f"Failed to get attack statistics: {e}")
            return {}
    
    def get_attack_patterns(self) -> List[Dict]:
        """Get known attack patterns"""
        query = "SELECT * FROM attack_patterns ORDER BY created_at DESC"
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get attack patterns: {e}")
            return []

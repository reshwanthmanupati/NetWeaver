"""
DDoS Detection Engine
Volumetric, Protocol, and Application Layer DDoS Detection
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import aio_pika

logger = logging.getLogger(__name__)


class DDoSDetector:
    """DDoS attack detector using flow analysis"""
    
    def __init__(self, storage, rabbitmq_config: Dict, thresholds: Dict):
        self.storage = storage
        self.rabbitmq_config = rabbitmq_config
        self.thresholds = thresholds
        self.is_running = False
        
        # Traffic metrics per source IP
        self.traffic_metrics = defaultdict(lambda: {
            'packets': 0,
            'bytes': 0,
            'syn_count': 0,
            'ack_count': 0,
            'udp_count': 0,
            'icmp_count': 0,
            'tcp_count': 0,
            'connections': set(),
            'protocols': defaultdict(int),
            'ports': defaultdict(int),
            'last_update': datetime.utcnow()
        })
        
        # Aggregated metrics for network-wide detection
        self.network_metrics = {
            'total_pps': 0,
            'total_bps': 0,
            'total_connections': 0,
            'window_start': datetime.utcnow()
        }
        
        self.connection = None
        self.channel = None
        self.consumer_task = None
        self.analysis_task = None
    
    async def start(self):
        """Start DDoS detector"""
        try:
            # Connect to RabbitMQ
            rabbitmq_url = f"amqp://{self.rabbitmq_config['user']}:{self.rabbitmq_config['password']}@{self.rabbitmq_config['host']}:{self.rabbitmq_config['port']}/"
            self.connection = await aio_pika.connect_robust(rabbitmq_url)
            self.channel = await self.connection.channel()
            
            # Declare queue for flow records
            queue = await self.channel.declare_queue('flow.records', durable=True)
            
            # Start consuming
            self.is_running = True
            self.consumer_task = asyncio.create_task(self._consume_flows(queue))
            self.analysis_task = asyncio.create_task(self._periodic_analysis())
            
            logger.info("DDoS Detector started, listening for flow records")
        except Exception as e:
            logger.error(f"Failed to start DDoS detector: {e}")
            raise
    
    async def stop(self):
        """Stop DDoS detector"""
        self.is_running = False
        
        if self.consumer_task:
            self.consumer_task.cancel()
        if self.analysis_task:
            self.analysis_task.cancel()
        
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        
        logger.info("DDoS Detector stopped")
    
    async def _consume_flows(self, queue):
        """Consume flow records from RabbitMQ"""
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        flow_data = json.loads(message.body.decode())
                        await self._process_flow(flow_data)
                    except Exception as e:
                        logger.error(f"Error processing flow: {e}")
    
    async def _process_flow(self, flow: Dict[str, Any]):
        """Process individual flow record"""
        source_ip = flow.get('source_ip')
        if not source_ip:
            return
        
        metrics = self.traffic_metrics[source_ip]
        
        # Update packet/byte counters
        packets = flow.get('packets', 1)
        bytes_count = flow.get('bytes', 0)
        
        metrics['packets'] += packets
        metrics['bytes'] += bytes_count
        
        # Update protocol-specific counters
        protocol = flow.get('protocol', '').lower()
        if protocol:
            metrics['protocols'][protocol] += packets
        
        # Track TCP flags for SYN flood detection
        tcp_flags = flow.get('tcp_flags', '')
        if 'SYN' in tcp_flags:
            metrics['syn_count'] += 1
        if 'ACK' in tcp_flags:
            metrics['ack_count'] += 1
        
        # Protocol-specific tracking
        if protocol == 'udp':
            metrics['udp_count'] += packets
        elif protocol == 'icmp':
            metrics['icmp_count'] += packets
        elif protocol == 'tcp':
            metrics['tcp_count'] += packets
        
        # Track destination ports
        dst_port = flow.get('destination_port')
        if dst_port:
            metrics['ports'][dst_port] += packets
        
        # Track unique connections
        connection_key = f"{source_ip}:{flow.get('source_port')}:{flow.get('destination_ip')}:{dst_port}"
        metrics['connections'].add(connection_key)
        
        metrics['last_update'] = datetime.utcnow()
        
        # Update network-wide metrics
        self.network_metrics['total_pps'] += packets
        self.network_metrics['total_bps'] += bytes_count * 8
    
    async def _periodic_analysis(self):
        """Periodically analyze traffic for DDoS attacks"""
        while self.is_running:
            try:
                await asyncio.sleep(10)  # Analyze every 10 seconds
                await self._analyze_traffic()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic analysis: {e}")
    
    async def _analyze_traffic(self):
        """Analyze traffic patterns for DDoS attacks"""
        current_time = datetime.utcnow()
        window_duration = (current_time - self.network_metrics['window_start']).total_seconds()
        
        if window_duration < 1:
            return
        
        # Calculate rates
        pps = self.network_metrics['total_pps'] / window_duration
        bps = self.network_metrics['total_bps'] / window_duration
        
        # Check for volumetric attacks
        if pps > self.thresholds['pps_threshold']:
            await self._detect_volumetric_attack('high_pps', pps, 'critical')
        
        if bps > self.thresholds['bps_threshold']:
            await self._detect_volumetric_attack('high_bandwidth', bps, 'critical')
        
        # Analyze per-source traffic
        for source_ip, metrics in list(self.traffic_metrics.items()):
            # Skip if no recent activity
            if (current_time - metrics['last_update']).total_seconds() > 60:
                del self.traffic_metrics[source_ip]
                continue
            
            # Check for SYN flood
            total_syn = metrics['syn_count']
            total_ack = metrics['ack_count']
            if total_syn > 0:
                syn_ratio = total_syn / (total_syn + total_ack + 1)
                if syn_ratio > self.thresholds['syn_ratio_threshold'] and total_syn > 100:
                    await self._detect_protocol_attack(
                        source_ip, 'syn_flood', 
                        {'syn_count': total_syn, 'syn_ratio': syn_ratio},
                        'high'
                    )
            
            # Check for UDP flood
            total_packets = metrics['packets']
            if total_packets > 0:
                udp_ratio = metrics['udp_count'] / total_packets
                if udp_ratio > self.thresholds['udp_ratio_threshold'] and metrics['udp_count'] > 1000:
                    await self._detect_protocol_attack(
                        source_ip, 'udp_flood',
                        {'udp_count': metrics['udp_count'], 'udp_ratio': udp_ratio},
                        'high'
                    )
            
            # Check for ICMP flood
            if total_packets > 0:
                icmp_ratio = metrics['icmp_count'] / total_packets
                if icmp_ratio > self.thresholds['icmp_ratio_threshold'] and metrics['icmp_count'] > 500:
                    await self._detect_protocol_attack(
                        source_ip, 'icmp_flood',
                        {'icmp_count': metrics['icmp_count'], 'icmp_ratio': icmp_ratio},
                        'medium'
                    )
            
            # Check for connection exhaustion
            if len(metrics['connections']) > self.thresholds['connections_threshold']:
                await self._detect_protocol_attack(
                    source_ip, 'connection_exhaustion',
                    {'connection_count': len(metrics['connections'])},
                    'high'
                )
            
            # Check for port scanning (many unique ports)
            if len(metrics['ports']) > 100:
                await self._detect_application_attack(
                    source_ip, 'port_scan',
                    {'unique_ports': len(metrics['ports']), 'ports': list(metrics['ports'].keys())[:20]},
                    'medium'
                )
        
        # Reset window
        self.network_metrics = {
            'total_pps': 0,
            'total_bps': 0,
            'total_connections': 0,
            'window_start': current_time
        }
    
    async def _detect_volumetric_attack(self, attack_type: str, value: float, severity: str):
        """Detect volumetric DDoS attack"""
        threat = self.storage.create_threat(
            threat_type='ddos_volumetric',
            severity=severity,
            source_ips=['multiple'],
            target_ips=[],
            details={
                'attack_type': attack_type,
                'value': value,
                'threshold': self.thresholds.get(f"{attack_type.split('_')[1]}_threshold")
            }
        )
        
        logger.warning(f"🚨 Volumetric DDoS detected: {attack_type} = {value:.0f}, Threat ID: {threat.id}")
    
    async def _detect_protocol_attack(self, source_ip: str, attack_type: str, details: Dict, severity: str):
        """Detect protocol-based DDoS attack"""
        threat = self.storage.create_threat(
            threat_type='ddos_protocol',
            severity=severity,
            source_ips=[source_ip],
            target_ips=[],
            details={
                'attack_type': attack_type,
                **details
            }
        )
        
        logger.warning(f"🚨 Protocol DDoS detected: {attack_type} from {source_ip}, Threat ID: {threat.id}")
    
    async def _detect_application_attack(self, source_ip: str, attack_type: str, details: Dict, severity: str):
        """Detect application-layer attack"""
        threat = self.storage.create_threat(
            threat_type='ddos_application',
            severity=severity,
            source_ips=[source_ip],
            target_ips=[],
            details={
                'attack_type': attack_type,
                **details
            }
        )
        
        logger.warning(f"🚨 Application attack detected: {attack_type} from {source_ip}, Threat ID: {threat.id}")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current traffic metrics"""
        return {
            'network': self.network_metrics.copy(),
            'top_sources': sorted(
                [(ip, m['packets']) for ip, m in self.traffic_metrics.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }

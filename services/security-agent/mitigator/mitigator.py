"""
Threat Mitigation Engine
Automatic DDoS mitigation strategies
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class ThreatMitigator:
    """Automatic threat mitigation"""
    
    def __init__(self, storage, device_manager_url: str):
        self.storage = storage
        self.device_manager_url = device_manager_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def mitigate(
        self,
        threat,
        mitigation_type: str,
        target_ips: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Apply mitigation strategy for threat
        
        Mitigation types:
        - blackhole: Null route malicious traffic
        - rate_limit: Rate limit traffic from source
        - acl: Apply ACL to block traffic
        - waf: Enable Web Application Firewall rules
        """
        logger.info(f"🛡️ Applying {mitigation_type} mitigation for threat {threat.id}")
        
        try:
            if mitigation_type == 'blackhole':
                await self._apply_blackhole(threat, target_ips or threat.source_ips)
            elif mitigation_type == 'rate_limit':
                await self._apply_rate_limit(threat, target_ips or threat.source_ips, parameters)
            elif mitigation_type == 'acl':
                await self._apply_acl(threat, target_ips or threat.source_ips, parameters)
            elif mitigation_type == 'waf':
                await self._apply_waf(threat, parameters)
            else:
                logger.error(f"Unknown mitigation type: {mitigation_type}")
                return
            
            # Update threat status
            self.storage.update_threat_status(threat.id, 'mitigated')
            logger.info(f"✅ Mitigation applied successfully for threat {threat.id}")
            
        except Exception as e:
            logger.error(f"Failed to apply mitigation: {e}")
            self.storage.update_threat_status(threat.id, 'mitigation_failed')
            raise
    
    async def _apply_blackhole(self, threat, target_ips: List[str]):
        """Blackhole routing - drop all traffic from source IPs"""
        for source_ip in target_ips:
            config = self._generate_blackhole_config(source_ip)
            
            # Deploy to edge routers
            devices = await self._get_edge_routers()
            for device in devices:
                await self._deploy_config(device['id'], config)
            
            # Record mitigation action
            self.storage.create_mitigation(
                threat_id=threat.id,
                mitigation_type='blackhole',
                target_ips=[source_ip],
                config=config,
                status='active'
            )
        
        logger.info(f"Blackhole routing applied for {len(target_ips)} IPs")
    
    async def _apply_rate_limit(self, threat, target_ips: List[str], parameters: Optional[Dict]):
        """Rate limiting - limit packets per second from source"""
        rate_limit = parameters.get('rate_pps', 1000) if parameters else 1000
        
        for source_ip in target_ips:
            config = self._generate_rate_limit_config(source_ip, rate_limit)
            
            # Deploy to edge routers
            devices = await self._get_edge_routers()
            for device in devices:
                await self._deploy_config(device['id'], config)
            
            # Record mitigation action
            self.storage.create_mitigation(
                threat_id=threat.id,
                mitigation_type='rate_limit',
                target_ips=[source_ip],
                config=config,
                parameters={'rate_pps': rate_limit},
                status='active'
            )
        
        logger.info(f"Rate limiting applied for {len(target_ips)} IPs at {rate_limit} pps")
    
    async def _apply_acl(self, threat, target_ips: List[str], parameters: Optional[Dict]):
        """ACL blocking - block specific traffic patterns"""
        protocol = parameters.get('protocol', 'ip') if parameters else 'ip'
        port = parameters.get('port') if parameters else None
        
        for source_ip in target_ips:
            config = self._generate_acl_config(source_ip, protocol, port)
            
            # Deploy to edge routers
            devices = await self._get_edge_routers()
            for device in devices:
                await self._deploy_config(device['id'], config)
            
            # Record mitigation action
            self.storage.create_mitigation(
                threat_id=threat.id,
                mitigation_type='acl',
                target_ips=[source_ip],
                config=config,
                parameters={'protocol': protocol, 'port': port},
                status='active'
            )
        
        logger.info(f"ACL blocking applied for {len(target_ips)} IPs")
    
    async def _apply_waf(self, threat, parameters: Optional[Dict]):
        """WAF rules - application layer protection"""
        rule_type = parameters.get('rule_type', 'sql_injection') if parameters else 'sql_injection'
        
        config = self._generate_waf_config(rule_type)
        
        # Deploy to application firewalls
        devices = await self._get_firewalls()
        for device in devices:
            await self._deploy_config(device['id'], config)
        
        # Record mitigation action
        self.storage.create_mitigation(
            threat_id=threat.id,
            mitigation_type='waf',
            target_ips=[],
            config=config,
            parameters={'rule_type': rule_type},
            status='active'
        )
        
        logger.info(f"WAF rules applied: {rule_type}")
    
    def _generate_blackhole_config(self, source_ip: str) -> str:
        """Generate blackhole route configuration"""
        # Cisco IOS format
        config = f"""!
! Blackhole route for {source_ip}
ip route {source_ip} 255.255.255.255 Null0
!
! Optional: Log dropped packets
access-list 199 deny ip host {source_ip} any log
!
"""
        return config
    
    def _generate_rate_limit_config(self, source_ip: str, rate_pps: int) -> str:
        """Generate rate limiting configuration"""
        # Cisco IOS rate-limiting
        config = f"""!
! Rate limit traffic from {source_ip} to {rate_pps} pps
ip access-list extended RATE_LIMIT_{source_ip.replace('.', '_')}
 permit ip host {source_ip} any
!
class-map match-all RATELIMIT-{source_ip.replace('.', '_')}
 match access-group name RATE_LIMIT_{source_ip.replace('.', '_')}
!
policy-map DDOS-RATELIMIT
 class RATELIMIT-{source_ip.replace('.', '_')}
  police {rate_pps} pps conform-action transmit exceed-action drop
!
interface GigabitEthernet0/0/0
 service-policy input DDOS-RATELIMIT
!
"""
        return config
    
    def _generate_acl_config(self, source_ip: str, protocol: str = 'ip', port: Optional[int] = None) -> str:
        """Generate ACL blocking configuration"""
        acl_name = f"BLOCK_{source_ip.replace('.', '_')}"
        
        if port and protocol in ['tcp', 'udp']:
            acl_line = f"deny {protocol} host {source_ip} any eq {port}"
        else:
            acl_line = f"deny {protocol} host {source_ip} any"
        
        config = f"""!
! Block traffic from {source_ip}
ip access-list extended {acl_name}
 {acl_line}
 permit ip any any
!
interface GigabitEthernet0/0/0
 ip access-group {acl_name} in
!
"""
        return config
    
    def _generate_waf_config(self, rule_type: str) -> str:
        """Generate WAF rule configuration"""
        # Generic WAF rule (actual format depends on WAF vendor)
        rules = {
            'sql_injection': """
! WAF Rule: Block SQL Injection
inspect http request pattern "(?i)(union.*select|select.*from|insert.*into|delete.*from|drop.*table)"
action block
log enabled
""",
            'xss': """
! WAF Rule: Block Cross-Site Scripting
inspect http request pattern "(?i)(<script|javascript:|onerror=|onload=)"
action block
log enabled
""",
            'command_injection': """
! WAF Rule: Block Command Injection
inspect http request pattern "(?i)(;.*whoami|&&.*ls|\\|.*cat|`.*id`)"
action block
log enabled
"""
        }
        
        return rules.get(rule_type, rules['sql_injection'])
    
    async def _get_edge_routers(self) -> List[Dict]:
        """Get list of edge routers from Device Manager"""
        try:
            response = await self.client.get(
                f"{self.device_manager_url}/api/v1/devices/search?role=edge_router"
            )
            response.raise_for_status()
            data = response.json()
            return data.get('devices', [])
        except Exception as e:
            logger.error(f"Failed to get edge routers: {e}")
            return []
    
    async def _get_firewalls(self) -> List[Dict]:
        """Get list of firewalls from Device Manager"""
        try:
            response = await self.client.get(
                f"{self.device_manager_url}/api/v1/devices/search?type=firewall"
            )
            response.raise_for_status()
            data = response.json()
            return data.get('devices', [])
        except Exception as e:
            logger.error(f"Failed to get firewalls: {e}")
            return []
    
    async def _deploy_config(self, device_id: str, config: str):
        """Deploy configuration to device via Device Manager"""
        try:
            response = await self.client.post(
                f"{self.device_manager_url}/api/v1/devices/{device_id}/config",
                json={
                    "configuration": config,
                    "method": "merge"
                }
            )
            response.raise_for_status()
            logger.info(f"✅ Configuration deployed to device {device_id}")
        except Exception as e:
            logger.error(f"Failed to deploy config to device {device_id}: {e}")
            raise
    
    async def rollback(self, threat_id: str, mitigations: List):
        """Rollback mitigation actions"""
        logger.info(f"🔄 Rolling back mitigations for threat {threat_id}")
        
        for mitigation in reversed(mitigations):
            try:
                rollback_config = self._generate_rollback_config(mitigation)
                
                if mitigation.mitigation_type in ['blackhole', 'rate_limit', 'acl']:
                    devices = await self._get_edge_routers()
                else:
                    devices = await self._get_firewalls()
                
                for device in devices:
                    await self._deploy_config(device['id'], rollback_config)
                
                logger.info(f"✅ Rolled back {mitigation.mitigation_type} mitigation")
            except Exception as e:
                logger.error(f"Failed to rollback mitigation: {e}")
        
        logger.info(f"Rollback completed for threat {threat_id}")
    
    def _generate_rollback_config(self, mitigation) -> str:
        """Generate configuration to remove mitigation"""
        if mitigation.mitigation_type == 'blackhole':
            source_ip = mitigation.target_ips[0] if mitigation.target_ips else '0.0.0.0'
            return f"no ip route {source_ip} 255.255.255.255 Null0\n"
        
        elif mitigation.mitigation_type == 'rate_limit':
            source_ip = mitigation.target_ips[0] if mitigation.target_ips else '0.0.0.0'
            acl_name = f"RATE_LIMIT_{source_ip.replace('.', '_')}"
            return f"no ip access-list extended {acl_name}\n"
        
        elif mitigation.mitigation_type == 'acl':
            source_ip = mitigation.target_ips[0] if mitigation.target_ips else '0.0.0.0'
            acl_name = f"BLOCK_{source_ip.replace('.', '_')}"
            return f"no ip access-list extended {acl_name}\n"
        
        return "! No rollback needed\n"

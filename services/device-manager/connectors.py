"""
Network Device Connectors
Vendor-specific adapters for device management
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ConnectionConfig:
    """Device connection configuration"""
    host: str
    port: int
    username: str
    password: str
    protocol: str  # ssh, netconf, eapi
    timeout: int = 30
    
@dataclass
class CommandResult:
    """Result of command execution"""
    command: str
    output: str
    success: bool
    error: Optional[str] = None

class DeviceConnector(ABC):
    """Abstract base class for device connectors"""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connected = False
        
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to device"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close connection to device"""
        pass
    
    @abstractmethod
    def get_config(self, config_type: str = "running") -> str:
        """Get device configuration"""
        pass
    
    @abstractmethod
    def push_config(self, configuration: str, commit: bool = True) -> bool:
        """Push configuration to device"""
        pass
    
    @abstractmethod
    def execute_commands(self, commands: List[str]) -> List[CommandResult]:
        """Execute CLI commands"""
        pass
    
    @abstractmethod
    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Get interface information"""
        pass
    
    @abstractmethod
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information (version, model, etc.)"""
        pass


class CiscoIOSConnector(DeviceConnector):
    """Cisco IOS/IOS-XE device connector"""
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.connection = None
        
    def connect(self) -> bool:
        """Connect to Cisco device via SSH or NETCONF"""
        try:
            if self.config.protocol == "ssh":
                return self._connect_ssh()
            elif self.config.protocol == "netconf":
                return self._connect_netconf()
            else:
                raise ValueError(f"Unsupported protocol: {self.config.protocol}")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def _connect_ssh(self) -> bool:
        """Connect via SSH using netmiko"""
        try:
            from netmiko import ConnectHandler
            
            device_params = {
                'device_type': 'cisco_ios',
                'host': self.config.host,
                'port': self.config.port,
                'username': self.config.username,
                'password': self.config.password,
                'timeout': self.config.timeout,
            }
            
            self.connection = ConnectHandler(**device_params)
            self.connected = True
            logger.info(f"Connected to {self.config.host} via SSH")
            return True
            
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            return False
    
    def _connect_netconf(self) -> bool:
        """Connect via NETCONF"""
        try:
            from ncclient import manager
            
            self.connection = manager.connect(
                host=self.config.host,
                port=self.config.port or 830,
                username=self.config.username,
                password=self.config.password,
                device_params={'name': 'iosxe'},
                hostkey_verify=False,
                timeout=self.config.timeout
            )
            
            self.connected = True
            logger.info(f"Connected to {self.config.host} via NETCONF")
            return True
            
        except Exception as e:
            logger.error(f"NETCONF connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from device"""
        if self.connection:
            try:
                if self.config.protocol == "ssh":
                    self.connection.disconnect()
                elif self.config.protocol == "netconf":
                    self.connection.close_session()
                
                self.connected = False
                logger.info(f"Disconnected from {self.config.host}")
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
    
    def get_config(self, config_type: str = "running") -> str:
        """Get device configuration"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            if self.config.protocol == "ssh":
                if config_type == "running":
                    return self.connection.send_command("show running-config")
                elif config_type == "startup":
                    return self.connection.send_command("show startup-config")
            
            elif self.config.protocol == "netconf":
                filter_xml = f"""
                <filter>
                    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"/>
                </filter>
                """
                result = self.connection.get_config(source=config_type, filter=filter_xml)
                return str(result)
                
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            raise
    
    def push_config(self, configuration: str, commit: bool = True) -> bool:
        """Push configuration to device"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            if self.config.protocol == "ssh":
                # Enter config mode
                self.connection.config_mode()
                
                # Send config commands
                output = self.connection.send_config_set(configuration.split('\n'))
                
                # Save if commit
                if commit:
                    self.connection.send_command("write memory")
                
                # Exit config mode
                self.connection.exit_config_mode()
                
                logger.info(f"Configuration pushed to {self.config.host}")
                return True
                
            elif self.config.protocol == "netconf":
                # TODO: Implement NETCONF edit-config
                pass
                
        except Exception as e:
            logger.error(f"Failed to push config: {e}")
            return False
    
    def execute_commands(self, commands: List[str]) -> List[CommandResult]:
        """Execute CLI commands"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        results = []
        
        for cmd in commands:
            try:
                output = self.connection.send_command(cmd)
                results.append(CommandResult(
                    command=cmd,
                    output=output,
                    success=True
                ))
            except Exception as e:
                results.append(CommandResult(
                    command=cmd,
                    output="",
                    success=False,
                    error=str(e)
                ))
        
        return results
    
    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Get interface information"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            output = self.connection.send_command("show ip interface brief")
            
            # Parse output (simplified)
            interfaces = []
            for line in output.split('\n')[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 6:
                        interfaces.append({
                            'name': parts[0],
                            'ip_address': parts[1] if parts[1] != 'unassigned' else None,
                            'status': parts[4],
                            'protocol': parts[5]
                        })
            
            return interfaces
            
        except Exception as e:
            logger.error(f"Failed to get interfaces: {e}")
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            version_output = self.connection.send_command("show version")
            
            # Parse version info (simplified)
            info = {
                'vendor': 'Cisco',
                'model': '',
                'version': '',
                'hostname': '',
                'uptime': '',
                'serial': ''
            }
            
            # Extract info from output
            for line in version_output.split('\n'):
                if 'Cisco IOS' in line or 'Cisco IOS-XE' in line:
                    info['version'] = line.strip()
                elif 'uptime is' in line:
                    info['uptime'] = line.split('uptime is')[1].strip()
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            raise


class JuniperJunOSConnector(DeviceConnector):
    """Juniper JunOS device connector"""
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.connection = None
        
    def connect(self) -> bool:
        """Connect to Juniper device"""
        try:
            from jnpr.junos import Device
            
            self.connection = Device(
                host=self.config.host,
                user=self.config.username,
                password=self.config.password,
                port=self.config.port or 22,
                timeout=self.config.timeout
            )
            
            self.connection.open()
            self.connected = True
            logger.info(f"Connected to Juniper device: {self.config.host}")
            return True
            
        except Exception as e:
            logger.error(f"Juniper connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Juniper device"""
        if self.connection:
            try:
                self.connection.close()
                self.connected = False
                logger.info(f"Disconnected from {self.config.host}")
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
    
    def get_config(self, config_type: str = "running") -> str:
        """Get Juniper configuration"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            from jnpr.junos import Configuration
            
            config = Configuration(self.connection)
            return config.get_config(config_type='candidate' if config_type == 'candidate' else 'committed')
            
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            raise
    
    def push_config(self, configuration: str, commit: bool = True) -> bool:
        """Push configuration to Juniper device"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            from jnpr.junos.utils.config import Config
            
            config = Config(self.connection)
            config.lock()
            
            # Load configuration
            config.load(configuration, format='set')
            
            # Commit if requested
            if commit:
                config.commit()
            
            config.unlock()
            
            logger.info(f"Configuration pushed to {self.config.host}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to push config: {e}")
            return False
    
    def execute_commands(self, commands: List[str]) -> List[CommandResult]:
        """Execute CLI commands on Juniper device"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        results = []
        
        for cmd in commands:
            try:
                output = self.connection.cli(cmd)
                results.append(CommandResult(
                    command=cmd,
                    output=output,
                    success=True
                ))
            except Exception as e:
                results.append(CommandResult(
                    command=cmd,
                    output="",
                    success=False,
                    error=str(e)
                ))
        
        return results
    
    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Get Juniper interface information"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            output = self.connection.cli("show interfaces terse")
            
            # Parse output (simplified)
            interfaces = []
            for line in output.split('\n'):
                if line.strip() and not line.startswith('Interface'):
                    parts = line.split()
                    if len(parts) >= 4:
                        interfaces.append({
                            'name': parts[0],
                            'status': parts[2],
                            'protocol': parts[3]
                        })
            
            return interfaces
            
        except Exception as e:
            logger.error(f"Failed to get interfaces: {e}")
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get Juniper system information"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            facts = self.connection.facts
            
            return {
                'vendor': 'Juniper',
                'model': facts.get('model', ''),
                'version': facts.get('version', ''),
                'hostname': facts.get('hostname', ''),
                'serial': facts.get('serialnumber', '')
            }
            
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            raise


class AristaEOSConnector(DeviceConnector):
    """Arista EOS device connector"""
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.connection = None
        
    def connect(self) -> bool:
        """Connect to Arista device via eAPI"""
        try:
            import pyeapi
            
            self.connection = pyeapi.connect(
                transport='https',
                host=self.config.host,
                port=self.config.port or 443,
                username=self.config.username,
                password=self.config.password,
                timeout=self.config.timeout
            )
            
            self.connected = True
            logger.info(f"Connected to Arista device: {self.config.host}")
            return True
            
        except Exception as e:
            logger.error(f"Arista connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Arista device"""
        self.connected = False
        logger.info(f"Disconnected from {self.config.host}")
    
    def get_config(self, config_type: str = "running") -> str:
        """Get Arista configuration"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            result = self.connection.execute(['show running-config'])
            return result['result'][0]['output']
            
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            raise
    
    def push_config(self, configuration: str, commit: bool = True) -> bool:
        """Push configuration to Arista device"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            commands = configuration.split('\n')
            result = self.connection.config(commands)
            
            if commit:
                self.connection.execute(['write memory'])
            
            logger.info(f"Configuration pushed to {self.config.host}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to push config: {e}")
            return False
    
    def execute_commands(self, commands: List[str]) -> List[CommandResult]:
        """Execute commands on Arista device"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        results = []
        
        try:
            response = self.connection.execute(commands)
            
            for i, cmd in enumerate(commands):
                results.append(CommandResult(
                    command=cmd,
                    output=str(response['result'][i]),
                    success=True
                ))
                
        except Exception as e:
            for cmd in commands:
                results.append(CommandResult(
                    command=cmd,
                    output="",
                    success=False,
                    error=str(e)
                ))
        
        return results
    
    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Get Arista interface information"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            result = self.connection.execute(['show interfaces status'])
            interfaces_data = result['result'][0]['interfaceStatuses']
            
            interfaces = []
            for name, info in interfaces_data.items():
                interfaces.append({
                    'name': name,
                    'status': info.get('linkStatus', 'unknown'),
                    'speed': info.get('bandwidth', ''),
                    'description': info.get('description', '')
                })
            
            return interfaces
            
        except Exception as e:
            logger.error(f"Failed to get interfaces: {e}")
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get Arista system information"""
        if not self.connected:
            raise ConnectionError("Not connected to device")
        
        try:
            result = self.connection.execute(['show version'])
            version_info = result['result'][0]
            
            return {
                'vendor': 'Arista',
                'model': version_info.get('modelName', ''),
                'version': version_info.get('version', ''),
                'hostname': version_info.get('hostname', ''),
                'serial': version_info.get('serialNumber', ''),
                'uptime': str(version_info.get('uptime', 0))
            }
            
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            raise


# Factory function to create appropriate connector
def create_connector(vendor: str, config: ConnectionConfig) -> DeviceConnector:
    """Factory function to create vendor-specific connector"""
    
    connectors = {
        'cisco_ios': CiscoIOSConnector,
        'cisco_iosxe': CiscoIOSConnector,
        'juniper_junos': JuniperJunOSConnector,
        'arista_eos': AristaEOSConnector,
    }
    
    connector_class = connectors.get(vendor.lower())
    if not connector_class:
        raise ValueError(f"Unsupported vendor: {vendor}")
    
    return connector_class(config)

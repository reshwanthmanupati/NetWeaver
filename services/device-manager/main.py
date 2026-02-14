"""
Device Manager Service
Multi-vendor network device abstraction and configuration management

Supports:
- Cisco IOS/IOS-XE (NETCONF, SSH)
- Juniper JunOS (NETCONF, SSH)
- Arista EOS (eAPI, SSH)
"""

import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import uvicorn
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Device Manager Service",
    description="Multi-vendor network device management",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enums
class VendorType(str, Enum):
    CISCO_IOS = "cisco_ios"
    CISCO_IOSXE = "cisco_iosxe"
    JUNIPER_JUNOS = "juniper_junos"
    ARISTA_EOS = "arista_eos"

class ConnectionProtocol(str, Enum):
    SSH = "ssh"
    NETCONF = "netconf"
    RESTCONF = "restconf"
    GNMI = "gnmi"
    EAPI = "eapi"

class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNREACHABLE = "unreachable"
    MAINTENANCE = "maintenance"

class ConfigStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"

# Request/Response Models
class Device(BaseModel):
    id: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Device hostname")
    vendor: VendorType
    model: str
    version: str
    ip_address: str
    port: int = 22
    protocol: ConnectionProtocol = ConnectionProtocol.SSH
    username: Optional[str] = None
    password: Optional[str] = None
    status: DeviceStatus = DeviceStatus.OFFLINE
    location: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class DeviceCreate(BaseModel):
    name: str
    vendor: VendorType
    model: str
    version: str
    ip_address: str
    port: int = 22
    protocol: ConnectionProtocol = ConnectionProtocol.SSH
    username: str
    password: str
    location: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

class ConfigDeployment(BaseModel):
    device_id: str
    configuration: str
    commit: bool = True
    backup: bool = True
    validate_before_deploy: bool = True
    rollback_on_error: bool = True

class ConfigDiff(BaseModel):
    device_id: str
    running_config: str
    candidate_config: str
    differences: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)

class DeviceHealth(BaseModel):
    device_id: str
    status: DeviceStatus
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    uptime_seconds: Optional[int] = None
    interface_count: Optional[int] = None
    interfaces_up: Optional[int] = None
    last_checked: datetime = Field(default_factory=datetime.now)

# In-memory storage (replace with database in production)
devices_db: Dict[str, Device] = {}
config_history: Dict[str, List[Dict[str, Any]]] = {}

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "device-manager",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/devices", response_model=Device, status_code=201)
async def create_device(device: DeviceCreate):
    """Register a new network device"""
    logger.info(f"Creating device: {device.name}")
    
    # Generate device ID
    device_id = f"device-{len(devices_db) + 1}"
    
    # Create device object
    new_device = Device(
        id=device_id,
        name=device.name,
        vendor=device.vendor,
        model=device.model,
        version=device.version,
        ip_address=device.ip_address,
        port=device.port,
        protocol=device.protocol,
        username=device.username,
        password="***",  # Mask password in response
        location=device.location,
        tags=device.tags,
        metadata=device.metadata
    )
    
    devices_db[device_id] = new_device
    
    logger.info(f"Device created: {device_id}")
    return new_device

@app.get("/api/v1/devices", response_model=List[Device])
async def list_devices(
    vendor: Optional[VendorType] = None,
    status: Optional[DeviceStatus] = None,
    tags: Optional[str] = None
):
    """List all registered devices with optional filtering"""
    devices = list(devices_db.values())
    
    # Apply filters
    if vendor:
        devices = [d for d in devices if d.vendor == vendor]
    if status:
        devices = [d for d in devices if d.status == status]
    if tags:
        tag_list = tags.split(",")
        devices = [d for d in devices if any(tag in d.tags for tag in tag_list)]
    
    return devices

@app.get("/api/v1/devices/{device_id}", response_model=Device)
async def get_device(device_id: str):
    """Get device details by ID"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    return devices_db[device_id]

@app.put("/api/v1/devices/{device_id}", response_model=Device)
async def update_device(device_id: str, device_update: DeviceCreate):
    """Update device configuration"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    device = devices_db[device_id]
    device.name = device_update.name
    device.vendor = device_update.vendor
    device.model = device_update.model
    device.version = device_update.version
    device.ip_address = device_update.ip_address
    device.port = device_update.port
    device.protocol = device_update.protocol
    device.location = device_update.location
    device.tags = device_update.tags
    device.metadata = device_update.metadata
    device.updated_at = datetime.now()
    
    logger.info(f"Device updated: {device_id}")
    return device

@app.delete("/api/v1/devices/{device_id}")
async def delete_device(device_id: str):
    """Delete a device"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    del devices_db[device_id]
    logger.info(f"Device deleted: {device_id}")
    
    return {"message": f"Device {device_id} deleted successfully"}

@app.get("/api/v1/devices/{device_id}/config")
async def get_device_config(device_id: str):
    """Get running configuration from device"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    device = devices_db[device_id]
    
    # TODO: Implement actual device connection and config retrieval
    # This would use netmiko, ncclient, or pyeapi depending on vendor
    
    logger.info(f"Fetching config for device: {device_id}")
    
    # Mock response
    return {
        "device_id": device_id,
        "device_name": device.name,
        "vendor": device.vendor,
        "configuration": "! Mock configuration\n! Device: " + device.name + "\n",
        "retrieved_at": datetime.now().isoformat()
    }

@app.post("/api/v1/devices/{device_id}/config")
async def deploy_config(device_id: str, deployment: ConfigDeployment, background_tasks: BackgroundTasks):
    """Deploy configuration to device"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    device = devices_db[device_id]
    
    logger.info(f"Deploying config to device: {device_id}")
    
    # Validate configuration before deployment
    if deployment.validate_before_deploy:
        logger.info(f"Validating configuration for {device_id}")
        # TODO: Implement syntax validation
    
    # Backup current config if requested
    if deployment.backup:
        logger.info(f"Backing up current config for {device_id}")
        # TODO: Implement backup
    
    # Schedule deployment in background
    background_tasks.add_task(deploy_config_task, device_id, deployment.configuration)
    
    # Store in config history
    if device_id not in config_history:
        config_history[device_id] = []
    
    config_history[device_id].append({
        "timestamp": datetime.now().isoformat(),
        "configuration": deployment.configuration,
        "status": ConfigStatus.PENDING
    })
    
    return {
        "device_id": device_id,
        "status": "pending",
        "message": f"Configuration deployment initiated for {device.name}"
    }

async def deploy_config_task(device_id: str, configuration: str):
    """Background task to deploy configuration"""
    logger.info(f"Executing config deployment for {device_id}")
    
    try:
        device = devices_db[device_id]
        
        # TODO: Implement actual device connection and config push
        # Based on vendor, use:
        # - Cisco: netmiko or ncclient
        # - Juniper: ncclient or junos-eznc
        # - Arista: pyeapi
        
        # Mock success
        logger.info(f"Config deployed successfully to {device_id}")
        
        # Update history
        if device_id in config_history and config_history[device_id]:
            config_history[device_id][-1]["status"] = ConfigStatus.SUCCESS
        
    except Exception as e:
        logger.error(f"Config deployment failed for {device_id}: {e}")
        
        # Update history
        if device_id in config_history and config_history[device_id]:
            config_history[device_id][-1]["status"] = ConfigStatus.FAILED
            config_history[device_id][-1]["error"] = str(e)

@app.post("/api/v1/devices/{device_id}/rollback")
async def rollback_config(device_id: str, steps: int = 1):
    """Rollback device configuration"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    if device_id not in config_history or len(config_history[device_id]) < steps + 1:
        raise HTTPException(status_code=400, detail="Not enough config history for rollback")
    
    logger.info(f"Rolling back config for {device_id} by {steps} steps")
    
    # Get previous config
    previous_config = config_history[device_id][-(steps + 1)]
    
    # TODO: Implement actual rollback
    
    return {
        "device_id": device_id,
        "status": "rollback_initiated",
        "steps": steps,
        "message": f"Rolling back to config from {previous_config['timestamp']}"
    }

@app.get("/api/v1/devices/{device_id}/health", response_model=DeviceHealth)
async def check_device_health(device_id: str):
    """Check device health status"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    device = devices_db[device_id]
    
    logger.info(f"Checking health for device: {device_id}")
    
    # TODO: Implement actual health check
    # - SSH/NETCONF connectivity test
    # - Query device status (CPU, memory, uptime)
    # - Check interface status
    
    # Mock response
    health = DeviceHealth(
        device_id=device_id,
        status=DeviceStatus.ONLINE,
        cpu_percent=45.2,
        memory_percent=62.8,
        uptime_seconds=1234567,
        interface_count=24,
        interfaces_up=22
    )
    
    return health

@app.post("/api/v1/devices/{device_id}/commands")
async def execute_commands(device_id: str, commands: List[str]):
    """Execute CLI commands on device"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    device = devices_db[device_id]
    
    logger.info(f"Executing {len(commands)} commands on {device_id}")
    
    # TODO: Implement command execution via SSH/NETCONF
    
    # Mock response
    results = []
    for cmd in commands:
        results.append({
            "command": cmd,
            "output": f"Mock output for: {cmd}",
            "success": True
        })
    
    return {
        "device_id": device_id,
        "commands": commands,
        "results": results,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/devices/{device_id}/interfaces")
async def get_interfaces(device_id: str):
    """Get interface status for device"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    logger.info(f"Fetching interfaces for device: {device_id}")
    
    # TODO: Query actual interface data
    
    # Mock response
    interfaces = [
        {
            "name": "GigabitEthernet0/0/0",
            "status": "up",
            "speed": "1000Mbps",
            "mtu": 1500,
            "ip_address": "192.168.1.1",
            "packets_in": 1234567890,
            "packets_out": 987654321
        },
        {
            "name": "GigabitEthernet0/0/1",
            "status": "down",
            "speed": "1000Mbps",
            "mtu": 1500,
            "ip_address": None,
            "packets_in": 0,
            "packets_out": 0
        }
    ]
    
    return {
        "device_id": device_id,
        "interfaces": interfaces,
        "total_count": len(interfaces),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/vendors")
async def list_vendors():
    """List supported vendors and their capabilities"""
    return {
        "vendors": [
            {
                "name": "Cisco IOS/IOS-XE",
                "vendor_code": "cisco_ios",
                "protocols": ["ssh", "netconf", "restconf"],
                "features": ["qos", "routing", "acl", "vlan", "ospf", "bgp"]
            },
            {
                "name": "Juniper JunOS",
                "vendor_code": "juniper_junos",
                "protocols": ["ssh", "netconf"],
                "features": ["class-of-service", "routing", "firewall", "mpls", "bgp"]
            },
            {
                "name": "Arista EOS",
                "vendor_code": "arista_eos",
                "protocols": ["ssh", "eapi"],
                "features": ["traffic-policy", "routing", "acl", "vxlan", "bgp"]
            }
        ]
    }

# Run server
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8083,
        reload=True,
        log_level="info"
    )

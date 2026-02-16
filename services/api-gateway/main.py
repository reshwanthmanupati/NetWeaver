"""
API Gateway - Unified Entry Point for NetWeaver
Handles authentication, rate limiting, and request routing
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import jwt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import httpx
import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "netweaver_secret_key_change_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Service URLs (defaults to localhost for local dev; Docker Compose sets env vars)
INTENT_ENGINE_URL = os.getenv("INTENT_ENGINE_URL", "http://localhost:8081")
DEVICE_MANAGER_URL = os.getenv("DEVICE_MANAGER_URL", "http://localhost:8083")
SELF_HEALING_URL = os.getenv("SELF_HEALING_URL", "http://localhost:8082")
SECURITY_AGENT_URL = os.getenv("SECURITY_AGENT_URL", "http://localhost:8084")

# Redis for rate limiting
redis_client = None
http_client = None

# WebSocket connections
websocket_connections: Dict[str, WebSocket] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    global redis_client, http_client
    
    logger.info("🚀 Starting API Gateway...")
    
    # Initialize Redis
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    
    try:
        redis_client = await redis.from_url(
            f"redis://{redis_host}:{redis_port}",
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("✅ Redis connected for rate limiting")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        logger.warning("Rate limiting will be disabled")
    
    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("✅ HTTP client initialized")
    
    logger.info("🌐 API Gateway ready on port 8080")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down API Gateway...")
    if redis_client:
        await redis_client.close()
    if http_client:
        await http_client.aclose()
    logger.info("✅ API Gateway stopped")


# Create FastAPI app
app = FastAPI(
    title="NetWeaver API Gateway",
    description="Unified API Gateway for NetWeaver Microservices",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()


# Models
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class User(BaseModel):
    username: str
    email: Optional[str] = None
    roles: List[str] = Field(default_factory=list)


# Authentication
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(token_data: dict = Depends(verify_token)) -> User:
    """Get current authenticated user"""
    username = token_data.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid authentication")
    
    return User(
        username=username,
        email=token_data.get("email"),
        roles=token_data.get("roles", ["user"])
    )


# Rate Limiting
async def check_rate_limit(request: Request, limit: int = 100, window: int = 60) -> bool:
    """
    Check rate limit for client IP
    Returns True if within limit, False if exceeded
    """
    if not redis_client:
        return True  # Skip if Redis unavailable
    
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"
    
    try:
        current = await redis_client.get(key)
        
        if current is None:
            await redis_client.setex(key, window, 1)
            return True
        
        current_count = int(current)
        if current_count >= limit:
            return False
        
        await redis_client.incr(key)
        return True
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return True  # Allow on error


async def require_rate_limit(request: Request):
    """Dependency to enforce rate limiting"""
    if not await check_rate_limit(request, limit=100, window=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")


# Request Forwarding
async def forward_request(
    service_url: str,
    path: str,
    method: str = "GET",
    headers: Optional[Dict] = None,
    json_data: Optional[Dict] = None,
    query_params: Optional[Dict] = None
) -> Dict[str, Any]:
    """Forward request to backend service"""
    url = f"{service_url}{path}"
    
    try:
        request_args = {
            "method": method,
            "url": url,
            "headers": headers or {},
            "params": query_params
        }
        
        if json_data is not None:
            request_args["json"] = json_data
        
        response = await http_client.request(**request_args)
        response.raise_for_status()
        
        try:
            return response.json()
        except Exception:
            return {"raw_response": response.text}
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error forwarding to {url}: {e}")
        # Try to forward the backend's error body for better diagnostics
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text or str(e)
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except httpx.RequestError as e:
        logger.error(f"Request error forwarding to {url}: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"Error forwarding request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health Check
@app.get("/health")
async def health_check():
    """API Gateway health check"""
    services_status = {}
    
    # Check all backend services
    for service_name, service_url in [
        ("intent_engine", INTENT_ENGINE_URL),
        ("device_manager", DEVICE_MANAGER_URL),
        ("self_healing", SELF_HEALING_URL),
        ("security_agent", SECURITY_AGENT_URL)
    ]:
        try:
            response = await http_client.get(f"{service_url}/health", timeout=5.0)
            services_status[service_name] = "healthy" if response.status_code == 200 else "unhealthy"
        except Exception as e:
            services_status[service_name] = "unavailable"
            logger.warning(f"{service_name} health check failed: {e}")
    
    return {
        "status": "healthy",
        "service": "api-gateway",
        "timestamp": datetime.utcnow().isoformat(),
        "services": services_status,
        "redis": "connected" if redis_client else "disconnected"
    }


# Authentication Endpoints
@app.post("/api/v1/auth/login", response_model=Token)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT token
    
    In production, validate against user database
    """
    # Demo: Accept any username/password for testing
    # In production: Validate against database with bcrypt
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    # Create token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": request.username,
            "email": f"{request.username}@netweaver.local",
            "roles": ["admin", "user"]
        },
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@app.get("/api/v1/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@app.post("/api/v1/auth/refresh", response_model=Token)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh access token"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": current_user.username,
            "email": current_user.email,
            "roles": current_user.roles
        },
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# Intent Engine Routes
@app.get("/api/v1/intents")
async def get_intents(
    request: Request,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(require_rate_limit)
):
    """Get all intents from Intent Engine"""
    return await forward_request(
        INTENT_ENGINE_URL,
        "/api/v1/intents",
        query_params=dict(request.query_params)
    )


@app.post("/api/v1/intents")
async def create_intent(
    request: Request,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(require_rate_limit)
):
    """Create new intent"""
    body = await request.json()
    return await forward_request(
        INTENT_ENGINE_URL,
        "/api/v1/intents",
        method="POST",
        json_data=body
    )


@app.get("/api/v1/intents/{intent_id}")
async def get_intent(
    intent_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get intent by ID"""
    return await forward_request(
        INTENT_ENGINE_URL,
        f"/api/v1/intents/{intent_id}"
    )


@app.delete("/api/v1/intents/{intent_id}")
async def delete_intent(
    intent_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete intent"""
    return await forward_request(
        INTENT_ENGINE_URL,
        f"/api/v1/intents/{intent_id}",
        method="DELETE"
    )


@app.post("/api/v1/intents/{intent_id}/deploy")
async def deploy_intent(
    intent_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Deploy intent"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    return await forward_request(
        INTENT_ENGINE_URL,
        f"/api/v1/intents/{intent_id}/deploy",
        method="POST",
        json_data=body
    )


# Device Manager Routes
@app.get("/api/v1/devices")
async def get_devices(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get all devices"""
    return await forward_request(
        DEVICE_MANAGER_URL,
        "/api/v1/devices",
        query_params=dict(request.query_params)
    )


@app.post("/api/v1/devices")
async def register_device(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Register new device"""
    body = await request.json()
    return await forward_request(
        DEVICE_MANAGER_URL,
        "/api/v1/devices",
        method="POST",
        json_data=body
    )


@app.get("/api/v1/devices/{device_id}")
async def get_device(
    device_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get device by ID"""
    return await forward_request(
        DEVICE_MANAGER_URL,
        f"/api/v1/devices/{device_id}"
    )


@app.post("/api/v1/devices/{device_id}/config")
async def deploy_device_config(
    device_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Deploy configuration to device"""
    body = await request.json()
    return await forward_request(
        DEVICE_MANAGER_URL,
        f"/api/v1/devices/{device_id}/config",
        method="POST",
        json_data=body
    )


# Self-Healing Routes
@app.get("/api/v1/incidents")
async def get_incidents(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get incidents from Self-Healing System"""
    return await forward_request(
        SELF_HEALING_URL,
        "/api/v1/incidents",
        query_params=dict(request.query_params)
    )


@app.get("/api/v1/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get incident by ID"""
    return await forward_request(
        SELF_HEALING_URL,
        f"/api/v1/incidents/{incident_id}"
    )


@app.post("/api/v1/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Resolve incident"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    return await forward_request(
        SELF_HEALING_URL,
        f"/api/v1/incidents/{incident_id}/resolve",
        method="POST",
        json_data=body
    )


@app.get("/api/v1/incidents/stats/mttr")
async def get_mttr(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get MTTR statistics"""
    return await forward_request(
        SELF_HEALING_URL,
        "/api/v1/stats/mttr",
        query_params=dict(request.query_params)
    )


# Security Agent Routes
@app.get("/api/v1/threats")
async def get_threats(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get security threats"""
    return await forward_request(
        SECURITY_AGENT_URL,
        "/api/v1/threats",
        query_params=dict(request.query_params)
    )


@app.get("/api/v1/threats/{threat_id}")
async def get_threat(
    threat_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get threat by ID"""
    return await forward_request(
        SECURITY_AGENT_URL,
        f"/api/v1/threats/{threat_id}"
    )


@app.post("/api/v1/mitigate")
async def mitigate_threat(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Trigger threat mitigation"""
    body = await request.json()
    return await forward_request(
        SECURITY_AGENT_URL,
        "/api/v1/mitigate",
        method="POST",
        json_data=body
    )


@app.get("/api/v1/security/stats")
async def get_security_stats(
    current_user: User = Depends(get_current_user)
):
    """Get security statistics"""
    return await forward_request(
        SECURITY_AGENT_URL,
        "/api/v1/stats"
    )


# Dashboard/Statistics Routes
@app.get("/api/v1/dashboard")
async def get_dashboard(current_user: User = Depends(get_current_user)):
    """Get aggregated dashboard data from all services"""
    dashboard_data = {}
    
    # Gather data from all services in parallel using asyncio.gather
    async def fetch_intents():
        try:
            stats = await forward_request(INTENT_ENGINE_URL, "/api/v1/intents")
            return {"total": stats.get("count", 0), "intents": stats.get("intents", [])[:5]}
        except Exception as e:
            logger.error(f"Failed to get intent stats: {e}")
            return {"error": str(e)}

    async def fetch_devices():
        try:
            stats = await forward_request(DEVICE_MANAGER_URL, "/api/v1/devices")
            devices = stats if isinstance(stats, list) else stats.get("devices", [])
            return {"total": len(devices), "online": sum(1 for d in devices if d.get("status") == "online")}
        except Exception as e:
            logger.error(f"Failed to get device stats: {e}")
            return {"error": str(e)}

    async def fetch_incidents():
        try:
            return await forward_request(SELF_HEALING_URL, "/api/v1/stats")
        except Exception as e:
            logger.error(f"Failed to get incident stats: {e}")
            return {"error": str(e)}

    async def fetch_threats():
        try:
            return await forward_request(SECURITY_AGENT_URL, "/api/v1/stats")
        except Exception as e:
            logger.error(f"Failed to get threat stats: {e}")
            return {"error": str(e)}

    results = await asyncio.gather(
        fetch_intents(), fetch_devices(), fetch_incidents(), fetch_threats()
    )
    dashboard_data["intents"] = results[0]
    dashboard_data["devices"] = results[1]
    dashboard_data["incidents"] = results[2]
    dashboard_data["threats"] = results[3]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "data": dashboard_data
    }


# WebSocket for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    
    # Generate client ID
    client_id = f"client-{int(time.time() * 1000000)}"
    websocket_connections[client_id] = websocket
    
    logger.info(f"WebSocket client {client_id} connected")
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            
            # Echo back for now (can be extended for pub/sub)
            await websocket.send_json({
                "type": "echo",
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            })
    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected")
        del websocket_connections[client_id]
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if client_id in websocket_connections:
            del websocket_connections[client_id]


async def broadcast_event(event_type: str, data: Dict):
    """Broadcast event to all connected WebSocket clients"""
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    for client_id, websocket in list(websocket_connections.items()):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send to {client_id}: {e}")
            del websocket_connections[client_id]


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )

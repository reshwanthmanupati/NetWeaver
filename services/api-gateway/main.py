"""
API Gateway - Unified Entry Point for NetWeaver
Handles authentication, rate limiting, and request routing
"""

import asyncio
import logging
import os
import time
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import jwt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration with validation
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    logger.warning("⚠️  JWT_SECRET_KEY not set in environment. Using generated key (NOT FOR PRODUCTION!)")
    SECRET_KEY = secrets.token_urlsafe(32)
elif SECRET_KEY == "netweaver_secret_key_change_in_production":
    logger.error("🚨 SECURITY WARNING: Default JWT secret key detected! Set JWT_SECRET_KEY environment variable!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
CSRF_PROTECTION_ENABLED = os.getenv("CSRF_PROTECTION", "true").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # development, staging, production

# Service URLs (defaults to localhost for local dev; Docker Compose sets env vars)
INTENT_ENGINE_URL = os.getenv("INTENT_ENGINE_URL", "http://localhost:8081")
DEVICE_MANAGER_URL = os.getenv("DEVICE_MANAGER_URL", "http://localhost:8083")
SELF_HEALING_URL = os.getenv("SELF_HEALING_URL", "http://localhost:8082")
SECURITY_AGENT_URL = os.getenv("SECURITY_AGENT_URL", "http://localhost:8084")

# CORS Configuration - restrict origins in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
if ENVIRONMENT == "production" and "*" in ALLOWED_ORIGINS:
    logger.error("🚨 SECURITY WARNING: Wildcard CORS origin (*) detected in production!")

# Redis for rate limiting
redis_client = None
http_client = None

# WebSocket connections
websocket_connections: Dict[str, WebSocket] = {}


# ─── Security Middleware ───────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Strict-Transport-Security (HSTS) for production HTTPS
        if ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Adjust based on your needs
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' http://localhost:* ws://localhost:* wss://localhost:*"
        )
        
        # Remove server header to not leak implementation details
        if "server" in response.headers:
            del response.headers["server"]
        
        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF Protection for state-changing operations"""
    async def dispatch(self, request: Request, call_next):
        if not CSRF_PROTECTION_ENABLED:
            return await call_next(request)
        
        # Skip CSRF for safe methods and specific paths
        if request.method in ["GET", "HEAD", "OPTIONS"] or request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            response = await call_next(request)
            # Set CSRF token cookie for subsequent requests
            if request.method == "GET" and "/api/" in request.url.path:
                csrf_token = secrets.token_urlsafe(32)
                response.set_cookie(
                    key="csrf_token",
                    value=csrf_token,
                    httponly=True,
                    secure=ENVIRONMENT == "production",
                    samesite="strict"
                )
            return response
        
        # Verify CSRF token for state-changing requests
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")
        
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid"}
            )
        
        return await call_next(request)


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

# Add security middlewares (order matters!)
app.add_middleware(SecurityHeadersMiddleware)
if CSRF_PROTECTION_ENABLED:
    app.add_middleware(CSRFProtectionMiddleware)

# CORS middleware - restrictive by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-CSRF-Token"],  # Expose CSRF token header
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Security
security = HTTPBearer()


# Models with validation
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, regex=r'^[a-zA-Z0-9_-]+$')
    password: str = Field(..., min_length=8, max_length=128)
    
    @validator('username')
    def validate_username(cls, v):
        """Sanitize username to prevent injection attacks"""
        if not v or not v.strip():
            raise ValueError('Username cannot be empty')
        return v.strip()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class User(BaseModel):
    username: str
    email: Optional[str] = None
    roles: List[str] = Field(default_factory=list)


# ─── Custom Exception Handler ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors without leaking sensitive information"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}", exc_info=True)
    
    # Don't expose internal errors in production
    if ENVIRONMENT == "production":
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred"}
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An error occurred",
                "error_type": type(exc).__name__,
                "error_message": str(exc)
            }
        )


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
        logger.warning(f"Rate limit exceeded for IP: {request.client.host}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": "60"}
        )


# Request Forwarding
async def forward_request(
    service_url: str,
    path: str,
    method: str = "GET",
    headers: Optional[Dict] = None,
    json_data: Optional[Dict] = None,
    query_params: Optional[Dict] = None,
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Forward request to backend service with security considerations
    - Timeout protection
    - Error sanitization
    - Request validation
    """
    url = f"{service_url}{path}"
    
    # Validate that we're not being redirected externally
    if not service_url.startswith(("http://intent-engine", "http://device-manager", 
                                    "http://self-healing", "http://security-agent",
                                    "http://localhost")):
        logger.error(f"Attempted request to unauthorized service: {service_url}")
        raise HTTPException(status_code=403, detail="Unauthorized service URL")
    
    try:
        request_args = {
            "method": method,
            "url": url,
            "headers": headers or {},
            "params": query_params,
            "timeout": timeout
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
        logger.error(f"HTTP error forwarding to {service_url}: {e.response.status_code}")
        # Forward backend errors but sanitize sensitive details
        try:
            detail = e.response.json()
            # Remove any keys that might leak internal info
            if isinstance(detail, dict):
                detail.pop("traceback", None)
                detail.pop("stack_trace", None)
        except Exception:
            detail = {"message": "Backend service error"}
        raise HTTPException(status_code=e.response.status_code, detail=detail)
        
    except httpx.TimeoutException:
        logger.error(f"Timeout forwarding to {service_url}")
        raise HTTPException(
            status_code=504,
            detail="Gateway timeout - backend service did not respond in time"
        )
        
    except httpx.RequestError as e:
        logger.error(f"Request error forwarding to {service_url}: {type(e).__name__}")
        raise HTTPException(
            status_code=503,
            detail="Backend service temporarily unavailable"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error forwarding request: {type(e).__name__}", exc_info=True)
        if ENVIRONMENT == "production":
            raise HTTPException(status_code=500, detail="Internal gateway error")
        else:
            raise HTTPException(status_code=500, detail=f"Gateway error: {str(e)}")


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
async def login(request: LoginRequest, req: Request):
    """
    Authenticate user and return JWT token
    
    Security considerations:
    - Rate limited to prevent brute force
    - Username/password validation
    - Secure token generation
    
    TODO: In production, validate against user database with bcrypt password hashing
    """
    # Additional rate limiting for login endpoint (stricter)
    if not await check_rate_limit(req, limit=5, window=300):  # 5 attempts per 5 minutes
        logger.warning(f"Login rate limit exceeded for IP: {req.client.host}, username: {request.username}")
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again in 5 minutes.",
            headers={"Retry-After": "300"}
        )
    
    # Demo mode: Accept any username/password for testing
    # In production, this should:
    # 1. Query user database
    # 2. Verify password with bcrypt.checkpw()
    # 3. Check if account is active/not locked
    # 4. Log authentication attempt
    
    if not request.username or not request.password:
        logger.warning(f"Login attempt with empty credentials from IP: {req.client.host}")
        raise HTTPException(status_code=400, detail="Username and password required")
    
    # Simulate successful authentication
    logger.info(f"User {request.username} authenticated from {req.client.host}")
    
    # Create token with limited lifetime
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": request.username,
            "email": f"{request.username}@netweaver.local",
            "roles": ["admin", "user"],
            "iat": datetime.utcnow(),  # Issued at
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

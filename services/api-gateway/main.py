"""
API Gateway - Unified Entry Point for NetWeaver
Handles authentication, rate limiting, request routing, user management, and security monitoring
"""

import asyncio
import logging
import os
import time
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

import jwt
import bcrypt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator, EmailStr
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import redis.asyncio as redis
import psycopg2
import psycopg2.pool
import psycopg2.extras

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

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "netweaver")
DB_USER = os.getenv("DB_USER", "netweaver")
DB_PASSWORD = os.getenv("DB_PASSWORD", "netweaver_secure_pass_2026")

# Account lockout configuration
MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.getenv("LOCKOUT_DURATION_MINUTES", "30"))

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
db_pool = None

# WebSocket connections
websocket_connections: Dict[str, WebSocket] = {}


# ─── Database Connection Pool ──────────────────────────────────────────────

def init_db_pool():
    """Initialize PostgreSQL connection pool for user management"""
    global db_pool
    try:
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        logger.info("✅ PostgreSQL connection pool initialized")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize database pool: {e}")
        return False


def get_db_connection():
    """Get a connection from the pool"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    return db_pool.getconn()


def release_db_connection(conn):
    """Return a connection to the pool"""
    if db_pool and conn:
        db_pool.putconn(conn)


# ─── Security Audit Logging ───────────────────────────────────────────────

class AuditEventType(str, Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TOKEN_REFRESH = "token_refresh"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


async def log_security_event(
    event_type: AuditEventType,
    severity: str = "info",
    username: Optional[str] = None,
    source_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict] = None
):
    """Log security events to database and broadcast alerts"""
    # Log to application logger
    log_msg = f"SECURITY_EVENT: {event_type.value} | user={username} | ip={source_ip} | {details or {}}"
    if severity == "critical":
        logger.critical(log_msg)
    elif severity == "warning":
        logger.warning(log_msg)
    else:
        logger.info(log_msg)
    
    # Persist to database
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO security_audit_log 
                       (event_type, severity, username, source_ip, user_agent, details) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        event_type.value,
                        severity,
                        username,
                        source_ip,
                        user_agent,
                        psycopg2.extras.Json(details or {})
                    )
                )
                conn.commit()
        finally:
            release_db_connection(conn)
    except Exception as e:
        logger.error(f"Failed to persist security event: {e}")
    
    # Broadcast critical events via WebSocket to connected admin dashboards
    if severity in ("critical", "warning"):
        await broadcast_event("security_alert", {
            "event_type": event_type.value,
            "severity": severity,
            "username": username,
            "source_ip": source_ip,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        })
    
    # Push to Redis pub/sub for external alert integrations (Slack, PagerDuty, email)
    if redis_client and severity == "critical":
        try:
            await redis_client.publish("netweaver:security_alerts", str({
                "event_type": event_type.value,
                "severity": severity,
                "username": username,
                "source_ip": source_ip,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }))
        except Exception as e:
            logger.error(f"Failed to publish security alert to Redis: {e}")


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
        
        # Login is intentionally exempt so first-time authentication can succeed
        if request.url.path == "/api/v1/auth/login":
            return await call_next(request)

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
    
    # Initialize PostgreSQL connection pool
    if init_db_pool():
        logger.info("✅ Database pool ready for user management")
    else:
        logger.warning("⚠️  Database unavailable - falling back to demo auth mode")
    
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
    if db_pool:
        db_pool.closeall()
        logger.info("✅ Database pool closed")
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
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
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
    full_name: Optional[str] = None
    is_active: bool = True


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, max_length=100)
    roles: List[str] = Field(default=["user"])
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Enforce strong password policy"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('roles')
    def validate_roles(cls, v):
        allowed_roles = {"admin", "user", "viewer", "operator"}
        for role in v:
            if role not in allowed_roles:
                raise ValueError(f"Invalid role: {role}. Allowed: {allowed_roles}")
        return v


class UpdateUserRequest(BaseModel):
    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, max_length=100)
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None
    
    @validator('roles')
    def validate_roles(cls, v):
        if v is not None:
            allowed_roles = {"admin", "user", "viewer", "operator"}
            for role in v:
                if role not in allowed_roles:
                    raise ValueError(f"Invalid role: {role}. Allowed: {allowed_roles}")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    roles: List[str]
    is_active: bool
    is_locked: bool
    last_login: Optional[str] = None
    created_at: str


class AuditLogEntry(BaseModel):
    log_id: str
    event_time: str
    event_type: str
    severity: str
    username: Optional[str] = None
    source_ip: Optional[str] = None
    details: Dict = {}
    resolved: bool = False


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


# ─── User Database Helpers ─────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password using bcrypt with cost factor 12"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def get_user_by_username(username: str) -> Optional[Dict]:
    """Fetch user from database by username"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT user_id, username, email, password_hash, full_name, 
                          roles, is_active, is_locked, failed_login_attempts, 
                          locked_until, last_login, created_at
                   FROM users WHERE username = %s""",
                (username,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        release_db_connection(conn)


def update_login_success(username: str):
    """Record successful login"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users 
                   SET last_login = NOW(), failed_login_attempts = 0, 
                       is_locked = false, locked_until = NULL, updated_at = NOW()
                   WHERE username = %s""",
                (username,)
            )
            conn.commit()
    finally:
        release_db_connection(conn)


def update_login_failure(username: str) -> int:
    """Record failed login attempt, returns new attempt count"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users 
                   SET failed_login_attempts = failed_login_attempts + 1, updated_at = NOW()
                   WHERE username = %s
                   RETURNING failed_login_attempts""",
                (username,)
            )
            result = cur.fetchone()
            attempts = result[0] if result else 0
            
            # Lock account if max attempts exceeded
            if attempts >= MAX_FAILED_ATTEMPTS:
                cur.execute(
                    """UPDATE users 
                       SET is_locked = true, 
                           locked_until = NOW() + INTERVAL '%s minutes',
                           updated_at = NOW()
                       WHERE username = %s""",
                    (LOCKOUT_DURATION_MINUTES, username)
                )
            conn.commit()
            return attempts
    finally:
        release_db_connection(conn)


# Authentication Endpoints
@app.post("/api/v1/auth/login", response_model=Token)
async def login(request: LoginRequest, req: Request):
    """
    Authenticate user and return JWT token
    
    Security:
    - Rate limited (5 attempts per 5 minutes)
    - Account lockout after 5 failed attempts
    - bcrypt password verification against database
    - All attempts logged to security audit trail
    """
    # Additional rate limiting for login endpoint (stricter)
    if not await check_rate_limit(req, limit=5, window=300):  # 5 attempts per 5 minutes
        logger.warning(f"Login rate limit exceeded for IP: {req.client.host}, username: {request.username}")
        await log_security_event(
            AuditEventType.RATE_LIMIT_EXCEEDED, "warning",
            username=request.username, source_ip=req.client.host,
            user_agent=req.headers.get("user-agent"),
            details={"endpoint": "/api/v1/auth/login"}
        )
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again in 5 minutes.",
            headers={"Retry-After": "300"}
        )
    
    if not request.username or not request.password:
        logger.warning(f"Login attempt with empty credentials from IP: {req.client.host}")
        raise HTTPException(status_code=400, detail="Username and password required")
    
    # ── Database authentication ──
    if db_pool:
        try:
            user = get_user_by_username(request.username)
            
            if not user:
                # Don't reveal whether username exists (timing-safe)
                await log_security_event(
                    AuditEventType.LOGIN_FAILURE, "warning",
                    username=request.username, source_ip=req.client.host,
                    user_agent=req.headers.get("user-agent"),
                    details={"reason": "user_not_found"}
                )
                raise HTTPException(status_code=401, detail="Invalid username or password")
            
            # Check if account is locked
            if user["is_locked"]:
                locked_until = user.get("locked_until")
                if locked_until and locked_until > datetime.utcnow():
                    await log_security_event(
                        AuditEventType.LOGIN_FAILURE, "warning",
                        username=request.username, source_ip=req.client.host,
                        user_agent=req.headers.get("user-agent"),
                        details={"reason": "account_locked", "locked_until": str(locked_until)}
                    )
                    raise HTTPException(
                        status_code=423,
                        detail=f"Account locked due to too many failed attempts. Try again after {locked_until.strftime('%H:%M UTC')}"
                    )
            
            # Check if account is active
            if not user["is_active"]:
                await log_security_event(
                    AuditEventType.LOGIN_FAILURE, "warning",
                    username=request.username, source_ip=req.client.host,
                    user_agent=req.headers.get("user-agent"),
                    details={"reason": "account_disabled"}
                )
                raise HTTPException(status_code=403, detail="Account is disabled. Contact administrator.")
            
            # Verify password with bcrypt
            if not verify_password(request.password, user["password_hash"]):
                attempts = update_login_failure(request.username)
                remaining = MAX_FAILED_ATTEMPTS - attempts
                
                severity = "critical" if attempts >= MAX_FAILED_ATTEMPTS else "warning"
                await log_security_event(
                    AuditEventType.LOGIN_FAILURE if remaining > 0 else AuditEventType.ACCOUNT_LOCKED,
                    severity,
                    username=request.username, source_ip=req.client.host,
                    user_agent=req.headers.get("user-agent"),
                    details={"reason": "wrong_password", "failed_attempts": attempts, "remaining": max(0, remaining)}
                )
                
                if remaining <= 0:
                    raise HTTPException(
                        status_code=423,
                        detail=f"Account locked after {MAX_FAILED_ATTEMPTS} failed attempts. Try again in {LOCKOUT_DURATION_MINUTES} minutes."
                    )
                raise HTTPException(status_code=401, detail="Invalid username or password")
            
            # Successful authentication
            update_login_success(request.username)
            
            await log_security_event(
                AuditEventType.LOGIN_SUCCESS, "info",
                username=request.username, source_ip=req.client.host,
                user_agent=req.headers.get("user-agent"),
                details={"roles": user["roles"]}
            )
            
            user_roles = user["roles"] if isinstance(user["roles"], list) else list(user["roles"])
            user_email = user.get("email") or f"{request.username}@netweaver.local"
            
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={
                    "sub": request.username,
                    "email": user_email,
                    "roles": user_roles,
                    "iat": datetime.utcnow(),
                },
                expires_delta=access_token_expires
            )
            
            return Token(
                access_token=access_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Database auth error: {e}", exc_info=True)
            # Fall through to demo mode if DB has issues
            logger.warning("Falling back to demo authentication mode")
    
    # ── Demo/Fallback mode (no database) ──
    logger.warning("⚠️  Using demo authentication (no database). NOT FOR PRODUCTION!")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": request.username,
            "email": f"{request.username}@netweaver.local",
            "roles": ["admin", "user"],
            "iat": datetime.utcnow(),
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
async def refresh_token(req: Request, current_user: User = Depends(get_current_user)):
    """Refresh access token"""
    await log_security_event(
        AuditEventType.TOKEN_REFRESH, "info",
        username=current_user.username, source_ip=req.client.host
    )
    
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


@app.post("/api/v1/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    req: Request,
    current_user: User = Depends(get_current_user)
):
    """Change current user's password"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="User management requires database connection")
    
    user = get_user_by_username(current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not verify_password(request.current_password, user["password_hash"]):
        await log_security_event(
            AuditEventType.PASSWORD_CHANGE, "warning",
            username=current_user.username, source_ip=req.client.host,
            details={"reason": "wrong_current_password"}
        )
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Update password
    new_hash = hash_password(request.new_password)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users 
                   SET password_hash = %s, password_changed_at = NOW(), updated_at = NOW()
                   WHERE username = %s""",
                (new_hash, current_user.username)
            )
            conn.commit()
    finally:
        release_db_connection(conn)
    
    await log_security_event(
        AuditEventType.PASSWORD_CHANGE, "info",
        username=current_user.username, source_ip=req.client.host,
        details={"status": "success"}
    )
    
    return {"message": "Password changed successfully"}


# ─── User Management Endpoints (Admin Only) ───────────────────────────────

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role"""
    if "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@app.get("/api/v1/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = None
):
    """List all users (admin only)"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="User management requires database connection")
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = """SELECT user_id, username, email, full_name, roles, is_active, 
                              is_locked, last_login, created_at
                       FROM users"""
            params = []
            
            if is_active is not None:
                query += " WHERE is_active = %s"
                params.append(is_active)
            
            query += " ORDER BY created_at DESC OFFSET %s LIMIT %s"
            params.extend([skip, limit])
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            return [
                UserResponse(
                    user_id=str(row["user_id"]),
                    username=row["username"],
                    email=row.get("email"),
                    full_name=row.get("full_name"),
                    roles=list(row["roles"]) if row["roles"] else ["user"],
                    is_active=row["is_active"],
                    is_locked=row["is_locked"],
                    last_login=row["last_login"].isoformat() if row.get("last_login") else None,
                    created_at=row["created_at"].isoformat()
                )
                for row in rows
            ]
    finally:
        release_db_connection(conn)


@app.post("/api/v1/users", response_model=UserResponse, status_code=201)
async def create_user(
    request: CreateUserRequest,
    req: Request,
    current_user: User = Depends(require_admin)
):
    """Create a new user (admin only)"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="User management requires database connection")
    
    # Check if username already exists
    existing = get_user_by_username(request.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    
    password_hash = hash_password(request.password)
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO users (username, email, password_hash, full_name, roles, created_by)
                   VALUES (%s, %s, %s, %s, %s, (SELECT user_id FROM users WHERE username = %s))
                   RETURNING user_id, username, email, full_name, roles, is_active, is_locked, created_at""",
                (
                    request.username, request.email, password_hash,
                    request.full_name, request.roles, current_user.username
                )
            )
            row = cur.fetchone()
            conn.commit()
            
            await log_security_event(
                AuditEventType.USER_CREATED, "info",
                username=current_user.username, source_ip=req.client.host,
                details={"created_user": request.username, "roles": request.roles}
            )
            
            return UserResponse(
                user_id=str(row["user_id"]),
                username=row["username"],
                email=row.get("email"),
                full_name=row.get("full_name"),
                roles=list(row["roles"]) if row["roles"] else ["user"],
                is_active=row["is_active"],
                is_locked=row["is_locked"],
                last_login=None,
                created_at=row["created_at"].isoformat()
            )
    except psycopg2.IntegrityError as e:
        conn.rollback()
        if "email" in str(e):
            raise HTTPException(status_code=409, detail="Email already in use")
        raise HTTPException(status_code=409, detail="User creation failed - duplicate entry")
    finally:
        release_db_connection(conn)


@app.get("/api/v1/users/{username}", response_model=UserResponse)
async def get_user(username: str, current_user: User = Depends(require_admin)):
    """Get user details (admin only)"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="User management requires database connection")
    
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        user_id=str(user["user_id"]),
        username=user["username"],
        email=user.get("email"),
        full_name=user.get("full_name"),
        roles=list(user["roles"]) if user["roles"] else ["user"],
        is_active=user["is_active"],
        is_locked=user["is_locked"],
        last_login=user["last_login"].isoformat() if user.get("last_login") else None,
        created_at=user["created_at"].isoformat()
    )


@app.put("/api/v1/users/{username}", response_model=UserResponse)
async def update_user(
    username: str,
    request: UpdateUserRequest,
    req: Request,
    current_user: User = Depends(require_admin)
):
    """Update user details (admin only)"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="User management requires database connection")
    
    existing = get_user_by_username(username)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build dynamic update query
    updates = []
    params = []
    
    if request.email is not None:
        updates.append("email = %s")
        params.append(request.email)
    if request.full_name is not None:
        updates.append("full_name = %s")
        params.append(request.full_name)
    if request.roles is not None:
        updates.append("roles = %s")
        params.append(request.roles)
    if request.is_active is not None:
        updates.append("is_active = %s")
        params.append(request.is_active)
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    updates.append("updated_at = NOW()")
    params.append(username)
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""UPDATE users SET {', '.join(updates)} WHERE username = %s
                    RETURNING user_id, username, email, full_name, roles, is_active, is_locked, last_login, created_at""",
                params
            )
            row = cur.fetchone()
            conn.commit()
            
            await log_security_event(
                AuditEventType.USER_UPDATED, "info",
                username=current_user.username, source_ip=req.client.host,
                details={"updated_user": username, "fields": list(request.dict(exclude_none=True).keys())}
            )
            
            return UserResponse(
                user_id=str(row["user_id"]),
                username=row["username"],
                email=row.get("email"),
                full_name=row.get("full_name"),
                roles=list(row["roles"]) if row["roles"] else ["user"],
                is_active=row["is_active"],
                is_locked=row["is_locked"],
                last_login=row["last_login"].isoformat() if row.get("last_login") else None,
                created_at=row["created_at"].isoformat()
            )
    finally:
        release_db_connection(conn)


@app.delete("/api/v1/users/{username}")
async def delete_user(
    username: str,
    req: Request,
    current_user: User = Depends(require_admin)
):
    """Delete user (admin only). Cannot delete yourself."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="User management requires database connection")
    
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s RETURNING username", (username,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            conn.commit()
            
            await log_security_event(
                AuditEventType.USER_DELETED, "warning",
                username=current_user.username, source_ip=req.client.host,
                details={"deleted_user": username}
            )
            
            return {"message": f"User '{username}' deleted successfully"}
    finally:
        release_db_connection(conn)


@app.post("/api/v1/users/{username}/unlock")
async def unlock_user(
    username: str,
    req: Request,
    current_user: User = Depends(require_admin)
):
    """Unlock a locked user account (admin only)"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="User management requires database connection")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users 
                   SET is_locked = false, locked_until = NULL, 
                       failed_login_attempts = 0, updated_at = NOW()
                   WHERE username = %s RETURNING username""",
                (username,)
            )
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            conn.commit()
            
            await log_security_event(
                AuditEventType.ACCOUNT_UNLOCKED, "info",
                username=current_user.username, source_ip=req.client.host,
                details={"unlocked_user": username}
            )
            
            return {"message": f"User '{username}' unlocked successfully"}
    finally:
        release_db_connection(conn)


@app.post("/api/v1/users/{username}/reset-password")
async def admin_reset_password(
    username: str,
    req: Request,
    current_user: User = Depends(require_admin)
):
    """Reset a user's password to a temporary one (admin only)"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="User management requires database connection")
    
    # Generate a strong temporary password
    temp_password = secrets.token_urlsafe(16) + "!A1"
    new_hash = hash_password(temp_password)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users 
                   SET password_hash = %s, password_changed_at = NOW(), 
                       is_locked = false, failed_login_attempts = 0, updated_at = NOW()
                   WHERE username = %s RETURNING username""",
                (new_hash, username)
            )
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            conn.commit()
            
            await log_security_event(
                AuditEventType.PASSWORD_CHANGE, "warning",
                username=current_user.username, source_ip=req.client.host,
                details={"target_user": username, "type": "admin_reset"}
            )
            
            return {
                "message": f"Password reset for '{username}'",
                "temporary_password": temp_password,
                "note": "User must change this password on next login"
            }
    finally:
        release_db_connection(conn)


# ─── Security Monitoring Endpoints ────────────────────────────────────────

@app.get("/api/v1/security/audit-log", response_model=List[AuditLogEntry])
async def get_audit_log(
    current_user: User = Depends(require_admin),
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    username: Optional[str] = None,
    source_ip: Optional[str] = None,
    since: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get security audit log entries (admin only)
    
    Filterable by event_type, severity, username, source_ip, and time range.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Security monitoring requires database connection")
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = "SELECT log_id, event_time, event_type, severity, username, source_ip, details, resolved FROM security_audit_log"
            conditions = []
            params = []
            
            if event_type:
                conditions.append("event_type = %s")
                params.append(event_type)
            if severity:
                conditions.append("severity = %s")
                params.append(severity)
            if username:
                conditions.append("username = %s")
                params.append(username)
            if source_ip:
                conditions.append("source_ip = %s")
                params.append(source_ip)
            if since:
                conditions.append("event_time >= %s")
                params.append(since)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY event_time DESC OFFSET %s LIMIT %s"
            params.extend([skip, limit])
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            return [
                AuditLogEntry(
                    log_id=str(row["log_id"]),
                    event_time=row["event_time"].isoformat(),
                    event_type=row["event_type"],
                    severity=row["severity"],
                    username=row.get("username"),
                    source_ip=str(row["source_ip"]) if row.get("source_ip") else None,
                    details=row.get("details") or {},
                    resolved=row["resolved"]
                )
                for row in rows
            ]
    finally:
        release_db_connection(conn)


@app.get("/api/v1/security/audit-log/summary")
async def get_audit_summary(
    current_user: User = Depends(require_admin),
    hours: int = Query(24, ge=1, le=720)
):
    """
    Get security audit log summary with aggregated stats (admin only)
    
    Returns counts by event type & severity for the specified time window.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Security monitoring requires database connection")
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Events by type
            cur.execute(
                """SELECT event_type, COUNT(*) as count
                   FROM security_audit_log
                   WHERE event_time >= NOW() - INTERVAL '%s hours'
                   GROUP BY event_type ORDER BY count DESC""",
                (hours,)
            )
            by_type = {row["event_type"]: row["count"] for row in cur.fetchall()}
            
            # Events by severity
            cur.execute(
                """SELECT severity, COUNT(*) as count
                   FROM security_audit_log
                   WHERE event_time >= NOW() - INTERVAL '%s hours'
                   GROUP BY severity ORDER BY count DESC""",
                (hours,)
            )
            by_severity = {row["severity"]: row["count"] for row in cur.fetchall()}
            
            # Top offending IPs
            cur.execute(
                """SELECT source_ip, COUNT(*) as count
                   FROM security_audit_log
                   WHERE event_time >= NOW() - INTERVAL '%s hours'
                     AND event_type IN ('login_failure', 'rate_limit_exceeded', 'account_locked')
                     AND source_ip IS NOT NULL
                   GROUP BY source_ip ORDER BY count DESC LIMIT 10""",
                (hours,)
            )
            top_offending_ips = [{"ip": str(row["source_ip"]), "count": row["count"]} for row in cur.fetchall()]
            
            # Failed logins per user
            cur.execute(
                """SELECT username, COUNT(*) as count
                   FROM security_audit_log
                   WHERE event_time >= NOW() - INTERVAL '%s hours'
                     AND event_type = 'login_failure'
                     AND username IS NOT NULL
                   GROUP BY username ORDER BY count DESC LIMIT 10""",
                (hours,)
            )
            failed_logins_by_user = {row["username"]: row["count"] for row in cur.fetchall()}
            
            # Locked accounts
            cur.execute(
                "SELECT username FROM users WHERE is_locked = true"
            )
            locked_accounts = [row["username"] for row in cur.fetchall()]
            
            return {
                "period_hours": hours,
                "timestamp": datetime.utcnow().isoformat(),
                "events_by_type": by_type,
                "events_by_severity": by_severity,
                "top_offending_ips": top_offending_ips,
                "failed_logins_by_user": failed_logins_by_user,
                "locked_accounts": locked_accounts,
                "total_events": sum(by_type.values()) if by_type else 0,
                "critical_events": by_severity.get("critical", 0),
                "warning_events": by_severity.get("warning", 0)
            }
    finally:
        release_db_connection(conn)


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



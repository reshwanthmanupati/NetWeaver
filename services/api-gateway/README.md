# API Gateway

Unified API Gateway for NetWeaver - Single entry point for all microservices with authentication, rate limiting, and routing.

## Overview

The API Gateway provides a unified HTTP interface to all NetWeaver Phase 2 microservices (Intent Engine, Device Manager, Self-Healing System, Security Agent). It handles cross-cutting concerns like authentication, authorization, rate limiting, and request routing.

## Features

### 🔐 Authentication & Authorization

- **JWT-based authentication**: Secure token-based auth
- **Token refresh**: Refresh tokens without re-login
- **Role-based access control**: User roles (admin, user)
- **Session management**: Secure session handling

### 🚦 Rate Limiting

- **Redis-backed rate limiting**: 100 requests/minute per IP
- **Configurable limits**: Adjust per endpoint
- **Graceful degradation**: Falls back if Redis unavailable
- **Per-client tracking**: IP-based tracking

### 🔀 Request Routing

- **Service discovery**: Routes to backend microservices
- **Health checking**: Service health monitoring
- **Load balancing**: Distributes requests (future)
- **Circuit breaker**: Handles service failures (future)

### 📡 Real-time Updates

- **WebSocket support**: Bi-directional real-time communication
- **Event broadcasting**: Broadcast to all connected clients
- **Connection management**: Automatic reconnection handling

### 📊 API Documentation

- **OpenAPI/Swagger**: Auto-generated API docs at `/docs`
- **ReDoc**: Alternative docs at `/redoc`
- **Interactive testing**: Built-in API testing UI

### 🛡️ Security

- **CORS support**: Configurable cross-origin requests
- **Request validation**: Pydantic models
- **Error handling**: Standardized error responses
- **Audit logging**: Request/response logging

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ↓
┌──────────────────────────┐
│     API Gateway          │
│  (Port 8080)             │
│                          │
│  ┌────────────────────┐  │
│  │ Authentication     │  │
│  │ Rate Limiting      │  │
│  │ Request Routing    │  │
│  └────────────────────┘  │
└──────────┬───────────────┘
           │
     ┌─────┼─────┬─────────┬─────────┐
     ↓     ↓     ↓         ↓         ↓
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Intent  │ │ Device  │ │  Self-  │ │Security │
│ Engine  │ │ Manager │ │ Healing │ │ Agent   │
│  :8081  │ │  :8083  │ │  :8082  │ │  :8084  │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
```

## API Endpoints

### Authentication

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer <token>
```

**Response:**
```json
{
  "username": "admin",
  "email": "admin@netweaver.local",
  "roles": ["admin", "user"]
}
```

#### Refresh Token
```http
POST /api/v1/auth/refresh
Authorization: Bearer <token>
```

### Intent Engine (via Gateway)

#### List Intents
```http
GET /api/v1/intents
Authorization: Bearer <token>
```

#### Create Intent
```http
POST /api/v1/intents
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "video-low-latency",
  "description": "Low latency for video traffic",
  "policy": {
    "traffic_type": "video",
    "max_latency_ms": 50
  }
}
```

#### Deploy Intent
```http
POST /api/v1/intents/{intent_id}/deploy
Authorization: Bearer <token>
Content-Type: application/json

{
  "device_ids": ["router-01", "router-02"]
}
```

### Device Manager (via Gateway)

#### List Devices
```http
GET /api/v1/devices
Authorization: Bearer <token>
```

#### Register Device
```http
POST /api/v1/devices
Authorization: Bearer <token>
Content-Type: application/json

{
  "hostname": "router-01",
  "ip_address": "192.168.1.1",
  "device_type": "router",
  "vendor": "cisco"
}
```

#### Deploy Configuration
```http
POST /api/v1/devices/{device_id}/config
Authorization: Bearer <token>
Content-Type: application/json

{
  "configuration": "interface GigabitEthernet0/0/0\n ip address 10.0.0.1 255.255.255.0",
  "method": "merge"
}
```

### Self-Healing (via Gateway)

#### List Incidents
```http
GET /api/v1/incidents?status=detected
Authorization: Bearer <token>
```

#### Get MTTR
```http
GET /api/v1/incidents/stats/mttr?period=24h
Authorization: Bearer <token>
```

#### Resolve Incident
```http
POST /api/v1/incidents/{incident_id}/resolve
Authorization: Bearer <token>
Content-Type: application/json

{
  "resolution": "Link restored manually",
  "resolved_by": "admin"
}
```

### Security Agent (via Gateway)

#### List Threats
```http
GET /api/v1/threats?severity=critical
Authorization: Bearer <token>
```

#### Mitigate Threat
```http
POST /api/v1/mitigate
Authorization: Bearer <token>
Content-Type: application/json

{
  "threat_id": "threat-1771056789123456",
  "mitigation_type": "blackhole",
  "target_ips": ["192.168.1.100"]
}
```

#### Get Security Statistics
```http
GET /api/v1/security/stats
Authorization: Bearer <token>
```

### Dashboard

#### Get Aggregated Dashboard
```http
GET /api/v1/dashboard
Authorization: Bearer <token>
```

**Response:**
```json
{
  "timestamp": "2026-02-14T10:30:00Z",
  "data": {
    "intents": {
      "total": 15,
      "intents": [...]
    },
    "devices": {
      "total": 50,
      "online": 45
    },
    "incidents": {
      "total_incidents": 127,
      "active_incidents": 5
    },
    "threats": {
      "total_threats": 35,
      "active_threats": 3
    }
  }
}
```

### WebSocket

#### Connect to WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

**Message Format:**
```json
{
  "type": "incident",
  "data": {
    "id": "incident-123",
    "status": "detected"
  },
  "timestamp": "2026-02-14T10:30:00Z"
}
```

## Configuration

### Environment Variables

```bash
# JWT Configuration  
JWT_SECRET_KEY=your_secret_key_here

# Backend Services
INTENT_ENGINE_URL=http://intent-engine:8081
DEVICE_MANAGER_URL=http://device-manager:8083
SELF_HEALING_URL=http://self-healing:8082
SECURITY_AGENT_URL=http://security-agent:8084

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Server
PORT=8080
```

### Rate Limiting Configuration

Default rate limits:
- **100 requests/minute** per IP address
- **60-second window**
- Configurable per endpoint

## Quick Start

### Standalone

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export JWT_SECRET_KEY=my_secret_key
export REDIS_HOST=localhost

# Run
python main.py
```

### Docker

```bash
# Build image
docker build -t netweaver-api-gateway .

# Run container
docker run -d \
  --name api-gateway \
  -p 8080:8080 \
  -e REDIS_HOST=redis \
  netweaver-api-gateway
```

### Docker Compose

```bash
# Start API Gateway with all dependencies
docker-compose up -d api-gateway
```

## Usage Examples

### Authentication Flow

```bash
# 1. Login to get token
TOKEN=$(curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access_token')

# 2. Use token in subsequent requests
curl http://localhost:8080/api/v1/intents \
  -H "Authorization: Bearer $TOKEN"
```

### Python Client Example

```python
import requests

# Login
response = requests.post('http://localhost:8080/api/v1/auth/login', json={
    'username': 'admin',
    'password': 'admin123'
})
token = response.json()['access_token']

# Make authenticated requests
headers = {'Authorization': f'Bearer {token}'}

# List intents
intents = requests.get('http://localhost:8080/api/v1/intents', headers=headers)
print(intents.json())

# Create intent
new_intent = requests.post('http://localhost:8080/api/v1/intents', 
    headers=headers,
    json={
        'name': 'video-qos',
        'policy': {'traffic_type': 'video', 'max_latency_ms': 50}
    })
print(new_intent.json())
```

### JavaScript/TypeScript Client

```typescript
class NetWeaverClient {
  private token: string | null = null;
  private baseUrl = 'http://localhost:8080';

  async login(username: string, password: string) {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await response.json();
    this.token = data.access_token;
  }

  async getIntents() {
    const response = await fetch(`${this.baseUrl}/api/v1/intents`, {
      headers: { 'Authorization': `Bearer ${this.token}` }
    });
    return response.json();
  }

  async createIntent(intent: any) {
    const response = await fetch(`${this.baseUrl}/api/v1/intents`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(intent)
    });
    return response.json();
  }
}

// Usage
const client = new NetWeaverClient();
await client.login('admin', 'admin123');
const intents = await client.getIntents();
console.log(intents);
```

## Security Considerations

### Production Deployment

1. **Change JWT Secret**: Set strong secret key in production
   ```bash
   export JWT_SECRET_KEY=$(openssl rand -hex 32)
   ```

2. **HTTPS Only**: Use TLS/SSL in production
   - Deploy behind reverse proxy (Nginx, Traefik)
   - Use Let's Encrypt certificates

3. **Configure CORS**: Restrict allowed origins
   ```python
   allow_origins=["https://yourdomain.com"]
   ```

4. **Database Authentication**: Implement proper user database
   - Hash passwords with bcrypt
   - Store users in PostgreSQL
   - Add email verification

5. **Rate Limiting**: Adjust based on traffic patterns
   - Per-user limits
   - Per-endpoint limits
   - DDoS protection

## Monitoring

### Health Check

```bash
curl http://localhost:8080/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "api-gateway",
  "timestamp": "2026-02-14T10:30:00Z",
  "services": {
    "intent_engine": "healthy",
    "device_manager": "healthy",
    "self_healing": "healthy",
    "security_agent": "healthy"
  },
  "redis": "connected"
}
```

### Metrics (Future)

- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- Authentication success/failure rate
- Rate limit hits
- WebSocket connections

## API Documentation

Access interactive API documentation:

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **OpenAPI JSON**: http://localhost:8080/openapi.json

## Troubleshooting

### Service Unavailable Errors

**Check backend service health:**
```bash
curl http://localhost:8080/health
```

**Check service directly:**
```bash
curl http://localhost:8081/health  # Intent Engine
curl http://localhost:8083/health  # Device Manager
curl http://localhost:8082/health  # Self-Healing
curl http://localhost:8084/health  # Security Agent
```

### Rate Limit Issues

**Check Redis connection:**
```bash
docker logs netweaver-api-gateway | grep Redis
```

**Clear rate limits:**
```bash
redis-cli KEYS "rate_limit:*" | xargs redis-cli DEL
```

### Authentication Failures

**Verify token:**
```bash
# Decode JWT (without verification)
echo "eyJhbGc..." | base64 -d
```

**Check token expiration:**
- Tokens expire after 60 minutes by default
- Use refresh endpoint to get new token

## Future Enhancements

- [ ] OAuth2/OIDC integration
- [ ] API key authentication
- [ ] GraphQL support
- [ ] gRPC gateway
- [ ] Request/response caching
- [ ] Circuit breaker pattern
- [ ] Service mesh integration (Istio/Linkerd)
- [ ] Distributed tracing (Jaeger/Zipkin)
- [ ] Advanced rate limiting (per-user, per-API)
- [ ] API versioning

## License

Copyright © 2026 NetWeaver Project

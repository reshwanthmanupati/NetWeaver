# NetWeaver AI Coding Agent Instructions

## Project Overview

NetWeaver is a **production-grade autonomous network infrastructure platform** combining real-time telemetry (1M+ flows/sec), ML traffic prediction, intent-based networking, autonomous self-healing, and security threat detection. This is a **microservices architecture** split across Phase 1 (Go telemetry/ML) and Phase 2 (6 microservices).

**Critical**: This is a **polyglot codebase** - Go (telemetry, intent engine, self-healing), Python (ML, API gateway, devices, security), React/TypeScript (web UI). Each language has distinct patterns.

---

## Architecture Mental Model

```
Web UI (React+Vite) → API Gateway (FastAPI) → 4 Backend Services (2 Go, 2 Python)
                                           ↓
                        TimescaleDB + RabbitMQ + Redis
```

**Service Boundaries (Critical for Cross-Service Changes):**
- **API Gateway** (`services/api-gateway/main.py`): JWT auth, rate limiting, CSRF protection, routes ALL external requests
- **Intent Engine** (`services/intent-engine/`, Go/Gin): YAML policy → vendor configs (Cisco/Juniper/Arista)
- **Device Manager** (`services/device-manager/`, FastAPI): SSH/NETCONF device connections
- **Self-Healing** (`services/self-healing/`, Go/Gin): Failure detection + auto-remediation
- **Security Agent** (`services/security-agent/`, FastAPI): DDoS detection, ML anomaly detection
- **Web UI** (`services/web-ui/`, React 18 + Vite): Material-UI dashboard

**Data Flow**: Client → API Gateway (port 8080) → Backend (8081-8084) → TimescaleDB. API Gateway forwards requests with `forward_request()` helper. Backend services never talk to each other directly (API Gateway orchestrates).

---

## Critical Developer Workflows

### Local Development (Zero Docker)
```bash
# 1. Start infrastructure only
docker-compose -f docker-compose-phase2.yml up -d timescaledb rabbitmq redis

# 2. Run services locally
cd services/api-gateway && uvicorn main:app --port 8080 --reload   # Python
cd services/intent-engine && go run main.go                          # Go
cd services/web-ui && npm run dev                                    # Vite hot reload
```

### Full Stack Docker
```bash
docker-compose -f docker-compose-phase2.yml up -d  # All 8 containers
curl http://localhost:8080/health                  # Verify
```

### Testing
```bash
# Go services: Built-in test files
cd services/intent-engine && go test ./...

# Python integration tests (requires running services)
cd tests && pytest test_api_gateway.py -v

# Web UI: No tests yet (manual browser testing)
```

### Rebuilding After Code Changes
```bash
# Option 1: Rebuild specific service
docker-compose -f docker-compose-phase2.yml build api-gateway
docker-compose -f docker-compose-phase2.yml up -d api-gateway

# Option 2: Rebuild all
docker-compose -f docker-compose-phase2.yml down
docker-compose -f docker-compose-phase2.yml up -d --build
```

---

## Project-Specific Patterns

### 1. Security (Non-Negotiable)
**All API endpoints require JWT authentication** except `/health` and `/api/v1/auth/login`.

Pattern in `services/api-gateway/main.py`:
```python
@app.post("/api/v1/intents")
async def create_intent(
    request: Request,
    current_user: User = Depends(get_current_user),    # JWT validation
    _rate_limit: None = Depends(require_rate_limit)    # Rate limiting
):
```

**CSRF Protection**: Enabled via middleware. Web UI sends `X-CSRF-Token` header (extracted from `csrf_token` cookie) on POST/PUT/DELETE. See `services/web-ui/src/services/api.ts` request interceptor.

**Input Validation**: Use Pydantic models with regex constraints (Python) or struct tags (Go). Example:
```python
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, regex=r'^[a-zA-Z0-9_-]+$')
```

**SQL Injection Prevention**: ALWAYS use parameterized queries. 
```go
// ✅ CORRECT
query := "SELECT * FROM intents WHERE id = $1"
s.db.QueryRow(query, id)

// ❌ NEVER DO THIS
query := fmt.Sprintf("SELECT * FROM intents WHERE id = '%s'", id)
```

See `SECURITY.md` for comprehensive security checklist.

---

### 2. Database Patterns

**TimescaleDB Schema** (`deployments/init-db.sql`):
- 12 tables, 7 hypertables (time-series optimized)
- Intent/Device/Incident/Threat tables share common pattern: UUID `id`, `created_at`, `updated_at`

**Go Database Access** (Intent Engine, Self-Healing):
```go
// services/intent-engine/internal/storage/postgres.go
type PostgresStorage struct {
    db *sql.DB  // Standard lib/pq, NOT pgx
}
```

**Python Database Access** (Device Manager, Security Agent):
```python
# Direct psycopg2 with connection pooling
import psycopg2.pool
pool = psycopg2.pool.SimpleConnectionPool(...)
```

**Critical**: Go services use `github.com/lib/pq` (not pgx despite go.mod), Python uses `psycopg2`. Placeholder syntax differs: `$1, $2` (Go) vs `%s, %s` (Python).

---

### 3. Go Service Structure (Intent Engine, Self-Healing)

Standard layout:
```
services/intent-engine/
├── main.go                    # Entry point, router setup
├── internal/
│   ├── api/handlers.go        # HTTP handlers (Gin)
│   ├── engine/                # Business logic
│   │   ├── intent_engine.go   # Core engine
│   │   ├── parser.go          # YAML parsing
│   │   └── translator.go      # Vendor config generation
│   └── storage/postgres.go    # Database layer
└── Dockerfile
```

**Router Pattern** (Gin):
```go
// main.go
router := gin.Default()
v1 := router.Group("/api/v1")
v1.GET("/intents", handler.ListIntents)
v1.POST("/intents", handler.CreateIntent)

// CRITICAL: Static routes BEFORE wildcard routes to prevent panic
router.Static("/static", "./static")  // ✅ First
router.GET("/:id", handler.Get)       // ✅ After
```

**Health Check Pattern**:
```go
router.GET("/health", func(c *gin.Context) {
    c.JSON(200, gin.H{"status": "healthy"})
})
```

---

### 4. Python Service Structure (API Gateway, Device Manager, Security Agent)

**FastAPI Pattern**:
```python
# services/api-gateway/main.py
app = FastAPI(lifespan=lifespan)  # Async startup/shutdown

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Redis, HTTP client
    global redis_client, http_client
    redis_client = await redis.from_url(...)
    http_client = httpx.AsyncClient()
    yield
    # Cleanup: Close connections
    await redis_client.close()
    await http_client.aclose()
```

**Dependency Injection for Auth**:
```python
async def get_current_user(token_data: dict = Depends(verify_token)) -> User:
    # Validates JWT, returns User object
    
@app.get("/protected")
async def protected_route(current_user: User = Depends(get_current_user)):
    # Endpoint requires valid JWT
```

**Request Forwarding** (API Gateway specific):
```python
await forward_request(
    INTENT_ENGINE_URL,        # http://intent-engine:8081
    "/api/v1/intents",        # Path
    method="POST",
    json_data=body,
    timeout=30.0
)
```

---

### 5. Web UI Patterns (React + TypeScript + Vite)

**Build System**: Migrated from `react-scripts` to **Vite 5** to fix ajv dependency conflicts. 

**Critical**: Run `npm run dev` (NOT `npm start`, though aliased). Vite dev server on port 3000.

**API Client Pattern** (`services/web-ui/src/services/api.ts`):
```typescript
class ApiService {
  private client: AxiosInstance;
  
  constructor() {
    this.client = axios.create({
      baseURL: '/api/v1',           // Proxied to localhost:8080 via vite.config.ts
      withCredentials: true,         // Enable cookies for CSRF
    });
    
    // Request interceptor adds CSRF token
    this.client.interceptors.request.use(config => {
      if (['post', 'put', 'delete'].includes(config.method)) {
        config.headers['X-CSRF-Token'] = getCsrfTokenFromCookie();
      }
    });
  }
}
```

**Vite Proxy** (`services/web-ui/vite.config.ts`):
```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8080',  // API Gateway
      changeOrigin: true,
    },
  },
}
```

**Material-UI Theming**: Uses `createTheme()` in `App.tsx` with dark mode toggle.

**Form Validation**: Intents creation requires `policy.type`, `policy.actions[]`, `targets[]`. See `services/web-ui/src/pages/Intents.tsx` for complex form example.

---

### 6. Multi-Vendor Device Configuration

**Core Logic**: `services/intent-engine/internal/engine/translator.go`

Pattern:
```go
func (ct *ConfigTranslator) TranslateIntent(intent *Intent, vendor string, deviceID string) (string, error) {
    switch vendor {
    case "cisco_ios":
        return ct.translateToCiscoIOS(intent)
    case "juniper_junos":
        return ct.translateToJuniperJunOS(intent)
    case "arista_eos":
        return ct.translateToAristaEOS(intent)
    }
}
```

**Templates**: `services/device-manager/templates/` contains Jinja2 templates for Cisco/Juniper/Arista.

**Deployment**: Device Manager uses `connectors.py` (SSH via Paramiko, NETCONF via ncclient, eAPI via requests).

---

## Common Pitfalls & Solutions

### 1. "ECONNREFUSED localhost:8080" in Web UI
**Cause**: API Gateway not running.  
**Fix**: `cd services/api-gateway && uvicorn main:app --port 8080` or start Docker Compose.

### 2. "500 Internal Server Error" when creating intents
**Cause**: Missing required fields (`policy.type`, `policy.actions[]`, `targets[]`).  
**Fix**: Use the updated intent creation form in `Intents.tsx` (has all fields).

### 3. Go service fails with "pq: relation 'intents' does not exist"
**Cause**: Database not initialized.  
**Fix**: Ensure TimescaleDB ran `init-db.sql`. Check: `docker logs netweaver-timescaledb`.

### 4. Web UI ajv dependency conflicts
**Cause**: Legacy `react-scripts` incompatibility.  
**Fix**: Already migrated to Vite. If recreating: `npm install --legacy-peer-deps` is NOT the solution, use Vite.

### 5. CSRF token missing errors
**Cause**: API Gateway sets `csrf_token` cookie only after first GET request.  
**Fix**: Web UI must make at least one GET (e.g., `/api/v1/dashboard`) before POST/PUT/DELETE.

### 6. Docker Compose services fail to communicate
**Cause**: Services use `localhost` instead of Docker service names.  
**Fix**: In Docker, use `http://intent-engine:8081` (service name), NOT `http://localhost:8081`.

---

## Environment Variables (Production)

**API Gateway** (`services/api-gateway/main.py`):
```bash
JWT_SECRET_KEY=<32-byte-secure-token>     # Generate with secrets.token_urlsafe(32)
ENVIRONMENT=production                     # Enables HSTS, sanitizes errors
ALLOWED_ORIGINS=https://yourdomain.com     # Restrict CORS
ACCESS_TOKEN_EXPIRE_MINUTES=30             # Default 60
CSRF_PROTECTION=true                       # Default true
```

**Backend Services** (Intent Engine, Device Manager, Self-Healing, Security Agent):
```bash
DB_HOST=timescaledb                        # Docker: service name, Local: localhost
DB_PORT=5432
DB_NAME=netweaver
DB_USER=netweaver
DB_PASSWORD=<secure-password>
```

See `SECURITY.md` § Configuration Guide for full list.

---

## Key Files for Context

- **`README.md`**: Architecture diagrams, API endpoints (40+ listed), quick start
- **`SECURITY.md`**: Security checklist, CSRF/JWT/HTTPS implementation details
- **`docker-compose-phase2.yml`**: All 8 services with health checks, dependencies
- **`deployments/init-db.sql`**: Complete database schema (12 tables)
- **`services/api-gateway/main.py`**: Request routing logic, authentication, rate limiting
- **`services/intent-engine/internal/engine/translator.go`**: Multi-vendor config generation
- **`services/web-ui/src/services/api.ts`**: API client with CSRF handling

---

## Testing Strategy

**Unit Tests**: Go services have `*_test.go` files (run `go test ./...`).

**Integration Tests**: `tests/test_api_gateway.py` - 18+ pytest tests covering:
- Authentication flow
- Intent/Device CRUD
- Incident/Threat monitoring
- Dashboard aggregation
- Rate limiting enforcement

**Manual Testing**: Use curl or Web UI. Example workflow:
```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r '.access_token')

# 2. Create intent
curl -X POST http://localhost:8080/api/v1/intents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @services/intent-engine/examples/latency-policy.yaml

# 3. Deploy to device
curl -X POST http://localhost:8080/api/v1/intents/{intent_id}/deploy \
  -H "Authorization: Bearer $TOKEN"
```

---

## When to Read Multiple Files

**Adding a new API endpoint:**
1. `services/api-gateway/main.py` - Add route + forwarding
2. `services/{service}/main.py` or `main.go` - Implement handler
3. `services/{service}/internal/storage/postgres.go|postgres.py` - Add DB queries
4. `services/web-ui/src/services/api.ts` - Add client method
5. `services/web-ui/src/pages/{Page}.tsx` - Update UI

**Debugging cross-service issues:**
1. Check API Gateway logs for routing errors
2. Check backend service logs for business logic errors  
3. Check TimescaleDB for schema/query issues: `docker exec -it netweaver-timescaledb psql -U netweaver -d netweaver`

**Security changes:**
1. `services/api-gateway/main.py` - Middleware, auth, rate limiting
2. `services/web-ui/src/services/api.ts` - Client-side token/CSRF handling
3. `SECURITY.md` - Update documentation

---

## Conventions that Differ from Defaults

1. **No `lib/pq` → `pgx` migration**: Despite `go.mod` listing `pgx`, Intent Engine uses `database/sql` + `lib/pq`. Keep it.

2. **API Gateway owns all auth**: Backend services trust API Gateway. Don't add JWT validation to Intent Engine/Device Manager/etc.

3. **Docker hostnames in production, localhost in dev**: Service URLs toggled via env vars. API Gateway defaults to `http://localhost:8081` but Docker Compose overrides to `http://intent-engine:8081`.

4. **Vite, not react-scripts**: Web UI build system is Vite 5. `npm run build` → `dist/` folder.

5. **TimescaleDB hypertables**: Use `CREATE TABLE` then `SELECT create_hypertable()`. See `init-db.sql` examples.

6. **Git workflow**: Direct commits to `main`. No PR process (single developer project).

---

## Module Naming

**Go**: `module github.com/netweaver/netweaver` (NOT `github.com/reshwanthmanupati/NetWeaver`).

**Python**: No package structure, each service is standalone with `requirements.txt`.

**Import Example** (Intent Engine):
```go
import (
    "github.com/netweaver/netweaver/services/intent-engine/internal/engine"
    "github.com/netweaver/netweaver/pkg/database"  // Phase 1 shared packages
)
```

---

## Questions to Ask for Unclear Intent

1. **"Should this endpoint require authentication?"** - Default: YES (except `/health`, `/docs`, `/login`)
2. **"Which service should this logic live in?"** - Follow domain: intents→Intent Engine, devices→Device Manager, incidents→Self-Healing, threats→Security Agent, auth/routing→API Gateway
3. **"Docker or local?"** - Assume Docker unless user says "local dev"
4. **"Production or dev environment?"** - Assume dev unless `ENVIRONMENT=production` mentioned
5. **"React component structure?"** - See existing `pages/*.tsx` for patterns (Material-UI, Recharts charts, API client usage)

---

## Final Notes

- **Documentation is authoritative**: `README.md`, `SECURITY.md`, and service-level READMEs are kept up-to-date
- **Commit messages**: Use conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
- **No TypeScript strict mode**: Web UI uses `tsconfig.json` with `"strict": false`
- **Go 1.21 features**: Use generics, `any`, `os.ReadFile` (not `ioutil`)
- **Python 3.11 features**: Use `asyncio.TaskGroup`, `tomllib`, match/case statements

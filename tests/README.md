# NetWeaver Integration Tests

Comprehensive integration test suite for NetWeaver Phase 2 services.

## Test Coverage

- **Authentication**: Login, token management, protected routes
- **Intent Management**: CRUD operations, deployment
- **Device Management**: Registration, configuration
- **Incident Monitoring**: Listing, resolution, MTTR stats
- **Threat Management**: Detection, mitigation
- **Dashboard**: Data aggregation from all services
- **End-to-End Workflows**: Complete intent creation to deployment
- **Health Checks**: Service availability
- **Rate Limiting**: API Gateway rate limit enforcement

## Prerequisites

Ensure all NetWeaver services are running:
- API Gateway (port 8080)
- Intent Engine (port 8081)
- Device Manager (port 8083)
- Self-Healing System (port 8082)
- Security Agent (port 8084)
- TimescaleDB, RabbitMQ, Redis

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest test_api_gateway.py -v

# Run specific test class
pytest test_api_gateway.py::TestAuthentication -v

# Run with parallel execution
pytest test_api_gateway.py -v -n 4

# Run with timeout (10s per test)
pytest test_api_gateway.py -v --timeout=10
```

## Test Classes

### TestAuthentication
Tests authentication and authorization:
- Login with valid/invalid credentials
- Token validation
- Protected route access
- Current user retrieval

### TestIntents
Tests intent management:
- List all intents
- Create new intent
- Get specific intent
- Delete intent

### TestDevices
Tests device management:
- List devices
- Register new device
- Device validation

### TestIncidents
Tests incident monitoring:
- List incidents
- Get MTTR statistics
- Incident filtering

### TestThreats
Tests threat management:
- List threats
- Get security statistics

### TestDashboard
Tests dashboard aggregation:
- Verify data from all services
- Check timestamp and structure

### TestEndToEndWorkflow
Tests complete workflows:
- Intent creation → device registration → deployment
- Cleanup and verification

### TestHealthChecks
Tests service health:
- API Gateway health
- All backend services health

### TestRateLimiting
Tests rate limiting:
- Enforce 100 requests/minute limit

## Configuration

Edit `BASE_URL` in test files to match your environment:

```python
BASE_URL = "http://localhost:8080/api/v1"
```

## Running Tests in CI/CD

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests with JUnit XML output
pytest test_api_gateway.py -v --junitxml=test-results.xml

# Run with coverage
pytest test_api_gateway.py -v --cov=. --cov-report=html
```

## Expected Results

All tests should pass when services are healthy:

```
test_api_gateway.py::TestAuthentication::test_login_success PASSED
test_api_gateway.py::TestAuthentication::test_login_invalid_credentials PASSED
test_api_gateway.py::TestAuthentication::test_get_current_user PASSED
test_api_gateway.py::TestAuthentication::test_protected_route_without_token PASSED
test_api_gateway.py::TestIntents::test_list_intents PASSED
test_api_gateway.py::TestIntents::test_create_intent PASSED
test_api_gateway.py::TestIntents::test_get_intent PASSED
test_api_gateway.py::TestIntents::test_delete_intent PASSED
test_api_gateway.py::TestDevices::test_list_devices PASSED
test_api_gateway.py::TestDevices::test_register_device PASSED
test_api_gateway.py::TestIncidents::test_list_incidents PASSED
test_api_gateway.py::TestIncidents::test_get_mttr_stats PASSED
test_api_gateway.py::TestThreats::test_list_threats PASSED
test_api_gateway.py::TestThreats::test_get_security_stats PASSED
test_api_gateway.py::TestDashboard::test_get_dashboard PASSED
test_api_gateway.py::TestEndToEndWorkflow::test_complete_intent_workflow PASSED
test_api_gateway.py::TestHealthChecks::test_api_gateway_health PASSED
test_api_gateway.py::TestHealthChecks::test_all_services_healthy PASSED
```

## Troubleshooting

### Connection Errors
- Verify all services are running: `docker ps`
- Check service health: `curl http://localhost:8080/health`

### Authentication Failures
- Ensure default credentials work: `admin` / `admin123`
- Check JWT secret is configured correctly

### Test Timeouts
- Increase timeout: `pytest test_api_gateway.py --timeout=30`
- Check service logs for performance issues

### Rate Limiting Tests
- Skip if needed: `pytest -m "not rate_limit"`
- Allow time between test runs for rate limits to reset

## Performance Validation

Target metrics:
- API response time: < 100ms (90th percentile)
- Intent creation: < 500ms
- Device registration: < 1s
- Dashboard aggregation: < 2s
- Authentication: < 50ms

## License

Copyright © 2026 NetWeaver Project

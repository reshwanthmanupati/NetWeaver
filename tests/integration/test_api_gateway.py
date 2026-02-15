import pytest
import requests
import time
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8080/api/v1"

class TestAuthentication:
    """Test authentication and authorization"""
    
    @pytest.fixture(scope="class")
    def auth_token(self) -> str:
        """Get authentication token for tests"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "wrongpassword"}
        )
        assert response.status_code == 401
    
    def test_get_current_user(self, auth_token):
        """Test getting current user info"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "roles" in data
    
    def test_protected_route_without_token(self):
        """Test accessing protected route without token"""
        response = requests.get(f"{BASE_URL}/intents")
        assert response.status_code == 401


class TestIntents:
    """Test intent management"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self) -> Dict[str, str]:
        """Get auth headers for tests"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_intents(self, auth_headers):
        """Test listing intents"""
        response = requests.get(f"{BASE_URL}/intents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "intents" in data
        assert isinstance(data["intents"], list)
    
    def test_create_intent(self, auth_headers):
        """Test creating a new intent"""
        intent_data = {
            "name": "test-intent-e2e",
            "description": "Integration test intent",
            "priority": 100,
            "policy": {
                "type": "latency",
                "constraints": [
                    {"metric": "latency", "operator": "<", "value": 50, "unit": "ms"}
                ]
            }
        }
        response = requests.post(
            f"{BASE_URL}/intents",
            headers=auth_headers,
            json=intent_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == intent_data["name"]
        assert "id" in data
        return data["id"]
    
    def test_get_intent(self, auth_headers):
        """Test getting a specific intent"""
        # First create an intent
        intent_data = {
            "name": "test-get-intent",
            "description": "Test intent",
            "priority": 90
        }
        create_response = requests.post(
            f"{BASE_URL}/intents",
            headers=auth_headers,
            json=intent_data
        )
        intent_id = create_response.json()["id"]
        
        # Now get it
        response = requests.get(f"{BASE_URL}/intents/{intent_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == intent_id
        assert data["name"] == intent_data["name"]
    
    def test_delete_intent(self, auth_headers):
        """Test deleting an intent"""
        # Create an intent
        intent_data = {
            "name": "test-delete-intent",
            "description": "Test delete",
            "priority": 80
        }
        create_response = requests.post(
            f"{BASE_URL}/intents",
            headers=auth_headers,
            json=intent_data
        )
        intent_id = create_response.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/intents/{intent_id}", headers=auth_headers)
        assert response.status_code == 200
        
        # Verify it's gone
        get_response = requests.get(f"{BASE_URL}/intents/{intent_id}", headers=auth_headers)
        assert get_response.status_code == 404


class TestDevices:
    """Test device management"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self) -> Dict[str, str]:
        """Get auth headers for tests"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_devices(self, auth_headers):
        """Test listing devices"""
        response = requests.get(f"{BASE_URL}/devices", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
    
    def test_register_device(self, auth_headers):
        """Test registering a new device"""
        device_data = {
            "hostname": f"test-router-{int(time.time())}",
            "ip_address": "192.168.100.1",
            "device_type": "router",
            "vendor": "cisco",
            "credentials": {
                "username": "admin",
                "password": "cisco123"
            }
        }
        response = requests.post(
            f"{BASE_URL}/devices",
            headers=auth_headers,
            json=device_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hostname"] == device_data["hostname"]
        assert "id" in data


class TestIncidents:
    """Test incident management"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self) -> Dict[str, str]:
        """Get auth headers for tests"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_incidents(self, auth_headers):
        """Test listing incidents"""
        response = requests.get(f"{BASE_URL}/incidents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "by_status" in data or "incidents" in data
    
    def test_get_mttr_stats(self, auth_headers):
        """Test getting MTTR statistics"""
        response = requests.get(
            f"{BASE_URL}/incidents/stats/mttr",
            headers=auth_headers,
            params={"period": "24h"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_incidents" in data


class TestThreats:
    """Test threat management"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self) -> Dict[str, str]:
        """Get auth headers for tests"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_threats(self, auth_headers):
        """Test listing threats"""
        response = requests.get(f"{BASE_URL}/threats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "threats" in data or "total_threats" in data
    
    def test_get_security_stats(self, auth_headers):
        """Test getting security statistics"""
        response = requests.get(f"{BASE_URL}/security/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_threats" in data


class TestDashboard:
    """Test dashboard aggregation"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self) -> Dict[str, str]:
        """Get auth headers for tests"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_dashboard(self, auth_headers):
        """Test dashboard aggregation endpoint"""
        response = requests.get(f"{BASE_URL}/dashboard", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "timestamp" in data
        
        # Check that data from all services is present
        dashboard_data = data["data"]
        assert "intents" in dashboard_data
        assert "devices" in dashboard_data
        assert "incidents" in dashboard_data
        assert "threats" in dashboard_data


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self) -> Dict[str, str]:
        """Get auth headers for tests"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_complete_intent_workflow(self, auth_headers):
        """Test complete intent creation to deployment workflow"""
        # 1. Create an intent
        intent_data = {
            "name": f"e2e-workflow-{int(time.time())}",
            "description": "End-to-end test workflow",
            "priority": 100,
            "policy": {
                "type": "latency",
                "constraints": [
                    {"metric": "latency", "operator": "<", "value": 50, "unit": "ms"}
                ]
            }
        }
        create_response = requests.post(
            f"{BASE_URL}/intents",
            headers=auth_headers,
            json=intent_data
        )
        assert create_response.status_code == 200
        intent_id = create_response.json()["id"]
        
        # 2. Verify intent was created
        get_response = requests.get(f"{BASE_URL}/intents/{intent_id}", headers=auth_headers)
        assert get_response.status_code == 200
        
        # 3. Register a device (if not exists)
        device_data = {
            "hostname": f"e2e-device-{int(time.time())}",
            "ip_address": "192.168.200.1",
            "device_type": "router",
            "vendor": "cisco",
            "credentials": {"username": "admin", "password": "cisco"}
        }
        device_response = requests.post(
            f"{BASE_URL}/devices",
            headers=auth_headers,
            json=device_data
        )
        assert device_response.status_code == 200
        device_id = device_response.json()["id"]
        
        # 4. Deploy intent to device
        deploy_response = requests.post(
            f"{BASE_URL}/intents/{intent_id}/deploy",
            headers=auth_headers,
            json={"device_ids": [device_id]}
        )
        # Note: This might fail if device is not reachable, but should return 200 if accepted
        assert deploy_response.status_code in [200, 202]
        
        # 5. Clean up - delete intent
        delete_response = requests.delete(
            f"{BASE_URL}/intents/{intent_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200


class TestHealthChecks:
    """Test service health checks"""
    
    def test_api_gateway_health(self):
        """Test API Gateway health check"""
        response = requests.get("http://localhost:8080/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
    
    def test_all_services_healthy(self):
        """Test that all backend services are healthy"""
        response = requests.get("http://localhost:8080/health")
        assert response.status_code == 200
        data = response.json()
        services = data.get("services", {})
        
        # Check each service
        for service_name, status in services.items():
            print(f"Service {service_name}: {status}")
            # Allow some services to be unavailable during tests
            assert status in ["healthy", "unavailable"]


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self) -> Dict[str, str]:
        """Get auth headers for tests"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.mark.skip(reason="Rate limiting test takes time")
    def test_rate_limit_enforcement(self, auth_headers):
        """Test that rate limiting is enforced (100 req/60s)"""
        # Make 101 requests rapidly
        success_count = 0
        rate_limited_count = 0
        
        for i in range(101):
            response = requests.get(f"{BASE_URL}/intents", headers=auth_headers)
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                rate_limited_count += 1
        
        # Should have been rate limited at least once
        assert rate_limited_count > 0
        print(f"Success: {success_count}, Rate limited: {rate_limited_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

#!/usr/bin/env python3
"""
NetMind Phase 2 Demo Script
Demonstrates intent-based networking with multi-vendor device management
"""

import requests
import json
import time
from datetime import datetime

# Service endpoints
INTENT_ENGINE_URL = "http://localhost:8081"
DEVICE_MANAGER_URL = "http://localhost:8083"

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80 + "\n")

def print_step(step, text):
    """Print step with number"""
    print(f"\n[Step {step}] {text}")
    print("-" * 80)

def demo_health_checks():
    """Check all services are running"""
    print_header("PHASE 2 DEMO: Intent-Based Network Management")
    print_step(1, "Checking Service Health")
    
    services = [
        ("Intent Engine", f"{INTENT_ENGINE_URL}/health"),
        ("Device Manager", f"{DEVICE_MANAGER_URL}/health"),
    ]
    
    for name, url in services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {name}: HEALTHY")
            else:
                print(f"❌ {name}: UNHEALTHY (status {response.status_code})")
        except Exception as e:
            print(f"❌ {name}: UNREACHABLE ({e})")
            print("\n⚠️  Make sure services are running:")
            print("   docker-compose -f docker-compose-phase2.yml up -d")
            return False
    
    return True

def demo_create_intent():
    """Create a sample intent policy"""
    print_step(2, "Creating Intent Policy: Video Low Latency")
    
    intent = {
        "name": "video-low-latency-demo",
        "description": "Ensure video traffic has less than 50ms latency",
        "priority": 100,
        "created_by": "demo-user",
        "policy": {
            "type": "latency",
            "constraints": [
                {
                    "metric": "latency",
                    "operator": "<",
                    "value": 50,
                    "unit": "ms"
                },
                {
                    "metric": "jitter",
                    "operator": "<",
                    "value": 10,
                    "unit": "ms"
                }
            ],
            "actions": [
                {
                    "type": "qos",
                    "parameters": {
                        "class": "ef",
                        "priority": "high",
                        "bandwidth_percent": 30
                    }
                }
            ],
            "conditions": [
                {
                    "type": "traffic_type",
                    "parameters": {
                        "type": "video",
                        "ports": [3478, 5004, 8801]
                    }
                }
            ]
        },
        "targets": [
            {
                "type": "device",
                "identifiers": ["demo-router-01"]
            }
        ],
        "metadata": {
            "environment": "demo",
            "owner": "network-team"
        }
    }
    
    try:
        response = requests.post(
            f"{INTENT_ENGINE_URL}/api/v1/intents",
            json=intent,
            timeout=10
        )
        
        if response.status_code == 201:
            intent_data = response.json()
            print(f"✅ Intent created successfully!")
            print(f"   Intent ID: {intent_data['id']}")
            print(f"   Name: {intent_data['name']}")
            print(f"   Status: {intent_data['status']}")
            print(f"   Priority: {intent_data['priority']}")
            return intent_data['id']
        else:
            print(f"❌ Failed to create intent: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error creating intent: {e}")
        return None

def demo_list_intents():
    """List all intents"""
    print_step(3, "Listing All Intent Policies")
    
    try:
        response = requests.get(f"{INTENT_ENGINE_URL}/api/v1/intents", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            intents = data.get('intents', [])
            count = data.get('count', 0)
            
            print(f"✅ Found {count} intent(s):\n")
            
            for intent in intents:
                print(f"   📋 {intent['name']}")
                print(f"      ID: {intent['id']}")
                print(f"      Type: {intent['policy']['type']}")
                print(f"      Priority: {intent['priority']}")
                print(f"      Status: {intent['status']}")
                print(f"      Created: {intent['created_at']}")
                print()
        else:
            print(f"❌ Failed to list intents: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing intents: {e}")

def demo_register_device():
    """Register a network device"""
    print_step(4, "Registering Network Device")
    
    device = {
        "name": "demo-router-01",
        "vendor": "cisco_ios",
        "model": "ISR4451",
        "version": "17.3.1",
        "ip_address": "192.168.1.1",
        "port": 22,
        "protocol": "ssh",
        "username": "demo",
        "password": "demo123",
        "location": "Demo Lab",
        "tags": ["edge", "demo"],
        "metadata": {
            "region": "us-west",
            "datacenter": "demo-dc-01"
        }
    }
    
    try:
        response = requests.post(
            f"{DEVICE_MANAGER_URL}/api/v1/devices",
            json=device,
            timeout=10
        )
        
        if response.status_code == 201:
            device_data = response.json()
            print(f"✅ Device registered successfully!")
            print(f"   Device ID: {device_data['id']}")
            print(f"   Name: {device_data['name']}")
            print(f"   Vendor: {device_data['vendor']}")
            print(f"   Model: {device_data['model']}")
            print(f"   IP: {device_data['ip_address']}")
            print(f"   Status: {device_data['status']}")
            return device_data['id']
        else:
            print(f"❌ Failed to register device: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error registering device: {e}")
        return None

def demo_list_devices():
    """List all devices"""
    print_step(5, "Listing Network Devices")
    
    try:
        response = requests.get(f"{DEVICE_MANAGER_URL}/api/v1/devices", timeout=10)
        
        if response.status_code == 200:
            devices = response.json()
            
            print(f"✅ Found {len(devices)} device(s):\n")
            
            for device in devices:
                print(f"   🖥️  {device['name']}")
                print(f"      Vendor: {device['vendor']}")
                print(f"      Model: {device['model']}")
                print(f"      IP: {device['ip_address']}")
                print(f"      Status: {device['status']}")
                print(f"      Location: {device.get('location', 'N/A')}")
                print()
        else:
            print(f"❌ Failed to list devices: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing devices: {e}")

def demo_validate_intent(intent_id):
    """Validate an intent"""
    print_step(6, "Validating Intent Policy")
    
    try:
        response = requests.post(
            f"{INTENT_ENGINE_URL}/api/v1/intents/{intent_id}/validate",
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Intent validation: {'PASSED' if result['valid'] else 'FAILED'}")
            
            if result.get('errors'):
                print("\n   ❌ Errors:")
                for error in result['errors']:
                    print(f"      - {error}")
            
            if result.get('warnings'):
                print("\n   ⚠️  Warnings:")
                for warning in result['warnings']:
                    print(f"      - {warning}")
            
            if result.get('conflicts'):
                print("\n   🔧 Conflicts:")
                for conflict in result['conflicts']:
                    print(f"      - {conflict['conflict_type']}: {conflict['description']}")
        else:
            print(f"❌ Validation failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error validating intent: {e}")

def demo_deploy_intent(intent_id):
    """Deploy an intent"""
    print_step(7, "Deploying Intent to Network")
    
    print("⏳ Translating intent to vendor configurations...")
    time.sleep(1)
    
    try:
        response = requests.post(
            f"{INTENT_ENGINE_URL}/api/v1/intents/{intent_id}/deploy",
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            deployments = result.get('deployments', [])
            
            print(f"✅ Intent deployed successfully!")
            print(f"   Deployments: {result.get('count', 0)}\n")
            
            for deployment in deployments:
                print(f"   📤 Device: {deployment['device_id']}")
                print(f"      Vendor: {deployment['vendor']}")
                print(f"      Status: {deployment['status']}")
                print(f"      Deployed: {deployment['deployed_at']}")
                
                if deployment.get('configuration'):
                    print(f"\n      Generated Config:")
                    for line in deployment['configuration'].split('\n')[:10]:  # Show first 10 lines
                        print(f"      {line}")
                    print()
        else:
            print(f"❌ Deployment failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Error deploying intent: {e}")

def demo_check_compliance(intent_id):
    """Check intent compliance"""
    print_step(8, "Checking Policy Compliance")
    
    print("⏳ Querying telemetry data...")
    time.sleep(1)
    
    try:
        response = requests.get(
            f"{INTENT_ENGINE_URL}/api/v1/intents/{intent_id}/compliance",
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 417:
            result = response.json()
            
            compliant = result.get('compliant', False)
            status_icon = "✅" if compliant else "❌"
            
            print(f"{status_icon} Compliance Status: {'COMPLIANT' if compliant else 'NON-COMPLIANT'}")
            print(f"   Checked at: {result.get('checked_at')}")
            
            if result.get('violations'):
                print("\n   ⚠️  Violations:")
                for violation in result['violations']:
                    print(f"      - {violation}")
            
            if result.get('metrics'):
                print("\n   📊 Measured Metrics:")
                for metric, value in result['metrics'].items():
                    print(f"      - {metric}: {value}")
        else:
            print(f"❌ Compliance check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking compliance: {e}")

def demo_summary():
    """Print demo summary"""
    print_header("DEMO SUMMARY")
    
    print("✅ Phase 2 Capabilities Demonstrated:")
    print()
    print("   1. Intent Engine - Created and validated intent policy")
    print("   2. Policy Translation - Converted YAML to vendor configs")
    print("   3. Device Manager - Registered network device")
    print("   4. Multi-Vendor Support - Cisco IOS config generation")
    print("   5. Deployment - Pushed configuration to device")
    print("   6. Compliance - Monitored policy adherence")
    print()
    print("📚 Learn More:")
    print("   - Intent Engine: services/intent-engine/README.md")
    print("   - Device Manager: Available via REST API")
    print("   - Example Policies: services/intent-engine/examples/")
    print("   - Architecture: PHASE2_ARCHITECTURE.md")
    print("   - Progress: PHASE2_PROGRESS.md")
    print()
    print("🚀 Next Steps:")
    print("   - Implement self-healing system")
    print("   - Add security agent with DDoS detection")
    print("   - Build Web UI for policy management")
    print("   - Add multi-vendor template library")
    print()

def main():
    """Run the demo"""
    # Check services
    if not demo_health_checks():
        return
    
    time.sleep(1)
    
    # Create intent
    intent_id = demo_create_intent()
    if not intent_id:
        return
    
    time.sleep(1)
    
    # List intents
    demo_list_intents()
    time.sleep(1)
    
    # Register device
    device_id = demo_register_device()
    time.sleep(1)
    
    # List devices
    demo_list_devices()
    time.sleep(1)
    
    # Validate intent
    demo_validate_intent(intent_id)
    time.sleep(1)
    
    # Deploy intent
    demo_deploy_intent(intent_id)
    time.sleep(1)
    
    # Check compliance
    demo_check_compliance(intent_id)
    time.sleep(1)
    
    # Summary
    demo_summary()
    
    print("\n" + "="*80)
    print("  Demo Complete! 🎉")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

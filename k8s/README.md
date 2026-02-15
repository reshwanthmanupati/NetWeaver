# NetWeaver Kubernetes Deployment

Production-ready Kubernetes manifests for deploying NetWeaver to a Kubernetes cluster.

## Prerequisites

- Kubernetes cluster (v1.24+)
- kubectl configured
- Ingress controller (nginx recommended)
- StorageClass for PersistentVolumes
- Optional: cert-manager for TLS certificates

## Quick Start

### Deploy All Services

```bash
# Create namespace and apply all manifests
kubectl apply -f k8s/

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n netweaver --timeout=300s

# Check deployment status
kubectl get all -n netweaver
```

### Deploy Individual Components

```bash
# Deploy in order
kubectl apply -f k8s/00-namespace-and-config.yaml
kubectl apply -f k8s/01-timescaledb.yaml
kubectl apply -f k8s/02-rabbitmq.yaml
kubectl apply -f k8s/03-redis.yaml
kubectl apply -f k8s/04-intent-engine.yaml
kubectl apply -f k8s/05-device-manager.yaml
kubectl apply -f k8s/06-self-healing.yaml
kubectl apply -f k8s/07-security-agent.yaml
kubectl apply -f k8s/08-api-gateway.yaml
kubectl apply -f k8s/09-web-ui.yaml
kubectl apply -f k8s/10-ingress.yaml
```

## Architecture

### Services
- **TimescaleDB** (1 replica): PostgreSQL database with time-series support
- **RabbitMQ** (1 replica): Message broker for event-driven architecture
- **Redis** (1 replica): Cache and rate limiting backend
- **Intent Engine** (3-10 replicas): NLP intent processing
- **Device Manager** (3-10 replicas): Multi-vendor device management
- **Self-Healing** (2-5 replicas): Autonomous failure remediation
- **Security Agent** (2-5 replicas): DDoS detection and mitigation
- **API Gateway** (3-10 replicas): Unified API with authentication
- **Web UI** (2 replicas): React frontend

### Horizontal Pod Autoscaling

All microservices have HPA configured:
- **Intent Engine**: 3-10 replicas (70% CPU)
- **Device Manager**: 3-10 replicas (70% CPU)
- **Self-Healing**: 2-5 replicas (70% CPU)
- **Security Agent**: 2-5 replicas (70% CPU)
- **API Gateway**: 3-10 replicas (70% CPU)

### Storage

PersistentVolumeClaims:
- **TimescaleDB**: 10Gi
- **RabbitMQ**: 5Gi
- **Redis**: 2Gi

## Configuration

### Secrets

Update secrets in `00-namespace-and-config.yaml`:

```bash
# Generate secure passwords
kubectl create secret generic netweaver-secrets \
  --from-literal=DB_PASSWORD=$(openssl rand -base64 32) \
  --from-literal=RABBITMQ_PASS=$(openssl rand -base64 32) \
  --from-literal=JWT_SECRET_KEY=$(openssl rand -base64 32) \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -base64 32) \
  -n netweaver --dry-run=client -o yaml
```

### Resource Limits

Default resource limits per service:

| Service | Requests (CPU/Mem) | Limits (CPU/Mem) |
|---------|-------------------|------------------|
| Intent Engine | 100m / 256Mi | 500m / 512Mi |
| Device Manager | 100m / 256Mi | 500m / 512Mi |
| Self-Healing | 100m / 256Mi | 500m / 512Mi |
| Security Agent | 200m / 512Mi | 1000m / 1Gi |
| API Gateway | 100m / 256Mi | 500m / 512Mi |
| Web UI | 50m / 64Mi | 200m / 128Mi |

Adjust based on your workload.

### Ingress

Update the ingress in `10-ingress.yaml`:

```yaml
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: netweaver-tls
  rules:
  - host: your-domain.com
```

## Monitoring

### Check Pod Status

```bash
kubectl get pods -n netweaver
kubectl describe pod <pod-name> -n netweaver
kubectl logs <pod-name> -n netweaver
```

### Check Services

```bash
kubectl get svc -n netweaver
```

### Check HPA

```bash
kubectl get hpa -n netweaver
```

### Port Forwarding (Development)

```bash
# API Gateway
kubectl port-forward -n netweaver svc/api-gateway 8080:8080

# Web UI
kubectl port-forward -n netweaver svc/web-ui 3000:80

# RabbitMQ Management
kubectl port-forward -n netweaver svc/rabbitmq 15672:15672
```

## Scaling

### Manual Scaling

```bash
# Scale Intent Engine
kubectl scale deployment intent-engine -n netweaver --replicas=5

# Scale API Gateway
kubectl scale deployment api-gateway -n netweaver --replicas=10
```

### Update HPA

```bash
kubectl edit hpa intent-engine-hpa -n netweaver
```

## Maintenance

### Rolling Updates

```bash
# Update Intent Engine image
kubectl set image deployment/intent-engine \
  intent-engine=netweaver-intent-engine:v2.0 \
  -n netweaver

# Check rollout status
kubectl rollout status deployment/intent-engine -n netweaver

# Rollback if needed
kubectl rollout undo deployment/intent-engine -n netweaver
```

### Backup Database

```bash
# Backup TimescaleDB
kubectl exec -n netweaver timescaledb-<pod-id> -- \
  pg_dump -U netweaver netweaver > backup.sql
```

### Restore Database

```bash
# Restore TimescaleDB
kubectl exec -i -n netweaver timescaledb-<pod-id> -- \
  psql -U netweaver netweaver < backup.sql
```

## Troubleshooting

### Pods Not Starting

```bash
# Check events
kubectl get events -n netweaver --sort-by='.lastTimestamp'

# Check pod logs
kubectl logs <pod-name> -n netweaver --previous

# Describe pod
kubectl describe pod <pod-name> -n netweaver
```

### Database Connection Issues

```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15 \
  --restart=Never -n netweaver -- \
  psql -h timescaledb -U netweaver -d netweaver
```

### Service Discovery Issues

```bash
# Verify DNS
kubectl run -it --rm debug --image=busybox \
  --restart=Never -n netweaver -- \
  nslookup intent-engine
```

## Security

### Network Policies

```bash
# Apply network policies
kubectl apply -f k8s/network-policies/
```

### Pod Security Policies

```bash
# Apply pod security policies
kubectl apply -f k8s/psp/
```

### RBAC

```bash
# Create service account with limited permissions
kubectl apply -f k8s/rbac/
```

## Production Checklist

- [ ] Update all secrets with strong passwords
- [ ] Configure TLS/SSL certificates
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure log aggregation (ELK/Loki)
- [ ] Enable network policies
- [ ] Set up backup automation
- [ ] Configure resource quotas
- [ ] Enable pod security policies
- [ ] Set up alerts for critical services
- [ ] Configure external DNS
- [ ] Test disaster recovery procedures
- [ ] Document runbooks
- [ ] Set up CI/CD pipeline
- [ ] Configure service mesh (optional)

## Performance Tuning

### Database Tuning

```sql
-- Connect to TimescaleDB
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
SELECT pg_reload_conf();
```

### RabbitMQ Tuning

```bash
# Increase message limit
kubectl exec -n netweaver rabbitmq-<pod> -- \
  rabbitmqctl set_vm_memory_high_watermark 0.6
```

### Redis Tuning

```bash
# Update maxmemory policy
kubectl exec -n netweaver redis-<pod> -- \
  redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

## License

Copyright © 2026 NetWeaver Project

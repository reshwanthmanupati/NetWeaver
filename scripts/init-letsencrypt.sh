#!/bin/bash
# ============================================================================
# init-letsencrypt.sh - Obtain Let's Encrypt TLS certificates for NetWeaver
# ============================================================================
# Usage:
#   chmod +x init-letsencrypt.sh
#   ./init-letsencrypt.sh
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - Domain DNS pointing to this server
#   - Ports 80 and 443 open
# ============================================================================

set -e

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo "ERROR: .env file not found. Copy .env.production to .env first."
    echo "  cp .env.production .env"
    echo "  vim .env  # Set DOMAIN and CERTBOT_EMAIL"
    exit 1
fi

DOMAIN="${DOMAIN:-netweaver.example.com}"
EMAIL="${CERTBOT_EMAIL:-admin@example.com}"
COMPOSE_FILE="docker-compose-production.yml"

if [ "$DOMAIN" = "netweaver.example.com" ]; then
    echo "ERROR: Please set DOMAIN in .env file (not the default example.com)"
    exit 1
fi

echo "============================================"
echo "NetWeaver TLS Certificate Setup"
echo "============================================"
echo "Domain:  $DOMAIN"
echo "Email:   $EMAIL"
echo "============================================"
echo ""

# Step 1: Start nginx without TLS first
echo "[1/4] Starting nginx in HTTP-only mode..."

# Create a temporary nginx config for initial cert acquisition
cat > /tmp/nginx-certbot.conf << 'EOF'
events { worker_connections 1024; }
http {
    server {
        listen 80;
        server_name _;
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        location / {
            return 200 'NetWeaver - Waiting for TLS setup';
            add_header Content-Type text/plain;
        }
    }
}
EOF

docker-compose -f $COMPOSE_FILE up -d nginx

# Step 2: Request certificate
echo "[2/4] Requesting Let's Encrypt certificate..."
docker-compose -f $COMPOSE_FILE run --rm certbot certonly \
    --webroot \
    -w /var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal

# Step 3: Verify certificate
echo "[3/4] Verifying certificate..."
docker-compose -f $COMPOSE_FILE run --rm certbot certificates

# Step 4: Reload nginx with full TLS config
echo "[4/4] Reloading nginx with TLS configuration..."
docker-compose -f $COMPOSE_FILE exec nginx nginx -s reload

echo ""
echo "============================================"
echo "TLS setup complete!"
echo "============================================"
echo "Your site is now available at:"
echo "  https://$DOMAIN"
echo ""
echo "Certificate auto-renewal is configured via certbot container."
echo "To manually renew: docker-compose -f $COMPOSE_FILE run --rm certbot renew"
echo "============================================"

#!/bin/bash

# ============================================
#  Nginx + SSL Setup Script
#  For Rattle or any Flask app
#  Fixed: webroot fallback now works (nginx running),
#         port is configurable, modern http2 syntax,
#         HTTP-only fallback if SSL fails.
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[*]${NC} $1"; }
print_success() { echo -e "${GREEN}[+]${NC} $1"; }
print_error() { echo -e "${RED}[!]${NC} $1"; }

if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

clear
echo ""
echo "=========================================="
echo -e "${GREEN}Nginx + SSL Setup${NC}"
echo "=========================================="
echo ""

read -p "Enter your domain (e.g., rattle.yourdomain.com): " DOMAIN
if [ -z "$DOMAIN" ]; then
    print_error "Domain cannot be empty"
    exit 1
fi

read -p "Enter your email for Let's Encrypt: " EMAIL
if [ -z "$EMAIL" ]; then
    EMAIL="admin@$DOMAIN"
    print_status "Using: $EMAIL"
fi

read -p "Enter project path [~/rattle]: " PROJECT_PATH
if [ -z "$PROJECT_PATH" ]; then
    PROJECT_PATH="$HOME/rattle"
fi

read -p "Enter backend port nginx should proxy to [8000]: " BACKEND_PORT
if [ -z "$BACKEND_PORT" ]; then
    BACKEND_PORT=8000
fi

# ============================================
# Install Nginx & Certbot
# ============================================

print_status "Installing Nginx, Certbot, and python3-certbot-nginx..."
apt update -qq
apt install -y -qq nginx certbot python3-certbot-nginx
print_success "Nginx and Certbot installed"

# ============================================
# Configure Nginx (HTTP first; HTTPS block added after cert exists)
# ============================================

print_status "Configuring Nginx (HTTP stage)..."

cat > /etc/nginx/sites-available/rattle << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias $PROJECT_PATH/static/;
        expires 1y;
    }

    access_log /var/log/nginx/rattle_access.log;
    error_log /var/log/nginx/rattle_error.log;
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/rattle /etc/nginx/sites-enabled/
nginx -t
systemctl start nginx
systemctl enable nginx
print_success "Nginx running (HTTP stage)"

# ============================================
# Obtain SSL certificate (nginx running -> webroot works)
# ============================================

print_status "Obtaining SSL certificate..."
mkdir -p /var/www/html

if certbot certonly --webroot -w /var/www/html -d "$DOMAIN" \
    --email "$EMAIL" --agree-tos --no-eff-email --non-interactive; then
    print_success "SSL certificate obtained"
    CERT_OK=1
else
    print_error "Certificate failed. Check DNS and try again later."
    print_status "Leaving site on HTTP so it still works."
    CERT_OK=0
fi

if [ "$CERT_OK" -eq 1 ]; then
    print_status "Upgrading Nginx to HTTPS..."
    cat > /etc/nginx/sites-available/rattle << EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias $PROJECT_PATH/static/;
        expires 1y;
    }

    access_log /var/log/nginx/rattle_access.log;
    error_log /var/log/nginx/rattle_error.log;
}
EOF
    nginx -t
    systemctl reload nginx
    print_success "Nginx serving HTTPS"
fi

# ============================================
# Auto-renewal
# ============================================

systemctl enable certbot.timer
systemctl start certbot.timer
print_success "Auto-renewal enabled"

# ============================================
# Done
# ============================================

echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
if [ "$CERT_OK" -eq 1 ]; then
    echo "  Site:     https://$DOMAIN"
else
    echo "  Site:     http://$DOMAIN  (SSL failed - fix DNS and re-run)"
fi
echo "  Nginx:    /etc/nginx/sites-available/rattle"
echo "  Backend:  127.0.0.1:$BACKEND_PORT"
echo ""
echo "  Next steps:"
echo "  1. Update Google Cloud Console:"
echo "     - JavaScript origins:  https://$DOMAIN"
echo "     - Redirect URI:        https://$DOMAIN/callback"
echo ""
echo "  2. Run your Flask app:"
echo "     cd $PROJECT_PATH"
echo "     gunicorn -w 1 --threads 4 -b 127.0.0.1:$BACKEND_PORT app:app"
echo ""
echo "  SSL renews automatically via certbot.timer."
echo "=========================================="

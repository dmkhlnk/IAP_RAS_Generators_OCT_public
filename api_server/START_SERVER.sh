#!/bin/bash
# Script to start the API server with proper configuration

cd "$(dirname "$0")/.." || exit 1

echo "=========================================="
echo "Starting OCT Generators API Server"
echo "=========================================="

# Get server IP using multiple methods
SERVER_IP=""

# Method 1: hostname -I (Linux)
if command -v hostname >/dev/null 2>&1; then
    IPS=$(hostname -I 2>/dev/null)
    for ip in $IPS; do
        # Filter out localhost and invalid IPs (like 240.x.x.x multicast)
        if [[ ! "$ip" =~ ^127\. ]] && [[ ! "$ip" =~ ^240\. ]] && [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            SERVER_IP="$ip"
            break
        fi
    done
fi

# Method 2: ip addr show (Linux)
if [ -z "$SERVER_IP" ] && command -v ip >/dev/null 2>&1; then
    IP_OUTPUT=$(ip addr show 2>/dev/null | grep "inet " | grep -v "127.0.0.1" | head -1)
    if [ -n "$IP_OUTPUT" ]; then
        SERVER_IP=$(echo "$IP_OUTPUT" | awk '{print $2}' | cut -d/ -f1)
        # Filter out invalid IPs
        if [[ "$SERVER_IP" =~ ^240\. ]]; then
            SERVER_IP=""
        fi
    fi
fi

# Method 3: Python fallback
if [ -z "$SERVER_IP" ]; then
    SERVER_IP=$(python3 -c "
import socket
import subprocess
try:
    result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
    if result.returncode == 0:
        ips = result.stdout.strip().split()
        for ip in ips:
            if ip and not ip.startswith('127.') and not ip.startswith('240.'):
                print(ip)
                break
except:
    pass
" 2>/dev/null)
fi

if [ -n "$SERVER_IP" ]; then
    echo "Detected Server IP: $SERVER_IP"
else
    echo "⚠ Could not detect server IP automatically"
    echo "  Check with: hostname -I"
fi
echo ""

# Check for SSL certificates
SSL_KEYFILE=""
SSL_CERTFILE=""

if [ -f "api_server/server.key" ] && [ -f "api_server/server.crt" ]; then
    SSL_KEYFILE="api_server/server.key"
    SSL_CERTFILE="api_server/server.crt"
    echo "✓ SSL certificates found - HTTPS will be enabled"
    PROTOCOL="https"
else
    echo "⚠ SSL certificates not found - HTTP only"
    echo "  Generate certificates with: python3 api_server/generate_ssl_cert.py"
    PROTOCOL="http"
fi
echo ""

# Start server
cd api_server || exit 1

if [ -n "$SSL_KEYFILE" ] && [ -n "$SSL_CERTFILE" ]; then
    python3 api_server.py --host 0.0.0.0 --port 8000 --show-ip \
        --ssl-keyfile "../$SSL_KEYFILE" --ssl-certfile "../$SSL_CERTFILE"
else
    python3 api_server.py --host 0.0.0.0 --port 8000 --show-ip
fi


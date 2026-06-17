#!/usr/bin/env python3
"""
Generate self-signed SSL certificate for HTTPS

This script creates a self-signed SSL certificate for development/testing.
For production, use Let's Encrypt or a proper CA-signed certificate.
"""

import os
import subprocess
import sys
from pathlib import Path

# Get script directory
SCRIPT_DIR = Path(__file__).parent
CERT_DIR = SCRIPT_DIR
KEY_FILE = CERT_DIR / "server.key"
CERT_FILE = CERT_DIR / "server.crt"

def generate_certificate():
    """Generate self-signed SSL certificate"""
    
    # Check if OpenSSL is available
    try:
        subprocess.run(['openssl', 'version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: OpenSSL is not installed or not in PATH")
        print("Install OpenSSL:")
        print("  Ubuntu/Debian: sudo apt-get install openssl")
        print("  macOS: brew install openssl")
        sys.exit(1)
    
    # Check if certificate already exists
    if KEY_FILE.exists() and CERT_FILE.exists():
        response = input(f"Certificate files already exist. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Certificate generation cancelled.")
            return
    
    # Get server hostname/IP
    import socket
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "127.0.0.1"
    
    print(f"Generating SSL certificate for {hostname} ({ip})...")
    print(f"Certificate will be valid for 365 days.")
    print()
    
    # Generate private key
    print("Step 1: Generating private key...")
    subprocess.run([
        'openssl', 'genrsa',
        '-out', str(KEY_FILE),
        '2048'
    ], check=True)
    print(f"✓ Private key created: {KEY_FILE}")
    
    # Generate certificate signing request
    print("Step 2: Generating certificate signing request...")
    csr_file = CERT_DIR / "server.csr"
    subprocess.run([
        'openssl', 'req',
        '-new',
        '-key', str(KEY_FILE),
        '-out', str(csr_file),
        '-subj', f'/C=US/ST=State/L=City/O=OCT Generators/CN={hostname}'
    ], check=True)
    
    # Generate self-signed certificate
    print("Step 3: Generating self-signed certificate...")
    subprocess.run([
        'openssl', 'x509',
        '-req',
        '-days', '365',
        '-in', str(csr_file),
        '-signkey', str(KEY_FILE),
        '-out', str(CERT_FILE),
        '-extensions', 'v3_req',
        '-extfile', '-'
    ], input=f"""[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = {hostname}
DNS.2 = localhost
IP.1 = {ip}
IP.2 = 127.0.0.1
""".encode(), check=True)
    
    # Clean up CSR file
    if csr_file.exists():
        csr_file.unlink()
    
    # Set permissions
    os.chmod(KEY_FILE, 0o600)
    os.chmod(CERT_FILE, 0o644)
    
    print()
    print("="*60)
    print("SSL Certificate Generated Successfully!")
    print("="*60)
    print(f"Private Key: {KEY_FILE}")
    print(f"Certificate: {CERT_FILE}")
    print()
    print("To use HTTPS, start the server with:")
    print(f"  python3 api_server.py --ssl-keyfile {KEY_FILE} --ssl-certfile {CERT_FILE}")
    print()
    print("Or set environment variables:")
    print(f"  export SSL_KEYFILE={KEY_FILE}")
    print(f"  export SSL_CERTFILE={CERT_FILE}")
    print()
    print("NOTE: This is a self-signed certificate.")
    print("Browsers will show a security warning. Click 'Advanced' -> 'Proceed' to continue.")
    print("For production, use Let's Encrypt or a CA-signed certificate.")

if __name__ == "__main__":
    try:
        generate_certificate()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Certificate generation failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCertificate generation cancelled.")
        sys.exit(1)


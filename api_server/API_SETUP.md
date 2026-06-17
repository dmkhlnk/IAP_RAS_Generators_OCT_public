# API Server Setup Guide

This guide explains how to set up and run the OCT Generators API server on a dedicated server.

## Overview

The API server provides REST endpoints for:
1. **Virtual Scanner API** - Process .dat scatterer files and generate OCT scans
2. **Agent System API** - Run generator and validator agents (to be implemented)

## Prerequisites

- Python 3.9 or higher
- All dependencies from `requirements.txt` installed
- Configuration.ini file in the project directory
- API key configured (for agent endpoints, when implemented)

## Installation

### 1. Install Dependencies

After cloning the repository, navigate to the project root directory:

```bash
cd OCT_Generators_IAP_RAS
pip install -r requirements.txt
```

This will install FastAPI, uvicorn, and other required packages.

### 2. Verify Configuration

Make sure `Configuration.ini` exists in the project directory:

```bash
ls -la Configuration.ini
```

### 3. Test the Server Locally

Start the server in development mode:

```bash
python3 api_server.py --host 0.0.0.0 --port 8000 --reload
```

The server will be available at `http://localhost:8000`

### 4. Check Health Endpoint

```bash
curl http://localhost:8000/health
```

You should see:
```json
{
  "status": "healthy",
  "service": "OCT Generators API",
  "version": "1.0.0",
  "timestamp": "..."
}
```

## Production Deployment

### Option 1: Systemd Service (Recommended)

1. Copy the service file:

```bash
sudo cp api_server.service /etc/systemd/system/
```

2. Edit the service file if needed (update paths, user, etc.):

```bash
sudo nano /etc/systemd/system/api_server.service
```

3. Reload systemd and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable api_server
sudo systemctl start api_server
```

4. Check status:

```bash
sudo systemctl status api_server
```

5. View logs:

```bash
sudo journalctl -u api_server -f
```

### Option 2: Using Screen/Tmux

For temporary deployment:

```bash
screen -S api_server
python3 api_server.py --host 0.0.0.0 --port 8000
# Press Ctrl+A then D to detach
```

### Option 3: Using Nohup

```bash
nohup python3 api_server.py --host 0.0.0.0 --port 8000 > api_server.log 2>&1 &
```

## API Endpoints

### Health Check

```bash
GET /health
GET /
```

Returns server status.

### Virtual Scanner - Process Scatterers

```bash
POST /api/v1/scanner/process
Content-Type: multipart/form-data

Parameters:
- file: .dat file (required)
- config_file: Optional path to custom Configuration.ini
```

Example using curl:

```bash
curl -X POST "http://your-server:8000/api/v1/scanner/process" \
  -F "file=@path/to/scatterers.dat"
```

Response:

```json
{
  "status": "success",
  "session_id": "uuid-here",
  "input_file": "scatterers.dat",
  "images": {
    "grayscale": "/api/v1/scanner/download/{session_id}/grayscale",
    "hot": "/api/v1/scanner/download/{session_id}/hot"
  }
}
```

### Download Generated Scan

```bash
GET /api/v1/scanner/download/{session_id}/{image_type}
```

Where `image_type` is either `grayscale` or `hot`.

Example:

```bash
curl -O "http://your-server:8000/api/v1/scanner/download/{session_id}/grayscale"
```

### Agent Endpoints (To be implemented)

- `POST /api/v1/agents/generate` - Run generator agent
- `POST /api/v1/agents/validate` - Run validator agent

## Security Considerations

### 1. Firewall Configuration

Only allow necessary ports:

```bash
sudo ufw allow 8000/tcp
```

### 2. CORS Configuration

Edit `api_server.py` to restrict CORS origins in production:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # Restrict to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Authentication

Consider adding API key authentication for production use. You can use FastAPI's security features:

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    if api_key != "your-secret-key":
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key
```

### 4. Rate Limiting

Consider adding rate limiting to prevent abuse:

```bash
pip install slowapi
```

## Monitoring

### Check Server Status

```bash
curl http://localhost:8000/health
```

### View Logs

If using systemd:

```bash
sudo journalctl -u api_server -n 100
```

### Disk Space

Monitor the `api_temp` directory for temporary files:

```bash
du -sh api_temp/
```

Temporary files are automatically cleaned up after 24 hours, but you can manually clean:

```bash
find api_temp/ -type f -mtime +1 -delete
```

## Troubleshooting

### Server Won't Start

1. Check Python version: `python3 --version` (should be 3.9+)
2. Check dependencies: `pip list | grep fastapi`
3. Check logs: `journalctl -u api_server -n 50`

### Import Errors

Make sure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### Port Already in Use

Change the port:

```bash
python3 api_server.py --port 8001
```

Or find and kill the process using port 8000:

```bash
sudo lsof -i :8000
sudo kill -9 <PID>
```

### Configuration File Not Found

Make sure `Configuration.ini` exists in the project directory:

```bash
ls -la Configuration.ini
```

## Testing the API

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Process scatterers
curl -X POST "http://localhost:8000/api/v1/scanner/process" \
  -F "file=@test_scatterers.dat"

# Download result (replace {session_id} with actual ID from response)
curl -O "http://localhost:8000/api/v1/scanner/download/{session_id}/grayscale"
```

### Using Python

```python
import requests

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())

# Process scatterers
with open("scatterers.dat", "rb") as f:
    files = {"file": f}
    response = requests.post("http://localhost:8000/api/v1/scanner/process", files=files)
    result = response.json()
    print(result)

# Download scan
session_id = result["session_id"]
response = requests.get(f"http://localhost:8000/api/v1/scanner/download/{session_id}/grayscale")
with open("output_scan.png", "wb") as f:
    f.write(response.content)
```

## Next Steps

1. Implement agent endpoints (`/api/v1/agents/generate` and `/api/v1/agents/validate`)
2. Add authentication/authorization
3. Add rate limiting
4. Add request logging and monitoring
5. Set up reverse proxy (nginx) for production


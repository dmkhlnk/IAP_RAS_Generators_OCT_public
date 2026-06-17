#!/usr/bin/env python3
"""
API Server for OCT Generators System

This server provides REST API endpoints for:
1. Virtual Scanner - process .dat files and generate OCT scans
2. Agent System - run generator and validator agents

The server is designed to run on a dedicated server with a permanent IP address.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import uuid
import traceback
from datetime import datetime
from contextlib import asynccontextmanager

# Add current directory and parent directory to path for imports
CURRENT_DIR = Path(__file__).parent  # api_server directory
PARENT_DIR = CURRENT_DIR.parent  # Root of repository
sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(PARENT_DIR))

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends, Form, Request
    from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.security import HTTPBasic, HTTPBasicCredentials
    from starlette.middleware.sessions import SessionMiddleware
    import secrets
    import uvicorn
except ImportError:
    print("ERROR: FastAPI and uvicorn are required. Install with: pip install fastapi uvicorn python-multipart starlette")
    sys.exit(1)

# Import virtual scanner (from parent directory)
try:
    from virtual_scanner import run_oct_simulation
except ImportError:
    print(f"ERROR: Could not import virtual_scanner. Make sure virtual_scanner.py is in {PARENT_DIR}")
    sys.exit(1)

# Import API key loader
try:
    from load_api_key import get_api_key, require_api_key
except ImportError:
    print("WARNING: Could not import load_api_key. API key validation will be skipped.")
    get_api_key = None
    require_api_key = None

# Configuration
BASE_DIR = Path(__file__).parent  # api_server directory
PARENT_DIR = BASE_DIR.parent  # Root of repository
CONFIG_FILE = PARENT_DIR / "Configuration.ini"  # Config in root directory
# Output directory for scans - visible in repository root
OUTPUT_DIR = PARENT_DIR / "api_scans"
OUTPUT_DIR.mkdir(exist_ok=True)
# Temporary directory for session data (cleaned up after 1 hour)
TEMP_DIR = BASE_DIR / "api_temp"
TEMP_DIR.mkdir(exist_ok=True)
# GUI files are now in the same directory as api_server.py
STATIC_DIR = BASE_DIR  # Files are in api_server/ directory

# Authentication configuration
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Load credentials from .env file
def load_auth_credentials():
    """Load admin username and password from .env file"""
    global ADMIN_USERNAME, ADMIN_PASSWORD
    env_file = PARENT_DIR / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('ADMIN_USERNAME='):
                        ADMIN_USERNAME = line.split('=', 1)[1].strip().strip('"').strip("'")
                    elif line.startswith('ADMIN_PASSWORD='):
                        ADMIN_PASSWORD = line.split('=', 1)[1].strip().strip('"').strip("'")
        except Exception as e:
            print(f"[AUTH WARNING] Error reading .env file: {e}")
    
    # If password is not set, generate a random one
    if not ADMIN_PASSWORD:
        import random
        import string
        ADMIN_PASSWORD = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        print(f"[AUTH] Generated random password: {ADMIN_PASSWORD}")
        print(f"[AUTH] Set ADMIN_PASSWORD in .env file to use a custom password")

# Load credentials on startup
load_auth_credentials()

# Session secret key (for session cookies)
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", secrets.token_urlsafe(32))

# Cleanup old temp files (older than 24 hours)
def cleanup_old_files():
    """Remove temporary files older than 24 hours"""
    if not TEMP_DIR.exists():
        return
    now = datetime.now().timestamp()
    for item in TEMP_DIR.iterdir():
        if item.is_file():
            try:
                if (now - item.stat().st_mtime) > 86400:  # 24 hours
                    item.unlink()
            except Exception:
                pass
        elif item.is_dir():
            try:
                if (now - item.stat().st_mtime) > 86400:  # 24 hours
                    shutil.rmtree(item)
            except Exception:
                pass

# Setup API key on startup (called before server starts)
def setup_api_key_on_startup(interactive=True):
    """Setup API key interactively if not found - called before server starts
    
    Args:
        interactive: If True, prompt user for API key if not found. If False, only check existing keys.
    """
    env_file = PARENT_DIR / ".env"
    
    # Check if API key already exists in .env file
    api_key_from_env = None
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('GEMINI_API_KEY=') or line.startswith('GOOGLE_API_KEY='):
                        api_key_from_env = line.split('=', 1)[1].strip()
                        # Remove quotes if present
                        if api_key_from_env.startswith('"') and api_key_from_env.endswith('"'):
                            api_key_from_env = api_key_from_env[1:-1]
                        if api_key_from_env.startswith("'") and api_key_from_env.endswith("'"):
                            api_key_from_env = api_key_from_env[1:-1]
                        if api_key_from_env:  # Make sure it's not empty
                            break
        except Exception as e:
            if interactive:
                print(f"[DEBUG] Error reading .env file: {e}")
    
    # Also check if load_api_key module is available and can get key
    if get_api_key is not None:
        try:
            api_key_from_module = get_api_key()
            if api_key_from_module:
                if interactive:
                    print("\n[API] API key found and configured.")
                return True
        except Exception:
            pass
    
    # If key exists in .env, use it
    if api_key_from_env:
        if interactive:
            print("\n[API] API key found in .env file.")
        os.environ['GEMINI_API_KEY'] = api_key_from_env
        return True
    
    # If not interactive, just return False (key not found)
    if not interactive:
        return False
    
    # Request API key from user
    print("\n" + "="*60)
    print("API Key Required")
    print("="*60)
    print("The API server requires a Gemini API key to function.")
    print("You can get one from: https://aistudio.google.com/app/apikey")
    print()
    
    if get_api_key is None:
        print("Note: load_api_key module not found, but you can still set the API key.")
        print("It will be saved to .env file for future use.")
        print()
    
    while True:
        try:
            api_key = input("Please enter your Gemini API key (or press Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nWARNING: API key input cancelled. Some features may not work.")
            print("You can set it later by creating a .env file in the project root.")
            print("="*60 + "\n")
            return False
        
        if not api_key:
            print("WARNING: No API key provided. Some features may not work.")
            print("You can set it later by creating a .env file in the project root.")
            print("="*60 + "\n")
            return False
        
        if len(api_key) < 20:
            print("ERROR: API key seems too short. Please check and try again.")
            continue
        
        # Save to .env file
        env_file = PARENT_DIR / ".env"
        env_example = PARENT_DIR / "env.example"
        
        # Create .env from example if it doesn't exist
        if not env_file.exists() and env_example.exists():
            with open(env_example, 'r') as f:
                env_content = f.read()
            with open(env_file, 'w') as f:
                f.write(env_content)
        
        # Update or add GEMINI_API_KEY
        if env_file.exists():
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            # Update existing key or add new one
            updated = False
            with open(env_file, 'w') as f:
                for line in lines:
                    if line.strip().startswith('GEMINI_API_KEY=') or line.strip().startswith('GOOGLE_API_KEY='):
                        f.write(f'GEMINI_API_KEY={api_key}\n')
                        updated = True
                    else:
                        f.write(line)
                
                if not updated:
                    f.write(f'\nGEMINI_API_KEY={api_key}\n')
        else:
            # Create new .env file
            with open(env_file, 'w') as f:
                f.write(f'GEMINI_API_KEY={api_key}\n')
        
        # Set environment variable for current session
        os.environ['GEMINI_API_KEY'] = api_key
        
        print(f"API key saved to {env_file}")
        print("="*60 + "\n")
        return True

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    cleanup_old_files()
    print(f"[API] Server started. Temp directory: {TEMP_DIR}")
    if not CONFIG_FILE.exists():
        print(f"[API WARNING] Configuration file not found: {CONFIG_FILE}")
    
    yield
    
    # Shutdown (if needed in future)
    pass

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="OCT Generators API",
    description="API server for Virtual Scanner and Agent System",
    version="1.0.0",
    lifespan=lifespan
)

# Session middleware (for authentication)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=86400 * 7,  # 7 days
    same_site="lax"
)

# CORS middleware (allow all origins for development, restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication dependency
def check_auth(request: Request):
    """Check if user is authenticated"""
    if not AUTH_ENABLED:
        return True
    
    session = request.session
    if session.get("authenticated"):
        return True
    
    return False

async def require_auth(request: Request):
    """Dependency to require authentication"""
    if not AUTH_ENABLED:
        return True
    
    session = request.session
    if not session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return True

# Authentication endpoints
@app.post("/api/auth/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Login endpoint - authenticate user"""
    if not AUTH_ENABLED:
        return JSONResponse(content={"status": "success", "message": "Authentication disabled"})
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["authenticated"] = True
        request.session["username"] = username
        return JSONResponse(content={"status": "success", "message": "Login successful"})
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

@app.post("/api/auth/logout")
async def logout(request: Request):
    """Logout endpoint"""
    request.session.clear()
    return JSONResponse(content={"status": "success", "message": "Logged out"})

@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check authentication status"""
    if not AUTH_ENABLED:
        return JSONResponse(content={"authenticated": True, "auth_enabled": False})
    
    is_authenticated = request.session.get("authenticated", False)
    return JSONResponse(content={
        "authenticated": is_authenticated,
        "auth_enabled": True,
        "username": request.session.get("username") if is_authenticated else None
    })

# Health check endpoint (define before static files mount)
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "OCT Generators API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

# Main GUI page (define before static files mount)
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main GUI page with authentication check"""
    # Check authentication if enabled
    if AUTH_ENABLED and not request.session.get("authenticated"):
        # Return login page
        return get_login_page()
    
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        with open(html_file, 'r', encoding='utf-8') as f:
            return f.read()
    # Fallback if GUI not available
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OCT Generators API</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #667eea; }
            a { color: #667eea; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>OCT Generators API</h1>
        <p>API is running. GUI is not available.</p>
        <p><a href="/docs">API Documentation (Swagger UI)</a></p>
        <p><a href="/health">Health Check</a></p>
    </body>
    </html>
    """

def get_login_page():
    """Return HTML login page"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OCT Generators - Login</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .login-container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                max-width: 400px;
                width: 100%;
            }
            .login-header {
                text-align: center;
                margin-bottom: 30px;
            }
            .login-header h1 {
                color: #667eea;
                font-size: 2em;
                margin-bottom: 10px;
            }
            .login-header p {
                color: #666;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 500;
            }
            .form-group input {
                width: 100%;
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 1em;
                transition: border-color 0.3s;
            }
            .form-group input:focus {
                outline: none;
                border-color: #667eea;
            }
            .login-button {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 1.1em;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s;
            }
            .login-button:hover {
                transform: scale(1.02);
            }
            .error-message {
                background: #f8d7da;
                color: #721c24;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 20px;
                display: none;
            }
            .error-message.show {
                display: block;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="login-header">
                <h1>OCT Generators</h1>
                <p>Virtual Scanner Access</p>
            </div>
            <div class="error-message" id="errorMessage"></div>
            <form id="loginForm">
                <div class="form-group">
                    <label for="username">Username</label>
                    <input type="text" id="username" name="username" required autocomplete="username">
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" required autocomplete="current-password">
                </div>
                <button type="submit" class="login-button">Login</button>
            </form>
        </div>
        <script>
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const errorDiv = document.getElementById('errorMessage');
                
                try {
                    const response = await fetch('/api/auth/login', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        window.location.href = '/';
                    } else {
                        errorDiv.textContent = data.detail || 'Login failed';
                        errorDiv.classList.add('show');
                    }
                } catch (error) {
                    errorDiv.textContent = 'Network error. Please try again.';
                    errorDiv.classList.add('show');
                }
            });
        </script>
    </body>
    </html>
    """

# Mount static files directory for GUI (CSS, JS files in api_server/)
# Static files are accessible without authentication
# This must be after route definitions to avoid conflicts
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Virtual Scanner API
@app.post("/api/v1/scanner/process")
async def process_scatterers(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    config_file: Optional[str] = None,
    _: bool = Depends(require_auth)
):
    """
    Process a scatterers .dat file and generate OCT scans.
    
    Args:
        file: Uploaded .dat file with scatterers data
        config_file: Optional path to custom Configuration.ini (uses default if not provided)
    
    Returns:
        JSON with download links to generated OCT scan images
    """
    # Validate file
    if not file.filename.endswith('.dat'):
        raise HTTPException(status_code=400, detail="File must be a .dat file")
    
    # Create unique session directory
    session_id = str(uuid.uuid4())
    session_dir = TEMP_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    
    try:
        # Save uploaded file
        input_file = session_dir / file.filename
        with open(input_file, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Use provided config or default
        config_path = config_file if config_file and Path(config_file).exists() else str(CONFIG_FILE)
        if not Path(config_path).exists():
            raise HTTPException(status_code=400, detail=f"Configuration file not found: {config_path}")
        
        # Run virtual scanner - save to visible output directory
        output_dir = OUTPUT_DIR / session_id
        output_dir.mkdir(exist_ok=True)
        
        # Also keep a copy in session_dir for download endpoint
        session_output_dir = session_dir / "output"
        session_output_dir.mkdir(exist_ok=True)
        
        print(f"[API] Processing scatterers file: {file.filename} (session: {session_id})")
        print(f"[API] Output directory: {output_dir}")
        
        run_oct_simulation(
            scatterers_file=str(input_file),
            output_dir=str(output_dir),
            config_template=config_path
        )
        
        # Copy results to session directory for download endpoint
        for png_file in output_dir.glob("*.png"):
            shutil.copy2(png_file, session_output_dir / png_file.name)
        
        # Find generated images
        grayscale_file = None
        hot_file = None
        
        base_name = Path(file.filename).stem
        for pattern in [f"{base_name}_grayscale.png", f"{base_name}_hot.png"]:
            candidate = output_dir / pattern
            if candidate.exists():
                if "grayscale" in pattern:
                    grayscale_file = candidate
                else:
                    hot_file = candidate
        
        if not grayscale_file and not hot_file:
            # Try to find any PNG files
            png_files = list(output_dir.glob("*.png"))
            if png_files:
                grayscale_file = png_files[0]
        
        if not grayscale_file and not hot_file:
            raise HTTPException(status_code=500, detail="No OCT scan images were generated")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_session, session_dir)
        
        # Return download links
        result = {
            "status": "success",
            "session_id": session_id,
            "input_file": file.filename,
            "images": {}
        }
        
        if grayscale_file:
            result["images"]["grayscale"] = f"/api/v1/scanner/download/{session_id}/grayscale"
        if hot_file:
            result["images"]["hot"] = f"/api/v1/scanner/download/{session_id}/hot"
        
        return JSONResponse(content=result)
    
    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on error
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
        error_msg = f"Error processing scatterers file: {str(e)}"
        print(f"[API ERROR] {error_msg}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/api/v1/scanner/download/{session_id}/{image_type}")
async def download_scan(
    request: Request,
    session_id: str,
    image_type: str,
    _: bool = Depends(require_auth)
):
    """
    Download generated OCT scan image.
    
    Args:
        session_id: Session ID from process_scatterers response
        image_type: Either 'grayscale' or 'hot'
    """
    if image_type not in ['grayscale', 'hot']:
        raise HTTPException(status_code=400, detail="image_type must be 'grayscale' or 'hot'")
    
    session_dir = TEMP_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    # Find the image file
    output_dir = session_dir / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")
    
    # Look for the image
    pattern = f"*_grayscale.png" if image_type == "grayscale" else f"*_hot.png"
    image_files = list(output_dir.glob(pattern))
    
    if not image_files:
        raise HTTPException(status_code=404, detail=f"{image_type} image not found")
    
    image_file = image_files[0]
    return FileResponse(
        path=str(image_file),
        media_type="image/png",
        filename=image_file.name
    )

def cleanup_session(session_dir: Path):
    """Clean up session directory after delay"""
    import time
    time.sleep(3600)  # Wait 1 hour before cleanup
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
        print(f"[API] Cleaned up session: {session_dir.name}")

# Agent System API (placeholder for future implementation)
@app.post("/api/v1/agents/generate")
async def agent_generate(request: Dict[str, Any]):
    """
    Run generator agent to create new configuration.
    
    This endpoint will be implemented to call the generator agent.
    """
    return JSONResponse(content={
        "status": "not_implemented",
        "message": "Agent API will be implemented in the next phase"
    })

@app.post("/api/v1/agents/validate")
async def agent_validate(request: Dict[str, Any]):
    """
    Run validator agent to validate OCT scans.
    
    This endpoint will be implemented to call the validator agent.
    """
    return JSONResponse(content={
        "status": "not_implemented",
        "message": "Agent API will be implemented in the next phase"
    })

def get_server_ip():
    """Get the server's IP address for remote access"""
    import socket
    import subprocess
    
    # Method 1: Try using hostname -I (Linux) - most reliable
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2, check=False)
        if result.returncode == 0 and result.stdout:
            ips = result.stdout.strip().split()
            # Filter out localhost and invalid IPs (like 240.x.x.x multicast)
            for ip in ips:
                ip = ip.strip()
                if ip and not ip.startswith('127.') and not ip.startswith('240.'):
                    # Check if it's a valid IP format
                    parts = ip.split('.')
                    if len(parts) == 4:
                        try:
                            # Validate all parts are numbers
                            all_numeric = all(p.isdigit() for p in parts)
                            if all_numeric:
                                first_octet = int(parts[0])
                                # Valid IP ranges: 1-223 (excluding 127, 169, 224-239)
                                if 1 <= first_octet <= 223 and first_octet != 127 and first_octet != 169:
                                    return ip
                        except (ValueError, IndexError):
                            continue
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        # Silently continue to next method
        pass
    
    # Method 2: Try using socket connection to external address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        try:
            # Connect to Google DNS to determine local IP
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            # Filter out invalid IPs
            if ip and not ip.startswith('127.') and not ip.startswith('240.'):
                parts = ip.split('.')
                if len(parts) == 4:
                    try:
                        first_octet = int(parts[0])
                        if 1 <= first_octet <= 223 and first_octet != 127 and first_octet != 169:
                            return ip
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
    except Exception:
        pass
    
    # Method 3: Try parsing ip addr output (Linux)
    try:
        result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=2, check=False)
        if result.returncode == 0 and result.stdout:
            import re
            # Look for inet addresses that are not localhost
            pattern = r'inet\s+(\d+\.\d+\.\d+\.\d+)/\d+'
            matches = re.findall(pattern, result.stdout)
            for ip in matches:
                if not ip.startswith('127.') and not ip.startswith('240.'):
                    parts = ip.split('.')
                    if len(parts) == 4:
                        try:
                            first_octet = int(parts[0])
                            if 1 <= first_octet <= 223 and first_octet != 127 and first_octet != 169:
                                return ip
                        except (ValueError, IndexError):
                            continue
    except Exception:
        pass
    
    # Fallback: return None if no valid IP found (will show localhost only)
    return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OCT Generators API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0 - all interfaces, use 127.0.0.1 for localhost only)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--skip-api-key", action="store_true", help="Skip interactive API key setup")
    parser.add_argument("--show-ip", action="store_true", help="Show server IP address for remote access")
    parser.add_argument("--ssl-keyfile", type=str, help="Path to SSL private key file (for HTTPS)")
    parser.add_argument("--ssl-certfile", type=str, help="Path to SSL certificate file (for HTTPS)")
    args = parser.parse_args()
    
    # Request API key interactively if not found (before server starts)
    if not args.skip_api_key:
        setup_api_key_on_startup(interactive=True)
    
    # Show server information
    server_ip = get_server_ip()
    
    # If IP detection failed, try one more time with direct command
    if not server_ip:
        try:
            import subprocess
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout:
                ips = result.stdout.strip().split()
                for ip in ips:
                    ip = ip.strip()
                    if ip and not ip.startswith('127.') and not ip.startswith('240.'):
                        parts = ip.split('.')
                        if len(parts) == 4 and all(p.isdigit() for p in parts):
                            first_octet = int(parts[0])
                            if 1 <= first_octet <= 223 and first_octet != 127 and first_octet != 169:
                                server_ip = ip
                                break
        except Exception:
            pass
    
    print(f"\n{'='*60}")
    print(f"[API] Starting server on {args.host}:{args.port}")
    print(f"{'='*60}")
    
    if args.host == "0.0.0.0":
        print(f"[API] Server is accessible from:")
        print(f"  - Localhost:     http://127.0.0.1:{args.port}")
        print(f"  - Localhost:     http://localhost:{args.port}")
        if server_ip and server_ip != "127.0.0.1":
            print(f"  - Remote access: http://{server_ip}:{args.port}")
            print(f"\n[API] ⚠ IMPORTANT: Use this IP for remote access: {server_ip}")
        else:
            # Try to get IP one more time and show it
            try:
                import subprocess
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    all_ips = result.stdout.strip()
                    print(f"  - Remote access: Detecting IP...")
                    # Extract first valid IP
                    for ip in all_ips.split():
                        ip = ip.strip()
                        if ip and not ip.startswith('127.') and not ip.startswith('240.'):
                            parts = ip.split('.')
                            if len(parts) == 4 and all(p.isdigit() for p in parts):
                                first_octet = int(parts[0])
                                if 1 <= first_octet <= 223 and first_octet != 127 and first_octet != 169:
                                    print(f"  - Remote access: http://{ip}:{args.port}")
                                    print(f"\n[API] ⚠ IMPORTANT: Use this IP for remote access: {ip}")
                                    server_ip = ip  # Update for later use
                                    break
                    if not server_ip:
                        print(f"  - Remote access: Check IP with: hostname -I")
            except Exception:
                print(f"  - Remote access: Check IP with: hostname -I")
        print(f"  - All interfaces: http://0.0.0.0:{args.port}")
    elif args.host == "127.0.0.1":
        print(f"[API] Server is accessible only from localhost:")
        print(f"  - http://127.0.0.1:{args.port}")
        print(f"  - http://localhost:{args.port}")
    else:
        print(f"[API] Server is accessible at:")
        print(f"  - http://{args.host}:{args.port}")
    
    if args.show_ip:
        if server_ip:
            print(f"\n[API] Server IP address: {server_ip}")
        else:
            print(f"\n[API] Server IP address: Could not detect (check with: hostname -I)")
            # Try to get IP using hostname -I as fallback
            try:
                import subprocess
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    ips = result.stdout.strip().split()
                    valid_ips = [ip for ip in ips if ip and not ip.startswith('127.') and not ip.startswith('240.')]
                    if valid_ips:
                        print(f"[API] Detected IPs: {', '.join(valid_ips)}")
            except Exception:
                pass
    
    print(f"{'='*60}\n")
    
    # SSL configuration
    ssl_keyfile = args.ssl_keyfile or os.getenv("SSL_KEYFILE")
    ssl_certfile = args.ssl_certfile or os.getenv("SSL_CERTFILE")
    
    if ssl_keyfile and ssl_certfile:
        if not Path(ssl_keyfile).exists() or not Path(ssl_certfile).exists():
            print(f"[SSL ERROR] SSL certificate files not found!")
            print(f"  Key file: {ssl_keyfile}")
            print(f"  Cert file: {ssl_certfile}")
            print(f"  Run: python3 {BASE_DIR}/generate_ssl_cert.py")
            sys.exit(1)
        print(f"[SSL] HTTPS enabled")
        print(f"  Key: {ssl_keyfile}")
        print(f"  Cert: {ssl_certfile}")
        protocol = "https"
    else:
        protocol = "http"
        print(f"[SSL] HTTPS not enabled (use --ssl-keyfile and --ssl-certfile)")
    
    # Update server URLs to use correct protocol
    if args.host == "0.0.0.0":
        if server_ip and server_ip != "127.0.0.1":
            print(f"\n[API] Remote access URL: {protocol}://{server_ip}:{args.port}")
    
    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile
    )


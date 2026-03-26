"""
Mobile Camera Server for myBay

FastAPI server that:
1. Serves a mobile-optimized camera interface
2. Accepts photo uploads from the user's phone
3. Broadcasts new photos via WebSocket for real-time desktop updates
4. Generates QR codes for easy phone access

Run with: python -m server.main
Or: uvicorn server.main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import uuid
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

from core.paths import get_queue_dir
QUEUE_DIR = get_queue_dir()

STATIC_DIR.mkdir(exist_ok=True)

# Create the FastAPI app
app = FastAPI(
    title="myBay - Camera Server",
    description="Mobile camera interface for product photo uploads",
    version="1.0.0"
)

# Enable CORS for local network access.
# allow_origins=["*"] is required because the phone IP is dynamic on the LAN.
# This is acceptable since the server only runs on the local network.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # Only the methods we actually use
    allow_headers=["*"],
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"📱 New connection. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"📱 Connection closed. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()


# ============================================================================
# Utility Functions
# ============================================================================

def get_local_ip() -> str:
    """Get the local IP address for network access."""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_image_id() -> str:
    """Generate a unique image ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}"


# ============================================================================
# API Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to camera page."""
    return """
    <html>
        <head>
            <meta http-equiv="refresh" content="0; url=/camera" />
        </head>
        <body>
            <p>Redirecting to <a href="/camera">camera</a>...</p>
        </body>
    </html>
    """


@app.get("/camera", response_class=HTMLResponse)
async def camera_page():
    """Serve the mobile camera interface."""
    camera_html = TEMPLATES_DIR / "camera.html"
    if camera_html.exists():
        return HTMLResponse(content=camera_html.read_text())
    else:
        return HTMLResponse(content="<h1>Camera template not found</h1>", status_code=404)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "server": "myBay Camera Server",
        "local_ip": get_local_ip(),
        "queue_dir": str(QUEUE_DIR),
        "pending_images": len(list(QUEUE_DIR.glob("*.jpg"))) + len(list(QUEUE_DIR.glob("*.png")))
    }


@app.get("/info")
async def server_info():
    """Get server info for desktop app."""
    local_ip = get_local_ip()
    return {
        "local_ip": local_ip,
        "port": 8000,
        "camera_url": f"http://{local_ip}:8000/camera",
        "upload_url": f"http://{local_ip}:8000/upload",
        "websocket_url": f"ws://{local_ip}:8000/ws",
    }


@app.post("/upload")
async def upload_images(files: list[UploadFile] = File(...)):
    """
    Accept image uploads from the mobile camera.
    
    Returns the image IDs and file paths for processing.
    """
    if not files:
        return JSONResponse(
            status_code=400,
            content={"error": "No files uploaded"}
        )
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file

    uploaded = []
    batch_id = generate_image_id()

    for i, file in enumerate(files):
        if not file.content_type or not file.content_type.startswith("image/"):
            continue

        # Generate unique filename
        ext = Path(file.filename or "image.jpg").suffix or ".jpg"
        image_id = f"{batch_id}_{i+1:02d}"
        filename = f"{image_id}{ext}"
        filepath = QUEUE_DIR / filename

        # Save the file
        try:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                print(f"⚠️ Rejected {file.filename}: {len(content):,} bytes exceeds 50 MB limit")
                continue
            with open(filepath, "wb") as f:
                f.write(content)
            
            uploaded.append({
                "image_id": image_id,
                "filename": filename,
                "path": str(filepath),
                "size_bytes": len(content),
            })
            
            print(f"📸 Saved: {filename} ({len(content):,} bytes)")
            
        except Exception as e:
            print(f"❌ Error saving {file.filename}: {e}")
    
    if not uploaded:
        return JSONResponse(
            status_code=400,
            content={"error": "No valid images uploaded"}
        )
    
    # Broadcast to connected desktop clients
    await manager.broadcast({
        "type": "new_images",
        "batch_id": batch_id,
        "images": uploaded,
        "timestamp": datetime.now().isoformat(),
    })
    
    return {
        "success": True,
        "batch_id": batch_id,
        "images": uploaded,
        "message": f"Uploaded {len(uploaded)} image(s) successfully!"
    }


@app.get("/queue")
async def list_queue():
    """List all images in the queue directory."""
    images = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
        for path in QUEUE_DIR.glob(ext):
            images.append({
                "filename": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            })
    
    # Sort by modification time, newest first
    images.sort(key=lambda x: x["modified"], reverse=True)
    
    return {
        "queue_dir": str(QUEUE_DIR),
        "count": len(images),
        "images": images
    }


@app.delete("/queue/{filename}")
async def delete_from_queue(filename: str):
    """Delete an image from the queue."""
    filepath = QUEUE_DIR / filename
    if filepath.exists() and filepath.parent == QUEUE_DIR:
        filepath.unlink()
        return {"success": True, "deleted": filename}
    return JSONResponse(
        status_code=404,
        content={"error": f"File not found: {filename}"}
    )


@app.get("/queue/{filename}")
async def get_queue_image(filename: str):
    """Serve an image from the queue."""
    filepath = QUEUE_DIR / filename
    if filepath.exists() and filepath.parent == QUEUE_DIR:
        return FileResponse(filepath)
    return JSONResponse(
        status_code=404,
        content={"error": f"File not found: {filename}"}
    )


# ============================================================================
# WebSocket for Real-Time Updates
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time communication.
    
    Desktop app connects here to receive notifications when new photos arrive.
    """
    await manager.connect(websocket)
    
    # Send initial connection message
    await websocket.send_json({
        "type": "connected",
        "message": "Connected to myBay server",
        "server_info": {
            "local_ip": get_local_ip(),
            "queue_dir": str(QUEUE_DIR),
        }
    })
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
                elif message.get("type") == "get_queue":
                    # Send current queue status
                    images = []
                    for ext in ["*.jpg", "*.jpeg", "*.png"]:
                        images.extend([p.name for p in QUEUE_DIR.glob(ext)])
                    await websocket.send_json({
                        "type": "queue_status",
                        "images": images,
                        "count": len(images)
                    })
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================================
# QR Code Generation
# ============================================================================

@app.get("/qr")
async def get_qr_code():
    """Generate and return a QR code for the camera URL."""
    try:
        import qrcode
        import io
        
        local_ip = get_local_ip()
        camera_url = f"http://{local_ip}:8000/camera"
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(camera_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(img_bytes, media_type="image/png")
        
    except ImportError:
        return JSONResponse(
            status_code=500,
            content={"error": "qrcode library not installed"}
        )


@app.get("/qr/data")
async def get_qr_data():
    """Get the data needed to generate a QR code client-side."""
    local_ip = get_local_ip()
    return {
        "camera_url": f"http://{local_ip}:8000/camera",
        "local_ip": local_ip,
        "port": 8000
    }


# ============================================================================
# eBay OAuth Callback
# ============================================================================

@app.get("/ebay/callback", response_class=HTMLResponse)
async def ebay_oauth_callback(request: Request):
    """
    Handle OAuth callback from eBay after user authorization.
    
    eBay redirects here with an authorization code that we exchange for tokens.
    """
    # Get query parameters
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description", "Authorization was declined")
    
    # Common styles for all pages
    base_style = """
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; margin: 0; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        }
        .container {
            text-align: center; padding: 50px;
            background: white; border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            max-width: 500px;
        }
        .logo { font-size: 48px; margin-bottom: 10px; }
        .app-name { font-size: 24px; font-weight: bold; color: #1a1a2e; margin-bottom: 30px; }
        h1 { margin-bottom: 16px; }
        p { color: #666; line-height: 1.6; }
        .btn {
            display: inline-block; padding: 12px 24px; margin-top: 20px;
            background: #1a1a2e; color: white; text-decoration: none;
            border-radius: 8px; font-weight: 500;
        }
        .btn:hover { background: #16213e; }
    """
    close_script = """
        <script>
            function closeWindow() {
                try { window.open('', '_self'); } catch (e) {}
                try { window.close(); } catch (e) {}
                setTimeout(function () {
                    document.body.innerHTML = `
                        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                                    display:flex;justify-content:center;align-items:center;min-height:100vh;
                                    margin:0;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);">
                            <div style="text-align:center;padding:36px;background:#fff;border-radius:14px;max-width:520px;">
                                <h2 style="margin:0 0 12px 0;color:#111827;">Return To myBay</h2>
                                <p style="color:#6b7280;margin:0 0 14px 0;">You can now close this browser tab.</p>
                            </div>
                        </div>
                    `;
                }, 250);
            }
            // Auto-close shortly after success/error page renders.
            window.addEventListener('load', function () {
                setTimeout(closeWindow, 1800);
            });
        </script>
    """
    
    if error:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>myBay - Authorization Declined</title>
            <style>
                {base_style}
                h1 {{ color: #c00; }}
                .error {{ background: #fee; padding: 16px; border-radius: 8px; margin: 20px 0; text-align: left; }}
            </style>
            {close_script}
        </head>
        <body>
            <div class="container">
                <div class="logo">📦</div>
                <div class="app-name">myBay</div>
                <h1>Authorization Declined</h1>
                <div class="error">
                    <strong>Error:</strong> {error}<br>
                    <strong>Details:</strong> {error_description}
                </div>
                <p>You can close this window and try again from the app.</p>
                <a href="#" onclick="closeWindow(); return false;" class="btn">Close Window</a>
            </div>
        </body>
        </html>
        """, status_code=400)
    
    if not code:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>myBay - Missing Code</title>
            <style>
                {base_style}
                h1 {{ color: #f59e0b; }}
            </style>
            {close_script}
        </head>
        <body>
            <div class="container">
                <div class="logo">📦</div>
                <div class="app-name">myBay</div>
                <h1>⚠️ Missing Authorization Code</h1>
                <p>No authorization code was received from eBay.</p>
                <p>Please try connecting again from the app.</p>
                <a href="#" onclick="closeWindow(); return false;" class="btn">Close Window</a>
            </div>
        </body>
        </html>
        """, status_code=400)
    
    # Exchange code for tokens
    try:
        # Import here to avoid circular imports
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from ebay.auth import get_auth
        
        auth = get_auth()
        tokens = auth.exchange_code_for_token(code)
        
        # Fetch and store user info
        username = "Unknown"
        try:
            user_info = auth.get_user_info()
            if user_info:
                username = user_info.get("username", "Unknown")
                # Update tokens with user info
                tokens.username = username
                tokens.user_id = user_info.get("userId")
                auth.config.tokens = tokens  # Re-save with username
        except Exception as e:
            print(f"Could not fetch user info: {e}")
        
        # Get environment for display
        env_label = "Production" if auth.config._active_environment == "production" else "Sandbox"
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>myBay - Connected!</title>
            <style>
                {base_style}
                h1 {{ color: #10b981; }}
                .success {{ background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); padding: 24px; border-radius: 12px; margin: 20px 0; }}
                .username {{ font-size: 24px; font-weight: bold; color: #065f46; margin: 10px 0; }}
                .env-badge {{ 
                    display: inline-block; padding: 4px 12px; 
                    background: {'#dc2626' if env_label == 'Production' else '#f59e0b'}; 
                    color: white; border-radius: 20px; font-size: 12px; font-weight: bold;
                    margin-bottom: 10px;
                }}
                .token-info {{ font-size: 13px; color: #888; margin-top: 20px; }}
            </style>
            {close_script}
        </head>
        <body>
            <div class="container">
                <div class="logo">📦</div>
                <div class="app-name">myBay</div>
                <h1>✅ Connected!</h1>
                <div class="success">
                    <div class="env-badge">{env_label}</div>
                    <p style="margin: 0; color: #065f46;">Signed in as:</p>
                    <p class="username">🏪 {username}</p>
                </div>
                <p>You can close this window and return to the app.</p>
                <p>Click <strong>🔄 Refresh</strong> in Settings to see your account.</p>
                <a href="#" onclick="closeWindow(); return false;" class="btn">Close Window</a>
                <p class="token-info">
                    Token expires in {tokens.expires_in // 3600} hours • 
                    Refresh token: {'✅' if tokens.refresh_token else '❌'}
                </p>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>myBay - Connection Error</title>
            <style>
                {base_style}
                h1 {{ color: #dc2626; }}
                .error {{ background: #fef2f2; padding: 16px; border-radius: 8px; margin: 20px 0; font-size: 14px; color: #991b1b; text-align: left; word-break: break-word; }}
            </style>
            {close_script}
        </head>
        <body>
            <div class="container">
                <div class="logo">📦</div>
                <div class="app-name">myBay</div>
                <h1>❌ Connection Failed</h1>
                <div class="error">{str(e)}</div>
                <p>Please check your eBay API credentials and try again.</p>
                <a href="#" onclick="closeWindow(); return false;" class="btn">Close Window</a>
            </div>
        </body>
        </html>
        """, status_code=500)


@app.get("/ebay/status")
async def ebay_auth_status():
    """Check eBay authentication status."""
    try:
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from ebay.config import get_config
        
        config = get_config()
        
        username = None
        if config.has_valid_token and config.tokens:
            username = config.tokens.username
        
        return {
            "configured": config.is_configured,
            "authenticated": config.has_valid_token,
            "environment": config.environment.value if config.is_configured else None,
            "username": username,
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# Run Server
# ============================================================================

def _is_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding."""
    import socket as _socket
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the server with uvicorn. Tries ports 8000-8010 if default is taken."""
    import uvicorn

    # Find an available port
    original_port = port
    for candidate in range(port, port + 11):
        if _is_port_available(host, candidate):
            port = candidate
            break
    else:
        print(f"❌ No available ports in range {original_port}-{original_port + 10}")
        return

    if port != original_port:
        print(f"⚠️  Port {original_port} in use, using {port} instead")

    local_ip = get_local_ip()
    print("\n" + "="*60)
    print("  📦 myBay - Camera Server")
    print("="*60)
    print(f"\n  🌐 Local URL:    http://localhost:{port}")
    print(f"  📱 Phone URL:    http://{local_ip}:{port}/camera")
    print(f"  🔗 QR Code:      http://localhost:{port}/qr")
    print(f"  📂 Queue Dir:    {QUEUE_DIR}")
    print("\n  Scan the QR code with your phone to start uploading!")
    print("="*60 + "\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()

#!/usr/bin/env python3
"""
Test script for myBay - Phase 2
Verifies the mobile camera server, file watcher, and QR code generation.

Usage:
    python tests/test_phase2.py
"""

import sys
import time
import threading
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_result(success: bool, message: str):
    """Print a result with icon."""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")


def test_imports():
    """Test that all Phase 2 modules import correctly."""
    print_header("Testing Imports")
    
    all_passed = True
    
    # Test FastAPI
    try:
        from fastapi import FastAPI
        print_result(True, "FastAPI imported")
    except ImportError as e:
        print_result(False, f"FastAPI import failed: {e}")
        all_passed = False
    
    # Test uvicorn
    try:
        import uvicorn
        print_result(True, "uvicorn imported")
    except ImportError as e:
        print_result(False, f"uvicorn import failed: {e}")
        all_passed = False
    
    # Test watchdog
    try:
        from watchdog.observers import Observer
        print_result(True, "watchdog imported")
    except ImportError as e:
        print_result(False, f"watchdog import failed: {e}")
        all_passed = False
    
    # Test qrcode
    try:
        import qrcode
        print_result(True, "qrcode imported")
    except ImportError as e:
        print_result(False, f"qrcode import failed: {e}")
        all_passed = False
    
    # Test websockets
    try:
        import websockets
        print_result(True, "websockets imported")
    except ImportError as e:
        print_result(False, f"websockets import failed: {e}")
        all_passed = False
    
    return all_passed


def test_server_module():
    """Test the server module."""
    print_header("Testing Server Module")
    
    all_passed = True
    
    try:
        from server.main import app, get_local_ip, QUEUE_DIR
        print_result(True, "Server module imported")
        
        # Test local IP detection
        ip = get_local_ip()
        print_result(True, f"Local IP detected: {ip}")
        
        # Test queue directory
        print_result(QUEUE_DIR.exists(), f"Queue directory exists: {QUEUE_DIR}")
        
        # Test app routes
        routes = [r.path for r in app.routes]
        required_routes = ["/", "/camera", "/upload", "/health", "/ws", "/qr"]
        for route in required_routes:
            if route in routes:
                print_result(True, f"Route {route} registered")
            else:
                print_result(False, f"Route {route} missing")
                all_passed = False
        
    except Exception as e:
        print_result(False, f"Server module test failed: {e}")
        all_passed = False
    
    return all_passed


def test_qr_code():
    """Test QR code generation."""
    print_header("Testing QR Code Generation")
    
    all_passed = True
    
    try:
        from core.qr_code import generate_qr_code, get_camera_url, save_qr_code
        
        # Test camera URL
        url = get_camera_url()
        print_result("http://" in url, f"Camera URL: {url}")
        
        # Test QR generation
        img = generate_qr_code()
        print_result(img is not None, f"QR code generated: {img.size}")
        
        # Test saving
        output_dir = Path(__file__).parent / "samples"
        output_dir.mkdir(exist_ok=True)
        qr_path = output_dir / "test_qr.png"
        save_qr_code(qr_path)
        print_result(qr_path.exists(), f"QR code saved: {qr_path}")
        
    except Exception as e:
        print_result(False, f"QR code test failed: {e}")
        all_passed = False
    
    return all_passed


def test_watcher():
    """Test the file watcher module."""
    print_header("Testing File Watcher")
    
    all_passed = True
    
    try:
        from core.watcher import QueueWatcher, ImageBatch
        
        # Create watcher
        test_queue = Path(__file__).parent / "test_queue"
        test_queue.mkdir(exist_ok=True)
        
        watcher = QueueWatcher(test_queue)
        print_result(True, f"QueueWatcher created: {watcher.queue_dir}")
        
        # Test callbacks
        received_batches = []
        
        def on_batch(batch):
            received_batches.append(batch)
        
        watcher.on_images_received = on_batch
        print_result(True, "Callbacks configured")
        
        # Start watcher
        watcher.start()
        print_result(True, "Watcher started")
        
        # Stop watcher
        time.sleep(0.5)
        watcher.stop()
        print_result(True, "Watcher stopped")
        
        # Cleanup
        import shutil
        if test_queue.exists():
            shutil.rmtree(test_queue)
        
    except Exception as e:
        print_result(False, f"Watcher test failed: {e}")
        all_passed = False
    
    return all_passed


def test_camera_html():
    """Test that camera HTML template exists and is valid."""
    print_header("Testing Camera Template")
    
    all_passed = True
    
    template_path = Path(__file__).parent.parent / "server" / "templates" / "camera.html"
    
    if template_path.exists():
        print_result(True, f"Template exists: {template_path.name}")
        
        content = template_path.read_text()
        
        # Check for required elements
        checks = [
            ("<html", "HTML document"),
            ("viewport", "Mobile viewport meta"),
            ('id="fileInput"', "File input element"),
            ('id="uploadBtn"', "Upload button"),
            ("WebSocket", "WebSocket support"),
            ("/upload", "Upload endpoint reference"),
        ]
        
        for pattern, description in checks:
            if pattern in content:
                print_result(True, f"Contains: {description}")
            else:
                print_result(False, f"Missing: {description}")
                all_passed = False
        
        print_result(True, f"Template size: {len(content):,} bytes")
        
    else:
        print_result(False, f"Template not found: {template_path}")
        all_passed = False
    
    return all_passed


def test_server_startup():
    """Test that the server can start (brief startup test)."""
    print_header("Testing Server Startup")
    
    all_passed = True
    
    try:
        import httpx
        from server.main import app
        
        # Use TestClient for quick startup test
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Health check passed: {data.get('status')}")
            print_result(True, f"Local IP: {data.get('local_ip')}")
        else:
            print_result(False, f"Health check failed: {response.status_code}")
            all_passed = False
        
        # Test info endpoint
        response = client.get("/info")
        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Camera URL: {data.get('camera_url')}")
        else:
            print_result(False, f"Info endpoint failed: {response.status_code}")
            all_passed = False
        
        # Test camera page
        response = client.get("/camera")
        if response.status_code == 200:
            print_result(True, f"Camera page served: {len(response.text):,} bytes")
        else:
            print_result(False, f"Camera page failed: {response.status_code}")
            all_passed = False
        
        # Test QR code
        response = client.get("/qr")
        if response.status_code == 200:
            print_result(True, f"QR code generated: {len(response.content):,} bytes")
        else:
            print_result(False, f"QR code failed: {response.status_code}")
            all_passed = False
        
    except Exception as e:
        print_result(False, f"Server startup test failed: {e}")
        all_passed = False
    
    return all_passed


def run_all_tests():
    """Run all Phase 2 tests."""
    print("\n" + "🔬 "*20)
    print("   MYBAY - PHASE 2 TEST SUITE")
    print("🔬 "*20)
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: Server module
    results.append(("Server Module", test_server_module()))
    
    # Test 3: QR Code
    results.append(("QR Code Generation", test_qr_code()))
    
    # Test 4: File Watcher
    results.append(("File Watcher", test_watcher()))
    
    # Test 5: Camera Template
    results.append(("Camera Template", test_camera_html()))
    
    # Test 6: Server Startup
    results.append(("Server Startup", test_server_startup()))
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = 0
    failed = 0
    
    for name, result in results:
        if result:
            print_result(True, f"{name}: PASSED")
            passed += 1
        else:
            print_result(False, f"{name}: FAILED")
            failed += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 Phase 2 is fully operational!")
        print("\nTo start the server, run:")
        print("   source venv/bin/activate")
        print("   python -m server.main")
        print("\nThen scan the QR code with your phone!")
    else:
        print("\n❌ Some tests failed. Please fix issues before proceeding.")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

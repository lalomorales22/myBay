#!/usr/bin/env python3
"""
myBay - Main Runner

Starts the mobile camera server, file watcher, and GUI together.
This is the main entry point for the app.

Usage:
    python run.py              # Start server only
    python run.py --watch      # Start server + file watcher
    python run.py --gui        # Start the desktop GUI (full app)
    python run.py --qr         # Show QR code in terminal
"""

import sys
import os
import argparse
import threading
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))


def show_banner():
    """Display the app banner."""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║       📦 myBay - Camera Server                            ║
║                                                           ║
║   Snap photos on your phone → AI creates the listing      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")


def show_qr_terminal():
    """Show QR code in terminal."""
    try:
        from core.qr_code import print_qr_ascii, get_camera_url
        print("\n📱 Scan this QR code with your phone:\n")
        print_qr_ascii()
    except ImportError:
        print("❌ qrcode library not installed")


def start_watcher():
    """Start the file watcher in a separate thread."""
    from core.watcher import QueueWatcher
    
    watcher = QueueWatcher()
    
    def on_listing(batch, result):
        print(f"\n{'='*50}")
        print("✅ NEW LISTING READY!")
        print(f"{'='*50}")
        print(f"📝 Title:       {result.title}")
        print(f"💰 Price:       ${result.suggested_price_usd:.2f}")
        print(f"🏷️  Brand:       {result.brand or 'Unknown'}")
        print(f"📦 Condition:   {result.condition}")
        print(f"🎯 Confidence:  {result.confidence_score*100:.0f}%")
        print(f"🔖 Category:    {', '.join(result.category_keywords)}")
        print(f"\n📄 Description:\n   {result.description}")
        print(f"{'='*50}\n")
    
    def on_error(batch, error):
        print(f"\n❌ Analysis error: {error}\n")
    
    watcher.on_new_listing = on_listing
    watcher.on_error = on_error
    
    watcher.start()
    return watcher


def start_watcher_with_db():
    """Start the file watcher with database integration."""
    from core.integration import create_watcher_with_db
    
    bridge = create_watcher_with_db()
    
    def on_draft(draft):
        print(f"\n{'='*50}")
        print("✅ DRAFT CREATED!")
        print(f"{'='*50}")
        print(f"📝 Title:       {draft.title}")
        print(f"💰 Price:       ${draft.price:.2f}")
        print(f"🎯 Confidence:  {draft.ai_confidence*100:.0f}%")
        print(f"🖼️  Images:      {len(draft.image_paths)}")
        print(f"{'='*50}\n")
    
    bridge.on_draft_created = on_draft
    bridge.start(blocking=False)
    return bridge


def start_server_thread(host: str, port: int):
    """Start the server in a background thread."""
    import uvicorn
    import server.main as server_module

    # Tell the server module which port we're actually using
    server_module.SERVER_PORT = port

    config = uvicorn.Config(
        server_module.app,
        host=host,
        port=port,
        log_level="warning"  # Quieter for GUI mode
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return thread


def run_gui(host: str = "0.0.0.0", port: int = 8000, auto_start_ngrok: bool = False):
    """Run the full GUI application with server and watcher."""
    show_banner()
    print("🖥️  Starting Desktop GUI Mode...\n")

    from core.paths import ensure_env_template, get_user_data_dir
    if ensure_env_template():
        data_dir = get_user_data_dir()
        print(f"📝 First launch detected! Created .env template at:")
        print(f"   {data_dir / '.env'}")
        print(f"   Edit that file and set your OPENAI_API_KEY to get started.\n")
    
    from core.qr_code import get_local_ip, get_camera_url
    local_ip = get_local_ip()
    camera_url = get_camera_url(port)
    
    print(f"📱 Phone URL:     {camera_url}")
    print(f"🔗 Server:        http://localhost:{port}")
    print(f"📂 Queue:         ./queue/")

    ngrok_started_by_app = False
    stop_ngrok = None
    if auto_start_ngrok:
        print("\n🌐 Ensuring ngrok tunnel...")
        try:
            from core.ngrok import ensure_ngrok_tunnel, stop_managed_ngrok

            ngrok_result = ensure_ngrok_tunnel(port=port)
            stop_ngrok = stop_managed_ngrok
            ngrok_started_by_app = ngrok_result.started_by_app

            if ngrok_result.public_url:
                print(f"✅ ngrok tunnel: {ngrok_result.public_url}")
            elif ngrok_result.running:
                print("⚠️ ngrok is running, but tunnel URL is not ready yet")
            else:
                print(f"⚠️ ngrok unavailable: {ngrok_result.error}")
        except Exception as ngrok_err:
            print(f"⚠️ ngrok startup error: {ngrok_err}")
    
    # Start server in background
    print("\n🚀 Starting camera server...")
    server_thread = start_server_thread(host, port)
    time.sleep(1)  # Let server start
    
    # Start watcher with database integration
    print("👁️  Starting file watcher with database...")
    bridge = start_watcher_with_db()
    
    # Start GUI (blocks until window closes)
    print("🖥️  Launching GUI...\n")
    print("-" * 50)
    
    try:
        from gui.app import MyBayApp
        app = MyBayApp()
        app.mainloop()
        
    except ImportError as e:
        print(f"\n❌ GUI dependencies not installed: {e}")
        print("   Run: pip install customtkinter pillow")
        return
    finally:
        print("\n👋 Shutting down...")
        bridge.stop()
        if ngrok_started_by_app and stop_ngrok:
            try:
                stop_ngrok()
                print("🛑 Stopped managed ngrok tunnel")
            except Exception:
                pass


def main():
    # Auto-enable GUI mode when running as bundled app
    is_bundled = getattr(sys, 'frozen', False)
    
    parser = argparse.ArgumentParser(
        description="myBay - Mobile Camera Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                  Start the camera server
  python run.py --watch          Start server with auto-analysis
  python run.py --gui            Start the desktop GUI (recommended!)
  python run.py --qr             Just show the QR code
  python run.py --port 9000      Use a different port
        """
    )
    
    parser.add_argument("--port", "-p", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--watch", "-w", action="store_true", help="Enable file watcher for auto-analysis")
    parser.add_argument("--gui", "-g", action="store_true", default=is_bundled, help="Launch the desktop GUI (recommended)")
    parser.add_argument("--qr", action="store_true", help="Just show QR code and exit")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser on startup")
    parser.add_argument("--no-ngrok", action="store_true", help="Disable auto-start ngrok tunnel in GUI mode")
    
    args = parser.parse_args()
    
    # GUI mode - the recommended way to run
    if args.gui:
        auto_start_ngrok = not args.no_ngrok
        run_gui(args.host, args.port, auto_start_ngrok=auto_start_ngrok)
        return
    
    show_banner()
    
    # QR only mode
    if args.qr:
        show_qr_terminal()
        return
    
    # Get server info
    from core.qr_code import get_local_ip, get_camera_url
    local_ip = get_local_ip()
    camera_url = get_camera_url(args.port)
    
    print(f"🌐 Local URL:     http://localhost:{args.port}")
    print(f"📱 Phone URL:     {camera_url}")
    print(f"🔗 QR Code:       http://localhost:{args.port}/qr")
    print(f"📂 Queue:         ./queue/")
    
    # Start file watcher if requested
    watcher = None
    if args.watch:
        print(f"\n👁️  Auto-analysis: ENABLED")
        print("   Photos will be analyzed automatically when received")
        watcher = start_watcher()
    else:
        print(f"\n👁️  Auto-analysis: DISABLED")
        print("   Use --watch to enable automatic AI analysis")
    
    # Show QR code
    print("\n" + "-"*50)
    show_qr_terminal()
    print("-"*50)
    
    print("\n🚀 Starting server... Press Ctrl+C to stop\n")
    
    # Start server
    try:
        import uvicorn
        from server.main import app
        
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
    finally:
        if watcher:
            watcher.stop()


if __name__ == "__main__":
    main()

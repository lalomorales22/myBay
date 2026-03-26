"""
QR Code Utility for myBay

Generates QR codes for the mobile camera URL.
Can be used standalone or integrated into the GUI.
"""

import io
import socket
from pathlib import Path

try:
    import qrcode
    from PIL import Image
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False


def get_local_ip() -> str:
    """Get the local IP address for network access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_camera_url(port: int = 8000) -> str:
    """Get the camera URL for the mobile device."""
    local_ip = get_local_ip()
    return f"http://{local_ip}:{port}/camera"


def generate_qr_code(
    url: str = None,
    port: int = 8000,
    size: int = 300,
    border: int = 4,
) -> Image.Image:
    """
    Generate a QR code image for the camera URL.
    
    Args:
        url: Custom URL (defaults to camera URL)
        port: Server port (used if url not provided)
        size: Size of the QR code in pixels
        border: Border width in boxes
        
    Returns:
        PIL Image object
        
    Raises:
        ImportError: If qrcode library is not installed
    """
    if not QRCODE_AVAILABLE:
        raise ImportError("qrcode library not installed. Run: pip install qrcode[pil]")
    
    if url is None:
        url = get_camera_url(port)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Resize to desired size
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    return img


def save_qr_code(
    output_path: str | Path,
    url: str = None,
    port: int = 8000,
    size: int = 300,
) -> Path:
    """
    Save QR code to a file.
    
    Args:
        output_path: Path to save the QR code image
        url: Custom URL (defaults to camera URL)
        port: Server port
        size: Size in pixels
        
    Returns:
        Path to the saved file
    """
    output_path = Path(output_path)
    img = generate_qr_code(url=url, port=port, size=size)
    
    # Save based on extension
    suffix = output_path.suffix.lower()
    if suffix == ".png":
        img.save(output_path, "PNG")
    else:
        # Convert to RGB for JPEG
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(output_path, "JPEG", quality=95)
    
    return output_path


def get_qr_code_bytes(
    url: str = None,
    port: int = 8000,
    size: int = 300,
    format: str = "PNG",
) -> bytes:
    """
    Get QR code as bytes (useful for embedding in GUI).
    
    Args:
        url: Custom URL
        port: Server port
        size: Size in pixels
        format: Image format (PNG or JPEG)
        
    Returns:
        Image bytes
    """
    img = generate_qr_code(url=url, port=port, size=size)
    
    buffer = io.BytesIO()
    if format.upper() == "PNG":
        img.save(buffer, "PNG")
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(buffer, "JPEG", quality=95)
    
    buffer.seek(0)
    return buffer.getvalue()


def print_qr_ascii(url: str = None, port: int = 8000):
    """
    Print QR code as ASCII art to terminal.
    
    Args:
        url: Custom URL
        port: Server port
    """
    if not QRCODE_AVAILABLE:
        print("qrcode library not installed")
        return
    
    if url is None:
        url = get_camera_url(port)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # Print to terminal
    qr.print_ascii(invert=True)
    print(f"\nScan with phone camera to open: {url}")


# CLI usage
if __name__ == "__main__":
    import sys
    
    print("="*50)
    print("  myBay - QR Code Generator")
    print("="*50)
    
    if not QRCODE_AVAILABLE:
        print("\n❌ qrcode library not installed")
        print("   Run: pip install qrcode[pil]")
        sys.exit(1)
    
    local_ip = get_local_ip()
    camera_url = get_camera_url()
    
    print(f"\n📱 Camera URL: {camera_url}")
    print(f"🌐 Local IP:   {local_ip}")
    
    # Save QR code
    output_dir = Path(__file__).parent.parent / "server" / "static"
    output_dir.mkdir(parents=True, exist_ok=True)
    qr_path = output_dir / "qr_code.png"
    
    save_qr_code(qr_path)
    print(f"💾 QR saved:   {qr_path}")
    
    # Print ASCII QR
    print("\n" + "-"*50)
    print_qr_ascii()

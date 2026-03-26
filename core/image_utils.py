"""
Image Utilities for myBay

Provides image processing functions including:
- Background removal for professional white backgrounds
- Image resizing and optimization for eBay
- Batch processing utilities
"""

import io
from pathlib import Path
from typing import Optional
from PIL import Image

# Try to import rembg, but make it optional
try:
    from rembg import remove as rembg_remove
    REMBG_AVAILABLE = True
except (ImportError, Exception):
    REMBG_AVAILABLE = False
    rembg_remove = None


def remove_background(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    background_color: tuple[int, int, int] = (255, 255, 255),
) -> Path:
    """
    Remove background from an image and optionally add a solid color background.
    
    Uses the rembg library for AI-powered background removal.
    
    Args:
        input_path: Path to the input image
        output_path: Path for the output image (auto-generated if None)
        background_color: RGB tuple for background color (default: white)
        
    Returns:
        Path to the processed image
        
    Raises:
        ImportError: If rembg is not installed
        FileNotFoundError: If input image doesn't exist
    """
    if not REMBG_AVAILABLE:
        raise ImportError(
            "rembg is not installed. Install it with: pip install rembg\n"
            "Note: This also requires onnxruntime."
        )
    
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")
    
    # Generate output path if not provided
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_nobg{input_path.suffix}"
    output_path = Path(output_path)
    
    # Read the input image
    with open(input_path, "rb") as f:
        input_data = f.read()
    
    # Remove background (returns PNG with transparency)
    output_data = rembg_remove(input_data)
    
    # Open the result and add solid background
    img_no_bg = Image.open(io.BytesIO(output_data)).convert("RGBA")
    
    # Create background image
    background = Image.new("RGBA", img_no_bg.size, (*background_color, 255))
    
    # Composite the images
    final_img = Image.alpha_composite(background, img_no_bg)
    
    # Convert to RGB for JPEG compatibility
    final_rgb = final_img.convert("RGB")
    
    # Determine output format from extension
    suffix = output_path.suffix.lower()
    if suffix in [".jpg", ".jpeg"]:
        final_rgb.save(output_path, "JPEG", quality=95)
    elif suffix == ".png":
        final_rgb.save(output_path, "PNG")
    else:
        # Default to JPEG
        output_path = output_path.with_suffix(".jpg")
        final_rgb.save(output_path, "JPEG", quality=95)
    
    return output_path


def optimize_for_ebay(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    max_size: tuple[int, int] = (1600, 1600),
    quality: int = 90,
) -> Path:
    """
    Optimize an image for eBay listing (resize and compress).
    
    eBay recommends images at least 500x500 pixels, with 1600x1600 being ideal.
    
    Args:
        input_path: Path to the input image
        output_path: Path for the output image (auto-generated if None)
        max_size: Maximum dimensions (width, height)
        quality: JPEG quality (1-100)
        
    Returns:
        Path to the optimized image
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")
    
    # Generate output path if not provided
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_optimized.jpg"
    output_path = Path(output_path)
    
    # Open and process the image
    img = Image.open(input_path)
    
    # Convert to RGB if necessary (handles RGBA, P mode, etc.)
    if img.mode in ("RGBA", "P", "LA"):
        # Create white background for transparent images
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    
    # Resize if larger than max_size while maintaining aspect ratio
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Save optimized image
    img.save(output_path, "JPEG", quality=quality, optimize=True)
    
    return output_path


def process_images_for_listing(
    image_paths: list[str | Path],
    output_dir: Optional[str | Path] = None,
    remove_bg: bool = True,
    optimize: bool = True,
) -> dict[str, list[Path]]:
    """
    Process multiple images for an eBay listing.
    
    Creates both original (optimized) and background-removed versions.
    
    Args:
        image_paths: List of input image paths
        output_dir: Directory for processed images (uses input dir if None)
        remove_bg: Whether to create background-removed versions
        optimize: Whether to optimize images for eBay
        
    Returns:
        Dictionary with 'original' and 'no_background' lists of paths
    """
    results = {
        "original": [],
        "no_background": [],
        "errors": [],
    }
    
    for i, path in enumerate(image_paths):
        path = Path(path)
        
        if output_dir:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = path.parent
        
        try:
            # Optimize original
            if optimize:
                opt_path = out_dir / f"{path.stem}_{i+1:02d}.jpg"
                optimized = optimize_for_ebay(path, opt_path)
                results["original"].append(optimized)
            else:
                results["original"].append(path)
            
            # Remove background
            if remove_bg and REMBG_AVAILABLE:
                nobg_path = out_dir / f"{path.stem}_{i+1:02d}_white.jpg"
                try:
                    processed = remove_background(path, nobg_path)
                    results["no_background"].append(processed)
                except Exception as e:
                    results["errors"].append(f"Background removal failed for {path.name}: {e}")
            
        except Exception as e:
            results["errors"].append(f"Failed to process {path.name}: {e}")
    
    return results


def get_image_info(image_path: str | Path) -> dict:
    """
    Get information about an image file.
    
    Args:
        image_path: Path to the image
        
    Returns:
        Dictionary with image metadata
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    
    img = Image.open(path)
    
    return {
        "path": str(path.absolute()),
        "filename": path.name,
        "format": img.format,
        "mode": img.mode,
        "width": img.width,
        "height": img.height,
        "size_bytes": path.stat().st_size,
        "size_readable": _format_size(path.stat().st_size),
    }


def _format_size(size_bytes: int) -> str:
    """Format byte size to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def is_valid_image(path: str | Path) -> bool:
    """
    Check if a file is a valid image that can be processed.
    
    Args:
        path: Path to check
        
    Returns:
        True if valid image, False otherwise
    """
    try:
        path = Path(path)
        if not path.exists():
            return False
        
        # Check extension
        valid_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
        if path.suffix.lower() not in valid_extensions:
            return False
        
        # Try to open the image
        img = Image.open(path)
        img.verify()  # Verify it's a valid image
        return True
        
    except Exception:
        return False


# CLI interface for testing
if __name__ == "__main__":
    import sys
    
    print("Image Utilities for myBay")
    print("=" * 40)
    
    if REMBG_AVAILABLE:
        print("✅ rembg is installed - background removal available")
    else:
        print("⚠️  rembg not installed - run: pip install rembg")
    
    if len(sys.argv) > 1:
        # Process provided image
        image_path = sys.argv[1]
        print(f"\nProcessing: {image_path}")
        
        try:
            info = get_image_info(image_path)
            print(f"  Size: {info['width']}x{info['height']}")
            print(f"  Format: {info['format']}")
            print(f"  File size: {info['size_readable']}")
            
            if REMBG_AVAILABLE:
                print("\nRemoving background...")
                output = remove_background(image_path)
                print(f"  Saved to: {output}")
                
        except Exception as e:
            print(f"  Error: {e}")
    else:
        print("\nUsage: python image_utils.py <image_path>")

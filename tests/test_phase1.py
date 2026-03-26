#!/usr/bin/env python3
"""
Test script for myBay - Phase 1
Verifies OpenAI connection, vision analysis, and image utilities.

Usage:
    python test_phase1.py              # Run all tests
    python test_phase1.py --create-sample  # Create a sample test image
    python test_phase1.py <image_path> # Analyze a specific image
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vision import ProductAnalyzer, ProductData, analyze_product
from core.image_utils import (
    REMBG_AVAILABLE,
    remove_background,
    optimize_for_ebay,
    get_image_info,
    is_valid_image,
)


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_result(success: bool, message: str):
    """Print a result with icon."""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")


def create_sample_image(output_path: Path) -> bool:
    """Create a simple test image using PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple product-like image
        img = Image.new('RGB', (800, 600), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        
        # Draw a simple "product" shape
        draw.rectangle([200, 100, 600, 500], fill=(70, 130, 180), outline=(50, 100, 150), width=3)
        
        # Add some text
        draw.text((300, 250), "TEST", fill=(255, 255, 255))
        draw.text((280, 300), "PRODUCT", fill=(255, 255, 255))
        
        # Add a "brand" label
        draw.rectangle([250, 450, 550, 490], fill=(255, 255, 255), outline=(200, 200, 200))
        draw.text((320, 460), "Sample Brand", fill=(100, 100, 100))
        
        img.save(output_path, "JPEG", quality=95)
        return True
        
    except Exception as e:
        print(f"Failed to create sample image: {e}")
        return False


def test_openai_connection():
    """Test connection to OpenAI API."""
    print_header("Testing OpenAI Connection")
    
    analyzer = ProductAnalyzer()

    if not analyzer.api_key:
        print_result(False, "OPENAI_API_KEY not set")
        print("   Add OPENAI_API_KEY to environment or .env")
        return False

    if analyzer.check_openai_status():
        print_result(True, f"OpenAI API reachable (model: {analyzer.model})")
        models = analyzer.get_available_models()
        if models:
            preview = ", ".join(models[:5])
            print(f"   Sample available models: {preview}")
        return True

    print_result(False, "OpenAI API check failed")
    print("   Verify API key, billing, model access, and network connectivity")
    return False


def test_image_utils():
    """Test image utility functions."""
    print_header("Testing Image Utilities")
    
    # Check PIL
    try:
        from PIL import Image
        print_result(True, "Pillow (PIL) is installed")
    except ImportError:
        print_result(False, "Pillow not installed - run: pip install Pillow")
        return False
    
    # Check rembg
    if REMBG_AVAILABLE:
        print_result(True, "rembg is installed (background removal available)")
    else:
        print_result(False, "rembg not installed (optional) - run: pip install rembg")
    
    # Test with a sample image if available
    sample_dir = Path(__file__).parent / "samples"
    sample_dir.mkdir(exist_ok=True)
    sample_path = sample_dir / "test_product.jpg"
    
    # Create a sample image for testing
    if not sample_path.exists():
        print("\nCreating sample test image...")
        if create_sample_image(sample_path):
            print_result(True, f"Created sample image: {sample_path}")
        else:
            print_result(False, "Could not create sample image")
            return True  # Not a critical failure
    
    # Test image info
    try:
        info = get_image_info(sample_path)
        print_result(True, f"get_image_info works: {info['width']}x{info['height']}")
    except Exception as e:
        print_result(False, f"get_image_info failed: {e}")
    
    # Test is_valid_image
    try:
        valid = is_valid_image(sample_path)
        print_result(valid, f"is_valid_image: {valid}")
    except Exception as e:
        print_result(False, f"is_valid_image failed: {e}")
    
    # Test optimize_for_ebay
    try:
        opt_path = sample_dir / "test_product_optimized.jpg"
        result = optimize_for_ebay(sample_path, opt_path)
        print_result(True, f"optimize_for_ebay works: {result.name}")
    except Exception as e:
        print_result(False, f"optimize_for_ebay failed: {e}")
    
    # Test background removal (if available)
    if REMBG_AVAILABLE:
        try:
            print("\nTesting background removal (this may take a moment on first run)...")
            nobg_path = sample_dir / "test_product_nobg.jpg"
            result = remove_background(sample_path, nobg_path)
            print_result(True, f"remove_background works: {result.name}")
        except Exception as e:
            print_result(False, f"remove_background failed: {e}")
    
    return True


def test_vision_analysis(image_path: Path = None):
    """Test the AI vision analysis."""
    print_header("Testing Vision Analysis")
    
    # Use sample image if none provided
    if image_path is None:
        sample_path = Path(__file__).parent / "samples" / "test_product.jpg"
        if not sample_path.exists():
            print("No test image available. Creating one...")
            sample_path.parent.mkdir(exist_ok=True)
            if not create_sample_image(sample_path):
                print_result(False, "Cannot create test image")
                return False
        image_path = sample_path
    
    # Check if OpenAI is ready
    analyzer = ProductAnalyzer()
    if not analyzer.check_openai_status():
        print_result(False, "OpenAI not ready - skipping vision test")
        print("   Set OPENAI_API_KEY and verify model access")
        return False
    
    print(f"Analyzing image: {image_path}")
    print("This may take 10-30 seconds...")
    
    try:
        result = analyzer.analyze_images([str(image_path)])
        
        print_result(True, "Vision analysis completed!")
        print("\n" + "-"*40)
        print("ANALYSIS RESULTS:")
        print("-"*40)
        print(f"Title:       {result.title}")
        print(f"Brand:       {result.brand or 'Unknown'}")
        print(f"Category:    {', '.join(result.category_keywords)}")
        print(f"Condition:   {result.condition}")
        print(f"Color:       {result.color or 'N/A'}")
        print(f"Material:    {result.material or 'N/A'}")
        print(f"Price:       ${result.suggested_price_usd:.2f}")
        print(f"Confidence:  {result.confidence_score*100:.0f}%")
        print(f"\nDescription: {result.description}")
        print("-"*40)
        
        # Output as JSON too
        print("\nJSON Output:")
        print(json.dumps(result.to_dict(), indent=2))
        
        return True
        
    except Exception as e:
        print_result(False, f"Vision analysis failed: {e}")
        return False


def run_all_tests():
    """Run all Phase 1 tests."""
    print("\n" + "🔬 "*20)
    print("   MYBAY - PHASE 1 TEST SUITE")
    print("🔬 "*20)
    
    results = []
    
    # Test 1: OpenAI connection
    results.append(("OpenAI Connection", test_openai_connection()))
    
    # Test 2: Image utilities
    results.append(("Image Utilities", test_image_utils()))
    
    # Test 3: Vision analysis (only if OpenAI is available)
    if results[0][1]:
        results.append(("Vision Analysis", test_vision_analysis()))
    else:
        results.append(("Vision Analysis", None))  # Skipped
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results:
        if result is True:
            print_result(True, f"{name}: PASSED")
            passed += 1
        elif result is False:
            print_result(False, f"{name}: FAILED")
            failed += 1
        else:
            print(f"⏭️  {name}: SKIPPED")
            skipped += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0 and skipped == 0:
        print("\n🎉 Phase 1 is fully operational! Ready for Phase 2.")
    elif failed == 0:
        print("\n⚠️  Phase 1 partially complete. See skipped tests above.")
    else:
        print("\n❌ Some tests failed. Please fix issues before proceeding.")
    
    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--create-sample":
            # Just create a sample image
            sample_path = Path(__file__).parent / "samples" / "test_product.jpg"
            sample_path.parent.mkdir(exist_ok=True)
            if create_sample_image(sample_path):
                print(f"✅ Created sample image: {sample_path}")
            else:
                print("❌ Failed to create sample image")
                
        elif arg == "--help" or arg == "-h":
            print(__doc__)
            
        else:
            # Analyze a specific image
            image_path = Path(arg)
            if image_path.exists():
                test_vision_analysis(image_path)
            else:
                print(f"❌ Image not found: {image_path}")
    else:
        # Run all tests
        success = run_all_tests()
        sys.exit(0 if success else 1)

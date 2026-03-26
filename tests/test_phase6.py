#!/usr/bin/env python3
"""
Test script for myBay - Phase 6 (Ollama Integration)

Verifies:
- OllamaAnalyzer connection and analysis
- Analyzer factory auto-detection and routing
- eBay pricing fallback for Ollama
- Presets persistence with new AI fields

Usage:
    python test_phase6.py           # Run all tests
    python test_phase6.py --skip-ollama  # Skip tests requiring Ollama
"""

import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vision import ProductAnalyzer, ProductData, ANALYSIS_PROMPT
from core.ollama import (
    OllamaAnalyzer,
    check_ollama_status,
    get_ollama_models,
    has_vision_model,
    DEFAULT_OLLAMA_URL,
    DEFAULT_OLLAMA_MODEL,
)
from core.analyzer_factory import get_analyzer, detect_available_backend
from core.presets import MybayPresets


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_result(success: bool, message: str):
    """Print a result with icon."""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")


def ollama_available() -> bool:
    """Check if Ollama is running locally."""
    try:
        import httpx
        r = httpx.get(f"{DEFAULT_OLLAMA_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


# ========== Ollama Module Tests ==========

def test_ollama_check_status_mock():
    """Test check_ollama_status with mocked responses."""
    print_header("Test: check_ollama_status (mocked)")

    # Mock a successful response
    with patch("core.ollama.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        result = check_ollama_status("http://fake:11434")
        print_result(result is True, "Returns True on 200")

    # Mock a failed connection
    with patch("core.ollama.httpx.get", side_effect=Exception("Connection refused")):
        result = check_ollama_status("http://fake:11434")
        print_result(result is False, "Returns False on connection error")

    return True


def test_get_ollama_models_mock():
    """Test get_ollama_models with mocked responses."""
    print_header("Test: get_ollama_models (mocked)")

    mock_data = {
        "models": [
            {"name": "qwen3.5:2b", "size": 4000000000},
            {"name": "llama3.2:latest", "size": 3000000000},
        ]
    }

    with patch("core.ollama.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_data
        mock_get.return_value = mock_resp
        models = get_ollama_models("http://fake:11434")
        print_result(len(models) == 2, f"Got {len(models)} models")
        print_result("qwen3.5:2b" in models, "qwen3.5:2b found")

    return True


def test_has_vision_model_mock():
    """Test has_vision_model with mocked responses."""
    print_header("Test: has_vision_model (mocked)")

    # With a vision model
    with patch("core.ollama.get_ollama_models", return_value=["qwen3.5:2b", "llama3.2:latest"]):
        result = has_vision_model("http://fake:11434")
        print_result(result is True, "Detects qwen3.5 as vision model")

    # Without a vision model
    with patch("core.ollama.get_ollama_models", return_value=["llama3.2:latest", "phi:latest"]):
        result = has_vision_model("http://fake:11434")
        print_result(result is False, "No vision model detected correctly")

    # With moondream
    with patch("core.ollama.get_ollama_models", return_value=["moondream:latest"]):
        result = has_vision_model("http://fake:11434")
        print_result(result is True, "Detects moondream as vision model")

    return True


def test_ollama_analyzer_init():
    """Test OllamaAnalyzer initialization."""
    print_header("Test: OllamaAnalyzer initialization")

    # Default init
    analyzer = OllamaAnalyzer()
    print_result(analyzer.model == DEFAULT_OLLAMA_MODEL, f"Default model: {analyzer.model}")
    print_result(analyzer.base_url == DEFAULT_OLLAMA_URL, f"Default URL: {analyzer.base_url}")
    print_result(analyzer.timeout == 120.0, f"Default timeout: {analyzer.timeout}")

    # Custom init
    analyzer = OllamaAnalyzer(model="moondream", base_url="http://custom:1234", timeout=60.0)
    print_result(analyzer.model == "moondream", "Custom model")
    print_result(analyzer.base_url == "http://custom:1234", "Custom URL")
    print_result(analyzer.timeout == 60.0, "Custom timeout")

    # Environment variable override
    with patch.dict(os.environ, {"OLLAMA_VISION_MODEL": "minicpm-v", "OLLAMA_URL": "http://env:5555"}):
        analyzer = OllamaAnalyzer()
        print_result(analyzer.model == "minicpm-v", "Env var model override")
        print_result(analyzer.base_url == "http://env:5555", "Env var URL override")

    return True


def test_ollama_json_parsing():
    """Test OllamaAnalyzer JSON response parsing."""
    print_header("Test: OllamaAnalyzer JSON parsing")

    analyzer = OllamaAnalyzer()

    # Clean JSON
    clean = '{"title": "Nike Air Max 90", "brand": "Nike", "model": "Air Max 90", "size": "10", "category_keywords": ["shoes"], "condition": "GOOD", "color": "White", "material": "Leather", "description": "A pair of shoes", "suggested_price_usd": 89.99, "confidence_score": 0.85}'
    result = analyzer._parse_json_response(clean)
    print_result(result["title"] == "Nike Air Max 90", "Clean JSON parsed")
    print_result(result["suggested_price_usd"] == 89.99, "Price correct")

    # JSON in markdown code block
    markdown = '```json\n{"title": "Test Item", "brand": null, "model": null, "size": null, "category_keywords": ["test"], "condition": "NEW", "color": null, "material": null, "description": "A test", "suggested_price_usd": 10.0, "confidence_score": 0.5}\n```'
    result = analyzer._parse_json_response(markdown)
    print_result(result["title"] == "Test Item", "Markdown code block parsed")

    # JSON with extra text
    messy = 'Here is the analysis:\n\n{"title": "Camera", "brand": "Canon", "model": "EOS R5", "size": null, "category_keywords": ["camera", "electronics"], "condition": "LIKE_NEW", "color": "Black", "material": null, "description": "A camera", "suggested_price_usd": 2499.99, "confidence_score": 0.90}\n\nLet me know if you need more details.'
    result = analyzer._parse_json_response(messy)
    print_result(result["title"] == "Camera", "Extra text stripped")

    # Trailing comma (common LLM error)
    trailing = '{"title": "Widget", "brand": null, "model": null, "size": null, "category_keywords": ["misc",], "condition": "GOOD", "color": null, "material": null, "description": "A widget", "suggested_price_usd": 5.0, "confidence_score": 0.4,}'
    result = analyzer._parse_json_response(trailing)
    print_result(result.get("title") == "Widget", "Trailing comma repaired")

    # Completely broken — regex fallback
    broken = 'I found a "title": "Broken Item" with "condition": "ACCEPTABLE" and "suggested_price_usd": 12.50 and "confidence_score": 0.3'
    result = analyzer._parse_json_response(broken)
    print_result(result.get("title") == "Broken Item", "Regex fallback extracted title")

    return True


def test_ollama_validate_product_data():
    """Test OllamaAnalyzer data validation."""
    print_header("Test: OllamaAnalyzer data validation")

    analyzer = OllamaAnalyzer()

    # Normal data
    data = {
        "title": "Test Product",
        "brand": "TestBrand",
        "condition": "GOOD",
        "category_keywords": ["test"],
        "suggested_price_usd": 25.0,
        "confidence_score": 0.8,
    }
    validated = analyzer._validate_product_data(data)
    print_result(validated["title"] == "Test Product", "Normal data passes through")

    # Invalid condition
    data["condition"] = "BROKEN"
    validated = analyzer._validate_product_data(data)
    print_result(validated["condition"] == "GOOD", "Invalid condition defaults to GOOD")

    # Price out of range
    data["suggested_price_usd"] = -50
    validated = analyzer._validate_product_data(data)
    print_result(validated["suggested_price_usd"] == 0.0, "Negative price clamped to 0")

    # Confidence out of range
    data["confidence_score"] = 1.5
    validated = analyzer._validate_product_data(data)
    print_result(validated["confidence_score"] == 1.0, "Confidence >1 clamped to 1.0")

    # Empty title
    data["title"] = ""
    validated = analyzer._validate_product_data(data)
    print_result(validated["title"] == "Unknown Item", "Empty title defaults to Unknown Item")

    # Keywords as string
    data["category_keywords"] = "shoes, clothing, apparel"
    validated = analyzer._validate_product_data(data)
    print_result(len(validated["category_keywords"]) == 3, "String keywords split to list")

    return True


def test_ollama_connection_live():
    """Test actual Ollama connection (skip if not running)."""
    print_header("Test: Ollama live connection")

    if not ollama_available():
        print_result(True, "SKIPPED — Ollama not running")
        return True

    result = check_ollama_status()
    print_result(result is True, "Ollama is reachable")

    models = get_ollama_models()
    print_result(len(models) > 0, f"Found {len(models)} models: {', '.join(models[:5])}")

    analyzer = OllamaAnalyzer()
    status = analyzer.check_ollama_status()
    print_result(isinstance(status, bool), f"Analyzer status check: {status}")

    return True


def test_ollama_analyze_live():
    """Test actual image analysis with Ollama (skip if not running)."""
    print_header("Test: Ollama live analysis")

    if not ollama_available():
        print_result(True, "SKIPPED — Ollama not running")
        return True

    if not has_vision_model():
        print_result(True, "SKIPPED — No vision model available")
        return True

    sample = Path(__file__).parent / "samples" / "test_product.jpg"
    if not sample.exists():
        print_result(True, "SKIPPED — No test image found")
        return True

    analyzer = OllamaAnalyzer()
    result = analyzer.analyze_images([str(sample)])
    print_result(isinstance(result, ProductData), "Returns ProductData")
    print_result(len(result.title) > 0, f"Title: {result.title}")
    print_result(result.confidence_score >= 0, f"Confidence: {result.confidence_score}")
    print(f"   Price: ${result.suggested_price_usd:.2f}")
    print(f"   Condition: {result.condition}")

    return True


# ========== Analyzer Factory Tests ==========

def test_analyzer_factory_openai():
    """Test factory returns ProductAnalyzer when OpenAI is requested."""
    print_header("Test: analyzer factory — openai backend")

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-fake-key"}):
        analyzer = get_analyzer("openai")
        print_result(isinstance(analyzer, ProductAnalyzer), "Returns ProductAnalyzer")

    return True


def test_analyzer_factory_ollama():
    """Test factory returns OllamaAnalyzer when Ollama is requested and running."""
    print_header("Test: analyzer factory — ollama backend")

    with patch("core.analyzer_factory.check_ollama_status", return_value=True):
        analyzer = get_analyzer("ollama")
        print_result(isinstance(analyzer, OllamaAnalyzer), "Returns OllamaAnalyzer")

    return True


def test_analyzer_factory_ollama_not_running():
    """Test factory raises when Ollama is requested but not running."""
    print_header("Test: analyzer factory — ollama not running")

    with patch("core.analyzer_factory.check_ollama_status", return_value=False):
        try:
            get_analyzer("ollama")
            print_result(False, "Should have raised RuntimeError")
            return False
        except RuntimeError as e:
            print_result("not running" in str(e).lower(), f"Correct error: {str(e)[:60]}")

    return True


def test_analyzer_factory_auto_detect():
    """Test auto-detection priority."""
    print_header("Test: analyzer factory — auto-detect")

    # Priority 1: OLLAMA_VISION_MODEL set + running
    with patch.dict(os.environ, {"OLLAMA_VISION_MODEL": "qwen3.5:2b"}, clear=False):
        with patch("core.analyzer_factory.check_ollama_status", return_value=True):
            with patch("core.analyzer_factory._backend_from_presets", return_value=None):
                analyzer = get_analyzer(None)
                print_result(isinstance(analyzer, OllamaAnalyzer), "Priority 1: OLLAMA_VISION_MODEL + running -> Ollama")

    # Priority 2: OpenAI key set
    env = {"OPENAI_API_KEY": "sk-test", "OLLAMA_VISION_MODEL": ""}
    with patch.dict(os.environ, env, clear=False):
        with patch("core.analyzer_factory.check_ollama_status", return_value=False):
            with patch("core.analyzer_factory._backend_from_presets", return_value=None):
                analyzer = get_analyzer(None)
                print_result(isinstance(analyzer, ProductAnalyzer), "Priority 2: OPENAI_API_KEY -> OpenAI")

    # Priority 3: Ollama running (no explicit env vars)
    env = {"OPENAI_API_KEY": "", "OLLAMA_VISION_MODEL": ""}
    with patch.dict(os.environ, env, clear=False):
        with patch("core.analyzer_factory.check_ollama_status", return_value=True):
            with patch("core.analyzer_factory._backend_from_presets", return_value=None):
                analyzer = get_analyzer(None)
                print_result(isinstance(analyzer, OllamaAnalyzer), "Priority 3: Ollama running -> Ollama")

    # Priority 4: Nothing available
    env = {"OPENAI_API_KEY": "", "OLLAMA_VISION_MODEL": ""}
    with patch.dict(os.environ, env, clear=False):
        with patch("core.analyzer_factory.check_ollama_status", return_value=False):
            with patch("core.analyzer_factory._backend_from_presets", return_value=None):
                try:
                    get_analyzer(None)
                    print_result(False, "Should have raised RuntimeError")
                    return False
                except RuntimeError as e:
                    print_result("no ai backend" in str(e).lower(), "Priority 4: Nothing -> clear error")

    return True


def test_detect_available_backend():
    """Test detect_available_backend utility."""
    print_header("Test: detect_available_backend")

    # Ollama env var + running
    with patch.dict(os.environ, {"OLLAMA_VISION_MODEL": "qwen3.5", "OPENAI_API_KEY": ""}, clear=False):
        with patch("core.analyzer_factory.check_ollama_status", return_value=True):
            result = detect_available_backend()
            print_result(result == "ollama", "OLLAMA_VISION_MODEL + running -> ollama")

    # OpenAI key
    with patch.dict(os.environ, {"OLLAMA_VISION_MODEL": "", "OPENAI_API_KEY": "sk-test"}, clear=False):
        with patch("core.analyzer_factory.check_ollama_status", return_value=False):
            result = detect_available_backend()
            print_result(result == "openai", "OPENAI_API_KEY -> openai")

    # Nothing
    with patch.dict(os.environ, {"OLLAMA_VISION_MODEL": "", "OPENAI_API_KEY": ""}, clear=False):
        with patch("core.analyzer_factory.check_ollama_status", return_value=False):
            result = detect_available_backend()
            print_result(result is None, "Nothing available -> None")

    return True


# ========== Presets Tests ==========

def test_presets_ai_fields():
    """Test MybayPresets AI backend fields."""
    print_header("Test: MybayPresets AI fields")

    # Default values
    presets = MybayPresets()
    print_result(presets.ai_backend == "auto", f"Default ai_backend: {presets.ai_backend}")
    print_result(presets.ollama_model == "qwen3.5:2b", f"Default ollama_model: {presets.ollama_model}")
    print_result(presets.ollama_url == "http://localhost:11434", f"Default ollama_url: {presets.ollama_url}")

    # Serialize and deserialize
    data = presets.to_dict()
    print_result("ai_backend" in data, "ai_backend in to_dict()")
    print_result("ollama_model" in data, "ollama_model in to_dict()")
    print_result("ollama_url" in data, "ollama_url in to_dict()")

    loaded = MybayPresets.from_dict(data)
    print_result(loaded.ai_backend == "auto", "Roundtrip ai_backend")
    print_result(loaded.ollama_model == "qwen3.5:2b", "Roundtrip ollama_model")

    # Custom values
    presets.ai_backend = "ollama"
    presets.ollama_model = "moondream"
    presets.ollama_url = "http://custom:9999"
    data = presets.to_dict()
    loaded = MybayPresets.from_dict(data)
    print_result(loaded.ai_backend == "ollama", "Custom ai_backend persists")
    print_result(loaded.ollama_model == "moondream", "Custom ollama_model persists")
    print_result(loaded.ollama_url == "http://custom:9999", "Custom ollama_url persists")

    # Backward compatibility: loading old data without new fields
    old_data = {
        "shipping": {},
        "returns": {},
        "location": {},
        "pricing": {},
        "turbo_mode": True,
    }
    loaded = MybayPresets.from_dict(old_data)
    print_result(loaded.ai_backend == "auto", "Old data defaults ai_backend to auto")
    print_result(loaded.ollama_model == "qwen3.5:2b", "Old data defaults ollama_model")
    print_result(loaded.turbo_mode is True, "Old data preserves turbo_mode")

    return True


def test_shared_analysis_prompt():
    """Test that OllamaAnalyzer uses the shared ANALYSIS_PROMPT."""
    print_header("Test: Shared analysis prompt")

    analyzer = OllamaAnalyzer()
    system_prompt = analyzer._build_system_prompt()
    print_result("expert eBay product listing" in system_prompt, "Contains shared ANALYSIS_PROMPT content")
    print_result("JSON" in system_prompt, "Contains JSON instruction")
    print_result("title" in system_prompt, "Contains schema fields")

    return True


# ========== Run All ==========

def run_all_tests(skip_ollama: bool = False):
    """Run all Phase 6 tests."""
    print("\n" + "=" * 60)
    print("  myBay — Phase 6 Tests (Ollama Integration)")
    print("=" * 60)

    results = []

    # Core Ollama tests (always run — use mocks)
    tests = [
        ("Ollama status check (mock)", test_ollama_check_status_mock),
        ("Ollama models list (mock)", test_get_ollama_models_mock),
        ("Ollama vision model check (mock)", test_has_vision_model_mock),
        ("Ollama analyzer init", test_ollama_analyzer_init),
        ("Ollama JSON parsing", test_ollama_json_parsing),
        ("Ollama data validation", test_ollama_validate_product_data),
        ("Shared analysis prompt", test_shared_analysis_prompt),
    ]

    if not skip_ollama:
        tests.extend([
            ("Ollama live connection", test_ollama_connection_live),
            ("Ollama live analysis", test_ollama_analyze_live),
        ])

    # Factory tests
    tests.extend([
        ("Factory: openai backend", test_analyzer_factory_openai),
        ("Factory: ollama backend", test_analyzer_factory_ollama),
        ("Factory: ollama not running", test_analyzer_factory_ollama_not_running),
        ("Factory: auto-detect", test_analyzer_factory_auto_detect),
        ("detect_available_backend", test_detect_available_backend),
    ])

    # Presets tests
    tests.append(("Presets AI fields", test_presets_ai_fields))

    for name, fn in tests:
        try:
            result = fn()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} CRASHED: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("  Results")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        icon = "✅" if result else "❌"
        print(f"  {icon} {name}")
    print(f"\n  {passed}/{total} passed\n")

    return passed == total


if __name__ == "__main__":
    skip = "--skip-ollama" in sys.argv
    success = run_all_tests(skip_ollama=skip)
    sys.exit(0 if success else 1)

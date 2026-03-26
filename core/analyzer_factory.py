"""
Analyzer Factory for myBay

Returns the appropriate AI analyzer (OpenAI or Ollama) based on
user preference, environment variables, and service availability.
"""

import os
from typing import Union

from core.vision import ProductAnalyzer, ProductData, _load_runtime_env
from core.ollama import OllamaAnalyzer, check_ollama_status


Analyzer = Union[ProductAnalyzer, OllamaAnalyzer]


def get_analyzer(backend: str = None) -> Analyzer:
    """
    Return the right analyzer based on user preference or auto-detection.

    Args:
        backend: "openai", "ollama", or None (auto-detect)

    Auto-detect priority:
      1. If OLLAMA_VISION_MODEL is set and Ollama is running -> OllamaAnalyzer
      2. If OPENAI_API_KEY is set -> ProductAnalyzer
      3. If Ollama is running (any model available) -> OllamaAnalyzer
      4. Raise with setup instructions

    Returns:
        ProductAnalyzer or OllamaAnalyzer instance
    """
    _load_runtime_env()

    # Allow presets to override if no explicit backend given
    if backend is None:
        backend = _backend_from_presets()

    if backend == "openai":
        return _make_openai_analyzer()

    if backend == "ollama":
        return _make_ollama_analyzer()

    # Auto-detect
    return _auto_detect()


def detect_available_backend() -> str | None:
    """
    Detect which backend is available without creating an analyzer.

    Returns:
        "openai", "ollama", or None if nothing is available.
    """
    _load_runtime_env()

    if os.getenv("OLLAMA_VISION_MODEL", "").strip() and check_ollama_status():
        return "ollama"

    if os.getenv("OPENAI_API_KEY", "").strip():
        return "openai"

    if check_ollama_status():
        return "ollama"

    return None


def _backend_from_presets() -> str | None:
    """Read the ai_backend preference from saved presets (if any)."""
    try:
        from core.presets import get_presets
        presets = get_presets()
        backend = getattr(presets, "ai_backend", "auto")
        if backend in ("openai", "ollama"):
            return backend
    except Exception:
        pass
    return None


def _make_openai_analyzer() -> ProductAnalyzer:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OpenAI backend selected but OPENAI_API_KEY is not set.\n"
            "Set it in your environment or .env file, or switch to Ollama (free, local)."
        )
    return ProductAnalyzer()


def _make_ollama_analyzer() -> OllamaAnalyzer:
    if not check_ollama_status():
        raise RuntimeError(
            "Ollama backend selected but Ollama is not running.\n"
            "Install: brew install ollama\n"
            "Start:   ollama serve\n"
            "Pull:    ollama pull llava:7b"
        )
    return OllamaAnalyzer()


def _auto_detect() -> Analyzer:
    """Try each backend in priority order."""
    # 1. Explicit Ollama model env var + running
    if os.getenv("OLLAMA_VISION_MODEL", "").strip() and check_ollama_status():
        return OllamaAnalyzer()

    # 2. OpenAI key present
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        return ProductAnalyzer()

    # 3. Ollama running with any model
    if check_ollama_status():
        return OllamaAnalyzer()

    # 4. Nothing available
    raise RuntimeError(
        "No AI backend available. Set up one of these:\n\n"
        "Option A — Ollama (free, local, no account needed):\n"
        "  brew install ollama && ollama serve\n"
        "  ollama pull llava:7b\n\n"
        "Option B — OpenAI (cloud, paid, best quality):\n"
        "  Set OPENAI_API_KEY in your environment or .env file\n"
        "  Get a key at https://platform.openai.com/api-keys"
    )

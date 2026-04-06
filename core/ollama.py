"""
Ollama Vision Analysis Module for myBay

Uses a local Ollama instance with vision-capable models to analyze
product images. Provides the same interface as ProductAnalyzer so
the two backends are interchangeable.

No API keys, no cost, fully private.
"""

import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Optional

import httpx

from core.vision import (
    ANALYSIS_PROMPT,
    PRODUCT_JSON_SCHEMA,
    ProductData,
    _load_runtime_env,
)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:2b"

# Ollama doesn't support OpenAI-style json_schema enforcement, so we
# embed the schema in the prompt and ask for strict JSON output.
_OLLAMA_JSON_INSTRUCTION = """
You MUST respond with ONLY a valid JSON object — no markdown, no explanation, no extra text.
The JSON must match this exact schema:

{schema}

Example output format (do NOT copy these values):
{{
  "title": "Brand Model Name Details",
  "brand": "BrandName",
  "model": "ModelNumber",
  "size": "Medium",
  "category_keywords": ["keyword1", "keyword2"],
  "condition": "GOOD",
  "color": "Black",
  "material": "Leather",
  "description": "A detailed description of the product...",
  "suggested_price_usd": 29.99,
  "confidence_score": 0.75
}}
"""


def check_ollama_status(
    base_url: str = DEFAULT_OLLAMA_URL, timeout: float = 5.0
) -> bool:
    """Check if Ollama is running and reachable."""
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def get_ollama_models(
    base_url: str = DEFAULT_OLLAMA_URL, timeout: float = 5.0
) -> list[str]:
    """Return list of model names available in the local Ollama instance."""
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        if r.status_code != 200:
            return []
        data = r.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def has_vision_model(
    base_url: str = DEFAULT_OLLAMA_URL, timeout: float = 5.0
) -> bool:
    """Check if at least one known vision-capable model is pulled."""
    models = get_ollama_models(base_url, timeout)
    vision_families = {"qwen3.5", "llava", "llama3.2-vision", "moondream", "minicpm-v", "bakllava"}
    for name in models:
        base_name = name.split(":")[0].lower()
        if base_name in vision_families:
            return True
    return False


class OllamaAnalyzer:
    """
    Analyzes product images using a local Ollama vision model.

    Drop-in alternative to ProductAnalyzer — same analyze_images() interface,
    returns the same ProductData dataclass.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: str = DEFAULT_OLLAMA_URL,
        timeout: float = 120.0,
    ):
        _load_runtime_env()

        self.model = (
            model
            or os.getenv("OLLAMA_VISION_MODEL", "").strip()
            or DEFAULT_OLLAMA_MODEL
        )
        self.base_url = (
            os.getenv("OLLAMA_URL", "").strip() or base_url
        ).rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def __del__(self):
        if hasattr(self, "_client"):
            self._client.close()

    def check_ollama_status(self) -> bool:
        """Check if Ollama is running and the configured model is available."""
        try:
            r = self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            if r.status_code != 200:
                return False
            models = [m.get("name", "") for m in r.json().get("models", [])]
            # Check exact match or base-name match (e.g. "llava:7b" matches "llava")
            for m in models:
                if m == self.model or m.startswith(self.model.split(":")[0]):
                    return True
            return False
        except Exception:
            return False

    def _encode_image_base64(self, image_path: str | Path) -> str:
        """Read an image file and return raw base64 (no data-URL prefix)."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _build_system_prompt(self) -> str:
        """Build the system prompt with JSON schema instructions."""
        schema_str = json.dumps(PRODUCT_JSON_SCHEMA["properties"], indent=2)
        return (
            ANALYSIS_PROMPT
            + "\n"
            + _OLLAMA_JSON_INSTRUCTION.format(schema=schema_str)
        )

    def analyze_images(
        self,
        image_paths: list[str | Path],
        additional_context: str = "",
    ) -> ProductData:
        """
        Analyze product images using the local Ollama model.

        Args:
            image_paths: List of paths to product images (1-5)
            additional_context: Optional extra context

        Returns:
            ProductData with analysis results
        """
        if not image_paths:
            raise ValueError("At least one image path is required")

        if len(image_paths) > 5:
            image_paths = image_paths[:5]

        # Encode images
        image_b64_list: list[str] = []
        for p in image_paths:
            try:
                image_b64_list.append(self._encode_image_base64(p))
            except FileNotFoundError as exc:
                print(f"Warning: {exc}")
                continue

        if not image_b64_list:
            raise ValueError("No valid images could be loaded")

        user_text = (
            "Analyze these product photos for an eBay listing. "
            "Return JSON only."
        )
        if additional_context:
            user_text += f"\nAdditional context: {additional_context}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                {
                    "role": "user",
                    "content": user_text,
                    "images": image_b64_list,
                },
            ],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 2048,
            },
        }

        try:
            response = self._client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            result = response.json()
            raw_text = result.get("message", {}).get("content", "")
            data = self._parse_json_response(raw_text)
            data = self._validate_product_data(data)
            return ProductData.from_dict(data)

        except httpx.TimeoutException:
            return ProductData(
                title="Analysis timed out",
                description=(
                    "Ollama took too long to respond. Try a smaller model "
                    "(e.g. moondream) or fewer images."
                ),
                confidence_score=0.0,
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else "unknown"
            body = exc.response.text[:300] if exc.response else ""
            return ProductData(
                title="Analysis failed",
                description=f"Ollama API error ({status}): {body}",
                confidence_score=0.0,
            )
        except httpx.RequestError as exc:
            return ProductData(
                title="Analysis failed",
                description=(
                    f"Could not connect to Ollama at {self.base_url}. "
                    f"Make sure Ollama is running (ollama serve). "
                    f"Details: {type(exc).__name__}: {str(exc)[:200]}"
                ),
                confidence_score=0.0,
            )

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from Ollama's response, handling common LLM quirks."""
        from core.parsing import parse_json_response
        return parse_json_response(text)

    def _validate_product_data(self, data: dict) -> dict:
        """Validate and normalize product data."""
        from core.parsing import validate_product_data
        return validate_product_data(data)


if __name__ == "__main__":
    print("Checking Ollama status...")
    analyzer = OllamaAnalyzer()

    if analyzer.check_ollama_status():
        print(f"  Ollama is running. Model: {analyzer.model}")
        models = get_ollama_models(analyzer.base_url)
        print(f"  Available models: {', '.join(models) if models else 'none'}")
    else:
        print("  Ollama is not running or model not found.")
        print("  Install: brew install ollama")
        print("  Start:   ollama serve")
        print(f"  Pull:    ollama pull {analyzer.model}")

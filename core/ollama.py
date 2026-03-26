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
                "num_predict": 1200,
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
        cleaned = text.strip()

        # Remove markdown code blocks
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            start_idx = 1
            end_idx = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "```":
                    end_idx = i
                    break
            cleaned = "\n".join(lines[start_idx:end_idx])

        # Extract first JSON object
        json_match = re.search(r"\{[\s\S]*\}", cleaned)
        if json_match:
            cleaned = json_match.group()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Attempt repair: trailing commas, unescaped newlines
        repaired = cleaned
        repaired = re.sub(r",\s*}", "}", repaired)
        repaired = re.sub(r",\s*]", "]", repaired)
        repaired = repaired.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Last resort: regex key extraction
        try:
            title = re.search(r'"title"\s*:\s*"([^"]*)"', cleaned)
            desc = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
            price = re.search(r'"suggested_price_usd"\s*:\s*([0-9.]+)', cleaned)
            conf = re.search(r'"confidence_score"\s*:\s*([0-9.]+)', cleaned)
            cond = re.search(r'"condition"\s*:\s*"([^"]*)"', cleaned)
            if title:
                return {
                    "title": title.group(1)[:80],
                    "brand": None,
                    "model": None,
                    "size": None,
                    "category_keywords": ["unknown"],
                    "condition": cond.group(1) if cond else "GOOD",
                    "color": None,
                    "material": None,
                    "description": desc.group(1)[:2000] if desc else "Parsed from partial AI response.",
                    "suggested_price_usd": float(price.group(1)) if price else 0,
                    "confidence_score": float(conf.group(1)) if conf else 0.3,
                }
        except Exception:
            pass

        return {
            "title": "Unable to analyze image",
            "brand": None,
            "model": None,
            "size": None,
            "category_keywords": ["unknown"],
            "condition": "GOOD",
            "color": None,
            "material": None,
            "description": "Ollama response parsing failed. Please try again.",
            "suggested_price_usd": 0,
            "confidence_score": 0.1,
        }

    def _validate_product_data(self, data: dict) -> dict:
        """Validate and normalize product data — mirrors ProductAnalyzer logic."""
        title = str(data.get("title", "Unknown Item")).strip()[:80]
        if not title:
            title = "Unknown Item"

        valid_conditions = {"NEW", "LIKE_NEW", "VERY_GOOD", "GOOD", "ACCEPTABLE"}
        condition = str(data.get("condition", "GOOD")).upper().replace(" ", "_")
        if condition not in valid_conditions:
            condition = "GOOD"

        keywords = data.get("category_keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",")]
        keywords = [str(k).strip() for k in keywords if str(k).strip()][:5]
        if not keywords:
            keywords = ["miscellaneous"]

        try:
            price = float(data.get("suggested_price_usd", 0))
            price = max(0.0, min(price, 100000.0))
        except (TypeError, ValueError):
            price = 0.0

        try:
            confidence = float(data.get("confidence_score", 0.5))
            confidence = max(0.0, min(confidence, 1.0))
        except (TypeError, ValueError):
            confidence = 0.5

        def clean_optional(value: object, max_len: int = 120) -> Optional[str]:
            if value is None:
                return None
            text = str(value).strip()
            return text[:max_len] if text else None

        description = str(data.get("description", "")).strip()[:2000]
        if not description:
            parts = ["Item analyzed from photos."]
            if clean_optional(data.get("brand")):
                parts.append(f"Brand appears to be {clean_optional(data.get('brand'))}.")
            if clean_optional(data.get("model")):
                parts.append(f"Model/details: {clean_optional(data.get('model'))}.")
            description = " ".join(parts)[:2000]

        return {
            "title": title,
            "brand": clean_optional(data.get("brand")),
            "model": clean_optional(data.get("model")),
            "size": clean_optional(data.get("size")),
            "category_keywords": keywords,
            "condition": condition,
            "color": clean_optional(data.get("color")),
            "material": clean_optional(data.get("material")),
            "description": description,
            "suggested_price_usd": round(price, 2),
            "confidence_score": round(confidence, 2),
        }


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

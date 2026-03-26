"""
Vision Analysis Module for myBay

Uses OpenAI's vision-capable models with built-in web search
to analyze product images and return structured listing data.
"""

import base64
import json
import mimetypes
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import httpx

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-nano-2026-03-17"


def _load_dotenv_fallback(env_path: Path) -> None:
    """
    Minimal .env parser used when python-dotenv is unavailable.
    """
    try:
        raw = env_path.read_text(encoding="utf-8")
    except Exception:
        return

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        # Remove single/double surrounding quotes.
        if len(value) >= 2 and (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def _load_runtime_env() -> None:
    """
    Load .env from common runtime locations.

    Priority is non-destructive (`override=False`), so existing environment
    variables always win.
    """
    candidates: list[Path] = []

    # User data directory (~/Library/Application Support/myBay/.env when bundled).
    try:
        from core.paths import get_user_data_dir
        candidates.append(get_user_data_dir() / ".env")
    except Exception:
        pass

    # Running from source: project root relative to this module.
    candidates.append(Path(__file__).resolve().parent.parent / ".env")
    # Running from arbitrary CWD.
    candidates.append(Path.cwd() / ".env")

    # Running from PyInstaller/macOS app bundle.
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / ".env")

        executable = Path(sys.executable).resolve()
        # .../myBay.app/Contents/MacOS/myBay -> Resources/.env
        candidates.append(executable.parent.parent / "Resources" / ".env")

    seen: set[str] = set()
    for env_path in candidates:
        key = str(env_path)
        if key in seen:
            continue
        seen.add(key)
        if env_path.exists():
            if load_dotenv is not None:
                try:
                    load_dotenv(env_path, override=False)
                    continue
                except Exception:
                    pass

            _load_dotenv_fallback(env_path)


@dataclass
class ProductData:
    """Structured product data returned by the AI vision model."""

    title: str = "Unknown Item"
    brand: Optional[str] = None
    model: Optional[str] = None  # Model name/number
    size: Optional[str] = None  # Size or measurements
    category_keywords: list[str] = field(default_factory=list)
    condition: str = "GOOD"  # NEW, LIKE_NEW, VERY_GOOD, GOOD, ACCEPTABLE
    color: Optional[str] = None
    material: Optional[str] = None
    description: str = ""
    suggested_price_usd: float = 0.0
    confidence_score: float = 0.0  # 0.0 - 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProductData":
        """Create ProductData from dictionary."""
        return cls(
            title=data.get("title", "Unknown Item"),
            brand=data.get("brand"),
            model=data.get("model"),
            size=data.get("size"),
            category_keywords=data.get("category_keywords", []),
            condition=data.get("condition", "GOOD"),
            color=data.get("color"),
            material=data.get("material"),
            description=data.get("description", ""),
            suggested_price_usd=float(data.get("suggested_price_usd", 0)),
            confidence_score=float(data.get("confidence_score", 0.5)),
        )


ANALYSIS_PROMPT = """You are an expert eBay product listing analyst.

You will receive product photos and you MUST:
1) Identify the exact or closest likely product from visible evidence.
2) Use built-in web search briefly to verify likely model/spec naming and recent market pricing.
3) Return ONLY valid JSON matching the schema exactly.

Rules:
- Never invent visible details. If uncertain, use null and lower confidence.
- Keep title <= 80 characters and optimized for eBay search.
- Prefer precise terms (brand, model, size, year, material, color) when justified.
- Suggested price must be a fair USD estimate based on condition and comparable market listings.
- Confidence should reflect identification certainty and photo clarity.

MYBAY TITLE STYLE:
[Condition Prefix] [Brand] [Model/Name] [Key Specs] [Size/Measurements] [Color] [Notable Features]

Condition enum must be one of:
NEW, LIKE_NEW, VERY_GOOD, GOOD, ACCEPTABLE
"""


PRODUCT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "title",
        "brand",
        "model",
        "size",
        "category_keywords",
        "condition",
        "color",
        "material",
        "description",
        "suggested_price_usd",
        "confidence_score",
    ],
    "properties": {
        "title": {"type": "string", "maxLength": 80},
        "brand": {"type": ["string", "null"]},
        "model": {"type": ["string", "null"]},
        "size": {"type": ["string", "null"]},
        "category_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 5,
        },
        "condition": {
            "type": "string",
            "enum": ["NEW", "LIKE_NEW", "VERY_GOOD", "GOOD", "ACCEPTABLE"],
        },
        "color": {"type": ["string", "null"]},
        "material": {"type": ["string", "null"]},
        "description": {"type": "string", "maxLength": 2000},
        "suggested_price_usd": {"type": "number", "minimum": 0},
        "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


class ProductAnalyzer:
    """
    Analyzes product images using OpenAI multimodal models + web search.

    Requires OPENAI_API_KEY in environment or .env.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = OPENAI_BASE_URL,
        timeout: float = 60.0,
    ):
        """
        Initialize the product analyzer.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use (defaults to OPENAI_VISION_MODEL or gpt-5.4-nano-2026-03-17)
            base_url: OpenAI API base URL
            timeout: Request timeout in seconds
        """
        _load_runtime_env()

        self.api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.model = (model or os.getenv("OPENAI_VISION_MODEL", DEFAULT_OPENAI_MODEL)).strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, "_client"):
            self._client.close()

    def _auth_headers(self) -> dict:
        """Build auth headers or raise if key is missing."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def check_openai_status(self) -> bool:
        """
        Check if OpenAI API key is configured and reachable.

        Returns:
            True if API appears ready, else False
        """
        try:
            headers = self._auth_headers()
            response = self._client.get(f"{self.base_url}/models/{self.model}", headers=headers)
            if response.status_code == 200:
                return True

            # Some aliases may not resolve on /models/{id}; use /models as fallback.
            if response.status_code == 404:
                fallback = self._client.get(f"{self.base_url}/models", headers=headers)
                return fallback.status_code == 200

            return False
        except Exception:
            return False

    def get_available_models(self) -> list[str]:
        """
        Get available OpenAI model IDs for this API key.

        Returns:
            List of model IDs
        """
        try:
            headers = self._auth_headers()
            response = self._client.get(f"{self.base_url}/models", headers=headers)
            if response.status_code != 200:
                return []
            payload = response.json()
            models = payload.get("data", [])
            return [m.get("id", "") for m in models if m.get("id")]
        except Exception:
            return []

    def _encode_image_as_data_url(self, image_path: str | Path) -> str:
        """
        Encode an image file into a data URL.

        Args:
            image_path: Path to image file

        Returns:
            data:image/...;base64,... URL
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            mime_type = "image/jpeg"

        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime_type};base64,{encoded}"

    def _extract_output_text(self, response_json: dict) -> str:
        """
        Extract text output from a Responses API payload.
        """
        if isinstance(response_json.get("output_text"), str) and response_json["output_text"].strip():
            return response_json["output_text"].strip()

        parts: list[str] = []
        for item in response_json.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                json_payload = content.get("json")
                if isinstance(json_payload, dict):
                    parts.append(json.dumps(json_payload))
                    continue
                text = content.get("text")
                if text:
                    parts.append(text)

        return "\n".join(parts).strip()

    def _parse_json_response(self, text: str) -> dict:
        """
        Parse JSON from model response, handling common issues.

        Args:
            text: Raw text response from the model

        Returns:
            Parsed JSON dictionary
        """
        cleaned = text.strip()

        # Remove markdown code blocks if present.
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            start_idx = 1
            end_idx = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "```":
                    end_idx = i
                    break
            cleaned = "\n".join(lines[start_idx:end_idx])

        # Extract first JSON object if extra text slipped in.
        json_match = re.search(r"\{[\s\S]*\}", cleaned)
        if json_match:
            cleaned = json_match.group()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Attempt repair: fix common issues (trailing commas, unescaped newlines)
        repaired = cleaned
        repaired = re.sub(r",\s*}", "}", repaired)  # trailing comma before }
        repaired = re.sub(r",\s*]", "]", repaired)   # trailing comma before ]
        repaired = repaired.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Last resort: extract key-value pairs with regex
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
            "description": "AI response parsing failed. Please try again.",
            "suggested_price_usd": 0,
            "confidence_score": 0.1,
        }

    def _call_responses_api(self, payload: dict) -> httpx.Response:
        """
        Call OpenAI Responses API. If web search tool is unavailable,
        retry once without it so vision analysis still works.
        """
        headers = self._auth_headers()
        response = self._post_with_retries(payload, headers)

        if response.status_code < 400:
            response = self._ensure_final_message(response, payload, headers)
            return response

        body_text = response.text.lower()
        if response.status_code == 400 and "web_search" in body_text:
            fallback_payload = dict(payload)
            fallback_payload.pop("tools", None)
            fallback_payload.pop("include", None)
            fallback = self._post_with_retries(fallback_payload, headers)
            if fallback.status_code < 400:
                fallback = self._ensure_final_message(fallback, fallback_payload, headers)
            return fallback

        return response

    def _has_message_output(self, response_json: dict) -> bool:
        """Return True when response contains assistant message content."""
        if isinstance(response_json.get("output_text"), str) and response_json["output_text"].strip():
            return True

        for item in response_json.get("output", []):
            if item.get("type") != "message":
                continue
            content = item.get("content", [])
            if content:
                return True
        return False

    def _ensure_final_message(self, response: httpx.Response, payload: dict, headers: dict) -> httpx.Response:
        """
        Some responses complete with only tool calls/reasoning and no final message.
        In that case, request a short follow-up completion using previous_response_id.
        """
        current = response
        base_tokens = int(payload.get("max_output_tokens", 900) or 900)

        for attempt in range(3):
            try:
                current_json = current.json()
            except Exception:
                return current

            if self._has_message_output(current_json):
                return current

            response_id = current_json.get("id")
            if not response_id:
                return current

            # Continue only when the model emitted reasoning/tool output
            # or explicitly ended incomplete.
            output_items = current_json.get("output", [])
            has_tool_or_reasoning = any(
                item.get("type") in {"web_search_call", "reasoning"} for item in output_items
            )
            is_incomplete = current_json.get("status") == "incomplete"
            if not has_tool_or_reasoning and not is_incomplete:
                return current

            follow_up_tokens = min(max(base_tokens * (attempt + 2), 1200), 2400)
            follow_up_payload = {
                "model": payload.get("model", self.model),
                "previous_response_id": response_id,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Return ONLY the final JSON object now. "
                                    "Do not include reasoning or extra text."
                                ),
                            }
                        ],
                    }
                ],
                "text": payload.get("text"),
                "max_output_tokens": follow_up_tokens,
                "reasoning": {"effort": "minimal"},
            }

            follow_up = self._post_with_retries(follow_up_payload, headers)
            if follow_up.status_code >= 400:
                return current
            current = follow_up

        return current

    def _post_with_retries(self, payload: dict, headers: dict, max_attempts: int = 3) -> httpx.Response:
        """
        POST to OpenAI with retries for transient network/TLS failures.
        """
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self._client.post(
                    f"{self.base_url}/responses",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= max_attempts:
                    raise
                # Brief exponential backoff for transient SSL/network issues.
                time.sleep(0.5 * attempt)

        if last_error:
            raise last_error
        raise RuntimeError("Unexpected retry flow in _post_with_retries")

    def analyze_images(
        self,
        image_paths: list[str | Path],
        additional_context: str = "",
    ) -> ProductData:
        """
        Analyze one or more product images and return structured data.

        Args:
            image_paths: List of paths to product images (1-3 recommended)
            additional_context: Optional context to help the AI

        Returns:
            ProductData with analysis results
        """
        if not image_paths:
            raise ValueError("At least one image path is required")

        if len(image_paths) > 5:
            image_paths = image_paths[:5]

        image_data_urls: list[str] = []
        for path in image_paths:
            try:
                image_data_urls.append(self._encode_image_as_data_url(path))
            except FileNotFoundError as exc:
                print(f"Warning: {exc}")
                continue

        if not image_data_urls:
            raise ValueError("No valid images could be loaded")

        user_content = [
            {
                "type": "input_text",
                "text": (
                    "Analyze these product photos for an eBay listing. "
                    "Use web search briefly to verify likely product naming and pricing. "
                    "Return JSON only."
                ),
            }
        ]

        if additional_context:
            user_content.append({"type": "input_text", "text": f"Additional context: {additional_context}"})

        for image_url in image_data_urls:
            user_content.append(
                {
                    "type": "input_image",
                    "image_url": image_url,
                    "detail": "high",
                }
            )

        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": ANALYSIS_PROMPT}]},
                {"role": "user", "content": user_content},
            ],
            "tools": [{"type": "web_search_preview", "search_context_size": "medium"}],
            "include": ["web_search_call.action.sources"],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "product_listing_analysis",
                    "strict": True,
                    "schema": PRODUCT_JSON_SCHEMA,
                }
            },
            "max_output_tokens": 900,
        }

        try:
            response = self._call_responses_api(payload)
            response.raise_for_status()

            result = response.json()
            raw_response = self._extract_output_text(result)
            data = self._parse_json_response(raw_response if raw_response else "{}")
            data = self._validate_product_data(data)
            return ProductData.from_dict(data)

        except ValueError as exc:
            # Covers missing API key from _auth_headers().
            return ProductData(
                title="AI configuration error",
                brand=None,
                model=None,
                size=None,
                category_keywords=[],
                condition="GOOD",
                color=None,
                material=None,
                description=str(exc),
                suggested_price_usd=0,
                confidence_score=0.0,
            )
        except httpx.TimeoutException:
            return ProductData(
                title="Analysis timed out",
                brand=None,
                model=None,
                size=None,
                category_keywords=[],
                condition="GOOD",
                color=None,
                material=None,
                description="The AI analysis took too long. Please try again with fewer or smaller images.",
                suggested_price_usd=0,
                confidence_score=0.0,
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else "unknown"
            body = ""
            if exc.response is not None:
                body = exc.response.text[:300]
            return ProductData(
                title="Analysis failed",
                brand=None,
                model=None,
                size=None,
                category_keywords=[],
                condition="GOOD",
                color=None,
                material=None,
                description=f"OpenAI API error ({status}): {body}",
                suggested_price_usd=0,
                confidence_score=0.0,
            )
        except httpx.RequestError as exc:
            # Includes transient TLS errors like SSLV3_ALERT_BAD_RECORD_MAC.
            return ProductData(
                title="Analysis failed",
                brand=None,
                model=None,
                size=None,
                category_keywords=[],
                condition="GOOD",
                color=None,
                material=None,
                description=(
                    "Network error while contacting OpenAI API. "
                    f"Please retry. Details: {type(exc).__name__}: {str(exc)[:220]}"
                ),
                suggested_price_usd=0,
                confidence_score=0.0,
            )

    def _validate_product_data(self, data: dict) -> dict:
        """
        Validate and normalize product data from model response.
        """
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
            if condition != "GOOD":
                parts.append(f"Condition estimated as {condition.replace('_', ' ').title()}.")
            else:
                parts.append("Condition appears used but functional.")
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


def analyze_product(
    image_paths: list[str | Path],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ProductData:
    """
    Convenience function for quick product analysis.
    """
    analyzer = ProductAnalyzer(api_key=api_key, model=model)
    return analyzer.analyze_images(image_paths)


if __name__ == "__main__":
    analyzer = ProductAnalyzer()

    print("Checking OpenAI status...")
    if analyzer.check_openai_status():
        print("✅ OpenAI API is reachable and model access looks good")
        print(f"   Model: {analyzer.model}")
    else:
        print("❌ OpenAI API is not ready")
        print("   Set OPENAI_API_KEY in your environment or .env")

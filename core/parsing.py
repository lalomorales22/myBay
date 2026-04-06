"""
Shared JSON parsing and product data validation for myBay.

Used by both ProductAnalyzer (OpenAI) and OllamaAnalyzer (Ollama)
to avoid duplicating ~100 lines of parsing/repair logic.
"""

import json
import re
from typing import Optional


def parse_json_response(text: str) -> dict:
    """
    Parse JSON from an LLM response, handling common issues like
    markdown code blocks, extra text, trailing commas, etc.

    Returns a dict with product fields, falling back to regex extraction.
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
    repaired = re.sub(r",\s*]", "]", repaired)  # trailing comma before ]
    repaired = repaired.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Truncated JSON repair: small models often run out of tokens mid-JSON.
    # Close any unclosed brackets/braces and strip trailing partial values.
    if "{" in cleaned:
        truncated = cleaned
        # Start from the first {
        brace_start = truncated.index("{")
        truncated = truncated[brace_start:]
        # Strip trailing partial key-value (e.g. `"key": 12` with no comma or brace)
        truncated = re.sub(r',\s*"?[^{}\[\]"]*$', '', truncated)
        # Close open brackets and braces
        open_brackets = truncated.count("[") - truncated.count("]")
        open_braces = truncated.count("{") - truncated.count("}")
        truncated += "]" * max(open_brackets, 0)
        truncated += "}" * max(open_braces, 0)
        # Clean trailing commas introduced by the truncation
        truncated = re.sub(r",\s*}", "}", truncated)
        truncated = re.sub(r",\s*]", "]", truncated)
        try:
            return json.loads(truncated)
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


def validate_product_data(data: dict) -> dict:
    """
    Validate and normalize product data from any model response.
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

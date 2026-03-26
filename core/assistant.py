"""
AI Business Assistant for myBay

Parses natural language messages into structured business entries
(expenses, income, mileage) using the same OpenAI API the app already uses.
"""

import json
import os
import re
import time
from datetime import date
from typing import Optional

import httpx

from core.vision import _load_runtime_env, OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL


ASSISTANT_PROMPT = """You are a business bookkeeping assistant for an eBay resale sole proprietorship.

When the user sends you a message, extract any business transactions and return them as structured JSON.

A single message may contain MULTIPLE transactions. For example "drove 40 miles to the post office to mail a bike part for 40 bucks" contains:
1. A mileage trip (40 miles, purpose: Post Office/Shipping)
2. An income entry ($40, source: ebay, description: bike part sale)

Another example: "spent $15 at goodwill on inventory and $8 on shipping tape at walmart" contains:
2 expenses.

Return a JSON object with three arrays: "expenses", "income", "mileage". Each array can be empty if that type wasn't mentioned.

Expense categories (use exactly these keys):
- inventory (buying items to resell — thrift stores, estate sales, swap meets, garage sales)
- shipping (postage, shipping labels, USPS/UPS/FedEx costs)
- supplies (packing supplies, tape, boxes, bubble wrap, mailers)
- ebay_fees (eBay seller fees, PayPal/payment processing fees)
- storage (storage unit, shelving)
- phone_internet (phone bill, internet bill for business use)
- office (office supplies, printer ink, paper)
- other (anything else)

Mileage purposes (use exactly these):
- Sourcing (driving to thrift stores, estate sales, swap meets, garage sales)
- Post Office (mailing packages)
- Supplies Run (buying packing/shipping supplies)
- Bank (bank trips)
- Other

Income sources:
- ebay (sold on eBay)
- cash (cash sale, in-person sale, swap meet sale)
- other

Rules:
- Today's date is {today}.
- If no date is mentioned, use today's date.
- If a relative date is mentioned ("yesterday", "last tuesday"), calculate the actual date.
- Always return valid JSON. No extra text.
- For mileage, the IRS rate is $0.70/mile for 2025. Just record miles, not the dollar deduction.
- If the message is just a question or greeting (not a transaction), return empty arrays and put your response in the "reply" field.
- Be smart about context: "mailed" or "shipped" with a dollar amount usually means income from a sale, not an expense.
- "Drove to goodwill" is both mileage AND potentially sourcing expense if they mention buying items.
"""

ASSISTANT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply", "expenses", "income", "mileage"],
    "properties": {
        "reply": {
            "type": "string",
        },
        "expenses": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["date", "category", "amount", "description", "vendor"],
                "properties": {
                    "date": {"type": "string"},
                    "category": {"type": "string", "enum": [
                        "inventory", "shipping", "supplies", "ebay_fees",
                        "storage", "phone_internet", "office", "other"
                    ]},
                    "amount": {"type": "number"},
                    "description": {"type": "string"},
                    "vendor": {"type": "string"},
                }
            }
        },
        "income": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["date", "source", "amount", "description",
                             "platform_fees", "shipping_cost"],
                "properties": {
                    "date": {"type": "string"},
                    "source": {"type": "string", "enum": ["ebay", "cash", "other"]},
                    "amount": {"type": "number"},
                    "description": {"type": "string"},
                    "platform_fees": {"type": "number"},
                    "shipping_cost": {"type": "number"},
                }
            }
        },
        "mileage": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["date", "purpose", "miles", "destination"],
                "properties": {
                    "date": {"type": "string"},
                    "purpose": {"type": "string", "enum": [
                        "Sourcing", "Post Office", "Supplies Run", "Bank", "Other"
                    ]},
                    "miles": {"type": "number"},
                    "destination": {"type": "string"},
                }
            }
        },
    }
}


class BusinessAssistant:
    """
    Parses natural language into structured expense/income/mileage entries.
    Uses the same OpenAI API and patterns as ProductAnalyzer.
    """

    def __init__(self, api_key: str = None, model: str = None):
        _load_runtime_env()
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.model = (model or os.getenv("OPENAI_VISION_MODEL", DEFAULT_OPENAI_MODEL)).strip()
        self.base_url = OPENAI_BASE_URL.rstrip("/")
        self._client = httpx.Client(timeout=30.0)

    def __del__(self):
        if hasattr(self, "_client"):
            self._client.close()

    def parse_message(self, message: str) -> dict:
        """
        Send a natural language message to OpenAI and get structured entries back.

        Returns dict with keys: reply, expenses, income, mileage
        """
        if not self.api_key:
            return {
                "reply": "OpenAI API key not configured. Set OPENAI_API_KEY in your environment.",
                "expenses": [], "income": [], "mileage": [],
            }

        prompt = ASSISTANT_PROMPT.replace("{today}", date.today().isoformat())

        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": message}]},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "business_entry_parser",
                    "strict": True,
                    "schema": ASSISTANT_SCHEMA,
                }
            },
            "max_output_tokens": 2000,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self._post_with_retries(payload, headers)

            if response.status_code >= 400:
                body = response.text[:300]
                return {
                    "reply": f"AI error ({response.status_code}): {body}",
                    "expenses": [], "income": [], "mileage": [],
                }

            result = response.json()
            raw = self._extract_text(result)
            parsed = self._parse_json(raw)

            # Ensure all required keys exist and are never None
            return {
                "reply": parsed.get("reply") or "Done!",
                "expenses": parsed.get("expenses") or [],
                "income": parsed.get("income") or [],
                "mileage": parsed.get("mileage") or [],
            }

        except Exception as exc:
            return {
                "reply": f"AI error: {type(exc).__name__}: {str(exc)[:200]}",
                "expenses": [], "income": [], "mileage": [],
            }

    def _post_with_retries(self, payload: dict, headers: dict,
                           max_attempts: int = 3) -> httpx.Response:
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self._client.post(
                    f"{self.base_url}/responses",
                    headers=headers, json=payload, timeout=30.0,
                )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= max_attempts:
                    raise
                time.sleep(0.5 * attempt)
        raise last_error

    def _extract_text(self, response_json: dict) -> str:
        if isinstance(response_json.get("output_text"), str):
            return response_json["output_text"].strip()

        parts = []
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

    def _parse_json(self, text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            end = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "```":
                    end = i
                    break
            cleaned = "\n".join(lines[1:end])

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            cleaned = match.group()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Attempt to repair truncated JSON by closing open brackets/braces
        repaired = cleaned
        open_braces = repaired.count("{") - repaired.count("}")
        open_brackets = repaired.count("[") - repaired.count("]")
        # Remove trailing comma or partial key
        repaired = re.sub(r',\s*"?[^{}\[\]"]*$', '', repaired)
        repaired += "]" * max(open_brackets, 0)
        repaired += "}" * max(open_braces, 0)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Last resort: extract individual arrays with regex
        result = {"reply": "", "expenses": [], "income": [], "mileage": []}
        for key in ("expenses", "income", "mileage"):
            arr_match = re.search(
                rf'"{key}"\s*:\s*\[(.*?)(?:\]|$)', cleaned, re.DOTALL
            )
            if arr_match:
                arr_text = "[" + arr_match.group(1)
                # Close any unclosed objects/arrays
                arr_text = re.sub(r',\s*"?[^{}\[\]"]*$', '', arr_text)
                ob = arr_text.count("{") - arr_text.count("}")
                arr_text += "}" * max(ob, 0)
                if not arr_text.rstrip().endswith("]"):
                    arr_text += "]"
                try:
                    result[key] = json.loads(arr_text)
                except json.JSONDecodeError:
                    pass

        reply_match = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
        if reply_match:
            result["reply"] = reply_match.group(1)

        if any(result[k] for k in ("expenses", "income", "mileage")):
            return result

        return {"reply": "I understood your message but the response was cut short. Please try again with a shorter message.",
                "expenses": [], "income": [], "mileage": []}

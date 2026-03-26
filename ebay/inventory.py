"""
eBay Inventory API for myBay

Handles creating inventory items, offers, and publishing listings.
This is the core API for getting products listed on eBay.
"""

import uuid
import hashlib
import re
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

import httpx

from .config import get_config
from .auth import get_auth


class ListingFormat(Enum):
    """eBay listing formats."""
    FIXED_PRICE = "FIXED_PRICE"
    AUCTION = "AUCTION"


class ItemCondition(Enum):
    """Common item conditions."""
    NEW = "NEW"
    LIKE_NEW = "LIKE_NEW"
    NEW_OTHER = "NEW_OTHER"
    NEW_WITH_DEFECTS = "NEW_WITH_DEFECTS"
    MANUFACTURER_REFURBISHED = "MANUFACTURER_REFURBISHED"
    CERTIFIED_REFURBISHED = "CERTIFIED_REFURBISHED"
    EXCELLENT_REFURBISHED = "EXCELLENT_REFURBISHED"
    VERY_GOOD_REFURBISHED = "VERY_GOOD_REFURBISHED"
    GOOD_REFURBISHED = "GOOD_REFURBISHED"
    SELLER_REFURBISHED = "SELLER_REFURBISHED"
    USED_EXCELLENT = "USED_EXCELLENT"
    USED_VERY_GOOD = "USED_VERY_GOOD"
    USED_GOOD = "USED_GOOD"
    USED_ACCEPTABLE = "USED_ACCEPTABLE"
    FOR_PARTS_OR_NOT_WORKING = "FOR_PARTS_OR_NOT_WORKING"


# User-friendly aliases (GUI/database values -> eBay enum values)
CONDITION_ALIASES = {
    "VERY_GOOD": "USED_VERY_GOOD",
    "GOOD": "USED_GOOD",
    "ACCEPTABLE": "USED_ACCEPTABLE",
    "EXCELLENT": "USED_EXCELLENT",
}


def normalize_item_condition(condition: ItemCondition | str | None) -> ItemCondition:
    """Normalize condition input from GUI/database into a valid ItemCondition enum."""
    if isinstance(condition, ItemCondition):
        return condition

    if condition is None:
        return ItemCondition.NEW

    if not isinstance(condition, str):
        raise ValueError(f"Invalid condition type: {type(condition).__name__}")

    key = condition.strip().upper().replace(" ", "_")
    key = CONDITION_ALIASES.get(key, key)

    try:
        return ItemCondition[key]
    except KeyError as exc:
        valid = ", ".join(c.name for c in ItemCondition)
        raise ValueError(f"Unsupported condition '{condition}'. Valid values: {valid}") from exc


# Condition ID mapping (eBay uses numeric IDs)
CONDITION_IDS = {
    ItemCondition.NEW: "1000",
    ItemCondition.LIKE_NEW: "1500",
    ItemCondition.NEW_OTHER: "1500",
    ItemCondition.NEW_WITH_DEFECTS: "1750",
    ItemCondition.MANUFACTURER_REFURBISHED: "2000",
    ItemCondition.CERTIFIED_REFURBISHED: "2000",
    ItemCondition.EXCELLENT_REFURBISHED: "2010",
    ItemCondition.VERY_GOOD_REFURBISHED: "2020",
    ItemCondition.GOOD_REFURBISHED: "2030",
    ItemCondition.SELLER_REFURBISHED: "2500",
    ItemCondition.USED_EXCELLENT: "3000",
    ItemCondition.USED_VERY_GOOD: "4000",
    ItemCondition.USED_GOOD: "5000",
    ItemCondition.USED_ACCEPTABLE: "6000",
    ItemCondition.FOR_PARTS_OR_NOT_WORKING: "7000",
}

# Preferred enum per condition ID (some IDs map to multiple enum aliases).
CONDITION_ID_TO_ENUM = {
    "1000": ItemCondition.NEW,
    "1500": ItemCondition.LIKE_NEW,
    "1750": ItemCondition.NEW_WITH_DEFECTS,
    "2000": ItemCondition.MANUFACTURER_REFURBISHED,
    "2010": ItemCondition.EXCELLENT_REFURBISHED,
    "2020": ItemCondition.VERY_GOOD_REFURBISHED,
    "2030": ItemCondition.GOOD_REFURBISHED,
    "2500": ItemCondition.SELLER_REFURBISHED,
    "3000": ItemCondition.USED_EXCELLENT,
    "4000": ItemCondition.USED_VERY_GOOD,
    "5000": ItemCondition.USED_GOOD,
    "6000": ItemCondition.USED_ACCEPTABLE,
    "7000": ItemCondition.FOR_PARTS_OR_NOT_WORKING,
}

NEW_CONDITION_IDS = {"1000", "1500", "1750"}
USED_CONDITION_IDS = {"3000", "4000", "5000", "6000", "7000"}
REFURB_CONDITION_IDS = {"2000", "2010", "2020", "2030", "2500"}


@dataclass
class Product:
    """Product details for an inventory item."""
    title: str
    description: str
    aspects: dict = field(default_factory=dict)  # Item specifics: {"Brand": ["Nike"], ...}
    image_urls: list = field(default_factory=list)
    upc: Optional[str] = None
    ean: Optional[str] = None
    isbn: Optional[str] = None
    mpn: Optional[str] = None  # Manufacturer Part Number
    brand: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to eBay API format."""
        data = {
            "title": self.title,
            "description": self.description,
        }
        
        if self.aspects:
            data["aspects"] = self.aspects
        
        if self.image_urls:
            data["imageUrls"] = self.image_urls
        
        # Product identifiers
        if self.upc:
            data.setdefault("upc", []).append(self.upc)
        if self.ean:
            data.setdefault("ean", []).append(self.ean)
        if self.isbn:
            data.setdefault("isbn", []).append(self.isbn)
        if self.mpn:
            data["mpn"] = self.mpn
        if self.brand:
            data.setdefault("aspects", {})["Brand"] = [self.brand]
        
        return data


@dataclass
class InventoryItem:
    """Complete inventory item for eBay."""
    sku: str
    product: Product
    condition: ItemCondition | str = ItemCondition.NEW
    condition_description: Optional[str] = None
    quantity: int = 1
    
    # Optional location
    merchant_location_key: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to eBay API format."""
        normalized_condition = normalize_item_condition(self.condition)
        data = {
            "product": self.product.to_dict(),
            "condition": normalized_condition.value,
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": self.quantity
                }
            }
        }
        
        if self.condition_description:
            data["conditionDescription"] = self.condition_description
        
        if self.merchant_location_key:
            data["availability"]["shipToLocationAvailability"]["availabilityDistributions"] = [{
                "merchantLocationKey": self.merchant_location_key,
                "quantity": self.quantity
            }]
        
        return data


@dataclass  
class Offer:
    """Offer (listing) details for an inventory item."""
    sku: str
    marketplace_id: str = "EBAY_US"
    format: ListingFormat = ListingFormat.FIXED_PRICE
    
    # Pricing
    price_value: float = 0.0
    price_currency: str = "USD"
    
    # Category
    category_id: str = ""
    
    # Business policies (required for publishing)
    payment_policy_id: Optional[str] = None
    return_policy_id: Optional[str] = None
    fulfillment_policy_id: Optional[str] = None
    
    # Listing options
    listing_duration: str = "GTC"  # Good Till Cancelled
    listing_description: Optional[str] = None
    merchant_location_key: Optional[str] = None
    
    # Shipping
    include_catalog_product_details: bool = True
    
    def to_dict(self) -> dict:
        """Convert to eBay API format."""
        data = {
            "sku": self.sku,
            "marketplaceId": self.marketplace_id,
            "format": self.format.value,
            "pricingSummary": {
                "price": {
                    "value": str(self.price_value),
                    "currency": self.price_currency
                }
            },
            "categoryId": self.category_id,
            "listingDuration": self.listing_duration,
            "includeCatalogProductDetails": self.include_catalog_product_details,
        }
        
        # Business policies
        if self.payment_policy_id:
            data["listingPolicies"] = data.get("listingPolicies", {})
            data["listingPolicies"]["paymentPolicyId"] = self.payment_policy_id
        if self.return_policy_id:
            data["listingPolicies"] = data.get("listingPolicies", {})
            data["listingPolicies"]["returnPolicyId"] = self.return_policy_id
        if self.fulfillment_policy_id:
            data["listingPolicies"] = data.get("listingPolicies", {})
            data["listingPolicies"]["fulfillmentPolicyId"] = self.fulfillment_policy_id
        
        if self.listing_description:
            data["listingDescription"] = self.listing_description
        
        if self.merchant_location_key:
            data["merchantLocationKey"] = self.merchant_location_key
        
        return data


@dataclass
class PublishResult:
    """Result of publishing an offer."""
    success: bool
    listing_id: Optional[str] = None
    offer_id: Optional[str] = None
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class EbayInventory:
    """
    eBay Inventory API client.
    
    Workflow for listing an item:
    1. Create inventory item (createOrReplaceInventoryItem)
    2. Create offer (createOffer)
    3. Publish offer (publishOffer)
    """
    
    def __init__(self, marketplace_id: str = "EBAY_US"):
        """
        Initialize inventory client.
        
        Args:
            marketplace_id: eBay marketplace ID
        """
        self.marketplace_id = marketplace_id
        self.config = get_config()
        self.auth = get_auth()
        self._http_client = None
        self._condition_policy_cache: dict[str, set[str]] = {}
    
    @property
    def http_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=60.0)
        return self._http_client
    
    @property
    def base_url(self) -> str:
        """Get inventory API base URL."""
        return f"{self.config.api_base_url}/sell/inventory/v1"
    
    def _get_headers(self) -> dict:
        """Get headers with user token."""
        return {
            **self.auth.get_auth_headers(),
            "Accept": "application/json",
            "Accept-Language": "en-US",
            "Content-Language": "en-US",
        }

    def _get_metadata_headers(self) -> dict:
        """Get headers for Metadata API calls."""
        return {
            **self.auth.get_auth_headers(),
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        }

    @staticmethod
    def _extract_error_id_set(errors: list) -> set[int]:
        """Extract numeric error IDs from eBay error payloads."""
        ids: set[int] = set()
        for err in errors or []:
            try:
                value = err.get("errorId")
                if value is None:
                    continue
                ids.add(int(value))
            except Exception:
                continue
        return ids

    @staticmethod
    def _condition_priority_for(requested_condition: ItemCondition) -> list[str]:
        """Return condition-ID fallback order based on the requested condition family."""
        requested_id = CONDITION_IDS.get(requested_condition, "")
        if requested_id in NEW_CONDITION_IDS:
            return [
                "1000", "1500", "1750",
                "5000", "4000", "3000", "6000", "7000",
                "2500", "2030", "2020", "2010", "2000",
            ]
        if requested_id in USED_CONDITION_IDS:
            return [
                "5000", "4000", "3000", "6000", "7000",
                "1000", "1500", "1750",
                "2500", "2030", "2020", "2010", "2000",
            ]
        if requested_id in REFURB_CONDITION_IDS:
            return [
                "2500", "2030", "2020", "2010", "2000",
                "5000", "4000", "3000", "6000", "7000",
                "1000", "1500", "1750",
            ]
        return [
            "5000", "4000", "3000", "6000", "7000",
            "1000", "1500", "1750",
            "2500", "2030", "2020", "2010", "2000",
        ]

    @classmethod
    def _pick_allowed_condition(
        cls,
        requested_condition: ItemCondition,
        allowed_condition_ids: set[str],
    ) -> ItemCondition:
        """
        Pick the best allowed condition for the listing category.

        If the requested condition is allowed, it is returned unchanged.
        Otherwise, this method selects the closest compatible fallback.
        """
        if not allowed_condition_ids:
            return requested_condition

        requested_id = CONDITION_IDS.get(requested_condition)
        if requested_id in allowed_condition_ids:
            return requested_condition

        for condition_id in cls._condition_priority_for(requested_condition):
            if condition_id in allowed_condition_ids:
                fallback = CONDITION_ID_TO_ENUM.get(condition_id)
                if fallback:
                    return fallback

        # Last resort: pick any known condition ID returned by eBay.
        for condition_id in sorted(allowed_condition_ids):
            fallback = CONDITION_ID_TO_ENUM.get(condition_id)
            if fallback:
                return fallback

        return requested_condition

    @staticmethod
    def _normalize_aspects(aspects: Optional[dict]) -> dict[str, list[str]]:
        """Normalize item specifics to {name: [values...]} with trimmed strings."""
        normalized: dict[str, list[str]] = {}
        if not isinstance(aspects, dict):
            return normalized

        for raw_name, raw_values in aspects.items():
            name = str(raw_name).strip()
            if not name:
                continue

            if isinstance(raw_values, list):
                values_iterable = raw_values
            elif raw_values is None:
                values_iterable = []
            else:
                values_iterable = [raw_values]

            cleaned_values: list[str] = []
            for value in values_iterable:
                text = str(value).strip()
                if text:
                    cleaned_values.append(text)

            if cleaned_values:
                normalized[name] = cleaned_values

        return normalized

    @staticmethod
    def _get_first_aspect_value(aspects: dict[str, list[str]], candidate_names: list[str]) -> Optional[str]:
        """Get the first value for the first matching aspect name (case-insensitive)."""
        if not aspects:
            return None

        lowered_map = {k.lower(): k for k in aspects.keys()}
        for candidate in candidate_names:
            key = lowered_map.get(candidate.lower())
            if not key:
                continue
            values = aspects.get(key) or []
            if values:
                return str(values[0]).strip()
        return None

    @staticmethod
    def _normalize_ring_size_value(value: str) -> Optional[str]:
        """Normalize ring size text into common numeric eBay format."""
        text = str(value).replace("\xa0", " ").strip()
        if not text:
            return None

        half_match = re.search(r"\b(\d{1,2})\s*1/2\b", text, re.IGNORECASE)
        if half_match:
            return f"{half_match.group(1)}.5"

        numeric_match = re.search(r"\b(\d{1,2}(?:\.\d{1,2})?)\b", text, re.IGNORECASE)
        if numeric_match:
            return numeric_match.group(1)

        return None

    @classmethod
    def _extract_ring_size_from_text(cls, title: str, description: str) -> Optional[str]:
        """Extract likely ring size from title/description text."""
        text = f"{title} {description}".replace("\xa0", " ").strip()
        if not text:
            return None

        patterns = [
            r"\bring\s*size\s*[:#-]?\s*([0-9]{1,2}(?:\.[0-9]{1,2})?)\b",
            r"\bsize\s*[:#-]?\s*([0-9]{1,2}(?:\.[0-9]{1,2})?)\b",
            r"\b([0-9]{1,2})\s*1/2\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            candidate = cls._normalize_ring_size_value(match.group(0))
            if candidate:
                return candidate

        return None

    @classmethod
    def _infer_item_specific_value(
        cls,
        specific_name: str,
        title: str,
        description: str,
        aspects: dict[str, list[str]],
    ) -> Optional[str]:
        """Infer a required item specific value from existing aspects/title/description."""
        normalized = str(specific_name).replace("\xa0", " ").strip().lower()
        if not normalized:
            return None

        alias_map = {
            "ring size": ["Ring Size", "Size", "US Ring Size", "RingSize"],
            "size": ["Size", "Ring Size", "US Ring Size"],
            "brand": ["Brand"],
            "color": ["Color", "Colour"],
            "material": ["Material"],
            "model": ["Model", "MPN"],
        }

        alias_candidates = alias_map.get(normalized, [specific_name])
        existing_value = cls._get_first_aspect_value(aspects, alias_candidates)
        if existing_value:
            if normalized == "ring size":
                return cls._normalize_ring_size_value(existing_value) or existing_value
            return existing_value

        if normalized in {"ring size", "size"}:
            inferred = cls._extract_ring_size_from_text(title=title, description=description)
            if inferred:
                return inferred

        return None

    @staticmethod
    def _extract_missing_item_specifics(errors: list) -> list[str]:
        """Extract missing item-specific names from eBay error payloads."""
        missing: list[str] = []
        seen: set[str] = set()
        pattern = re.compile(r"item specific\s+(.+?)\s+is missing", re.IGNORECASE)

        def add_candidate(value: str):
            cleaned = str(value).replace("\xa0", " ").strip(" .:\t")
            if not cleaned:
                return
            key = cleaned.lower()
            if key in seen:
                return
            seen.add(key)
            missing.append(cleaned)

        for err in errors or []:
            if not isinstance(err, dict):
                continue

            for field in ("message", "longMessage"):
                raw = str(err.get(field, "")).replace("\xa0", " ")
                match = pattern.search(raw)
                if match:
                    add_candidate(match.group(1))

            for param in err.get("parameters", []) or []:
                value = str(param.get("value", "")).replace("\xa0", " ").strip()
                if not value:
                    continue
                lower_value = value.lower()
                # Ignore full sentence variants and keep likely specific names.
                if "item specific" in lower_value and "missing" in lower_value:
                    continue
                if len(value) > 80:
                    continue
                if re.search(r"[A-Za-z]", value):
                    add_candidate(value)

        return missing

    @classmethod
    def _apply_missing_item_specifics(
        cls,
        aspects: dict[str, list[str]],
        missing_specifics: list[str],
        title: str,
        description: str,
    ) -> tuple[dict[str, list[str]], list[str], list[str]]:
        """
        Attempt to populate missing required item specifics.

        Returns:
            (updated_aspects, unresolved_specific_names, messages_about_autofill)
        """
        updated_aspects = {k: list(v) for k, v in aspects.items()}
        unresolved: list[str] = []
        messages: list[str] = []

        for specific_name in missing_specifics:
            current = cls._get_first_aspect_value(updated_aspects, [specific_name])
            if current:
                continue

            inferred = cls._infer_item_specific_value(
                specific_name=specific_name,
                title=title,
                description=description,
                aspects=updated_aspects,
            )
            if inferred:
                updated_aspects[specific_name] = [inferred]
                messages.append(f"Auto-filled missing item specific '{specific_name}' with '{inferred}'.")
            else:
                unresolved.append(specific_name)

        return updated_aspects, unresolved, messages
    
    def generate_sku(self, product_title: str) -> str:
        """
        Generate a unique SKU for a product.
        
        Args:
            product_title: Product title for SKU base
            
        Returns:
            Unique SKU string
        """
        # Create short hash from title + UUID
        unique_id = f"{product_title}-{uuid.uuid4().hex[:8]}"
        short_hash = hashlib.md5(unique_id.encode()).hexdigest()[:10].upper()
        
        # Prefix with MYBAY for identification
        return f"MYBAY-{short_hash}"
    
    # ========== Inventory Item Methods ==========
    
    def create_or_replace_inventory_item(self, item: InventoryItem) -> bool:
        """
        Create or replace an inventory item.
        
        Args:
            item: InventoryItem object
            
        Returns:
            True if successful
        """
        url = f"{self.base_url}/inventory_item/{item.sku}"
        
        response = self.http_client.put(
            url,
            headers=self._get_headers(),
            json=item.to_dict()
        )
        
        if response.status_code in (200, 201, 204):
            return True
        
        error_data = response.json()
        raise ValueError(
            f"Failed to create inventory item: {error_data.get('errors', response.text)}"
        )
    
    def get_inventory_item(self, sku: str) -> dict:
        """Get an inventory item by SKU."""
        url = f"{self.base_url}/inventory_item/{sku}"
        
        response = self.http_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        return response.json()
    
    def get_inventory_items(self, limit: int = 25, offset: int = 0) -> dict:
        """Get all inventory items."""
        url = f"{self.base_url}/inventory_item"
        params = {"limit": limit, "offset": offset}
        
        response = self.http_client.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        
        return response.json()
    
    def delete_inventory_item(self, sku: str) -> bool:
        """Delete an inventory item."""
        url = f"{self.base_url}/inventory_item/{sku}"
        
        response = self.http_client.delete(url, headers=self._get_headers())
        return response.status_code in (200, 204)
    
    # ========== Offer Methods ==========
    
    def create_offer(self, offer: Offer) -> str:
        """
        Create an offer for an inventory item.
        
        Args:
            offer: Offer object
            
        Returns:
            The offer ID
        """
        url = f"{self.base_url}/offer"
        
        response = self.http_client.post(
            url,
            headers=self._get_headers(),
            json=offer.to_dict()
        )
        
        if response.status_code in (200, 201):
            offer_id = ""
            try:
                data = response.json()
                offer_id = str(data.get("offerId", "")).strip()
            except ValueError:
                pass

            # Some 201 responses only return offer ID in the Location header.
            if not offer_id:
                location = response.headers.get("Location", "")
                if location:
                    offer_id = location.rstrip("/").split("/")[-1]

            if offer_id:
                return offer_id

            raise ValueError("Failed to create offer: eBay response did not include an offerId.")

        try:
            error_data = response.json()
        except ValueError:
            error_data = {}

        errors = error_data.get("errors", []) if isinstance(error_data, dict) else []
        error_ids = self._extract_error_id_set(errors)

        # Reuse the existing offer when SKU already has an offer entity.
        if 25002 in error_ids:
            existing_offer_id = self._extract_offer_id_from_errors(errors)
            if existing_offer_id:
                try:
                    updated = self.update_offer(existing_offer_id, offer)
                    if not updated:
                        print(
                            f"Warning: Existing offer {existing_offer_id} found for SKU {offer.sku}, "
                            "but update returned non-success. Continuing with existing offer."
                        )
                    return existing_offer_id
                except Exception as e:
                    print(
                        f"Warning: Existing offer {existing_offer_id} found for SKU {offer.sku}, "
                        f"but update failed ({e}). Continuing with existing offer."
                    )
                    return existing_offer_id

        raise ValueError(
            f"Failed to create offer: {error_data.get('errors', response.text)}"
        )

    @staticmethod
    def _extract_offer_id_from_errors(errors: list) -> Optional[str]:
        """Extract offerId from eBay error payload parameters when present."""
        for err in errors or []:
            for param in err.get("parameters", []):
                name = str(param.get("name", "")).strip().lower()
                if name != "offerid":
                    continue
                value = str(param.get("value", "")).strip()
                if value:
                    return value
        return None

    @staticmethod
    def _normalize_listing_id(listing_id: Optional[str]) -> Optional[str]:
        """
        Normalize eBay listing identifiers.

        eBay may return plain legacy item IDs (e.g., 110588827413) or
        REST-style IDs (e.g., v1|110588827413|0). For browser links, use
        the legacy numeric ID when present.
        """
        if listing_id is None:
            return None

        raw = str(listing_id).strip()
        if not raw:
            return None

        if "|" in raw:
            for token in raw.split("|"):
                token = token.strip()
                if token.isdigit():
                    return token

        return raw

    @classmethod
    def _extract_listing_id(cls, payload: dict) -> Optional[str]:
        """Extract a usable listing/item ID from known eBay payload shapes."""
        if not isinstance(payload, dict):
            return None

        candidates = [
            payload.get("listingId"),
            payload.get("itemId"),
            payload.get("legacyItemId"),
        ]

        listing_obj = payload.get("listing")
        if isinstance(listing_obj, dict):
            candidates.extend(
                [
                    listing_obj.get("listingId"),
                    listing_obj.get("itemId"),
                    listing_obj.get("legacyItemId"),
                ]
            )

        for candidate in candidates:
            normalized = cls._normalize_listing_id(candidate)
            if normalized:
                return normalized

        return None
    
    def get_offer(self, offer_id: str) -> dict:
        """Get an offer by ID."""
        url = f"{self.base_url}/offer/{offer_id}"
        
        response = self.http_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        return response.json()
    
    def get_offers(self, sku: Optional[str] = None, limit: int = 25, offset: int = 0) -> dict:
        """Get offers, optionally filtered by SKU."""
        url = f"{self.base_url}/offer"
        params = {"limit": limit, "offset": offset}
        if sku:
            params["sku"] = sku
        
        response = self.http_client.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        
        return response.json()
    
    def update_offer(self, offer_id: str, offer: Offer) -> bool:
        """Update an existing offer."""
        url = f"{self.base_url}/offer/{offer_id}"
        
        response = self.http_client.put(
            url,
            headers=self._get_headers(),
            json=offer.to_dict()
        )
        
        return response.status_code in (200, 204)
    
    def delete_offer(self, offer_id: str) -> bool:
        """Delete an unpublished offer."""
        url = f"{self.base_url}/offer/{offer_id}"
        
        response = self.http_client.delete(url, headers=self._get_headers())
        return response.status_code in (200, 204)
    
    # ========== Publish Methods ==========
    
    def publish_offer(self, offer_id: str) -> PublishResult:
        """
        Publish an offer to create a live eBay listing.
        
        Args:
            offer_id: The offer ID to publish
            
        Returns:
            PublishResult with listing ID if successful
        """
        url = f"{self.base_url}/offer/{offer_id}/publish"
        
        response = self.http_client.post(url, headers=self._get_headers())
        
        if response.status_code in (200, 201):
            try:
                data = response.json()
            except ValueError:
                data = {}

            listing_id = self._extract_listing_id(data)
            warnings = data.get("warnings", []) if isinstance(data, dict) else []

            # Fallback: fetch offer details in case listingId wasn't in publish response.
            if not listing_id:
                try:
                    offer_payload = self.get_offer(offer_id)
                    listing_id = self._extract_listing_id(offer_payload)
                except Exception:
                    pass

            if listing_id:
                return PublishResult(
                    success=True,
                    listing_id=listing_id,
                    offer_id=offer_id,
                    warnings=warnings
                )

            return PublishResult(
                success=False,
                offer_id=offer_id,
                errors=[{
                    "message": (
                        "Offer published, but eBay did not return a usable listing ID. "
                        "Check Seller Hub and retry opening from Recent Activity."
                    )
                }],
                warnings=warnings,
            )

        try:
            error_data = response.json()
            errors = error_data.get("errors", [])
        except ValueError:
            errors = [{"message": response.text or f"HTTP {response.status_code}"}]

        return PublishResult(
            success=False,
            offer_id=offer_id,
            errors=errors
        )
    
    def withdraw_offer(self, offer_id: str) -> bool:
        """
        Withdraw (end) a published listing.
        
        The offer remains and can be republished later.
        """
        url = f"{self.base_url}/offer/{offer_id}/withdraw"
        
        response = self.http_client.post(url, headers=self._get_headers())
        return response.status_code in (200, 204)
    
    def get_listing_fees(self, offers: list[Offer]) -> list[dict]:
        """
        Get estimated listing fees for offers.
        
        Args:
            offers: List of Offer objects
            
        Returns:
            List of fee estimates
        """
        url = f"{self.base_url}/offer/get_listing_fees"
        
        data = {
            "offers": [o.to_dict() for o in offers]
        }
        
        response = self.http_client.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        
        return response.json().get("feeSummaries", [])

    def get_item_web_url(self, legacy_item_id: str) -> Optional[str]:
        """
        Get canonical eBay web URL for a published listing ID.

        Args:
            legacy_item_id: Numeric eBay listing/item ID

        Returns:
            Canonical itemWebUrl if found, otherwise None
        """
        if not legacy_item_id:
            return None

        url = f"{self.config.api_base_url}/buy/browse/v1/item/get_item_by_legacy_id"
        params = {"legacy_item_id": str(legacy_item_id)}
        headers = self.auth.get_auth_headers()
        headers["Accept"] = "application/json"

        response = self.http_client.get(url, params=params, headers=headers)
        if response.status_code != 200:
            return None

        try:
            data = response.json()
        except ValueError:
            return None

        item_web_url = data.get("itemWebUrl")
        return str(item_web_url).strip() if item_web_url else None
    
    # ========== Location Methods ==========
    
    def create_location(
        self,
        location_key: str,
        name: str,
        postal_code: str,
        state: str,
        country: str = "US"
    ) -> bool:
        """
        Create a merchant location (required for inventory).
        
        Args:
            location_key: Unique identifier for location
            name: Display name
            postal_code: ZIP/postal code
            state: State/province
            country: Country code
            
        Returns:
            True if successful
        """
        url = f"{self.base_url}/location/{location_key}"
        
        data = {
            "location": {
                "address": {
                    "postalCode": postal_code,
                    "stateOrProvince": state,
                    "country": country
                }
            },
            "name": name,
            "merchantLocationStatus": "ENABLED",
            "locationTypes": ["WAREHOUSE"]
        }
        
        response = self.http_client.post(url, headers=self._get_headers(), json=data)
        if response.status_code in (200, 201, 204):
            return True

        # Treat "already exists" as success.
        try:
            payload = response.json()
            for err in payload.get("errors", []):
                if err.get("errorId") == 25803:
                    return True
        except Exception:
            pass

        return False
    
    def get_locations(self) -> dict:
        """Get all merchant locations."""
        url = f"{self.base_url}/location"
        
        # Some environments return 400 for this list endpoint; caller should handle fallback.
        response = self.http_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        return response.json()

    def get_location(self, location_key: str) -> dict:
        """Get a specific merchant location by key."""
        url = f"{self.base_url}/location/{location_key}"
        response = self.http_client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def _get_default_location_values(self) -> tuple[str, str, str, str]:
        """
        Get default location values (name, postal_code, state, country).
        Uses myBay presets when available, with sandbox-friendly fallbacks.
        """
        location_name = "myBay Default Warehouse"
        postal_code = "95125"
        state = "CA"
        country = "US"

        try:
            from core.presets import get_presets
            presets = get_presets()
            loc = presets.location
            if loc.postal_code:
                postal_code = loc.postal_code
            if loc.state:
                state = loc.state
            if loc.country:
                country = loc.country
            if loc.city:
                location_name = f"{loc.city} Warehouse"
        except Exception:
            pass

        return location_name, postal_code, state, country

    def ensure_merchant_location(self, location_key: Optional[str] = None) -> str:
        """
        Ensure a merchant location exists and return its key.
        """
        key = location_key or f"MYBAYDEFAULT-{self.marketplace_id}"

        # Fast path: location already exists.
        try:
            self.get_location(key)
            return key
        except Exception:
            pass

        name, postal_code, state, country = self._get_default_location_values()
        created = self.create_location(
            location_key=key,
            name=name,
            postal_code=postal_code,
            state=state,
            country=country,
        )
        if not created:
            raise ValueError(
                "Could not create merchant location required for publishing. "
                "Please set a valid location (city/state/ZIP) in setup and try again."
            )
        return key
    
    # ========== Business Policies ==========

    # ========== Category Condition Policies ==========

    def get_item_condition_policies(self, category_ids: Optional[list[str]] = None) -> list:
        """
        Get category condition policies from Metadata API.

        Returns list of itemConditionPolicy objects.
        """
        url = (
            f"{self.config.api_base_url}/sell/metadata/v1/marketplace/"
            f"{self.marketplace_id}/get_item_condition_policies"
        )
        params = {}
        if category_ids:
            trimmed = [str(c).strip() for c in category_ids if str(c).strip()]
            if trimmed:
                params["filter"] = f"categoryIds:{{{'|'.join(trimmed)}}}"

        response = self.http_client.get(
            url,
            params=params or None,
            headers=self._get_metadata_headers(),
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("itemConditionPolicies", [])

        error_detail = self._format_account_api_error(response)
        raise ValueError(f"Failed to fetch item condition policies. {error_detail}")

    def get_allowed_condition_ids(self, category_id: str) -> set[str]:
        """
        Get allowed condition IDs for a category, using a small in-memory cache.
        """
        normalized_category_id = str(category_id).strip()
        if not normalized_category_id:
            return set()

        cached = self._condition_policy_cache.get(normalized_category_id)
        if cached is not None:
            return cached

        policies = self.get_item_condition_policies([normalized_category_id])

        allowed: set[str] = set()
        # Prefer exact match for requested category.
        for policy in policies:
            if str(policy.get("categoryId", "")).strip() != normalized_category_id:
                continue
            for condition in policy.get("itemConditions", []):
                condition_id = str(condition.get("conditionId", "")).strip()
                if condition_id:
                    allowed.add(condition_id)
            break

        # Fallback to the first non-empty policy payload if exact match was absent.
        if not allowed:
            for policy in policies:
                for condition in policy.get("itemConditions", []):
                    condition_id = str(condition.get("conditionId", "")).strip()
                    if condition_id:
                        allowed.add(condition_id)
                if allowed:
                    break

        self._condition_policy_cache[normalized_category_id] = allowed
        return allowed
    
    def _get_account_headers(self) -> dict:
        """Get headers for Account API calls."""
        return {
            **self.auth.get_auth_headers(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _format_account_api_error(response: httpx.Response) -> str:
        """Format Account API errors into a readable message."""
        detail = f"HTTP {response.status_code}"
        try:
            data = response.json()
        except ValueError:
            text = response.text.strip()
            if text:
                return f"{detail}: {text[:300]}"
            return detail

        errors = data.get("errors", []) if isinstance(data, dict) else []
        if not errors:
            return detail

        messages = []
        for err in errors:
            short = err.get("message")
            long_msg = err.get("longMessage")
            if short and long_msg and short != long_msg:
                messages.append(f"{short} ({long_msg})")
            elif long_msg:
                messages.append(long_msg)
            elif short:
                messages.append(short)

        if messages:
            return f"{detail}: {'; '.join(messages)}"
        return detail

    def _get_account_policy_collection(
        self,
        endpoint: str,
        response_key: str,
        policy_label: str,
    ) -> list:
        """Fetch a policy collection from the Account API."""
        url = f"{self.config.api_base_url}/sell/account/v1/{endpoint}"
        params = {"marketplace_id": self.marketplace_id}

        response = self.http_client.get(url, params=params, headers=self._get_account_headers())
        if response.status_code == 200:
            data = response.json()
            return data.get(response_key, [])

        error_detail = self._format_account_api_error(response)
        raise ValueError(f"Failed to fetch {policy_label} policies. {error_detail}")
    
    def get_fulfillment_policies(self) -> list:
        """Get seller's fulfillment/shipping policies."""
        return self._get_account_policy_collection(
            endpoint="fulfillment_policy",
            response_key="fulfillmentPolicies",
            policy_label="fulfillment",
        )
    
    def get_payment_policies(self) -> list:
        """Get seller's payment policies."""
        return self._get_account_policy_collection(
            endpoint="payment_policy",
            response_key="paymentPolicies",
            policy_label="payment",
        )
    
    def get_return_policies(self) -> list:
        """Get seller's return policies."""
        return self._get_account_policy_collection(
            endpoint="return_policy",
            response_key="returnPolicies",
            policy_label="return",
        )
    
    def get_default_policies(self) -> dict:
        """
        Get default policy IDs for listing.
        
        Returns dict with payment_policy_id, return_policy_id, fulfillment_policy_id
        or empty dict if policies not found.
        """
        policies = {}
        
        # Get first available payment policy
        payment_policies = self.get_payment_policies()
        if payment_policies:
            policies["payment_policy_id"] = payment_policies[0].get("paymentPolicyId")
        
        # Get first available return policy
        return_policies = self.get_return_policies()
        if return_policies:
            policies["return_policy_id"] = return_policies[0].get("returnPolicyId")
        
        # Get first available fulfillment policy
        fulfillment_policies = self.get_fulfillment_policies()
        if fulfillment_policies:
            policies["fulfillment_policy_id"] = fulfillment_policies[0].get("fulfillmentPolicyId")
        
        return policies

    def opt_in_to_program(self, program_type: str = "SELLING_POLICY_MANAGEMENT") -> bool:
        """
        Opt the seller account into an Account API program.

        Common use case in sandbox: SELLING_POLICY_MANAGEMENT.
        """
        url = f"{self.config.api_base_url}/sell/account/v1/program/opt_in"
        payload = {"programType": program_type}

        response = self.http_client.post(
            url,
            headers=self._get_account_headers(),
            json=payload,
        )

        if response.status_code in (200, 204, 409):
            return True

        # eBay can return 400/409 with "already exists" semantics
        try:
            data = response.json()
            for err in data.get("errors", []):
                if err.get("errorId") == 25803:
                    return True
        except ValueError:
            pass

        error_detail = self._format_account_api_error(response)
        raise ValueError(f"Program opt-in failed for {program_type}. {error_detail}")

    def get_opted_in_programs(self) -> list[str]:
        """Get seller programs currently opted in for this account."""
        url = f"{self.config.api_base_url}/sell/account/v1/program/get_opted_in_programs"
        response = self.http_client.get(url, headers=self._get_account_headers())

        if response.status_code != 200:
            error_detail = self._format_account_api_error(response)
            raise ValueError(f"Failed to fetch opted-in programs. {error_detail}")

        data = response.json()
        programs = data.get("programs", []) if isinstance(data, dict) else []
        return [p.get("programType", "") for p in programs if p.get("programType")]
    
    # ========== High-Level Helper ==========
    
    def quick_list(
        self,
        title: str,
        description: str,
        price: float,
        category_id: str,
        image_urls: list[str],
        sku: Optional[str] = None,
        condition: ItemCondition | str = ItemCondition.NEW,
        quantity: int = 1,
        listing_format: str = "FIXED_PRICE",
        aspects: dict = None,
        condition_description: str = None,
        payment_policy_id: str = None,
        return_policy_id: str = None,
        fulfillment_policy_id: str = None,
        merchant_location_key: str = None,
    ) -> PublishResult:
        """
        Quick helper to list an item in one call.
        
        Creates inventory item, offer, and publishes.
        
        Args:
            title: Product title
            description: Product description
            price: Listing price
            category_id: eBay category ID
            image_urls: List of image URLs
            sku: Optional custom SKU (if omitted, one is generated)
            condition: Item condition
            quantity: Quantity available
            listing_format: "FIXED_PRICE" or "AUCTION"
            aspects: Item specifics dict
            condition_description: Description of condition (for used items)
            payment_policy_id: Payment policy ID (auto-fetched if not provided)
            return_policy_id: Return policy ID (auto-fetched if not provided)
            fulfillment_policy_id: Fulfillment/shipping policy ID (auto-fetched if not provided)
            
        Returns:
            PublishResult
        """
        policy_lookup_error = None
        condition_adjustment_message = None

        # Auto-fetch business policies if not provided
        if not payment_policy_id or not return_policy_id or not fulfillment_policy_id:
            try:
                default_policies = self.get_default_policies()
                if not payment_policy_id:
                    payment_policy_id = default_policies.get("payment_policy_id")
                if not return_policy_id:
                    return_policy_id = default_policies.get("return_policy_id")
                if not fulfillment_policy_id:
                    fulfillment_policy_id = default_policies.get("fulfillment_policy_id")
            except Exception as e:
                policy_lookup_error = str(e)
                print(f"Warning: Could not fetch default policies: {e}")
        
        # Check if we have all required policies
        missing_policies = []
        if not payment_policy_id:
            missing_policies.append("Payment")
        if not return_policy_id:
            missing_policies.append("Return")
        if not fulfillment_policy_id:
            missing_policies.append("Fulfillment/Shipping")
        
        if missing_policies:
            active_env = self.config.environment.value
            message_parts = [
                f"Missing business policies: {', '.join(missing_policies)}."
            ]

            if policy_lookup_error:
                message_parts.append(f"Policy lookup error: {policy_lookup_error}.")

            if active_env == "sandbox":
                try:
                    opted_programs = self.get_opted_in_programs()
                except Exception as e:
                    opted_programs = []
                    message_parts.append(f"Could not verify sandbox opted-in programs: {e}.")

                if "SELLING_POLICY_MANAGEMENT" in opted_programs:
                    message_parts.append(
                        "Sandbox account is already opted into SELLING_POLICY_MANAGEMENT, but no "
                        "business policies were found for this account/marketplace. Create Payment, "
                        "Return, and Fulfillment policies in https://www.bizpolicy.sandbox.ebay.com "
                        "while logged into this same sandbox seller user."
                    )
                else:
                    message_parts.append(
                        "Sandbox account is not opted into Business Policies yet. "
                        "Visit https://www.bizpolicy.sandbox.ebay.com, opt into "
                        "SELLING_POLICY_MANAGEMENT, then create Payment, Return, and Fulfillment policies."
                    )
            else:
                message_parts.append(
                    "Create Payment, Return, and Fulfillment policies in eBay Seller Hub "
                    "(Account settings > Business policies)."
                )

            message_parts.append(f"Marketplace: {self.marketplace_id}.")
            message_parts.append(f"Active environment: {active_env}.")
            return PublishResult(
                success=False,
                errors=[{
                    "message": " ".join(message_parts)
                }]
            )
        
        # Generate SKU
        sku = sku or self.generate_sku(title)
        listing_aspects = self._normalize_aspects(aspects)
        
        # Create product
        product = Product(
            title=title,
            description=description,
            image_urls=image_urls,
            aspects=listing_aspects
        )
        
        # Normalize condition from GUI/database values to eBay enum values
        try:
            normalized_condition = normalize_item_condition(condition)
        except ValueError as e:
            return PublishResult(
                success=False,
                errors=[{"message": f"Invalid item condition: {e}"}]
            )

        # Validate selected condition against category policy and auto-fallback when needed.
        try:
            allowed_condition_ids = self.get_allowed_condition_ids(category_id)
            adjusted_condition = self._pick_allowed_condition(
                requested_condition=normalized_condition,
                allowed_condition_ids=allowed_condition_ids,
            )
            if adjusted_condition != normalized_condition:
                requested_id = CONDITION_IDS.get(normalized_condition, "unknown")
                adjusted_id = CONDITION_IDS.get(adjusted_condition, "unknown")
                condition_adjustment_message = (
                    f"Requested condition {normalized_condition.value} ({requested_id}) is not valid "
                    f"for category {category_id}. Using {adjusted_condition.value} ({adjusted_id})."
                )
                print(f"Warning: {condition_adjustment_message}")
                normalized_condition = adjusted_condition
        except Exception as e:
            print(f"Warning: Could not validate category condition policy: {e}")

        # Ensure merchant location exists so Item.Country is present during publish.
        try:
            merchant_location_key = self.ensure_merchant_location(merchant_location_key)
        except Exception as e:
            return PublishResult(
                success=False,
                errors=[{"message": f"Missing/invalid item location: {e}"}]
            )

        # Create inventory item
        item = InventoryItem(
            sku=sku,
            product=product,
            condition=normalized_condition,
            condition_description=condition_description,
            quantity=quantity,
            merchant_location_key=merchant_location_key,
        )
        
        try:
            self.create_or_replace_inventory_item(item)
        except Exception as e:
            return PublishResult(
                success=False,
                errors=[{"message": f"Failed to create inventory item: {e}"}]
            )
        
        # Create offer
        # Convert string format to enum
        format_enum = ListingFormat.AUCTION if listing_format == "AUCTION" else ListingFormat.FIXED_PRICE
        
        offer = Offer(
            sku=sku,
            marketplace_id=self.marketplace_id,
            format=format_enum,
            price_value=price,
            category_id=category_id,
            payment_policy_id=payment_policy_id,
            return_policy_id=return_policy_id,
            fulfillment_policy_id=fulfillment_policy_id,
            merchant_location_key=merchant_location_key,
        )
        
        try:
            offer_id = self.create_offer(offer)
        except Exception as e:
            missing_specifics = self._extract_missing_item_specifics([{"message": str(e)}])
            if missing_specifics:
                return PublishResult(
                    success=False,
                    errors=[{
                        "message": (
                            f"Missing required item specifics for category {category_id}: "
                            f"{', '.join(missing_specifics)}. Add these specifics and retry."
                        )
                    }]
                )
            return PublishResult(
                success=False,
                errors=[{"message": f"Failed to create offer: {e}"}]
            )
        
        # Publish
        result = self.publish_offer(offer_id)

        # Retry once with NEW if eBay rejects condition/category pairing at publish time.
        error_ids = self._extract_error_id_set(result.errors)
        if not result.success and 25021 in error_ids and normalized_condition != ItemCondition.NEW:
            retry_message = (
                f"Condition {normalized_condition.value} was rejected for category {category_id} "
                "at publish time. Retrying with NEW."
            )
            print(f"Warning: {retry_message}")
            retry_item = InventoryItem(
                sku=sku,
                product=product,
                condition=ItemCondition.NEW,
                condition_description=None,
                quantity=quantity,
                merchant_location_key=merchant_location_key,
            )
            try:
                self.create_or_replace_inventory_item(retry_item)
                retry_result = self.publish_offer(offer_id)
                if retry_result.success:
                    retry_result.warnings = list(retry_result.warnings or [])
                    retry_result.warnings.append({"message": retry_message})
                    if condition_adjustment_message:
                        retry_result.warnings.append({"message": condition_adjustment_message})
                    return retry_result
                result = retry_result
            except Exception as e:
                print(f"Warning: Retry with NEW condition failed before publish: {e}")

        # Retry once if eBay reports missing required item specifics.
        missing_specifics = self._extract_missing_item_specifics(result.errors)
        if not result.success and missing_specifics:
            retry_aspects, unresolved_specifics, autofill_messages = self._apply_missing_item_specifics(
                aspects=listing_aspects,
                missing_specifics=missing_specifics,
                title=title,
                description=description,
            )

            for message in autofill_messages:
                print(f"Warning: {message}")

            if retry_aspects != listing_aspects:
                retry_product = Product(
                    title=title,
                    description=description,
                    image_urls=image_urls,
                    aspects=retry_aspects,
                )
                retry_item = InventoryItem(
                    sku=sku,
                    product=retry_product,
                    condition=normalized_condition,
                    condition_description=condition_description,
                    quantity=quantity,
                    merchant_location_key=merchant_location_key,
                )
                try:
                    self.create_or_replace_inventory_item(retry_item)
                    retry_result = self.publish_offer(offer_id)
                    if retry_result.success:
                        retry_result.warnings = list(retry_result.warnings or [])
                        for message in autofill_messages:
                            retry_result.warnings.append({"message": message})
                        if condition_adjustment_message:
                            retry_result.warnings.append({"message": condition_adjustment_message})
                        return retry_result
                    result = retry_result
                except Exception as e:
                    print(f"Warning: Retry with auto-filled item specifics failed: {e}")

            if unresolved_specifics:
                hint = (
                    "Missing required item specifics: "
                    + ", ".join(unresolved_specifics)
                    + ". Add these values in the draft and retry publish."
                )
                errors = list(result.errors or [])
                errors.insert(0, {"message": hint})
                result.errors = errors

        if result.success and condition_adjustment_message:
            result.warnings = list(result.warnings or [])
            result.warnings.append({"message": condition_adjustment_message})
        return result
    
    def close(self):
        """Close the HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


# Convenience functions

_inventory: Optional[EbayInventory] = None


def get_inventory() -> EbayInventory:
    """Get the global inventory instance."""
    global _inventory
    if _inventory is None:
        _inventory = EbayInventory()
    return _inventory

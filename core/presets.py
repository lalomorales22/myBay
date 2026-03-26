"""
Smart Defaults ("myBay Presets") for myBay

Stores user preferences that are auto-applied to every listing:
- Preferred shipping method
- Return policy
- Handling time
- Default item location
- Markup percentage
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json

from data.database import get_db


@dataclass
class ShippingPreset:
    """Shipping preferences."""
    carrier: str = "USPS"
    service: str = "USPS Ground Advantage"
    handling_time: int = 1  # Business days
    free_shipping: bool = False
    flat_rate: Optional[float] = None  # None = calculated
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ShippingPreset":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ReturnPreset:
    """Return policy preferences."""
    returns_accepted: bool = True
    return_period: int = 30  # Days
    return_shipping_paid_by: str = "Buyer"  # or "Seller"
    refund_method: str = "MONEY_BACK"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ReturnPreset":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LocationPreset:
    """Item location preferences."""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "US"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "LocationPreset":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @property
    def display_string(self) -> str:
        """Get displayable location string."""
        parts = [self.city, self.state, self.postal_code]
        return ", ".join(p for p in parts if p)


@dataclass
class PricingPreset:
    """Pricing preferences."""
    markup_percent: float = 0.0  # Applied to AI suggested price
    round_to_99: bool = True  # Round prices to .99
    minimum_price: float = 5.00  # Minimum listing price
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "PricingPreset":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def apply_to_price(self, price: float) -> float:
        """Apply pricing rules to a base price."""
        # Apply markup
        price = price * (1 + self.markup_percent / 100)
        
        # Apply minimum
        price = max(price, self.minimum_price)
        
        # Round to .99 if enabled
        if self.round_to_99:
            price = int(price) + 0.99
        
        return price


@dataclass
class MybayPresets:
    """
    All of the user's preferences in one object.
    
    Usage:
        presets = MybayPresets.load()
        presets.shipping.handling_time = 2
        presets.save()
    """
    shipping: ShippingPreset = field(default_factory=ShippingPreset)
    returns: ReturnPreset = field(default_factory=ReturnPreset)
    location: LocationPreset = field(default_factory=LocationPreset)
    pricing: PricingPreset = field(default_factory=PricingPreset)
    
    # eBay policy IDs (from seller hub)
    payment_policy_id: str = ""
    return_policy_id: str = ""
    fulfillment_policy_id: str = ""
    
    # AI backend
    ai_backend: str = "auto"  # "openai", "ollama", "auto"
    ollama_model: str = "qwen3.5:2b"
    ollama_url: str = "http://localhost:11434"

    # Feature toggles
    turbo_mode: bool = False
    turbo_threshold: float = 0.90
    auto_remove_background: bool = True
    
    # Completed setup?
    setup_completed: bool = False
    
    def to_dict(self) -> dict:
        return {
            "shipping": self.shipping.to_dict(),
            "returns": self.returns.to_dict(),
            "location": self.location.to_dict(),
            "pricing": self.pricing.to_dict(),
            "payment_policy_id": self.payment_policy_id,
            "return_policy_id": self.return_policy_id,
            "fulfillment_policy_id": self.fulfillment_policy_id,
            "ai_backend": self.ai_backend,
            "ollama_model": self.ollama_model,
            "ollama_url": self.ollama_url,
            "turbo_mode": self.turbo_mode,
            "turbo_threshold": self.turbo_threshold,
            "auto_remove_background": self.auto_remove_background,
            "setup_completed": self.setup_completed,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MybayPresets":
        return cls(
            shipping=ShippingPreset.from_dict(data.get("shipping", {})),
            returns=ReturnPreset.from_dict(data.get("returns", {})),
            location=LocationPreset.from_dict(data.get("location", {})),
            pricing=PricingPreset.from_dict(data.get("pricing", {})),
            payment_policy_id=data.get("payment_policy_id", ""),
            return_policy_id=data.get("return_policy_id", ""),
            fulfillment_policy_id=data.get("fulfillment_policy_id", ""),
            ai_backend=data.get("ai_backend", "auto"),
            ollama_model=data.get("ollama_model", "qwen3.5:2b"),
            ollama_url=data.get("ollama_url", "http://localhost:11434"),
            turbo_mode=data.get("turbo_mode", False),
            turbo_threshold=data.get("turbo_threshold", 0.90),
            auto_remove_background=data.get("auto_remove_background", True),
            setup_completed=data.get("setup_completed", False),
        )
    
    def save(self):
        """Save presets to database."""
        db = get_db()
        db.set_setting("mybay_presets", json.dumps(self.to_dict()))
        
        # Also save individual settings for easy access
        db.set_setting("turbo_mode", "1" if self.turbo_mode else "0")
        db.set_setting("turbo_threshold", str(self.turbo_threshold))
        db.set_setting("markup_percent", str(self.pricing.markup_percent))
        db.set_setting("ebay_payment_policy_id", self.payment_policy_id)
        db.set_setting("ebay_return_policy_id", self.return_policy_id)
        db.set_setting("ebay_fulfillment_policy_id", self.fulfillment_policy_id)
    
    @classmethod
    def load(cls) -> "MybayPresets":
        """Load presets from database."""
        db = get_db()
        data = db.get_setting("mybay_presets")
        if data:
            try:
                return cls.from_dict(json.loads(data))
            except:
                pass
        return cls()
    
    @property
    def is_ready_to_list(self) -> bool:
        """Check if all required settings are configured."""
        return bool(
            self.payment_policy_id and
            self.return_policy_id and
            self.fulfillment_policy_id and
            self.location.postal_code
        )
    
    @property
    def missing_settings(self) -> list[str]:
        """Get list of missing required settings."""
        missing = []
        if not self.payment_policy_id:
            missing.append("Payment Policy")
        if not self.return_policy_id:
            missing.append("Return Policy")
        if not self.fulfillment_policy_id:
            missing.append("Shipping Policy")
        if not self.location.postal_code:
            missing.append("Item Location")
        return missing


# Global presets instance
_presets: Optional[MybayPresets] = None


def get_presets() -> MybayPresets:
    """Get the global presets instance."""
    global _presets
    if _presets is None:
        _presets = MybayPresets.load()
    return _presets


def save_presets(presets: MybayPresets):
    """Save presets and update global instance."""
    global _presets
    presets.save()
    _presets = presets


def needs_setup() -> bool:
    """Check if first-run setup is needed."""
    presets = get_presets()
    return not presets.setup_completed


# CLI interface
if __name__ == "__main__":
    presets = get_presets()
    
    print("=" * 50)
    print("  myBay Presets")
    print("=" * 50)
    print(f"\n📦 Shipping:")
    print(f"   Carrier: {presets.shipping.carrier}")
    print(f"   Service: {presets.shipping.service}")
    print(f"   Handling: {presets.shipping.handling_time} day(s)")
    
    print(f"\n↩️ Returns:")
    print(f"   Accepted: {'Yes' if presets.returns.returns_accepted else 'No'}")
    print(f"   Period: {presets.returns.return_period} days")
    
    print(f"\n📍 Location: {presets.location.display_string or 'Not set'}")
    
    print(f"\n💰 Pricing:")
    print(f"   Markup: {presets.pricing.markup_percent}%")
    print(f"   Round to .99: {'Yes' if presets.pricing.round_to_99 else 'No'}")
    
    print(f"\n⚡ Turbo Mode: {'ON' if presets.turbo_mode else 'OFF'}")
    print(f"   Threshold: {presets.turbo_threshold*100:.0f}%")
    
    print(f"\n✅ Setup Complete: {'Yes' if presets.setup_completed else 'No'}")
    
    if not presets.is_ready_to_list:
        print(f"\n⚠️ Missing: {', '.join(presets.missing_settings)}")

"""
eBay API Integration for myBay

This package provides easy access to eBay's APIs for:
- OAuth authentication
- Category/taxonomy suggestions  
- Inventory management and listing creation

Quick Start:
    1. Configure credentials:
        >>> from ebay import setup_credentials
        >>> setup_credentials(
        ...     client_id="your_client_id",
        ...     client_secret="your_client_secret", 
        ...     ru_name="your_runame",
        ...     environment="sandbox"  # or "production"
        ... )
    
    2. Authenticate (opens browser):
        >>> from ebay import start_auth_flow
        >>> start_auth_flow()
    
    3. Use the APIs:
        >>> from ebay import suggest_category, get_inventory
        >>> 
        >>> # Find category for product
        >>> categories = suggest_category("vintage camera")
        >>> print(categories[0].category_name)
        >>>
        >>> # List an item
        >>> inv = get_inventory()
        >>> result = inv.quick_list(
        ...     title="Vintage Polaroid Camera",
        ...     description="Great condition vintage camera",
        ...     price=49.99,
        ...     category_id=categories[0].category_id,
        ...     image_urls=["https://example.com/camera.jpg"],
        ... )
"""

# Config
from .config import (
    get_config,
    EbayConfig,
    EbayCredentials,
    EbayTokens,
    EbayEnvironment,
    DEFAULT_SCOPES,
)

# Auth
from .auth import (
    get_auth,
    start_auth_flow,
    get_token,
    get_headers,
    EbayAuth,
)

# Taxonomy
from .taxonomy import (
    get_taxonomy,
    suggest_category,
    get_required_aspects,
    EbayTaxonomy,
    CategorySuggestion,
    ItemAspect,
)

# Inventory
from .inventory import (
    get_inventory,
    EbayInventory,
    Product,
    InventoryItem,
    Offer,
    PublishResult,
    ItemCondition,
    ListingFormat,
)

# Images
from .images import (
    get_images,
    upload_image,
    upload_images,
    EbayImages,
    ImageUploadResult,
    BatchUploadResult,
)

# Pricing Intelligence
from .pricing import (
    get_pricing,
    get_market_price,
    get_market_price_sync,
    PricingIntelligence,
    PricingAnalysis,
    ComparableItem,
)


def setup_credentials(
    client_id: str,
    client_secret: str,
    ru_name: str,
    environment: str = "sandbox"
):
    """
    Configure eBay API credentials.
    
    Args:
        client_id: eBay App ID (Client ID)
        client_secret: eBay Cert ID (Client Secret)
        ru_name: RuName from eBay developer portal
        environment: "sandbox" or "production"
    """
    config = get_config()
    config.setup_credentials(
        client_id=client_id,
        client_secret=client_secret,
        ru_name=ru_name,
        environment=environment
    )


def is_configured() -> bool:
    """Check if eBay credentials are configured."""
    return get_config().is_configured


def is_authenticated() -> bool:
    """Check if we have a valid eBay access token."""
    return get_config().has_valid_token


__all__ = [
    # Setup
    "setup_credentials",
    "is_configured",
    "is_authenticated",
    
    # Config
    "get_config",
    "EbayConfig",
    "EbayCredentials",
    "EbayTokens",
    "EbayEnvironment",
    "DEFAULT_SCOPES",
    
    # Auth
    "get_auth",
    "start_auth_flow",
    "get_token",
    "get_headers",
    "EbayAuth",
    
    # Taxonomy
    "get_taxonomy",
    "suggest_category",
    "get_required_aspects",
    "EbayTaxonomy",
    "CategorySuggestion",
    "ItemAspect",
    
    # Inventory
    "get_inventory",
    "EbayInventory",
    "Product",
    "InventoryItem",
    "Offer",
    "PublishResult",
    "ItemCondition",
    "ListingFormat",
    
    # Images
    "get_images",
    "upload_image",
    "upload_images",
    "EbayImages",
    "ImageUploadResult",
    "BatchUploadResult",

    # Pricing Intelligence
    "get_pricing",
    "get_market_price",
    "get_market_price_sync",
    "PricingIntelligence",
    "PricingAnalysis",
    "ComparableItem",
]

"""
eBay Taxonomy API for myBay

Handles category suggestions and item aspects/specifics.
Uses application tokens (no user auth required).
"""

from typing import Optional
from dataclasses import dataclass, field

import httpx

from .config import get_config, APP_TOKEN_SCOPES, EbayEnvironment
from .auth import get_auth


@dataclass
class CategorySuggestion:
    """eBay category suggestion."""
    category_id: str
    category_name: str
    category_tree_node_level: int
    relevancy: str  # "HIGH", "MEDIUM", "LOW"
    ancestors: list = field(default_factory=list)  # Breadcrumb path
    
    @property
    def full_path(self) -> str:
        """Get full category path."""
        if self.ancestors:
            return " > ".join([a["categoryName"] for a in self.ancestors] + [self.category_name])
        return self.category_name


@dataclass  
class ItemAspect:
    """eBay item aspect (item specific)."""
    name: str
    required: bool
    data_type: str  # "STRING", "NUMBER", "DATE", etc.
    mode: str  # "FREE_TEXT", "SELECTION_ONLY"
    values: list = field(default_factory=list)  # Predefined values
    usage: str = "RECOMMENDED"  # "REQUIRED", "RECOMMENDED", "OPTIONAL"
    
    @property
    def is_required(self) -> bool:
        return self.usage == "REQUIRED" or self.required


class EbayTaxonomy:
    """
    eBay Taxonomy API client.
    
    Provides category suggestions and item aspects for listings.
    """
    
    # US marketplace tree ID
    DEFAULT_TREE_ID = "0"  
    
    def __init__(self, marketplace_id: str = "EBAY_US"):
        """
        Initialize taxonomy client.
        
        Args:
            marketplace_id: eBay marketplace ID (default: EBAY_US)
        """
        self.marketplace_id = marketplace_id
        self.config = get_config()
        self._http_client = None
        self._app_token: Optional[str] = None
    
    @property
    def http_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0)
        return self._http_client
    
    @property
    def base_url(self) -> str:
        """Get taxonomy API base URL."""
        return f"{self.config.api_base_url}/commerce/taxonomy/v1"
    
    def _get_headers(self) -> dict:
        """Get headers with application token."""
        # Taxonomy API uses application token (no user auth needed)
        if self._app_token is None:
            auth = get_auth()
            self._app_token = auth.get_application_token(scopes=APP_TOKEN_SCOPES)
        
        return {
            "Authorization": f"Bearer {self._app_token}",
            "Accept": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
        }
    
    def get_default_category_tree_id(self) -> str:
        """
        Get the default category tree ID for the marketplace.
        
        Returns:
            Category tree ID string
        """
        url = f"{self.base_url}/get_default_category_tree_id"
        params = {"marketplace_id": self.marketplace_id}
        
        response = self.http_client.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        
        data = response.json()
        return data.get("categoryTreeId", self.DEFAULT_TREE_ID)
    
    def get_category_suggestions(
        self, 
        query: str, 
        tree_id: Optional[str] = None
    ) -> list[CategorySuggestion]:
        """
        Get category suggestions based on a product query.
        
        Args:
            query: Product name/keywords to search
            tree_id: Category tree ID (defaults to US tree)
            
        Returns:
            List of CategorySuggestion objects sorted by relevancy
        """
        # eBay documents this endpoint as unsupported in Sandbox.
        if self.config.environment == EbayEnvironment.SANDBOX:
            return []

        tree_id = tree_id or self.DEFAULT_TREE_ID
        url = f"{self.base_url}/category_tree/{tree_id}/get_category_suggestions"
        params = {"q": query}
        
        response = self.http_client.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        
        data = response.json()
        suggestions = []
        
        for item in data.get("categorySuggestions", []):
            category = item.get("category", {})
            suggestions.append(CategorySuggestion(
                category_id=category.get("categoryId", ""),
                category_name=category.get("categoryName", ""),
                category_tree_node_level=item.get("categoryTreeNodeLevel", 0),
                relevancy=item.get("relevancy", "MEDIUM"),
                ancestors=category.get("categoryAncestorIds", []),
            ))
        
        return suggestions
    
    def get_item_aspects(
        self, 
        category_id: str,
        tree_id: Optional[str] = None
    ) -> list[ItemAspect]:
        """
        Get item aspects (specifics) for a category.
        
        Args:
            category_id: eBay category ID
            tree_id: Category tree ID (defaults to US tree)
            
        Returns:
            List of ItemAspect objects
        """
        tree_id = tree_id or self.DEFAULT_TREE_ID
        url = f"{self.base_url}/category_tree/{tree_id}/get_item_aspects_for_category"
        params = {"category_id": category_id}
        
        response = self.http_client.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        
        data = response.json()
        aspects = []
        
        for item in data.get("aspects", []):
            constraint = item.get("aspectConstraint", {})
            values_list = item.get("aspectValues", [])
            
            aspects.append(ItemAspect(
                name=item.get("localizedAspectName", ""),
                required=constraint.get("aspectRequired", False),
                data_type=constraint.get("aspectDataType", "STRING"),
                mode=constraint.get("aspectMode", "FREE_TEXT"),
                values=[v.get("localizedValue", "") for v in values_list],
                usage=constraint.get("aspectUsage", "RECOMMENDED"),
            ))
        
        return aspects
    
    def get_category_subtree(
        self, 
        category_id: str,
        tree_id: Optional[str] = None
    ) -> dict:
        """
        Get category subtree (children categories).
        
        Args:
            category_id: Parent category ID
            tree_id: Category tree ID
            
        Returns:
            Raw category subtree data
        """
        tree_id = tree_id or self.DEFAULT_TREE_ID
        url = f"{self.base_url}/category_tree/{tree_id}/get_category_subtree"
        params = {"category_id": category_id}
        
        response = self.http_client.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        
        return response.json()
    
    def close(self):
        """Close the HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


# Convenience functions

_taxonomy: Optional[EbayTaxonomy] = None


def get_taxonomy() -> EbayTaxonomy:
    """Get the global taxonomy instance."""
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = EbayTaxonomy()
    return _taxonomy


def suggest_category(product_name: str) -> list[CategorySuggestion]:
    """
    Quick helper to get category suggestions for a product.
    
    Args:
        product_name: Name/description of the product
        
    Returns:
        List of suggested categories
    """
    return get_taxonomy().get_category_suggestions(product_name)


def get_required_aspects(category_id: str) -> list[ItemAspect]:
    """
    Get required item aspects for a category.
    
    Args:
        category_id: eBay category ID
        
    Returns:
        List of required aspects only
    """
    all_aspects = get_taxonomy().get_item_aspects(category_id)
    return [a for a in all_aspects if a.is_required]


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m ebay.taxonomy <product_name>")
        print("Example: python -m ebay.taxonomy 'vintage camera'")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    print(f"\n🔍 Finding categories for: {query}\n")
    
    try:
        suggestions = suggest_category(query)
        
        if not suggestions:
            print("No categories found")
            sys.exit(0)
        
        print(f"Found {len(suggestions)} category suggestions:\n")
        
        for i, cat in enumerate(suggestions[:5], 1):
            print(f"  {i}. {cat.category_name}")
            print(f"     ID: {cat.category_id}")
            print(f"     Relevancy: {cat.relevancy}")
            if cat.full_path != cat.category_name:
                print(f"     Path: {cat.full_path}")
            print()
        
        # Show aspects for top suggestion
        top = suggestions[0]
        print(f"\n📋 Required aspects for '{top.category_name}':\n")
        
        aspects = get_required_aspects(top.category_id)
        for aspect in aspects[:10]:
            values_hint = ""
            if aspect.values:
                values_hint = f" (e.g., {', '.join(aspect.values[:3])})"
            print(f"  • {aspect.name}{values_hint}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

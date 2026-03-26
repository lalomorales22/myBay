"""
Pricing Intelligence for myBay

Uses eBay's Browse API to find comparable sold items and suggest
optimal pricing based on market data.

Features:
- Search for similar sold items
- Calculate average market price
- Warn if price is below/above market
- Get price range (min/max/median)
"""

import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from statistics import mean, median

import httpx

from .auth import get_auth
from .config import get_config


# Browse API base URLs
BROWSE_API_SANDBOX = "https://api.sandbox.ebay.com/buy/browse/v1"
BROWSE_API_PRODUCTION = "https://api.ebay.com/buy/browse/v1"


@dataclass
class ComparableItem:
    """A comparable item found on eBay."""
    title: str
    price: float
    currency: str = "USD"
    condition: str = "NEW"
    item_id: str = ""
    image_url: str = ""
    seller_rating: Optional[float] = None
    
    def __repr__(self):
        return f"ComparableItem({self.title[:30]}... ${self.price:.2f})"


@dataclass 
class PricingAnalysis:
    """Analysis of market pricing for a product."""
    query: str
    comparable_count: int
    
    # Price statistics
    average_price: float
    median_price: float
    min_price: float
    max_price: float
    
    # Recommendations
    suggested_price: float
    price_range_low: float
    price_range_high: float
    
    # Comparable items
    comparables: list[ComparableItem] = field(default_factory=list)
    
    def __repr__(self):
        return (
            f"PricingAnalysis(avg=${self.average_price:.2f}, "
            f"median=${self.median_price:.2f}, "
            f"suggested=${self.suggested_price:.2f}, "
            f"{self.comparable_count} comps)"
        )
    
    def is_price_too_low(self, price: float, threshold: float = 0.20) -> bool:
        """Check if a price is more than threshold% below market."""
        return price < (self.suggested_price * (1 - threshold))
    
    def is_price_too_high(self, price: float, threshold: float = 0.30) -> bool:
        """Check if a price is more than threshold% above market."""
        return price > (self.suggested_price * (1 + threshold))
    
    def get_price_advice(self, price: float) -> str:
        """Get advice on a proposed price."""
        if self.comparable_count == 0:
            return "⚠️ No market data available"
        
        if self.is_price_too_low(price):
            pct = ((self.suggested_price - price) / self.suggested_price) * 100
            return f"⚠️ Price is {pct:.0f}% below market (${self.suggested_price:.2f})"
        elif self.is_price_too_high(price):
            pct = ((price - self.suggested_price) / self.suggested_price) * 100
            return f"📈 Price is {pct:.0f}% above market (${self.suggested_price:.2f})"
        else:
            return f"✅ Price is competitive (market: ${self.suggested_price:.2f})"


class PricingIntelligence:
    """
    Provides market pricing intelligence using eBay's Browse API.
    
    Usage:
        pricing = PricingIntelligence()
        analysis = await pricing.analyze("Nike Air Max 90")
        print(analysis.suggested_price)
        print(analysis.get_price_advice(my_price))
    """
    
    def __init__(self):
        self.config = get_config()
        self.auth = get_auth()
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def base_url(self) -> str:
        """Get the API base URL for current environment."""
        if self.config.credentials and self.config.credentials.environment == "production":
            return BROWSE_API_PRODUCTION
        return BROWSE_API_SANDBOX
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def _get_headers(self) -> dict:
        """Get headers with authentication."""
        # Browse API uses application tokens, not user tokens
        token = self.auth.get_application_token()
        if not token:
            # Try to get one
            token = await self._get_app_token()
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        }
    
    async def _get_app_token(self) -> str:
        """Get an application token using client credentials flow."""
        import base64
        
        if not self.config.credentials:
            raise ValueError("eBay credentials not configured")
        
        creds = self.config.credentials
        auth_string = f"{creds.client_id}:{creds.client_secret}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        
        token_url = (
            "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
            if creds.environment == "sandbox"
            else "https://api.ebay.com/identity/v1/oauth2/token"
        )
        
        client = await self._get_client()
        response = await client.post(
            token_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {auth_base64}",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token", "")
        
        return ""
    
    def _clean_query(self, query: str) -> str:
        """Clean up a search query."""
        # Remove special characters
        query = re.sub(r'[^\w\s-]', ' ', query)
        # Collapse whitespace
        query = ' '.join(query.split())
        # Truncate if too long
        return query[:100]
    
    async def search_items(
        self,
        query: str,
        limit: int = 20,
        condition: str = None,
        min_price: float = None,
        max_price: float = None,
    ) -> list[ComparableItem]:
        """
        Search for comparable items on eBay.
        
        Args:
            query: Search keywords
            limit: Max results to return
            condition: Filter by condition (NEW, USED, etc.)
            min_price: Minimum price filter
            max_price: Maximum price filter
            
        Returns:
            List of comparable items
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        # Build filters
        filters = ["buyingOptions:{FIXED_PRICE}", "priceCurrency:USD"]
        if condition:
            filters.append(f"conditions:{{{condition}}}")
        if min_price:
            filters.append(f"price:[{min_price}..{max_price or ''}]")
        elif max_price:
            filters.append(f"price:[..{max_price}]")
        
        params = {
            "q": self._clean_query(query),
            "limit": str(limit),
            "filter": ",".join(filters),
            "sort": "price",
        }
        
        try:
            response = await client.get(
                f"{self.base_url}/item_summary/search",
                headers=headers,
                params=params,
            )
            
            if response.status_code != 200:
                print(f"Browse API error: {response.status_code}")
                return []
            
            data = response.json()
            items = []
            
            for item in data.get("itemSummaries", []):
                price_info = item.get("price", {})
                items.append(ComparableItem(
                    title=item.get("title", ""),
                    price=float(price_info.get("value", 0)),
                    currency=price_info.get("currency", "USD"),
                    condition=item.get("condition", ""),
                    item_id=item.get("itemId", ""),
                    image_url=item.get("image", {}).get("imageUrl", ""),
                ))
            
            return items
            
        except Exception as e:
            print(f"Error searching items: {e}")
            return []
    
    async def analyze(
        self,
        query: str,
        condition: str = None,
        current_price: float = None,
    ) -> PricingAnalysis:
        """
        Analyze market pricing for a product.
        
        Args:
            query: Product title or keywords
            condition: Item condition filter
            current_price: Your proposed price (for comparison)
            
        Returns:
            PricingAnalysis with market insights
        """
        # Search for comparable items
        comparables = await self.search_items(
            query=query,
            limit=20,
            condition=condition,
        )
        
        if not comparables:
            # Return empty analysis
            return PricingAnalysis(
                query=query,
                comparable_count=0,
                average_price=0,
                median_price=0,
                min_price=0,
                max_price=0,
                suggested_price=current_price or 0,
                price_range_low=0,
                price_range_high=0,
                comparables=[],
            )
        
        # Extract prices
        prices = [c.price for c in comparables if c.price > 0]
        
        if not prices:
            return PricingAnalysis(
                query=query,
                comparable_count=0,
                average_price=0,
                median_price=0,
                min_price=0,
                max_price=0,
                suggested_price=current_price or 0,
                price_range_low=0,
                price_range_high=0,
                comparables=comparables,
            )
        
        # Calculate statistics
        avg_price = mean(prices)
        med_price = median(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        # Suggested price: slightly below median for faster sales
        suggested = med_price * 0.95
        
        # Price range: 10th to 90th percentile approximation
        sorted_prices = sorted(prices)
        low_idx = max(0, len(sorted_prices) // 10)
        high_idx = min(len(sorted_prices) - 1, len(sorted_prices) * 9 // 10)
        
        return PricingAnalysis(
            query=query,
            comparable_count=len(comparables),
            average_price=avg_price,
            median_price=med_price,
            min_price=min_price,
            max_price=max_price,
            suggested_price=suggested,
            price_range_low=sorted_prices[low_idx],
            price_range_high=sorted_prices[high_idx],
            comparables=comparables,
        )
    
    def analyze_sync(
        self,
        query: str,
        condition: str = None,
        current_price: float = None,
    ) -> PricingAnalysis:
        """Synchronous wrapper for analyze()."""
        return asyncio.run(self.analyze(query, condition, current_price))
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_pricing: Optional[PricingIntelligence] = None


def get_pricing() -> PricingIntelligence:
    """Get the global pricing intelligence instance."""
    global _pricing
    if _pricing is None:
        _pricing = PricingIntelligence()
    return _pricing


async def get_market_price(title: str, condition: str = None) -> PricingAnalysis:
    """
    Quick helper to get market pricing for a product.
    
    Usage:
        analysis = await get_market_price("Nike Air Max 90")
        print(f"Market price: ${analysis.suggested_price}")
    """
    pricing = get_pricing()
    return await pricing.analyze(title, condition)


def get_market_price_sync(title: str, condition: str = None) -> PricingAnalysis:
    """Synchronous version of get_market_price()."""
    return asyncio.run(get_market_price(title, condition))


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m ebay.pricing 'product search query'")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    print(f"\n🔍 Searching for: {query}\n")
    
    analysis = get_market_price_sync(query)
    
    if analysis.comparable_count == 0:
        print("❌ No comparable items found")
    else:
        print(f"📊 Found {analysis.comparable_count} comparable items")
        print(f"\n💰 Price Analysis:")
        print(f"   Average:    ${analysis.average_price:.2f}")
        print(f"   Median:     ${analysis.median_price:.2f}")
        print(f"   Range:      ${analysis.min_price:.2f} - ${analysis.max_price:.2f}")
        print(f"\n✨ Suggested Price: ${analysis.suggested_price:.2f}")
        print(f"   Competitive Range: ${analysis.price_range_low:.2f} - ${analysis.price_range_high:.2f}")

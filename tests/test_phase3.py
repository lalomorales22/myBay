"""
Tests for eBay API Integration (Phase 3)

Tests the eBay module structure and functionality without actual API calls.
"""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEbayConfig(unittest.TestCase):
    """Test eBay configuration management."""
    
    def test_import_config(self):
        """Test that config module can be imported."""
        from ebay.config import (
            EbayConfig,
            EbayCredentials,
            EbayTokens,
            EbayEnvironment,
            ENDPOINTS,
            DEFAULT_SCOPES,
        )
        
        # Check environment endpoints exist
        self.assertIn(EbayEnvironment.SANDBOX, ENDPOINTS)
        self.assertIn(EbayEnvironment.PRODUCTION, ENDPOINTS)
        
        # Check scopes are defined
        self.assertIsInstance(DEFAULT_SCOPES, list)
        self.assertTrue(len(DEFAULT_SCOPES) > 0)
    
    def test_credentials_basic_auth(self):
        """Test credentials Basic auth encoding."""
        from ebay.config import EbayCredentials
        
        creds = EbayCredentials(
            client_id="test_client_id",
            client_secret="test_client_secret",
            ru_name="test_runame"
        )
        
        auth = creds.get_basic_auth()
        self.assertTrue(auth.startswith("Basic "))
        
        # Verify Base64 encoding
        import base64
        encoded = auth.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()
        self.assertEqual(decoded, "test_client_id:test_client_secret")
    
    def test_credentials_serialization(self):
        """Test credentials to/from dict."""
        from ebay.config import EbayCredentials
        
        creds = EbayCredentials(
            client_id="test_id",
            client_secret="test_secret",
            ru_name="test_ru",
            environment="production"
        )
        
        data = creds.to_dict()
        restored = EbayCredentials.from_dict(data)
        
        self.assertEqual(creds.client_id, restored.client_id)
        self.assertEqual(creds.client_secret, restored.client_secret)
        self.assertEqual(creds.ru_name, restored.ru_name)
        self.assertEqual(creds.environment, restored.environment)
    
    def test_tokens_expiry_check(self):
        """Test token expiry checking."""
        from ebay.config import EbayTokens
        import time
        
        # Fresh token (not expired)
        tokens = EbayTokens(
            access_token="test_token",
            token_type="Bearer",
            expires_in=7200,  # 2 hours
            access_token_created=time.time()
        )
        self.assertFalse(tokens.is_access_token_expired())
        
        # Expired token
        expired_tokens = EbayTokens(
            access_token="test_token",
            token_type="Bearer",
            expires_in=7200,
            access_token_created=time.time() - 8000  # Created 2+ hours ago
        )
        self.assertTrue(expired_tokens.is_access_token_expired())
    
    def test_config_with_temp_file(self):
        """Test config save/load with temporary file."""
        from ebay.config import EbayConfig
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            config_path = Path(f.name)
        
        try:
            config = EbayConfig(config_path=config_path)
            
            # Initially not configured
            self.assertFalse(config.is_configured)
            
            # Setup credentials
            config.setup_credentials(
                client_id="test_id",
                client_secret="test_secret",
                ru_name="test_ru",
                environment="sandbox"
            )
            
            self.assertTrue(config.is_configured)
            self.assertEqual(config.credentials.client_id, "test_id")
            
            # Verify file was saved
            self.assertTrue(config_path.exists())
            
            # Load in new instance
            config2 = EbayConfig(config_path=config_path)
            self.assertTrue(config2.is_configured)
            self.assertEqual(config2.credentials.client_id, "test_id")
            
        finally:
            if config_path.exists():
                config_path.unlink()


class TestEbayAuth(unittest.TestCase):
    """Test eBay OAuth authentication."""
    
    def test_import_auth(self):
        """Test that auth module can be imported."""
        from ebay.auth import (
            EbayAuth,
            get_auth,
            start_auth_flow,
            get_token,
            get_headers,
        )
    
    def test_consent_url_generation(self):
        """Test OAuth consent URL generation."""
        from ebay.auth import EbayAuth
        from ebay.config import EbayConfig, EbayCredentials
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            config_path = Path(f.name)
        
        try:
            config = EbayConfig(config_path=config_path)
            config.setup_credentials(
                client_id="test_client_id",
                client_secret="test_secret",
                ru_name="test_runame"
            )
            
            # Patch get_config to return our test config
            with patch('ebay.auth.get_config', return_value=config):
                auth = EbayAuth()
                auth.config = config
                
                url = auth.get_consent_url()
                
                self.assertIn("https://auth.sandbox.ebay.com/oauth2/authorize", url)
                self.assertIn("client_id=test_client_id", url)
                self.assertIn("response_type=code", url)
                
        finally:
            if config_path.exists():
                config_path.unlink()


class TestEbayTaxonomy(unittest.TestCase):
    """Test eBay Taxonomy API."""
    
    def test_import_taxonomy(self):
        """Test that taxonomy module can be imported."""
        from ebay.taxonomy import (
            EbayTaxonomy,
            CategorySuggestion,
            ItemAspect,
            get_taxonomy,
            suggest_category,
            get_required_aspects,
        )
    
    def test_category_suggestion_structure(self):
        """Test CategorySuggestion data structure."""
        from ebay.taxonomy import CategorySuggestion
        
        cat = CategorySuggestion(
            category_id="12345",
            category_name="Cameras & Photography",
            category_tree_node_level=2,
            relevancy="HIGH",
            ancestors=[
                {"categoryName": "Electronics"},
                {"categoryName": "Cameras"}
            ]
        )
        
        self.assertEqual(cat.full_path, "Electronics > Cameras > Cameras & Photography")
    
    def test_item_aspect_structure(self):
        """Test ItemAspect data structure."""
        from ebay.taxonomy import ItemAspect
        
        # Required aspect
        aspect = ItemAspect(
            name="Brand",
            required=True,
            data_type="STRING",
            mode="FREE_TEXT",
            values=["Canon", "Nikon", "Sony"],
            usage="REQUIRED"
        )
        
        self.assertTrue(aspect.is_required)
        
        # Optional aspect
        optional = ItemAspect(
            name="Color",
            required=False,
            data_type="STRING",
            mode="SELECTION_ONLY",
            values=["Black", "Silver"],
            usage="RECOMMENDED"
        )
        
        self.assertFalse(optional.is_required)


class TestEbayInventory(unittest.TestCase):
    """Test eBay Inventory API."""
    
    def test_import_inventory(self):
        """Test that inventory module can be imported."""
        from ebay.inventory import (
            EbayInventory,
            Product,
            InventoryItem,
            Offer,
            PublishResult,
            ItemCondition,
            ListingFormat,
            get_inventory,
        )
    
    def test_product_to_dict(self):
        """Test Product serialization."""
        from ebay.inventory import Product
        
        product = Product(
            title="Vintage Camera",
            description="Great condition vintage camera",
            aspects={"Brand": ["Canon"], "Type": ["SLR"]},
            image_urls=["https://example.com/image.jpg"],
            brand="Canon"
        )
        
        data = product.to_dict()
        
        self.assertEqual(data["title"], "Vintage Camera")
        self.assertEqual(data["description"], "Great condition vintage camera")
        self.assertIn("https://example.com/image.jpg", data["imageUrls"])
        self.assertIn("Brand", data["aspects"])
    
    def test_inventory_item_to_dict(self):
        """Test InventoryItem serialization."""
        from ebay.inventory import Product, InventoryItem, ItemCondition
        
        product = Product(
            title="Test Product",
            description="Test description"
        )
        
        item = InventoryItem(
            sku="TEST-SKU-123",
            product=product,
            condition=ItemCondition.USED_GOOD,
            condition_description="Minor wear",
            quantity=5
        )
        
        data = item.to_dict()
        
        self.assertEqual(data["condition"], "USED_GOOD")
        self.assertEqual(data["conditionDescription"], "Minor wear")
        self.assertEqual(data["availability"]["shipToLocationAvailability"]["quantity"], 5)
    
    def test_offer_to_dict(self):
        """Test Offer serialization."""
        from ebay.inventory import Offer, ListingFormat
        
        offer = Offer(
            sku="TEST-SKU-123",
            marketplace_id="EBAY_US",
            format=ListingFormat.FIXED_PRICE,
            price_value=49.99,
            price_currency="USD",
            category_id="12345",
            payment_policy_id="policy1",
            return_policy_id="policy2",
            fulfillment_policy_id="policy3",
        )
        
        data = offer.to_dict()
        
        self.assertEqual(data["sku"], "TEST-SKU-123")
        self.assertEqual(data["format"], "FIXED_PRICE")
        self.assertEqual(data["pricingSummary"]["price"]["value"], "49.99")
        self.assertEqual(data["categoryId"], "12345")
        self.assertIn("listingPolicies", data)
    
    def test_sku_generation(self):
        """Test SKU generation."""
        from ebay.inventory import EbayInventory
        
        with patch('ebay.inventory.get_config'), \
             patch('ebay.inventory.get_auth'):
            inv = EbayInventory()
            
            sku1 = inv.generate_sku("Vintage Camera")
            sku2 = inv.generate_sku("Vintage Camera")
            
            # SKUs should be unique
            self.assertNotEqual(sku1, sku2)
            
            # SKUs should have MYBAY prefix
            self.assertTrue(sku1.startswith("MYBAY-"))
            self.assertTrue(sku2.startswith("MYBAY-"))
    
    def test_item_conditions(self):
        """Test item condition enum values."""
        from ebay.inventory import ItemCondition, CONDITION_IDS
        
        # Check common conditions have IDs
        self.assertIn(ItemCondition.NEW, CONDITION_IDS)
        self.assertIn(ItemCondition.USED_GOOD, CONDITION_IDS)
        
        # Check ID values are strings
        for condition, cid in CONDITION_IDS.items():
            self.assertIsInstance(cid, str)

    def test_pick_allowed_condition_keeps_requested_when_valid(self):
        """Keep requested condition if category allows it."""
        from ebay.inventory import EbayInventory, ItemCondition

        picked = EbayInventory._pick_allowed_condition(
            requested_condition=ItemCondition.USED_GOOD,
            allowed_condition_ids={"1000", "5000"},
        )
        self.assertEqual(picked, ItemCondition.USED_GOOD)

    def test_pick_allowed_condition_falls_back_to_new(self):
        """Fallback to NEW when used condition is not allowed."""
        from ebay.inventory import EbayInventory, ItemCondition

        picked = EbayInventory._pick_allowed_condition(
            requested_condition=ItemCondition.USED_GOOD,
            allowed_condition_ids={"1000", "1500"},
        )
        self.assertEqual(picked, ItemCondition.NEW)

    def test_extract_offer_id_from_errors(self):
        """Extract offerId parameter from eBay error payload."""
        from ebay.inventory import EbayInventory

        errors = [{
            "errorId": 25002,
            "parameters": [{"name": "offerId", "value": "117756543011"}],
        }]
        self.assertEqual(
            EbayInventory._extract_offer_id_from_errors(errors),
            "117756543011",
        )

    def test_create_offer_reuses_existing_offer_on_duplicate(self):
        """Reuse existing offer ID when create_offer returns duplicate-offer error."""
        from ebay.inventory import EbayInventory, Offer, ListingFormat

        with patch("ebay.inventory.get_config") as mock_get_config, \
             patch("ebay.inventory.get_auth") as mock_get_auth:
            mock_config = Mock()
            mock_config.api_base_url = "https://api.ebay.com"
            mock_get_config.return_value = mock_config

            mock_auth = Mock()
            mock_auth.get_auth_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_get_auth.return_value = mock_auth

            inv = EbayInventory()
            inv._http_client = Mock()

            response = Mock()
            response.status_code = 400
            response.json.return_value = {
                "errors": [{
                    "errorId": 25002,
                    "message": "Offer entity already exists.",
                    "parameters": [{"name": "offerId", "value": "117756543011"}],
                }]
            }
            response.text = "duplicate offer"
            inv._http_client.post.return_value = response

            offer = Offer(
                sku="TEST-SKU-123",
                marketplace_id="EBAY_US",
                format=ListingFormat.FIXED_PRICE,
                price_value=49.99,
                price_currency="USD",
                category_id="12345",
                payment_policy_id="p1",
                return_policy_id="r1",
                fulfillment_policy_id="f1",
            )

            with patch.object(inv, "update_offer", return_value=True) as mock_update_offer:
                offer_id = inv.create_offer(offer)

            self.assertEqual(offer_id, "117756543011")
            mock_update_offer.assert_called_once_with("117756543011", offer)

    def test_extract_missing_item_specifics(self):
        """Extract missing item specific names from eBay error payload."""
        from ebay.inventory import EbayInventory

        errors = [{
            "errorId": 25002,
            "message": "A user error has occurred. The item specific Ring Size is missing.",
            "parameters": [
                {"name": "0", "value": "The item specific Ring Size is missing."},
                {"name": "2", "value": "Ring Size"},
            ],
        }]

        missing = EbayInventory._extract_missing_item_specifics(errors)
        self.assertIn("Ring Size", missing)

    def test_apply_missing_item_specifics_uses_size_aspect(self):
        """Use existing Size aspect to auto-fill Ring Size when missing."""
        from ebay.inventory import EbayInventory

        updated, unresolved, messages = EbayInventory._apply_missing_item_specifics(
            aspects={"Size": ["7.5"]},
            missing_specifics=["Ring Size"],
            title="Vintage ring",
            description="Sterling silver",
        )

        self.assertEqual(updated.get("Ring Size"), ["7.5"])
        self.assertEqual(unresolved, [])
        self.assertTrue(any("Ring Size" in m for m in messages))

    def test_listing_id_normalization(self):
        """Test normalization of REST-style listing IDs to legacy numeric IDs."""
        from ebay.inventory import EbayInventory

        self.assertEqual(
            EbayInventory._normalize_listing_id("v1|110588827413|0"),
            "110588827413",
        )
        self.assertEqual(
            EbayInventory._normalize_listing_id("110588827413"),
            "110588827413",
        )
        self.assertIsNone(EbayInventory._normalize_listing_id(None))

    def test_extract_listing_id_from_payload_shapes(self):
        """Test listing ID extraction from publish/offer response payloads."""
        from ebay.inventory import EbayInventory

        publish_payload = {"listingId": "v1|110588827413|0"}
        offer_payload = {"listing": {"legacyItemId": "110588827412"}}

        self.assertEqual(
            EbayInventory._extract_listing_id(publish_payload),
            "110588827413",
        )
        self.assertEqual(
            EbayInventory._extract_listing_id(offer_payload),
            "110588827412",
        )

    def test_get_item_web_url_success(self):
        """Test canonical itemWebUrl lookup from Browse API."""
        from ebay.inventory import EbayInventory

        with patch("ebay.inventory.get_config") as mock_get_config, \
             patch("ebay.inventory.get_auth") as mock_get_auth:
            mock_config = Mock()
            mock_config.api_base_url = "https://api.sandbox.ebay.com"
            mock_get_config.return_value = mock_config

            mock_auth = Mock()
            mock_auth.get_auth_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_get_auth.return_value = mock_auth

            inv = EbayInventory()
            inv._http_client = Mock()

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "itemWebUrl": "https://cgi.sandbox.ebay.com/itm/Test-Item/110588827444"
            }
            inv._http_client.get.return_value = mock_response

            url = inv.get_item_web_url("110588827444")

            self.assertEqual(
                url,
                "https://cgi.sandbox.ebay.com/itm/Test-Item/110588827444"
            )
            inv._http_client.get.assert_called_once()

    def test_get_item_web_url_non_200(self):
        """Test canonical itemWebUrl lookup fallback on non-200 response."""
        from ebay.inventory import EbayInventory

        with patch("ebay.inventory.get_config") as mock_get_config, \
             patch("ebay.inventory.get_auth") as mock_get_auth:
            mock_config = Mock()
            mock_config.api_base_url = "https://api.sandbox.ebay.com"
            mock_get_config.return_value = mock_config

            mock_auth = Mock()
            mock_auth.get_auth_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_get_auth.return_value = mock_auth

            inv = EbayInventory()
            inv._http_client = Mock()

            mock_response = Mock()
            mock_response.status_code = 404
            inv._http_client.get.return_value = mock_response

            self.assertIsNone(inv.get_item_web_url("110588827444"))


class TestEbayPackage(unittest.TestCase):
    """Test eBay package main exports."""
    
    def test_package_imports(self):
        """Test that main package exports work."""
        from ebay import (
            # Setup functions
            setup_credentials,
            is_configured,
            is_authenticated,
            
            # Config
            get_config,
            EbayConfig,
            
            # Auth
            get_auth,
            start_auth_flow,
            EbayAuth,
            
            # Taxonomy
            get_taxonomy,
            suggest_category,
            CategorySuggestion,
            ItemAspect,
            
            # Inventory
            get_inventory,
            EbayInventory,
            Product,
            InventoryItem,
            Offer,
            PublishResult,
            ItemCondition,
            ListingFormat,
        )


class TestServerEbayEndpoints(unittest.TestCase):
    """Test server eBay OAuth endpoints."""
    
    def test_server_has_ebay_routes(self):
        """Test that server has eBay OAuth routes."""
        from server.main import app
        
        routes = [route.path for route in app.routes]
        
        self.assertIn("/ebay/callback", routes)
        self.assertIn("/ebay/status", routes)


if __name__ == "__main__":
    print("=" * 60)
    print("  Phase 3 Tests: eBay API Integration")
    print("=" * 60)
    
    # Run tests
    unittest.main(verbosity=2)

"""
Test Suite for Phase 4: Database & GUI

Run with: pytest tests/test_phase4.py -v
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDatabase:
    """Tests for the SQLite database module."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        from data.database import Database
        
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        yield db
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
    
    def test_database_creation(self, temp_db):
        """Test that database tables are created correctly."""
        # Check that we can use the database
        assert temp_db.draft_count() == 0
        assert temp_db.listing_count() == 0
    
    def test_add_draft(self, temp_db):
        """Test adding a draft to the database."""
        from data.database import Draft
        
        draft = Draft(
            sku="TEST-001",
            title="Test Product",
            description="A test product description",
            category_id="12345",
            category_name="Test Category",
            condition="NEW",
            price=29.99,
            image_paths=["test1.jpg", "test2.jpg"],
            ai_confidence=0.85,
        )
        
        draft_id = temp_db.add_draft(draft)
        assert draft_id is not None
        assert draft_id > 0
    
    def test_get_draft(self, temp_db):
        """Test retrieving a draft by SKU."""
        from data.database import Draft
        
        # Add a draft
        draft = Draft(
            sku="TEST-002",
            title="Test Product 2",
            description="Description",
            category_id="12345",
            category_name="Test Category",
            condition="NEW",
            price=19.99,
            image_paths=["img.jpg"],
            ai_confidence=0.90,
            brand="TestBrand",
            color="Blue"
        )
        
        temp_db.add_draft(draft)
        
        # Retrieve it by SKU
        retrieved = temp_db.get_draft("TEST-002")
        
        assert retrieved is not None
        assert retrieved.title == "Test Product 2"
        assert retrieved.price == 19.99
        assert retrieved.brand == "TestBrand"
        assert retrieved.ai_confidence == 0.90
    
    def test_get_all_drafts(self, temp_db):
        """Test retrieving all drafts."""
        from data.database import Draft
        
        # Add multiple drafts
        for i in range(3):
            draft = Draft(
                sku=f"TEST-{i:03d}",
                title=f"Product {i}",
                description="Desc",
                category_id="1",
                category_name="Cat",
                condition="NEW",
                price=10.0 + i,
                image_paths=[],
                ai_confidence=0.8,
            )
            temp_db.add_draft(draft)
        
        drafts = temp_db.get_all_drafts()
        assert len(drafts) == 3
    
    def test_update_draft(self, temp_db):
        """Test updating a draft."""
        from data.database import Draft
        
        # Add a draft
        draft = Draft(
            sku="TEST-UPDATE",
            title="Original Title",
            description="Desc",
            category_id="1",
            category_name="Cat",
            condition="NEW",
            price=25.00,
            image_paths=[],
            ai_confidence=0.75,
        )
        draft_id = temp_db.add_draft(draft)
        
        # Update it (using SKU)
        draft.id = draft_id
        draft.title = "Updated Title"
        draft.price = 30.00
        
        temp_db.update_draft(draft)
        
        # Verify update
        updated = temp_db.get_draft("TEST-UPDATE")
        assert updated.title == "Updated Title"
        assert updated.price == 30.00
    
    def test_delete_draft(self, temp_db):
        """Test deleting a draft."""
        from data.database import Draft
        
        # Add a draft
        draft = Draft(
            sku="TEST-DELETE",
            title="To Delete",
            description="Desc",
            category_id="1",
            category_name="Cat",
            condition="NEW",
            price=15.00,
            image_paths=[],
            ai_confidence=0.8,
        )
        temp_db.add_draft(draft)
        
        # Delete it by SKU
        temp_db.delete_draft("TEST-DELETE")
        
        # Verify deletion
        deleted = temp_db.get_draft("TEST-DELETE")
        assert deleted is None
    
    def test_add_listing(self, temp_db):
        """Test adding a listing."""
        from data.database import Draft, Listing
        
        # Create a listing directly
        listing = Listing(
            sku="TEST-LIST-001",
            ebay_listing_id="EBAY-12345",
            title="Listing Test",
            price=45.00,
            status="ACTIVE"
        )
        
        listing_id = temp_db.add_listing(listing)
        
        assert listing_id is not None
        assert listing_id > 0
        
        # Listing should exist
        retrieved = temp_db.get_listing("TEST-LIST-001")
        assert retrieved is not None
        assert retrieved.title == "Listing Test"
        assert retrieved.ebay_listing_id == "EBAY-12345"

    def test_delete_listing(self, temp_db):
        """Test deleting a listing from local DB history."""
        from data.database import Listing

        listing = Listing(
            sku="TEST-LIST-DEL",
            ebay_listing_id="EBAY-DEL-1",
            title="Delete Me",
            price=12.34,
            status="ACTIVE",
        )
        temp_db.add_listing(listing)

        assert temp_db.get_listing("TEST-LIST-DEL") is not None
        assert temp_db.delete_listing("TEST-LIST-DEL") is True
        assert temp_db.get_listing("TEST-LIST-DEL") is None
    
    def test_daily_stats(self, temp_db):
        """Test daily stats tracking via listing creation."""
        from data.database import Listing
        
        # Adding listings automatically increments stats
        for i in range(2):
            listing = Listing(
                sku=f"STAT-{i}",
                ebay_listing_id=f"EBAY-{i}",
                title=f"Product {i}",
                price=50.00
            )
            temp_db.add_listing(listing)
        
        # Get today's stats
        stats = temp_db.get_today_stats()
        
        assert stats is not None
        assert stats.listings_created == 2
        # Time saved should be 5 min * 2 = 10 min (300 seconds * 2)
        assert stats.time_saved_seconds == 600
    
    def test_settings(self, temp_db):
        """Test settings storage."""
        # Set values
        temp_db.set_setting("turbo_mode", "1")
        temp_db.set_setting("markup_percent", "15")
        
        # Get values
        assert temp_db.get_setting("turbo_mode") == "1"
        assert temp_db.get_setting("markup_percent") == "15"
        assert temp_db.get_setting("nonexistent", "default") == "default"
        
        # Update value
        temp_db.set_setting("turbo_mode", "0")
        assert temp_db.get_setting("turbo_mode") == "0"


class TestIntegration:
    """Tests for the watcher-database integration."""
    
    def test_generate_sku(self):
        """Test SKU generation."""
        from core.integration import generate_sku
        
        sku1 = generate_sku("Test Product")
        sku2 = generate_sku("Test Product")
        
        assert sku1.startswith("MYBAY-")
        assert len(sku1) == 16  # MYBAY- + 10 chars
        assert sku1 != sku2  # Should be unique
    
    def test_product_data_to_draft(self):
        """Test converting ProductData to Draft."""
        from core.integration import product_data_to_draft
        from core.vision import ProductData
        from core.watcher import ImageBatch
        from pathlib import Path
        
        # Mock ProductData
        product = ProductData(
            title="Test Nike Shoes",
            description="A pair of running shoes",
            category_keywords=["Shoes", "Athletic"],
            condition="LIKE_NEW",
            suggested_price_usd=59.99,
            confidence_score=0.88,
            brand="Nike",
            color="Black",
            material="Synthetic",
        )
        
        # Mock ImageBatch
        batch = ImageBatch(
            batch_id="test-batch",
            image_paths=[Path("img1.jpg"), Path("img2.jpg")]
        )
        
        draft = product_data_to_draft(batch, product)
        
        assert draft.title == "Test Nike Shoes"
        assert draft.price == 59.99
        assert draft.condition == "LIKE_NEW"
        assert draft.ai_confidence == 0.88
        assert draft.brand == "Nike"
        assert draft.color == "Black"
        assert len(draft.image_paths) == 2
        assert "Brand" in draft.aspects
        assert draft.aspects["Brand"] == ["Nike"]


class TestGuiImports:
    """Test that GUI components can be imported."""
    
    def test_import_gui_app(self):
        """Test importing the main GUI app."""
        try:
            from gui.app import MyBayApp
            assert MyBayApp is not None
        except ImportError as e:
            if "customtkinter" in str(e).lower():
                pytest.skip("CustomTkinter not installed")
            raise
    
    def test_import_database(self):
        """Test importing the database module."""
        from data.database import Database, Draft, Listing, DailyStat, get_db
        
        assert Database is not None
        assert Draft is not None
        assert Listing is not None
        assert DailyStat is not None


class TestDraftWorkflow:
    """Test the complete draft workflow."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        from data.database import Database
        
        db_path = tmp_path / "workflow_test.db"
        db = Database(db_path)
        yield db
        try:
            os.unlink(db_path)
        except:
            pass
    
    def test_complete_workflow(self, temp_db):
        """Test: create draft -> update -> publish -> track stats."""
        from data.database import Draft, Listing
        
        # 1. Create a draft (simulating AI analysis)
        draft = Draft(
            sku="WKFLW-001",
            title="Vintage Nike Air Max",
            description="Classic shoes in great condition",
            category_id="",
            category_name="Shoes, Athletic",
            condition="USED_GOOD",
            price=85.00,
            image_paths=["photos/shoe1.jpg", "photos/shoe2.jpg"],
            ai_confidence=0.92,
            brand="Nike",
            color="White/Red",
        )
        draft_id = temp_db.add_draft(draft)
        assert draft_id is not None
        
        # 2. User edits the draft (adjusts price)
        draft.id = draft_id
        draft.price = 95.00
        draft.title = "Vintage Nike Air Max 90 - Classic"
        temp_db.update_draft(draft)
        
        updated = temp_db.get_draft("WKFLW-001")
        assert updated.price == 95.00
        assert "Classic" in updated.title
        
        # 3. Publish to eBay (convert to listing)
        # Delete the draft and create a listing
        listing = Listing(
            sku="WKFLW-001",
            ebay_listing_id="EBAY-ABC123",
            title=updated.title,
            price=updated.price,
            status="ACTIVE"
        )
        listing_id = temp_db.add_listing(listing)
        temp_db.delete_draft("WKFLW-001")
        
        assert listing_id is not None
        
        # Draft should be gone
        assert temp_db.get_draft("WKFLW-001") is None
        
        # Listing should exist
        fetched_listing = temp_db.get_listing("WKFLW-001")
        assert fetched_listing is not None
        assert fetched_listing.status == "ACTIVE"
        assert fetched_listing.ebay_listing_id == "EBAY-ABC123"
        
        # 4. Check stats (listing was created, so stats should increment)
        stats = temp_db.get_today_stats()
        assert stats.listings_created == 1
        assert stats.time_saved_seconds == 300  # 5 minutes saved
        
        # 5. Simulate a sale
        temp_db.mark_listing_sold("WKFLW-001", 95.00)
        
        sold_listing = temp_db.get_listing("WKFLW-001")
        assert sold_listing.status == "SOLD"
        assert sold_listing.sold_price == 95.00
        
        # Stats should be updated (sale was recorded)
        final_stats = temp_db.get_today_stats()
        assert final_stats.items_sold == 1
        assert final_stats.revenue == 95.00


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

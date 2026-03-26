"""
Integration Module for myBay

Bridges the file watcher (camera uploads) with the database (GUI drafts).
When AI analysis completes, creates a draft in the database.
"""

import uuid
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

# Import components
from core.watcher import QueueWatcher, ImageBatch
from core.vision import ProductData
from data.database import get_db, Draft


def generate_sku(title: str) -> str:
    """Generate a unique SKU from a title."""
    unique_id = f"{title}-{datetime.now().timestamp()}-{uuid.uuid4().hex[:8]}"
    short_hash = hashlib.md5(unique_id.encode()).hexdigest()[:10].upper()
    return f"MYBAY-{short_hash}"


def product_data_to_draft(batch: ImageBatch, result: ProductData) -> Draft:
    """
    Convert AI analysis result to a database Draft.
    
    Args:
        batch: The image batch that was analyzed
        result: The ProductData from AI analysis
        
    Returns:
        A Draft object ready to save to the database
    """
    # Build aspects dict from AI result
    aspects = {}
    if result.brand:
        aspects["Brand"] = [result.brand]
    if result.color:
        aspects["Color"] = [result.color]
    if result.material:
        aspects["Material"] = [result.material]
    if result.size:
        aspects["Size"] = [result.size]
    
    # Map condition to eBay format
    condition_map = {
        "NEW": "NEW",
        "LIKE_NEW": "LIKE_NEW",
        "VERY_GOOD": "USED_VERY_GOOD",
        "GOOD": "USED_GOOD",
        "ACCEPTABLE": "USED_ACCEPTABLE",
    }
    condition = condition_map.get(result.condition, "NEW")
    
    # Create draft
    return Draft(
        sku=generate_sku(result.title),
        title=result.title,
        description=result.description,
        category_id="",  # Will be filled during publishing
        category_name=", ".join(result.category_keywords[:2]) if result.category_keywords else "",
        condition=condition,
        price=result.suggested_price_usd,
        image_paths=[str(p) for p in batch.image_paths],
        ai_confidence=result.confidence_score,
        aspects=aspects,
        brand=result.brand,
        model=result.model,
        size=result.size,
        color=result.color,
    )


class WatcherDatabaseBridge:
    """
    Connects the file watcher to the database.
    
    When photos arrive and AI analyzes them, automatically
    creates drafts in the database for the GUI to display.
    """
    
    def __init__(self, queue_dir: str | Path = None):
        """
        Initialize the bridge.
        
        Args:
            queue_dir: Directory to watch for uploads
        """
        self.db = get_db()
        self.watcher = QueueWatcher(queue_dir)
        
        # Set up callbacks
        self.watcher.on_new_listing = self._on_analysis_complete
        self.watcher.on_error = self._on_error
        
        # User callbacks
        self.on_draft_created: Optional[callable] = None
        self.on_analysis_error: Optional[callable] = None
    
    def _on_analysis_complete(self, batch: ImageBatch, result: ProductData):
        """Handle completed AI analysis."""
        try:
            # Convert to draft
            draft = product_data_to_draft(batch, result)
            
            # Save to database
            draft_id = self.db.add_draft(draft)
            draft.id = draft_id
            
            print(f"💾 Draft created: {draft.title} (SKU: {draft.sku})")
            
            # Notify callback
            if self.on_draft_created:
                self.on_draft_created(draft)
            
            # Check for Turbo Mode (auto-publish high confidence)
            self._check_turbo_mode(draft)
            
        except Exception as e:
            print(f"❌ Failed to create draft: {e}")
            if self.on_analysis_error:
                self.on_analysis_error(batch, e)
    
    def _on_error(self, batch: ImageBatch, error: Exception):
        """Handle analysis errors."""
        print(f"❌ Analysis error for batch {batch.batch_id}: {error}")
        if self.on_analysis_error:
            self.on_analysis_error(batch, error)
    
    def _check_turbo_mode(self, draft: Draft):
        """Auto-publish if Turbo Mode is enabled and confidence is high."""
        turbo_enabled = self.db.get_setting("turbo_mode", "0") == "1"
        
        if turbo_enabled and draft.ai_confidence >= 0.90:
            print(f"⚡ Turbo Mode: Would auto-publish {draft.title}")
            # Note: Actual auto-publish would go here
            # For safety, keeping it as a notification for now
    
    def start(self, blocking: bool = False):
        """Start watching for new images."""
        print("👀 Watching for new images...")
        self.watcher.start(blocking=blocking)
    
    def stop(self):
        """Stop watching."""
        self.watcher.stop()


def create_watcher_with_db(queue_dir: str | Path = None) -> WatcherDatabaseBridge:
    """
    Create a watcher that automatically saves to the database.
    
    Usage:
        bridge = create_watcher_with_db()
        bridge.start(blocking=True)
    """
    return WatcherDatabaseBridge(queue_dir)


# CLI interface
if __name__ == "__main__":
    print("=" * 50)
    print("  myBay — Watcher + Database Bridge")
    print("=" * 50)
    
    bridge = create_watcher_with_db()
    
    def on_draft(draft: Draft):
        print(f"\n📋 New draft ready for review:")
        print(f"   Title: {draft.title}")
        print(f"   Price: ${draft.price:.2f}")
        print(f"   Confidence: {draft.ai_confidence*100:.0f}%")
        print(f"   Images: {len(draft.image_paths)}")
    
    bridge.on_draft_created = on_draft
    
    try:
        bridge.start(blocking=True)
    except KeyboardInterrupt:
        print("\n👋 Stopping watcher...")
        bridge.stop()

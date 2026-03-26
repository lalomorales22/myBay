"""
Turbo Mode for myBay

Auto-publishes high-confidence listings without review.
Includes undo functionality and notification system.
"""

import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable
from queue import Queue

from data.database import get_db, Draft, Listing


# Turbo Mode settings
DEFAULT_CONFIDENCE_THRESHOLD = 0.90
UNDO_WINDOW_SECONDS = 30


@dataclass
class TurboPublishResult:
    """Result of a Turbo Mode auto-publish."""
    draft: Draft
    success: bool
    listing_id: Optional[str] = None
    ebay_listing_id: Optional[str] = None
    error: Optional[str] = None
    published_at: datetime = field(default_factory=datetime.now)
    can_undo: bool = True
    
    @property
    def undo_expires_at(self) -> datetime:
        return self.published_at + timedelta(seconds=UNDO_WINDOW_SECONDS)
    
    @property
    def undo_time_remaining(self) -> int:
        """Seconds remaining to undo."""
        remaining = (self.undo_expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))


class TurboMode:
    """
    Handles automatic publishing of high-confidence drafts.
    
    When enabled, drafts with AI confidence >= threshold are
    automatically published to eBay without review.
    
    Features:
    - Configurable confidence threshold
    - 30-second undo window
    - Notifications for each auto-publish
    - Queue management for pending undos
    """
    
    def __init__(self):
        self.db = get_db()
        self.enabled = False
        self.confidence_threshold = DEFAULT_CONFIDENCE_THRESHOLD
        
        # Track recent publishes for undo
        self._recent_publishes: list[TurboPublishResult] = []
        self._undo_lock = threading.Lock()
        
        # Callbacks
        self.on_auto_publish: Optional[Callable[[TurboPublishResult], None]] = None
        self.on_undo: Optional[Callable[[TurboPublishResult], None]] = None
        self.on_undo_expired: Optional[Callable[[TurboPublishResult], None]] = None
        
        # Load settings from database
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from database."""
        self.enabled = self.db.get_setting("turbo_mode", "0") == "1"
        threshold = self.db.get_setting("turbo_threshold", str(DEFAULT_CONFIDENCE_THRESHOLD))
        try:
            self.confidence_threshold = float(threshold)
        except ValueError:
            self.confidence_threshold = DEFAULT_CONFIDENCE_THRESHOLD
    
    def _save_settings(self):
        """Save settings to database."""
        self.db.set_setting("turbo_mode", "1" if self.enabled else "0")
        self.db.set_setting("turbo_threshold", str(self.confidence_threshold))
    
    def enable(self, threshold: float = None):
        """Enable Turbo Mode."""
        self.enabled = True
        if threshold is not None:
            self.confidence_threshold = threshold
        self._save_settings()
        print(f"⚡ Turbo Mode ENABLED (threshold: {self.confidence_threshold*100:.0f}%)")
    
    def disable(self):
        """Disable Turbo Mode."""
        self.enabled = False
        self._save_settings()
        print("⚡ Turbo Mode DISABLED")
    
    def toggle(self) -> bool:
        """Toggle Turbo Mode. Returns new state."""
        if self.enabled:
            self.disable()
        else:
            self.enable()
        return self.enabled
    
    def should_auto_publish(self, draft: Draft) -> bool:
        """Check if a draft qualifies for auto-publishing."""
        if not self.enabled:
            return False
        return draft.ai_confidence >= self.confidence_threshold
    
    def auto_publish(self, draft: Draft) -> TurboPublishResult:
        """
        Auto-publish a draft to eBay.

        Args:
            draft: The draft to publish

        Returns:
            TurboPublishResult with status and undo info
        """
        if not self.should_auto_publish(draft):
            return TurboPublishResult(
                draft=draft,
                success=False,
                error="Does not meet Turbo Mode criteria"
            )

        try:
            # Import eBay inventory here to avoid circular imports
            from ebay.inventory import get_inventory

            inv = get_inventory()

            # Upload images to eBay Picture Services
            from ebay.images import upload_images as ebay_upload_images
            batch = ebay_upload_images(draft.image_paths)
            image_urls = batch.successful_urls

            if not batch.any_successful:
                errors = "; ".join(r.error for r in batch.failed if r.error)
                return TurboPublishResult(
                    draft=draft,
                    success=False,
                    error=f"All image uploads failed: {errors}"
                )

            # Get business policies from settings
            payment_policy = self.db.get_setting("ebay_payment_policy_id", "")
            return_policy = self.db.get_setting("ebay_return_policy_id", "")
            fulfillment_policy = self.db.get_setting("ebay_fulfillment_policy_id", "")

            if not all([payment_policy, return_policy, fulfillment_policy]):
                return TurboPublishResult(
                    draft=draft,
                    success=False,
                    error="Business policies not configured"
                )

            # Apply markup if set
            try:
                markup_pct = float(self.db.get_setting("markup_percent", "0"))
            except (TypeError, ValueError):
                markup_pct = 0.0
            price = draft.price * (1 + markup_pct / 100)

            # Publish to eBay
            result = inv.quick_list(
                sku=draft.sku,
                title=draft.title,
                description=draft.description,
                price=price,
                category_id=draft.category_id,
                condition=draft.condition,
                image_urls=image_urls,
                aspects=draft.aspects,
                payment_policy_id=payment_policy,
                return_policy_id=return_policy,
                fulfillment_policy_id=fulfillment_policy,
            )

            if result.success:
                # Create listing in database
                listing = Listing(
                    sku=draft.sku,
                    ebay_listing_id=result.listing_id,
                    title=draft.title,
                    price=price,
                    status="ACTIVE",
                    environment=inv.config.environment.value,
                )
                listing_id = self.db.add_listing(listing)

                # Delete draft
                self.db.delete_draft(draft.sku)

                publish_result = TurboPublishResult(
                    draft=draft,
                    success=True,
                    listing_id=str(listing_id),
                    ebay_listing_id=result.listing_id,
                )

                # Track for undo
                with self._undo_lock:
                    self._recent_publishes.append(publish_result)
                    self._cleanup_expired()

                # Notify
                if self.on_auto_publish:
                    self.on_auto_publish(publish_result)

                print(f"⚡ Turbo Published: {draft.title} — ${price:.2f}")
                return publish_result
            else:
                return TurboPublishResult(
                    draft=draft,
                    success=False,
                    error=result.error or "Unknown error"
                )

        except Exception as e:
            return TurboPublishResult(
                draft=draft,
                success=False,
                error=str(e)
            )

    def auto_publish_sync(self, draft: Draft) -> TurboPublishResult:
        """Alias for auto_publish (kept for backwards compatibility)."""
        return self.auto_publish(draft)
    
    def _cleanup_expired(self):
        """Remove expired undo entries."""
        now = datetime.now()
        expired = [p for p in self._recent_publishes if p.undo_expires_at < now]
        self._recent_publishes = [p for p in self._recent_publishes if p.undo_expires_at >= now]
        
        # Notify of expiries
        for p in expired:
            p.can_undo = False
            if self.on_undo_expired:
                self.on_undo_expired(p)
    
    def get_undoable_publishes(self) -> list[TurboPublishResult]:
        """Get list of recent publishes that can still be undone."""
        with self._undo_lock:
            self._cleanup_expired()
            return list(self._recent_publishes)
    
    def undo_publish(self, result: TurboPublishResult) -> bool:
        """
        Undo an auto-publish (within the undo window).

        Args:
            result: The TurboPublishResult to undo

        Returns:
            True if undo was successful
        """
        if result.undo_time_remaining <= 0:
            print("⏰ Undo window has expired")
            return False

        try:
            # Import eBay inventory
            from ebay.inventory import get_inventory

            inv = get_inventory()

            # End the listing on eBay
            if result.ebay_listing_id:
                inv.withdraw_offer(result.ebay_listing_id)

            # Re-create the draft
            self.db.add_draft(result.draft)

            # Remove from recent publishes
            with self._undo_lock:
                self._recent_publishes = [
                    p for p in self._recent_publishes
                    if p.ebay_listing_id != result.ebay_listing_id
                ]

            result.can_undo = False

            # Notify
            if self.on_undo:
                self.on_undo(result)

            print(f"↩️ Undone: {result.draft.title}")
            return True

        except Exception as e:
            print(f"❌ Undo failed: {e}")
            return False

    def undo_publish_sync(self, result: TurboPublishResult) -> bool:
        """Alias for undo_publish (kept for backwards compatibility)."""
        return self.undo_publish(result)
    
    def process_draft(self, draft: Draft) -> Optional[TurboPublishResult]:
        """
        Process a new draft - auto-publish if it qualifies.
        
        Call this when a new draft is created from AI analysis.
        """
        if self.should_auto_publish(draft):
            return self.auto_publish_sync(draft)
        return None


# Singleton instance
_turbo: Optional[TurboMode] = None


def get_turbo() -> TurboMode:
    """Get the global TurboMode instance."""
    global _turbo
    if _turbo is None:
        _turbo = TurboMode()
    return _turbo


# Quick helpers
def is_turbo_enabled() -> bool:
    """Check if Turbo Mode is enabled."""
    return get_turbo().enabled


def toggle_turbo() -> bool:
    """Toggle Turbo Mode. Returns new state."""
    return get_turbo().toggle()


# CLI interface
if __name__ == "__main__":
    turbo = get_turbo()
    
    print("=" * 50)
    print("  myBay — Turbo Mode")
    print("=" * 50)
    print(f"\n⚡ Status: {'ENABLED' if turbo.enabled else 'DISABLED'}")
    print(f"🎯 Threshold: {turbo.confidence_threshold*100:.0f}%")
    
    undoable = turbo.get_undoable_publishes()
    if undoable:
        print(f"\n↩️ Recent publishes ({len(undoable)} can be undone):")
        for p in undoable:
            print(f"   • {p.draft.title} — {p.undo_time_remaining}s remaining")

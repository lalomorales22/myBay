"""
File Watcher for myBay

Monitors the queue directory for new images and triggers AI analysis.
This bridges the mobile upload (Phase 2) with the AI vision pipeline.
"""

from __future__ import annotations

import time
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional
from collections import deque

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

# Import vision module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.vision import ProductData
from core.analyzer_factory import get_analyzer
from core.ollama import OllamaAnalyzer


@dataclass
class ImageBatch:
    """Represents a batch of images to be processed."""
    batch_id: str
    image_paths: list[Path] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    processed: bool = False
    result: Optional[ProductData] = None
    error: Optional[str] = None


class QueueHandler(FileSystemEventHandler):
    """
    Watches for new images in the queue directory.
    
    Groups images by batch (images uploaded within a short time window)
    and triggers analysis when the batch is complete.
    """
    
    def __init__(
        self,
        on_new_batch: Callable[[ImageBatch], None] = None,
        on_analysis_complete: Callable[[ImageBatch, ProductData], None] = None,
        on_error: Callable[[ImageBatch, Exception], None] = None,
        batch_timeout: float = 3.0,  # seconds to wait for more images
        auto_analyze: bool = True,
    ):
        """
        Initialize the queue handler.
        
        Args:
            on_new_batch: Callback when new images arrive
            on_analysis_complete: Callback when analysis finishes
            on_error: Callback when an error occurs
            batch_timeout: Seconds to wait for more images in same batch
            auto_analyze: Whether to automatically analyze new batches
        """
        super().__init__()
        self.on_new_batch = on_new_batch
        self.on_analysis_complete = on_analysis_complete
        self.on_error = on_error
        self.batch_timeout = batch_timeout
        self.auto_analyze = auto_analyze
        
        self._current_batch: Optional[ImageBatch] = None
        self._batch_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._analyzer = get_analyzer()
        
        # Queue for processed batches
        self.completed_batches: deque[ImageBatch] = deque(maxlen=50)
    
    def on_created(self, event: FileCreatedEvent):
        """Handle new file creation events."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        # Check if it's a valid image
        if not self._is_image_file(path):
            return
        
        # Wait a moment for file to finish writing
        time.sleep(0.3)
        
        if not path.exists():
            return
        
        with self._lock:
            self._add_to_batch(path)
    
    def _is_image_file(self, path: Path) -> bool:
        """Check if a path is a valid image file."""
        valid_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
        return path.suffix.lower() in valid_extensions
    
    def _add_to_batch(self, path: Path):
        """Add an image to the current batch."""
        # Cancel existing timer
        if self._batch_timer:
            self._batch_timer.cancel()
        
        # Create new batch if needed
        if self._current_batch is None:
            batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._current_batch = ImageBatch(batch_id=batch_id)
            print(f"📷 New batch started: {batch_id}")
        
        # Add image to batch
        self._current_batch.image_paths.append(path)
        print(f"   Added: {path.name} ({len(self._current_batch.image_paths)} images)")
        
        # Start timer for batch completion
        self._batch_timer = threading.Timer(
            self.batch_timeout,
            self._finalize_batch
        )
        self._batch_timer.start()
    
    def _finalize_batch(self):
        """Finalize the current batch and trigger processing."""
        with self._lock:
            if self._current_batch is None:
                return
            
            batch = self._current_batch
            self._current_batch = None
        
        print(f"📦 Batch complete: {batch.batch_id} ({len(batch.image_paths)} images)")
        
        # Notify callback
        if self.on_new_batch:
            try:
                self.on_new_batch(batch)
            except Exception as e:
                print(f"   Callback error: {e}")
        
        # Auto-analyze if enabled
        if self.auto_analyze:
            self._analyze_batch(batch)
    
    def _analyze_batch(self, batch: ImageBatch):
        """Run AI analysis on a batch of images."""
        print(f"🤖 Analyzing batch: {batch.batch_id}...")
        
        try:
            # Validate backend readiness before calling the API.
            if isinstance(self._analyzer, OllamaAnalyzer):
                if not self._analyzer.check_ollama_status():
                    raise RuntimeError("Ollama is not running. Start it with: ollama serve")
            elif hasattr(self._analyzer, "api_key") and not self._analyzer.api_key:
                raise RuntimeError("OpenAI is not ready. Set OPENAI_API_KEY and verify internet access.")
            
            # Run analysis
            image_paths = [str(p) for p in batch.image_paths if p.exists()]
            if not image_paths:
                raise ValueError("No valid images in batch")
            
            result = self._analyzer.analyze_images(image_paths)
            if result.title in {"Analysis failed", "AI configuration error", "Analysis timed out"}:
                raise RuntimeError(result.description or result.title)

            # Ollama can't do web search for pricing — fall back to eBay Browse API
            if isinstance(self._analyzer, OllamaAnalyzer) and result.suggested_price_usd <= 0:
                result = self._enrich_price_from_ebay(result)

            batch.result = result
            batch.processed = True
            
            print(f"✅ Analysis complete!")
            print(f"   Title: {result.title}")
            print(f"   Price: ${result.suggested_price_usd:.2f}")
            print(f"   Confidence: {result.confidence_score*100:.0f}%")
            
            # Add to completed queue
            self.completed_batches.append(batch)
            
            # Notify callback
            if self.on_analysis_complete:
                self.on_analysis_complete(batch, result)
            
        except Exception as e:
            batch.error = str(e)
            batch.processed = True
            print(f"❌ Analysis failed: {e}")
            
            if self.on_error:
                self.on_error(batch, e)
    
    def _enrich_price_from_ebay(self, product_data: ProductData) -> ProductData:
        """Use eBay Browse API to get market pricing when Ollama can't web-search."""
        try:
            import asyncio
            from ebay.pricing import PricingIntelligence

            pricing = PricingIntelligence()
            analysis = asyncio.run(
                pricing.analyze(product_data.title, condition=product_data.condition)
            )
            if analysis and analysis.suggested_price > 0:
                product_data.suggested_price_usd = round(analysis.suggested_price, 2)
                print(f"   eBay pricing fallback: ${product_data.suggested_price_usd:.2f}")
        except Exception as e:
            print(f"   eBay pricing fallback skipped: {e}")
        return product_data

    def analyze_batch_sync(self, batch: ImageBatch) -> ProductData:
        """Synchronously analyze a batch (blocking)."""
        self._analyze_batch(batch)
        return batch.result


class QueueWatcher:
    """
    High-level interface for watching the image queue.
    
    Example:
        watcher = QueueWatcher("./queue")
        watcher.on_new_listing = lambda batch, result: print(result.title)
        watcher.start()
    """
    
    def __init__(self, queue_dir: str | Path = None):
        """
        Initialize the queue watcher.
        
        Args:
            queue_dir: Directory to watch (defaults to ./queue)
        """
        if queue_dir is None:
            from core.paths import get_queue_dir
            queue_dir = get_queue_dir()
        
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # Callbacks
        self.on_images_received: Optional[Callable[[ImageBatch], None]] = None
        self.on_new_listing: Optional[Callable[[ImageBatch, ProductData], None]] = None
        self.on_error: Optional[Callable[[ImageBatch, Exception], None]] = None
        
        # Create handler
        self._handler = QueueHandler(
            on_new_batch=self._handle_new_batch,
            on_analysis_complete=self._handle_analysis,
            on_error=self._handle_error,
        )
        
        self._observer = None  # Type: Observer | None
        self._running = False
    
    def _handle_new_batch(self, batch: ImageBatch):
        if self.on_images_received:
            self.on_images_received(batch)
    
    def _handle_analysis(self, batch: ImageBatch, result: ProductData):
        if self.on_new_listing:
            self.on_new_listing(batch, result)
    
    def _handle_error(self, batch: ImageBatch, error: Exception):
        if self.on_error:
            self.on_error(batch, error)
    
    @property
    def completed_batches(self) -> deque[ImageBatch]:
        """Get completed batches."""
        return self._handler.completed_batches
    
    def start(self, blocking: bool = False):
        """
        Start watching the queue directory.
        
        Args:
            blocking: If True, block until stopped
        """
        if self._running:
            return
        
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.queue_dir), recursive=False)
        self._observer.start()
        self._running = True
        
        print(f"👁️  Watching: {self.queue_dir}")
        
        if blocking:
            try:
                while self._running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
    
    def stop(self):
        """Stop watching the queue directory."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        self._running = False
        print("👁️  Watcher stopped")
    
    def process_existing(self) -> list[ImageBatch]:
        """
        Process any existing images in the queue.
        
        Returns:
            List of processed batches
        """
        batches = []
        
        # Find all images (case-insensitive)
        images = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.heic",
                     "*.JPG", "*.JPEG", "*.PNG", "*.WEBP", "*.HEIC"]:
            images.extend(self.queue_dir.glob(ext))
        # Deduplicate in case filesystem is case-insensitive
        images = list({p.resolve(): p for p in images}.values())

        if not images:
            return batches
        
        # Group by timestamp prefix (batch)
        from collections import defaultdict
        groups = defaultdict(list)
        
        for img in images:
            # Extract batch ID from filename (format: YYYYMMDD_HHMMSS_xxx_nn.ext)
            parts = img.stem.split("_")
            if len(parts) >= 3:
                batch_id = "_".join(parts[:3])
            else:
                batch_id = img.stem
            groups[batch_id].append(img)
        
        # Process each group
        for batch_id, paths in groups.items():
            batch = ImageBatch(batch_id=batch_id, image_paths=list(paths))
            self._handler._analyze_batch(batch)
            batches.append(batch)
        
        return batches
    
    def clear_queue(self):
        """Delete all images from the queue."""
        count = 0
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.heic",
                     "*.JPG", "*.JPEG", "*.PNG", "*.WEBP", "*.HEIC"]:
            for path in self.queue_dir.glob(ext):
                path.unlink()
                count += 1
        print(f"🗑️  Cleared {count} images from queue")


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="myBay - Queue Watcher")
    parser.add_argument("--queue-dir", "-q", default=None, help="Queue directory path")
    parser.add_argument("--process-existing", "-p", action="store_true", help="Process existing images")
    parser.add_argument("--clear", "-c", action="store_true", help="Clear the queue")
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  👁️  myBay - Queue Watcher")
    print("="*60)
    
    watcher = QueueWatcher(args.queue_dir)
    
    # Set up callbacks
    def on_images(batch):
        print(f"\n📷 Received {len(batch.image_paths)} images")
    
    def on_listing(batch, result):
        print(f"\n✅ New listing ready!")
        print(f"   Title: {result.title}")
        print(f"   Price: ${result.suggested_price_usd:.2f}")
        print(f"   Category: {', '.join(result.category_keywords)}")
    
    def on_err(batch, error):
        print(f"\n❌ Error: {error}")
    
    watcher.on_images_received = on_images
    watcher.on_new_listing = on_listing
    watcher.on_error = on_err
    
    if args.clear:
        watcher.clear_queue()
    
    if args.process_existing:
        print("\nProcessing existing images...")
        batches = watcher.process_existing()
        print(f"Processed {len(batches)} batch(es)")
    
    # Start watching
    print(f"\n📂 Queue: {watcher.queue_dir}")
    print("Waiting for photos from your phone...")
    print("Press Ctrl+C to stop\n")
    
    watcher.start(blocking=True)

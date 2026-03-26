# myBay - Core Module
"""
Core functionality for myBay including:
- vision: AI-powered product analysis using OpenAI vision + web search
- image_utils: Background removal and image processing
- qr_code: QR code generation for mobile access
- watcher: File system watcher for queue processing
- integration: Bridge between watcher and database
- turbo: Turbo Mode auto-publishing
- retry: Error handling and retry logic
- presets: myBay smart defaults
"""

from .vision import ProductAnalyzer, ProductData
from .image_utils import remove_background, process_images_for_listing
from .qr_code import generate_qr_code, get_camera_url, get_local_ip
from .watcher import QueueWatcher, ImageBatch
from .integration import WatcherDatabaseBridge, create_watcher_with_db
from .turbo import TurboMode, get_turbo, is_turbo_enabled, toggle_turbo
from .retry import with_retry, APIError, APIException, get_offline_queue
from .presets import MybayPresets, get_presets, needs_setup

__all__ = [
    # Vision
    "ProductAnalyzer",
    "ProductData", 
    # Image processing
    "remove_background",
    "process_images_for_listing",
    # QR/Network
    "generate_qr_code",
    "get_camera_url",
    "get_local_ip",
    # Watcher
    "QueueWatcher",
    "ImageBatch",
    "WatcherDatabaseBridge",
    "create_watcher_with_db",
    # Turbo Mode
    "TurboMode",
    "get_turbo",
    "is_turbo_enabled",
    "toggle_turbo",
    # Error handling
    "with_retry",
    "APIError",
    "APIException",
    "get_offline_queue",
    # Presets  
    "MybayPresets",
    "get_presets",
    "needs_setup",
]

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
from .retry import with_retry, APIError, APIException, get_offline_queue


def __getattr__(name):
    """Lazy-load modules that depend on data.database to avoid circular imports."""
    _lazy = {
        "WatcherDatabaseBridge": ("core.integration", "WatcherDatabaseBridge"),
        "create_watcher_with_db": ("core.integration", "create_watcher_with_db"),
        "TurboMode": ("core.turbo", "TurboMode"),
        "get_turbo": ("core.turbo", "get_turbo"),
        "is_turbo_enabled": ("core.turbo", "is_turbo_enabled"),
        "toggle_turbo": ("core.turbo", "toggle_turbo"),
        "MybayPresets": ("core.presets", "MybayPresets"),
        "get_presets": ("core.presets", "get_presets"),
        "needs_setup": ("core.presets", "needs_setup"),
    }
    if name in _lazy:
        import importlib
        module_path, attr = _lazy[name]
        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    raise AttributeError(f"module 'core' has no attribute {name!r}")


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

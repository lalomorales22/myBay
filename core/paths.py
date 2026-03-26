"""
Centralized path resolution for myBay.

When running from source, data lives in the project root.
When running as a bundled .app, writable data goes to:
    ~/Library/Application Support/myBay/
"""

import sys
import os
from pathlib import Path

APP_NAME = "myBay"

_is_frozen = getattr(sys, "frozen", False)


def get_user_data_dir() -> Path:
    """Return the writable user data directory.

    - Source mode: project root (parent of core/)
    - Bundled mode: ~/Library/Application Support/myBay/
    """
    if _is_frozen:
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support" / APP_NAME
        elif sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
        else:
            base = Path.home() / f".{APP_NAME.lower()}"
        base.mkdir(parents=True, exist_ok=True)
        return base

    return Path(__file__).resolve().parent.parent


def get_db_path() -> Path:
    return get_user_data_dir() / "mybay.db"


def get_ebay_config_path() -> Path:
    return get_user_data_dir() / ".ebay_config.json"


def get_admin_files_dir() -> Path:
    d = get_user_data_dir() / "admin_files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_receipts_dir() -> Path:
    d = get_admin_files_dir() / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_documents_dir() -> Path:
    d = get_admin_files_dir() / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_queue_dir() -> Path:
    d = get_user_data_dir() / "queue"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_env_template() -> bool:
    """Create a .env template in the user data dir if one doesn't exist.

    Returns True if a new template was created (first launch).
    """
    env_path = get_user_data_dir() / ".env"
    if env_path.exists():
        return False

    env_path.write_text(
        "# myBay - Configuration\n"
        "# Replace the placeholder below with your real OpenAI API key.\n"
        "# Get one at: https://platform.openai.com/api-keys\n"
        "OPENAI_API_KEY=sk-REPLACE-ME\n"
        "\n"
        "# Optional: ngrok auth token (for phone camera over the internet)\n"
        "# NGROK_AUTHTOKEN=\n"
    )
    return True

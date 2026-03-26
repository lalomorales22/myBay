"""
eBay API Configuration for myBay

Manages API credentials, endpoints, and environment settings.
Credentials are stored securely in a local config file.
"""

import json
import base64
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from enum import Enum

from core.paths import get_ebay_config_path


class EbayEnvironment(Enum):
    """eBay API environments."""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


# API Endpoints
ENDPOINTS = {
    EbayEnvironment.SANDBOX: {
        "api": "https://api.sandbox.ebay.com",
        "auth": "https://auth.sandbox.ebay.com",
        "identity": "https://api.sandbox.ebay.com/identity/v1",
    },
    EbayEnvironment.PRODUCTION: {
        "api": "https://api.ebay.com",
        "auth": "https://auth.ebay.com",
        "identity": "https://api.ebay.com/identity/v1",
    }
}

# Default OAuth scopes for myBay
DEFAULT_SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
]

# Scopes that only need application token (not user token)
APP_TOKEN_SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
]


@dataclass
class EbayCredentials:
    """eBay API credentials."""
    client_id: str
    client_secret: str
    ru_name: str  # Redirect URL name
    environment: str = "sandbox"  # or "production"
    
    def get_basic_auth(self) -> str:
        """Get Base64-encoded credentials for Basic auth."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "EbayCredentials":
        return cls(**data)


@dataclass
class EbayTokens:
    """OAuth tokens for eBay API."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    refresh_token_expires_in: Optional[int] = None
    
    # Timestamps for tracking expiry
    access_token_created: Optional[float] = None
    refresh_token_created: Optional[float] = None
    
    # Connected user info
    username: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "EbayTokens":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def is_access_token_expired(self) -> bool:
        """Check if access token is expired (with 5 min buffer)."""
        import time
        if not self.access_token_created:
            return True
        elapsed = time.time() - self.access_token_created
        return elapsed >= (self.expires_in - 300)  # 5 min buffer
    
    def is_refresh_token_expired(self) -> bool:
        """Check if refresh token is expired."""
        import time
        if not self.refresh_token or not self.refresh_token_created or not self.refresh_token_expires_in:
            return True
        elapsed = time.time() - self.refresh_token_created
        return elapsed >= self.refresh_token_expires_in


class EbayConfig:
    """
    Configuration manager for eBay API integration.
    
    Handles loading/saving credentials and tokens from a secure local file.
    """
    
    DEFAULT_CONFIG_PATH = get_ebay_config_path()
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config file (defaults to .ebay_config.json)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._active_environment: str = "sandbox"
        # Store credentials/tokens per environment
        self._sandbox_credentials: Optional[EbayCredentials] = None
        self._sandbox_tokens: Optional[EbayTokens] = None
        self._production_credentials: Optional[EbayCredentials] = None
        self._production_tokens: Optional[EbayTokens] = None
        self._load_config()
    
    def reload(self):
        """Reload configuration from file (picks up changes made by other processes)."""
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                
                # Load active environment
                self._active_environment = data.get("active_environment", "sandbox")
                
                # Load sandbox credentials/tokens
                if "sandbox" in data:
                    if "credentials" in data["sandbox"]:
                        self._sandbox_credentials = EbayCredentials.from_dict(data["sandbox"]["credentials"])
                    if "tokens" in data["sandbox"]:
                        self._sandbox_tokens = EbayTokens.from_dict(data["sandbox"]["tokens"])
                
                # Load production credentials/tokens
                if "production" in data:
                    if "credentials" in data["production"]:
                        self._production_credentials = EbayCredentials.from_dict(data["production"]["credentials"])
                    if "tokens" in data["production"]:
                        self._production_tokens = EbayTokens.from_dict(data["production"]["tokens"])
                
                # Backwards compatibility: migrate old single-credential format
                if "credentials" in data and "sandbox" not in data and "production" not in data:
                    old_creds = EbayCredentials.from_dict(data["credentials"])
                    if old_creds.environment == "production":
                        self._production_credentials = old_creds
                        if "tokens" in data:
                            self._production_tokens = EbayTokens.from_dict(data["tokens"])
                    else:
                        self._sandbox_credentials = old_creds
                        if "tokens" in data:
                            self._sandbox_tokens = EbayTokens.from_dict(data["tokens"])
                    # Re-save in new format
                    self._save_config()
                    
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load eBay config: {e}")
    
    def _save_config(self):
        """Save configuration to file."""
        data = {
            "active_environment": self._active_environment
        }
        
        # Save sandbox
        sandbox_data = {}
        if self._sandbox_credentials:
            sandbox_data["credentials"] = self._sandbox_credentials.to_dict()
        if self._sandbox_tokens:
            sandbox_data["tokens"] = self._sandbox_tokens.to_dict()
        if sandbox_data:
            data["sandbox"] = sandbox_data
        
        # Save production
        production_data = {}
        if self._production_credentials:
            production_data["credentials"] = self._production_credentials.to_dict()
        if self._production_tokens:
            production_data["tokens"] = self._production_tokens.to_dict()
        if production_data:
            data["production"] = production_data
        
        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
        
        # Set restrictive permissions (owner read/write only)
        self.config_path.chmod(0o600)
    
    @property
    def credentials(self) -> Optional[EbayCredentials]:
        """Get credentials for the active environment."""
        if self._active_environment == "production":
            return self._production_credentials
        return self._sandbox_credentials
    
    @credentials.setter
    def credentials(self, value: EbayCredentials):
        """Set credentials for the specified environment."""
        if value.environment == "production":
            self._production_credentials = value
            self._active_environment = "production"
        else:
            self._sandbox_credentials = value
            self._active_environment = "sandbox"
        self._save_config()
    
    def get_credentials_for_env(self, environment: str) -> Optional[EbayCredentials]:
        """Get credentials for a specific environment."""
        if environment == "production":
            return self._production_credentials
        return self._sandbox_credentials
    
    def set_active_environment(self, environment: str):
        """Switch the active environment."""
        self._active_environment = environment
        self._save_config()
    
    @property
    def tokens(self) -> Optional[EbayTokens]:
        """Get tokens for the active environment."""
        if self._active_environment == "production":
            return self._production_tokens
        return self._sandbox_tokens
    
    @tokens.setter
    def tokens(self, value: EbayTokens):
        """Set tokens for the active environment."""
        if self._active_environment == "production":
            self._production_tokens = value
        else:
            self._sandbox_tokens = value
        self._save_config()
    
    @property
    def is_configured(self) -> bool:
        """Check if credentials are configured for the active environment."""
        return self.credentials is not None
    
    @property
    def has_valid_token(self) -> bool:
        """Check if we have a valid (non-expired) access token."""
        tokens = self.tokens
        if not tokens:
            return False
        return not tokens.is_access_token_expired()
    
    @property
    def environment(self) -> EbayEnvironment:
        """Get the current environment."""
        return EbayEnvironment(self._active_environment)
    
    @property
    def api_base_url(self) -> str:
        """Get the API base URL for current environment."""
        return ENDPOINTS[self.environment]["api"]
    
    @property
    def auth_base_url(self) -> str:
        """Get the auth base URL for current environment."""
        return ENDPOINTS[self.environment]["auth"]
    
    @property
    def identity_url(self) -> str:
        """Get the identity API URL for current environment."""
        return ENDPOINTS[self.environment]["identity"]
    
    def setup_credentials(
        self,
        client_id: str,
        client_secret: str,
        ru_name: str,
        environment: str = "sandbox"
    ):
        """
        Set up eBay API credentials.
        
        Args:
            client_id: eBay App ID (Client ID)
            client_secret: eBay Cert ID (Client Secret)
            ru_name: Redirect URL name from eBay developer portal
            environment: "sandbox" or "production"
        """
        self.credentials = EbayCredentials(
            client_id=client_id,
            client_secret=client_secret,
            ru_name=ru_name,
            environment=environment
        )
        print(f"✅ eBay credentials saved for {environment} environment")
    
    def clear_tokens(self):
        """Clear stored tokens for the active environment (logout)."""
        if self._active_environment == "production":
            self._production_tokens = None
        else:
            self._sandbox_tokens = None
        self._save_config()
        print(f"🔓 eBay tokens cleared for {self._active_environment}")
    
    def clear_all(self):
        """Clear all configuration."""
        self._sandbox_credentials = None
        self._sandbox_tokens = None
        self._production_credentials = None
        self._production_tokens = None
        if self.config_path.exists():
            self.config_path.unlink()
        print("🗑️  eBay configuration cleared")


# Global config instance
_config: Optional[EbayConfig] = None


def get_config() -> EbayConfig:
    """Get the global eBay config instance."""
    global _config
    if _config is None:
        _config = EbayConfig()
    return _config


# CLI interface
if __name__ == "__main__":
    import sys
    
    config = get_config()
    
    print("=" * 50)
    print("  eBay Configuration Status")
    print("=" * 50)
    
    if config.is_configured:
        print(f"✅ Credentials configured")
        print(f"   Environment: {config.environment.value}")
        print(f"   Client ID:   {config.credentials.client_id[:10]}...")
        print(f"   RuName:      {config.credentials.ru_name[:20]}...")
        
        if config.tokens:
            if config.has_valid_token:
                print(f"✅ Access token valid")
            else:
                print(f"⚠️  Access token expired")
            
            if config.tokens.refresh_token:
                if not config.tokens.is_refresh_token_expired():
                    print(f"✅ Refresh token valid")
                else:
                    print(f"⚠️  Refresh token expired")
        else:
            print(f"❌ No tokens (need to authenticate)")
    else:
        print("❌ Not configured")
        print("\nTo configure, run:")
        print("   from ebay.config import get_config")
        print("   config = get_config()")
        print("   config.setup_credentials(")
        print('       client_id="your_client_id",')
        print('       client_secret="your_client_secret",')
        print('       ru_name="your_runame",')
        print('       environment="sandbox"  # or "production"')
        print("   )")

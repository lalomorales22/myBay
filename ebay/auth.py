"""
eBay OAuth 2.0 Authentication for myBay

Handles:
- User consent URL generation
- Authorization code exchange
- Token refresh
- Application token (for non-user APIs)
"""

import time
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs
from typing import Optional
from dataclasses import dataclass

import httpx

from .config import (
    get_config, 
    EbayTokens, 
    DEFAULT_SCOPES, 
    APP_TOKEN_SCOPES,
    EbayEnvironment
)


@dataclass
class AuthError:
    """Authentication error details."""
    error: str
    error_description: str


class EbayAuth:
    """
    eBay OAuth 2.0 authentication handler.
    
    Supports both:
    - User token flow (for selling APIs)
    - Application token flow (for public APIs like taxonomy)
    """
    
    def __init__(self, callback_port: int = 8000):
        """
        Initialize auth handler.
        
        Args:
            callback_port: Port for OAuth callback (should match RuName setting)
        """
        self.config = get_config()
        self.callback_port = callback_port
        self.callback_path = "/ebay/callback"
        self._http_client = None
    
    @property
    def http_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0)
        return self._http_client
    
    @property
    def redirect_uri(self) -> str:
        """Get the OAuth redirect URI."""
        return f"http://localhost:{self.callback_port}{self.callback_path}"
    
    def get_consent_url(self, scopes: Optional[list] = None, state: str = "ebay_auth") -> str:
        """
        Generate the eBay OAuth consent URL.
        
        Args:
            scopes: List of OAuth scopes (defaults to selling scopes)
            state: State parameter for CSRF protection
            
        Returns:
            URL to redirect user to for eBay login
        """
        if not self.config.is_configured:
            raise ValueError("eBay credentials not configured. Run config.setup_credentials() first.")
        
        scopes = scopes or DEFAULT_SCOPES
        scope_str = " ".join(scopes)
        
        params = {
            "client_id": self.config.credentials.client_id,
            "response_type": "code",
            "redirect_uri": self.config.credentials.ru_name,
            "scope": scope_str,
            "state": state,
        }
        
        base_url = f"{self.config.auth_base_url}/oauth2/authorize"
        return f"{base_url}?{urlencode(params)}"
    
    def exchange_code_for_token(self, authorization_code: str) -> EbayTokens:
        """
        Exchange authorization code for access/refresh tokens.
        
        Args:
            authorization_code: Code received from OAuth callback
            
        Returns:
            EbayTokens with access and refresh tokens
            
        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If response is invalid
        """
        if not self.config.is_configured:
            raise ValueError("eBay credentials not configured")
        
        url = f"{self.config.identity_url}/oauth2/token"
        
        headers = {
            "Authorization": self.config.credentials.get_basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.config.credentials.ru_name,
        }
        
        response = self.http_client.post(url, headers=headers, data=data)
        
        if response.status_code != 200:
            error_data = response.json()
            raise ValueError(
                f"Token exchange failed: {error_data.get('error_description', response.text)}"
            )
        
        token_data = response.json()
        
        # Add timestamps
        tokens = EbayTokens(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data["expires_in"],
            refresh_token=token_data.get("refresh_token"),
            refresh_token_expires_in=token_data.get("refresh_token_expires_in"),
            access_token_created=time.time(),
            refresh_token_created=time.time() if token_data.get("refresh_token") else None,
        )
        
        # Save tokens
        self.config.tokens = tokens
        print("✅ eBay authentication successful!")
        
        return tokens
    
    def refresh_access_token(self) -> EbayTokens:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            Updated EbayTokens
            
        Raises:
            ValueError: If no refresh token available or refresh fails
        """
        if not self.config.tokens or not self.config.tokens.refresh_token:
            raise ValueError("No refresh token available. Need to re-authenticate.")
        
        if self.config.tokens.is_refresh_token_expired():
            raise ValueError("Refresh token expired. Need to re-authenticate.")
        
        url = f"{self.config.identity_url}/oauth2/token"
        
        headers = {
            "Authorization": self.config.credentials.get_basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.config.tokens.refresh_token,
        }
        
        response = self.http_client.post(url, headers=headers, data=data)
        
        if response.status_code != 200:
            error_data = response.json()
            raise ValueError(
                f"Token refresh failed: {error_data.get('error_description', response.text)}"
            )
        
        token_data = response.json()
        
        # Update tokens (keep existing refresh token if new one not provided)
        tokens = EbayTokens(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data["expires_in"],
            refresh_token=token_data.get("refresh_token", self.config.tokens.refresh_token),
            refresh_token_expires_in=token_data.get(
                "refresh_token_expires_in", 
                self.config.tokens.refresh_token_expires_in
            ),
            access_token_created=time.time(),
            refresh_token_created=self.config.tokens.refresh_token_created,
        )
        
        self.config.tokens = tokens
        print("✅ Access token refreshed!")
        
        return tokens
    
    def get_application_token(self, scopes: Optional[list] = None) -> str:
        """
        Get an application token (client credentials flow).
        
        This is for APIs that don't need user authorization,
        like the Taxonomy API for category lookups.
        
        Args:
            scopes: List of OAuth scopes (defaults to app-level scopes)
            
        Returns:
            Access token string
        """
        if not self.config.is_configured:
            raise ValueError("eBay credentials not configured")
        
        scopes = scopes or APP_TOKEN_SCOPES
        scope_str = " ".join(scopes)
        
        url = f"{self.config.identity_url}/oauth2/token"
        
        headers = {
            "Authorization": self.config.credentials.get_basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": scope_str,
        }
        
        response = self.http_client.post(url, headers=headers, data=data)
        
        if response.status_code != 200:
            error_data = response.json()
            raise ValueError(
                f"Application token failed: {error_data.get('error_description', response.text)}"
            )
        
        token_data = response.json()
        return token_data["access_token"]
    
    def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Valid access token string
            
        Raises:
            ValueError: If no valid token and can't refresh
        """
        if self.config.has_valid_token:
            return self.config.tokens.access_token
        
        if self.config.tokens and self.config.tokens.refresh_token:
            try:
                self.refresh_access_token()
                return self.config.tokens.access_token
            except ValueError:
                pass  # Will raise below
        
        raise ValueError(
            "No valid access token. Please authenticate:\n"
            "  from ebay.auth import start_auth_flow\n"
            "  start_auth_flow()"
        )
    
    def get_auth_headers(self) -> dict:
        """
        Get authorization headers for API requests.
        
        Returns:
            Dict with Authorization header
        """
        token = self.get_valid_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    
    def start_browser_auth(self, scopes: Optional[list] = None):
        """
        Start the OAuth flow by opening consent URL in browser.
        
        Args:
            scopes: Optional custom scopes
        """
        url = self.get_consent_url(scopes)
        print(f"\n🔐 Opening eBay login in your browser...")
        print(f"   If browser doesn't open, visit:\n   {url}\n")
        webbrowser.open(url)
    
    def handle_callback(self, callback_url: str) -> Optional[EbayTokens]:
        """
        Handle the OAuth callback URL.
        
        Args:
            callback_url: Full callback URL with authorization code
            
        Returns:
            EbayTokens if successful, None if error
        """
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        
        if "error" in params:
            error = params["error"][0]
            description = params.get("error_description", ["Unknown error"])[0]
            print(f"❌ Authentication failed: {error} - {description}")
            return None
        
        if "code" not in params:
            print("❌ No authorization code in callback URL")
            return None
        
        code = params["code"][0]
        return self.exchange_code_for_token(code)
    
    def get_user_info(self) -> Optional[dict]:
        """
        Get the authenticated user's eBay account info.
        
        Returns:
            Dict with user info (userId, username) or None if not authenticated
        """
        if not self.config.has_valid_token:
            return None
        
        try:
            # Use the Commerce Identity API to get user info
            url = f"{self.config.api_base_url}/commerce/identity/v1/user/"
            
            headers = self.get_auth_headers()
            response = self.http_client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "userId": data.get("userId"),
                    "username": data.get("username"),
                    "accountType": data.get("accountType"),
                }
        except Exception as e:
            print(f"Could not fetch user info: {e}")
        
        return None
    
    def close(self):
        """Close the HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


# Convenience functions

_auth: Optional[EbayAuth] = None


def get_auth() -> EbayAuth:
    """Get the global auth instance."""
    global _auth
    if _auth is None:
        _auth = EbayAuth()
    return _auth


def start_auth_flow():
    """
    Start the interactive OAuth flow.
    
    Opens browser for eBay login. After login, eBay redirects
    back to the local server which captures the auth code.
    """
    auth = get_auth()
    
    if not auth.config.is_configured:
        print("❌ eBay credentials not configured!")
        print("\nFirst, configure your credentials:")
        print("   from ebay.config import get_config")
        print("   config = get_config()")
        print("   config.setup_credentials(")
        print('       client_id="your_client_id",')
        print('       client_secret="your_client_secret",')
        print('       ru_name="your_runame"')
        print("   )")
        return
    
    auth.start_browser_auth()
    print("Waiting for OAuth callback...")
    print("Make sure the server is running: python run.py")


def get_token() -> str:
    """Get a valid access token."""
    return get_auth().get_valid_token()


def get_headers() -> dict:
    """Get authorization headers for API requests."""
    return get_auth().get_auth_headers()


# CLI interface
if __name__ == "__main__":
    config = get_config()
    
    if not config.is_configured:
        print("❌ Please configure credentials first")
    elif config.has_valid_token:
        print("✅ Already authenticated with valid token")
    else:
        start_auth_flow()

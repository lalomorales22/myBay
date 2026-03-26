"""
Error Handling & Retry Logic for myBay

Provides robust API error handling with:
- Automatic retry with exponential backoff
- Token refresh on 401 errors
- User-friendly error messages
- Offline detection and queueing
"""

import time
import asyncio
import functools
from enum import Enum
from typing import Callable, TypeVar, Optional, Any
from dataclasses import dataclass

import httpx


T = TypeVar('T')


class ErrorType(Enum):
    """Types of API errors."""
    AUTH_EXPIRED = "auth_expired"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


@dataclass
class APIError:
    """Structured API error."""
    error_type: ErrorType
    message: str
    status_code: Optional[int] = None
    raw_error: Optional[str] = None
    retryable: bool = False
    
    def __str__(self):
        return self.message


# User-friendly error messages
ERROR_MESSAGES = {
    ErrorType.AUTH_EXPIRED: "Your eBay session has expired. Please reconnect your account.",
    ErrorType.RATE_LIMITED: "Too many requests. Please wait a moment and try again.",
    ErrorType.SERVER_ERROR: "eBay is having technical difficulties. Please try again later.",
    ErrorType.NETWORK_ERROR: "Unable to connect to eBay. Please check your internet connection.",
    ErrorType.VALIDATION_ERROR: "There's an issue with your listing details.",
    ErrorType.NOT_FOUND: "The requested item was not found.",
    ErrorType.UNKNOWN: "An unexpected error occurred. Please try again.",
}


def classify_error(
    status_code: Optional[int] = None,
    exception: Optional[Exception] = None,
) -> APIError:
    """
    Classify an error and return a user-friendly APIError.
    
    Args:
        status_code: HTTP status code (if available)
        exception: The original exception (if available)
        
    Returns:
        APIError with user-friendly message
    """
    if exception:
        if isinstance(exception, httpx.ConnectError):
            return APIError(
                error_type=ErrorType.NETWORK_ERROR,
                message=ERROR_MESSAGES[ErrorType.NETWORK_ERROR],
                raw_error=str(exception),
                retryable=True,
            )
        elif isinstance(exception, httpx.TimeoutException):
            return APIError(
                error_type=ErrorType.NETWORK_ERROR,
                message="Request timed out. Please try again.",
                raw_error=str(exception),
                retryable=True,
            )
    
    if status_code:
        if status_code == 401:
            return APIError(
                error_type=ErrorType.AUTH_EXPIRED,
                message=ERROR_MESSAGES[ErrorType.AUTH_EXPIRED],
                status_code=status_code,
                retryable=True,  # Can retry after refresh
            )
        elif status_code == 429:
            return APIError(
                error_type=ErrorType.RATE_LIMITED,
                message=ERROR_MESSAGES[ErrorType.RATE_LIMITED],
                status_code=status_code,
                retryable=True,
            )
        elif status_code == 400:
            return APIError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=ERROR_MESSAGES[ErrorType.VALIDATION_ERROR],
                status_code=status_code,
                retryable=False,
            )
        elif status_code == 404:
            return APIError(
                error_type=ErrorType.NOT_FOUND,
                message=ERROR_MESSAGES[ErrorType.NOT_FOUND],
                status_code=status_code,
                retryable=False,
            )
        elif 500 <= status_code < 600:
            return APIError(
                error_type=ErrorType.SERVER_ERROR,
                message=ERROR_MESSAGES[ErrorType.SERVER_ERROR],
                status_code=status_code,
                retryable=True,
            )
    
    return APIError(
        error_type=ErrorType.UNKNOWN,
        message=ERROR_MESSAGES[ErrorType.UNKNOWN],
        status_code=status_code,
        raw_error=str(exception) if exception else None,
        retryable=False,
    )


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


# Default retry config
DEFAULT_RETRY_CONFIG = RetryConfig()


def with_retry(
    config: RetryConfig = None,
    on_retry: Callable[[int, APIError], None] = None,
):
    """
    Decorator that adds retry logic to an async function.
    
    Args:
        config: RetryConfig for retry behavior
        on_retry: Callback called before each retry (attempt, error)
        
    Usage:
        @with_retry()
        async def call_api():
            ...
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except httpx.HTTPStatusError as e:
                    error = classify_error(status_code=e.response.status_code)
                    last_error = error
                    
                    if not error.retryable or attempt >= config.max_retries:
                        raise APIException(error) from e
                    
                    # Handle 401 - try to refresh token
                    if error.error_type == ErrorType.AUTH_EXPIRED:
                        try:
                            from ebay.auth import get_auth
                            auth = get_auth()
                            await auth.refresh_token_async()
                        except:
                            pass
                    
                    delay = config.get_delay(attempt)
                    if on_retry:
                        on_retry(attempt + 1, error)
                    
                    await asyncio.sleep(delay)
                    
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    error = classify_error(exception=e)
                    last_error = error
                    
                    if attempt >= config.max_retries:
                        raise APIException(error) from e
                    
                    delay = config.get_delay(attempt)
                    if on_retry:
                        on_retry(attempt + 1, error)
                    
                    await asyncio.sleep(delay)
            
            raise APIException(last_error or classify_error())
        
        return wrapper
    return decorator


def with_retry_sync(
    config: RetryConfig = None,
    on_retry: Callable[[int, APIError], None] = None,
):
    """
    Decorator that adds retry logic to a sync function.
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except httpx.HTTPStatusError as e:
                    error = classify_error(status_code=e.response.status_code)
                    last_error = error
                    
                    if not error.retryable or attempt >= config.max_retries:
                        raise APIException(error) from e
                    
                    # Handle 401 - try to refresh token
                    if error.error_type == ErrorType.AUTH_EXPIRED:
                        try:
                            from ebay.auth import get_auth
                            auth = get_auth()
                            auth.refresh_token()
                        except:
                            pass
                    
                    delay = config.get_delay(attempt)
                    if on_retry:
                        on_retry(attempt + 1, error)
                    
                    time.sleep(delay)
                    
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    error = classify_error(exception=e)
                    last_error = error
                    
                    if attempt >= config.max_retries:
                        raise APIException(error) from e
                    
                    delay = config.get_delay(attempt)
                    if on_retry:
                        on_retry(attempt + 1, error)
                    
                    time.sleep(delay)
            
            raise APIException(last_error or classify_error())
        
        return wrapper
    return decorator


class APIException(Exception):
    """Exception wrapping an APIError."""
    
    def __init__(self, error: APIError):
        self.error = error
        super().__init__(error.message)
    
    @property
    def user_message(self) -> str:
        """Get user-friendly error message."""
        return self.error.message
    
    @property
    def is_retryable(self) -> bool:
        """Check if this error can be retried."""
        return self.error.retryable


class OfflineQueue:
    """
    Queue for operations that failed due to network errors.
    
    When internet is restored, operations can be replayed.
    """
    
    def __init__(self):
        self._queue: list[dict] = []
        self._is_offline = False
    
    @property
    def is_offline(self) -> bool:
        return self._is_offline
    
    @property
    def queue_size(self) -> int:
        return len(self._queue)
    
    def set_offline(self, offline: bool = True):
        """Set offline status."""
        self._is_offline = offline
        if offline:
            print("📴 Offline mode activated - operations will be queued")
        else:
            print("📶 Back online")
    
    def enqueue(self, operation: str, args: tuple, kwargs: dict):
        """Add an operation to the offline queue."""
        self._queue.append({
            "operation": operation,
            "args": args,
            "kwargs": kwargs,
            "queued_at": time.time(),
        })
        print(f"📋 Queued: {operation} (total: {len(self._queue)})")
    
    def peek(self) -> Optional[dict]:
        """Get the next operation without removing it."""
        return self._queue[0] if self._queue else None
    
    def dequeue(self) -> Optional[dict]:
        """Remove and return the next operation."""
        return self._queue.pop(0) if self._queue else None
    
    def clear(self):
        """Clear the queue."""
        self._queue = []
    
    async def process_queue(self, executor: Callable) -> int:
        """
        Process all queued operations.
        
        Args:
            executor: Async function that executes an operation
            
        Returns:
            Number of successfully processed operations
        """
        processed = 0
        failed = []
        
        while self._queue:
            item = self.dequeue()
            try:
                await executor(item)
                processed += 1
            except APIException as e:
                if e.error.error_type == ErrorType.NETWORK_ERROR:
                    # Still offline, put it back
                    failed.append(item)
                    self.set_offline(True)
                    break
                else:
                    # Other error, log and skip
                    print(f"❌ Failed to process queued operation: {e.user_message}")
        
        # Put failed items back
        self._queue = failed + self._queue
        return processed


# Global offline queue
_offline_queue = OfflineQueue()


def get_offline_queue() -> OfflineQueue:
    """Get the global offline queue."""
    return _offline_queue


async def check_connectivity() -> bool:
    """
    Check if we can reach eBay's API.
    
    Returns:
        True if connected, False if offline
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://api.ebay.com/")
            return response.status_code < 500
    except:
        return False


# CLI interface
if __name__ == "__main__":
    import asyncio
    
    print("=" * 50)
    print("  myBay — Connection Check")
    print("=" * 50)
    
    async def check():
        connected = await check_connectivity()
        if connected:
            print("\n✅ Connected to eBay API")
        else:
            print("\n📴 Cannot reach eBay API")
        
        queue = get_offline_queue()
        if queue.queue_size > 0:
            print(f"\n📋 Offline queue: {queue.queue_size} operations pending")
    
    asyncio.run(check())

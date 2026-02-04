"""Simple TTL cache for frequently accessed data."""

import time
import logging
from typing import Any, Optional, Dict, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class TTLCache:
    """Thread-safe TTL cache for caching expensive operations."""
    
    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if time.time() < entry["expires_at"]:
                return entry["value"]
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        expires_at = time.time() + (ttl or self._default_ttl)
        self._cache[key] = {
            "value": value,
            "expires_at": expires_at
        }
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if v["expires_at"] < now]
        for key in expired:
            del self._cache[key]
        return len(expired)
    
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        self.cleanup_expired()
        return {
            "size": len(self._cache),
            "keys": list(self._cache.keys())
        }


cache = TTLCache(default_ttl=300)


def cached(key_prefix: str, ttl: int = 300):
    """Decorator for caching function results."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{':'.join(str(a) for a in args)}"
            
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


def invalidate_user_cache(user_id: int) -> None:
    """Invalidate all cache entries for a user."""
    keys_to_delete = [k for k in cache._cache.keys() if str(user_id) in k]
    for key in keys_to_delete:
        cache.delete(key)

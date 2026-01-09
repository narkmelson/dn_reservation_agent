"""
File-based caching for API responses.

Caches Tavily API responses to avoid redundant API calls during development
and repeated discovery runs. Cache is enabled by default with 24-hour TTL.

Configuration via environment variables:
- DISABLE_CACHE=true: Disable caching entirely
- CACHE_TTL_HOURS=24: Time-to-live for cached items (default: 24 hours)
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional, Any, Dict
from functools import wraps


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / 'data' / 'cache'

# Configuration from environment
def is_cache_enabled() -> bool:
    """Check if caching is enabled (default: True)."""
    return os.getenv('DISABLE_CACHE', '').lower() != 'true'


def get_cache_ttl_seconds() -> int:
    """Get cache TTL in seconds (default: 24 hours)."""
    hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
    return hours * 3600


def get_cache_key(identifier: str) -> str:
    """
    Generate a cache key from an identifier (URL, query, etc.).

    Args:
        identifier: String to hash (URL, search query, etc.)

    Returns:
        MD5 hash of the identifier
    """
    return hashlib.md5(identifier.encode()).hexdigest()


def get_cached(identifier: str, cache_type: str = 'default') -> Optional[Any]:
    """
    Retrieve a cached value if it exists and hasn't expired.

    Args:
        identifier: The cache key identifier (URL, query, etc.)
        cache_type: Subdirectory for organizing cache (e.g., 'extract', 'map', 'search')

    Returns:
        Cached data if valid, None if expired or not found
    """
    if not is_cache_enabled():
        return None

    cache_key = get_cache_key(identifier)
    cache_subdir = CACHE_DIR / cache_type
    cache_file = cache_subdir / f"{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())

        # Check if expired
        age_seconds = time.time() - data.get('timestamp', 0)
        if age_seconds > get_cache_ttl_seconds():
            # Expired - remove the file
            cache_file.unlink(missing_ok=True)
            return None

        return data.get('content')

    except (json.JSONDecodeError, KeyError, OSError):
        # Corrupted cache file - remove it
        cache_file.unlink(missing_ok=True)
        return None


def set_cached(identifier: str, content: Any, cache_type: str = 'default') -> None:
    """
    Store a value in the cache.

    Args:
        identifier: The cache key identifier (URL, query, etc.)
        content: Data to cache (must be JSON-serializable)
        cache_type: Subdirectory for organizing cache
    """
    if not is_cache_enabled():
        return

    cache_key = get_cache_key(identifier)
    cache_subdir = CACHE_DIR / cache_type
    cache_subdir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_subdir / f"{cache_key}.json"

    try:
        cache_file.write_text(json.dumps({
            'timestamp': time.time(),
            'identifier': identifier,
            'content': content
        }, indent=2))
    except (OSError, TypeError) as e:
        # Log but don't fail if caching fails
        print(f"Warning: Failed to cache {identifier}: {e}")


def clear_cache() -> Dict[str, int]:
    """
    Clear all cached files.

    Returns:
        Dict with counts: {'files_removed': N, 'errors': M}
    """
    files_removed = 0
    errors = 0

    if not CACHE_DIR.exists():
        return {'files_removed': 0, 'errors': 0}

    # Iterate through all subdirectories
    for cache_subdir in CACHE_DIR.iterdir():
        if cache_subdir.is_dir():
            for cache_file in cache_subdir.glob('*.json'):
                try:
                    cache_file.unlink()
                    files_removed += 1
                except OSError:
                    errors += 1

    return {'files_removed': files_removed, 'errors': errors}


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with cache info: size, file count, age of oldest/newest
    """
    if not CACHE_DIR.exists():
        return {
            'enabled': is_cache_enabled(),
            'ttl_hours': get_cache_ttl_seconds() // 3600,
            'total_files': 0,
            'total_size_kb': 0,
            'cache_types': {}
        }

    stats = {
        'enabled': is_cache_enabled(),
        'ttl_hours': get_cache_ttl_seconds() // 3600,
        'total_files': 0,
        'total_size_kb': 0,
        'cache_types': {}
    }

    for cache_subdir in CACHE_DIR.iterdir():
        if cache_subdir.is_dir():
            subdir_files = list(cache_subdir.glob('*.json'))
            subdir_size = sum(f.stat().st_size for f in subdir_files)

            stats['cache_types'][cache_subdir.name] = {
                'files': len(subdir_files),
                'size_kb': round(subdir_size / 1024, 2)
            }
            stats['total_files'] += len(subdir_files)
            stats['total_size_kb'] += subdir_size / 1024

    stats['total_size_kb'] = round(stats['total_size_kb'], 2)
    return stats


def cached_tavily_call(cache_type: str):
    """
    Decorator for caching Tavily API calls.

    Usage:
        @cached_tavily_call('extract')
        def tavily_extract(client, urls):
            return client.extract(urls=urls)

    Args:
        cache_type: Type of cache ('extract', 'map', 'search', 'crawl')
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function args
            # For URLs, use the URL itself; for queries, use the query string
            cache_identifier = None

            if 'urls' in kwargs and kwargs['urls']:
                # For extract calls with multiple URLs
                cache_identifier = '|'.join(sorted(kwargs['urls']))
            elif 'url' in kwargs:
                # For map/crawl calls with single URL
                cache_identifier = kwargs['url']
            elif 'query' in kwargs:
                # For search calls
                cache_identifier = kwargs['query']
            elif len(args) > 1:
                # Fallback to positional args
                cache_identifier = str(args[1]) if args[1] else None

            if cache_identifier:
                cached = get_cached(cache_identifier, cache_type)
                if cached is not None:
                    return cached

            # Call the actual function
            result = func(*args, **kwargs)

            # Cache the result
            if cache_identifier and result:
                set_cached(cache_identifier, result, cache_type)

            return result
        return wrapper
    return decorator

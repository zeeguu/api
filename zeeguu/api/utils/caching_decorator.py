# Claude's Idea
from functools import wraps


def cache_on_data_keys(*cache_keys):
    """Decorator that caches functions taking 'data' as first parameter"""

    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(data, *args, **kwargs):
            # Create cache key from specified dictionary keys
            cache_key = tuple(data.get(key) for key in cache_keys)

            if cache_key not in cache:
                cache[cache_key] = func(data, *args, **kwargs)

            return cache[cache_key]

        # Add cache management methods
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_info = (
            lambda: f"Cache size: {len(cache)}, Keys: {list(cache.keys())}"
        )

        return wrapper

    return decorator

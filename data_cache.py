"""
Session-based data caching for Slickcharts and YFinance data
Reduces redundant API calls and improves performance
"""

import time
import json
import hashlib
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    data: Any
    timestamp: float
    ttl: float  # Time to live in seconds
    source: str
    key: str
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return time.time() - self.timestamp > self.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "data": self.data,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "source": self.source,
            "key": self.key
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Create from dictionary"""
        return cls(**data)

class DataCache:
    """Thread-safe data cache with TTL and persistence"""
    
    def __init__(self, cache_file: Optional[str] = None, default_ttl: int = 300):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self.cache_file = cache_file
        self.default_ttl = default_ttl
        self._load_from_file()
    
    def _generate_key(self, source: str, params: Dict[str, Any]) -> str:
        """Generate cache key from source and parameters"""
        # Sort parameters for consistent key generation
        sorted_params = json.dumps(params, sort_keys=True)
        key_string = f"{source}:{sorted_params}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, source: str, params: Dict[str, Any]) -> Optional[Any]:
        """Get data from cache"""
        key = self._generate_key(source, params)
        
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    logger.debug(f"Cache hit for {source} with key {key[:8]}...")
                    return entry.data
                else:
                    # Remove expired entry
                    del self._cache[key]
                    logger.debug(f"Cache entry expired for {source} with key {key[:8]}...")
            
            logger.debug(f"Cache miss for {source} with key {key[:8]}...")
            return None
    
    def set(self, source: str, params: Dict[str, Any], data: Any, ttl: Optional[int] = None) -> str:
        """Set data in cache"""
        key = self._generate_key(source, params)
        ttl = ttl or self.default_ttl
        
        with self._lock:
            entry = CacheEntry(
                data=data,
                timestamp=time.time(),
                ttl=ttl,
                source=source,
                key=key
            )
            self._cache[key] = entry
            logger.debug(f"Cached data for {source} with key {key[:8]}... (TTL: {ttl}s)")
        
        return key
    
    def invalidate(self, source: str, params: Optional[Dict[str, Any]] = None):
        """Invalidate cache entries"""
        with self._lock:
            if params is None:
                # Invalidate all entries for this source
                keys_to_remove = [
                    key for key, entry in self._cache.items()
                    if entry.source == source
                ]
            else:
                # Invalidate specific entry
                key = self._generate_key(source, params)
                keys_to_remove = [key] if key in self._cache else []
            
            for key in keys_to_remove:
                del self._cache[key]
                logger.debug(f"Invalidated cache entry {key[:8]}... for {source}")
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def cleanup_expired(self):
        """Remove expired entries from cache"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired())
            active_entries = total_entries - expired_entries
            
            # Group by source
            sources = {}
            for entry in self._cache.values():
                if entry.source not in sources:
                    sources[entry.source] = 0
                sources[entry.source] += 1
            
            return {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "expired_entries": expired_entries,
                "sources": sources,
                "memory_usage_mb": self._estimate_memory_usage()
            }
    
    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage in MB"""
        total_size = 0
        for entry in self._cache.values():
            try:
                # Rough estimate of object size
                total_size += len(str(entry.data)) * 2  # 2 bytes per char (rough estimate)
            except:
                total_size += 1024  # Fallback estimate
        return total_size / (1024 * 1024)  # Convert to MB
    
    def _load_from_file(self):
        """Load cache from file"""
        if not self.cache_file or not Path(self.cache_file).exists():
            return
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            
            with self._lock:
                for key, entry_data in data.items():
                    try:
                        entry = CacheEntry.from_dict(entry_data)
                        # Only load non-expired entries
                        if not entry.is_expired():
                            self._cache[key] = entry
                    except Exception as e:
                        logger.warning(f"Failed to load cache entry {key}: {e}")
            
            logger.info(f"Loaded {len(self._cache)} cache entries from {self.cache_file}")
            
        except Exception as e:
            logger.error(f"Failed to load cache from {self.cache_file}: {e}")
    
    def save_to_file(self):
        """Save cache to file"""
        if not self.cache_file:
            return
        
        try:
            # Create directory if it doesn't exist
            Path(self.cache_file).parent.mkdir(parents=True, exist_ok=True)
            
            with self._lock:
                # Convert to serializable format
                data = {
                    key: entry.to_dict()
                    for key, entry in self._cache.items()
                    if not entry.is_expired()  # Only save non-expired entries
                }
            
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.debug(f"Saved {len(data)} cache entries to {self.cache_file}")
            
        except Exception as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")

# Global cache instance
data_cache = DataCache(cache_file="cache/data_cache.json", default_ttl=300)

class CachedDataProvider:
    """Data provider with caching capabilities"""
    
    def __init__(self, cache: DataCache = None):
        self.cache = cache or data_cache
    
    def get_slickcharts_data(self, num_stocks: int = 15, force_refresh: bool = False) -> Optional[Any]:
        """Get Slickcharts data with caching"""
        params = {"num_stocks": num_stocks}
        
        if not force_refresh:
            cached_data = self.cache.get("slickcharts", params)
            if cached_data is not None:
                return cached_data
        
        # Data not in cache or force refresh - would be fetched by actual function
        return None
    
    def get_yfinance_data(self, symbol: str, period: str = "1y", force_refresh: bool = False) -> Optional[Any]:
        """Get YFinance data with caching"""
        params = {"symbol": symbol, "period": period}
        
        if not force_refresh:
            cached_data = self.cache.get("yfinance", params)
            if cached_data is not None:
                return cached_data
        
        # Data not in cache or force refresh - would be fetched by actual function
        return None
    
    def get_alpha_vantage_data(self, symbol: str, function: str = "GLOBAL_QUOTE", 
                              force_refresh: bool = False) -> Optional[Any]:
        """Get Alpha Vantage data with caching"""
        params = {"symbol": symbol, "function": function}
        
        if not force_refresh:
            cached_data = self.cache.get("alpha_vantage", params)
            if cached_data is not None:
                return cached_data
        
        # Data not in cache or force refresh - would be fetched by actual function
        return None
    
    def cache_slickcharts_data(self, data: Any, num_stocks: int = 15, ttl: int = 600):
        """Cache Slickcharts data"""
        params = {"num_stocks": num_stocks}
        self.cache.set("slickcharts", params, data, ttl)
    
    def cache_yfinance_data(self, data: Any, symbol: str, period: str = "1y", ttl: int = 300):
        """Cache YFinance data"""
        params = {"symbol": symbol, "period": period}
        self.cache.set("yfinance", params, data, ttl)
    
    def cache_alpha_vantage_data(self, data: Any, symbol: str, function: str = "GLOBAL_QUOTE", ttl: int = 300):
        """Cache Alpha Vantage data"""
        params = {"symbol": symbol, "function": function}
        self.cache.set("alpha_vantage", params, data, ttl)
    
    def invalidate_symbol_data(self, symbol: str):
        """Invalidate all cached data for a specific symbol"""
        self.cache.invalidate("yfinance", {"symbol": symbol})
        self.cache.invalidate("alpha_vantage", {"symbol": symbol})
        logger.info(f"Invalidated cache for symbol {symbol}")
    
    def cleanup_expired(self):
        """Clean up expired cache entries"""
        self.cache.cleanup_expired()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()

# Global data provider instance
cached_data_provider = CachedDataProvider()

# Convenience functions
def get_cached_data(source: str, params: Dict[str, Any]) -> Optional[Any]:
    """Get cached data"""
    return data_cache.get(source, params)

def set_cached_data(source: str, params: Dict[str, Any], data: Any, ttl: int = 300) -> str:
    """Set cached data"""
    return data_cache.set(source, params, data, ttl)

def invalidate_cache(source: str, params: Optional[Dict[str, Any]] = None):
    """Invalidate cache entries"""
    data_cache.invalidate(source, params)

def cleanup_cache():
    """Clean up expired cache entries"""
    data_cache.cleanup_expired()

def save_cache():
    """Save cache to file"""
    data_cache.save_to_file()
"""
Cache service module for video.fm

Centralized caching system for songs, videos, and other data.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from core.utils.cache import load_cache, save_cache


class CacheService:
    """Centralized cache management service."""
    
    def __init__(self, cache_dir: Path):
        """Initialize cache service.
        
        Args:
            cache_dir: Directory for cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Cache file paths
        self.songs_cache_file = self.cache_dir / "songs_cache.json"
        self.video_cache_file = self.cache_dir / "video_cache.json"
        self.progress_cache_file = self.cache_dir / "progress.json"
        
        # In-memory caches
        self._songs_cache = None
        self._video_cache = None
        self._progress_cache = None
    
    def load_songs_cache(self, cache_key: str) -> Optional[List[Tuple[str, str]]]:
        """Load songs from cache.
        
        Args:
            cache_key: Unique cache key for the songs
            
        Returns:
            List of (artist, title) tuples if found, None otherwise
        """
        if self._songs_cache is None:
            self._songs_cache = load_cache("songs_cache.json") or {}
        
        cached_data = self._songs_cache.get(cache_key)
        if cached_data:
            # Convert back to list of tuples
            return [(item[0], item[1]) for item in cached_data]
        return None
    
    def save_songs_cache(self, cache_key: str, songs: List[Tuple[str, str]]) -> None:
        """Save songs to cache.
        
        Args:
            cache_key: Unique cache key for the songs
            songs: List of (artist, title) tuples to cache
        """
        if self._songs_cache is None:
            self._songs_cache = load_cache("songs_cache.json") or {}
        
        # Convert tuples to list for JSON serialization
        self._songs_cache[cache_key] = [[artist, title] for artist, title in songs]
        save_cache(self._songs_cache, "songs_cache.json")
    
    def load_video_cache(self) -> Dict[str, str]:
        """Load video URL cache.
        
        Returns:
            Dictionary mapping search queries to YouTube URLs
        """
        if self._video_cache is None:
            self._video_cache = load_cache("video_cache.json") or {}
        return self._video_cache.copy()
    
    def save_video_cache(self, video_cache: Dict[str, str]) -> None:
        """Save video URL cache.
        
        Args:
            video_cache: Dictionary mapping search queries to YouTube URLs
        """
        self._video_cache = video_cache.copy()
        save_cache(self._video_cache, "video_cache.json")
    
    def get_cached_video_url(self, search_query: str) -> Optional[str]:
        """Get cached video URL for a search query.
        
        Args:
            search_query: The search query
            
        Returns:
            Cached YouTube URL if found, None otherwise
        """
        video_cache = self.load_video_cache()
        return video_cache.get(search_query)
    
    def cache_video_url(self, search_query: str, video_url: str) -> None:
        """Cache a video URL for a search query.
        
        Args:
            search_query: The search query
            video_url: The YouTube URL to cache
        """
        video_cache = self.load_video_cache()
        video_cache[search_query] = video_url
        self.save_video_cache(video_cache)
    
    def load_progress_cache(self) -> Dict[str, Any]:
        """Load progress cache.
        
        Returns:
            Dictionary with progress data
        """
        if self._progress_cache is None:
            self._progress_cache = load_cache("progress.json") or {}
        return self._progress_cache.copy()
    
    def save_progress_cache(self, progress_data: Dict[str, Any]) -> None:
        """Save progress cache.
        
        Args:
            progress_data: Progress data to cache
        """
        self._progress_cache = progress_data.copy()
        save_cache(self._progress_cache, "progress.json")
    
    def update_progress(self, key: str, value: Any) -> None:
        """Update a single progress entry.
        
        Args:
            key: Progress key
            value: Progress value
        """
        progress = self.load_progress_cache()
        progress[key] = value
        self.save_progress_cache(progress)
    
    def clear_cache(self, cache_type: str = "all") -> None:
        """Clear cache files.
        
        Args:
            cache_type: Type of cache to clear ('songs', 'video', 'progress', 'all')
        """
        if cache_type in ("songs", "all"):
            if self.songs_cache_file.exists():
                self.songs_cache_file.unlink()
            self._songs_cache = None
        
        if cache_type in ("video", "all"):
            if self.video_cache_file.exists():
                self.video_cache_file.unlink()
            self._video_cache = None
        
        if cache_type in ("progress", "all"):
            if self.progress_cache_file.exists():
                self.progress_cache_file.unlink()
            self._progress_cache = None
        
        print(f"✅ Cleared {cache_type} cache")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cache files.
        
        Returns:
            Dictionary with cache file information
        """
        info = {}
        
        for cache_name, cache_file in [
            ("songs", self.songs_cache_file),
            ("video", self.video_cache_file),
            ("progress", self.progress_cache_file)
        ]:
            if cache_file.exists():
                stat = cache_file.stat()
                info[cache_name] = {
                    "exists": True,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime
                }
            else:
                info[cache_name] = {"exists": False}
        
        return info
    
    def cleanup_old_cache(self, max_age_days: int = 30) -> None:
        """Remove old cache files.
        
        Args:
            max_age_days: Maximum age in days for cache files
        """
        import time
        
        max_age_seconds = max_age_days * 24 * 60 * 60
        current_time = time.time()
        
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.exists():
                file_age = current_time - cache_file.stat().st_mtime
                if file_age > max_age_seconds:
                    cache_file.unlink()
                    print(f"🧹 Removed old cache file: {cache_file.name}")
    
    def validate_cache_integrity(self) -> bool:
        """Validate cache file integrity.
        
        Returns:
            True if all cache files are valid, False otherwise
        """
        valid = True
        
        for cache_name, cache_file in [
            ("songs", self.songs_cache_file),
            ("video", self.video_cache_file),
            ("progress", self.progress_cache_file)
        ]:
            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"⚠️ Invalid {cache_name} cache file: {e}")
                    valid = False
        
        return valid 
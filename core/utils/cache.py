"""
Cache Utilities Module

Handles file-based caching for the video.fm application including:
- Loading and saving JSON cache files
- Managing cache directory structure
"""

import os
import sys
import json
from pathlib import Path
from typing import Any, Dict


def get_cache_dir() -> Path:
    """Get the appropriate cache directory based on environment.
    
    Returns:
        Path to cache directory
    """
    # Check if running as packaged app
    if getattr(sys, 'frozen', False):
        # If running as packaged app, use user's home directory
        base_dir = Path.home() / "Library/Application Support/video.fm"
        cache_dir = base_dir / "cache"
    else:
        # When running as script, use current directory
        cache_dir = Path("cache")
    
    # Ensure directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_cache(filename: str) -> Dict[str, Any]:
    """Load data from a JSON cache file.
    
    Args:
        filename: Name of the cache file
        
    Returns:
        Dictionary containing cached data, empty dict if file doesn't exist
    """
    cache_dir = get_cache_dir()
    cache_file = cache_dir / filename
    
    try:
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ Error loading cache {filename}: {e}")
    
    return {}


def save_cache(data: Dict[str, Any], filename: str) -> None:
    """Save data to a JSON cache file.
    
    Args:
        data: Dictionary to save to cache
        filename: Name of the cache file
    """
    cache_dir = get_cache_dir()
    cache_file = cache_dir / filename
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"⚠️ Error saving cache {filename}: {e}")


def clear_cache(filename: str = None) -> None:
    """Clear cache file(s).
    
    Args:
        filename: Specific cache file to clear, or None to clear all cache files
    """
    cache_dir = get_cache_dir()
    
    if filename:
        # Clear specific file
        cache_file = cache_dir / filename
        if cache_file.exists():
            cache_file.unlink()
            print(f"✅ Cleared cache: {filename}")
    else:
        # Clear all cache files
        for cache_file in cache_dir.glob("*.json"):
            cache_file.unlink()
            print(f"✅ Cleared cache: {cache_file.name}")


def get_cache_size(filename: str = None) -> int:
    """Get the size of cache file(s) in bytes.
    
    Args:
        filename: Specific cache file to check, or None for total cache size
        
    Returns:
        Size in bytes
    """
    cache_dir = get_cache_dir()
    
    if filename:
        # Get size of specific file
        cache_file = cache_dir / filename
        return cache_file.stat().st_size if cache_file.exists() else 0
    else:
        # Get total cache size
        total_size = 0
        for cache_file in cache_dir.glob("*.json"):
            total_size += cache_file.stat().st_size
        return total_size 
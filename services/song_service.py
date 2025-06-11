"""
Song service module for video.fm

Handles all song data fetching, processing, and management operations.
"""

import os
import requests
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from core.api.lastfm_client import create_lastfm_client
from services.cache_service import CacheService


class SongService:
    """Handles song data fetching and processing operations."""
    
    def __init__(self, cache_service: CacheService):
        """Initialize song service.
        
        Args:
            cache_service: CacheService instance for caching operations
        """
        self.cache_service = cache_service
        self.lastfm_client = None
    
    def initialize_lastfm_client(self, api_key: str) -> bool:
        """Initialize Last.fm API client.
        
        Args:
            api_key: Last.fm API key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.lastfm_client = create_lastfm_client(api_key)
            return True
        except Exception as e:
            print(f"❌ Error initializing Last.fm client: {e}")
            return False
    
    def get_top_songs(self, username: str, time_period: str, target_year: int, 
                     target_month: Optional[int] = None, num_songs: int = 50) -> List[Tuple[str, str]]:
        """Get top songs from Last.fm with caching.
        
        Args:
            username: Last.fm username
            time_period: 'month', 'year', or 'alltime'
            target_year: Target year for the data
            target_month: Target month (if time_period is 'month')
            num_songs: Number of songs to fetch
            
        Returns:
            List of (artist, title) tuples
        """
        # Create cache key
        cache_key = self._create_cache_key(username, time_period, target_year, target_month, num_songs)
        
        # Try to load from cache first
        cached_songs = self.cache_service.load_songs_cache(cache_key)
        if cached_songs:
            print(f"✅ Loaded {len(cached_songs)} songs from cache")
            return cached_songs
        
        # Fetch from API if not in cache
        print(f"🔍 Fetching top {num_songs} songs from Last.fm...")
        
        if not self.lastfm_client:
            raise ValueError("Last.fm client not initialized. Call initialize_lastfm_client() first.")
        
        try:
            # Make API request using the correct method
            songs = self.lastfm_client.get_top_songs(
                username=username,
                time_period=time_period,
                target_year=int(target_year),
                target_month=int(target_month) if target_month else None,
                num_songs=num_songs
            )
            
            # The Last.fm client already returns (artist, title) tuples
            processed_songs = songs
            
            # Cache the results
            self.cache_service.save_songs_cache(cache_key, processed_songs)
            
            print(f"✅ Successfully fetched {len(processed_songs)} songs from Last.fm")
            return processed_songs
            
        except Exception as e:
            print(f"❌ Error fetching songs from Last.fm: {e}")
            return []
    
    def clean_query(self, text: str) -> str:
        """Clean search query text for better YouTube matching.
        
        Args:
            text: Raw search text
            
        Returns:
            Cleaned search text
        """
        import re
        
        # Remove common bracketed content that hurts search results
        # Remove content in brackets/parentheses that typically contains:
        # - feat./featuring artists
        # - remix information  
        # - release info
        # - version info
        
        patterns_to_remove = [
            r'\[.*?\]',  # Square brackets
            r'\(.*?\)',  # Parentheses
            r'\bfeat\.?\s+.*',  # featuring
            r'\bfeaturing\s+.*',  # featuring
            r'\bft\.?\s+.*',  # ft.
            r'\bremix\b.*',  # remix
            r'\bremaster\b.*',  # remaster
            r'\b\d{4}\s+remaster\b',  # year remaster
            r'-\s*remaster.*',  # dash remaster
        ]
        
        cleaned = text
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned.strip()
    
    def _create_cache_key(self, username: str, time_period: str, target_year: int, 
                         target_month: Optional[int], num_songs: int) -> str:
        """Create a unique cache key for the song request."""
        if time_period == 'month':
            # Ensure target_month is an integer
            month_int = int(target_month) if target_month is not None else 1
            return f"{username}_{time_period}_{target_year}_{month_int:02d}_{num_songs}"
        elif time_period == 'year':
            return f"{username}_{time_period}_{target_year}_{num_songs}"
        else:  # alltime
            return f"{username}_{time_period}_{num_songs}"
    
    def _get_month_date_range(self, year: int, month: int) -> Tuple[str, str]:
        """Get Unix timestamp range for a specific month."""
        import calendar
        import datetime
        
        # Convert to integers if they're strings
        year = int(year) if isinstance(year, str) else year
        month = int(month) if isinstance(month, str) else month
        
        # First day of the month
        start_date = datetime.datetime(year, month, 1)
        
        # Last day of the month
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime.datetime(year, month, last_day, 23, 59, 59)
        
        # Convert to Unix timestamps
        from_timestamp = str(int(start_date.timestamp()))
        to_timestamp = str(int(end_date.timestamp()))
        
        return from_timestamp, to_timestamp
    
    def _get_year_date_range(self, year: int) -> Tuple[str, str]:
        """Get Unix timestamp range for a specific year."""
        import datetime
        
        # First day of the year
        start_date = datetime.datetime(year, 1, 1)
        
        # Last day of the year
        end_date = datetime.datetime(year, 12, 31, 23, 59, 59)
        
        # Convert to Unix timestamps
        from_timestamp = str(int(start_date.timestamp()))
        to_timestamp = str(int(end_date.timestamp()))
        
        return from_timestamp, to_timestamp
    
    def _process_song_data(self, raw_songs: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """Process raw API response into (artist, title) tuples.
        
        Args:
            raw_songs: Raw song data from Last.fm API
            
        Returns:
            List of (artist, title) tuples
        """
        processed_songs = []
        
        for song_data in raw_songs:
            try:
                # Extract artist and title from Last.fm response format
                if isinstance(song_data, dict):
                    artist = song_data.get('artist', {})
                    if isinstance(artist, dict):
                        artist_name = artist.get('name', '')
                    else:
                        artist_name = str(artist)
                    
                    title = song_data.get('name', '')
                    
                    if artist_name and title:
                        processed_songs.append((artist_name, title))
                        
            except Exception as e:
                print(f"⚠️ Error processing song data: {e}")
                continue
        
        return processed_songs
    
    def validate_songs_data(self, songs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Validate and filter song data.
        
        Args:
            songs: List of (artist, title) tuples
            
        Returns:
            Filtered list of valid songs
        """
        valid_songs = []
        
        for artist, title in songs:
            # Basic validation
            if not artist or not title:
                continue
            
            # Remove very short or suspicious entries
            if len(artist.strip()) < 2 or len(title.strip()) < 2:
                continue
            
            # Clean up the data
            clean_artist = artist.strip()
            clean_title = title.strip()
            
            valid_songs.append((clean_artist, clean_title))
        
        return valid_songs 
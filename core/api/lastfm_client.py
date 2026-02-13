"""
Last.fm API Client Module

Handles all interactions with the Last.fm API including:
- Fetching user listening history
- Caching scrobble data
- Calculating top songs for different time periods
"""

import os
import sys
import time
import datetime
import requests
from collections import Counter
from typing import List, Tuple, Optional, Dict, Any

# Import utility functions
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from core.utils.cache import load_cache, save_cache


class LastFmClient:
    """Client for interacting with Last.fm API."""

    API_BASE_URL = "https://ws.audioscrobbler.com/2.0/"
    
    def __init__(self, api_key: str):
        """Initialize the Last.fm client.
        
        Args:
            api_key: Last.fm API key
        """
        self.api_key = api_key
        self.cache_file = "lastfm_cache.json"
        self._session = requests.Session()
        # Some endpoints/providers get picky without a User-Agent; include one.
        self._session.headers.update(
            {
                "User-Agent": "video.fm/1.0 (+https://github.com/; contact: local)",
                "Accept": "application/json",
            }
        )
        
    def get_top_songs(self, username: str, time_period: str, target_year: int, 
                     target_month: Optional[int] = None, num_songs: int = 10) -> List[Tuple[str, str]]:
        """Fetch top songs for the specified time period from Last.fm.
        
        Uses cached data when available. Otherwise, fetches all scrobbles for the 
        time period and calculates the top songs.
        
        Args:
            username: Last.fm username
            time_period: "month", "year", or "alltime"
            target_year: Year to fetch data for
            target_month: Month to fetch data for (required if time_period is "month")
            num_songs: Number of top songs to return
            
        Returns:
            List of tuples containing (artist, title) for the top songs
        """
        cache = load_cache(self.cache_file)
        
        # Create cache key based on time period
        if time_period == "month":
            cache_key = f"{username}_{target_year}-{int(target_month):02d}"
            period_description = f"{target_year}-{int(target_month):02d}"
        elif time_period == "year":
            cache_key = f"{username}_{target_year}"
            period_description = f"{target_year}"
        else:  # alltime
            cache_key = f"{username}_alltime"
            period_description = "all-time"
        
        current_time = int(time.time())

        # Adaptive cache expiration based on time period
        cache_duration = self._get_cache_duration(time_period)

        # Check cache first with adaptive expiration
        if cache_key in cache and current_time - cache[cache_key].get("last_fetched", 0) < cache_duration:
            print(f"✅ Using cached data for {cache_key}")
            top_songs = [
                artist_title
                for artist_title, _ in Counter(map(tuple, cache[cache_key]["scrobbles"])).most_common(num_songs)
            ]
            print(f"📋 Top songs from cache: {top_songs}")
            sys.stdout.flush()
            return top_songs

        # Fetch fresh data from API
        scrobbles = self._fetch_scrobbles_for_period(username, time_period, target_year, target_month, period_description)
        
        # Count occurrences of each song and get the most-played ones
        track_counts = Counter(scrobbles).most_common(num_songs)

        # Save results to cache
        cache[cache_key] = {
            "last_fetched": int(time.time()),
            "scrobbles": scrobbles
        }
        save_cache(cache, self.cache_file)

        return [song[0] for song in track_counts]
    
    def _get_cache_duration(self, time_period: str) -> int:
        """Get cache duration based on time period.
        
        Args:
            time_period: "month", "year", or "alltime"
            
        Returns:
            Cache duration in seconds
        """
        if time_period == "alltime":
            # All-time: cache for 7 days (since all-time data changes slowly)
            return 7 * 24 * 3600  # 7 days
        elif time_period == "year":
            # Yearly: cache for 1 day (yearly data is relatively stable)
            return 24 * 3600  # 1 day
        else:  # monthly
            # Monthly: cache for 6 hours (monthly data can change more frequently)
            return 6 * 3600  # 6 hours
    
    def _fetch_scrobbles_for_period(self, username: str, time_period: str, target_year: int, 
                                   target_month: Optional[int], period_description: str) -> List[Tuple[str, str]]:
        """Fetch scrobbles from Last.fm API for the specified time period.
        
        Args:
            username: Last.fm username
            time_period: "month", "year", or "alltime"
            target_year: Year to fetch data for
            target_month: Month to fetch data for (required if time_period is "month")
            period_description: Human-readable description of the period
            
        Returns:
            List of (artist, title) tuples
        """
        # Determine timestamp range for the target period
        start_date, end_date = self._get_date_range(time_period, target_year, target_month)
        
        all_tracks = []
        page = 1
        found_earliest = False  # Flag to track when we've found the earliest track for the period

        # Fetch all scrobbles from Last.fm API
        while not found_earliest:
            print(f"📥 Fetching page {page} from Last.fm...")
            sys.stdout.flush()  # Force output to be sent immediately
            
            try:
                params = {
                    "method": "user.getrecenttracks",
                    "user": username,
                    "api_key": self.api_key,
                    "format": "json",
                    "limit": 1000,
                    "page": page,
                }

                response = self._session.get(self.API_BASE_URL, params=params, timeout=20)

                # Handle rate limiting explicitly so we can retry a few times.
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    sleep_s = 2.0
                    if retry_after:
                        try:
                            sleep_s = max(1.0, float(retry_after))
                        except ValueError:
                            pass
                    print(f"⏳ Last.fm rate limited (429). Sleeping {sleep_s:.1f}s then retrying…")
                    time.sleep(sleep_s)
                    continue

                # Raise for other HTTP errors, but provide a helpful message for 403/401.
                if response.status_code in (401, 403):
                    raise RuntimeError(
                        "Last.fm API request was forbidden. "
                        "This is usually an invalid/disabled API key, or a blocked/non-HTTPS request."
                    )

                response.raise_for_status()

                data: Dict[str, Any] = response.json()

                # Check for API errors
                if "error" in data:
                    # Example: {"error":6,"message":"Invalid parameters","links":[]}
                    message = data.get("message") or "Unknown Last.fm API error"
                    raise RuntimeError(f"Last.fm API error: {message}")

                # Validate response structure
                if 'recenttracks' not in data or 'track' not in data['recenttracks']:
                    raise RuntimeError("Invalid Last.fm API response (missing recenttracks.track)")

                tracks = data["recenttracks"]["track"]
                if not tracks:
                    break  # No more tracks to fetch

                for track in tracks:
                    # Skip currently playing track (no timestamp)
                    if "date" in track:
                        timestamp = int(track["date"]["uts"])

                        if time_period == "alltime":
                            # All-time: collect all tracks
                            artist = track["artist"]["#text"]
                            title = track["name"]
                            all_tracks.append((artist, title))
                        elif start_date <= timestamp < end_date:
                            # Track belongs to our target period
                            artist = track["artist"]["#text"]
                            title = track["name"]
                            all_tracks.append((artist, title))
                        elif timestamp < start_date:
                            # We've reached tracks before our target period
                            print(f"✅ Found earliest track for {period_description}, stopping fetch.")
                            sys.stdout.flush()
                            found_earliest = True
                            break

                # For all-time, stop when we've processed all available tracks
                if time_period == "alltime" and len(tracks) < 1000:
                    print(f"✅ Reached end of {period_description} data, stopping fetch.")
                    sys.stdout.flush()
                    found_earliest = True
                    break

                if found_earliest:
                    break

            except (requests.exceptions.RequestException, ValueError) as e:
                # ValueError can happen from response.json() on invalid payloads.
                raise RuntimeError(f"Error fetching data from Last.fm: {e}") from e

            page += 1
            time.sleep(0.5)  # Prevent API rate-limiting

        return all_tracks
    
    def _get_date_range(self, time_period: str, target_year: int, target_month: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
        """Get start and end timestamps for the specified time period.
        
        Args:
            time_period: "month", "year", or "alltime"
            target_year: Year to fetch data for
            target_month: Month to fetch data for
            
        Returns:
            Tuple of (start_timestamp, end_timestamp) or (None, None) for alltime
        """
        if time_period == "month":
            start_date = int(datetime.datetime(int(target_year), int(target_month), 1).timestamp())
            
            # Calculate end date (first day of next month)
            if int(target_month) < 12:
                end_date = int(datetime.datetime(int(target_year), int(target_month) + 1, 1).timestamp())
            else:
                end_date = int(datetime.datetime(int(target_year) + 1, 1, 1).timestamp())
                
            return start_date, end_date
            
        elif time_period == "year":
            # Yearly: from January 1st to December 31st
            start_date = int(datetime.datetime(int(target_year), 1, 1).timestamp())
            end_date = int(datetime.datetime(int(target_year) + 1, 1, 1).timestamp())
            return start_date, end_date
            
        else:  # alltime
            # All-time: no date filtering
            return None, None


def create_lastfm_client(api_key: str) -> LastFmClient:
    """Factory function to create a Last.fm client.
    
    Args:
        api_key: Last.fm API key
        
    Returns:
        LastFmClient instance
        
    Raises:
        ValueError: If API key is not provided
    """
    if not api_key:
        raise ValueError("Last.fm API key is required")
    
    return LastFmClient(api_key) 
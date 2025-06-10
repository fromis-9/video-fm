"""
YouTube API Client Module

Handles all interactions with the YouTube Data API including:
- Searching for music videos
- Managing API keys and quota limits
- Smart video matching and ranking
"""

import os
import sys
import re
from typing import Optional, Dict, Any, List
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import utility functions
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from core.utils.cache import load_cache, save_cache


class YouTubeClient:
    """Client for interacting with YouTube Data API."""
    
    def __init__(self, api_key: str):
        """Initialize the YouTube client.
        
        Args:
            api_key: YouTube Data API key
        """
        self.api_key = api_key
        self.service = self._build_service()
        self.cache_file = "video_cache.json"
        self.progress_file = "progress.json"
        
    def _build_service(self):
        """Build YouTube service with current API key."""
        return build("youtube", "v3", developerKey=self.api_key)
    
    def update_api_key(self, new_api_key: str):
        """Update the API key and rebuild the service.
        
        Args:
            new_api_key: New YouTube Data API key
        """
        self.api_key = new_api_key
        self.service = self._build_service()
    
    def search_video(self, artist: str, title: str, allow_manual_input: bool = False) -> Optional[str]:
        """Search for a YouTube video matching the artist and title.
        
        Optimized for all languages and international music while
        being efficient with API usage. Prioritizes official music videos
        over lyric videos and other content.
        
        Args:
            artist: Artist name
            title: Song title
            allow_manual_input: Whether to allow manual URL input if no video found
            
        Returns:
            YouTube URL if found, None if not found
        """
        artist, title = str(artist), str(title)
        
        # Use a less aggressive cleaning function for non-Latin scripts
        def gentle_clean(text):
            # Remove only problematic characters but preserve non-Latin characters
            return re.sub(r'[#<>:"?*|/\\]', "", text)
        
        # Create query with minimal cleaning to preserve non-Latin characters
        query = f"{gentle_clean(artist)} - {gentle_clean(title)}"

        # Check progress cache for previously processed queries
        progress = load_cache(self.progress_file)
        if query in progress:
            print(f"🔁 Using cached result for: {query}")
            return progress[query]

        # Check video cache
        video_cache = load_cache(self.cache_file)

        # Define search queries with international terms
        search_queries = [
            # First try: Artist - Title (exact match)
            f"{artist} - {title}",
            # Second try: Add universal terms for official content
            f"{artist} - {title} official MV"
        ]
        
        # Find the best video match
        best_match = self._search_with_queries(search_queries, artist, title)
        
        if best_match:
            # Save results in both caches
            video_cache[query] = best_match['url']
            save_cache(video_cache, self.cache_file)
            progress[query] = best_match['url']
            save_cache(progress, self.progress_file)
            
            return best_match['url']
        
        # No matches found through automatic search
        print(f"❌ No valid video found for {artist} - {title}")
        sys.stdout.flush()
        
        # Allow user manual input if enabled
        if allow_manual_input:
            user_input = input(f"❌ No valid video found for {artist} - {title}. Enter a manual YouTube URL (or press Enter to skip): ").strip()
            
            if user_input.startswith("https://www.youtube.com/watch"):
                print(f"✅ Manual URL provided: {user_input}")
                # Save manual URL to cache
                video_cache[query] = user_input
                save_cache(video_cache, self.cache_file)
                progress[query] = user_input
                save_cache(progress, self.progress_file)
                return user_input
            else:
                print(f"⏭️ Skipping {artist} - {title}")
                # Cache the skip decision
                progress[query] = None
                save_cache(progress, self.progress_file)
                return None
        
        # Cache the failed search
        progress[query] = None
        save_cache(progress, self.progress_file)
        return None
    
    def _search_with_queries(self, search_queries: List[str], artist: str, title: str) -> Optional[Dict[str, Any]]:
        """Search YouTube with multiple queries and return the best match.
        
        Args:
            search_queries: List of search query strings
            artist: Artist name
            title: Song title
            
        Returns:
            Best match video data or None
        """
        # Group indicators by priority tiers (1 = highest, 3 = lowest)
        quality_indicators = {
            # Tier 1: Official music videos (highest priority)
            "music_video": [
                # Universal
                "official music video", "official video", "mv", "m/v", "vevo", "music video",
                # Korean
                "뮤직비디오", "official mv", "performance video", "special clip",
                # Japanese
                "ミュージックビデオ", "pv", "オフィシャル",
                # Spanish
                "video oficial",
                # Portuguese 
                "vídeo oficial", "clipe oficial",
                # French
                "clip officiel", "vidéo officielle",
                # Chinese
                "官方完整版", "官方版", "官方高清", "官方网易云", "MV超清", "官方MV", "完整版",
                # Hindi/Indian
                "official video song", "full video song",
                # Russian/Slavic
                "официальное видео", "официальный клип", "официальная премьера", "музыкальный клип",
                # German
                "offizielles video", "offizielles musikvideo", "offizieller musikfilm",
                # Arabic
                "فيديو كليب رسمي", "الفيديو الرسمي",
                # Italian
                "video ufficiale", "videoclip ufficiale",
                # Turkish
                "resmi video", "resmi müzik video", "official video klip",
                # Thai
                "เอ็มวี", "มิวสิควิดีโอ",
                # Indonesian/Malay
                "video klip resmi", "video rasmi", "musik video"
            ],
            
            # Tier 2: Topic channels and official audio (medium priority)
            "audio": [
                # Official audio indicators
                "official audio", "audio oficial", "audio ufficiale", 
                # Generic Topic channel indicators
                "topic", "studio", "audio", "- Topic"
            ],
            
            # Tier 3: Lyric videos (lowest priority)
            "lyrics": [
                "lyric video", "lyrics", "with lyrics", "letra", "paroles",
                "लिरिक्स", "lirik video", "official visualizer", "visualizer"
            ]
        }
        
        # Function to check what tier a video belongs to
        def get_match_tier(video_title_lower, channel_title):
            # Check for Topic channels specifically
            if "- Topic" in channel_title:
                return "audio", "- Topic"
                
            # Check each tier from highest to lowest
            for tier, indicators in quality_indicators.items():
                for indicator in indicators:
                    if indicator.lower() in video_title_lower:
                        return tier, indicator
                        
            # No specific tier found
            return None, None
        
        # Try each query
        best_matches = {
            "music_video": None,  # Best music video match
            "audio": None,        # Best audio match
            "lyrics": None,       # Best lyric video match
            "other": None         # Fallback match
        }
        
        for search_query in search_queries:
            try:
                print(f"🔍 Searching: {search_query}...")
                request = self.service.search().list(
                    part="snippet",
                    q=search_query,
                    type="video",
                    maxResults=8,
                    order="relevance",
                    videoCategoryId="10"  # Music category
                )
                response = request.execute()
                
                # First pass: Categorize all videos by tier and find the best in each
                for item in response.get("items", []):
                    video_title = item["snippet"]["title"]
                    video_title_lower = video_title.lower()
                    channel_title = item["snippet"]["channelTitle"]
                    
                    # Basic relevance check - need either title or artist in the video title
                    is_relevant = (title.lower() in video_title_lower) or (artist.lower() in video_title_lower)
                    
                    # Skip if not even relevant
                    if not is_relevant:
                        continue
                        
                    # Get the tier of this video
                    tier, indicator = get_match_tier(video_title_lower, channel_title)
                    
                    # If no specific tier, check other quality signals
                    is_artist_channel = artist.lower() in channel_title.lower()
                    title_exact_match = (
                        f"{artist} - {title}".lower() in video_title_lower or 
                        f"{title} - {artist}".lower() in video_title_lower
                    )
                    
                    # Store the video in its tier if we don't have one yet for this tier
                    if 'videoId' in item['id']:  # Add this check
                        video_id = item['id']['videoId']
                        video_data = {
                            'id': video_id,
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'title': video_title,
                            'channel': channel_title,
                            'exact_match': title_exact_match,
                            'artist_channel': is_artist_channel,
                            'indicator': indicator
                        }
                        
                        # High-quality perfect match
                        if title_exact_match or (is_artist_channel and title.lower() in video_title_lower):
                            # Put in appropriate tier, or "other" if no specific tier
                            tier_key = tier if tier else "other"
                            if not best_matches[tier_key]:
                                best_matches[tier_key] = video_data
                        elif is_relevant:
                            # Less perfect but still relevant match
                            tier_key = tier if tier else "other"
                            if not best_matches[tier_key]:
                                best_matches[tier_key] = video_data
                
                # If we found at least one good match, stop searching
                if any(best_matches.values()):
                    break
                    
            except HttpError as e:
                print(f"❌ YouTube API Error: {e}")
                if e.resp.status == 403:
                    print("⚠️ YouTube API quota exceeded!")
                    raise  # Re-raise to be handled by calling code
                else:
                    print(f"⚠️ YouTube API Error (status {e.resp.status}): {e}")
                    raise
            except Exception as e:
                print(f"❌ Unexpected error during YouTube search: {type(e).__name__}: {e}")
                break
        
        # Return the best match based on priority tier
        for tier in ["music_video", "audio", "lyrics", "other"]:
            if best_matches[tier]:
                match = best_matches[tier]
                
                # Determine the match type description
                if tier == "music_video":
                    match_type = "music video"
                elif tier == "audio":
                    match_type = "audio" if match['indicator'] != "- Topic" else "topic channel"
                elif tier == "lyrics":
                    match_type = "lyric video"
                else:
                    match_type = "relevant video"
                    
                print(f"✅ Found {match_type}: {match['url']}")
                print(f"   Title: '{match['title']}'")
                print(f"   Channel: {match['channel']}")
                
                return match
        
        return None


def create_youtube_client(api_key: str) -> YouTubeClient:
    """Factory function to create a YouTube client.
    
    Args:
        api_key: YouTube Data API key
        
    Returns:
        YouTubeClient instance
        
    Raises:
        ValueError: If API key is not provided
    """
    if not api_key:
        raise ValueError("YouTube API key is required")
    
    return YouTubeClient(api_key) 
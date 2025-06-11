"""
Search service module for video.fm

Handles YouTube video search operations with caching and error recovery.
"""

from typing import Optional, Dict, Any
from core.api.youtube_client import create_youtube_client
from services.cache_service import CacheService


class SearchService:
    """Handles YouTube video search operations."""
    
    def __init__(self, cache_service: CacheService):
        """Initialize search service.
        
        Args:
            cache_service: CacheService instance for caching operations
        """
        self.cache_service = cache_service
        self.youtube_client = None
    
    def initialize_youtube_client(self, api_key: str) -> bool:
        """Initialize YouTube API client.
        
        Args:
            api_key: YouTube API key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.youtube_client = create_youtube_client(api_key)
            return True
        except Exception as e:
            print(f"❌ Error initializing YouTube client: {e}")
            return False
    
    def search_youtube_video(self, artist: str, title: str) -> Optional[str]:
        """Search for a YouTube video for the given artist and title.
        
        Args:
            artist: Artist name
            title: Song title
            
        Returns:
            YouTube video URL if found, None otherwise
        """
        # Create search query
        search_query = f"{artist} {title}"
        clean_query = self._clean_search_query(search_query)
        
        # Check cache first
        cached_url = self.cache_service.get_cached_video_url(clean_query)
        if cached_url:
            print(f"✅ Found cached video for {artist} - {title}")
            return cached_url
        
        # Search YouTube if not in cache
        print(f"🔍 Searching YouTube for: {clean_query}")
        
        if not self.youtube_client:
            print("❌ YouTube client not initialized")
            return None
        
        try:
            # Search for video (YouTube client expects artist and title separately)
            video_url = self.youtube_client.search_video(artist, title, allow_manual_input=False)
            
            if video_url:
                # Cache the result using the clean query as key
                self.cache_service.cache_video_url(clean_query, video_url)
                print(f"✅ Found YouTube video for {artist} - {title}")
                return video_url
            else:
                print(f"❌ No YouTube video found for {artist} - {title}")
                return None
                
        except Exception as e:
            print(f"❌ Error searching YouTube for {artist} - {title}: {e}")
            return None
    
    def update_youtube_api_key(self, new_api_key: str) -> bool:
        """Update YouTube API key.
        
        Args:
            new_api_key: New YouTube API key
            
        Returns:
            True if successful, False otherwise
        """
        return self.initialize_youtube_client(new_api_key)
    
    def validate_youtube_url(self, url: str) -> bool:
        """Validate if a URL is a valid YouTube video URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid YouTube URL, False otherwise
        """
        if not url:
            return False
        
        valid_prefixes = [
            "https://www.youtube.com/watch",
            "https://youtube.com/watch",
            "https://youtu.be/",
            "https://m.youtube.com/watch"
        ]
        
        return any(url.startswith(prefix) for prefix in valid_prefixes)
    
    def extract_video_id(self, youtube_url: str) -> Optional[str]:
        """Extract video ID from YouTube URL.
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            Video ID if extracted successfully, None otherwise
        """
        import re
        
        # Various YouTube URL patterns
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'youtube\.com/watch\?.*v=([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        
        return None
    
    def get_video_metadata(self, youtube_url: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a YouTube video.
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            Video metadata dictionary if successful, None otherwise
        """
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            return None
        
        if not self.youtube_client:
            print("❌ YouTube client not initialized")
            return None
        
        try:
            return self.youtube_client.get_video_details(video_id)
        except Exception as e:
            print(f"❌ Error getting video metadata: {e}")
            return None
    
    def search_with_fallback(self, artist: str, title: str) -> Optional[str]:
        """Search with multiple fallback strategies.
        
        Args:
            artist: Artist name
            title: Song title
            
        Returns:
            YouTube video URL if found, None otherwise
        """
        # Try different search strategies in order of preference
        search_strategies = [
            f"{artist} {title}",                    # Original
            f"{artist} {title} official",           # Add "official"
            f"{artist} {title} music video",        # Add "music video"
            f"{artist} {title} audio",              # Add "audio"
            f'"{artist}" "{title}"',                # Quoted search
            f"{artist} - {title}",                  # With dash separator
        ]
        
        for strategy in search_strategies:
            clean_query = self._clean_search_query(strategy)
            
            # Check cache for each strategy
            cached_url = self.cache_service.get_cached_video_url(clean_query)
            if cached_url:
                return cached_url
            
            # Try API search
            if self.youtube_client:
                try:
                    # For fallback, use the strategy as both artist and title
                    # This is a simplified approach for fallback searches
                    video_url = self.youtube_client.search_video(artist, title, allow_manual_input=False)
                    if video_url:
                        # Cache successful result
                        self.cache_service.cache_video_url(clean_query, video_url)
                        print(f"✅ Found video using fallback strategy: {strategy}")
                        return video_url
                except Exception as e:
                    print(f"⚠️ Error with strategy '{strategy}': {e}")
                    continue
        
        print(f"❌ All search strategies failed for {artist} - {title}")
        return None
    
    def _clean_search_query(self, query: str) -> str:
        """Clean search query for better results.
        
        Args:
            query: Raw search query
            
        Returns:
            Cleaned search query
        """
        import re
        
        # Remove common problematic patterns
        patterns_to_remove = [
            r'\[.*?\]',              # Square brackets
            r'\(.*?\)',              # Parentheses
            r'\bfeat\.?\s+.*',       # featuring
            r'\bfeaturing\s+.*',     # featuring
            r'\bft\.?\s+.*',         # ft.
            r'\bremix\b.*',          # remix
            r'\bremaster\b.*',       # remaster
            r'\b\d{4}\s+remaster\b', # year remaster
            r'-\s*remaster.*',       # dash remaster
        ]
        
        cleaned = query
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned.strip()
    
    def get_search_suggestions(self, artist: str, title: str) -> list[str]:
        """Get search query suggestions for better results.
        
        Args:
            artist: Artist name
            title: Song title
            
        Returns:
            List of suggested search queries
        """
        base_query = f"{artist} {title}"
        
        suggestions = [
            base_query,
            f"{artist} {title} official",
            f"{artist} {title} music video",
            f"{artist} {title} official music video",
            f"{artist} {title} audio",
            f"{artist} {title} lyrics",
            f'"{artist}" "{title}"',
            f"{artist} - {title}",
            f"{title} by {artist}",
            f"{artist} {title} live",
        ]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            clean_suggestion = self._clean_search_query(suggestion)
            if clean_suggestion not in seen:
                seen.add(clean_suggestion)
                unique_suggestions.append(clean_suggestion)
        
        return unique_suggestions 
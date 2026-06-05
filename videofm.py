#!/usr/bin/env python3
"""
video.fm - Video Compilation Creator from Last.fm Top Songs

A modular application that creates video compilations from Last.fm top songs using YouTube videos.
Transformed from monolithic architecture to clean service-oriented design.

Author: video.fm team
Architecture: Service-oriented with clean separation of concerns
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Core configuration and services
from config import VideoConfig
from services.song_service import SongService
from services.cache_service import CacheService
from services.search_service import SearchService
from services.compilation_service import CompilationService

# Video processing components
from downloader import VideoDownloader
from processor import VideoProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('videofm.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class VideoFMApp:
    """
    Main application orchestrator for video.fm
    
    Coordinates between services to create video compilations from Last.fm data.
    """
    
    def __init__(self):
        """Initialize the application with all required services."""
        logger.info("Initializing video.fm application...")
        
        # Load configuration
        self.config = VideoConfig()
        
        # Initialize core services
        self.cache_service = CacheService(self.config.cache_dir)
        self.song_service = SongService(self.cache_service)
        self.search_service = SearchService(self.cache_service)
        self.compilation_service = CompilationService(self.config)
        
        # Initialize video processing components
        self.downloader = VideoDownloader(self.config)
        self.processor = VideoProcessor(self.config)
        
        logger.info("Application initialization complete")
    
    def validate_environment(self) -> bool:
        """
        Validate that all required environment variables and dependencies are available.
        
        Returns:
            bool: True if environment is valid, False otherwise
        """
        logger.info("Validating environment...")
        
        # Check required API keys
        required_env_vars = ['LASTFM_API_KEY', 'YOUTUBE_API_KEY']
        missing_vars = []
        
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {missing_vars}")
            print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set these variables and try again.")
            return False
        
        # Validate external dependencies
        try:
            import yt_dlp
            import ffmpeg
            logger.info("External dependencies validated successfully")
        except ImportError as e:
            logger.error(f"Missing required dependency: {e}")
            print(f"\n❌ Missing required dependency: {e}")
            print("Please install all dependencies and try again.")
            return False
        
        logger.info("Environment validation successful")
        return True
    
    def get_user_input(self) -> Tuple[str, int, str, Optional[int], Optional[int], str, bool]:
        """
        Get user input for compilation parameters.
        
        Returns:
            Tuple[str, int, str, Optional[int], Optional[int], str, bool]:
                username, number of songs, time period, target_year, target_month, output_format, enable_replacement
        """
        print("\n🎵 Welcome to video.fm - Video Compilation Creator")
        print("=" * 50)

        username = os.getenv('LASTFM_USER')
        if not username:
            username = input("\nEnter your Last.fm username: ").strip()
            if not username:
                print("❌ Username is required!")
                sys.exit(1)
        else:
            print(f"\nUsing Last.fm username: {username}")

        # Get number of songs
        while True:
            try:
                num_songs_input = input(f"\nNumber of songs (default: {self.config.max_songs}): ").strip()
                if not num_songs_input:
                    num_songs = self.config.max_songs
                else:
                    num_songs = int(num_songs_input)
                    if num_songs <= 0:
                        print("❌ Number of songs must be positive!")
                        continue
                break
            except ValueError:
                print("❌ Please enter a valid number!")
        
        # Get time period
        print(f"\nSelect time period:")
        print("1. Monthly (specific month/year)")
        print("2. Yearly (entire year)")
        print("3. All-time (overall top songs)")
        
        period_map = {
            '1': 'month',
            '2': 'year',
            '3': 'alltime'
        }
        
        while True:
            choice = input(f"\nChoose time period (1-3, default: 3): ").strip()
            if not choice:
                choice = '3'
            
            if choice in period_map:
                period = period_map[choice]
                break
            else:
                print("❌ Please enter a number between 1 and 3!")
        
        # Get specific year/month if needed
        target_year = None
        target_month = None
        
        if period in ['month', 'year']:
            while True:
                try:
                    year_input = input(f"\nEnter year (e.g., 2024): ").strip()
                    target_year = int(year_input)
                    if target_year < 2000 or target_year > 2030:
                        print("❌ Please enter a year between 2000 and 2030!")
                        continue
                    break
                except ValueError:
                    print("❌ Please enter a valid year!")
        
        if period == 'month':
            print(f"\nSelect month:")
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            for i, month in enumerate(months, 1):
                print(f"{i:2d}. {month}")
            
            while True:
                try:
                    month_input = input(f"\nChoose month (1-12): ").strip()
                    target_month = int(month_input)
                    if target_month < 1 or target_month > 12:
                        print("❌ Please enter a number between 1 and 12!")
                        continue
                    break
                except ValueError:
                    print("❌ Please enter a valid month number!")
        
        # Get enable URL replacement option
        while True:
            enable_replacement = input("\nEnable manual URL replacement if videos are missing? (y/N): ").strip().lower()
            if enable_replacement in ['', 'n', 'no']:
                enable_replacement = False
                break
            elif enable_replacement in ['y', 'yes']:
                enable_replacement = True
                break
            else:
                print("❌ Please enter 'y' for yes or 'n' for no")

        # Get output format
        print("\n📋 Choose output format:")
        print("1. Vertical (1080x1920) - Instagram/TikTok")
        print("2. Horizontal (1920x1080) - YouTube")
        
        while True:
            format_choice = input("\nEnter choice (1-2): ").strip()
            if format_choice == "1":
                output_format = "vertical"
                break
            elif format_choice == "2":
                output_format = "horizontal"
                break
            else:
                print("❌ Please enter 1 or 2")

        print(f"\n✅ Configuration:")
        print(f"   Username: {username}")
        print(f"   Songs: {num_songs}")
        if period == 'month':
            month_name = ["January", "February", "March", "April", "May", "June",
                         "July", "August", "September", "October", "November", "December"][target_month - 1]
            print(f"   Period: {month_name} {target_year}")
        elif period == 'year':
            print(f"   Period: {target_year}")
        else:
            print(f"   Period: All-time")
        print()
        
        return username, num_songs, period, target_year, target_month, output_format, enable_replacement
    
    def create_compilation(self, username: str, num_songs: int, period: str, 
                          target_year: Optional[int] = None, target_month: Optional[int] = None, 
                          enable_replacement: bool = False) -> Optional[str]:
        """
        Create a video compilation for the specified user and parameters.
    
    Args:
            username: Last.fm username
            num_songs: Number of top songs to include
            period: Time period for top songs ('month', 'year', 'alltime')
            target_year: Target year (required for 'month' and 'year')
            target_month: Target month (required for 'month')
        
    Returns:
            Optional[str]: Path to created video file, or None if failed
        """
        logger.info(f"Starting compilation creation for user {username}")
        
        try:
            # Step 1: Initialize APIs
            lastfm_api_key = os.getenv('LASTFM_API_KEY')
            youtube_api_key = os.getenv('YOUTUBE_API_KEY')
            
            if not self.song_service.initialize_lastfm_client(lastfm_api_key):
                print("❌ Failed to initialize Last.fm API")
                return None
                
            if not self.search_service.initialize_youtube_client(youtube_api_key):
                print("❌ Failed to initialize YouTube API")
                return None
            
            # Step 2: Fetch top songs from Last.fm
            print("🎵 Fetching top songs from Last.fm...")
            
            # Set default values for alltime
            if period == 'alltime':
                api_target_year = 2024  # Default year for alltime
                api_target_month = None
            else:
                api_target_year = target_year
                api_target_month = target_month
            
            songs = self.song_service.get_top_songs(
                username=username,
                time_period=period, 
                target_year=api_target_year,
                target_month=api_target_month,
                num_songs=num_songs
            )
            
            if not songs:
                print("❌ No songs found for the specified criteria")
                logger.error(f"No songs found for user {username}")
                return None
            
            print(f"✅ Found {len(songs)} top songs")
            for i, (artist, title) in enumerate(songs, 1):
                print(f"   {i}. {artist} - {title}")
            
            # Step 3: Search for YouTube videos
            print("\n🔍 Searching for YouTube videos...")
            video_urls = []
            
            for i, (artist, title) in enumerate(songs):
                cache_key = f"youtube:{artist}:{title}"
                cached_url = self.cache_service.get_cached_video_url(cache_key)
                
                if cached_url:
                    video_urls.append(cached_url)
                    print(f"   ✅ Cached: {artist} - {title}")
                else:
                    url = self.search_service.search_youtube_video(artist, title)
                    if url:
                        video_urls.append(url)
                        self.cache_service.cache_video_url(cache_key, url)
                        print(f"   ✅ Found: {artist} - {title}")
                    else:
                        print(f"   ❌ Not found: {artist} - {title}")
                        
                        # Manual URL replacement if enabled
                        if enable_replacement:
                            while True:
                                manual_url = input(f"      💭 Enter YouTube URL for '{artist} - {title}' (or press Enter to skip): ").strip()
                                if not manual_url:
                                    # Skip this song - will create black screen placeholder
                                    video_urls.append(None)
                                    print(f"      ⏭️ Skipped: {artist} - {title}")
                                    break
                                elif 'youtube.com/watch?v=' in manual_url or 'youtu.be/' in manual_url:
                                    video_urls.append(manual_url)
                                    self.cache_service.cache_video_url(cache_key, manual_url)
                                    print(f"      ✅ Manual URL added: {artist} - {title}")
                                    break
                                else:
                                    print("      ❌ Invalid YouTube URL format. Please try again.")
                        else:
                            # No replacement enabled - create placeholder
                            video_urls.append(None)
            
            print(f"\n✅ Found {len([url for url in video_urls if url])} YouTube videos")
            if None in video_urls:
                missing_count = video_urls.count(None)
                print(f"⚠️  {missing_count} song(s) will have 'Video not found' placeholder")
            
            # Step 4: Create video compilation
            print("\n🎬 Creating video compilation...")
            
            # Convert song tuples to dictionaries for compilation service
            # Include all songs, even those without videos
            song_dicts = [{'artist': artist, 'title': title} for artist, title in songs]
            
            output_file = self.compilation_service.create_compilation(
                video_urls, 
                song_dicts,
                username,
                period,
                target_year,
                target_month
            )
            
            if output_file and os.path.exists(output_file):
                print(f"\n🎉 Compilation created successfully!")
                print(f"📁 Output file: {output_file}")
                logger.info(f"Compilation created successfully: {output_file}")
                
                # Post-generation video replacement
                output_file = self._offer_video_replacement(
                    songs,
                    video_urls,
                    output_file,
                    enable_replacement,
                    username=username,
                    period=period,
                    target_year=target_year,
                    target_month=target_month,
                )
                
                return output_file
            else:
                print("❌ Failed to create compilation")
                logger.error("Compilation creation failed")
                return None
            
        except Exception as e:
            logger.error(f"Error creating compilation: {e}", exc_info=True)
            print(f"❌ Error creating compilation: {e}")
        return None

    def _offer_video_replacement(
        self,
        songs: List[Tuple[str, str]],
        video_urls: List[Optional[str]],
        output_path: str,
        enable_replacement: bool,
        *,
        username: str,
        period: str,
        target_year: Optional[int],
        target_month: Optional[int],
    ) -> str:
        """Offer post-generation video replacement.

        Returns the final output path (may change if compilation is regenerated).
        """
        if not enable_replacement:
            return output_path
            
        while True:
            print("\n🤔 Do you want to replace any videos in the compilation?")
            choice = input("Enter 'y' for yes, 'n' for no: ").strip().lower()
            
            if choice in ['n', 'no', '']:
                print("✅ No replacements made")
                return output_path
            elif choice in ['y', 'yes']:
                new_output_path = self._interactive_video_replacement(
                    songs,
                    video_urls,
                    output_path,
                    username=username,
                    period=period,
                    target_year=target_year,
                    target_month=target_month,
                )
                return new_output_path
            else:
                print("❌ Please enter 'y' for yes or 'n' for no")
        
        return output_path

    def _interactive_video_replacement(
        self,
        songs: List[Tuple[str, str]],
        video_urls: List[Optional[str]],
        output_path: str,
        *,
        username: str,
        period: str,
        target_year: Optional[int],
        target_month: Optional[int],
    ) -> str:
        """Handle interactive video replacement.

        Returns the final output path (may change if compilation is regenerated).
        """
        print("\n📺 Current videos in compilation:")
        for i, (song, url) in enumerate(zip(songs, video_urls), 1):
            artist, title = song
            status = "✅ Has video" if url else "❌ No video (placeholder)"
            print(f"   {i}. {artist} - {title} - {status}")
        
        current_output_path = output_path
        while True:
            try:
                choice = input(f"\nEnter song number to replace (1-{len(songs)}) or 'done' to finish: ").strip().lower()
                
                if choice in ['done', 'exit', 'quit', '']:
                    return current_output_path
                
                song_num = int(choice)
                if 1 <= song_num <= len(songs):
                    maybe_new_output = self._replace_single_video(
                        songs,
                        video_urls,
                        song_num - 1,
                        current_output_path,
                        username=username,
                        period=period,
                        target_year=target_year,
                        target_month=target_month,
                    )
                    current_output_path = maybe_new_output
                else:
                    print(f"❌ Please enter a number between 1 and {len(songs)}")
                    
            except ValueError:
                print("❌ Please enter a valid number or 'done'")

        return current_output_path

    def _replace_single_video(
        self,
        songs: List[Tuple[str, str]],
        video_urls: List[Optional[str]],
        index: int,
        output_path: str,
        *,
        username: str,
        period: str,
        target_year: Optional[int],
        target_month: Optional[int],
    ) -> str:
        """Replace a single video with manual URL input.

        Returns the (possibly updated) output path.
        """
        artist, title = songs[index]
        current_url = video_urls[index]
        
        print(f"\n🎵 Replacing: {artist} - {title}")
        if current_url:
            print(f"   Current URL: {current_url}")
        else:
            print("   Current: No video (placeholder)")
        
        while True:
            new_url = input("   Enter new YouTube URL (or press Enter to cancel): ").strip()
            
            if not new_url:
                print("   ⏭️ Replacement cancelled")
                break
                
            if 'youtube.com/watch?v=' in new_url or 'youtu.be/' in new_url:
                # Update the URL
                video_urls[index] = new_url
                
                # Cache the new URL
                cache_key = f"youtube:{artist}:{title}"
                self.cache_service.cache_video_url(cache_key, new_url)
                
                print(f"   ✅ URL updated for: {artist} - {title}")
                
                # Ask if they want to regenerate the compilation
                regenerate = input("   🔄 Regenerate compilation now? (y/N): ").strip().lower()
                if regenerate in ['y', 'yes']:
                    new_output = self._regenerate_compilation(
                        songs,
                        video_urls,
                        output_path,
                        username=username,
                        period=period,
                        target_year=target_year,
                        target_month=target_month,
                    )
                    return new_output or output_path
                return output_path
            else:
                print("   ❌ Invalid YouTube URL format. Please try again.")

        return output_path

    def _regenerate_compilation(
        self,
        songs: List[Tuple[str, str]],
        video_urls: List[Optional[str]],
        output_path: str,
        *,
        username: str,
        period: str,
        target_year: Optional[int],
        target_month: Optional[int],
    ) -> Optional[str]:
        """Regenerate the compilation with updated video URLs.

        Returns the new output path if regeneration succeeds, else None.
        """
        print("\n🔄 Regenerating compilation with updated videos...")
        old_output_path = output_path
        
        # Convert song tuples to dictionaries
        song_dicts = [{'artist': artist, 'title': title} for artist, title in songs]
        
        # Create new compilation
        try:
            new_output = self.compilation_service.create_compilation(
                video_urls, 
                song_dicts,
                username,
                period,
                target_year,
                target_month,
            )
            
            if new_output and os.path.exists(new_output):
                print(f"✅ Compilation regenerated: {new_output}")
                # Only remove old output after new one exists.
                if old_output_path and os.path.exists(old_output_path) and old_output_path != new_output:
                    try:
                        os.remove(old_output_path)
                    except OSError:
                        pass
                return new_output
            else:
                print("❌ Failed to regenerate compilation")
                return None
                
        except Exception as e:
            print(f"❌ Error regenerating compilation: {e}")
            return None

    def run(self):
        """Main application entry point."""
        logger.info("Starting video.fm application")
        
        try:
            # Validate environment
            if not self.validate_environment():
                sys.exit(1)
            
            # Get user input
            username, num_songs, period, target_year, target_month, output_format, enable_replacement = self.get_user_input()
            
            # Create compilation
            output_file = self.create_compilation(username, num_songs, period, target_year, target_month, enable_replacement)
            
            if output_file:
                print(f"\n🎉 Success! Your video compilation is ready:")
                print(f"📁 {output_file}")
                
                # Optional: Open the video file
                if sys.platform == "darwin":  # macOS
                    os.system(f"open '{output_file}'")
                elif sys.platform == "linux":
                    os.system(f"xdg-open '{output_file}'")
                elif sys.platform == "win32":
                    os.system(f"start '{output_file}'")
            else:
                print("\n❌ Failed to create video compilation")
                sys.exit(1)
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            logger.info("Application terminated by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            print(f"\n❌ Unexpected error: {e}")
            sys.exit(1)


def main():
    """Application entry point."""
    app = VideoFMApp()
    app.run()


if __name__ == "__main__":
    main()
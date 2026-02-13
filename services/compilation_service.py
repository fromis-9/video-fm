"""
Compilation service module for video.fm

Orchestrates video compilation creation from YouTube videos and song metadata.
Designed to work with the modular video.fm architecture.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import subprocess

from config import VideoConfig
from downloader import VideoDownloader
from processor import VideoProcessor
from services.chorus_detector import ChorusDetector
import ffmpeg


class CompilationService:
    """Service for creating video compilations from YouTube URLs and song metadata."""
    
    def __init__(self, config: VideoConfig):
        """Initialize compilation service.
        
        Args:
            config: Video processing configuration
        """
        self.config = config
        self.downloader = VideoDownloader(config)
        self.processor = VideoProcessor(config)
        self.chorus_detector = ChorusDetector(
            clip_duration=config.clip_duration,
            cache_dir=config.cache_dir,
        )
        
        # Ensure output directory exists
        self.config.video_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Clips directory is the same as video output directory
        self.clips_dir = self.config.video_output_dir
    
    def create_compilation(self, video_urls: List[str], songs: List[Dict[str, str]], 
                          username: str, period: str, target_year: Optional[int] = None, 
                          target_month: Optional[int] = None) -> Optional[str]:
        """Create a video compilation from YouTube URLs and song metadata.
        
        Args:
            video_urls: List of YouTube video URLs
            songs: List of song dictionaries with 'artist' and 'title' keys
            username: Last.fm username
            period: Time period for the compilation
            target_year: Target year (if applicable)
            target_month: Target month (if applicable)
            
        Returns:
            Path to created video file, or None if failed
        """
        if not video_urls or not songs:
            print("❌ No videos or songs provided")
            return None
        
        try:
            print(f"\n🎬 Creating compilation for {username} ({period})")
            print(f"📹 Processing {len(video_urls)} videos...")
            
            # Create song-video pairs for all songs (including None URLs for missing videos)
            paired_songs_videos = list(zip(songs, video_urls))
            
            print(f"📹 Processing {len(paired_songs_videos)} song-video combinations")
            
            # Arrange in countdown order (standard behavior for top songs videos)
            # Last.fm gives us songs in rank order (1st, 2nd, 3rd, 4th, 5th)
            # Countdown videos show: 5th, 4th, 3rd, 2nd, 1st (building to #1)
            countdown_pairs = list(reversed(paired_songs_videos))
            
            clip_paths = []
            final_clip_paths = []
            
            # Step 1: Download and extract clips (or create placeholders)
            for i, (song, video_url) in enumerate(countdown_pairs):
                print(f"\n📥 Processing {i+1}/{len(countdown_pairs)}: {song['artist']} - {song['title']}")
                
                if video_url is None:
                    # Create black screen placeholder for missing video
                    clip_path = self._create_placeholder_clip(song, i)
                else:
                    # Download actual video clip
                    clip_path = self._process_video_clip(video_url, song, i)
                
                if clip_path and clip_path.exists():
                    clip_paths.append(clip_path)
                    print(f"✅ Clip {i+1} processed successfully")
                else:
                    print(f"❌ Failed to process clip {i+1}")
            
            if not clip_paths:
                print("❌ No clips were successfully processed")
                return None
            
            print(f"\n✅ Successfully processed {len(clip_paths)} clips")
            
            # Step 2: Add text overlays to clips
            countdown_songs = [song for song, _ in countdown_pairs]
            for i, (clip_path, song) in enumerate(zip(clip_paths, countdown_songs[:len(clip_paths)])):
                print(f"\n✏️ Adding text overlay {i+1}/{len(clip_paths)}: {song['artist']} - {song['title']}")
                
                final_clip_path = self._add_text_overlay(clip_path, song, i, len(countdown_songs))
                if final_clip_path and final_clip_path.exists():
                    final_clip_paths.append(final_clip_path)
            
            if not final_clip_paths:
                print("❌ No final clips were created")
                return None
            
            print(f"\n✅ Successfully created {len(final_clip_paths)} final clips")
            
            # Step 3: Create final compilation
            output_filename = self._generate_output_filename(username, period)
            output_path = self.config.video_output_dir / output_filename
            
            print(f"\n🎞️ Creating final compilation...")
            
            # Prepare user settings for black screen
            user_settings = {
                'lastfm_user': username,
                'num_songs': len(final_clip_paths),
                'time_period': period,
                'target_year': target_year,
                'target_month': target_month
            }
            
            success = self._merge_clips(final_clip_paths, output_path, countdown_songs[:len(final_clip_paths)], user_settings)
            
            if success and output_path.exists():
                print(f"✅ Compilation created successfully!")
                return str(output_path)
            else:
                print("❌ Failed to create final compilation")
                return None
                
        except Exception as e:
            print(f"❌ Error creating compilation: {e}")
            return None
    
    def _process_video_clip(self, video_url: str, song: Dict[str, str], index: int) -> Optional[Path]:
        """Process a single video into a clip.
        
        Args:
            video_url: YouTube video URL
            song: Song metadata dictionary
            index: Clip index
            
        Returns:
            Path to processed clip, or None if failed
        """
        try:
            # Define output path for this clip
            clip_filename = f"clip_{index:03d}_{song['artist']}_{song['title']}.mp4"
            # Clean filename for filesystem
            clip_filename = self._clean_filename(clip_filename)
            clip_path = self.clips_dir / clip_filename
            
            # Detect the best chorus section for this video
            print(f"   🔍 Detecting chorus for {song['artist']} - {song['title']}...")
            start_time = self.chorus_detector.detect_chorus_timestamp(video_url)
            duration = self.config.clip_duration  # Should be 15 seconds
            
            print(f"   🎵 Extracting {duration}s clip starting at {start_time}s")
            
            success = self.downloader.download_video(
                video_url=video_url,
                output_path=clip_path,
                start_time=start_time,
                duration=duration
            )
            
            if success and clip_path.exists() and clip_path.stat().st_size > 0:
                print(f"   ✅ Downloaded clip: {clip_path.name}")
                return clip_path
            else:
                print(f"   ❌ Download failed for {song['artist']} - {song['title']}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error processing clip: {e}")
            return None
    
    def _add_text_overlay(self, clip_path: Path, song: Dict[str, str], index: int, total_songs: int) -> Optional[Path]:
        """Add text overlay to a video clip.
        
        Args:
            clip_path: Path to the original clip
            song: Song metadata dictionary
            index: Clip index
            total_songs: Total number of songs for countdown calculation
            
        Returns:
            Path to final clip with text overlay, or None if failed
        """
        try:
            # Define output path for final clip with text overlay
            final_filename = f"final_{index:03d}_{song['artist']}_{song['title']}.mp4"
            # Clean filename for filesystem
            final_filename = self._clean_filename(final_filename)
            final_path = self.config.video_output_dir / final_filename
            
            # Calculate countdown number (proper countdown: first song = highest number, last song = 1)
            countdown_number = total_songs - index
            overlay_text = f"{countdown_number}. {song['artist']} - {song['title']}"
            
            print(f"   ✏️ Adding text overlay: '{overlay_text}'")
            
            success = self.processor.add_text_overlay(
                input_clip=clip_path,
                output_clip=final_path,
                text=overlay_text
            )
            
            if success and final_path.exists() and final_path.stat().st_size > 0:
                print(f"   ✅ Text overlay added: {final_path.name}")
                return final_path
            else:
                print(f"   ❌ Text overlay failed for {song['artist']} - {song['title']}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error adding text overlay: {e}")
            return None
    
    def _merge_clips(self, clip_paths: List[Path], output_path: Path, songs: List[Dict[str, str]], user_settings: Dict[str, Any]) -> bool:
        """Merge video clips into final compilation.
        
        Args:
            clip_paths: List of paths to video clips
            output_path: Path for final output video
            songs: List of song metadata
            user_settings: User settings for black screen text generation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"   🔗 Merging {len(clip_paths)} clips...")
            
            # Create black screen intro
            print(f"   🖤 Creating black screen intro...")
            black_screen_path = self._create_black_screen(user_settings)
            
            # Use the processor to merge videos with black screen intro
            success = self.processor.merge_videos(clip_paths, output_path, black_screen_path)
            
            if success and output_path.exists():
                file_size = output_path.stat().st_size / (1024 * 1024)  # MB
                print(f"   ✅ Final video created: {output_path.name} ({file_size:.1f} MB)")
                return True
            else:
                print(f"   ❌ Failed to create final video")
                return False
                
        except Exception as e:
            print(f"   ❌ Error merging clips: {e}")
            return False
    
    def _create_black_screen(self, user_settings: Dict[str, Any]) -> Optional[Path]:
        """Create a black screen intro with title text and silent audio.
        
        Uses standardized 1920x1080@30fps format to match all clips.
        
        Args:
            user_settings: Dictionary containing user settings for text generation
            
        Returns:
            Path to the black screen video file, or None if failed
        """
        black_screen_path = self.config.video_output_dir / "black_screen_intro.mp4"
        
        if black_screen_path.exists():
            print(f"   🖤 Using existing black screen: {black_screen_path}")
            return black_screen_path
        
        print(f"   🖤 Creating standardized black screen intro...")
        
        # Generate title text
        period_text = self._format_period_text(user_settings)
        black_screen_text = f"{user_settings['lastfm_user']}'s Top {user_settings['num_songs']} songs {period_text}"
        
        # Get system font path
        font_path = self._get_system_font_path()
        
        try:
            # Text overlay parameters for 1920x1080 format
            text_filter = {
                "text": black_screen_text,
                "fontsize": 64,  # Large font for intro screen
                "fontcolor": "white",
                "x": "(w-text_w)/2",  # Center horizontally
                "y": "(h-text_h)/2", # Center vertically
                "shadowcolor": "black",
                "shadowx": 3,
                "shadowy": 3
            }
            
            if font_path:
                text_filter["fontfile"] = font_path
                
            # Create a standardized black video (1920x1080@30fps, 3 seconds) with text and audio
            video_input = ffmpeg.input('color=c=black:s=1920x1080:r=30', f='lavfi', t=3)
            # Keep audio parameters consistent with the rest of the pipeline (48kHz stereo)
            audio_input = ffmpeg.input('anullsrc=r=48000:cl=stereo', f='lavfi', t=3)
            
            # Apply text overlay to video
            video_with_text = video_input.filter("drawtext", **text_filter)
            
            # Combine video and audio with standardized encoding
            ffmpeg.output(
                video_with_text,
                audio_input,
                str(black_screen_path),
                vcodec=self.config.selected_codec,
                acodec="aac",
                **{"b:a": "192k"},  # Proper audio bitrate syntax
                r=30,  # Force 30fps to match clips
                vsync="cfr",  # Constant frame rate
                t=3,  # Exactly 3 seconds
                preset="fast"
            ).run(overwrite_output=True)
            
            print(f"   ✅ Black screen created: {black_screen_path}")
            return black_screen_path
            
        except ffmpeg.Error as e:
            print(f"   ❌ Error creating black screen: {e}")
            return None
    
    def _format_period_text(self, user_settings: Dict[str, Any]) -> str:
        """Format the period text for display."""
        time_period = user_settings.get('time_period', '')
        target_year = user_settings.get('target_year')
        target_month = user_settings.get('target_month')
        
        if time_period == 'month' and target_year and target_month:
            import calendar
            month_name = calendar.month_name[target_month]
            return f"of {month_name} {target_year}"
        elif time_period == 'year' and target_year:
            return f"of {target_year}"
        elif time_period == 'alltime':
            return "of all time"
        else:
            return f"of {time_period}"
    
    def _get_system_font_path(self) -> Optional[str]:
        """Get system font path for different operating systems."""
        import os
        
        # Try different font paths based on OS
        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       # Linux
            "C:\\Windows\\Fonts\\arialuni.ttf",                     # Windows Unicode
            "C:\\Windows\\Fonts\\arial.ttf"                         # Windows Arial
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                return font_path
        
        return None  # Let ffmpeg use default font
    
    def _generate_output_filename(self, username: str, period: str) -> str:
        """Generate filename for output video.
        
        Args:
            username: Last.fm username
            period: Time period
            
        Returns:
            Generated filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_username = self._clean_filename(username)
        return f"videofm_{clean_username}_{period}_{timestamp}.mp4"
    
    def _clean_filename(self, filename: str) -> str:
        """Clean filename for filesystem compatibility.
        
        Args:
            filename: Original filename
            
        Returns:
            Cleaned filename
        """
        import re
        # Remove or replace problematic characters
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
        cleaned = re.sub(r'[^\w\-_.]', '_', cleaned)
        cleaned = re.sub(r'_+', '_', cleaned)  # Replace multiple underscores with one
        return cleaned.strip('_')
    
    def _create_placeholder_clip(self, song: dict, index: int) -> Optional[Path]:
        """Create a black screen placeholder clip for songs without videos.
        
        Args:
            song: Song dictionary with artist and title
            index: Index for naming the clip file
            
        Returns:
            Path to created placeholder clip, or None if creation failed
        """
        try:
            # Create safe filename
            safe_artist = self._clean_filename(song['artist'])
            safe_title = self._clean_filename(song['title'])
            clip_filename = f"clip_{index:03d}_{safe_artist}_{safe_title}_placeholder.mp4"
            clip_path = self.clips_dir / clip_filename
            
            print(f"   🖤 Creating placeholder for missing video")
            
            # Create 15-second black screen with only "Video not found" text
            # The text overlay step will add the song info with countdown number
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', 'color=c=black:s=1920x1080:r=30',  # Black video
                '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',       # Silent audio (match pipeline)
                '-t', '15',  # 15 second duration
                '-filter_complex', f"""
                [0:v]drawtext=text='Video not found':
                fontfile=/System/Library/Fonts/Arial.ttf:
                fontsize=60:
                fontcolor=white:
                x=(w-text_w)/2:
                y=(h-text_h)/2[v]
                """,
                '-map', '[v]', '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                '-pix_fmt', 'yuv420p',
                str(clip_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and clip_path.exists():
                print(f"   ✅ Created placeholder: {clip_filename}")
                return clip_path
            else:
                print(f"   ❌ Failed to create placeholder: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error creating placeholder clip: {e}")
            return None 
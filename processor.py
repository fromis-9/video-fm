"""
Video processor module for video.fm

This module handles all FFmpeg video processing operations including:
- Video duration detection
- Text overlay addition
- Black screen generation
- Video merging and concatenation
"""

import os
import calendar
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import ffmpeg

from config import VideoConfig


class VideoProcessor:
    """Handles all FFmpeg video processing operations."""
    
    def __init__(self, config: VideoConfig):
        """Initialize processor with configuration.
        
        Args:
            config: VideoConfig instance with all settings
        """
        self.config = config
    
    def get_video_duration(self, video_path: str | Path) -> Optional[float]:
        """Get the duration of a video in seconds.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Duration in seconds, or None if error
        """
        try:
            # Convert to Path object and ensure it's a string for ffmpeg
            video_path = Path(video_path)
            video_path_str = str(video_path)
                
            print(f"Probing video file: {video_path}")
            print(f"File exists: {video_path.exists()}")
            print(f"File size: {video_path.stat().st_size if video_path.exists() else 'N/A'}")
            probe = ffmpeg.probe(video_path_str)
            duration = float(probe["format"]["duration"])
            return duration
        except ffmpeg.Error as e:
            print(f"⚠️ FFprobe error: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                stderr_text = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else str(e.stderr)
                print(f"FFprobe stderr: {stderr_text}")
            return None
        except Exception as e:
            print(f"⚠️ Unexpected error in get_video_duration: {type(e).__name__}: {str(e)}")
            print(f"Path type: {type(video_path)}")
            return None
    
    def prepare_black_screen(self, user_settings: Dict[str, Any]) -> Optional[Path]:
        """Create a black screen with text and audio for the intro.
        
        Args:
            user_settings: Dictionary with user configuration including:
                - lastfm_user: Username
                - num_songs: Number of songs  
                - time_period: 'month', 'year', or 'alltime'
                - target_year: Year (if applicable)
                - target_month: Month (if applicable)
                
        Returns:
            Path to the created black screen video, or None if error
        """
        # Define file paths using pathlib
        black_screen_with_text = self.config.video_output_dir / "black_screen_with_text.mp4"
        black_screen_final = self.config.video_output_dir / "black_screen_final.mp4"
        
        # Ensure output directory exists
        self.config.video_output_dir.mkdir(exist_ok=True)
        
        # Check if final black screen already exists
        if black_screen_final.exists():
            return black_screen_final
        
        # Generate black screen text
        black_screen_text = self._generate_black_screen_text(user_settings)
        
        if not black_screen_with_text.exists():
            print("✏️ Generating black screen with text...")
            
            # Determine font path for different operating systems
            font_path = self._get_system_font_path()
            
            try:
                # Generate a 3-second black video with text
                text_filter = {
                    "text": black_screen_text,
                    "fontsize": 50,
                    "fontcolor": "white",
                    "x": "(w-text_w)/2",
                    "y": "(h-text_h)/2"
                }
                
                if font_path:
                    text_filter["fontfile"] = font_path
                    
                # Create a black video source and add text (force square pixels / SAR=1)
                ffmpeg.input('color=c=black:s=1920x1080:r=30', f='lavfi', t=3).filter(
                    "drawtext", **text_filter
                ).filter(
                    "setsar", "1"
                ).output(
                    str(black_screen_with_text), 
                    vcodec=self.config.selected_codec,
                    video_bitrate=self.config.video_bitrate,
                    vsync="cfr",
                    r=30
                ).run()
            except ffmpeg.Error as e:
                print(f"❌ Error creating black screen: {e}")
                return None
        
        # Add silent audio track to ensure compatibility
        if not black_screen_final.exists():
            print("🔇 Adding silent audio track to black screen...")
            try:
                # Create two separate inputs
                video = ffmpeg.input(str(black_screen_with_text))
                # Match the rest of the pipeline (48kHz stereo) to keep concat happy
                audio = ffmpeg.input('anullsrc=r=48000:cl=stereo', f='lavfi', t=3)
                
                # Combine video and audio streams
                ffmpeg.output(
                    video,
                    audio,
                    str(black_screen_final),
                    vcodec=self.config.selected_codec,
                    acodec="aac",
                    audio_bitrate=self.config.audio_bitrate,
                    shortest=None
                ).run()
            except ffmpeg.Error as e:
                print(f"❌ Error adding silent audio: {e}")
                print(f"Detailed error: {str(e)}")
                # Use version with text as fallback
                if black_screen_with_text.exists():
                    import shutil
                    shutil.copy(black_screen_with_text, black_screen_final)
                    print("⚠️ Using black screen without audio as fallback")
        
        return black_screen_final
    
    def add_text_overlay(self, input_clip: str | Path, output_clip: str | Path, text: str) -> bool:
        """Add text overlay to video clip with consistent sizing and positioning.
        
        All clips are expected to be standardized to 1920x1080@30fps format.
        
        Args:
            input_clip: Path to input video (standardized to 1920x1080)
            output_clip: Path to save output video
            text: Text to overlay
            
        Returns:
            True if successful, False otherwise
        """
        # Convert Path objects to strings for ffmpeg compatibility
        input_clip_str = str(input_clip)
        output_clip_str = str(output_clip)
        
        # Use fixed dimensions since all clips are now standardized
        width = 1920
        height = 1080
        
        # Base font size as percentage of video height
        base_fontsize = int(height * 0.05)  # 5% of video height (54px for 1080p)
        
        # Adjust font size based on text length to ensure it fits
        char_width_factor = 0.6  # Approximate width of a character relative to font size
        estimated_text_width = len(text) * base_fontsize * char_width_factor
        
        # If estimated width is too large, scale down the font size
        if estimated_text_width > width * 0.85:  # Allow text to use 85% of width
            fontsize = int(base_fontsize * (width * 0.85) / estimated_text_width)
        else:
            fontsize = base_fontsize
        
        # Scale shadow size based on resolution
        shadowx = max(2, int(width * 0.002))  # 4px for 1080p
        shadowy = max(2, int(height * 0.002))  # 2px for 1080p
        
        # Calculate position from bottom as percentage of height
        bottom_margin = int(height * 0.08)  # 8% from bottom (86px for 1080p)
        y_position = f"h-{bottom_margin}"
        
        # Determine font path for different operating systems
        font_path = self._get_system_font_path()
        
        # Text with enhanced shadow for better readability
        text_params = {
            'text': text,
            'fontsize': fontsize,
            'fontcolor': 'white',
            'x': '(w-text_w)/2',  # Center horizontally
            'y': y_position,      # Consistent distance from bottom
            'shadowcolor': 'black',
            'shadowx': shadowx,
            'shadowy': shadowy
        }
        
        if font_path:
            text_params['fontfile'] = font_path
        
        try:
            # Apply text filter with audio copying
            input_video = ffmpeg.input(input_clip_str)
            
            # Apply text overlay to video stream and normalize SAR so concat filter won't fail
            video_with_text = input_video.video.filter('drawtext', **text_params).filter('setsar', '1')
            
            # Copy audio stream unchanged
            audio_stream = input_video.audio
            
            # Output with both video and audio (codec-specific settings)
            out_kwargs = {
                "vcodec": self.config.selected_codec,
                "r": 30,          # Force 30fps
                "vsync": "cfr",   # Constant frame rate
                "map_metadata": "-1",
                "preset": self.config.ffmpeg_preset,
            }
            # Always standardize audio to AAC 48kHz stereo so large concat runs
            # can use the concat demuxer reliably (uniform stream parameters).
            out_kwargs.update({
                "acodec": "aac",
                **{"b:a": "192k"},
                "ar": 48000,
                "ac": 2,
            })
            if "videotoolbox" in self.config.selected_codec:
                out_kwargs.update({
                    **{"b:v": self.config.video_bitrate},
                    "pix_fmt": "yuv420p",
                })
            else:
                out_kwargs.update({
                    "crf": self.config.video_crf,
                })

            ffmpeg.output(
                video_with_text,
                audio_stream,
                output_clip_str, 
                **out_kwargs
            ).run(overwrite_output=True)
            return True
        except ffmpeg.Error as e:
            print(f"❌ Error adding text overlay: {e}")
            return False
    
    def merge_videos(self, video_list: List[Path], output_file: Path, 
                    black_screen_path: Optional[Path] = None) -> bool:
        """Merge video clips into final compilation.
        
        All clips should be standardized to 1920x1080@30fps format.
        
        Args:
            video_list: List of paths to video clips (standardized format)
            output_file: Path for final output video
            black_screen_path: Optional path to black screen intro
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"   🔗 Merging {len(video_list)} clips...")
            
            # Verify all videos exist
            all_videos = []
            if black_screen_path and black_screen_path.exists():
                all_videos.append(black_screen_path)
            all_videos.extend(video_list)
            
            missing_files = [video for video in all_videos if not Path(video).exists()]
            if missing_files:
                print(f"   ❌ Missing files: {missing_files}")
                return False

            # For large N (e.g. 200 clips), the concat *filter* approach creates one input per file
            # and can exceed OS thread limits (pthread_create fails). Use concat *demuxer* instead:
            # it processes files sequentially and scales to hundreds/thousands of segments.
            concat_list_path = output_file.with_suffix(".concat.txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for p in all_videos:
                    # Our filenames are sanitized elsewhere; keep quoting simple for spaces.
                    f.write(f"file '{Path(p).resolve()}'\n")

            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_path),
                "-map_metadata", "-1",
                "-r", "30",
                "-vsync", "cfr",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-ac", "2",
            ]

            if "videotoolbox" in self.config.selected_codec:
                cmd += ["-c:v", self.config.selected_codec, "-b:v", str(self.config.video_bitrate)]
            else:
                cmd += [
                    "-c:v", self.config.selected_codec,
                    "-crf", str(self.config.video_crf),
                    "-preset", str(self.config.ffmpeg_preset),
                ]

            cmd += [str(output_file)]

            result = subprocess.run(cmd, capture_output=True, text=True)
            try:
                concat_list_path.unlink(missing_ok=True)
            except Exception:
                pass

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                print(f"   ❌ Error during merge: {stderr[-2000:] if stderr else 'Unknown ffmpeg error'}")
                return False
            
            print(f"   ✅ Merge completed: {output_file}")
            return True
            
        except ffmpeg.Error as e:
            print(f"   ❌ Error during merge: {e}")
            return False
        except Exception as e:
            print(f"   ❌ Unexpected error during merge: {type(e).__name__}: {str(e)}")
            return False
    
    def _generate_black_screen_text(self, user_settings: Dict[str, Any]) -> str:
        """Generate text for the black screen intro."""
        time_period = user_settings.get('time_period', 'alltime')
        lastfm_user = user_settings.get('lastfm_user', 'User')
        num_songs = user_settings.get('num_songs', 50)
        target_year = user_settings.get('target_year')
        target_month = user_settings.get('target_month')
        
        if time_period == "month" and target_month and target_year:
            month_name = calendar.month_name[int(target_month)]
            return f"{lastfm_user}'s Top {num_songs} songs of {month_name} {target_year}"
        elif time_period == "year" and target_year:
            return f"{lastfm_user}'s Top {num_songs} songs of {target_year}"
        else:  # alltime
            return f"{lastfm_user}'s Top {num_songs} songs of all time"
    
    def _get_system_font_path(self) -> Optional[str]:
        """Get appropriate font path for the current operating system."""
        font_path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"  # Mac path
        if not os.path.exists(font_path):
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Linux fallback
            if not os.path.exists(font_path):
                font_path = "C:\\Windows\\Fonts\\arialuni.ttf"  # Windows Unicode font
                if not os.path.exists(font_path):
                    font_path = "C:\\Windows\\Fonts\\arial.ttf"  # Windows regular Arial
                    if not os.path.exists(font_path):
                        font_path = None  # Let ffmpeg use default font
        return font_path 
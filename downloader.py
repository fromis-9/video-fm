"""
Video downloader module for video.fm

This module handles all video downloading functionality using yt-dlp,
including progress tracking, error handling, and clip extraction.
"""

import os
import sys
import subprocess
import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import yt_dlp
from tqdm import tqdm

from config import VideoConfig


class VideoDownloader:
    """Handles video downloading and clip extraction using yt-dlp and FFmpeg."""
    
    def __init__(self, config: VideoConfig):
        """Initialize downloader with configuration.
        
        Args:
            config: VideoConfig instance with all settings
        """
        self.config = config
    
    def download_video(self, video_url: str, output_path: str | Path, 
                      start_time: Optional[str | int] = None, 
                      duration: Optional[int] = None) -> bool:
        """Download a video and optionally extract a precise clip.
        
        Args:
            video_url: YouTube URL to download
            output_path: Path to save the output video
            start_time: Start time for clip extraction (string HH:MM:SS or seconds)
            duration: Duration of clip in seconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        
        # Convert to Path object if it's a string
        output_path = Path(output_path)
        
        # Check if output file already exists and is valid
        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"✅ Output file already exists and is valid: {output_path}")
            return True

        # Windows-specific handling
        if sys.platform == 'win32':
            return self._download_windows(video_url, output_path, start_time, duration)
        else:
            return self._download_unix(video_url, output_path, start_time, duration)
    
    def _download_windows(self, video_url: str, output_path: Path, 
                         start_time: Optional[str | int], 
                         duration: Optional[int]) -> bool:
        """Windows-specific download implementation."""
        print("Windows platform detected - using hidden batch approach for download")
        try:
            # Create Windows-appropriate paths
            base_dir = Path.home() / "AppData/Local/video.fm/clips"
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Create temporary download path
            tmp_download_path = output_path.with_suffix("_download.mp4")
            
            # Clean up any existing temporary file
            if tmp_download_path.exists():
                try:
                    tmp_download_path.unlink()
                except Exception as e:
                    print(f"⚠️ Could not remove existing temp file {tmp_download_path}: {e}")
            
            print(f"Downloading from {video_url} to {tmp_download_path}")
            
            # Create a temporary batch file to run yt-dlp
            batch_file = base_dir / "download.bat"
            
            # Write batch file contents for downloading - with hidden window execution
            with open(batch_file, "w") as f:
                f.write(f'@echo off\n')
                f.write(f'echo Downloading with yt-dlp...\n')
                f.write(f'yt-dlp "{video_url}" -o "{tmp_download_path}" --format mp4\n')
            
            # Execute batch file with hidden window
            print(f"Executing hidden batch file for download")
            
            # Use startupinfo to hide the console window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            
            # Run the process with hidden window
            subprocess.run(str(batch_file), startupinfo=startupinfo)
            
            # Clean up batch file
            try:
                batch_file.unlink()
            except:
                pass
            
            # Check if download succeeded, then proceed with normal processing
            if tmp_download_path.exists() and tmp_download_path.stat().st_size > 0:
                print(f"Download successful: {tmp_download_path}")
                
                # Extract clip if needed
                if start_time is not None and duration is not None:
                    return self._extract_clip_windows(tmp_download_path, output_path, start_time, duration)
                else:
                    # If no clip extraction needed, just rename
                    tmp_download_path.rename(output_path)
                    return True
            else:
                print(f"Download failed: {tmp_download_path} not found or empty")
                return False
        
        except Exception as e:
            print(f"❌ Error during Windows approach: {type(e).__name__}: {str(e)}")
            return False
    
    def _extract_clip_windows(self, tmp_download_path: Path, output_path: Path,
                             start_time: str | int, duration: int) -> bool:
        """Extract clip on Windows platform."""
        # Convert start_time to seconds if it's in HH:MM:SS format
        if isinstance(start_time, str) and ":" in start_time:
            h, m, s = map(int, start_time.split(":"))
            start_seconds = h * 3600 + m * 60 + s
        else:
            start_seconds = int(start_time)
        
        # Format time for ffmpeg
        start_time_str = str(datetime.timedelta(seconds=start_seconds))
        
        print(f"✂️ Extracting {duration}s clip starting at {start_time_str}")
        
        # Use os.system for clip extraction to avoid encoding issues
        cmd = (f'ffmpeg -i "{tmp_download_path}" -ss {start_time_str} -t {duration} '
               f'-c:v {self.config.selected_codec} -crf {self.config.video_crf} '
               f'-c:a aac -b:a {self.config.audio_bitrate} -r 30 "{output_path}" -y')
        print(f"Running command: {cmd}")
        os.system(cmd)
        
        # Clean up downloaded file
        try:
            tmp_download_path.unlink()
        except:
            pass
        
        return output_path.exists()
    
    def _download_unix(self, video_url: str, output_path: Path, 
                      start_time: Optional[str | int], 
                      duration: Optional[int]) -> bool:
        """Unix/Linux/macOS download implementation."""
        
        # Ensure all path and URL arguments are strings, not bytes
        if isinstance(video_url, bytes):
            video_url = video_url.decode('utf-8')
        if isinstance(start_time, bytes) and start_time is not None:
            start_time = start_time.decode('utf-8')
        
        # Create progress bar for download
        progress_bar = tqdm(total=100, desc="Downloading", unit="%", position=0, leave=True)

        def progress_hook(d):
            """Update progress bar during download."""
            if d['status'] == 'downloading' and 'downloaded_bytes' in d and 'total_bytes' in d:
                percentage = (d['downloaded_bytes'] / d['total_bytes']) * 100
                progress_bar.n = percentage
                progress_bar.refresh()
            elif d['status'] == 'finished':
                progress_bar.n = 100
                progress_bar.close()
        
        # Use yt-dlp with external downloader for direct clip extraction + format standardization
        ydl_opts = {
            'format': self._get_format_selector(),
            'outtmpl': str(output_path),
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'prefer_insecure': True,
            'socket_timeout': 15
        }
        
        # Add clip extraction and format standardization if parameters provided
        if start_time is not None and duration is not None:
            ydl_opts['external_downloader'] = 'ffmpeg'
            ydl_opts['external_downloader_args'] = [
                '-ss', str(start_time),
                '-t', str(duration),
                # CRITICAL: Standardize format to prevent sync issues
                '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
                '-r', '30',  # Force 30fps
                '-c:v', self.config.selected_codec,
                '-c:a', 'aac',
                '-b:a', '192k',
                '-vsync', 'cfr'  # Constant frame rate
            ]
        
        try:
            # Download the video (with clip extraction if parameters provided)
            print(f"Starting download for URL: {video_url}")
            print(f"Output path: {output_path}")
            if start_time is not None and duration is not None:
                print(f"Extracting {duration}s clip starting at {start_time}s with format standardization")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                
            # Check if download/extraction succeeded
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"✅ Download successful: {output_path} ({output_path.stat().st_size} bytes)")
                return True
            else:
                print(f"❌ Download failed: File not found or empty at {output_path}")
                return False
            
        except Exception as e:
            print(f"❌ Error during video processing: {type(e).__name__}: {str(e)}")
            return False
    
    def _get_format_selector(self) -> str:
        """Get the appropriate format selector based on MAX_VIDEO_QUALITY setting."""
        quality_map = {
            "480": "best[height<=480]",
            "720": "best[height<=720]", 
            "1080": "best[height<=1080]",
            "1440": "best[height<=1440]",
            "2160": "best[height<=2160]"
        }
        
        base_format = quality_map.get(self.config.max_video_quality, "best[height<=1080]")
        # Add robust fallbacks for YouTube signature issues
        return f"{base_format}/best[height<=720]/best/worst"
    
    def get_video_info(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Get video information without downloading."""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info
        except Exception as e:
            print(f"⚠️ Error getting video info: {e}")
            return None 
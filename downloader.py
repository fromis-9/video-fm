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
from typing import Optional, Dict, Any
import yt_dlp
from yt_dlp.utils import DownloadError
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
                f.write('@echo off\n')
                f.write('echo Downloading with yt-dlp...\n')
                # Prefer HTTPS progressive formats and an alternate YouTube client to reduce 403s.
                # Note: -o expects an output template; we pass a concrete filename intentionally.
                ua = os.getenv(
                    "YTDLP_USER_AGENT",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                )
                f.write(
                    f'yt-dlp "{video_url}" '
                    f'--no-playlist --retries 3 --fragment-retries 3 '
                    f'--user-agent "{ua}" '
                    f'--extractor-args "youtube:player_client=android" '
                    f'-f "bestvideo[protocol^=https]+bestaudio[protocol^=https]/best[protocol^=https]" '
                    f'--merge-output-format mp4 '
                    f'-o "{tmp_download_path}"\n'
                )
            
            # Execute batch file with hidden window
            print("Executing hidden batch file for download")
            
            # Use startupinfo to hide the console window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            
            # Run the process with hidden window
            subprocess.run(str(batch_file), startupinfo=startupinfo)
            
            # Clean up batch file
            try:
                batch_file.unlink()
            except Exception:
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
        except Exception:
            pass
        
        return output_path.exists()
    
    def _download_unix(self, video_url: str, output_path: Path, 
                      start_time: Optional[str | int], 
                      duration: Optional[int]) -> bool:
        """Unix/Linux/macOS download implementation.
        
        Uses a two-step approach for clip extraction:
        1. Download full video with yt-dlp (handles bestvideo+bestaudio merging)
        2. Extract clip with ffmpeg (handles time-based extraction + format standardization)
        """
        
        # Ensure all path and URL arguments are strings, not bytes
        if isinstance(video_url, bytes):
            video_url = video_url.decode('utf-8')
        if isinstance(start_time, bytes) and start_time is not None:
            start_time = start_time.decode('utf-8')
        
        # Create progress bar for download
        progress_bar = tqdm(total=100, desc="Downloading", unit="%", position=0, leave=True)

        def progress_hook(d):
            """Update progress bar during download."""
            try:
                if d.get('status') == 'downloading':
                    downloaded = d.get('downloaded_bytes') or 0
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    if total:
                        percentage = (downloaded / total) * 100
                        progress_bar.n = percentage
                        progress_bar.refresh()
                elif d.get('status') == 'finished':
                    progress_bar.n = 100
                    progress_bar.close()
            except Exception:
                # Never let progress UI break downloads
                pass
        
        # Determine if we need clip extraction
        need_clip_extraction = start_time is not None and duration is not None
        
        # Use temp file for full download if we need to extract a clip
        if need_clip_extraction:
            temp_download_path = output_path.with_suffix('.temp.mp4')
        else:
            temp_download_path = output_path
        
        def build_ydl_opts(*, extractor_args: Optional[dict] = None, fmt: Optional[str] = None) -> dict:
            """Build yt-dlp options with sane defaults and optional YouTube tweaks."""
            ua = os.getenv(
                "YTDLP_USER_AGENT",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            )
            cookiefile = os.getenv("YTDLP_COOKIEFILE") or os.getenv("YTDLP_COOKIES")
            proxy = os.getenv("YTDLP_PROXY")

            opts: dict = {
                'format': fmt or self._get_format_selector(),
                'outtmpl': str(temp_download_path),
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
                # For single-URL downloads, don't hide failures (we rely on exceptions to retry)
                'ignoreerrors': False,
                # Put yt-dlp cache under our configurable cache dir (so you can move it to an external SSD)
                'cachedir': str((self.config.cache_dir / "yt-dlp").resolve()),
                'noplaylist': True,
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 3,
                'merge_output_format': 'mp4',  # Ensure output is mp4 with merged streams
                'http_headers': {
                    'User-Agent': ua,
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.youtube.com/',
                },
            }

            if extractor_args:
                opts['extractor_args'] = extractor_args
            if cookiefile:
                opts['cookiefile'] = cookiefile
            if proxy:
                opts['proxy'] = proxy

            return opts
        
        try:
            print(f"Starting download for URL: {video_url}")
            print(f"Output path: {output_path}")
            if need_clip_extraction:
                print(f"Extracting {duration}s clip starting at {start_time}s with format standardization")

            # YouTube can intermittently block certain clients/requests with HTTP 403.
            # Retry with alternative "player clients" and, as a last resort, avoid HLS/DASH manifests.
            attempts: list[tuple[str, dict, Optional[str]]] = [
                ("default", {}, None),
                ("android player client", {"youtube": {"player_client": ["android"]}}, None),
                (
                    "android client + skip dash/hls",
                    {"youtube": {"player_client": ["android"], "skip": ["dash", "hls"]}},
                    # Prefer plain HTTPS formats when skipping manifests
                    "bestvideo[protocol^=https]+bestaudio[protocol^=https]/best[protocol^=https]",
                ),
            ]

            last_err: Optional[BaseException] = None
            for idx, (label, extractor_args, fmt) in enumerate(attempts, start=1):
                try:
                    if idx > 1:
                        print(f"🔁 Retrying download with {label}…")
                    with yt_dlp.YoutubeDL(build_ydl_opts(extractor_args=extractor_args or None, fmt=fmt)) as ydl:
                        ydl.download([video_url])
                    last_err = None
                    break
                except DownloadError as e:
                    last_err = e
                    # Try next attempt
                    continue
                except Exception as e:
                    last_err = e
                    continue

            if last_err is not None:
                raise last_err

            # Check if download succeeded
            if not temp_download_path.exists() or temp_download_path.stat().st_size == 0:
                print(f"❌ Download failed: File not found or empty at {temp_download_path}")
                return False

            # Validate that the downloaded file has a video stream
            if not self._has_video_stream(temp_download_path):
                print("⚠️ Downloaded file has no video stream (audio-only)")
                # Clean up and return False
                try:
                    temp_download_path.unlink()
                except Exception:
                    pass
                return False

            # Step 2: If clip extraction needed, use ffmpeg to extract and standardize
            if need_clip_extraction:
                success = self._extract_clip_ffmpeg(temp_download_path, output_path, start_time, duration)

                # Clean up temp file
                try:
                    temp_download_path.unlink()
                except Exception:
                    pass

                if success:
                    print(f"✅ Download successful: {output_path} ({output_path.stat().st_size} bytes)")
                return success

            print(f"✅ Download successful: {output_path} ({output_path.stat().st_size} bytes)")
            return True
            
        except Exception as e:
            print(f"❌ Error during video processing: {type(e).__name__}: {str(e)}")
            # Clean up temp file on error
            if need_clip_extraction and temp_download_path.exists():
                try:
                    temp_download_path.unlink()
                except Exception:
                    pass
            return False
        finally:
            try:
                if progress_bar and hasattr(progress_bar, "close"):
                    progress_bar.close()
            except Exception:
                pass
    
    def _has_video_stream(self, file_path: Path) -> bool:
        """Check if a media file has a video stream using ffprobe.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            bool: True if file has a video stream, False otherwise
        """
        try:
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'quiet',
                    '-select_streams', 'v:0',  # Select first video stream
                    '-show_entries', 'stream=codec_type',
                    '-of', 'csv=p=0',
                    str(file_path)
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            # If there's a video stream, ffprobe outputs "video"
            return 'video' in result.stdout.strip()
        except Exception:
            # If ffprobe fails, assume no video (safer)
            return False
    
    def _extract_clip_ffmpeg(self, input_path: Path, output_path: Path,
                             start_time: str | int, duration: int) -> bool:
        """Extract a clip from a video using ffmpeg with format standardization.
        
        Args:
            input_path: Path to the input video file
            output_path: Path to save the extracted clip
            start_time: Start time in seconds or HH:MM:SS format
            duration: Duration of clip in seconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Convert start_time to seconds if it's in HH:MM:SS format
        if isinstance(start_time, str) and ":" in start_time:
            parts = start_time.split(":")
            if len(parts) == 3:
                h, m, s = map(int, parts)
                start_seconds = h * 3600 + m * 60 + s
            else:
                start_seconds = int(start_time)
        else:
            start_seconds = int(start_time)
        
        # Build ffmpeg command for clip extraction with format standardization.
        # Important: Avoid audio "time-stretch" filters (which can pitch-shift).
        # Instead, enforce CFR video via fps filter and reset timestamps on both streams.
        # IMPORTANT: Do all trimming in the filtergraph so audio+video are *exactly* `duration`
        # and start at PTS 0. This prevents segment-to-segment drift and "video freezes while audio continues".
        vf = (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
            "setsar=1,"
            "fps=30,"
            f"trim=duration={duration},"
            "setpts=PTS-STARTPTS"
        )
        af = f"aresample=48000,atrim=duration={duration},asetpts=PTS-STARTPTS"

        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-ss', str(start_seconds),  # Seek before input (faster)
            '-i', str(input_path),
            # Hard limit processing duration as well (prevents long-running encodes on some sources)
            '-t', str(duration),
            '-filter_complex', f"[0:v]{vf}[v];[0:a]{af}[a]",
            '-map', '[v]',
            '-map', '[a]',
            '-c:v', self.config.selected_codec,
            '-crf', str(self.config.video_crf),
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '48000',
            '-ac', '2',
            '-shortest',
            str(output_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # Some sources decode/encode slower; avoid false timeouts
            )
            
            if result.returncode != 0:
                print(f"❌ FFmpeg error: {result.stderr[:500] if result.stderr else 'Unknown error'}")
                return False
            
            return output_path.exists() and output_path.stat().st_size > 0
            
        except subprocess.TimeoutExpired:
            print("❌ FFmpeg timed out")
            return False
        except Exception as e:
            print(f"❌ Error during clip extraction: {type(e).__name__}: {str(e)}")
            return False
    
    def _get_format_selector(self) -> str:
        """Get the appropriate format selector based on MAX_VIDEO_QUALITY setting.
        
        Uses a fallback chain to maximize compatibility while ensuring video is included.
        The _has_video_stream check will catch any audio-only downloads.
        """
        max_height = self.config.max_video_quality or "1080"
        
        # Build a comprehensive fallback chain:
        # 1. Best video+audio at max quality
        # 2. Best video+audio at lower qualities  
        # 3. Any combined format with video
        # 4. Best available (caught by _has_video_stream if audio-only)
        format_chain = [
            f"bestvideo[height<={max_height}][protocol^=https]+bestaudio[protocol^=https]",
            "bestvideo[height<=1080][protocol^=https]+bestaudio[protocol^=https]",
            "bestvideo[height<=720][protocol^=https]+bestaudio[protocol^=https]",
            "bestvideo[protocol^=https]+bestaudio[protocol^=https]",
            f"best[height<={max_height}][protocol^=https]",
            "best[height<=1080][protocol^=https]",
            "best[height<=720][protocol^=https]",
            "best"
        ]
        
        return "/".join(format_chain)
    
    def get_video_info(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Get video information without downloading."""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info
        except Exception as e:
            print(f"⚠️ Error getting video info: {e}")
            return None 
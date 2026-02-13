"""
Chorus detection service for video.fm

Uses librosa for audio analysis to find the best chorus/hook section
of a song for clip extraction. Falls back to intelligent heuristics
if detection fails.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("⚠️ librosa not installed - chorus detection will use fallback heuristics")


class ChorusDetector:
    """Detects chorus/hook sections in audio for optimal clip extraction."""
    
    def __init__(self, clip_duration: int = 15, cache_dir: str | Path = Path("cache")):
        """Initialize chorus detector.
        
        Args:
            clip_duration: Duration of clip to extract in seconds
            cache_dir: Directory for yt-dlp and analysis caches
        """
        self.clip_duration = clip_duration
        self.sample_rate = 22050  # Standard for music analysis
        self.cache_dir = Path(cache_dir)
        # Keep yt-dlp caches stable across runs and avoid cluttering temp dirs
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def detect_chorus_timestamp(self, video_url: str) -> int:
        """Detect the best chorus timestamp for a YouTube video.
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Start timestamp in seconds for the best chorus section
        """
        if not LIBROSA_AVAILABLE:
            print("   ⚠️ librosa not available, using fallback")
            return self._fallback_timestamp(video_url)
        
        # Download audio to temp file
        audio_path = self._download_audio(video_url)
        if not audio_path:
            print("   ⚠️ Audio download failed, using fallback")
            return self._fallback_timestamp(video_url)
        
        try:
            # Analyze audio and find best chorus section
            timestamp = self._analyze_audio(audio_path)
            return timestamp
        finally:
            # Clean up temp audio file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass
    
    def _download_audio(self, video_url: str) -> Optional[str]:
        """Download audio from YouTube video to temp file.
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Path to downloaded audio file, or None if failed
        """
        try:
            # Create temp file for audio
            temp_dir = tempfile.gettempdir()
            audio_path = os.path.join(temp_dir, f"videofm_audio_{os.getpid()}.mp3")
            
            # Remove existing file if present
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            # Use yt-dlp with robust options matching downloader.py
            import yt_dlp
            from yt_dlp.utils import DownloadError
            
            def build_ydl_opts(*, extractor_args: Optional[dict] = None) -> dict:
                ua = os.getenv(
                    "YTDLP_USER_AGENT",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                )
                cookiefile = os.getenv("YTDLP_COOKIEFILE") or os.getenv("YTDLP_COOKIES")
                proxy = os.getenv("YTDLP_PROXY")

                opts: dict = {
                    'format': 'bestaudio/best',
                    'outtmpl': audio_path.replace('.mp3', '.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',  # Lower quality is fine for analysis
                    }],
                    'quiet': True,
                    'no_warnings': True,
                    # Don't hide failures; we want to fall back quickly
                    'ignoreerrors': False,
                    # Put yt-dlp cache under our configurable cache dir (so you can move it to an external SSD)
                    'cachedir': str((self.cache_dir / "yt-dlp").resolve()),
                    'noplaylist': True,
                    'socket_timeout': 30,
                    'retries': 3,
                    'fragment_retries': 3,
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
            
            # Retry with alternate player client if YouTube blocks default extraction.
            attempts: list[tuple[str, dict]] = [
                ("default", {}),
                ("android player client", {"youtube": {"player_client": ["android"]}}),
                ("android client + skip dash/hls", {"youtube": {"player_client": ["android"], "skip": ["dash", "hls"]}}),
            ]

            last_err: Optional[BaseException] = None
            for idx, (label, extractor_args) in enumerate(attempts, start=1):
                try:
                    if idx > 1:
                        print(f"   🔁 Retrying audio download with {label}…")
                    with yt_dlp.YoutubeDL(build_ydl_opts(extractor_args=extractor_args or None)) as ydl:
                        ydl.download([video_url])
                    last_err = None
                    break
                except DownloadError as e:
                    last_err = e
                    continue
                except Exception as e:
                    last_err = e
                    continue

            if last_err is not None:
                raise last_err
            
            # Check for the output file (might have different extension before conversion)
            if os.path.exists(audio_path):
                return audio_path
            
            # Sometimes the file keeps original extension, check common ones
            for ext in ['.mp3', '.m4a', '.webm', '.opus']:
                alt_path = audio_path.replace('.mp3', ext)
                if os.path.exists(alt_path):
                    return alt_path
            
            print(f"   ⚠️ Audio file not found after download")
            return None
                
        except subprocess.TimeoutExpired:
            print("   ⚠️ Audio download timed out")
            return None
        except Exception as e:
            print(f"   ⚠️ Audio download error: {e}")
            return None
    
    def _analyze_audio(self, audio_path: str) -> int:
        """Analyze audio file to find the best chorus section.
        
        Uses multiple features:
        1. Spectral energy (choruses are typically louder/fuller)
        2. Spectral contrast (choruses have more dynamic range)
        3. Beat strength (choruses often have stronger beats)
        4. Self-similarity (choruses repeat)
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Best start timestamp in seconds
        """
        try:
            print("   🎵 Analyzing audio for chorus detection...")
            
            # Load audio (only first 4 minutes to save time)
            y, sr = librosa.load(audio_path, sr=self.sample_rate, duration=240)
            duration = len(y) / sr
            
            if duration < 30:
                # Very short song, just use middle
                return max(0, int(duration / 2) - self.clip_duration // 2)
            
            # Calculate frame-level features
            hop_length = 512
            
            # 1. RMS Energy - choruses are typically louder
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            
            # 2. Spectral Centroid - choruses often have brighter sound
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
            
            # 3. Spectral Contrast - choruses have more dynamic range
            spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop_length)
            contrast_mean = np.mean(spectral_contrast, axis=0)
            
            # Normalize features to 0-1 range
            rms_norm = self._normalize(rms)
            centroid_norm = self._normalize(spectral_centroid)
            contrast_norm = self._normalize(contrast_mean)
            
            # Combined "chorus likelihood" score
            # Weight energy highest, then contrast, then brightness
            chorus_score = (0.5 * rms_norm + 0.3 * contrast_norm + 0.2 * centroid_norm)
            
            # Smooth the score to avoid picking transient peaks
            window_size = int(2.0 * sr / hop_length)  # 2-second window
            if window_size > 1:
                chorus_score = np.convolve(chorus_score, np.ones(window_size)/window_size, mode='same')
            
            # Convert clip duration to frames
            clip_frames = int(self.clip_duration * sr / hop_length)
            
            # Find the best section (highest average score for clip_duration)
            best_start_frame = 0
            best_score = 0
            
            # Don't start in first 15 seconds (usually intro) or last 15 seconds (usually outro)
            start_buffer = int(15 * sr / hop_length)
            end_buffer = int(15 * sr / hop_length)
            
            for i in range(start_buffer, len(chorus_score) - clip_frames - end_buffer):
                section_score = np.mean(chorus_score[i:i + clip_frames])
                if section_score > best_score:
                    best_score = section_score
                    best_start_frame = i
            
            # Convert frame to timestamp
            best_timestamp = int(best_start_frame * hop_length / sr)
            
            # Ensure we don't exceed video bounds
            max_start = max(0, int(duration) - self.clip_duration - 5)
            best_timestamp = min(best_timestamp, max_start)
            best_timestamp = max(15, best_timestamp)  # Don't start before 15 seconds
            
            print(f"   ✅ Detected best section at {best_timestamp}s (score: {best_score:.2f})")
            return best_timestamp
            
        except Exception as e:
            print(f"   ⚠️ Audio analysis failed: {e}")
            return self._fallback_timestamp_from_duration(duration if 'duration' in dir() else 180)
    
    def _normalize(self, arr: np.ndarray) -> np.ndarray:
        """Normalize array to 0-1 range."""
        arr_min = np.min(arr)
        arr_max = np.max(arr)
        if arr_max - arr_min == 0:
            return np.zeros_like(arr)
        return (arr - arr_min) / (arr_max - arr_min)
    
    def _fallback_timestamp(self, video_url: str) -> int:
        """Get fallback timestamp when audio analysis isn't available.
        
        Uses yt-dlp to get video duration, then picks an intelligent default.
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Fallback start timestamp in seconds
        """
        try:
            # Get video duration using yt-dlp
            cmd = ['yt-dlp', '--get-duration', '--no-playlist', video_url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout.strip():
                duration_str = result.stdout.strip()
                duration = self._parse_duration(duration_str)
                return self._fallback_timestamp_from_duration(duration)
        except:
            pass
        
        # Ultimate fallback: assume 3-4 minute song, start around 1 minute
        return 60
    
    def _fallback_timestamp_from_duration(self, duration: float) -> int:
        """Calculate fallback timestamp based on song duration.
        
        Heuristic: First chorus usually appears around 25-35% into the song.
        
        Args:
            duration: Song duration in seconds
            
        Returns:
            Fallback start timestamp in seconds
        """
        if duration < 60:
            # Very short, just use middle
            return max(0, int(duration / 2) - self.clip_duration // 2)
        elif duration < 150:
            # Short song (< 2.5 min): chorus around 30 seconds
            return 30
        elif duration < 240:
            # Normal song (2.5-4 min): chorus around 50-60 seconds
            return int(duration * 0.28)  # ~28% in
        else:
            # Long song (> 4 min): chorus around 60-90 seconds  
            return int(duration * 0.25)  # ~25% in
    
    def _parse_duration(self, duration_str: str) -> float:
        """Parse duration string from yt-dlp (format: MM:SS or HH:MM:SS).
        
        Args:
            duration_str: Duration string
            
        Returns:
            Duration in seconds
        """
        parts = duration_str.strip().split(':')
        try:
            if len(parts) == 1:
                return float(parts[0])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except:
            pass
        return 180  # Default 3 minutes
    
    def detect_multiple_choruses(self, video_url: str, count: int = 3) -> List[int]:
        """Detect multiple chorus sections in a song.
        
        Useful for finding repeated sections that are likely choruses.
        
        Args:
            video_url: YouTube video URL
            count: Number of top sections to return
            
        Returns:
            List of start timestamps for likely chorus sections
        """
        # For now, just return the best one and some alternatives
        best = self.detect_chorus_timestamp(video_url)
        
        # Add some alternative timestamps
        alternatives = [best]
        
        # Add a section later in the song (second chorus typically ~30-45s after first)
        second_chorus = best + 40
        alternatives.append(second_chorus)
        
        # Add the fallback position
        fallback = self._fallback_timestamp(video_url)
        if abs(fallback - best) > 20:  # Only add if significantly different
            alternatives.append(fallback)
        
        return alternatives[:count]


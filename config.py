"""
Configuration module for video.fm

Contains configuration classes for different aspects of the application.
"""

from pathlib import Path
from dataclasses import dataclass, field
import os
import sys


@dataclass
class VideoConfig:
    """Configuration settings for video processing and output."""
    
    # Video processing settings
    video_output_dir: Path = field(default_factory=lambda: Path("clips"))
    cache_dir: Path = field(default_factory=lambda: Path("cache"))
    selected_codec: str = "libx264"
    max_video_quality: str = "1080"
    video_crf: str = "18"
    video_bitrate: str = "8M"
    ffmpeg_preset: str = "fast"
    max_songs: int = 50
    clip_duration: int = 15

    def __post_init__(self) -> None:
        """Allow lightweight runtime config via environment variables.

        Useful for performance tuning without editing code:
        - USE_VIDEOTOOLBOX=1 (macOS) -> uses h264_videotoolbox
        - VIDEO_CODEC=libx264|h264_videotoolbox|... -> override encoder
        - VIDEO_PRESET=ultrafast|superfast|... -> x264 preset
        - VIDEO_BITRATE=8M -> target bitrate (esp. for videotoolbox)
        - VIDEO_CRF=18 -> x264 CRF quality target
        """
        if os.getenv("USE_VIDEOTOOLBOX") in {"1", "true", "TRUE", "yes", "YES"} and sys.platform == "darwin":
            self.selected_codec = "h264_videotoolbox"

        # Allow storing clips/cache on an external drive (or any custom location)
        output_dir = os.getenv("VIDEO_OUTPUT_DIR")
        if output_dir:
            self.video_output_dir = Path(output_dir).expanduser()

        cache_dir = os.getenv("CACHE_DIR")
        if cache_dir:
            self.cache_dir = Path(cache_dir).expanduser()

        codec = os.getenv("VIDEO_CODEC")
        if codec:
            self.selected_codec = codec.strip()

        preset = os.getenv("VIDEO_PRESET")
        if preset:
            self.ffmpeg_preset = preset.strip()

        bitrate = os.getenv("VIDEO_BITRATE")
        if bitrate:
            self.video_bitrate = bitrate.strip()

        crf = os.getenv("VIDEO_CRF")
        if crf:
            self.video_crf = crf.strip()


class Config:
    """Main application configuration (placeholder for future expansion)."""
    
    def __init__(self):
        self.video = VideoConfig() 
"""
Configuration module for video.fm

Contains configuration classes for different aspects of the application.
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


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
    max_songs: int = 50
    clip_duration: int = 15


class Config:
    """Main application configuration (placeholder for future expansion)."""
    
    def __init__(self):
        self.video = VideoConfig() 
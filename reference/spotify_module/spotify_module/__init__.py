"""
Spotify Controller - Cross-platform Spotify automation module
"""

__version__ = "2.0.0"
__author__ = "Jeremy Hyde"

from .platform_detector import PlatformDetector
from .device_manager import DeviceManager
from .playlist_manager import PlaylistManager
from .playback_controller import PlaybackController

__all__ = [
    'PlatformDetector',
    'DeviceManager', 
    'PlaylistManager',
    'PlaybackController'
]

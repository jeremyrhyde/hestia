"""
Platform Detection Module
Detects operating system, architecture, and system capabilities
"""

import platform
import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple


class PlatformDetector:
    """Detects platform-specific information for cross-platform compatibility"""
    
    def __init__(self):
        self._system = platform.system().lower()
        self._machine = platform.machine().lower()
        self._platform_info = {
            'system': self._system,
            'machine': self._machine,
            'is_raspberry_pi': self._is_raspberry_pi_setup(),
            'is_macos': self._system == 'darwin',
            'is_linux': self._system == 'linux',
            'is_arm': 'arm' in self._machine or 'aarch64' in self._machine
        }
        self._platform_info["audio_system"] = self._detect_audio_system()
        self._platform_info["has_gui"] = self._has_gui_environment()
        self._platform_info["spotifyd_binary_name"] = self._get_spotifyd_binary_name()

    def _detect_platform_info(self) -> Dict[str, any]:
        """Detect comprehensive platform information"""
        info = {
            'system': self._system,
            'machine': self._machine,
            'is_raspberry_pi': self._is_raspberry_pi_setup(),
            'is_macos': self._system == 'darwin',
            'is_linux': self._system == 'linux',
            'is_arm': 'arm' in self._machine or 'aarch64' in self._machine,
            'audio_system': self._detect_audio_system(),
            'has_gui': self._has_gui_environment(),
            'spotifyd_binary_name': self._get_spotifyd_binary_name()
        }

        return info
    
    def _is_raspberry_pi_setup(self) -> bool:
        """Check if running on Raspberry Pi"""
        if self._system != 'linux':
            return False
        
        # Check for Pi-specific files
        pi_indicators = [
            '/proc/device-tree/model',
            '/sys/firmware/devicetree/base/model'
        ]
        
        for indicator in pi_indicators:
            if os.path.exists(indicator):
                try:
                    with open(indicator, 'r') as f:
                        content = f.read().lower()
                        if 'raspberry pi' in content:
                            return True
                except:
                    pass
        
        # Check /proc/cpuinfo as fallback
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read().lower()
                return 'raspberry pi' in content or 'bcm' in content
        except:
            return False
    
    def _detect_audio_system(self) -> str:
        """Detect the audio system in use"""
        if self.is_macos():
            return 'coreaudio'
        elif self.is_linux():
            # Check for PulseAudio
            if shutil.which('pulseaudio') or os.path.exists('/usr/bin/pulseaudio'):
                return 'pulseaudio'
            # Check for ALSA
            elif os.path.exists('/proc/asound') or shutil.which('aplay'):
                return 'alsa'
            else:
                return 'alsa'  # Default for Linux
        else:
            return 'unknown'
    
    def _has_gui_environment(self) -> bool:
        """Check if GUI environment is available"""
        if self.is_macos():
            # macOS always has GUI capabilities
            return True
        elif self.is_linux():
            # Check for X11 or Wayland
            return bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
        return False
    
    def _get_spotifyd_binary_name(self) -> str:
        """Get the appropriate spotifyd binary name for this platform"""
        if self.is_macos():
            if self._machine == 'arm64':
                return 'spotifyd-macos-arm64'
            else:
                return 'spotifyd-macos-x86_64'
        elif self.is_linux():
            if self.is_raspberry_pi():
                return 'spotifyd-linux-aarch64' # was armf but not working
            elif 'aarch64' in self._machine or 'arm64' in self._machine:
                return 'spotifyd-linux-aarch64'
            else:
                return 'spotifyd-linux-x86_64'
        else:
            raise RuntimeError(f"Unsupported platform: {self._system}")
    
    # Public interface methods
    def is_raspberry_pi(self) -> bool:
        """Check if running on Raspberry Pi"""
        return self._platform_info['is_raspberry_pi']
    
    def is_macos(self) -> bool:
        """Check if running on macOS"""
        return self._platform_info['is_macos']
    
    def is_linux(self) -> bool:
        """Check if running on Linux"""
        return self._platform_info['is_linux']
    
    def is_arm(self) -> bool:
        """Check if running on ARM architecture"""
        return self._platform_info['is_arm']
    
    def get_audio_system(self) -> str:
        """Get the audio system (alsa, pulseaudio, coreaudio)"""
        return self._platform_info['audio_system']
    
    def has_gui(self) -> bool:
        """Check if GUI environment is available"""
        return self._platform_info['has_gui']
    
    def get_spotifyd_binary_name(self) -> str:
        """Get the appropriate spotifyd binary name"""
        return self._platform_info['spotifyd_binary_name']
    
    def get_platform_summary(self) -> Dict[str, any]:
        """Get a summary of platform information"""
        return self._platform_info.copy()
    
    def get_config_recommendations(self) -> Dict[str, any]:
        """Get recommended configuration for this platform"""
        config = {
            'device_name_suffix': self._get_device_name_suffix(),
            'audio_backend': self.get_audio_system(),
            'cache_path': self._get_cache_path(),
            'config_path': self._get_config_path()
        }
        
        if self.is_raspberry_pi():
            config.update({
                'bitrate': 160,  # Lower bitrate for Pi
                'volume_normalisation': True,
                'normalisation_pregain': -10
            })
        else:
            config.update({
                'bitrate': 320,  # Higher quality for computers
                'volume_normalisation': True,
                'normalisation_pregain': -6
            })
        
        return config
    
    def _get_device_name_suffix(self) -> str:
        """Get appropriate device name suffix"""
        if self.is_raspberry_pi():
            return 'RaspberryPi'
        elif self.is_macos():
            return 'Mac'
        else:
            return 'Linux'
    
    def _get_cache_path(self) -> str:
        """Get appropriate cache directory path"""
        if self.is_macos():
            return str(Path.home() / 'Library' / 'Caches' / 'spotifyd')
        else:
            return str(Path.home() / '.cache' / 'spotifyd')
    
    def _get_config_path(self) -> str:
        """Get appropriate config directory path"""
        if self.is_macos():
            return str(Path.home() / 'Library' / 'Application Support' / 'spotifyd')
        else:
            return str(Path.home() / '.config' / 'spotifyd')

"""
Device Manager Module
Handles spotifyd installation, configuration, and lifecycle management
"""

import os
import subprocess
import time
import requests
import tarfile
import zipfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile
import signal
import psutil

from .platform_detector import PlatformDetector
from logger import get_logger


class DeviceManager:
    """Manages spotifyd installation and device lifecycle"""
    
    SPOTIFYD_RELEASES_URL = "https://api.github.com/repos/Spotifyd/spotifyd/releases/latest"
    
    def __init__(self, platform_detector: PlatformDetector, config: Dict = None):
        self.platform = platform_detector
        self.config = config or {}
        self.logger = get_logger("device_manager")
        self.spotifyd_path = self._get_spotifyd_path()
        self.config_dir = Path(self.platform.get_config_recommendations()['config_path'])
        self.cache_dir = Path(self.platform.get_config_recommendations()['cache_path'])
        self._spotifyd_process = None
        
        self.logger.info(f"DeviceManager initialized for platform: {self.platform.get_platform_summary()}")
        
    def _get_spotifyd_path(self) -> Path:
        """Get the path where spotifyd should be installed"""
        if self.platform.is_macos():
            return Path.home() / '.local' / 'bin' / 'spotifyd'
        else:
            return Path.home() / '.local' / 'bin' / 'spotifyd'
    
    def is_spotifyd_installed(self) -> bool:
        """Check if spotifyd is installed and executable"""
        installed = self.spotifyd_path.exists() and os.access(self.spotifyd_path, os.X_OK)
        self.logger.debug(f"spotifyd installed check: {installed} at {self.spotifyd_path}")
        return installed
    
    def is_spotifyd_running(self) -> bool:
        """Check if spotifyd process is currently running"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] == 'spotifyd' or (
                    proc.info['cmdline'] and 
                    any('spotifyd' in arg for arg in proc.info['cmdline'])
                ):
                    self.logger.debug(f"Found running spotifyd process: PID {proc.info['pid']}")
                    return True
            self.logger.debug("No running spotifyd process found")
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.logger.warning(f"Error checking spotifyd process: {e}")
            return False
    
    def get_spotifyd_pid(self) -> Optional[int]:
        """Get the PID of running spotifyd process"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] == 'spotifyd' or (
                    proc.info['cmdline'] and 
                    any('spotifyd' in arg for arg in proc.info['cmdline'])
                ):
                    pid = proc.info['pid']
                    self.logger.debug(f"Found spotifyd PID: {pid}")
                    return pid
            return None
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.logger.warning(f"Error getting spotifyd PID: {e}")
            return None
    
    def install_spotifyd(self, force_reinstall: bool = False) -> bool:
        """Download and install spotifyd for the current platform"""
        if self.is_spotifyd_installed() and not force_reinstall:
            self.logger.info("spotifyd is already installed")
            return True
        
        self.logger.info(f"Installing spotifyd for {self.platform.get_platform_summary()}")
        
        try:
            # Create directories
            self.spotifyd_path.parent.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {self.spotifyd_path.parent}")
            
            # Get download URL
            download_url = self._get_download_url()
            if not download_url:
                self.logger.error("Could not find appropriate spotifyd binary for this platform")
                return False
            
            # Download and extract
            self.logger.info(f"Downloading from: {download_url}")
            if self._download_and_extract(download_url):
                # Make executable
                os.chmod(self.spotifyd_path, 0o755)
                self.logger.info(f"spotifyd installed successfully at: {self.spotifyd_path}")
                return True
            else:
                self.logger.error("Failed to download and extract spotifyd")
                return False
                
        except Exception as e:
            self.logger.error(f"Error installing spotifyd: {e}")
            return False
    
    def _get_download_url(self) -> Optional[str]:
        """Get the download URL for the appropriate spotifyd binary"""
        try:
            self.logger.debug(f"Fetching release info from: {self.SPOTIFYD_RELEASES_URL}")
            response = requests.get(self.SPOTIFYD_RELEASES_URL)
            response.raise_for_status()
            release_data = response.json()
            
            binary_name = self.platform.get_spotifyd_binary_name()
            self.logger.debug(f"Looking for binary matching: {binary_name}")
            
            for asset in release_data['assets']:
                if binary_name in asset['name']:
                    url = asset['browser_download_url']
                    self.logger.debug(f"Found matching asset: {asset['name']} -> {url}")
                    return url
            
            self.logger.error(f"Could not find binary matching: {binary_name}")
            self.logger.debug(f"Available assets: {[asset['name'] for asset in release_data['assets']]}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching release info: {e}")
            return None
    
    def _download_and_extract(self, url: str) -> bool:
        """Download and extract spotifyd binary"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Download file
                self.logger.debug(f"Downloading to temporary directory: {temp_path}")
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                filename = url.split('/')[-1]
                download_path = temp_path / filename
                
                with open(download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                self.logger.debug(f"Downloaded {filename} ({download_path.stat().st_size} bytes)")
                
                # Extract based on file type
                if filename.endswith('.tar.gz'):
                    self.logger.debug("Extracting tar.gz archive")
                    with tarfile.open(download_path, 'r:gz') as tar:
                        # Find the spotifyd binary in the archive
                        for member in tar.getmembers():
                            if member.name.endswith('spotifyd') and member.isfile():
                                tar.extract(member, temp_path)
                                extracted_path = temp_path / member.name
                                shutil.move(str(extracted_path), str(self.spotifyd_path))
                                self.logger.debug(f"Extracted and moved binary from {member.name}")
                                return True
                elif filename.endswith('.zip'):
                    self.logger.debug("Extracting zip archive")
                    with zipfile.ZipFile(download_path, 'r') as zip_file:
                        for member in zip_file.namelist():
                            if member.endswith('spotifyd'):
                                zip_file.extract(member, temp_path)
                                extracted_path = temp_path / member
                                shutil.move(str(extracted_path), str(self.spotifyd_path))
                                self.logger.debug(f"Extracted and moved binary from {member}")
                                return True
                else:
                    # Assume it's a direct binary
                    self.logger.debug("Treating as direct binary")
                    shutil.move(str(download_path), str(self.spotifyd_path))
                    return True
                
                self.logger.error("Could not find spotifyd binary in downloaded archive")
                return False
                
        except Exception as e:
            self.logger.error(f"Error downloading/extracting: {e}")
            return False
    
    def create_spotifyd_config(self, device_name: str, spotify_config: Dict) -> bool:
        """Create spotifyd configuration file"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created config directory: {self.config_dir}")
            self.logger.debug(f"Created cache directory: {self.cache_dir}")
            
            config_file = self.config_dir / 'spotifyd.conf'
            platform_config = self.platform.get_config_recommendations()
            
            config_content = f"""[global]
username = "{spotify_config.get('username', '')}"
password = "{spotify_config.get('password', '')}"
client_id = "{spotify_config['client_id']}"
client_secret = "{spotify_config['client_secret']}"

device_name = "{device_name}"
device_type = "computer"
mixer = "softvol"
volume_controller = "softvol"
backend = "{platform_config['audio_backend']}"
bitrate = {platform_config['bitrate']}
cache_path = "{self.cache_dir}"

volume_normalisation = {str(platform_config['volume_normalisation']).lower()}
normalisation_pregain = {platform_config['normalisation_pregain']}

no_audio_cache = false
use_mpris = false
"""
            
            # Add platform-specific settings
            if self.platform.is_raspberry_pi():
                config_content += """
# Raspberry Pi specific settings
initial_volume = "50"
max_cache_size = 1000000000
"""
            
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            self.logger.info(f"Created spotifyd config at: {config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating spotifyd config: {e}")
            return False
    
    def start_spotifyd(self, device_name: str = None, background: bool = True) -> bool:
        """Start spotifyd daemon"""
        if not self.is_spotifyd_installed():
            self.logger.info("spotifyd is not installed. Installing now...")
            if not self.install_spotifyd():
                return False
        
        if self.is_spotifyd_running():
            self.logger.info("spotifyd is already running")
            return True
        
        device_name = device_name or f"SpotifyBot-{self.platform._get_device_name_suffix()}"
        
        try:
            cmd = [
                str(self.spotifyd_path),
                '--no-daemon' if not background else '--daemon',
                '--device-name', device_name
            ]
            
            # Add config file if it exists
            config_file = self.config_dir / 'spotifyd.conf'
            if config_file.exists():
                cmd.extend(['--config-path', str(config_file)])
                self.logger.debug(f"Using config file: {config_file}")
            
            self.logger.info(f"Starting spotifyd with command: {' '.join(cmd)}")
            
            if background:
                # Start as background process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                # Give it time to start
                time.sleep(3)
                
                if self.is_spotifyd_running():
                    self.logger.info(f"spotifyd started successfully as device: {device_name}")
                    return True
                else:
                    self.logger.error("spotifyd failed to start")
                    return False
            else:
                # Start in foreground (for debugging)
                self._spotifyd_process = subprocess.Popen(cmd)
                time.sleep(2)
                success = self._spotifyd_process.poll() is None
                if success:
                    self.logger.info(f"spotifyd started in foreground as device: {device_name}")
                else:
                    self.logger.error("spotifyd failed to start in foreground")
                return success
                
        except Exception as e:
            self.logger.error(f"Error starting spotifyd: {e}")
            return False
    
    def stop_spotifyd(self) -> bool:
        """Stop spotifyd daemon"""
        try:
            pid = self.get_spotifyd_pid()
            if pid:
                self.logger.info(f"Stopping spotifyd process (PID: {pid})")
                os.kill(pid, signal.SIGTERM)
                time.sleep(2)
                
                # Force kill if still running
                if self.is_spotifyd_running():
                    self.logger.warning("spotifyd still running, force killing...")
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(1)
                
                self.logger.info("spotifyd stopped")
                return True
            else:
                self.logger.info("spotifyd is not running")
                return True
                
        except Exception as e:
            self.logger.error(f"Error stopping spotifyd: {e}")
            return False
    
    def restart_spotifyd(self, device_name: str = None) -> bool:
        """Restart spotifyd daemon"""
        self.logger.info("Restarting spotifyd...")
        self.stop_spotifyd()
        time.sleep(2)
        return self.start_spotifyd(device_name)
    
    def get_device_id(self) -> Optional[str]:
        """Get the device ID of our spotifyd instance"""
        # This would need to be implemented by querying Spotify API
        # for devices and finding the one with our device name
        # For now, return None and let the Spotify class handle device discovery
        self.logger.debug("Device ID lookup not implemented, returning None")
        return None
    
    def ensure_spotifyd_ready(self, device_name: str = None, spotify_config: Dict = None) -> bool:
        """Ensure spotifyd is installed, configured, and running"""
        self.logger.info("Ensuring spotifyd is ready...")
        
        # Install if needed
        if not self.is_spotifyd_installed():
            if not self.install_spotifyd():
                return False
        
        # Create config if provided
        if spotify_config:
            if not self.create_spotifyd_config(device_name or "SpotifyBot", spotify_config):
                self.logger.warning("Could not create spotifyd config")
        
        # Start if not running
        if not self.is_spotifyd_running():
            if not self.start_spotifyd(device_name):
                return False
        
        self.logger.info("spotifyd is ready!")
        return True

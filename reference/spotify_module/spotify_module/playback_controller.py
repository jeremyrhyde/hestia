"""
Playback Controller Module
Handles Spotify playback control, volume management, and background operations
"""

import time
import threading
import signal
import sys
from typing import Dict, List, Optional, Callable
import spotipy
from logger import get_logger


class PlaybackController:
    """Controls Spotify playback with background operation support"""
    
    def __init__(self, spotify_client: spotipy.Spotify, device_id: str = None):
        self.sp = spotify_client
        self.device_id = device_id
        self.logger = get_logger("playback_controller")
        
        # Background operation state
        self._background_thread = None
        self._stop_background = threading.Event()
        self._is_playing = False
        self._current_volume = 50
        self._volume_ramp_active = False
        
        # Playback state
        self._current_playlist = None
        self._current_tracks = []
        
        self.logger.info("PlaybackController initialized")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, stopping playback...")
        self.stop_playback()
        sys.exit(0)
    
    def get_available_devices(self) -> List[Dict]:
        """Get list of available Spotify devices"""
        try:
            devices = self.sp.devices()
            device_list = []
            
            for device in devices['devices']:
                device_list.append({
                    'id': device['id'],
                    'name': device['name'],
                    'type': device['type'],
                    'is_active': device['is_active'],
                    'is_private_session': device['is_private_session'],
                    'is_restricted': device['is_restricted'],
                    'volume_percent': device['volume_percent']
                })
            
            self.logger.info(f"Found {len(device_list)} available devices")
            return device_list
            
        except Exception as e:
            self.logger.error(f"Error getting devices: {e}")
            return []
    
    def set_device(self, device_id: str = None, device_name: str = None) -> bool:
        """
        Set the target device for playback
        
        Args:
            device_id: Specific device ID to use
            device_name: Device name to search for (if device_id not provided)
            
        Returns:
            True if device was set successfully
        """
        try:
            if device_id:
                self.device_id = device_id
                self.logger.info(f"Device set to ID: {device_id}")
                return True
            elif device_name:
                devices = self.get_available_devices()
                for device in devices:
                    if device_name.lower() in device['name'].lower():
                        self.device_id = device['id']
                        self.logger.info(f"Device set to: {device['name']} (ID: {device['id']})")
                        return True
                
                self.logger.error(f"Device with name '{device_name}' not found")
                return False
            else:
                # Use first available device
                devices = self.get_available_devices()
                if devices:
                    self.device_id = devices[0]['id']
                    self.logger.info(f"Using first available device: {devices[0]['name']}")
                    return True
                else:
                    self.logger.error("No devices available")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error setting device: {e}")
            return False
    
    def start_playback(self, track_uris: List[str], device_id: str = None) -> bool:
        """
        Start playback of tracks
        
        Args:
            track_uris: List of Spotify track URIs
            device_id: Optional device ID override
            
        Returns:
            True if playback started successfully
        """
        try:
            target_device = device_id or self.device_id
            
            if not target_device:
                self.logger.error("No device specified for playback")
                return False
            
            self.logger.info(f"Starting playback of {len(track_uris)} tracks on device: {target_device}")
            
            self.sp.start_playback(device_id=target_device, uris=track_uris)
            self._is_playing = True
            self._current_tracks = track_uris
            
            self.logger.info("Playback started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting playback: {e}")
            return False
    
    def pause_playback(self) -> bool:
        """Pause current playback"""
        try:
            self.sp.pause_playback(device_id=self.device_id)
            self._is_playing = False
            self.logger.info("Playback paused")
            return True
        except Exception as e:
            self.logger.error(f"Error pausing playback: {e}")
            return False
    
    def resume_playback(self) -> bool:
        """Resume paused playback"""
        try:
            self.sp.start_playback(device_id=self.device_id)
            self._is_playing = True
            self.logger.info("Playback resumed")
            return True
        except Exception as e:
            self.logger.error(f"Error resuming playback: {e}")
            return False
    
    def stop_playback(self) -> bool:
        """Stop current playback"""
        try:
            # Stop background operations
            self._stop_background.set()
            if self._background_thread and self._background_thread.is_alive():
                self._background_thread.join(timeout=2)
            
            # Pause playback
            self.sp.pause_playback(device_id=self.device_id)
            self._is_playing = False
            self._volume_ramp_active = False
            
            self.logger.info("Playback stopped")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping playback: {e}")
            return False
    
    def set_volume(self, volume: int) -> bool:
        """
        Set playback volume
        
        Args:
            volume: Volume level (0-100)
            
        Returns:
            True if volume was set successfully
        """
        try:
            if not 0 <= volume <= 100:
                self.logger.error(f"Invalid volume level: {volume}. Must be 0-100")
                return False
            
            self.sp.volume(volume, device_id=self.device_id)
            self._current_volume = volume
            self.logger.info(f"Volume set to {volume}%")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting volume: {e}")
            return False
    
    def get_current_volume(self) -> int:
        """Get current volume level"""
        try:
            devices = self.sp.devices()
            for device in devices['devices']:
                if device['id'] == self.device_id:
                    volume = device['volume_percent']
                    self._current_volume = volume
                    return volume
            return self._current_volume
        except Exception as e:
            self.logger.error(f"Error getting volume: {e}")
            return self._current_volume
    
    def next_track(self) -> bool:
        """Skip to next track"""
        try:
            self.sp.next_track(device_id=self.device_id)
            self.logger.info("Skipped to next track")
            return True
        except Exception as e:
            self.logger.error(f"Error skipping track: {e}")
            return False
    
    def previous_track(self) -> bool:
        """Go to previous track"""
        try:
            self.sp.previous_track(device_id=self.device_id)
            self.logger.info("Went to previous track")
            return True
        except Exception as e:
            self.logger.error(f"Error going to previous track: {e}")
            return False
    
    def get_playback_state(self) -> Optional[Dict]:
        """Get current playback state"""
        try:
            state = self.sp.current_playback()
            if state:
                return {
                    'is_playing': state['is_playing'],
                    'progress_ms': state['progress_ms'],
                    'track': {
                        'name': state['item']['name'] if state['item'] else 'Unknown',
                        'artist': ', '.join([artist['name'] for artist in state['item']['artists']]) if state['item'] else 'Unknown',
                        'duration_ms': state['item']['duration_ms'] if state['item'] else 0
                    },
                    'device': {
                        'name': state['device']['name'],
                        'volume_percent': state['device']['volume_percent']
                    }
                }
            return None
        except Exception as e:
            self.logger.error(f"Error getting playback state: {e}")
            return None
    
    def start_volume_ramp(self, start_volume: int = 10, end_volume: int = 80, 
                         duration_seconds: int = 300, increment: int = 2) -> bool:
        """
        Start gradual volume increase in background
        
        Args:
            start_volume: Starting volume level
            end_volume: Target volume level
            duration_seconds: Total duration for the ramp
            increment: Volume increment per step
            
        Returns:
            True if ramp started successfully
        """
        try:
            if self._volume_ramp_active:
                self.logger.warning("Volume ramp already active")
                return False
            
            # Calculate delay between increments
            total_increments = (end_volume - start_volume) // increment
            delay_per_increment = duration_seconds / total_increments if total_increments > 0 else 1
            
            self.logger.info(f"Starting volume ramp: {start_volume}% -> {end_volume}% over {duration_seconds}s")
            
            # Set initial volume
            self.set_volume(start_volume)
            
            # Start background ramp
            self._volume_ramp_active = True
            self._stop_background.clear()
            self._background_thread = threading.Thread(
                target=self._volume_ramp_worker,
                args=(start_volume, end_volume, increment, delay_per_increment)
            )
            self._background_thread.daemon = True
            self._background_thread.start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting volume ramp: {e}")
            return False
    
    def _volume_ramp_worker(self, start_volume: int, end_volume: int, 
                           increment: int, delay: float):
        """Background worker for volume ramping"""
        try:
            current_volume = start_volume
            
            while (current_volume < end_volume and 
                   not self._stop_background.is_set() and 
                   self._volume_ramp_active):
                
                time.sleep(delay)
                
                if self._stop_background.is_set():
                    break
                
                current_volume = min(current_volume + increment, end_volume)
                self.set_volume(current_volume)
                
                self.logger.debug(f"Volume ramp: {current_volume}%")
            
            self._volume_ramp_active = False
            self.logger.info(f"Volume ramp completed at {current_volume}%")
            
        except Exception as e:
            self.logger.error(f"Error in volume ramp worker: {e}")
            self._volume_ramp_active = False
    
    def stop_volume_ramp(self) -> bool:
        """Stop active volume ramp"""
        try:
            if self._volume_ramp_active:
                self._volume_ramp_active = False
                self.logger.info("Volume ramp stopped")
                return True
            else:
                self.logger.info("No active volume ramp to stop")
                return False
        except Exception as e:
            self.logger.error(f"Error stopping volume ramp: {e}")
            return False
    
    def play_playlist_with_ramp(self, track_uris: List[str], playlist_name: str = None,
                               start_volume: int = 10, end_volume: int = 80,
                               ramp_duration: int = 300) -> bool:
        """
        Play playlist with automatic volume ramping
        
        Args:
            track_uris: List of track URIs to play
            playlist_name: Name of playlist for logging
            start_volume: Starting volume
            end_volume: Target volume
            ramp_duration: Duration of volume ramp in seconds
            
        Returns:
            True if playback started successfully
        """
        try:
            playlist_name = playlist_name or "Unknown Playlist"
            self.logger.info(f"Starting playlist '{playlist_name}' with volume ramp")
            
            # Start playback
            if not self.start_playback(track_uris):
                return False
            
            # Start volume ramp
            if not self.start_volume_ramp(start_volume, end_volume, ramp_duration):
                self.logger.warning("Failed to start volume ramp, continuing with playback")
            
            self._current_playlist = playlist_name
            return True
            
        except Exception as e:
            self.logger.error(f"Error playing playlist with ramp: {e}")
            return False
    
    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self._is_playing
    
    def is_volume_ramping(self) -> bool:
        """Check if volume ramp is active"""
        return self._volume_ramp_active
    
    def get_status(self) -> Dict:
        """Get comprehensive status information"""
        return {
            'is_playing': self._is_playing,
            'current_volume': self._current_volume,
            'volume_ramp_active': self._volume_ramp_active,
            'current_playlist': self._current_playlist,
            'device_id': self.device_id,
            'track_count': len(self._current_tracks)
        }

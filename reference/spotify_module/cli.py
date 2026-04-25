"""
Interactive CLI for Spotify Controller
Allows users to search and play playlists by name with real-time control
"""

import sys
import time
import threading
from typing import Optional
import yaml
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from spotify_module import (
    PlatformDetector, 
    DeviceManager, 
    PlaylistManager, 
    PlaybackController
)
from logger import get_logger


class SpotifyControllerCLI:
    """Interactive command-line interface for Spotify automation"""
    
    def __init__(self):
        self.logger = get_logger("spotify_cli")
        self.platform = None
        self.device_manager = None
        self.playlist_manager = None
        self.playback_controller = None
        self.spotify_client = None
        self.config = None
        
        # CLI state
        self.running = False
        self.current_playlist = None
        
    def load_config(self, config_path: str = "config/config.yaml") -> bool:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            self.logger.info(f"Configuration loaded from {config_path}")
            return True
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {config_path}")
            self.logger.info("Please create a config.yaml file with your Spotify credentials")
            return False
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return False
    
    def initialize_components(self) -> bool:
        """Initialize all controller components"""
        try:
            # Initialize platform detection
            self.platform = PlatformDetector()
            self.logger.info(f"Platform detected: {self.platform.get_platform_summary()}")
            
            # Initialize Spotify client
            spotify_config = self.config['spotify']
            self.spotify_client = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=spotify_config['client_id'],
                client_secret=spotify_config['client_secret'],
                redirect_uri=spotify_config.get('redirect_uri', 'http://localhost:8888/callback'),
                scope="user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative",
                cache_path=".spotify_cache"
            ))
            
            # Test authentication
            user_info = self.spotify_client.current_user()
            self.logger.info(f"Authenticated as: {user_info['id']}")
            
            # Initialize device manager
            self.device_manager = DeviceManager(self.platform, self.config)
            
            # Initialize playlist manager
            self.playlist_manager = PlaylistManager(self.spotify_client)
            
            # Initialize playback controller
            self.playback_controller = PlaybackController(self.spotify_client)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing components: {e}")
            return False
    
    def setup_device(self) -> bool:
        """Setup and ensure spotifyd device is ready"""
        try:
            device_name = self.config.get('device_name', 'SpotifyBot')
            
            # Ensure spotifyd is ready
            if not self.device_manager.ensure_spotifyd_ready(device_name, self.config['spotify']):
                self.logger.error("Failed to setup spotifyd device")
                return False
            
            # Wait a moment for device to appear in Spotify
            time.sleep(3)
            
            # Set device for playback controller
            if not self.playback_controller.set_device(device_name=device_name):
                self.logger.error("Failed to set playback device")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up device: {e}")
            return False
    
    def search_and_select_playlist(self, query: str) -> Optional[dict]:
        """Search for playlists and let user select one"""
        try:
            print(f"\nSearching for playlists matching '{query}'...")
            playlists = self.playlist_manager.search_playlists(query, limit=10)
            
            if not playlists:
                print("No playlists found matching your search.")
                return None
            
            print("\nFound playlists:")
            for i, playlist in enumerate(playlists, 1):
                summary = self.playlist_manager.create_playlist_summary(playlist)
                print(f"{i}. {summary}")
            
            # Auto-select if only one result
            if len(playlists) == 1:
                print(f"\nAuto-selecting: {playlists[0]['name']}")
                return playlists[0]
            
            # Let user choose
            while True:
                try:
                    choice = input(f"\nSelect playlist (1-{len(playlists)}) or 'q' to quit: ").strip()
                    if choice.lower() == 'q':
                        return None
                    
                    index = int(choice) - 1
                    if 0 <= index < len(playlists):
                        return playlists[index]
                    else:
                        print(f"Please enter a number between 1 and {len(playlists)}")
                        
                except ValueError:
                    print("Please enter a valid number or 'q' to quit")
                    
        except Exception as e:
            self.logger.error(f"Error searching playlists: {e}")
            return None
    
    def start_playlist_playback(self, playlist: dict) -> bool:
        """Start playing the selected playlist"""
        try:
            print(f"\nLoading tracks from '{playlist['name']}'...")
            track_uris = self.playlist_manager.get_playlist_tracks(playlist['id'])
            
            if not track_uris:
                print("No tracks found in playlist")
                return False
            
            print(f"Found {len(track_uris)} tracks")
            
            # Start playback
            print("Starting playback...")
            success = self.playback_controller.start_playback(track_uris)
            if success:
                volume = self.config.get('default_volume', 50)
                self.playback_controller.set_volume(volume)
                print(f"Volume set to {volume}%")
            
            if success:
                self.current_playlist = playlist
                print(f"✓ Now playing: {playlist['name']}")
                return True
            else:
                print("✗ Failed to start playback")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting playlist playback: {e}")
            return False
    
    def show_help(self):
        """Display available commands"""
        print("\nAvailable commands:")
        print("  [p]ause     - Pause playback")
        print("  [r]esume    - Resume playback")
        print("  [s]top      - Stop playback")
        print("  [v] <num>   - Set volume (0-100)")
        print("  [n]ext      - Skip to next track")
        print("  [b]ack      - Go to previous track")
        print("  [i]nfo      - Show current track info")
        print("  [st]atus    - Show playback status")
        print("  [h]elp      - Show this help")
        print("  [q]uit      - Quit application")
        print("  <playlist>  - Search and play new playlist")
    
    def handle_command(self, command: str) -> bool:
        """Handle user commands during playback"""
        command = command.strip().lower()
        
        if command in ['p', 'pause']:
            if self.playback_controller.pause_playback():
                print("⏸ Playback paused")
            else:
                print("✗ Failed to pause")
                
        elif command in ['r', 'resume']:
            if self.playback_controller.resume_playback():
                print("▶ Playback resumed")
            else:
                print("✗ Failed to resume")
                
        elif command in ['s', 'stop']:
            if self.playback_controller.stop_playback():
                print("⏹ Playback stopped")
                self.current_playlist = None
            else:
                print("✗ Failed to stop")
                
        elif command.startswith('v '):
            try:
                volume = int(command.split()[1])
                if self.playback_controller.set_volume(volume):
                    print(f"🔊 Volume set to {volume}%")
                else:
                    print("✗ Failed to set volume")
            except (ValueError, IndexError):
                print("Usage: v <number> (0-100)")
                
        elif command in ['n', 'next']:
            if self.playback_controller.next_track():
                print("⏭ Skipped to next track")
            else:
                print("✗ Failed to skip track")
                
        elif command in ['b', 'back']:
            if self.playback_controller.previous_track():
                print("⏮ Went to previous track")
            else:
                print("✗ Failed to go back")
                
        elif command in ['i', 'info']:
            state = self.playback_controller.get_playback_state()
            if state:
                track = state['track']
                progress_min = state['progress_ms'] // 60000
                progress_sec = (state['progress_ms'] % 60000) // 1000
                duration_min = track['duration_ms'] // 60000
                duration_sec = (track['duration_ms'] % 60000) // 1000
                
                print(f"🎵 {track['name']} by {track['artist']}")
                print(f"⏱ {progress_min}:{progress_sec:02d} / {duration_min}:{duration_sec:02d}")
                print(f"🔊 Volume: {state['device']['volume_percent']}%")
            else:
                print("No playback information available")
                
        elif command in ['st', 'status']:
            status = self.playback_controller.get_status()
            print(f"\nPlayback Status:")
            print(f"  Playing: {'Yes' if status['is_playing'] else 'No'}")
            print(f"  Volume: {status['current_volume']}%")
            print(f"  Volume Ramp: {'Active' if status['volume_ramp_active'] else 'Inactive'}")
            print(f"  Playlist: {status['current_playlist'] or 'None'}")
            print(f"  Tracks: {status['track_count']}")
            
        elif command in ['h', 'help']:
            self.show_help()
            
        elif command in ['q', 'quit']:
            return False
            
        else:
            # Treat as playlist search
            if command:
                playlist = self.search_and_select_playlist(command)
                if playlist:
                    self.start_playlist_playback(playlist)
            
        return True
    
    def run_interactive_mode(self):
        """Run the interactive command loop"""
        print("\n" + "="*60)
        print("🎵 Spotify Controller - Interactive Mode")
        print("="*60)
        
        self.show_help()
        
        print(f"\nCurrent device: {self.playback_controller.device_id}")
        print("Ready! Enter a playlist name to search and play, or use commands above.")
        
        self.running = True
        
        try:
            while self.running:
                try:
                    command = input("\n> ").strip()
                    if not command:
                        continue
                        
                    if not self.handle_command(command):
                        break
                        
                except KeyboardInterrupt:
                    print("\n\nShutting down...")
                    break
                except EOFError:
                    break
                    
        finally:
            # Cleanup
            if self.playback_controller:
                self.playback_controller.stop_playback()
            if self.device_manager:
                self.device_manager.stop_spotifyd()
            print("Goodbye!")
    
    def run(self, config_path: str = "config.yaml"):
        """Main entry point"""
        print("🎵 Spotify Controller Starting...")
        
        # Load configuration
        if not self.load_config(config_path):
            return False
        
        # Initialize components
        if not self.initialize_components():
            return False
        
        # Setup device
        if not self.setup_device():
            return False
        
        # Run interactive mode
        self.run_interactive_mode()
        
        return True


def main():
    """CLI entry point"""
    cli = SpotifyControllerCLI()
    
    config_file = "config/config.yaml"
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    try:
        cli.run(config_file)
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

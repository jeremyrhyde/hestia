"""
Playlist Manager Module
Handles playlist search, retrieval, and management
"""

import spotipy
from typing import Dict, List, Optional, Tuple
from logger import get_logger


class PlaylistManager:
    """Manages playlist operations and search functionality"""
    
    def __init__(self, spotify_client: spotipy.Spotify):
        self.sp = spotify_client
        self.logger = get_logger("playlist_manager")
        self.logger.info("PlaylistManager initialized")
    
    def search_playlists(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for playlists by name
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of playlist dictionaries with id, name, owner, and track count
        """
        try:
            self.logger.info(f"Searching for playlists with query: '{query}'")
            
            # Search user's own playlists first
            user_playlists = self._search_user_playlists(query, limit // 2)
            
            # Search public playlists
            public_playlists = self._search_public_playlists(query, limit - len(user_playlists))
            
            # Combine and deduplicate
            all_playlists = user_playlists + public_playlists
            seen_ids = set()
            unique_playlists = []
            
            for playlist in all_playlists:
                if playlist['id'] not in seen_ids:
                    seen_ids.add(playlist['id'])
                    unique_playlists.append(playlist)
            
            self.logger.info(f"Found {len(unique_playlists)} unique playlists")
            return unique_playlists[:limit]
            
        except Exception as e:
            self.logger.error(f"Error searching playlists: {e}")
            return []
    
    def _search_user_playlists(self, query: str, limit: int) -> List[Dict]:
        """Search user's own playlists"""
        try:
            user_playlists = []
            offset = 0
            query_lower = query.lower()
            
            while len(user_playlists) < limit:
                results = self.sp.current_user_playlists(limit=50, offset=offset)
                
                if not results['items']:
                    break
                
                for playlist in results['items']:
                    if playlist and playlist['name']:
                        if query_lower in playlist['name'].lower():
                            user_playlists.append({
                                'id': playlist['id'],
                                'name': playlist['name'],
                                'owner': playlist['owner']['display_name'] or playlist['owner']['id'],
                                'track_count': playlist['tracks']['total'],
                                'is_own': True,
                                'public': playlist['public'],
                                'description': playlist.get('description', ''),
                                'uri': playlist['uri']
                            })
                            
                            if len(user_playlists) >= limit:
                                break
                
                offset += 50
                if offset >= results['total']:
                    break
            
            self.logger.debug(f"Found {len(user_playlists)} user playlists matching '{query}'")
            return user_playlists
            
        except Exception as e:
            self.logger.error(f"Error searching user playlists: {e}")
            return []
    
    def _search_public_playlists(self, query: str, limit: int) -> List[Dict]:
        """Search public playlists"""
        try:
            results = self.sp.search(q=query, type='playlist', limit=limit)
            public_playlists = []
            
            for playlist in results['playlists']['items']:
                if playlist and playlist['name']:
                    public_playlists.append({
                        'id': playlist['id'],
                        'name': playlist['name'],
                        'owner': playlist['owner']['display_name'] or playlist['owner']['id'],
                        'track_count': playlist['tracks']['total'],
                        'is_own': False,
                        'public': playlist['public'],
                        'description': playlist.get('description', ''),
                        'uri': playlist['uri']
                    })
            
            self.logger.debug(f"Found {len(public_playlists)} public playlists matching '{query}'")
            return public_playlists
            
        except Exception as e:
            self.logger.error(f"Error searching public playlists: {e}")
            return []
    
    def get_playlist_by_name(self, name: str, exact_match: bool = False) -> Optional[Dict]:
        """
        Get a specific playlist by name
        
        Args:
            name: Playlist name to search for
            exact_match: If True, requires exact name match
            
        Returns:
            Playlist dictionary or None if not found
        """
        try:
            playlists = self.search_playlists(name, limit=50)
            
            if exact_match:
                # Look for exact match first
                for playlist in playlists:
                    if playlist['name'].lower() == name.lower():
                        self.logger.info(f"Found exact match for playlist: '{name}'")
                        return playlist
                return None
            else:
                # Return first match (best match from search)
                if playlists:
                    self.logger.info(f"Found playlist match: '{playlists[0]['name']}'")
                    return playlists[0]
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting playlist by name '{name}': {e}")
            return None
    
    def get_playlist_tracks(self, playlist_id: str) -> List[str]:
        """
        Get all track URIs from a playlist
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            List of track URIs
        """
        try:
            self.logger.info(f"Fetching tracks for playlist ID: {playlist_id}")
            
            tracks = []
            offset = 0
            
            while True:
                results = self.sp.playlist_tracks(playlist_id, offset=offset, limit=100)
                
                for item in results['items']:
                    if item['track'] and item['track']['uri']:
                        tracks.append(item['track']['uri'])
                
                if not results['next']:
                    break
                    
                offset += 100
            
            self.logger.info(f"Retrieved {len(tracks)} tracks from playlist")
            return tracks
            
        except Exception as e:
            self.logger.error(f"Error fetching playlist tracks: {e}")
            return []
    
    def get_playlist_info(self, playlist_id: str) -> Optional[Dict]:
        """
        Get detailed playlist information
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            Detailed playlist information dictionary
        """
        try:
            playlist = self.sp.playlist(playlist_id)
            
            info = {
                'id': playlist['id'],
                'name': playlist['name'],
                'description': playlist.get('description', ''),
                'owner': playlist['owner']['display_name'] or playlist['owner']['id'],
                'track_count': playlist['tracks']['total'],
                'followers': playlist['followers']['total'],
                'public': playlist['public'],
                'collaborative': playlist['collaborative'],
                'uri': playlist['uri'],
                'external_urls': playlist['external_urls'],
                'images': playlist['images']
            }
            
            self.logger.debug(f"Retrieved info for playlist: '{info['name']}'")
            return info
            
        except Exception as e:
            self.logger.error(f"Error getting playlist info: {e}")
            return None
    
    def list_user_playlists(self, limit: int = 50) -> List[Dict]:
        """
        List all user's playlists
        
        Args:
            limit: Maximum number of playlists to return
            
        Returns:
            List of user's playlists
        """
        try:
            self.logger.info("Fetching user's playlists")
            
            playlists = []
            offset = 0
            
            while len(playlists) < limit:
                results = self.sp.current_user_playlists(limit=50, offset=offset)
                
                if not results['items']:
                    break
                
                for playlist in results['items']:
                    if playlist:
                        playlists.append({
                            'id': playlist['id'],
                            'name': playlist['name'],
                            'owner': playlist['owner']['display_name'] or playlist['owner']['id'],
                            'track_count': playlist['tracks']['total'],
                            'public': playlist['public'],
                            'collaborative': playlist['collaborative'],
                            'description': playlist.get('description', ''),
                            'uri': playlist['uri']
                        })
                        
                        if len(playlists) >= limit:
                            break
                
                offset += 50
                if offset >= results['total']:
                    break
            
            self.logger.info(f"Retrieved {len(playlists)} user playlists")
            return playlists
            
        except Exception as e:
            self.logger.error(f"Error listing user playlists: {e}")
            return []
    
    def create_playlist_summary(self, playlist: Dict) -> str:
        """
        Create a human-readable summary of a playlist
        
        Args:
            playlist: Playlist dictionary
            
        Returns:
            Formatted playlist summary string
        """
        summary = f"'{playlist['name']}' by {playlist['owner']}"
        summary += f" ({playlist['track_count']} tracks)"
        
        if playlist.get('is_own'):
            summary += " [Your playlist]"
        elif playlist.get('public'):
            summary += " [Public]"
        else:
            summary += " [Private]"
        
        if playlist.get('description'):
            # Truncate long descriptions
            desc = playlist['description'][:100]
            if len(playlist['description']) > 100:
                desc += "..."
            summary += f" - {desc}"
        
        return summary

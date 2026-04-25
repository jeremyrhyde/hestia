"""
Main entry point for Spotify Controller
Uses the SpotifyControllerCLI class for interactive control
"""

import sys
from cli import SpotifyControllerCLI

def main():
    """Main function using SpotifyControllerCLI"""
    cli = SpotifyControllerCLI()
    
    config_file = "config/config.yaml"
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    try:
        cli.run(config_file)
        return 0
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

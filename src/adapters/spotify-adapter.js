const BaseAdapter = require('./base-adapter');
const { spawn } = require('child_process');
const path = require('path');

/**
 * Spotify adapter for interfacing with Spotify control modules
 * Integrates with the Python-based spotify-module submodule
 */
class SpotifyAdapter extends BaseAdapter {
  constructor(deviceConfig, logger) {
    super(deviceConfig, logger);
    this.currentState = {
      playing: false,
      volume: deviceConfig.settings?.default_volume || 50,
      track: null,
      playlist: null,
      shuffle: false,
      repeat: 'off', // 'off', 'track', 'context'
      position: 0
    };
    this.modulePath = path.join(__dirname, '../modules/spotify-module');
    this.pythonProcess = null;
  }

  /**
   * Initialize the Spotify adapter
   * @returns {Promise<boolean>} Success status
   */
  async initialize() {
    try {
      // Check if Python module exists
      const fs = require('fs');
      const mainPyPath = path.join(this.modulePath, 'main.py');
      
      if (!fs.existsSync(mainPyPath)) {
        throw new Error(`Spotify module not found at ${mainPyPath}`);
      }
      
      // Test Python module availability
      const testResult = await this.executePythonCommand(['--help']);
      if (testResult.success) {
        this.connected = true;
        
        if (this.logger) {
          this.logger.info(`Spotify adapter initialized for device: ${this.deviceConfig.id}`);
        }
        
        return true;
      } else {
        throw new Error('Failed to initialize Python Spotify module');
      }
      
    } catch (error) {
      this.handleError(error, 'initialize');
      return false;
    }
  }

  /**
   * Execute a Python command in the spotify module
   * @param {Array} args - Command arguments
   * @returns {Promise<Object>} Command result
   */
  async executePythonCommand(args = []) {
    return new Promise((resolve) => {
      const pythonProcess = spawn('python3', ['main.py', ...args], {
        cwd: this.modulePath,
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';

      pythonProcess.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      pythonProcess.on('close', (code) => {
        resolve({
          success: code === 0,
          stdout: stdout.trim(),
          stderr: stderr.trim(),
          code
        });
      });

      pythonProcess.on('error', (error) => {
        resolve({
          success: false,
          error: error.message,
          code: -1
        });
      });
    });
  }

  /**
   * Get current Spotify playback status
   * @returns {Promise<Object>} Playback status
   */
  async getStatus() {
    try {
      // TODO: Replace with actual module call
      // const status = await this.spotifyModule.getCurrentPlayback();
      
      // For now, return simulated status
      return {
        ...this.currentState,
        device_id: this.deviceConfig.id,
        device_name: this.deviceConfig.name,
        online: this.connected,
        last_updated: new Date().toISOString()
      };
    } catch (error) {
      this.handleError(error, 'getStatus');
      throw error;
    }
  }

  /**
   * Execute a command on the Spotify device
   * @param {string} command - Command name (play, pause, skip, volume, etc.)
   * @param {Object} params - Command parameters
   * @returns {Promise<Object>} Command result
   */
  async executeCommand(command, params = {}) {
    const validation = this.validateCommand(command, params);
    if (!validation.valid) {
      throw new Error(validation.error);
    }

    try {
      let result = {};

      switch (command) {
        case 'play':
          result = await this.play(params.uri, params.playlist);
          break;
          
        case 'pause':
          result = await this.pause();
          break;
          
        case 'skip':
          result = await this.skip(params.direction || 'next');
          break;
          
        case 'volume':
          result = await this.setVolume(params.level);
          break;
          
        case 'shuffle':
          result = await this.setShuffle(params.state);
          break;
          
        case 'repeat':
          result = await this.setRepeat(params.mode);
          break;
          
        default:
          throw new Error(`Unknown command: ${command}`);
      }

      return {
        success: true,
        command,
        params,
        result,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      this.handleError(error, `executeCommand:${command}`);
      throw error;
    }
  }

  /**
   * Start or resume playback
   * @param {string} uri - Spotify URI to play (optional)
   * @param {string} playlist - Playlist name to play (optional)
   * @returns {Promise<Object>} Result
   */
  async play(uri = null, playlist = null) {
    // TODO: Replace with actual module call
    // if (playlist) {
    //   await this.spotifyModule.playPlaylist(playlist);
    // } else if (uri) {
    //   await this.spotifyModule.play(uri);
    // } else {
    //   await this.spotifyModule.resume();
    // }
    
    this.currentState.playing = true;
    
    if (playlist) {
      this.currentState.playlist = playlist;
    }
    
    if (this.logger) {
      const action = playlist ? `playlist ${playlist}` : uri ? `URI ${uri}` : 'current track';
      this.logger.info(`Spotify ${this.deviceConfig.id} playing: ${action}`);
    }
    
    return { 
      playing: true, 
      uri, 
      playlist,
      action: playlist ? 'playlist' : uri ? 'track' : 'resume'
    };
  }

  /**
   * Pause playback
   * @returns {Promise<Object>} Result
   */
  async pause() {
    // TODO: Replace with actual module call
    // await this.spotifyModule.pause();
    
    this.currentState.playing = false;
    
    if (this.logger) {
      this.logger.info(`Spotify ${this.deviceConfig.id} paused`);
    }
    
    return { playing: false };
  }

  /**
   * Skip to next or previous track
   * @param {string} direction - 'next' or 'previous'
   * @returns {Promise<Object>} Result
   */
  async skip(direction = 'next') {
    if (!['next', 'previous'].includes(direction)) {
      throw new Error('Direction must be "next" or "previous"');
    }

    // TODO: Replace with actual module call
    // if (direction === 'next') {
    //   await this.spotifyModule.skipToNext();
    // } else {
    //   await this.spotifyModule.skipToPrevious();
    // }
    
    if (this.logger) {
      this.logger.info(`Spotify ${this.deviceConfig.id} skipped to ${direction} track`);
    }
    
    return { skipped: direction };
  }

  /**
   * Set playback volume
   * @param {number} level - Volume level (0-100)
   * @returns {Promise<Object>} Result
   */
  async setVolume(level) {
    const maxVolume = this.deviceConfig.settings?.max_volume || 100;
    
    if (level < 0 || level > maxVolume) {
      throw new Error(`Volume must be between 0 and ${maxVolume}`);
    }

    // TODO: Replace with actual module call
    // await this.spotifyModule.setVolume(level);
    
    this.currentState.volume = level;
    
    if (this.logger) {
      this.logger.info(`Spotify ${this.deviceConfig.id} volume set to: ${level}%`);
    }
    
    return { volume: level };
  }

  /**
   * Set shuffle mode
   * @param {boolean} state - Shuffle state
   * @returns {Promise<Object>} Result
   */
  async setShuffle(state) {
    // TODO: Replace with actual module call
    // await this.spotifyModule.setShuffle(state);
    
    this.currentState.shuffle = state;
    
    if (this.logger) {
      this.logger.info(`Spotify ${this.deviceConfig.id} shuffle set to: ${state}`);
    }
    
    return { shuffle: state };
  }

  /**
   * Set repeat mode
   * @param {string} mode - Repeat mode ('off', 'track', 'context')
   * @returns {Promise<Object>} Result
   */
  async setRepeat(mode) {
    if (!['off', 'track', 'context'].includes(mode)) {
      throw new Error('Repeat mode must be "off", "track", or "context"');
    }

    // TODO: Replace with actual module call
    // await this.spotifyModule.setRepeat(mode);
    
    this.currentState.repeat = mode;
    
    if (this.logger) {
      this.logger.info(`Spotify ${this.deviceConfig.id} repeat set to: ${mode}`);
    }
    
    return { repeat: mode };
  }

  /**
   * Validate Spotify-specific commands
   * @param {string} command - Command name
   * @param {Object} params - Parameters to validate
   * @returns {Object} Validation result
   */
  validateCommand(command, params) {
    const baseValidation = super.validateCommand(command, params);
    if (!baseValidation.valid) {
      return baseValidation;
    }

    // Additional Spotify-specific validation
    switch (command) {
      case 'volume':
        if (typeof params.level !== 'number' || params.level < 0 || params.level > 100) {
          return { valid: false, error: 'Volume level must be a number between 0 and 100' };
        }
        break;
        
      case 'shuffle':
        if (typeof params.state !== 'boolean') {
          return { valid: false, error: 'Shuffle state must be boolean' };
        }
        break;
        
      case 'repeat':
        if (!['off', 'track', 'context'].includes(params.mode)) {
          return { valid: false, error: 'Repeat mode must be "off", "track", or "context"' };
        }
        break;
        
      case 'skip':
        if (params.direction && !['next', 'previous'].includes(params.direction)) {
          return { valid: false, error: 'Skip direction must be "next" or "previous"' };
        }
        break;
    }

    return { valid: true };
  }

  /**
   * Get Spotify-specific device information
   * @returns {Object} Extended device info
   */
  getDeviceInfo() {
    const baseInfo = super.getDeviceInfo();
    return {
      ...baseInfo,
      currentState: this.currentState,
      settings: this.deviceConfig.settings,
      connection: this.deviceConfig.connection
    };
  }
}

module.exports = SpotifyAdapter;

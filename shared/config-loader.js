const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

class ConfigLoader {
  constructor(configDir = 'config') {
    this.configDir = configDir;
    this.cache = new Map();
    this.watchers = new Map();
  }

  /**
   * Load a specific configuration file
   * @param {string} configPath - Path relative to config directory
   * @param {boolean} useCache - Whether to use cached version
   * @returns {Object} Parsed configuration object
   */
  load(configPath, useCache = true) {
    const fullPath = path.join(this.configDir, configPath);
    
    if (useCache && this.cache.has(fullPath)) {
      return this.cache.get(fullPath);
    }

    try {
      const fileContent = fs.readFileSync(fullPath, 'utf8');
      const config = yaml.load(fileContent);
      
      if (useCache) {
        this.cache.set(fullPath, config);
      }
      
      return config;
    } catch (error) {
      throw new Error(`Failed to load config file ${configPath}: ${error.message}`);
    }
  }

  /**
   * Load all configuration files and merge them into a single object
   * @returns {Object} Complete configuration object
   */
  loadAll() {
    const config = {
      app: this.load('app.yaml'),
      rooms: this.load('rooms.yaml'),
      devices: {
        lights: this.load('devices/lights.yaml'),
        spotify: this.load('devices/spotify.yaml'),
        kasa: this.load('devices/kasa.yaml')
      },
      services: {},
      scenes: {
        morning: this.load('scenes/morning.yaml')
      }
    };

    // Load optional service configurations
    try {
      config.services.llm = this.load('services/llm.yaml');
    } catch (error) {
      // LLM service is optional, skip if not found
      // Only log this once by checking if it's already been logged
      if (!this._llmWarningLogged) {
        console.log('LLM service configuration not found, skipping...');
        this._llmWarningLogged = true;
      }
    }

    return config;
  }

  /**
   * Get device configuration by ID
   * @param {string} deviceId - Device identifier
   * @returns {Object|null} Device configuration or null if not found
   */
  getDevice(deviceId) {
    const devices = this.loadAll().devices;
    
    // Search through all device types
    for (const deviceType of Object.keys(devices)) {
      const deviceTypeConfig = devices[deviceType];
      
      // The structure is: devices.lights.lights[deviceId] or devices.kasa.kasa[deviceId]
      // So we need to look for the deviceType key within the config
      if (deviceTypeConfig[deviceType] && deviceTypeConfig[deviceType][deviceId]) {
        return {
          id: deviceId,
          type: deviceType,
          ...deviceTypeConfig[deviceType][deviceId]
        };
      }
    }
    
    return null;
  }

  /**
   * Get all devices of a specific type
   * @param {string} type - Device type (lights, spotify, etc.)
   * @returns {Array} Array of device configurations
   */
  getDevicesByType(type) {
    const devices = this.loadAll().devices;
    
    if (!devices[type]) {
      return [];
    }

    return Object.entries(devices[type]).map(([id, config]) => ({
      id,
      type,
      ...config
    }));
  }

  /**
   * Get room configuration with resolved device details
   * @param {string} roomId - Room identifier
   * @returns {Object|null} Room configuration with device details
   */
  getRoom(roomId) {
    const rooms = this.load('rooms.yaml').rooms;
    
    if (!rooms[roomId]) {
      return null;
    }

    const room = { ...rooms[roomId], id: roomId };
    
    // Resolve device details
    room.devices = room.devices.map(deviceRef => {
      const deviceConfig = this.getDevice(deviceRef.id);
      return deviceConfig ? { ...deviceRef, ...deviceConfig } : deviceRef;
    });

    return room;
  }

  /**
   * Get all rooms with resolved device details
   * @returns {Array} Array of room configurations
   */
  getAllRooms() {
    const rooms = this.load('rooms.yaml').rooms;
    
    return Object.keys(rooms).map(roomId => this.getRoom(roomId));
  }

  /**
   * Get scene configuration
   * @param {string} sceneId - Scene identifier
   * @returns {Object|null} Scene configuration
   */
  getScene(sceneId) {
    try {
      const scene = this.load(`scenes/${sceneId}.yaml`);
      return { id: sceneId, ...scene };
    } catch (error) {
      return null;
    }
  }

  /**
   * Watch configuration files for changes
   * @param {string} configPath - Path to watch
   * @param {Function} callback - Callback function when file changes
   */
  watch(configPath, callback) {
    const fullPath = path.join(this.configDir, configPath);
    
    if (this.watchers.has(fullPath)) {
      return; // Already watching
    }

    const watcher = fs.watchFile(fullPath, (curr, prev) => {
      // Clear cache for this file
      this.cache.delete(fullPath);
      
      if (callback) {
        callback(configPath, curr, prev);
      }
    });

    this.watchers.set(fullPath, watcher);
  }

  /**
   * Stop watching a configuration file
   * @param {string} configPath - Path to stop watching
   */
  unwatch(configPath) {
    const fullPath = path.join(this.configDir, configPath);
    
    if (this.watchers.has(fullPath)) {
      fs.unwatchFile(fullPath);
      this.watchers.delete(fullPath);
    }
  }

  /**
   * Clear all cached configurations
   */
  clearCache() {
    this.cache.clear();
  }

  /**
   * Validate configuration structure
   * @returns {Object} Validation result with errors if any
   */
  validate() {
    const errors = [];
    
    try {
      const config = this.loadAll();
      
      // Validate required sections
      if (!config.app) errors.push('Missing app configuration');
      if (!config.rooms) errors.push('Missing rooms configuration');
      if (!config.devices) errors.push('Missing devices configuration');
      
      // Validate room device references
      if (config.rooms && config.rooms.rooms) {
        Object.entries(config.rooms.rooms).forEach(([roomId, room]) => {
          if (room.devices) {
            room.devices.forEach(deviceRef => {
              const device = this.getDevice(deviceRef.id);
              if (!device) {
                errors.push(`Room ${roomId} references unknown device: ${deviceRef.id}`);
              }
            });
          }
        });
      }
      
    } catch (error) {
      errors.push(`Configuration loading error: ${error.message}`);
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }
}

module.exports = ConfigLoader;

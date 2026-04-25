const LightsAdapter = require('./lights-adapter');
const SpotifyAdapter = require('./spotify-adapter');
const KasaAdapter = require('./kasa-adapter');

/**
 * Adapter Manager - Manages all device adapters and provides a unified interface
 */
class AdapterManager {
  constructor(configLoader, logger) {
    this.configLoader = configLoader;
    this.logger = logger;
    this.adapters = new Map();
    this.adapterTypes = {
      lights: LightsAdapter,
      spotify: SpotifyAdapter,
      kasa: KasaAdapter
    };
  }

  /**
   * Initialize all adapters based on configuration
   * @returns {Promise<Object>} Initialization results
   */
  async initializeAll() {
    const results = {
      success: [],
      failed: [],
      total: 0
    };

    try {
      const config = this.configLoader.loadAll();
      
      // Initialize adapters for each device type
      for (const [deviceType, devices] of Object.entries(config.devices)) {
        if (this.adapterTypes[deviceType]) {
          for (const [deviceId, deviceConfig] of Object.entries(devices[deviceType] || {})) {
            results.total++;
            
            try {
              const adapter = await this.createAdapter(deviceType, deviceId, deviceConfig);
              const initialized = await adapter.initialize();
              
              if (initialized) {
                this.adapters.set(deviceId, adapter);
                results.success.push(deviceId);
                
                if (this.logger) {
                  this.logger.info(`Successfully initialized adapter for ${deviceId}`);
                }
              } else {
                results.failed.push({ deviceId, error: 'Initialization failed' });
              }
            } catch (error) {
              results.failed.push({ deviceId, error: error.message });
              
              if (this.logger) {
                this.logger.error(`Failed to initialize adapter for ${deviceId}:`, error);
              }
            }
          }
        }
      }
    } catch (error) {
      if (this.logger) {
        this.logger.error('Failed to initialize adapters:', error);
      }
      throw error;
    }

    return results;
  }

  /**
   * Create an adapter for a specific device
   * @param {string} deviceType - Type of device (lights, spotify, etc.)
   * @param {string} deviceId - Device identifier
   * @param {Object} deviceConfig - Device configuration
   * @returns {Promise<BaseAdapter>} Created adapter
   */
  async createAdapter(deviceType, deviceId, deviceConfig) {
    const AdapterClass = this.adapterTypes[deviceType];
    
    if (!AdapterClass) {
      throw new Error(`No adapter available for device type: ${deviceType}`);
    }

    const fullConfig = {
      id: deviceId,
      type: deviceType,
      ...deviceConfig
    };

    return new AdapterClass(fullConfig, this.logger);
  }

  /**
   * Get an adapter by device ID
   * @param {string} deviceId - Device identifier
   * @returns {BaseAdapter|null} Adapter instance or null if not found
   */
  getAdapter(deviceId) {
    return this.adapters.get(deviceId) || null;
  }

  /**
   * Get all adapters of a specific type
   * @param {string} deviceType - Device type
   * @returns {Array<BaseAdapter>} Array of adapters
   */
  getAdaptersByType(deviceType) {
    const adapters = [];
    
    for (const [deviceId, adapter] of this.adapters) {
      if (adapter.deviceConfig.type === deviceType) {
        adapters.push(adapter);
      }
    }
    
    return adapters;
  }

  /**
   * Execute a command on a specific device
   * @param {string} deviceId - Device identifier
   * @param {string} command - Command name
   * @param {Object} params - Command parameters
   * @returns {Promise<Object>} Command result
   */
  async executeCommand(deviceId, command, params = {}) {
    if (this.logger) {
      this.logger.info(`[ADAPTER MANAGER] executeCommand called for device: ${deviceId}, command: ${command}, params:`, params);
    }

    const adapter = this.getAdapter(deviceId);
    
    if (!adapter) {
      if (this.logger) {
        this.logger.error(`[ADAPTER MANAGER] No adapter found for device: ${deviceId}`);
      }
      throw new Error(`No adapter found for device: ${deviceId}`);
    }

    if (this.logger) {
      this.logger.info(`[ADAPTER MANAGER] Found adapter for ${deviceId}, type: ${adapter.constructor.name}`);
    }

    const result = await adapter.executeCommand(command, params);
    
    if (this.logger) {
      this.logger.info(`[ADAPTER MANAGER] Command result for ${deviceId}:`, result);
    }

    return result;
  }

  /**
   * Execute a command on multiple devices
   * @param {Array<string>} deviceIds - Array of device identifiers
   * @param {string} command - Command name
   * @param {Object} params - Command parameters
   * @returns {Promise<Object>} Batch command results
   */
  async executeCommandBatch(deviceIds, command, params = {}) {
    const results = {
      success: [],
      failed: [],
      total: deviceIds.length
    };

    const promises = deviceIds.map(async (deviceId) => {
      try {
        const result = await this.executeCommand(deviceId, command, params);
        results.success.push({ deviceId, result });
      } catch (error) {
        results.failed.push({ deviceId, error: error.message });
      }
    });

    await Promise.allSettled(promises);
    return results;
  }

  /**
   * Execute a command on all devices in a room
   * @param {string} roomId - Room identifier
   * @param {string} command - Command name
   * @param {Object} params - Command parameters
   * @returns {Promise<Object>} Room command results
   */
  async executeRoomCommand(roomId, command, params = {}) {
    const room = this.configLoader.getRoom(roomId);
    
    if (!room) {
      throw new Error(`Room not found: ${roomId}`);
    }

    const deviceIds = room.devices.map(device => device.id);
    return await this.executeCommandBatch(deviceIds, command, params);
  }

  /**
   * Execute a command on devices of a specific type in a room
   * @param {string} roomId - Room identifier
   * @param {string} deviceType - Device type to target
   * @param {string} command - Command name
   * @param {Object} params - Command parameters
   * @returns {Promise<Object>} Filtered room command results
   */
  async executeRoomCommandByType(roomId, deviceType, command, params = {}) {
    const room = this.configLoader.getRoom(roomId);
    
    if (!room) {
      throw new Error(`Room not found: ${roomId}`);
    }

    const deviceIds = room.devices
      .filter(device => device.type === deviceType)
      .map(device => device.id);

    if (deviceIds.length === 0) {
      return {
        success: [],
        failed: [],
        total: 0,
        message: `No ${deviceType} devices found in room ${roomId}`
      };
    }

    return await this.executeCommandBatch(deviceIds, command, params);
  }

  /**
   * Get status of a specific device
   * @param {string} deviceId - Device identifier
   * @returns {Promise<Object>} Device status
   */
  async getDeviceStatus(deviceId) {
    const adapter = this.getAdapter(deviceId);
    
    if (!adapter) {
      throw new Error(`No adapter found for device: ${deviceId}`);
    }

    return await adapter.getStatus();
  }

  /**
   * Get status of all devices in a room
   * @param {string} roomId - Room identifier
   * @returns {Promise<Object>} Room status
   */
  async getRoomStatus(roomId) {
    const room = this.configLoader.getRoom(roomId);
    
    if (!room) {
      throw new Error(`Room not found: ${roomId}`);
    }

    const deviceStatuses = await Promise.allSettled(
      room.devices.map(async (device) => {
        try {
          const status = await this.getDeviceStatus(device.id);
          return { deviceId: device.id, status, success: true };
        } catch (error) {
          return { deviceId: device.id, error: error.message, success: false };
        }
      })
    );

    return {
      roomId,
      roomName: room.name,
      devices: deviceStatuses.map(result => result.value || result.reason)
    };
  }

  /**
   * Get status of all devices
   * @returns {Promise<Object>} All device statuses
   */
  async getAllDeviceStatuses() {
    const statuses = {};
    
    for (const [deviceId, adapter] of this.adapters) {
      try {
        statuses[deviceId] = await adapter.getStatus();
      } catch (error) {
        statuses[deviceId] = {
          error: error.message,
          online: false
        };
      }
    }
    
    return statuses;
  }

  /**
   * Test connectivity of all adapters
   * @returns {Promise<Object>} Connection test results
   */
  async testAllConnections() {
    const results = {
      online: [],
      offline: [],
      total: this.adapters.size
    };

    for (const [deviceId, adapter] of this.adapters) {
      try {
        const testResult = await adapter.testConnection();
        
        if (testResult.success) {
          results.online.push({ deviceId, ...testResult });
        } else {
          results.offline.push({ deviceId, ...testResult });
        }
      } catch (error) {
        results.offline.push({
          deviceId,
          success: false,
          error: error.message
        });
      }
    }

    return results;
  }

  /**
   * Clean up all adapters
   * @returns {Promise<void>}
   */
  async cleanup() {
    const cleanupPromises = Array.from(this.adapters.values()).map(adapter => 
      adapter.cleanup().catch(error => {
        if (this.logger) {
          this.logger.error(`Error cleaning up adapter ${adapter.deviceConfig.id}:`, error);
        }
      })
    );

    await Promise.allSettled(cleanupPromises);
    this.adapters.clear();
  }

  /**
   * Get information about all managed adapters
   * @returns {Object} Adapter information
   */
  getAdapterInfo() {
    const info = {
      total: this.adapters.size,
      byType: {},
      devices: {}
    };

    for (const [deviceId, adapter] of this.adapters) {
      const deviceInfo = adapter.getDeviceInfo();
      const deviceType = deviceInfo.type;
      
      // Count by type
      if (!info.byType[deviceType]) {
        info.byType[deviceType] = 0;
      }
      info.byType[deviceType]++;
      
      // Store device info
      info.devices[deviceId] = deviceInfo;
    }

    return info;
  }
}

module.exports = AdapterManager;

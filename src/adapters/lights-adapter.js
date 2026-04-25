const BaseAdapter = require('./base-adapter');

/**
 * Lights adapter for interfacing with smart lights
 * This adapter handles various types of smart bulbs and LED strips
 */
class LightsAdapter extends BaseAdapter {
  constructor(deviceConfig, logger) {
    super(deviceConfig, logger);
    this.currentState = {
      power: false,
      brightness: deviceConfig.settings?.default_brightness || 80,
      color: deviceConfig.settings?.default_color || '#ffffff',
      temperature: deviceConfig.settings?.default_temperature || 3000
    };
  }

  /**
   * Initialize the lights adapter
   * @returns {Promise<boolean>} Success status
   */
  async initialize() {
    try {
      // TODO: Replace with actual module initialization when submodule is added
      // const LightsModule = require('../modules/lights-module');
      // this.lightsModule = new LightsModule(this.deviceConfig);
      // await this.lightsModule.connect();
      
      // For now, simulate successful connection
      this.connected = true;
      
      if (this.logger) {
        this.logger.info(`Lights adapter initialized for device: ${this.deviceConfig.id}`);
      }
      
      return true;
    } catch (error) {
      this.handleError(error, 'initialize');
      return false;
    }
  }

  /**
   * Get current light status
   * @returns {Promise<Object>} Light status
   */
  async getStatus() {
    try {
      // TODO: Replace with actual module call
      // const status = await this.lightsModule.getStatus();
      
      // For now, return simulated status
      return {
        ...this.currentState,
        device_id: this.deviceConfig.id,
        name: this.deviceConfig.name,
        online: this.connected,
        last_updated: new Date().toISOString()
      };
    } catch (error) {
      this.handleError(error, 'getStatus');
      throw error;
    }
  }

  /**
   * Execute a command on the light
   * @param {string} command - Command name (power, brightness, color, temperature)
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
        case 'power':
          result = await this.setPower(params.state);
          break;
          
        case 'brightness':
          result = await this.setBrightness(params.level);
          break;
          
        case 'color':
          result = await this.setColor(params.color);
          break;
          
        case 'temperature':
          result = await this.setTemperature(params.temperature);
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
   * Set device power state
   * @param {boolean} state - Power state (true = on, false = off)
   * @returns {Promise<Object>} Result
   */
  async setPower(state) {
    console.log("HEEEELELELELELELE - LightsAdapter setPower called for", this.deviceConfig.id, "with state:", state);
    
    // TODO: Replace with actual module call
    // await this.lightsModule.setPower(state);
    
    this.currentState.power = state;
    
    if (this.logger) {
      this.logger.info(`Light ${this.deviceConfig.id} power set to: ${state ? 'ON' : 'OFF'}`);
    }
    
    return { power: state };
  }

  /**
   * Set light brightness
   * @param {number} level - Brightness level (0-100)
   * @returns {Promise<Object>} Result
   */
  async setBrightness(level) {
    const minBrightness = this.deviceConfig.settings?.min_brightness || 1;
    const maxBrightness = this.deviceConfig.settings?.max_brightness || 100;
    
    if (level < minBrightness || level > maxBrightness) {
      throw new Error(`Brightness must be between ${minBrightness} and ${maxBrightness}`);
    }

    // TODO: Replace with actual module call
    // await this.lightsModule.setBrightness(level);
    
    this.currentState.brightness = level;
    
    if (this.logger) {
      this.logger.info(`Light ${this.deviceConfig.id} brightness set to: ${level}%`);
    }
    
    return { brightness: level };
  }

  /**
   * Set light color
   * @param {string} color - Color in hex format (#ffffff)
   * @returns {Promise<Object>} Result
   */
  async setColor(color) {
    if (!this.deviceConfig.capabilities?.includes('color')) {
      throw new Error('Color control not supported by this device');
    }

    // Validate hex color format
    if (!/^#[0-9A-F]{6}$/i.test(color)) {
      throw new Error('Color must be in hex format (#ffffff)');
    }

    // TODO: Replace with actual module call
    // await this.lightsModule.setColor(color);
    
    this.currentState.color = color;
    
    if (this.logger) {
      this.logger.info(`Light ${this.deviceConfig.id} color set to: ${color}`);
    }
    
    return { color };
  }

  /**
   * Set light color temperature
   * @param {number} temperature - Color temperature in Kelvin
   * @returns {Promise<Object>} Result
   */
  async setTemperature(temperature) {
    if (!this.deviceConfig.capabilities?.includes('temperature')) {
      throw new Error('Temperature control not supported by this device');
    }

    // Validate temperature range (typical range for smart bulbs)
    if (temperature < 2000 || temperature > 6500) {
      throw new Error('Temperature must be between 2000K and 6500K');
    }

    // TODO: Replace with actual module call
    // await this.lightsModule.setTemperature(temperature);
    
    this.currentState.temperature = temperature;
    
    if (this.logger) {
      this.logger.info(`Light ${this.deviceConfig.id} temperature set to: ${temperature}K`);
    }
    
    return { temperature };
  }

  /**
   * Validate light-specific commands
   * @param {string} command - Command name
   * @param {Object} params - Parameters to validate
   * @returns {Object} Validation result
   */
  validateCommand(command, params) {
    const baseValidation = super.validateCommand(command, params);
    if (!baseValidation.valid) {
      return baseValidation;
    }

    // Additional light-specific validation
    switch (command) {
      case 'power':
        if (typeof params.state !== 'boolean') {
          return { valid: false, error: 'Power state must be boolean' };
        }
        break;
        
      case 'brightness':
        if (typeof params.level !== 'number' || params.level < 0 || params.level > 100) {
          return { valid: false, error: 'Brightness level must be a number between 0 and 100' };
        }
        break;
        
      case 'color':
        if (!params.color || typeof params.color !== 'string') {
          return { valid: false, error: 'Color parameter is required and must be a string' };
        }
        break;
        
      case 'temperature':
        if (typeof params.temperature !== 'number') {
          return { valid: false, error: 'Temperature must be a number' };
        }
        break;
    }

    return { valid: true };
  }

  /**
   * Get light-specific device information
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

module.exports = LightsAdapter;

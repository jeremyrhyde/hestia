const BaseAdapter = require('./base-adapter');
const { spawn } = require('child_process');
const path = require('path');

/**
 * Kasa adapter for interfacing with TP-Link Kasa smart devices
 * Maintains persistent Python bridge process with bulb instances
 */
class KasaAdapter extends BaseAdapter {
  constructor(deviceConfig, logger) {
    super(deviceConfig, logger);
    this.currentState = {
      power: false,
      brightness: deviceConfig.settings?.default_brightness || 100,
      color: deviceConfig.settings?.default_color || '#ffffff',
      temperature: deviceConfig.settings?.default_temperature || 2700,
      online: false
    };
    this.modulePath = path.join(__dirname, '../modules/kasa-module');
    this.deviceType = deviceConfig.type || 'bulb'; // 'bulb' or 'plug'
    this.bridgeProcess = null;
    this.isInitialized = false;
  }

  /**
   * Initialize the Kasa adapter with persistent bridge
   * @returns {Promise<boolean>} Success status
   */
  async initialize() {
    try {
      // Check if Python bridge exists
      const fs = require('fs');
      const bridgePath = path.join(this.modulePath, 'kasa_bridge.py');
      
      if (!fs.existsSync(bridgePath)) {
        throw new Error(`Kasa bridge not found at ${bridgePath}`);
      }
      
      // Start persistent Python bridge process
      await this.startBridge();
      
      // Initialize the bulb instance in the bridge
      const deviceAddress = this.deviceConfig.connection?.address;
      if (!deviceAddress) {
        throw new Error('Device address not configured');
      }
      
      const initResult = await this.sendBridgeCommand({
        action: 'initialize',
        device_id: this.deviceConfig.id,
        ip_address: deviceAddress,
        name: this.deviceConfig.name
      });
      
      if (initResult.success) {
        this.connected = true;
        this.isInitialized = true;
        
        if (this.logger) {
          this.logger.info(`Kasa adapter initialized for device: ${this.deviceConfig.id}`);
        }
        
        return true;
      } else {
        if (this.logger) {
          this.logger.warn(`Kasa device ${this.deviceConfig.id} initialization failed: ${initResult.error}, but adapter registered`);
        }
        this.connected = false;
        return true; // Still return true to allow the adapter to be registered
      }
      
    } catch (error) {
      this.handleError(error, 'initialize');
      return false;
    }
  }

  /**
   * Start the persistent Python bridge process
   * @returns {Promise<void>}
   */
  async startBridge() {
    if (this.bridgeProcess) {
      return; // Already started
    }

    return new Promise((resolve, reject) => {
      this.bridgeProcess = spawn('python3', ['kasa_bridge.py'], {
        cwd: this.modulePath,
        stdio: ['pipe', 'pipe', 'pipe']
      });

      this.bridgeProcess.on('error', (error) => {
        if (this.logger) {
          this.logger.error(`Bridge process error: ${error.message}`);
        }
        reject(error);
      });

      this.bridgeProcess.on('close', (code) => {
        if (this.logger) {
          this.logger.warn(`Bridge process closed with code ${code}`);
        }
        this.bridgeProcess = null;
        this.isInitialized = false;
      });

      // Give the process a moment to start
      setTimeout(() => {
        if (this.bridgeProcess && !this.bridgeProcess.killed) {
          resolve();
        } else {
          reject(new Error('Failed to start bridge process'));
        }
      }, 1000);
    });
  }

  /**
   * Send a command to the Python bridge
   * @param {Object} command - Command object
   * @returns {Promise<Object>} Response from bridge
   */
  async sendBridgeCommand(command) {
    if (!this.bridgeProcess) {
      throw new Error('Bridge process not started');
    }

    console.log("HEEEELELELELELELE");

    return new Promise((resolve, reject) => {
      let responseReceived = false;
      
      const timeout = setTimeout(() => {
        if (!responseReceived) {
          responseReceived = true;
          reject(new Error('Bridge command timeout'));
        }
      }, 10000);

      const onData = (data) => {
        if (responseReceived) return;
        
        try {
          const response = JSON.parse(data.toString().trim());
          responseReceived = true;
          clearTimeout(timeout);
          this.bridgeProcess.stdout.removeListener('data', onData);
          resolve(response);
        } catch (error) {
          if (!responseReceived) {
            responseReceived = true;
            clearTimeout(timeout);
            this.bridgeProcess.stdout.removeListener('data', onData);
            reject(new Error(`Invalid JSON response: ${data.toString()}`));
          }
        }
      };

      this.bridgeProcess.stdout.on('data', onData);
      
      // Send command
      this.bridgeProcess.stdin.write(JSON.stringify(command) + '\n');
    });
  }

  /**
   * Execute a Python command in the kasa module
   * @param {Array} args - Command arguments
   * @param {string} script - Python script to run (default: discover.py)
   * @returns {Promise<Object>} Command result
   */
  async executePythonCommand(args = [], script = 'discover.py') {
    return new Promise((resolve) => {
      const pythonProcess = spawn('python3', [script, ...args], {
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
   * Get current device status using bridge
   * @returns {Promise<Object>} Device status
   */
  async getStatus() {
    try {
      if (!this.isInitialized) {
        return {
          ...this.currentState,
          device_id: this.deviceConfig.id,
          device_name: this.deviceConfig.name,
          device_type: this.deviceType,
          online: false,
          error: 'Device not initialized',
          last_updated: new Date().toISOString()
        };
      }

      const result = await this.sendBridgeCommand({
        action: 'execute',
        device_id: this.deviceConfig.id,
        command: 'get_status'
      });
      
      if (result.success && result.status) {
        this.currentState = { ...this.currentState, ...result.status };
        this.connected = true;
      }

      return {
        ...this.currentState,
        device_id: this.deviceConfig.id,
        device_name: this.deviceConfig.name,
        device_type: this.deviceType,
        online: this.connected,
        last_updated: new Date().toISOString()
      };
    } catch (error) {
      this.handleError(error, 'getStatus');
      return {
        ...this.currentState,
        device_id: this.deviceConfig.id,
        device_name: this.deviceConfig.name,
        device_type: this.deviceType,
        online: false,
        error: error.message,
        last_updated: new Date().toISOString()
      };
    }
  }

  /**
   * Execute a command on the Kasa device
   * @param {string} command - Command name (power, brightness, color, etc.)
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
   * Set device power state using bridge
   * @param {boolean} state - Power state (true = on, false = off)
   * @returns {Promise<Object>} Result
   */
  async setPower(state) {
    if (this.logger) {
      this.logger.info(`[KASA ADAPTER] setPower called for ${this.deviceConfig.id} with state: ${state}`);
    }

    if (!this.isInitialized) {
      if (this.logger) {
        this.logger.error(`[KASA ADAPTER] Device ${this.deviceConfig.id} not initialized`);
      }
      throw new Error('Device not initialized');
    }

    const command = state ? 'turn_on' : 'turn_off';
    
    if (this.logger) {
      this.logger.info(`[KASA ADAPTER] Sending bridge command: ${command} to device ${this.deviceConfig.id}`);
    }
    
    try {
      const result = await this.sendBridgeCommand({
        action: 'execute',
        device_id: this.deviceConfig.id,
        command: command
      });
      
      if (this.logger) {
        this.logger.info(`[KASA ADAPTER] Bridge command result for ${this.deviceConfig.id}:`, result);
      }
      
      if (result.success) {
        this.currentState.power = state;
        
        if (this.logger) {
          this.logger.info(`[KASA ADAPTER] Successfully set ${this.deviceConfig.id} power to: ${state ? 'ON' : 'OFF'}`);
        }
        
        return { power: state, success: true };
      } else {
        // Check if this is a communication error (device not found)
        const isCommError = result.error && result.error.includes('Communication error');
        
        if (isCommError) {
          // Device not found - fall back to simulation mode
          if (this.logger) {
            this.logger.warn(`[KASA ADAPTER] Device ${this.deviceConfig.id} not found on network, using simulation mode`);
          }
          
          this.currentState.power = state;
          this.currentState.online = false; // Mark as offline but functional
          
          return { 
            power: state, 
            success: true, 
            simulated: true,
            message: `Device ${this.deviceConfig.id} simulated (not found on network)`
          };
        } else {
          // Other error - report failure
          if (this.logger) {
            this.logger.error(`[KASA ADAPTER] Failed to set ${this.deviceConfig.id} power: ${result.error || 'Unknown error'}`);
          }
          
          return { power: state, success: false, error: result.error };
        }
      }
    } catch (error) {
      if (this.logger) {
        this.logger.error(`[KASA ADAPTER] Bridge communication error for ${this.deviceConfig.id}:`, error);
      }
      
      // Fall back to simulation mode on bridge errors
      this.currentState.power = state;
      this.currentState.online = false;
      
      return { 
        power: state, 
        success: true, 
        simulated: true,
        message: `Device ${this.deviceConfig.id} simulated (bridge error)`
      };
    }
  }

  /**
   * Set device brightness (bulbs only)
   * @param {number} level - Brightness level (0-100)
   * @returns {Promise<Object>} Result
   */
  async setBrightness(level) {
    if (this.deviceType !== 'bulb') {
      throw new Error('Brightness control only available for bulbs');
    }

    if (level < 0 || level > 100) {
      throw new Error('Brightness must be between 0 and 100');
    }

    const deviceAddress = this.deviceConfig.connection?.address;
    if (!deviceAddress) {
      throw new Error('Device address not configured');
    }

    const result = await this.executePythonCommand(['brightness', deviceAddress, level.toString()], 'kasa_bulb.py');
    
    if (result.success) {
      this.currentState.brightness = level;
      
      if (this.logger) {
        this.logger.info(`Kasa ${this.deviceConfig.id} brightness set to: ${level}%`);
      }
    }
    
    return { brightness: level, success: result.success };
  }

  /**
   * Set device color (color bulbs only)
   * @param {string} color - Color in hex format (#RRGGBB)
   * @returns {Promise<Object>} Result
   */
  async setColor(color) {
    if (this.deviceType !== 'bulb') {
      throw new Error('Color control only available for bulbs');
    }

    if (!color.match(/^#[0-9A-Fa-f]{6}$/)) {
      throw new Error('Color must be in hex format (#RRGGBB)');
    }

    const deviceAddress = this.deviceConfig.connection?.address;
    if (!deviceAddress) {
      throw new Error('Device address not configured');
    }

    const result = await this.executePythonCommand(['color', deviceAddress, color], 'kasa_bulb.py');
    
    if (result.success) {
      this.currentState.color = color;
      
      if (this.logger) {
        this.logger.info(`Kasa ${this.deviceConfig.id} color set to: ${color}`);
      }
    }
    
    return { color, success: result.success };
  }

  /**
   * Set color temperature (bulbs only)
   * @param {number} temperature - Color temperature in Kelvin (2500-9000)
   * @returns {Promise<Object>} Result
   */
  async setTemperature(temperature) {
    if (this.deviceType !== 'bulb') {
      throw new Error('Temperature control only available for bulbs');
    }

    if (temperature < 2500 || temperature > 9000) {
      throw new Error('Temperature must be between 2500K and 9000K');
    }

    const deviceAddress = this.deviceConfig.connection?.address;
    if (!deviceAddress) {
      throw new Error('Device address not configured');
    }

    const result = await this.executePythonCommand(['temperature', deviceAddress, temperature.toString()], 'kasa_bulb.py');
    
    if (result.success) {
      this.currentState.temperature = temperature;
      
      if (this.logger) {
        this.logger.info(`Kasa ${this.deviceConfig.id} temperature set to: ${temperature}K`);
      }
    }
    
    return { temperature, success: result.success };
  }

  /**
   * Validate Kasa-specific commands
   * @param {string} command - Command name
   * @param {Object} params - Parameters to validate
   * @returns {Object} Validation result
   */
  validateCommand(command, params) {
    const baseValidation = super.validateCommand(command, params);
    if (!baseValidation.valid) {
      return baseValidation;
    }

    // Additional Kasa-specific validation
    switch (command) {
      case 'power':
        if (typeof params.state !== 'boolean') {
          return { valid: false, error: 'Power state must be boolean' };
        }
        break;
        
      case 'brightness':
        if (this.deviceType !== 'bulb') {
          return { valid: false, error: 'Brightness control only available for bulbs' };
        }
        if (typeof params.level !== 'number' || params.level < 0 || params.level > 100) {
          return { valid: false, error: 'Brightness level must be a number between 0 and 100' };
        }
        break;
        
      case 'color':
        if (this.deviceType !== 'bulb') {
          return { valid: false, error: 'Color control only available for bulbs' };
        }
        if (!params.color || !params.color.match(/^#[0-9A-Fa-f]{6}$/)) {
          return { valid: false, error: 'Color must be in hex format (#RRGGBB)' };
        }
        break;
        
      case 'temperature':
        if (this.deviceType !== 'bulb') {
          return { valid: false, error: 'Temperature control only available for bulbs' };
        }
        if (typeof params.temperature !== 'number' || params.temperature < 2500 || params.temperature > 9000) {
          return { valid: false, error: 'Temperature must be a number between 2500K and 9000K' };
        }
        break;
    }

    return { valid: true };
  }

  /**
   * Get Kasa-specific device information
   * @returns {Object} Extended device info
   */
  getDeviceInfo() {
    const baseInfo = super.getDeviceInfo();
    return {
      ...baseInfo,
      deviceType: this.deviceType,
      currentState: this.currentState,
      settings: this.deviceConfig.settings,
      connection: this.deviceConfig.connection
    };
  }
}

module.exports = KasaAdapter;

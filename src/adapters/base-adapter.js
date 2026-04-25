/**
 * Base adapter class that all device adapters should extend
 * Provides a consistent interface for device communication
 */
class BaseAdapter {
  constructor(deviceConfig, logger) {
    this.deviceConfig = deviceConfig;
    this.logger = logger;
    this.connected = false;
    this.lastError = null;
  }

  /**
   * Initialize the adapter and establish connection to the device
   * @returns {Promise<boolean>} Success status
   */
  async initialize() {
    throw new Error('initialize() must be implemented by subclass');
  }

  /**
   * Check if the device is currently connected and responsive
   * @returns {Promise<boolean>} Connection status
   */
  async isConnected() {
    return this.connected;
  }

  /**
   * Get current device status/state
   * @returns {Promise<Object>} Device status object
   */
  async getStatus() {
    throw new Error('getStatus() must be implemented by subclass');
  }

  /**
   * Execute a command on the device
   * @param {string} command - Command name
   * @param {Object} params - Command parameters
   * @returns {Promise<Object>} Command result
   */
  async executeCommand(command, params = {}) {
    throw new Error('executeCommand() must be implemented by subclass');
  }

  /**
   * Get list of supported commands for this device
   * @returns {Array<string>} Array of command names
   */
  getSupportedCommands() {
    return this.deviceConfig.capabilities || [];
  }

  /**
   * Validate command parameters
   * @param {string} command - Command name
   * @param {Object} params - Parameters to validate
   * @returns {Object} Validation result
   */
  validateCommand(command, params) {
    const supportedCommands = this.getSupportedCommands();
    
    if (!supportedCommands.includes(command)) {
      return {
        valid: false,
        error: `Command '${command}' not supported by device ${this.deviceConfig.id}`
      };
    }

    return { valid: true };
  }

  /**
   * Handle errors consistently across all adapters
   * @param {Error} error - Error object
   * @param {string} context - Context where error occurred
   */
  handleError(error, context = 'unknown') {
    this.lastError = {
      message: error.message,
      context,
      timestamp: new Date().toISOString()
    };

    if (this.logger) {
      this.logger.error(`Adapter error in ${context}:`, error);
    }

    // Mark as disconnected if it's a connection error
    if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT') {
      this.connected = false;
    }
  }

  /**
   * Get the last error that occurred
   * @returns {Object|null} Last error object or null
   */
  getLastError() {
    return this.lastError;
  }

  /**
   * Clean up resources when adapter is no longer needed
   * @returns {Promise<void>}
   */
  async cleanup() {
    this.connected = false;
    this.lastError = null;
  }

  /**
   * Get device information
   * @returns {Object} Device info object
   */
  getDeviceInfo() {
    return {
      id: this.deviceConfig.id,
      name: this.deviceConfig.name,
      type: this.deviceConfig.type,
      brand: this.deviceConfig.brand,
      capabilities: this.deviceConfig.capabilities,
      connected: this.connected,
      lastError: this.lastError
    };
  }

  /**
   * Test device connectivity
   * @returns {Promise<Object>} Test result
   */
  async testConnection() {
    try {
      const status = await this.getStatus();
      return {
        success: true,
        connected: this.connected,
        status,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      this.handleError(error, 'connection_test');
      return {
        success: false,
        connected: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }
}

module.exports = BaseAdapter;

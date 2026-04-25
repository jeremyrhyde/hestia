const express = require('express');
const router = express.Router();

/**
 * GET /devices
 * Get all devices with their current status
 */
router.get('/', async (req, res) => {
  try {
    const { type } = req.query;
    
    let devices;
    if (type) {
      // Get devices of specific type
      devices = req.configLoader.getDevicesByType(type);
    } else {
      // Get all devices
      const config = req.configLoader.loadAll();
      devices = [];
      
      for (const [deviceType, deviceConfigs] of Object.entries(config.devices)) {
        const typeDevices = Object.entries(deviceConfigs[deviceType] || {}).map(([id, config]) => ({
          id,
          type: deviceType,
          ...config
        }));
        devices.push(...typeDevices);
      }
    }
    
    // Get current status for each device
    const devicesWithStatus = await Promise.all(
      devices.map(async (device) => {
        try {
          const status = await req.adapterManager.getDeviceStatus(device.id);
          return { ...device, status };
        } catch (error) {
          return { 
            ...device, 
            status: { 
              error: error.message, 
              online: false 
            } 
          };
        }
      })
    );
    
    res.json({
      devices: devicesWithStatus,
      total: devicesWithStatus.length
    });
    
  } catch (error) {
    req.logger.error('Error getting devices:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /devices/:deviceId
 * Get specific device information and status
 */
router.get('/:deviceId', async (req, res) => {
  try {
    const { deviceId } = req.params;
    
    // Get device configuration
    const device = req.configLoader.getDevice(deviceId);
    if (!device) {
      return res.status(404).json({ error: 'Device not found' });
    }
    
    // Get current status
    try {
      const status = await req.adapterManager.getDeviceStatus(deviceId);
      res.json({ ...device, status });
    } catch (error) {
      res.json({ 
        ...device, 
        status: { 
          error: error.message, 
          online: false 
        } 
      });
    }
    
  } catch (error) {
    req.logger.error(`Error getting device ${req.params.deviceId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /devices/:deviceId/command
 * Execute a command on a specific device
 */
router.post('/:deviceId/command', async (req, res) => {
  try {
    const { deviceId } = req.params;
    const { command, params = {} } = req.body;
    
    if (req.logger) {
      req.logger.info(`[DEVICE ROUTE] POST /:deviceId/command called for device: ${deviceId}, command: ${command}, params:`, params);
    }
    
    if (!command) {
      return res.status(400).json({ error: 'Command is required' });
    }
    
    // Execute command
    if (req.logger) {
      req.logger.info(`[DEVICE ROUTE] Calling adapterManager.executeCommand for ${deviceId}`);
    }
    
    const result = await req.adapterManager.executeCommand(deviceId, command, params);
    
    if (req.logger) {
      req.logger.info(`[DEVICE ROUTE] Command execution result for ${deviceId}:`, result);
    }
    
    // Log the operation
    req.logger.logDeviceOperation(deviceId, command, result);
    
    // Broadcast status update via WebSocket
    try {
      const status = await req.adapterManager.getDeviceStatus(deviceId);
      req.io.emit('device:status:update', { deviceId, status });
    } catch (statusError) {
      req.logger.warn('Failed to broadcast device status update:', statusError);
    }
    
    res.json(result);
    
  } catch (error) {
    if (req.logger && req.logger.error) {
      req.logger.error(`[DEVICE ROUTE] Device command failed for ${req.params.deviceId}:`, error);
    }
    res.status(400).json({ error: error.message });
  }
});

/**
 * GET /devices/:deviceId/status
 * Get current status of a specific device
 */
router.get('/:deviceId/status', async (req, res) => {
  try {
    const { deviceId } = req.params;
    const status = await req.adapterManager.getDeviceStatus(deviceId);
    res.json({ deviceId, status });
    
  } catch (error) {
    req.logger.error(`Error getting device status ${req.params.deviceId}:`, error);
    res.status(404).json({ error: error.message });
  }
});

/**
 * GET /devices/:deviceId/capabilities
 * Get device capabilities and supported commands
 */
router.get('/:deviceId/capabilities', async (req, res) => {
  try {
    const { deviceId } = req.params;
    
    const adapter = req.adapterManager.getAdapter(deviceId);
    if (!adapter) {
      return res.status(404).json({ error: 'Device not found' });
    }
    
    const capabilities = adapter.getSupportedCommands();
    const deviceInfo = adapter.getDeviceInfo();
    
    res.json({
      deviceId,
      capabilities,
      deviceInfo: {
        type: deviceInfo.type,
        brand: deviceInfo.brand,
        name: deviceInfo.name
      }
    });
    
  } catch (error) {
    req.logger.error(`Error getting device capabilities ${req.params.deviceId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /devices/:deviceId/test
 * Test device connectivity
 */
router.post('/:deviceId/test', async (req, res) => {
  try {
    const { deviceId } = req.params;
    
    const adapter = req.adapterManager.getAdapter(deviceId);
    if (!adapter) {
      return res.status(404).json({ error: 'Device not found' });
    }
    
    const testResult = await adapter.testConnection();
    res.json(testResult);
    
  } catch (error) {
    req.logger.error(`Error testing device ${req.params.deviceId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /devices/batch/command
 * Execute a command on multiple devices
 */
router.post('/batch/command', async (req, res) => {
  try {
    const { deviceIds, command, params = {} } = req.body;
    
    if (!deviceIds || !Array.isArray(deviceIds) || deviceIds.length === 0) {
      return res.status(400).json({ error: 'deviceIds array is required' });
    }
    
    if (!command) {
      return res.status(400).json({ error: 'Command is required' });
    }
    
    // Execute batch command
    const result = await req.adapterManager.executeCommandBatch(deviceIds, command, params);
    
    // Log the operation
    if (req.logger && req.logger.info) {
      req.logger.info('Batch Device Operation', {
        deviceIds,
        command,
        params,
        result: {
          success: result.success.length,
          failed: result.failed.length,
          total: result.total
        }
      });
    }
    
    // Broadcast status updates for successful devices
    for (const successResult of result.success) {
      try {
        const status = await req.adapterManager.getDeviceStatus(successResult.deviceId);
        req.io.emit('device:status:update', { deviceId: successResult.deviceId, status });
      } catch (statusError) {
        req.logger.warn(`Failed to broadcast status update for ${successResult.deviceId}:`, statusError);
      }
    }
    
    res.json(result);
    
  } catch (error) {
    req.logger.error('Error executing batch device command:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /devices/types
 * Get available device types
 */
router.get('/types', (req, res) => {
  try {
    const config = req.configLoader.loadAll();
    const types = Object.keys(config.devices);
    
    const typeInfo = types.map(type => {
      const devices = req.configLoader.getDevicesByType(type);
      return {
        type,
        count: devices.length,
        devices: devices.map(d => ({ id: d.id, name: d.name }))
      };
    });
    
    res.json({ types: typeInfo });
    
  } catch (error) {
    req.logger.error('Error getting device types:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;

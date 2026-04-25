const express = require('express');
const router = express.Router();

/**
 * GET /status
 * Get overall system status
 */
router.get('/', async (req, res) => {
  try {
    const adapterInfo = req.adapterManager.getAdapterInfo();
    const connectionTests = await req.adapterManager.testAllConnections();
    
    const systemStatus = {
      server: {
        status: 'running',
        uptime: process.uptime(),
        timestamp: new Date().toISOString(),
        version: req.configLoader.load('app.yaml').app.version
      },
      adapters: {
        total: adapterInfo.total,
        online: connectionTests.online.length,
        offline: connectionTests.offline.length,
        byType: adapterInfo.byType
      },
      configuration: {
        valid: true,
        lastLoaded: new Date().toISOString()
      }
    };
    
    // Validate configuration
    const configValidation = req.configLoader.validate();
    systemStatus.configuration.valid = configValidation.valid;
    if (!configValidation.valid) {
      systemStatus.configuration.errors = configValidation.errors;
    }
    
    res.json(systemStatus);
    
  } catch (error) {
    req.logger.error('Error getting system status:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /status/devices
 * Get status of all devices
 */
router.get('/devices', async (req, res) => {
  try {
    const deviceStatuses = await req.adapterManager.getAllDeviceStatuses();
    
    const summary = {
      total: Object.keys(deviceStatuses).length,
      online: 0,
      offline: 0,
      byType: {}
    };
    
    // Calculate summary statistics
    Object.entries(deviceStatuses).forEach(([deviceId, status]) => {
      const device = req.configLoader.getDevice(deviceId);
      if (!device) return;
      
      const deviceType = device.type;
      
      // Count by type
      if (!summary.byType[deviceType]) {
        summary.byType[deviceType] = { total: 0, online: 0, offline: 0 };
      }
      summary.byType[deviceType].total++;
      
      // Count online/offline
      if (status.error || status.online === false) {
        summary.offline++;
        summary.byType[deviceType].offline++;
      } else {
        summary.online++;
        summary.byType[deviceType].online++;
      }
    });
    
    res.json({
      summary,
      devices: deviceStatuses,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    req.logger.error('Error getting device statuses:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /status/rooms
 * Get status of all rooms
 */
router.get('/rooms', async (req, res) => {
  try {
    const rooms = req.configLoader.getAllRooms();
    
    const roomStatuses = await Promise.all(
      rooms.map(async (room) => {
        try {
          const roomStatus = await req.adapterManager.getRoomStatus(room.id);
          
          // Calculate room summary
          const summary = {
            totalDevices: roomStatus.devices.length,
            onlineDevices: roomStatus.devices.filter(d => d.success && d.status && d.status.online !== false).length,
            deviceTypes: {}
          };
          
          roomStatus.devices.forEach(deviceStatus => {
            const device = room.devices.find(d => d.id === deviceStatus.deviceId);
            if (device) {
              const deviceType = device.type;
              if (!summary.deviceTypes[deviceType]) {
                summary.deviceTypes[deviceType] = { total: 0, online: 0 };
              }
              summary.deviceTypes[deviceType].total++;
              if (deviceStatus.success && deviceStatus.status && deviceStatus.status.online !== false) {
                summary.deviceTypes[deviceType].online++;
              }
            }
          });
          
          return {
            roomId: room.id,
            roomName: room.name,
            summary,
            status: roomStatus
          };
        } catch (error) {
          return {
            roomId: room.id,
            roomName: room.name,
            error: error.message
          };
        }
      })
    );
    
    const overallSummary = {
      totalRooms: roomStatuses.length,
      totalDevices: roomStatuses.reduce((sum, room) => sum + (room.summary?.totalDevices || 0), 0),
      onlineDevices: roomStatuses.reduce((sum, room) => sum + (room.summary?.onlineDevices || 0), 0)
    };
    
    res.json({
      summary: overallSummary,
      rooms: roomStatuses,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    req.logger.error('Error getting room statuses:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /status/adapters
 * Get detailed adapter status and connection information
 */
router.get('/adapters', async (req, res) => {
  try {
    const adapterInfo = req.adapterManager.getAdapterInfo();
    const connectionTests = await req.adapterManager.testAllConnections();
    
    const adapterDetails = {};
    
    // Get detailed information for each adapter
    Object.entries(adapterInfo.devices).forEach(([deviceId, deviceInfo]) => {
      const connectionTest = [...connectionTests.online, ...connectionTests.offline]
        .find(test => test.deviceId === deviceId);
      
      adapterDetails[deviceId] = {
        ...deviceInfo,
        connectionTest: connectionTest || { success: false, error: 'No test performed' }
      };
    });
    
    res.json({
      summary: {
        total: adapterInfo.total,
        byType: adapterInfo.byType,
        online: connectionTests.online.length,
        offline: connectionTests.offline.length
      },
      adapters: adapterDetails,
      connectionTests: {
        online: connectionTests.online,
        offline: connectionTests.offline
      },
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    req.logger.error('Error getting adapter status:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /status/configuration
 * Get configuration validation status
 */
router.get('/configuration', (req, res) => {
  try {
    const validation = req.configLoader.validate();
    const config = req.configLoader.loadAll();
    
    const configStatus = {
      valid: validation.valid,
      errors: validation.errors || [],
      structure: {
        devices: {
          types: Object.keys(config.devices),
          totalDevices: Object.values(config.devices).reduce((sum, typeDevices) => {
            return sum + Object.keys(typeDevices).length;
          }, 0)
        },
        rooms: {
          total: Object.keys(config.rooms.rooms || {}).length,
          groups: Object.keys(config.rooms.room_groups || {}).length
        },
        scenes: {
          total: Object.keys(config.scenes || {}).length
        }
      },
      lastValidated: new Date().toISOString()
    };
    
    res.json(configStatus);
    
  } catch (error) {
    req.logger.error('Error getting configuration status:', error);
    res.status(500).json({ 
      valid: false,
      error: error.message,
      lastValidated: new Date().toISOString()
    });
  }
});

/**
 * POST /status/test
 * Run comprehensive system tests
 */
router.post('/test', async (req, res) => {
  try {
    const { includeDevices = true, includeConfiguration = true } = req.body;
    
    const testResults = {
      timestamp: new Date().toISOString(),
      overall: { passed: 0, failed: 0, total: 0 },
      tests: {}
    };
    
    // Test configuration
    if (includeConfiguration) {
      testResults.tests.configuration = {
        name: 'Configuration Validation',
        passed: false,
        details: {}
      };
      
      try {
        const validation = req.configLoader.validate();
        testResults.tests.configuration.passed = validation.valid;
        testResults.tests.configuration.details = validation;
        
        if (validation.valid) {
          testResults.overall.passed++;
        } else {
          testResults.overall.failed++;
        }
        testResults.overall.total++;
        
      } catch (error) {
        testResults.tests.configuration.details = { error: error.message };
        testResults.overall.failed++;
        testResults.overall.total++;
      }
    }
    
    // Test device connections
    if (includeDevices) {
      testResults.tests.deviceConnections = {
        name: 'Device Connection Tests',
        passed: false,
        details: {}
      };
      
      try {
        const connectionTests = await req.adapterManager.testAllConnections();
        testResults.tests.deviceConnections.details = connectionTests;
        testResults.tests.deviceConnections.passed = connectionTests.offline.length === 0;
        
        if (connectionTests.offline.length === 0) {
          testResults.overall.passed++;
        } else {
          testResults.overall.failed++;
        }
        testResults.overall.total++;
        
      } catch (error) {
        testResults.tests.deviceConnections.details = { error: error.message };
        testResults.overall.failed++;
        testResults.overall.total++;
      }
    }
    
    // Test WebSocket functionality
    testResults.tests.websocket = {
      name: 'WebSocket Server',
      passed: !!req.io,
      details: {
        connected: req.io ? req.io.engine.clientsCount : 0,
        enabled: !!req.io
      }
    };
    
    if (req.io) {
      testResults.overall.passed++;
    } else {
      testResults.overall.failed++;
    }
    testResults.overall.total++;
    
    // Calculate overall success rate
    testResults.overall.successRate = testResults.overall.total > 0 
      ? (testResults.overall.passed / testResults.overall.total * 100).toFixed(1) + '%'
      : '0%';
    
    req.logger.info('System Test Completed', {
      overall: testResults.overall,
      timestamp: testResults.timestamp
    });
    
    res.json(testResults);
    
  } catch (error) {
    req.logger.error('Error running system tests:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /status/health
 * Simple health check endpoint
 */
router.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

module.exports = router;

const express = require('express');
const router = express.Router();

/**
 * GET /rooms
 * Get all rooms with their devices and current status
 */
router.get('/', async (req, res) => {
  try {
    const rooms = req.configLoader.getAllRooms();
    
    // Get status for each room
    const roomsWithStatus = await Promise.all(
      rooms.map(async (room) => {
        try {
          const roomStatus = await req.adapterManager.getRoomStatus(room.id);
          return { ...room, status: roomStatus };
        } catch (error) {
          return { 
            ...room, 
            status: { 
              error: error.message,
              devices: []
            } 
          };
        }
      })
    );
    
    res.json({
      rooms: roomsWithStatus,
      total: roomsWithStatus.length
    });
    
  } catch (error) {
    req.logger.error('Error getting rooms:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /rooms/:roomId
 * Get specific room information and device status
 */
router.get('/:roomId', async (req, res) => {
  try {
    const { roomId } = req.params;
    
    // Get room configuration
    const room = req.configLoader.getRoom(roomId);
    if (!room) {
      return res.status(404).json({ error: 'Room not found' });
    }
    
    // Get room status
    try {
      const roomStatus = await req.adapterManager.getRoomStatus(roomId);
      res.json({ ...room, status: roomStatus });
    } catch (error) {
      res.json({ 
        ...room, 
        status: { 
          error: error.message,
          devices: []
        } 
      });
    }
    
  } catch (error) {
    req.logger.error(`Error getting room ${req.params.roomId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /rooms/:roomId/command
 * Execute a command on all devices in a room
 */
router.post('/:roomId/command', async (req, res) => {
  try {
    const { roomId } = req.params;
    const { command, params = {}, deviceType } = req.body;
    
    if (!command) {
      return res.status(400).json({ error: 'Command is required' });
    }
    
    // Execute room command
    let result;
    if (deviceType) {
      result = await req.adapterManager.executeRoomCommandByType(roomId, deviceType, command, params);
    } else {
      result = await req.adapterManager.executeRoomCommand(roomId, command, params);
    }
    
    // Log the operation
    req.logger.logRoomOperation(roomId, `${command}${deviceType ? ` (${deviceType})` : ''}`, result);
    
    // Broadcast room status update via WebSocket
    try {
      const roomStatus = await req.adapterManager.getRoomStatus(roomId);
      req.io.emit('room:status:update', roomStatus);
    } catch (statusError) {
      req.logger.warn('Failed to broadcast room status update:', statusError);
    }
    
    res.json(result);
    
  } catch (error) {
    req.logger.logRoomOperation(req.params.roomId, req.body.command, null, error);
    res.status(400).json({ error: error.message });
  }
});

/**
 * GET /rooms/:roomId/status
 * Get current status of all devices in a room
 */
router.get('/:roomId/status', async (req, res) => {
  try {
    const { roomId } = req.params;
    const roomStatus = await req.adapterManager.getRoomStatus(roomId);
    res.json(roomStatus);
    
  } catch (error) {
    req.logger.error(`Error getting room status ${req.params.roomId}:`, error);
    res.status(404).json({ error: error.message });
  }
});

/**
 * GET /rooms/:roomId/devices
 * Get all devices in a specific room
 */
router.get('/:roomId/devices', async (req, res) => {
  try {
    const { roomId } = req.params;
    const { type } = req.query;
    
    const room = req.configLoader.getRoom(roomId);
    if (!room) {
      return res.status(404).json({ error: 'Room not found' });
    }
    
    let devices = room.devices;
    
    // Filter by device type if specified
    if (type) {
      devices = devices.filter(device => device.type === type);
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
      roomId,
      roomName: room.name,
      devices: devicesWithStatus,
      total: devicesWithStatus.length
    });
    
  } catch (error) {
    req.logger.error(`Error getting devices for room ${req.params.roomId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /rooms/:roomId/devices/:deviceType/command
 * Execute a command on all devices of a specific type in a room
 */
router.post('/:roomId/devices/:deviceType/command', async (req, res) => {
  try {
    const { roomId, deviceType } = req.params;
    const { command, params = {} } = req.body;
    
    if (!command) {
      return res.status(400).json({ error: 'Command is required' });
    }
    
    // Execute command on devices of specific type
    const result = await req.adapterManager.executeRoomCommandByType(roomId, deviceType, command, params);
    
    // Log the operation
    req.logger.logRoomOperation(roomId, `${command} (${deviceType})`, result);
    
    // Broadcast status updates for affected devices
    if (result.success && result.success.length > 0) {
      for (const successResult of result.success) {
        try {
          const status = await req.adapterManager.getDeviceStatus(successResult.deviceId);
          req.io.emit('device:status:update', { deviceId: successResult.deviceId, status });
        } catch (statusError) {
          req.logger.warn(`Failed to broadcast status update for ${successResult.deviceId}:`, statusError);
        }
      }
    }
    
    res.json(result);
    
  } catch (error) {
    req.logger.logRoomOperation(req.params.roomId, `${req.body.command} (${req.params.deviceType})`, null, error);
    res.status(400).json({ error: error.message });
  }
});

/**
 * GET /rooms/:roomId/summary
 * Get a summary of room status (aggregated device states)
 */
router.get('/:roomId/summary', async (req, res) => {
  try {
    const { roomId } = req.params;
    
    const room = req.configLoader.getRoom(roomId);
    if (!room) {
      return res.status(404).json({ error: 'Room not found' });
    }
    
    const roomStatus = await req.adapterManager.getRoomStatus(roomId);
    
    // Aggregate device states by type
    const summary = {
      roomId,
      roomName: room.name,
      deviceCounts: {},
      onlineDevices: 0,
      totalDevices: room.devices.length,
      deviceTypes: {}
    };
    
    // Process each device status
    roomStatus.devices.forEach(deviceStatus => {
      const device = room.devices.find(d => d.id === deviceStatus.deviceId);
      if (!device) return;
      
      const deviceType = device.type;
      
      // Count devices by type
      if (!summary.deviceCounts[deviceType]) {
        summary.deviceCounts[deviceType] = 0;
      }
      summary.deviceCounts[deviceType]++;
      
      // Count online devices
      if (deviceStatus.success && deviceStatus.status && deviceStatus.status.online !== false) {
        summary.onlineDevices++;
      }
      
      // Aggregate device type status
      if (!summary.deviceTypes[deviceType]) {
        summary.deviceTypes[deviceType] = {
          total: 0,
          online: 0,
          states: {}
        };
      }
      
      summary.deviceTypes[deviceType].total++;
      
      if (deviceStatus.success && deviceStatus.status) {
        summary.deviceTypes[deviceType].online++;
        
        // Aggregate common states for lights
        if (deviceType === 'lights' && deviceStatus.status.power !== undefined) {
          if (!summary.deviceTypes[deviceType].states.power) {
            summary.deviceTypes[deviceType].states.power = { on: 0, off: 0 };
          }
          if (deviceStatus.status.power) {
            summary.deviceTypes[deviceType].states.power.on++;
          } else {
            summary.deviceTypes[deviceType].states.power.off++;
          }
        }
        
        // Aggregate common states for Spotify
        if (deviceType === 'spotify' && deviceStatus.status.playing !== undefined) {
          if (!summary.deviceTypes[deviceType].states.playing) {
            summary.deviceTypes[deviceType].states.playing = { playing: 0, paused: 0 };
          }
          if (deviceStatus.status.playing) {
            summary.deviceTypes[deviceType].states.playing.playing++;
          } else {
            summary.deviceTypes[deviceType].states.playing.paused++;
          }
        }
      }
    });
    
    res.json(summary);
    
  } catch (error) {
    req.logger.error(`Error getting room summary ${req.params.roomId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /rooms/groups
 * Get room groups configuration
 */
router.get('/groups', (req, res) => {
  try {
    const roomsConfig = req.configLoader.load('rooms.yaml');
    const groups = roomsConfig.room_groups || {};
    
    res.json({ groups });
    
  } catch (error) {
    req.logger.error('Error getting room groups:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /rooms/groups/:groupId/command
 * Execute a command on all rooms in a group
 */
router.post('/groups/:groupId/command', async (req, res) => {
  try {
    const { groupId } = req.params;
    const { command, params = {}, deviceType } = req.body;
    
    if (!command) {
      return res.status(400).json({ error: 'Command is required' });
    }
    
    const roomsConfig = req.configLoader.load('rooms.yaml');
    const group = roomsConfig.room_groups?.[groupId];
    
    if (!group) {
      return res.status(404).json({ error: 'Room group not found' });
    }
    
    // Execute command on all rooms in the group
    const results = await Promise.allSettled(
      group.rooms.map(async (roomId) => {
        try {
          let result;
          if (deviceType) {
            result = await req.adapterManager.executeRoomCommandByType(roomId, deviceType, command, params);
          } else {
            result = await req.adapterManager.executeRoomCommand(roomId, command, params);
          }
          return { roomId, success: true, result };
        } catch (error) {
          return { roomId, success: false, error: error.message };
        }
      })
    );
    
    const groupResult = {
      groupId,
      groupName: group.name,
      rooms: results.map(result => result.value || result.reason),
      summary: {
        total: results.length,
        success: results.filter(r => r.value?.success).length,
        failed: results.filter(r => !r.value?.success).length
      }
    };
    
    // Log the operation
    req.logger.info('Room Group Operation', {
      groupId,
      command,
      params,
      deviceType,
      summary: groupResult.summary
    });
    
    res.json(groupResult);
    
  } catch (error) {
    req.logger.error(`Error executing group command ${req.params.groupId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;

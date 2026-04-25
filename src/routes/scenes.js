const express = require('express');
const router = express.Router();

/**
 * GET /scenes
 * Get all available scenes
 */
router.get('/', (req, res) => {
  try {
    const config = req.configLoader.loadAll();
    const scenes = config.scenes || {};
    
    const sceneList = Object.entries(scenes).map(([sceneId, sceneConfig]) => ({
      id: sceneId,
      ...sceneConfig.scene,
      actions: Object.keys(sceneConfig.actions || {}).length,
      hasConditions: !!(sceneConfig.conditions)
    }));
    
    res.json({
      scenes: sceneList,
      total: sceneList.length
    });
    
  } catch (error) {
    req.logger.error('Error getting scenes:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /scenes/:sceneId
 * Get specific scene configuration
 */
router.get('/:sceneId', (req, res) => {
  try {
    const { sceneId } = req.params;
    const scene = req.configLoader.getScene(sceneId);
    
    if (!scene) {
      return res.status(404).json({ error: 'Scene not found' });
    }
    
    res.json(scene);
    
  } catch (error) {
    req.logger.error(`Error getting scene ${req.params.sceneId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /scenes/:sceneId/activate
 * Activate a scene (execute all its actions)
 */
router.post('/:sceneId/activate', async (req, res) => {
  try {
    const { sceneId } = req.params;
    const { force = false } = req.body;
    
    const scene = req.configLoader.getScene(sceneId);
    if (!scene) {
      return res.status(404).json({ error: 'Scene not found' });
    }
    
    // Check conditions if not forcing
    if (!force && scene.conditions) {
      const conditionCheck = checkSceneConditions(scene.conditions);
      if (!conditionCheck.valid) {
        return res.status(400).json({
          error: 'Scene conditions not met',
          conditions: conditionCheck.reasons
        });
      }
    }
    
    const results = {
      sceneId,
      sceneName: scene.scene.name,
      actions: {
        lights: { success: [], failed: [] },
        spotify: { success: [], failed: [] }
      },
      summary: { total: 0, success: 0, failed: 0 }
    };
    
    // Execute light actions
    if (scene.actions.lights) {
      for (const [deviceId, lightAction] of Object.entries(scene.actions.lights)) {
        results.summary.total++;
        
        try {
          // Convert scene action to device commands
          const commands = convertLightActionToCommands(lightAction);
          
          for (const { command, params } of commands) {
            await req.adapterManager.executeCommand(deviceId, command, params);
          }
          
          results.actions.lights.success.push({ deviceId, action: lightAction });
          results.summary.success++;
          
        } catch (error) {
          results.actions.lights.failed.push({ 
            deviceId, 
            action: lightAction, 
            error: error.message 
          });
          results.summary.failed++;
        }
      }
    }
    
    // Execute Spotify actions
    if (scene.actions.spotify) {
      for (const [deviceId, spotifyAction] of Object.entries(scene.actions.spotify)) {
        results.summary.total++;
        
        try {
          // Convert scene action to device commands
          const commands = convertSpotifyActionToCommands(spotifyAction);
          
          for (const { command, params } of commands) {
            await req.adapterManager.executeCommand(deviceId, command, params);
          }
          
          results.actions.spotify.success.push({ deviceId, action: spotifyAction });
          results.summary.success++;
          
        } catch (error) {
          results.actions.spotify.failed.push({ 
            deviceId, 
            action: spotifyAction, 
            error: error.message 
          });
          results.summary.failed++;
        }
      }
    }
    
    // Log the scene activation
    req.logger.info('Scene Activated', {
      sceneId,
      sceneName: scene.scene.name,
      summary: results.summary,
      forced: force
    });
    
    // Broadcast scene activation via WebSocket
    req.io.emit('scene:activated', {
      sceneId,
      sceneName: scene.scene.name,
      timestamp: new Date().toISOString(),
      results: results.summary
    });
    
    res.json(results);
    
  } catch (error) {
    req.logger.error(`Error activating scene ${req.params.sceneId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /scenes/:sceneId/preview
 * Preview what a scene would do without executing it
 */
router.post('/:sceneId/preview', (req, res) => {
  try {
    const { sceneId } = req.params;
    const scene = req.configLoader.getScene(sceneId);
    
    if (!scene) {
      return res.status(404).json({ error: 'Scene not found' });
    }
    
    const preview = {
      sceneId,
      sceneName: scene.scene.name,
      description: scene.scene.description,
      conditions: scene.conditions || null,
      conditionsValid: scene.conditions ? checkSceneConditions(scene.conditions).valid : true,
      actions: {
        lights: [],
        spotify: []
      },
      timing: scene.timing || null
    };
    
    // Preview light actions
    if (scene.actions.lights) {
      for (const [deviceId, lightAction] of Object.entries(scene.actions.lights)) {
        const device = req.configLoader.getDevice(deviceId);
        preview.actions.lights.push({
          deviceId,
          deviceName: device?.name || 'Unknown Device',
          action: lightAction,
          commands: convertLightActionToCommands(lightAction)
        });
      }
    }
    
    // Preview Spotify actions
    if (scene.actions.spotify) {
      for (const [deviceId, spotifyAction] of Object.entries(scene.actions.spotify)) {
        const device = req.configLoader.getDevice(deviceId);
        preview.actions.spotify.push({
          deviceId,
          deviceName: device?.name || 'Unknown Device',
          action: spotifyAction,
          commands: convertSpotifyActionToCommands(spotifyAction)
        });
      }
    }
    
    res.json(preview);
    
  } catch (error) {
    req.logger.error(`Error previewing scene ${req.params.sceneId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Helper function to check scene conditions
 */
function checkSceneConditions(conditions) {
  const result = { valid: true, reasons: [] };
  
  // Check time range
  if (conditions.time_range) {
    const now = new Date();
    const currentTime = now.toTimeString().slice(0, 5); // HH:MM format
    
    if (currentTime < conditions.time_range.start || currentTime > conditions.time_range.end) {
      result.valid = false;
      result.reasons.push(`Current time ${currentTime} is outside allowed range ${conditions.time_range.start}-${conditions.time_range.end}`);
    }
  }
  
  // Check days of week
  if (conditions.days) {
    const now = new Date();
    const dayNames = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    const currentDay = dayNames[now.getDay()];
    
    if (!conditions.days.includes(currentDay)) {
      result.valid = false;
      result.reasons.push(`Current day ${currentDay} is not in allowed days: ${conditions.days.join(', ')}`);
    }
  }
  
  return result;
}

/**
 * Helper function to convert light scene actions to device commands
 */
function convertLightActionToCommands(lightAction) {
  const commands = [];
  
  if (lightAction.power !== undefined) {
    commands.push({ command: 'power', params: { state: lightAction.power } });
  }
  
  if (lightAction.brightness !== undefined) {
    commands.push({ command: 'brightness', params: { level: lightAction.brightness } });
  }
  
  if (lightAction.color !== undefined) {
    commands.push({ command: 'color', params: { color: lightAction.color } });
  }
  
  if (lightAction.temperature !== undefined) {
    commands.push({ command: 'temperature', params: { temperature: lightAction.temperature } });
  }
  
  return commands;
}

/**
 * Helper function to convert Spotify scene actions to device commands
 */
function convertSpotifyActionToCommands(spotifyAction) {
  const commands = [];
  
  if (spotifyAction.action === 'play') {
    const params = {};
    if (spotifyAction.playlist) {
      params.playlist = spotifyAction.playlist;
    }
    if (spotifyAction.uri) {
      params.uri = spotifyAction.uri;
    }
    commands.push({ command: 'play', params });
  } else if (spotifyAction.action === 'pause') {
    commands.push({ command: 'pause', params: {} });
  }
  
  if (spotifyAction.volume !== undefined) {
    commands.push({ command: 'volume', params: { level: spotifyAction.volume } });
  }
  
  if (spotifyAction.shuffle !== undefined) {
    commands.push({ command: 'shuffle', params: { state: spotifyAction.shuffle } });
  }
  
  return commands;
}

module.exports = router;

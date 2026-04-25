const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const { createServer } = require('http');
const { Server } = require('socket.io');
require('dotenv').config();

const ConfigLoader = require('../shared/config-loader');
const AdapterManager = require('./adapters/adapter-manager');
const logger = require('./utils/logger');

// Import routes
const deviceRoutes = require('./routes/devices');
const roomRoutes = require('./routes/rooms');
const sceneRoutes = require('./routes/scenes');
const statusRoutes = require('./routes/status');

class HomeAutomationServer {
  constructor() {
    this.app = express();
    this.server = createServer(this.app);
    this.io = new Server(this.server);
    
    // Initialize core components
    this.configLoader = new ConfigLoader();
    this.adapterManager = new AdapterManager(this.configLoader, logger);
    
    this.config = null;
    this.isInitialized = false;
  }

  /**
   * Initialize the server
   */
  async initialize() {
    try {
      // Load configuration
      this.config = this.configLoader.loadAll();
      
      // Validate configuration
      const validation = this.configLoader.validate();
      if (!validation.valid) {
        throw new Error(`Configuration validation failed: ${validation.errors.join(', ')}`);
      }

      // Initialize adapters
      const adapterResults = await this.adapterManager.initializeAll();
      logger.info(`Initialized ${adapterResults.success.length}/${adapterResults.total} adapters`);
      
      if (adapterResults.failed.length > 0) {
        logger.warn('Some adapters failed to initialize:', adapterResults.failed);
      }

      // Setup middleware
      this.setupMiddleware();
      
      // Setup routes
      this.setupRoutes();
      
      // Setup WebSocket handlers
      this.setupWebSocket();
      
      // Setup error handling
      this.setupErrorHandling();
      
      this.isInitialized = true;
      logger.info('Home automation server initialized successfully');
      
    } catch (error) {
      logger.error('Failed to initialize server:', error);
      throw error;
    }
  }

  /**
   * Setup Express middleware
   */
  setupMiddleware() {
    // Security middleware
    this.app.use(helmet());
    
    // CORS configuration
    this.app.use(cors({
      origin: this.config.app.security.cors_origins,
      credentials: true
    }));
    
    // Logging middleware
    this.app.use(morgan('combined', {
      stream: { write: message => logger.info(message.trim()) }
    }));
    
    // Body parsing middleware
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true }));
    
    // Make core components available to routes
    this.app.use((req, res, next) => {
      req.configLoader = this.configLoader;
      req.adapterManager = this.adapterManager;
      req.io = this.io;
      req.logger = logger;
      next();
    });
  }

  /**
   * Setup API routes
   */
  setupRoutes() {
    const apiPrefix = this.config.app.api.prefix;
    
    // Health check endpoint
    this.app.get('/health', (req, res) => {
      res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        version: this.config.app.app.version,
        initialized: this.isInitialized
      });
    });
    
    // API routes
    this.app.use(`${apiPrefix}/devices`, deviceRoutes);
    this.app.use(`${apiPrefix}/rooms`, roomRoutes);
    this.app.use(`${apiPrefix}/scenes`, sceneRoutes);
    this.app.use(`${apiPrefix}/status`, statusRoutes);
    
    // Root endpoint
    this.app.get('/', (req, res) => {
      res.json({
        name: this.config.app.app.name,
        version: this.config.app.app.version,
        status: 'running',
        endpoints: {
          health: '/health',
          api: apiPrefix,
          websocket: '/socket.io'
        }
      });
    });
  }

  /**
   * Setup WebSocket handlers
   */
  setupWebSocket() {
    this.io.on('connection', (socket) => {
      logger.info(`Client connected: ${socket.id}`);
      
      // Send initial status
      socket.emit('server:status', {
        connected: true,
        timestamp: new Date().toISOString()
      });
      
      // Handle device commands
      socket.on('device:command', async (data) => {
        try {
          const { deviceId, command, params } = data;
          const result = await this.adapterManager.executeCommand(deviceId, command, params);
          
          socket.emit('device:command:result', {
            success: true,
            deviceId,
            command,
            result
          });
          
          // Broadcast device status update to all clients
          const status = await this.adapterManager.getDeviceStatus(deviceId);
          this.io.emit('device:status:update', { deviceId, status });
          
        } catch (error) {
          socket.emit('device:command:result', {
            success: false,
            error: error.message
          });
        }
      });
      
      // Handle room commands
      socket.on('room:command', async (data) => {
        try {
          const { roomId, command, params, deviceType } = data;
          
          let result;
          if (deviceType) {
            result = await this.adapterManager.executeRoomCommandByType(roomId, deviceType, command, params);
          } else {
            result = await this.adapterManager.executeRoomCommand(roomId, command, params);
          }
          
          socket.emit('room:command:result', {
            success: true,
            roomId,
            command,
            result
          });
          
          // Broadcast room status update
          const roomStatus = await this.adapterManager.getRoomStatus(roomId);
          this.io.emit('room:status:update', roomStatus);
          
        } catch (error) {
          socket.emit('room:command:result', {
            success: false,
            error: error.message
          });
        }
      });
      
      // Handle status requests
      socket.on('status:request', async (data) => {
        try {
          const { type, id } = data;
          let status;
          
          switch (type) {
            case 'device':
              status = await this.adapterManager.getDeviceStatus(id);
              break;
            case 'room':
              status = await this.adapterManager.getRoomStatus(id);
              break;
            case 'all':
              status = await this.adapterManager.getAllDeviceStatuses();
              break;
            default:
              throw new Error(`Unknown status type: ${type}`);
          }
          
          socket.emit('status:response', { type, id, status });
          
        } catch (error) {
          socket.emit('status:error', { error: error.message });
        }
      });
      
      // Handle disconnection
      socket.on('disconnect', () => {
        logger.info(`Client disconnected: ${socket.id}`);
      });
    });
  }

  /**
   * Setup error handling middleware
   */
  setupErrorHandling() {
    // 404 handler
    this.app.use((req, res) => {
      res.status(404).json({
        error: 'Not Found',
        message: `Route ${req.method} ${req.path} not found`,
        timestamp: new Date().toISOString()
      });
    });
    
    // Global error handler
    this.app.use((error, req, res, next) => {
      logger.error('Unhandled error:', error);
      
      res.status(error.status || 500).json({
        error: error.name || 'Internal Server Error',
        message: error.message || 'An unexpected error occurred',
        timestamp: new Date().toISOString(),
        ...(process.env.NODE_ENV === 'development' && { stack: error.stack })
      });
    });
  }

  /**
   * Start the server
   */
  async start() {
    if (!this.isInitialized) {
      await this.initialize();
    }
    
    const port = this.config.app.app.port || 3001;
    const host = this.config.app.app.host || 'localhost';
    
    return new Promise((resolve, reject) => {
      this.server.listen(port, host, (error) => {
        if (error) {
          reject(error);
        } else {
          logger.info(`Home automation server running on http://${host}:${port}`);
          resolve({ host, port });
        }
      });
    });
  }

  /**
   * Stop the server gracefully
   */
  async stop() {
    logger.info('Shutting down server...');
    
    // Close WebSocket connections
    this.io.close();
    
    // Cleanup adapters
    await this.adapterManager.cleanup();
    
    // Close HTTP server
    return new Promise((resolve) => {
      this.server.close(() => {
        logger.info('Server shut down successfully');
        resolve();
      });
    });
  }
}

// Create and export server instance
const server = new HomeAutomationServer();

// Handle process signals for graceful shutdown
process.on('SIGTERM', async () => {
  await server.stop();
  process.exit(0);
});

process.on('SIGINT', async () => {
  await server.stop();
  process.exit(0);
});

// Start server if this file is run directly
if (require.main === module) {
  server.start().catch((error) => {
    logger.error('Failed to start server:', error);
    process.exit(1);
  });
}

module.exports = server;

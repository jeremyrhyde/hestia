const winston = require('winston');
const path = require('path');
const fs = require('fs');

// Ensure logs directory exists
const logsDir = path.join(process.cwd(), 'logs');
if (!fs.existsSync(logsDir)) {
  fs.mkdirSync(logsDir, { recursive: true });
}

// Custom format for console output
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.colorize(),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    let metaStr = '';
    if (Object.keys(meta).length > 0) {
      metaStr = ' ' + JSON.stringify(meta);
    }
    return `${timestamp} [${level}]: ${message}${metaStr}`;
  })
);

// Custom format for file output
const fileFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

// Create logger instance
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: fileFormat,
  defaultMeta: { service: 'hera-home-automation' },
  transports: [
    // File transport for all logs
    new winston.transports.File({
      filename: path.join(logsDir, 'app.log'),
      maxsize: 5242880, // 5MB
      maxFiles: 5,
      tailable: true
    }),
    
    // Separate file for errors
    new winston.transports.File({
      filename: path.join(logsDir, 'error.log'),
      level: 'error',
      maxsize: 5242880, // 5MB
      maxFiles: 5,
      tailable: true
    })
  ]
});

// Add console transport in development or if explicitly enabled
if (process.env.NODE_ENV !== 'production' || process.env.LOG_CONSOLE === 'true') {
  logger.add(new winston.transports.Console({
    format: consoleFormat
  }));
}

// Add request logging helper
logger.logRequest = (req, res, next) => {
  const start = Date.now();
  
  res.on('finish', () => {
    const duration = Date.now() - start;
    const logData = {
      method: req.method,
      url: req.url,
      status: res.statusCode,
      duration: `${duration}ms`,
      ip: req.ip || req.connection.remoteAddress,
      userAgent: req.get('User-Agent')
    };
    
    if (res.statusCode >= 400) {
      logger.warn('HTTP Request', logData);
    } else {
      logger.info('HTTP Request', logData);
    }
  });
  
  next();
};

// Add device operation logging helper
logger.logDeviceOperation = (deviceId, operation, result, error = null) => {
  const logData = {
    deviceId,
    operation,
    timestamp: new Date().toISOString(),
    success: !error
  };
  
  if (error) {
    logData.error = error.message;
    logger.error('Device Operation Failed', logData);
  } else {
    logData.result = result;
    logger.info('Device Operation', logData);
  }
};

// Add room operation logging helper
logger.logRoomOperation = (roomId, operation, result, error = null) => {
  const logData = {
    roomId,
    operation,
    timestamp: new Date().toISOString(),
    success: !error
  };
  
  if (error) {
    logData.error = error.message;
    logger.error('Room Operation Failed', logData);
  } else {
    logData.result = result;
    logger.info('Room Operation', logData);
  }
};

// Add adapter logging helper
logger.logAdapterEvent = (adapterId, event, data = {}) => {
  logger.info('Adapter Event', {
    adapterId,
    event,
    timestamp: new Date().toISOString(),
    ...data
  });
};

// Handle uncaught exceptions and unhandled rejections
logger.exceptions.handle(
  new winston.transports.File({
    filename: path.join(logsDir, 'exceptions.log')
  })
);

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

module.exports = logger;

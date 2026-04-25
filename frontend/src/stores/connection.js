import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { io } from 'socket.io-client'
import { useAppStore } from './app'

export const useConnectionStore = defineStore('connection', () => {
  // State
  const socket = ref(null)
  const isConnected = ref(false)
  const connectionAttempts = ref(0)
  const maxReconnectAttempts = ref(5)
  const reconnectDelay = ref(1000)
  const lastPing = ref(null)

  // Getters
  const connectionStatus = computed(() => {
    if (isConnected.value) return 'connected'
    if (connectionAttempts.value > 0) return 'reconnecting'
    return 'disconnected'
  })

  const shouldReconnect = computed(() => {
    return connectionAttempts.value < maxReconnectAttempts.value
  })

  // Actions
  function connect() {
    if (socket.value?.connected) {
      return
    }

    try {
      socket.value = io('/', {
        transports: ['websocket', 'polling'],
        timeout: 5000,
        reconnection: true,
        reconnectionAttempts: maxReconnectAttempts.value,
        reconnectionDelay: reconnectDelay.value
      })

      setupEventListeners()
      
    } catch (error) {
      console.error('Failed to create socket connection:', error)
      handleConnectionError(error)
    }
  }

  function disconnect() {
    if (socket.value) {
      socket.value.disconnect()
      socket.value = null
    }
    isConnected.value = false
    connectionAttempts.value = 0
  }

  function setupEventListeners() {
    if (!socket.value) return

    const appStore = useAppStore()

    // Connection events
    socket.value.on('connect', () => {
      isConnected.value = true
      connectionAttempts.value = 0
      lastPing.value = new Date().toISOString()
      
      console.log('WebSocket connected')
      appStore.showSuccess('Connected', 'Real-time updates enabled')
    })

    socket.value.on('disconnect', (reason) => {
      isConnected.value = false
      console.log('WebSocket disconnected:', reason)
      
      if (reason === 'io server disconnect') {
        // Server initiated disconnect, don't reconnect automatically
        appStore.showWarning('Disconnected', 'Server closed the connection')
      } else {
        // Client-side disconnect, will attempt to reconnect
        appStore.showWarning('Connection lost', 'Attempting to reconnect...')
      }
    })

    socket.value.on('connect_error', (error) => {
      connectionAttempts.value++
      console.error('WebSocket connection error:', error)
      handleConnectionError(error)
    })

    socket.value.on('reconnect', (attemptNumber) => {
      isConnected.value = true
      connectionAttempts.value = 0
      console.log(`WebSocket reconnected after ${attemptNumber} attempts`)
      appStore.showSuccess('Reconnected', 'Connection restored')
    })

    socket.value.on('reconnect_error', (error) => {
      console.error('WebSocket reconnection error:', error)
    })

    socket.value.on('reconnect_failed', () => {
      console.error('WebSocket reconnection failed')
      appStore.showError('Connection failed', 'Unable to reconnect to server')
    })

    // Server status events
    socket.value.on('server:status', (data) => {
      console.log('Server status:', data)
      lastPing.value = data.timestamp
    })

    // Device status updates
    socket.value.on('device:status:update', (data) => {
      console.log('Device status update:', data)
      // Emit custom event for components to listen to
      window.dispatchEvent(new CustomEvent('device-status-update', { detail: data }))
    })

    // Room status updates
    socket.value.on('room:status:update', (data) => {
      console.log('Room status update:', data)
      // Emit custom event for components to listen to
      window.dispatchEvent(new CustomEvent('room-status-update', { detail: data }))
    })

    // Scene activation events
    socket.value.on('scene:activated', (data) => {
      console.log('Scene activated:', data)
      appStore.showSuccess('Scene activated', `${data.sceneName} is now active`)
      // Emit custom event for components to listen to
      window.dispatchEvent(new CustomEvent('scene-activated', { detail: data }))
    })

    // Command result events
    socket.value.on('device:command:result', (data) => {
      console.log('Device command result:', data)
      if (data.success) {
        appStore.showSuccess('Command executed', `Device ${data.deviceId} updated`)
      } else {
        appStore.showError('Command failed', data.error)
      }
    })

    socket.value.on('room:command:result', (data) => {
      console.log('Room command result:', data)
      if (data.success) {
        appStore.showSuccess('Room command executed', `${data.roomId} updated`)
      } else {
        appStore.showError('Room command failed', data.error)
      }
    })

    // Error events
    socket.value.on('status:error', (data) => {
      console.error('Status error:', data)
      appStore.showError('Status error', data.error)
    })
  }

  function handleConnectionError(error) {
    const appStore = useAppStore()
    
    if (connectionAttempts.value >= maxReconnectAttempts.value) {
      appStore.showError(
        'Connection failed', 
        'Unable to connect to home automation server. Please check your connection.'
      )
    } else if (connectionAttempts.value === 1) {
      appStore.showWarning(
        'Connection issue', 
        'Trying to connect to server...'
      )
    }
  }

  // WebSocket command methods
  function sendDeviceCommand(deviceId, command, params = {}) {
    if (!socket.value?.connected) {
      throw new Error('Not connected to server')
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Command timeout'))
      }, 10000)

      socket.value.once('device:command:result', (data) => {
        clearTimeout(timeout)
        if (data.success) {
          resolve(data.result)
        } else {
          reject(new Error(data.error))
        }
      })

      socket.value.emit('device:command', {
        deviceId,
        command,
        params
      })
    })
  }

  function sendRoomCommand(roomId, command, params = {}, deviceType = null) {
    if (!socket.value?.connected) {
      throw new Error('Not connected to server')
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Command timeout'))
      }, 15000)

      socket.value.once('room:command:result', (data) => {
        clearTimeout(timeout)
        if (data.success) {
          resolve(data.result)
        } else {
          reject(new Error(data.error))
        }
      })

      socket.value.emit('room:command', {
        roomId,
        command,
        params,
        deviceType
      })
    })
  }

  function requestStatus(type, id = null) {
    if (!socket.value?.connected) {
      throw new Error('Not connected to server')
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Status request timeout'))
      }, 5000)

      socket.value.once('status:response', (data) => {
        clearTimeout(timeout)
        resolve(data.status)
      })

      socket.value.once('status:error', (data) => {
        clearTimeout(timeout)
        reject(new Error(data.error))
      })

      socket.value.emit('status:request', { type, id })
    })
  }

  return {
    // State
    socket,
    isConnected,
    connectionAttempts,
    maxReconnectAttempts,
    reconnectDelay,
    lastPing,
    
    // Getters
    connectionStatus,
    shouldReconnect,
    
    // Actions
    connect,
    disconnect,
    sendDeviceCommand,
    sendRoomCommand,
    requestStatus
  }
})

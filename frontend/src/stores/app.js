import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // State
  const isLoading = ref(false)
  const loadingMessage = ref('')
  const notifications = ref([])
  const systemStatus = ref(null)
  const lastUpdated = ref(null)

  // Getters
  const hasNotifications = computed(() => notifications.value.length > 0)
  const isSystemHealthy = computed(() => {
    return systemStatus.value?.server?.status === 'running' && 
           systemStatus.value?.configuration?.valid === true
  })

  // Actions
  function setLoading(loading, message = '') {
    isLoading.value = loading
    loadingMessage.value = message
  }

  function addNotification(notification) {
    const id = Date.now() + Math.random()
    const newNotification = {
      id,
      type: 'info',
      title: '',
      message: '',
      duration: 5000,
      ...notification
    }
    
    notifications.value.push(newNotification)
    
    // Auto-remove notification after duration
    if (newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id)
      }, newNotification.duration)
    }
    
    return id
  }

  function removeNotification(id) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  function clearNotifications() {
    notifications.value = []
  }

  function showSuccess(title, message = '', duration = 3000) {
    return addNotification({
      type: 'success',
      title,
      message,
      duration
    })
  }

  function showError(title, message = '', duration = 5000) {
    return addNotification({
      type: 'error',
      title,
      message,
      duration
    })
  }

  function showWarning(title, message = '', duration = 4000) {
    return addNotification({
      type: 'warning',
      title,
      message,
      duration
    })
  }

  function showInfo(title, message = '', duration = 3000) {
    return addNotification({
      type: 'info',
      title,
      message,
      duration
    })
  }

  function updateSystemStatus(status) {
    systemStatus.value = status
    lastUpdated.value = new Date().toISOString()
  }

  async function initialize() {
    try {
      setLoading(true, 'Initializing application...')
      
      // Load initial system status
      const response = await fetch('/api/v1/status')
      if (response.ok) {
        const status = await response.json()
        updateSystemStatus(status)
      }
      
      showSuccess('Application initialized', 'Connected to home automation system')
      
    } catch (error) {
      console.error('Failed to initialize app:', error)
      showError('Initialization failed', 'Could not connect to home automation system')
    } finally {
      setLoading(false)
    }
  }

  return {
    // State
    isLoading,
    loadingMessage,
    notifications,
    systemStatus,
    lastUpdated,
    
    // Getters
    hasNotifications,
    isSystemHealthy,
    
    // Actions
    setLoading,
    addNotification,
    removeNotification,
    clearNotifications,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    updateSystemStatus,
    initialize
  }
})

<template>
  <div class="container mx-auto px-4 py-8">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900">Settings</h1>
      <p class="mt-2 text-gray-600">Configure your home automation system</p>
    </div>

    <div class="space-y-8">
      <!-- System Status -->
      <div class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-medium text-gray-900">System Status</h2>
        </div>
        <div class="px-6 py-4">
          <div v-if="systemStatus" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div class="text-center">
              <div class="text-2xl font-bold text-green-600">{{ systemStatus.uptime || 'N/A' }}</div>
              <div class="text-sm text-gray-500">Uptime</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-blue-600">{{ systemStatus.connectedDevices || 0 }}</div>
              <div class="text-sm text-gray-500">Connected Devices</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-purple-600">{{ systemStatus.activeScenes || 0 }}</div>
              <div class="text-sm text-gray-500">Active Scenes</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-orange-600">{{ systemStatus.version || 'N/A' }}</div>
              <div class="text-sm text-gray-500">Version</div>
            </div>
          </div>
          <div v-else class="text-center py-4">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
            <p class="mt-2 text-sm text-gray-500">Loading system status...</p>
          </div>
        </div>
      </div>

      <!-- General Settings -->
      <div class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-medium text-gray-900">General Settings</h2>
        </div>
        <div class="px-6 py-4 space-y-6">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-medium text-gray-900">Dark Mode</h3>
              <p class="text-sm text-gray-500">Enable dark theme for the interface</p>
            </div>
            <button
              @click="toggleDarkMode"
              :class="settings.darkMode ? 'bg-blue-600' : 'bg-gray-200'"
              class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span
                :class="settings.darkMode ? 'translate-x-5' : 'translate-x-0'"
                class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
              ></span>
            </button>
          </div>

          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-medium text-gray-900">Auto-refresh</h3>
              <p class="text-sm text-gray-500">Automatically refresh device status</p>
            </div>
            <button
              @click="toggleAutoRefresh"
              :class="settings.autoRefresh ? 'bg-blue-600' : 'bg-gray-200'"
              class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span
                :class="settings.autoRefresh ? 'translate-x-5' : 'translate-x-0'"
                class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
              ></span>
            </button>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-900 mb-2">Refresh Interval</label>
            <select
              v-model="settings.refreshInterval"
              @change="updateSettings"
              class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            >
              <option value="5">5 seconds</option>
              <option value="10">10 seconds</option>
              <option value="30">30 seconds</option>
              <option value="60">1 minute</option>
              <option value="300">5 minutes</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Notifications -->
      <div class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-medium text-gray-900">Notifications</h2>
        </div>
        <div class="px-6 py-4 space-y-6">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-medium text-gray-900">Device Alerts</h3>
              <p class="text-sm text-gray-500">Get notified when devices go offline</p>
            </div>
            <button
              @click="toggleDeviceAlerts"
              :class="settings.deviceAlerts ? 'bg-blue-600' : 'bg-gray-200'"
              class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span
                :class="settings.deviceAlerts ? 'translate-x-5' : 'translate-x-0'"
                class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
              ></span>
            </button>
          </div>

          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-medium text-gray-900">Scene Notifications</h3>
              <p class="text-sm text-gray-500">Get notified when scenes are activated</p>
            </div>
            <button
              @click="toggleSceneNotifications"
              :class="settings.sceneNotifications ? 'bg-blue-600' : 'bg-gray-200'"
              class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span
                :class="settings.sceneNotifications ? 'translate-x-5' : 'translate-x-0'"
                class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
              ></span>
            </button>
          </div>
        </div>
      </div>

      <!-- System Actions -->
      <div class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-medium text-gray-900">System Actions</h2>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-medium text-gray-900">Restart System</h3>
              <p class="text-sm text-gray-500">Restart the home automation system</p>
            </div>
            <button
              @click="restartSystem"
              :disabled="restarting"
              class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-orange-600 hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="restarting" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
              Restart
            </button>
          </div>

          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-medium text-gray-900">Export Configuration</h3>
              <p class="text-sm text-gray-500">Download system configuration as backup</p>
            </div>
            <button
              @click="exportConfig"
              :disabled="exporting"
              class="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="exporting" class="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600 mr-2"></span>
              Export
            </button>
          </div>

          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-medium text-gray-900">Clear Logs</h3>
              <p class="text-sm text-gray-500">Clear system logs and history</p>
            </div>
            <button
              @click="clearLogs"
              :disabled="clearingLogs"
              class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="clearingLogs" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
              Clear Logs
            </button>
          </div>
        </div>
      </div>

      <!-- About -->
      <div class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-medium text-gray-900">About</h2>
        </div>
        <div class="px-6 py-4">
          <div class="space-y-4">
            <div>
              <h3 class="text-sm font-medium text-gray-900">Hera Home Automation</h3>
              <p class="text-sm text-gray-500">A modern home automation system built with Vue.js and Node.js</p>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div>
                <span class="font-medium text-gray-900">Version:</span>
                <span class="ml-2 text-gray-600">{{ systemStatus?.version || '1.0.0' }}</span>
              </div>
              <div>
                <span class="font-medium text-gray-900">Build:</span>
                <span class="ml-2 text-gray-600">{{ systemStatus?.build || 'Development' }}</span>
              </div>
              <div>
                <span class="font-medium text-gray-900">Node.js:</span>
                <span class="ml-2 text-gray-600">{{ systemStatus?.nodeVersion || 'N/A' }}</span>
              </div>
              <div>
                <span class="font-medium text-gray-900">Platform:</span>
                <span class="ml-2 text-gray-600">{{ systemStatus?.platform || 'N/A' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import axios from 'axios'

export default {
  name: 'Settings',
  setup() {
    const systemStatus = ref(null)
    const settings = ref({
      darkMode: false,
      autoRefresh: true,
      refreshInterval: 30,
      deviceAlerts: true,
      sceneNotifications: true
    })
    
    const restarting = ref(false)
    const exporting = ref(false)
    const clearingLogs = ref(false)

    const fetchSystemStatus = async () => {
      try {
        const response = await axios.get('/api/status')
        systemStatus.value = response.data
      } catch (err) {
        console.error('Error fetching system status:', err)
      }
    }

    const loadSettings = () => {
      const savedSettings = localStorage.getItem('hera-settings')
      if (savedSettings) {
        settings.value = { ...settings.value, ...JSON.parse(savedSettings) }
      }
    }

    const saveSettings = () => {
      localStorage.setItem('hera-settings', JSON.stringify(settings.value))
    }

    const updateSettings = () => {
      saveSettings()
    }

    const toggleDarkMode = () => {
      settings.value.darkMode = !settings.value.darkMode
      saveSettings()
      // Apply dark mode class to document
      if (settings.value.darkMode) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }

    const toggleAutoRefresh = () => {
      settings.value.autoRefresh = !settings.value.autoRefresh
      saveSettings()
    }

    const toggleDeviceAlerts = () => {
      settings.value.deviceAlerts = !settings.value.deviceAlerts
      saveSettings()
    }

    const toggleSceneNotifications = () => {
      settings.value.sceneNotifications = !settings.value.sceneNotifications
      saveSettings()
    }

    const restartSystem = async () => {
      if (restarting.value) return
      
      if (!confirm('Are you sure you want to restart the system? This will temporarily interrupt all automation.')) {
        return
      }
      
      try {
        restarting.value = true
        await axios.post('/api/system/restart')
        // Show success message or redirect
      } catch (err) {
        console.error('Error restarting system:', err)
      } finally {
        restarting.value = false
      }
    }

    const exportConfig = async () => {
      if (exporting.value) return
      
      try {
        exporting.value = true
        const response = await axios.get('/api/system/export', {
          responseType: 'blob'
        })
        
        // Create download link
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `hera-config-${new Date().toISOString().split('T')[0]}.json`)
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)
      } catch (err) {
        console.error('Error exporting configuration:', err)
      } finally {
        exporting.value = false
      }
    }

    const clearLogs = async () => {
      if (clearingLogs.value) return
      
      if (!confirm('Are you sure you want to clear all system logs? This action cannot be undone.')) {
        return
      }
      
      try {
        clearingLogs.value = true
        await axios.delete('/api/system/logs')
        // Show success message
      } catch (err) {
        console.error('Error clearing logs:', err)
      } finally {
        clearingLogs.value = false
      }
    }

    onMounted(() => {
      fetchSystemStatus()
      loadSettings()
      
      // Apply dark mode if enabled
      if (settings.value.darkMode) {
        document.documentElement.classList.add('dark')
      }
    })

    return {
      systemStatus,
      settings,
      restarting,
      exporting,
      clearingLogs,
      updateSettings,
      toggleDarkMode,
      toggleAutoRefresh,
      toggleDeviceAlerts,
      toggleSceneNotifications,
      restartSystem,
      exportConfig,
      clearLogs
    }
  }
}
</script>

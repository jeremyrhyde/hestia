<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="md:flex md:items-center md:justify-between">
      <div class="flex-1 min-w-0">
        <h2 class="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
          Dashboard
        </h2>
        <p class="mt-1 text-sm text-gray-500">
          Welcome to your home automation control center
        </p>
      </div>
      <div class="mt-4 flex md:mt-0 md:ml-4">
        <button
          @click="refreshData"
          :disabled="isLoading"
          class="btn-outline"
        >
          <div v-if="isLoading" class="loading-spinner w-4 h-4 mr-2"></div>
          <span>{{ isLoading ? 'Refreshing...' : 'Refresh' }}</span>
        </button>
      </div>
    </div>

    <!-- System Status Cards -->
    <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      <!-- Total Devices -->
      <div class="card">
        <div class="card-body">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <div class="w-8 h-8 bg-blue-500 rounded-md flex items-center justify-center">
                <span class="text-white text-sm font-medium">📱</span>
              </div>
            </div>
            <div class="ml-5 w-0 flex-1">
              <dl>
                <dt class="text-sm font-medium text-gray-500 truncate">
                  Total Devices
                </dt>
                <dd class="text-lg font-medium text-gray-900">
                  {{ systemStats.totalDevices }}
                </dd>
              </dl>
            </div>
          </div>
        </div>
      </div>

      <!-- Online Devices -->
      <div class="card">
        <div class="card-body">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <div class="w-8 h-8 bg-green-500 rounded-md flex items-center justify-center">
                <span class="text-white text-sm font-medium">✓</span>
              </div>
            </div>
            <div class="ml-5 w-0 flex-1">
              <dl>
                <dt class="text-sm font-medium text-gray-500 truncate">
                  Online Devices
                </dt>
                <dd class="text-lg font-medium text-gray-900">
                  {{ systemStats.onlineDevices }}
                </dd>
              </dl>
            </div>
          </div>
        </div>
      </div>

      <!-- Total Rooms -->
      <div class="card">
        <div class="card-body">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <div class="w-8 h-8 bg-purple-500 rounded-md flex items-center justify-center">
                <span class="text-white text-sm font-medium">🏠</span>
              </div>
            </div>
            <div class="ml-5 w-0 flex-1">
              <dl>
                <dt class="text-sm font-medium text-gray-500 truncate">
                  Total Rooms
                </dt>
                <dd class="text-lg font-medium text-gray-900">
                  {{ systemStats.totalRooms }}
                </dd>
              </dl>
            </div>
          </div>
        </div>
      </div>

      <!-- Available Scenes -->
      <div class="card">
        <div class="card-body">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <div class="w-8 h-8 bg-yellow-500 rounded-md flex items-center justify-center">
                <span class="text-white text-sm font-medium">🎬</span>
              </div>
            </div>
            <div class="ml-5 w-0 flex-1">
              <dl>
                <dt class="text-sm font-medium text-gray-500 truncate">
                  Available Scenes
                </dt>
                <dd class="text-lg font-medium text-gray-900">
                  {{ systemStats.totalScenes }}
                </dd>
              </dl>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="card">
      <div class="card-header">
        <h3 class="text-lg leading-6 font-medium text-gray-900">
          Quick Actions
        </h3>
        <p class="mt-1 max-w-2xl text-sm text-gray-500">
          Common home automation controls
        </p>
      </div>
      <div class="card-body">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <button
            @click="executeQuickAction('all_lights_off')"
            class="btn-outline flex flex-col items-center p-4 h-24"
          >
            <span class="text-2xl mb-2">💡</span>
            <span class="text-sm">All Lights Off</span>
          </button>
          
          <button
            @click="executeQuickAction('all_lights_on')"
            class="btn-outline flex flex-col items-center p-4 h-24"
          >
            <span class="text-2xl mb-2">🔆</span>
            <span class="text-sm">All Lights On</span>
          </button>
          
          <button
            @click="executeQuickAction('music_pause')"
            class="btn-outline flex flex-col items-center p-4 h-24"
          >
            <span class="text-2xl mb-2">⏸️</span>
            <span class="text-sm">Pause Music</span>
          </button>
          
          <button
            @click="activateScene('morning')"
            class="btn-outline flex flex-col items-center p-4 h-24"
          >
            <span class="text-2xl mb-2">🌅</span>
            <span class="text-sm">Morning Scene</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Recent Activity -->
    <div class="card">
      <div class="card-header">
        <h3 class="text-lg leading-6 font-medium text-gray-900">
          Recent Activity
        </h3>
        <p class="mt-1 max-w-2xl text-sm text-gray-500">
          Latest device and system events
        </p>
      </div>
      <div class="card-body">
        <div v-if="recentActivity.length === 0" class="text-center py-8">
          <span class="text-gray-500">No recent activity</span>
        </div>
        <div v-else class="flow-root">
          <ul class="-mb-8">
            <li
              v-for="(activity, index) in recentActivity"
              :key="activity.id"
              class="relative pb-8"
            >
              <div v-if="index !== recentActivity.length - 1" class="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"></div>
              <div class="relative flex space-x-3">
                <div>
                  <span
                    :class="[
                      'h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white',
                      activity.type === 'success' ? 'bg-green-500' :
                      activity.type === 'error' ? 'bg-red-500' :
                      activity.type === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'
                    ]"
                  >
                    <span class="text-white text-xs">
                      {{ activity.type === 'success' ? '✓' : 
                         activity.type === 'error' ? '✕' : 
                         activity.type === 'warning' ? '⚠' : 'ℹ' }}
                    </span>
                  </span>
                </div>
                <div class="min-w-0 flex-1 pt-1.5 flex justify-between space-x-4">
                  <div>
                    <p class="text-sm text-gray-500">
                      {{ activity.message }}
                    </p>
                  </div>
                  <div class="text-right text-sm whitespace-nowrap text-gray-500">
                    {{ formatTime(activity.timestamp) }}
                  </div>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { useConnectionStore } from '@/stores/connection'

const appStore = useAppStore()
const connectionStore = useConnectionStore()

// State
const isLoading = ref(false)
const systemStats = ref({
  totalDevices: 0,
  onlineDevices: 0,
  totalRooms: 0,
  totalScenes: 0
})
const recentActivity = ref([])

// Methods
async function loadDashboardData() {
  isLoading.value = true
  
  try {
    // Load system status
    const statusResponse = await fetch('/api/v1/status')
    if (statusResponse.ok) {
      const status = await statusResponse.json()
      systemStats.value.totalDevices = status.adapters.total
      systemStats.value.onlineDevices = status.adapters.online
    }
    
    // Load rooms count
    const roomsResponse = await fetch('/api/v1/rooms')
    if (roomsResponse.ok) {
      const rooms = await roomsResponse.json()
      systemStats.value.totalRooms = rooms.total
    }
    
    // Load scenes count
    const scenesResponse = await fetch('/api/v1/scenes')
    if (scenesResponse.ok) {
      const scenes = await scenesResponse.json()
      systemStats.value.totalScenes = scenes.total
    }
    
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
    appStore.showError('Failed to load dashboard', 'Could not retrieve system information')
  } finally {
    isLoading.value = false
  }
}

async function refreshData() {
  await loadDashboardData()
  appStore.showSuccess('Dashboard refreshed', 'Latest data loaded')
}

async function executeQuickAction(action) {
  console.log("HEEEELELELELELELE - executeQuickAction called with:", action)
  try {
    switch (action) {
      case 'all_lights_off':
        console.log("HEEEELELELELELELE - all_lights_off case triggered")
        appStore.showInfo('Quick Action', 'Turning off all lights...')
        await turnAllLights(false)
        break
      case 'all_lights_on':
        console.log("HEEEELELELELELELE - all_lights_on case triggered")
        appStore.showInfo('Quick Action', 'Turning on all lights...')
        await turnAllLights(true)
        break
      case 'music_pause':
        appStore.showInfo('Quick Action', 'Pausing music...')
        break
      default:
        appStore.showWarning('Unknown Action', `Action ${action} not implemented`)
    }
  } catch (error) {
    console.error("HEEEELELELELELELE - Error in executeQuickAction:", error)
    appStore.showError('Action Failed', error.message)
  }
}

async function turnAllLights(state) {
  try {
    // Get all devices
    const devicesResponse = await fetch('/api/v1/devices')
    if (!devicesResponse.ok) {
      throw new Error('Failed to get devices')
    }
    
    const devicesData = await devicesResponse.json()
    const lightDevices = devicesData.devices.filter(device => 
      device.capabilities && device.capabilities.includes('power') &&
      (device.type === 'smart_bulb' || device.type === 'led_strip' || device.type === 'bulb')
    )
    
    if (lightDevices.length === 0) {
      appStore.showWarning('No Lights Found', 'No controllable lights were found')
      return
    }
    
    // Send individual commands to each light device
    const results = await Promise.allSettled(
      lightDevices.map(async (device) => {
        const response = await fetch(`/api/v1/devices/${device.id}/command`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            command: 'power',
            params: { state }
          })
        })
        
        if (!response.ok) {
          throw new Error(`Failed to control ${device.name}`)
        }
        
        return { deviceId: device.id, name: device.name }
      })
    )
    
    const successful = results.filter(result => result.status === 'fulfilled')
    const failed = results.filter(result => result.status === 'rejected')
    
    if (successful.length > 0) {
      appStore.showSuccess(
        `Lights ${state ? 'On' : 'Off'}`, 
        `Successfully turned ${state ? 'on' : 'off'} ${successful.length} lights`
      )
      addActivity('success', `Turned ${state ? 'on' : 'off'} ${successful.length} lights`)
    }
    
    if (failed.length > 0) {
      appStore.showWarning(
        'Some Lights Failed', 
        `${failed.length} lights failed to respond`
      )
    }
    
  } catch (error) {
    console.error('Failed to control lights:', error)
    appStore.showError('Light Control Failed', error.message)
  }
}

async function activateScene(sceneId) {
  try {
    const response = await fetch(`/api/v1/scenes/${sceneId}/activate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const result = await response.json()
      appStore.showSuccess('Scene Activated', `${result.sceneName} scene is now active`)
      addActivity('success', `Scene "${result.sceneName}" activated`)
    } else {
      const error = await response.json()
      appStore.showError('Scene Activation Failed', error.error)
    }
  } catch (error) {
    appStore.showError('Scene Activation Failed', error.message)
  }
}

function addActivity(type, message) {
  recentActivity.value.unshift({
    id: Date.now(),
    type,
    message,
    timestamp: new Date().toISOString()
  })
  
  // Keep only last 10 activities
  if (recentActivity.value.length > 10) {
    recentActivity.value = recentActivity.value.slice(0, 10)
  }
}

function formatTime(timestamp) {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) { // Less than 1 minute
    return 'Just now'
  } else if (diff < 3600000) { // Less than 1 hour
    const minutes = Math.floor(diff / 60000)
    return `${minutes}m ago`
  } else if (diff < 86400000) { // Less than 1 day
    const hours = Math.floor(diff / 3600000)
    return `${hours}h ago`
  } else {
    return date.toLocaleDateString()
  }
}

// Event listeners for real-time updates
function handleDeviceUpdate(event) {
  addActivity('success', `Device ${event.detail.deviceId} updated`)
}

function handleRoomUpdate(event) {
  addActivity('success', `Room ${event.detail.roomId} updated`)
}

function handleSceneActivated(event) {
  addActivity('success', `Scene "${event.detail.sceneName}" activated`)
}

// Lifecycle
onMounted(() => {
  loadDashboardData()
  
  // Listen for real-time updates
  window.addEventListener('device-status-update', handleDeviceUpdate)
  window.addEventListener('room-status-update', handleRoomUpdate)
  window.addEventListener('scene-activated', handleSceneActivated)
})

onUnmounted(() => {
  // Clean up event listeners
  window.removeEventListener('device-status-update', handleDeviceUpdate)
  window.removeEventListener('room-status-update', handleRoomUpdate)
  window.removeEventListener('scene-activated', handleSceneActivated)
})
</script>

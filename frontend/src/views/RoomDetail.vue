<template>
  <div class="container mx-auto px-4 py-8">
    <div class="mb-6">
      <button 
        @click="$router.go(-1)"
        class="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
      >
        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
        </svg>
        Back to Rooms
      </button>
    </div>

    <div v-if="loading" class="flex justify-center items-center h-64">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
    </div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-md p-4">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800">Error loading room</h3>
          <div class="mt-2 text-sm text-red-700">
            <p>{{ error }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="room">
      <!-- Room Header -->
      <div class="bg-white shadow rounded-lg mb-8">
        <div class="px-6 py-4 border-b border-gray-200">
          <div class="flex items-center justify-between">
            <div class="flex items-center">
              <div class="w-12 h-12 bg-blue-500 rounded-full flex items-center justify-center">
                <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"/>
                </svg>
              </div>
              <div class="ml-4">
                <h1 class="text-2xl font-bold text-gray-900">{{ room.name }}</h1>
                <p class="text-sm text-gray-500">{{ room.devices.length }} devices</p>
              </div>
            </div>
            <div class="flex items-center space-x-4">
              <div class="text-right">
                <div class="text-sm text-gray-500">Active</div>
                <div class="text-lg font-semibold text-green-600">{{ activeDevicesCount }}</div>
              </div>
              <div class="text-right">
                <div class="text-sm text-gray-500">Inactive</div>
                <div class="text-lg font-semibold text-gray-600">{{ inactiveDevicesCount }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Room Controls -->
        <div class="px-6 py-4">
          <div class="flex space-x-4">
            <button
              @click="toggleAllDevices(true)"
              :disabled="updating"
              class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="updating" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
              Turn All On
            </button>
            <button
              @click="toggleAllDevices(false)"
              :disabled="updating"
              class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="updating" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
              Turn All Off
            </button>
          </div>
        </div>
      </div>

      <!-- Devices Grid -->
      <div v-if="room.devices.length > 0">
        <h2 class="text-xl font-semibold text-gray-900 mb-6">Devices in {{ room.name }}</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="device in room.devices"
            :key="device.id"
            class="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-200 cursor-pointer"
            @click="$router.push(`/devices/${device.id}`)"
          >
            <div class="p-6">
              <div class="flex items-center justify-between mb-4">
                <div class="flex items-center">
                  <div class="flex-shrink-0">
                    <div :class="getDeviceIconClass(device.type)" class="w-10 h-10 rounded-full flex items-center justify-center">
                      <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path v-if="device.type === 'light'" d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.34.208-.646.477-.859a4 4 0 10-4.954 0c.27.213.462.519.477.859h4z"/>
                        <path v-else-if="device.type === 'switch'" d="M17 4H3a1 1 0 000 2h14a1 1 0 100-2zM3 8a1 1 0 000 2h14a1 1 0 100-2H3zM3 12a1 1 0 100 2h14a1 1 0 100-2H3z"/>
                        <path v-else d="M9 12a1 1 0 102 0V8a1 1 0 10-2 0v4zm6-8a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h10z"/>
                      </svg>
                    </div>
                  </div>
                  <div class="ml-4">
                    <h3 class="text-lg font-medium text-gray-900">{{ device.name }}</h3>
                    <p class="text-sm text-gray-500 capitalize">{{ device.type }}</p>
                  </div>
                </div>
                <div class="flex items-center">
                  <span
                    :class="device.status?.power ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'"
                    class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                  >
                    {{ device.status?.power ? 'On' : 'Off' }}
                  </span>
                </div>
              </div>

              <div class="space-y-2">
                <div v-if="device.status?.brightness !== undefined" class="flex items-center justify-between text-sm">
                  <span class="text-gray-500">Brightness</span>
                  <span class="text-gray-900">{{ device.status.brightness }}%</span>
                </div>
                <div v-if="device.status?.temperature !== undefined" class="flex items-center justify-between text-sm">
                  <span class="text-gray-500">Temperature</span>
                  <span class="text-gray-900">{{ device.status.temperature }}°</span>
                </div>
              </div>

              <!-- Quick Actions -->
              <div class="mt-4 pt-4 border-t border-gray-200">
                <button
                  @click.stop="toggleDevice(device)"
                  :disabled="device.updating"
                  :class="device.status?.power ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'"
                  class="w-full inline-flex justify-center items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span v-if="device.updating" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
                  {{ device.status?.power ? 'Turn Off' : 'Turn On' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 12h6m-6-4h6m2 5.291A7.962 7.962 0 0112 15c-2.34 0-4.29.82-5.877 2.172M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.875a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0z" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900">No devices in this room</h3>
        <p class="mt-1 text-sm text-gray-500">This room doesn't have any devices configured yet.</p>
      </div>
    </div>

    <div v-else class="text-center py-12">
      <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2V7zm0 0V5a2 2 0 012-2h6l2 2h6a2 2 0 012 2v2M7 13h10M7 17h4" />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">Room not found</h3>
      <p class="mt-1 text-sm text-gray-500">The requested room could not be found.</p>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

export default {
  name: 'RoomDetail',
  setup() {
    const route = useRoute()
    const room = ref(null)
    const loading = ref(true)
    const error = ref(null)
    const updating = ref(false)

    const activeDevicesCount = computed(() => {
      if (!room.value) return 0
      return room.value.devices.filter(device => device.status?.power).length
    })

    const inactiveDevicesCount = computed(() => {
      if (!room.value) return 0
      return room.value.devices.filter(device => !device.status?.power).length
    })

    const fetchRoom = async () => {
      try {
        loading.value = true
        error.value = null
        const response = await axios.get(`/api/rooms/${route.params.id}`)
        room.value = response.data
      } catch (err) {
        error.value = err.response?.data?.message || 'Failed to load room'
        console.error('Error fetching room:', err)
      } finally {
        loading.value = false
      }
    }

    const toggleDevice = async (device) => {
      if (device.updating) return
      
      try {
        device.updating = true
        const newPowerState = !device.status?.power
        await axios.post(`/api/devices/${device.id}/power`, {
          power: newPowerState
        })
        
        // Update local state
        if (device.status) {
          device.status.power = newPowerState
        }
      } catch (err) {
        console.error('Error toggling device:', err)
      } finally {
        device.updating = false
      }
    }

    const toggleAllDevices = async (powerState) => {
      if (!room.value || updating.value) return
      
      try {
        updating.value = true
        await axios.post(`/api/rooms/${room.value.name}/power`, {
          power: powerState
        })
        
        // Update local state
        room.value.devices.forEach(device => {
          if (device.status) {
            device.status.power = powerState
          }
        })
      } catch (err) {
        console.error('Error toggling all devices:', err)
      } finally {
        updating.value = false
      }
    }

    const getDeviceIconClass = (type) => {
      const classes = {
        light: 'bg-yellow-500',
        switch: 'bg-blue-500',
        sensor: 'bg-green-500',
        speaker: 'bg-purple-500',
        default: 'bg-gray-500'
      }
      return classes[type] || classes.default
    }

    onMounted(() => {
      fetchRoom()
    })

    return {
      room,
      loading,
      error,
      updating,
      activeDevicesCount,
      inactiveDevicesCount,
      toggleDevice,
      toggleAllDevices,
      getDeviceIconClass
    }
  }
}
</script>

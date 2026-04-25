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
        Back
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
          <h3 class="text-sm font-medium text-red-800">Error loading device</h3>
          <div class="mt-2 text-sm text-red-700">
            <p>{{ error }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="device" class="bg-white shadow rounded-lg">
      <div class="px-6 py-4 border-b border-gray-200">
        <h1 class="text-2xl font-bold text-gray-900">{{ device.name }}</h1>
        <p class="text-sm text-gray-500 mt-1">{{ device.type }} • {{ device.room }}</p>
      </div>

      <div class="px-6 py-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <!-- Device Status -->
          <div class="space-y-4">
            <h2 class="text-lg font-medium text-gray-900">Status</h2>
            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium text-gray-700">Power</span>
                <span :class="device.status?.power ? 'text-green-600' : 'text-red-600'" class="text-sm font-medium">
                  {{ device.status?.power ? 'On' : 'Off' }}
                </span>
              </div>
              <div v-if="device.status?.brightness !== undefined" class="flex items-center justify-between">
                <span class="text-sm font-medium text-gray-700">Brightness</span>
                <span class="text-sm font-medium text-gray-900">{{ device.status.brightness }}%</span>
              </div>
              <div v-if="device.status?.temperature !== undefined" class="flex items-center justify-between">
                <span class="text-sm font-medium text-gray-700">Temperature</span>
                <span class="text-sm font-medium text-gray-900">{{ device.status.temperature }}°</span>
              </div>
            </div>
          </div>

          <!-- Device Controls -->
          <div class="space-y-4">
            <h2 class="text-lg font-medium text-gray-900">Controls</h2>
            <div class="space-y-3">
              <button 
                @click="togglePower"
                :disabled="updating"
                :class="device.status?.power ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'"
                class="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="updating" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
                {{ device.status?.power ? 'Turn Off' : 'Turn On' }}
              </button>

              <div v-if="device.type === 'light' && device.status?.power" class="space-y-3">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">Brightness</label>
                  <input 
                    type="range" 
                    min="1" 
                    max="100" 
                    :value="device.status.brightness || 50"
                    @input="updateBrightness($event.target.value)"
                    class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  >
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Device Information -->
        <div class="mt-8 pt-6 border-t border-gray-200">
          <h2 class="text-lg font-medium text-gray-900 mb-4">Device Information</h2>
          <dl class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <dt class="text-sm font-medium text-gray-500">Device ID</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ device.id }}</dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">Type</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ device.type }}</dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">Room</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ device.room }}</dd>
            </div>
            <div v-if="device.manufacturer">
              <dt class="text-sm font-medium text-gray-500">Manufacturer</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ device.manufacturer }}</dd>
            </div>
            <div v-if="device.model">
              <dt class="text-sm font-medium text-gray-500">Model</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ device.model }}</dd>
            </div>
            <div v-if="device.lastSeen">
              <dt class="text-sm font-medium text-gray-500">Last Seen</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ formatDate(device.lastSeen) }}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-12">
      <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 12h6m-6-4h6m2 5.291A7.962 7.962 0 0112 15c-2.34 0-4.29.82-5.877 2.172M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.875a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0z" />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">Device not found</h3>
      <p class="mt-1 text-sm text-gray-500">The requested device could not be found.</p>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

export default {
  name: 'DeviceDetail',
  setup() {
    const route = useRoute()
    const device = ref(null)
    const loading = ref(true)
    const error = ref(null)
    const updating = ref(false)

    const fetchDevice = async () => {
      try {
        loading.value = true
        error.value = null
        const response = await axios.get(`/api/devices/${route.params.id}`)
        device.value = response.data
      } catch (err) {
        error.value = err.response?.data?.message || 'Failed to load device'
        console.error('Error fetching device:', err)
      } finally {
        loading.value = false
      }
    }

    const togglePower = async () => {
      if (!device.value || updating.value) return
      
      try {
        updating.value = true
        const newPowerState = !device.value.status?.power
        await axios.post(`/api/devices/${device.value.id}/power`, {
          power: newPowerState
        })
        
        // Update local state
        if (device.value.status) {
          device.value.status.power = newPowerState
        }
      } catch (err) {
        error.value = err.response?.data?.message || 'Failed to toggle power'
        console.error('Error toggling power:', err)
      } finally {
        updating.value = false
      }
    }

    const updateBrightness = async (brightness) => {
      if (!device.value || updating.value) return
      
      try {
        await axios.post(`/api/devices/${device.value.id}/brightness`, {
          brightness: parseInt(brightness)
        })
        
        // Update local state
        if (device.value.status) {
          device.value.status.brightness = parseInt(brightness)
        }
      } catch (err) {
        console.error('Error updating brightness:', err)
      }
    }

    const formatDate = (dateString) => {
      return new Date(dateString).toLocaleString()
    }

    onMounted(() => {
      fetchDevice()
    })

    return {
      device,
      loading,
      error,
      updating,
      togglePower,
      updateBrightness,
      formatDate
    }
  }
}
</script>

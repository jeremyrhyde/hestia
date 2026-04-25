<template>
  <div class="container mx-auto px-4 py-8">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900">Rooms</h1>
      <p class="mt-2 text-gray-600">Manage devices by room</p>
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
          <h3 class="text-sm font-medium text-red-800">Error loading rooms</h3>
          <div class="mt-2 text-sm text-red-700">
            <p>{{ error }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else>
      <!-- Rooms Grid -->
      <div v-if="rooms.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="room in rooms"
          :key="room.name"
          class="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-200 cursor-pointer"
          @click="$router.push(`/rooms/${room.name}`)"
        >
          <div class="p-6">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-12 h-12 bg-blue-500 rounded-full flex items-center justify-center">
                    <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"/>
                    </svg>
                  </div>
                </div>
                <div class="ml-4">
                  <h3 class="text-xl font-semibold text-gray-900">{{ room.name }}</h3>
                  <p class="text-sm text-gray-500">{{ room.devices.length }} devices</p>
                </div>
              </div>
            </div>

            <div class="space-y-3">
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500">Active Devices</span>
                <span class="text-gray-900 font-medium">{{ activeDevicesCount(room) }}</span>
              </div>
              
              <!-- Device Types Summary -->
              <div v-if="room.deviceTypes && room.deviceTypes.length > 0" class="flex flex-wrap gap-1">
                <span
                  v-for="type in room.deviceTypes"
                  :key="type"
                  class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                >
                  {{ type }}
                </span>
              </div>

              <!-- Recent Devices -->
              <div v-if="room.devices.length > 0" class="space-y-2">
                <h4 class="text-sm font-medium text-gray-700">Recent Devices</h4>
                <div class="space-y-1">
                  <div
                    v-for="device in room.devices.slice(0, 3)"
                    :key="device.id"
                    class="flex items-center justify-between text-sm"
                  >
                    <span class="text-gray-600">{{ device.name }}</span>
                    <span
                      :class="device.status?.power ? 'text-green-600' : 'text-gray-400'"
                      class="text-xs"
                    >
                      {{ device.status?.power ? 'On' : 'Off' }}
                    </span>
                  </div>
                  <div v-if="room.devices.length > 3" class="text-xs text-gray-500">
                    +{{ room.devices.length - 3 }} more devices
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2V7zm0 0V5a2 2 0 012-2h6l2 2h6a2 2 0 012 2v2M7 13h10M7 17h4" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900">No rooms found</h3>
        <p class="mt-1 text-sm text-gray-500">No rooms have been configured yet.</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

export default {
  name: 'Rooms',
  setup() {
    const rooms = ref([])
    const loading = ref(true)
    const error = ref(null)

    const fetchRooms = async () => {
      try {
        loading.value = true
        error.value = null
        const response = await axios.get('/api/rooms')
        rooms.value = response.data
      } catch (err) {
        error.value = err.response?.data?.message || 'Failed to load rooms'
        console.error('Error fetching rooms:', err)
      } finally {
        loading.value = false
      }
    }

    const activeDevicesCount = (room) => {
      return room.devices.filter(device => device.status?.power).length
    }

    onMounted(() => {
      fetchRooms()
    })

    return {
      rooms,
      loading,
      error,
      activeDevicesCount
    }
  }
}
</script>

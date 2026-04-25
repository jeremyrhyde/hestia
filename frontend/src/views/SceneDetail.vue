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
        Back to Scenes
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
          <h3 class="text-sm font-medium text-red-800">Error loading scene</h3>
          <div class="mt-2 text-sm text-red-700">
            <p>{{ error }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="scene" class="space-y-8">
      <!-- Scene Header -->
      <div class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <div class="flex items-center justify-between">
            <div class="flex items-center">
              <div :class="getSceneIconClass(scene.type)" class="w-12 h-12 rounded-full flex items-center justify-center">
                <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path v-if="scene.type === 'morning'" d="M10 2L13.09 8.26L20 9L14 14.74L15.18 21.02L10 18L4.82 21.02L6 14.74L0 9L6.91 8.26L10 2Z"/>
                  <path v-else-if="scene.type === 'evening'" d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
                  <path v-else-if="scene.type === 'party'" d="M9 12a1 1 0 102 0V8a1 1 0 10-2 0v4zm6-8a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h10z"/>
                  <path v-else d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v3h8v-3z"/>
                </svg>
              </div>
              <div class="ml-4">
                <h1 class="text-2xl font-bold text-gray-900">{{ scene.name }}</h1>
                <p class="text-sm text-gray-500 capitalize">{{ scene.type || 'Custom' }} Scene</p>
              </div>
            </div>
            <div class="flex items-center space-x-4">
              <span
                :class="scene.active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'"
                class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium"
              >
                {{ scene.active ? 'Active' : 'Inactive' }}
              </span>
              <button
                @click="activateScene"
                :disabled="activating"
                class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="activating" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
                Activate Scene
              </button>
            </div>
          </div>
        </div>

        <div class="px-6 py-4">
          <p v-if="scene.description" class="text-gray-600">{{ scene.description }}</p>
          <p v-else class="text-gray-500 italic">No description provided</p>
        </div>
      </div>

      <!-- Scene Information -->
      <div class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-medium text-gray-900">Scene Information</h2>
        </div>
        <div class="px-6 py-4">
          <dl class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <dt class="text-sm font-medium text-gray-500">Type</dt>
              <dd class="mt-1 text-sm text-gray-900 capitalize">{{ scene.type || 'Custom' }}</dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">Devices</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ scene.devices?.length || 0 }} devices</dd>
            </div>
            <div v-if="scene.schedule">
              <dt class="text-sm font-medium text-gray-500">Schedule</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ formatSchedule(scene.schedule) }}</dd>
            </div>
            <div v-if="scene.lastActivated">
              <dt class="text-sm font-medium text-gray-500">Last Activated</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ formatDate(scene.lastActivated) }}</dd>
            </div>
            <div v-if="scene.createdAt">
              <dt class="text-sm font-medium text-gray-500">Created</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ formatDate(scene.createdAt) }}</dd>
            </div>
            <div v-if="scene.activationCount">
              <dt class="text-sm font-medium text-gray-500">Activation Count</dt>
              <dd class="mt-1 text-sm text-gray-900">{{ scene.activationCount }} times</dd>
            </div>
          </dl>
        </div>
      </div>

      <!-- Device Actions -->
      <div v-if="scene.devices && scene.devices.length > 0" class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-medium text-gray-900">Device Actions</h2>
          <p class="text-sm text-gray-500">Actions that will be performed when this scene is activated</p>
        </div>
        <div class="px-6 py-4">
          <div class="space-y-4">
            <div
              v-for="action in scene.devices"
              :key="action.deviceId"
              class="flex items-center justify-between p-4 border border-gray-200 rounded-lg"
            >
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div :class="getDeviceIconClass(action.deviceType)" class="w-8 h-8 rounded-full flex items-center justify-center">
                    <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path v-if="action.deviceType === 'light'" d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.34.208-.646.477-.859a4 4 0 10-4.954 0c.27.213.462.519.477.859h4z"/>
                      <path v-else-if="action.deviceType === 'switch'" d="M17 4H3a1 1 0 000 2h14a1 1 0 100-2zM3 8a1 1 0 000 2h14a1 1 0 100-2H3zM3 12a1 1 0 100 2h14a1 1 0 100-2H3z"/>
                      <path v-else d="M9 12a1 1 0 102 0V8a1 1 0 10-2 0v4zm6-8a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h10z"/>
                    </svg>
                  </div>
                </div>
                <div class="ml-3">
                  <h3 class="text-sm font-medium text-gray-900">{{ action.deviceName || action.deviceId }}</h3>
                  <p class="text-sm text-gray-500 capitalize">{{ action.deviceType }}</p>
                </div>
              </div>
              <div class="text-right">
                <div class="space-y-1">
                  <div v-if="action.power !== undefined" class="text-sm">
                    <span class="text-gray-500">Power:</span>
                    <span :class="action.power ? 'text-green-600' : 'text-red-600'" class="ml-1 font-medium">
                      {{ action.power ? 'On' : 'Off' }}
                    </span>
                  </div>
                  <div v-if="action.brightness !== undefined" class="text-sm">
                    <span class="text-gray-500">Brightness:</span>
                    <span class="ml-1 font-medium text-gray-900">{{ action.brightness }}%</span>
                  </div>
                  <div v-if="action.temperature !== undefined" class="text-sm">
                    <span class="text-gray-500">Temperature:</span>
                    <span class="ml-1 font-medium text-gray-900">{{ action.temperature }}°</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Schedule Information -->
      <div v-if="scene.schedule" class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-medium text-gray-900">Schedule</h2>
        </div>
        <div class="px-6 py-4">
          <div class="space-y-4">
            <div v-if="scene.schedule.time" class="flex items-center justify-between">
              <span class="text-sm text-gray-500">Daily at</span>
              <span class="text-sm font-medium text-gray-900">{{ scene.schedule.time }}</span>
            </div>
            <div v-if="scene.schedule.days" class="flex items-center justify-between">
              <span class="text-sm text-gray-500">Days</span>
              <span class="text-sm font-medium text-gray-900">{{ scene.schedule.days.join(', ') }}</span>
            </div>
            <div v-if="scene.schedule.enabled !== undefined" class="flex items-center justify-between">
              <span class="text-sm text-gray-500">Status</span>
              <span :class="scene.schedule.enabled ? 'text-green-600' : 'text-red-600'" class="text-sm font-medium">
                {{ scene.schedule.enabled ? 'Enabled' : 'Disabled' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-12">
      <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">Scene not found</h3>
      <p class="mt-1 text-sm text-gray-500">The requested scene could not be found.</p>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

export default {
  name: 'SceneDetail',
  setup() {
    const route = useRoute()
    const scene = ref(null)
    const loading = ref(true)
    const error = ref(null)
    const activating = ref(false)

    const fetchScene = async () => {
      try {
        loading.value = true
        error.value = null
        const response = await axios.get(`/api/scenes/${route.params.id}`)
        scene.value = response.data
      } catch (err) {
        error.value = err.response?.data?.message || 'Failed to load scene'
        console.error('Error fetching scene:', err)
      } finally {
        loading.value = false
      }
    }

    const activateScene = async () => {
      if (!scene.value || activating.value) return
      
      try {
        activating.value = true
        await axios.post(`/api/scenes/${scene.value.id}/activate`)
        
        // Update local state
        scene.value.active = true
        scene.value.lastActivated = new Date().toISOString()
        if (scene.value.activationCount) {
          scene.value.activationCount++
        } else {
          scene.value.activationCount = 1
        }
      } catch (err) {
        console.error('Error activating scene:', err)
      } finally {
        activating.value = false
      }
    }

    const getSceneIconClass = (type) => {
      const classes = {
        morning: 'bg-yellow-500',
        evening: 'bg-indigo-500',
        night: 'bg-purple-900',
        party: 'bg-pink-500',
        relax: 'bg-green-500',
        work: 'bg-blue-500',
        default: 'bg-gray-500'
      }
      return classes[type] || classes.default
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

    const formatSchedule = (schedule) => {
      if (!schedule) return 'Manual'
      if (schedule.time) {
        return `Daily at ${schedule.time}`
      }
      if (schedule.cron) {
        return 'Custom schedule'
      }
      return 'Scheduled'
    }

    const formatDate = (dateString) => {
      return new Date(dateString).toLocaleString()
    }

    onMounted(() => {
      fetchScene()
    })

    return {
      scene,
      loading,
      error,
      activating,
      activateScene,
      getSceneIconClass,
      getDeviceIconClass,
      formatSchedule,
      formatDate
    }
  }
}
</script>

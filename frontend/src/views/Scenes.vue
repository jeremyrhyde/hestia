<template>
  <div class="container mx-auto px-4 py-8">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900">Scenes</h1>
      <p class="mt-2 text-gray-600">Manage and activate automation scenes</p>
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
          <h3 class="text-sm font-medium text-red-800">Error loading scenes</h3>
          <div class="mt-2 text-sm text-red-700">
            <p>{{ error }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else>
      <!-- Scenes Grid -->
      <div v-if="scenes.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="scene in scenes"
          :key="scene.id"
          class="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-200"
        >
          <div class="p-6">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div :class="getSceneIconClass(scene.type)" class="w-12 h-12 rounded-full flex items-center justify-center">
                    <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path v-if="scene.type === 'morning'" d="M10 2L13.09 8.26L20 9L14 14.74L15.18 21.02L10 18L4.82 21.02L6 14.74L0 9L6.91 8.26L10 2Z"/>
                      <path v-else-if="scene.type === 'evening'" d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
                      <path v-else-if="scene.type === 'party'" d="M9 12a1 1 0 102 0V8a1 1 0 10-2 0v4zm6-8a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h10z"/>
                      <path v-else d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v3h8v-3z"/>
                    </svg>
                  </div>
                </div>
                <div class="ml-4">
                  <h3 class="text-lg font-medium text-gray-900">{{ scene.name }}</h3>
                  <p class="text-sm text-gray-500 capitalize">{{ scene.type || 'Custom' }}</p>
                </div>
              </div>
              <div class="flex items-center">
                <span
                  :class="scene.active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'"
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                >
                  {{ scene.active ? 'Active' : 'Inactive' }}
                </span>
              </div>
            </div>

            <div class="space-y-3">
              <p v-if="scene.description" class="text-sm text-gray-600">{{ scene.description }}</p>
              
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500">Devices</span>
                <span class="text-gray-900 font-medium">{{ scene.devices?.length || 0 }}</span>
              </div>

              <div v-if="scene.schedule" class="flex items-center justify-between text-sm">
                <span class="text-gray-500">Schedule</span>
                <span class="text-gray-900 font-medium">{{ formatSchedule(scene.schedule) }}</span>
              </div>

              <div v-if="scene.lastActivated" class="flex items-center justify-between text-sm">
                <span class="text-gray-500">Last Run</span>
                <span class="text-gray-900 font-medium">{{ formatDate(scene.lastActivated) }}</span>
              </div>
            </div>

            <!-- Scene Actions -->
            <div class="mt-6 flex space-x-3">
              <button
                @click="activateScene(scene)"
                :disabled="scene.activating"
                class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="scene.activating" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
                Activate
              </button>
              <button
                @click="$router.push(`/scenes/${scene.id}`)"
                class="inline-flex items-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900">No scenes found</h3>
        <p class="mt-1 text-sm text-gray-500">No automation scenes have been configured yet.</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import axios from 'axios'

export default {
  name: 'Scenes',
  setup() {
    const scenes = ref([])
    const loading = ref(true)
    const error = ref(null)

    const fetchScenes = async () => {
      try {
        loading.value = true
        error.value = null
        const response = await axios.get('/api/scenes')
        scenes.value = response.data
      } catch (err) {
        error.value = err.response?.data?.message || 'Failed to load scenes'
        console.error('Error fetching scenes:', err)
      } finally {
        loading.value = false
      }
    }

    const activateScene = async (scene) => {
      if (scene.activating) return
      
      try {
        scene.activating = true
        await axios.post(`/api/scenes/${scene.id}/activate`)
        
        // Update local state
        scene.active = true
        scene.lastActivated = new Date().toISOString()
        
        // Deactivate other scenes if this is an exclusive scene
        if (scene.exclusive) {
          scenes.value.forEach(s => {
            if (s.id !== scene.id) {
              s.active = false
            }
          })
        }
      } catch (err) {
        console.error('Error activating scene:', err)
        // You might want to show a toast notification here
      } finally {
        scene.activating = false
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
      const date = new Date(dateString)
      const now = new Date()
      const diffMs = now - date
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMins / 60)
      const diffDays = Math.floor(diffHours / 24)

      if (diffMins < 1) return 'Just now'
      if (diffMins < 60) return `${diffMins}m ago`
      if (diffHours < 24) return `${diffHours}h ago`
      if (diffDays < 7) return `${diffDays}d ago`
      return date.toLocaleDateString()
    }

    onMounted(() => {
      fetchScenes()
    })

    return {
      scenes,
      loading,
      error,
      activateScene,
      getSceneIconClass,
      formatSchedule,
      formatDate
    }
  }
}
</script>

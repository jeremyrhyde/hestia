<template>
  <div id="app" class="min-h-screen bg-gray-100">
    <nav class="bg-white shadow-lg">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <router-link to="/" class="flex-shrink-0 flex items-center">
              <h1 class="text-xl font-bold text-gray-900">Hera Home Automation</h1>
            </router-link>
          </div>
          
          <div class="flex items-center space-x-4">
            <router-link 
              to="/" 
              class="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
              :class="{ 'bg-gray-200': $route.path === '/' }"
            >
              Dashboard
            </router-link>
            <router-link 
              to="/rooms" 
              class="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
              :class="{ 'bg-gray-200': $route.path.startsWith('/rooms') }"
            >
              Rooms
            </router-link>
            <router-link 
              to="/devices" 
              class="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
              :class="{ 'bg-gray-200': $route.path.startsWith('/devices') }"
            >
              Devices
            </router-link>
            <router-link 
              to="/scenes" 
              class="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
              :class="{ 'bg-gray-200': $route.path.startsWith('/scenes') }"
            >
              Scenes
            </router-link>
            
            <!-- Connection Status Indicator -->
            <div class="flex items-center space-x-2">
              <div 
                :class="[
                  'w-3 h-3 rounded-full',
                  connectionStore.isConnected ? 'bg-green-500' : 'bg-red-500'
                ]"
                :title="connectionStore.isConnected ? 'Connected' : 'Disconnected'"
              ></div>
              <span class="text-sm text-gray-600">
                {{ connectionStore.isConnected ? 'Online' : 'Offline' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <main class="max-w-7xl mx-auto py-6 px-4">
      <router-view />
    </main>

    <!-- Global Loading Overlay -->
    <div 
      v-if="appStore.isLoading" 
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
    >
      <div class="bg-white rounded-lg p-6 flex items-center space-x-3">
        <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
        <span class="text-gray-700">{{ appStore.loadingMessage || 'Loading...' }}</span>
      </div>
    </div>

    <!-- Global Notifications -->
    <div class="fixed top-4 right-4 z-40 space-y-2">
      <div
        v-for="notification in appStore.notifications"
        :key="notification.id"
        :class="[
          'max-w-sm w-full bg-white shadow-lg rounded-lg pointer-events-auto ring-1 ring-black ring-opacity-5 overflow-hidden',
          'transform transition-all duration-300 ease-in-out'
        ]"
      >
        <div class="p-4">
          <div class="flex items-start">
            <div class="flex-shrink-0">
              <div 
                :class="[
                  'w-6 h-6 rounded-full flex items-center justify-center',
                  notification.type === 'success' ? 'bg-green-100' : 
                  notification.type === 'error' ? 'bg-red-100' : 
                  notification.type === 'warning' ? 'bg-yellow-100' : 'bg-blue-100'
                ]"
              >
                <span 
                  :class="[
                    'text-sm',
                    notification.type === 'success' ? 'text-green-600' : 
                    notification.type === 'error' ? 'text-red-600' : 
                    notification.type === 'warning' ? 'text-yellow-600' : 'text-blue-600'
                  ]"
                >
                  {{ notification.type === 'success' ? '✓' : 
                     notification.type === 'error' ? '✕' : 
                     notification.type === 'warning' ? '⚠' : 'ℹ' }}
                </span>
              </div>
            </div>
            <div class="ml-3 w-0 flex-1 pt-0.5">
              <p class="text-sm font-medium text-gray-900">
                {{ notification.title }}
              </p>
              <p v-if="notification.message" class="mt-1 text-sm text-gray-500">
                {{ notification.message }}
              </p>
            </div>
            <div class="ml-4 flex-shrink-0 flex">
              <button
                @click="appStore.removeNotification(notification.id)"
                class="bg-white rounded-md inline-flex text-gray-400 hover:text-gray-500 focus:outline-none"
              >
                <span class="sr-only">Close</span>
                <span class="text-xl">&times;</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { useConnectionStore } from '@/stores/connection'

const appStore = useAppStore()
const connectionStore = useConnectionStore()

onMounted(() => {
  // Initialize WebSocket connection
  connectionStore.connect()
  
  // Load initial data
  appStore.initialize()
})

onUnmounted(() => {
  // Clean up WebSocket connection
  connectionStore.disconnect()
})
</script>

<style scoped>
/* Component-specific styles can go here */
</style>

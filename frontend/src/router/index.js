import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Dashboard',
      component: Dashboard,
      meta: {
        title: 'Dashboard'
      }
    },
    {
      path: '/rooms',
      name: 'Rooms',
      component: () => import('@/views/Rooms.vue'),
      meta: {
        title: 'Rooms'
      }
    },
    {
      path: '/rooms/:id',
      name: 'RoomDetail',
      component: () => import('@/views/RoomDetail.vue'),
      meta: {
        title: 'Room Details'
      }
    },
    {
      path: '/devices',
      name: 'Devices',
      component: () => import('@/views/Devices.vue'),
      meta: {
        title: 'Devices'
      }
    },
    {
      path: '/devices/:id',
      name: 'DeviceDetail',
      component: () => import('@/views/DeviceDetail.vue'),
      meta: {
        title: 'Device Details'
      }
    },
    {
      path: '/scenes',
      name: 'Scenes',
      component: () => import('@/views/Scenes.vue'),
      meta: {
        title: 'Scenes'
      }
    },
    {
      path: '/scenes/:id',
      name: 'SceneDetail',
      component: () => import('@/views/SceneDetail.vue'),
      meta: {
        title: 'Scene Details'
      }
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('@/views/Settings.vue'),
      meta: {
        title: 'Settings'
      }
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound.vue'),
      meta: {
        title: 'Page Not Found'
      }
    }
  ]
})

// Update document title based on route
router.beforeEach((to, from, next) => {
  const baseTitle = 'Hera Home Automation'
  document.title = to.meta.title ? `${to.meta.title} - ${baseTitle}` : baseTitle
  next()
})

export default router

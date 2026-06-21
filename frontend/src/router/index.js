import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
  },
  {
    path: '/employee',
    name: 'EmployeeLayout',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { role: 'employee' },
    children: [
      {
        path: '',
        name: 'EmployeeDashboard',
        component: () => import('@/views/employee/EmployeeDashboard.vue'),
      },
      {
        path: 'input',
        name: 'EmployeeInput',
        component: () => import('@/views/employee/EmployeeInput.vue'),
      },
    ],
  },
  {
    path: '/manager',
    name: 'ManagerLayout',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { role: 'manager' },
    children: [
      {
        path: '',
        name: 'ManagerDashboard',
        component: () => import('@/views/manager/ManagerDashboard.vue'),
      },
      {
        path: 'approval/:id',
        name: 'ApprovalDetail',
        component: () => import('@/views/manager/ApprovalDetail.vue'),
      },
    ],
  },
  {
    path: '/',
    redirect: '/login',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.path === '/login') {
    next()
    return
  }
  if (!auth.isLoggedIn) {
    next('/login')
    return
  }
  next()
})

export default router

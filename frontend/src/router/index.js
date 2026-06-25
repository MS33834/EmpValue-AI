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
    meta: { role: ['employee'] },
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
      {
        path: 'history',
        name: 'EmployeeHistory',
        component: () => import('@/views/employee/EmployeeHistory.vue'),
        meta: { title: '历史评估' },
      },
      {
        path: 'feedback',
        name: 'EmployeeFeedback',
        component: () => import('@/views/employee/EmployeeFeedback.vue'),
        meta: { title: '反馈申诉' },
      },
    ],
  },
  {
    path: '/manager',
    name: 'ManagerLayout',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { role: ['manager', 'hr', 'admin'] },
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
      {
        path: 'team',
        name: 'TeamAnalytics',
        component: () => import('@/views/manager/TeamAnalytics.vue'),
        meta: { title: '团队分析' },
      },
    ],
  },
  {
    path: '/hr',
    name: 'HRLayout',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { role: ['hr'] },
    children: [
      {
        path: '',
        name: 'HRDashboard',
        component: () => import('@/views/hr/HRDashboard.vue'),
        meta: { title: 'HR复核' },
      },
    ],
  },
  {
    path: '/admin',
    name: 'AdminLayout',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { role: ['admin'] },
    children: [
      {
        path: '',
        name: 'AdminModel',
        component: () => import('@/views/admin/AdminModel.vue'),
        meta: { title: '模型管理' },
      },
      {
        path: 'audit-logs',
        name: 'AdminAuditLogs',
        component: () => import('@/views/admin/AdminAuditLogs.vue'),
        meta: { title: '审计日志' },
      },
    ],
  },
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

let authChecked = false

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()
  if (to.path === '/login') {
    next()
    return
  }
  if (!auth.isLoggedIn) {
    authChecked = false
    next('/login')
    return
  }
  if (!authChecked) {
    authChecked = true
    const ok = await auth.checkAuth()
    if (!ok) {
      next('/login')
      return
    }
  }
  const requiredRole = to.meta.role || to.matched.find((r) => r.meta.role)?.meta.role
  if (requiredRole) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole]
    if (!roles.includes(auth.role)) {
      next('/login')
      return
    }
  }
  next()
})

export default router

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '../store/authStore'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // 120 s — EasyOCR can take ~45 s on first CPU load; text/URL calls are fast.
  timeout: 120_000,
})

// Separate client for image uploads: OCR + model load can take up to 90 s on CPU.
export const imageApiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 180_000,
})

// ── Shared interceptor factory ────────────────────────────────────────────────
function applyInterceptors(client: ReturnType<typeof axios.create>) {
  client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = useAuthStore.getState().token
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    },
    (error: AxiosError) => Promise.reject(error),
  )

  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      if (error.response?.status === 401) {
        useAuthStore.getState().logout()
      }
      return Promise.reject(error)
    },
  )
}

applyInterceptors(apiClient)
applyInterceptors(imageApiClient)

export default apiClient

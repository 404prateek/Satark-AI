import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import apiClient from '../api/client'

// ── Types ──────────────────────────────────────────────────────────────────────
export type UserRole = 'admin' | 'analyst' | 'viewer'

export interface AuthUser {
  id: string
  email: string
  username: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface LoginApiResponse {
  message: string
  user: AuthUser
  token: {
    access_token: string
    token_type: string
    expires_in: number
  }
}

// ── Store shape ────────────────────────────────────────────────────────────────
interface AuthState {
  token: string | null
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  login: (payload: LoginPayload) => Promise<void>
  setAuthData: (token: string, user: AuthUser) => void
  logout: () => void
  clearError: () => void
}

// ── Store ──────────────────────────────────────────────────────────────────────
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (payload: LoginPayload) => {
        set({ isLoading: true, error: null })
        try {
          const { data } = await apiClient.post<LoginApiResponse>('/auth/login', payload)
          set({
            token: data.token.access_token,
            user: data.user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
        } catch (err: unknown) {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response?.data
              ?.detail ?? 'Login failed. Please try again.'
          set({ isLoading: false, error: message, isAuthenticated: false })
          throw err
        }
      },

      setAuthData: (token: string, user: AuthUser) => {
        set({ token, user, isAuthenticated: true, error: null })
      },

      logout: () => {
        set({ token: null, user: null, isAuthenticated: false, error: null })
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'satark-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ token: state.token, user: state.user, isAuthenticated: state.isAuthenticated }),
    },
  ),
)

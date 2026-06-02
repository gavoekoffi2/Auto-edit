import { useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { getMe } from '../api/auth'

export function useAuth() {
  const { accessToken, user, setUser, logout } = useAuthStore()

  useEffect(() => {
    if (accessToken && !user) {
      getMe()
        .then(setUser)
        .catch(() => logout())
    }
  }, [accessToken, user, setUser, logout])

  return {
    isAuthenticated: !!accessToken,
    user,
    logout,
  }
}

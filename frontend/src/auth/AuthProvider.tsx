import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { login as loginApi, me as meApi, logout as logoutApi } from '../api/auth'
import { AuthContext } from './useAuth'
import type { AuthContextValue } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const meQuery = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        const res = await meApi()
        return res.user
      } catch {
        return null
      }
    },
    retry: false,
  })

  const loginMutation = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      loginApi({ email, password }).then((res) => res.user),
    onSuccess: (user) => {
      queryClient.setQueryData(['me'], user)
    },
  })

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await logoutApi()
    },
    onSuccess: () => {
      queryClient.setQueryData(['me'], null)
      queryClient.clear()
    },
  })

  const value: AuthContextValue = {
    user: meQuery.data ?? null,
    isLoading: meQuery.isLoading,
    login: (email: string, password: string) => loginMutation.mutateAsync({ email, password }),
    logout: () => logoutMutation.mutateAsync(),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

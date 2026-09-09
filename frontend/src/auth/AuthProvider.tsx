import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { googleLogin, login as loginApi, me as meApi, logout as logoutApi } from '../api/auth'
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
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['me'] })
    },
    onSuccess: async (user) => {
      await queryClient.cancelQueries({ queryKey: ['me'] })
      queryClient.setQueryData(['me'], user)
    },
  })

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await logoutApi()
    },
    onSuccess: async () => {
      window.google?.accounts.id.disableAutoSelect()
      await queryClient.cancelQueries()
      queryClient.setQueryData(['me'], null)
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'me' })
    },
  })

  const googleMutation = useMutation({
    mutationFn: (credential: string) => googleLogin(credential).then((res) => res.user),
    onSuccess: async (user) => {
      await queryClient.cancelQueries({ queryKey: ['me'] })
      queryClient.setQueryData(['me'], user)
    },
  })

  const value: AuthContextValue = {
    user: meQuery.data ?? null,
    isLoading: meQuery.isLoading,
    login: (email: string, password: string) => loginMutation.mutateAsync({ email, password }),
    loginWithGoogle: (credential: string) => googleMutation.mutateAsync(credential),
    logout: () => logoutMutation.mutateAsync(),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { initI18n } from './lib/i18n'
import { queryClient } from './lib/queryClient'
import { router } from './App'
import './styles/global.css'

initI18n()

const savedTheme = localStorage.getItem('novamart_theme')
if (savedTheme === 'dark') {
  document.documentElement.dataset.theme = 'dark'
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)

import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { ToastProvider } from './components/Toast'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Cache reads for 30s — feels instant on mobile when navigating tabs
      staleTime: 30_000,
      // Keep data around so the previous view shows immediately on revisit
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
      // Important for PWAs / flaky mobile networks
      networkMode: 'offlineFirst',
    },
    mutations: {
      retry: 0,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>
)

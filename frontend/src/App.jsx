import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'

const Library      = lazy(() => import('./pages/Library'))
const Scraper      = lazy(() => import('./pages/Scraper'))
const Editor       = lazy(() => import('./pages/Editor'))
const CreateListing = lazy(() => import('./pages/CreateListing'))
const Audit        = lazy(() => import('./pages/Audit'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center py-20 text-gray-400">
      <svg className="w-6 h-6 animate-spin" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
    </div>
  )
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/',        element: <Suspense fallback={<PageLoader />}><Library /></Suspense> },
      { path: '/scraper', element: <Suspense fallback={<PageLoader />}><Scraper /></Suspense> },
      { path: '/create',  element: <Suspense fallback={<PageLoader />}><CreateListing /></Suspense> },
      { path: '/edit/:id', element: <Suspense fallback={<PageLoader />}><Editor /></Suspense> },
      { path: '/audit',   element: <Suspense fallback={<PageLoader />}><Audit /></Suspense> },
    ],
  },
])

export default function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
    </ErrorBoundary>
  )
}

import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './components/Layout'
import Library from './pages/Library'
import Scraper from './pages/Scraper'
import Editor from './pages/Editor'
import ErrorBoundary from './components/ErrorBoundary'

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Library /> },
      { path: '/scraper', element: <Scraper /> },
      { path: '/edit/:id', element: <Editor /> },
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

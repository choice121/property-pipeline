import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './components/Layout'
import Library from './pages/Library'
import Scraper from './pages/Scraper'
import Editor from './pages/Editor'

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
  return <RouterProvider router={router} />
}

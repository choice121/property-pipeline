import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      includeAssets: ['favicon.svg'],
      manifest: false, // we ship our own at /manifest.webmanifest
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,webp}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            // Cache transformed ImageKit images on the device
            urlPattern: /^https:\/\/ik\.imagekit\.io\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'imagekit-cache',
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // Local proxied / app-served images
            urlPattern: /^\/api\/(images|proxy-image).*/i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'app-images',
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
          {
            // Read-only listing data — works offline once seen
            urlPattern: /^\/api\/(properties|setup\/status).*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-data',
              networkTimeoutSeconds: 4,
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  root: 'frontend',
  publicDir: 'public',
  server: {
    host: '0.0.0.0',
    port: 5000,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
    watch: {
      ignored: ['**/.local/**', '**/.cache/**'],
    },
  },
  define: {
    'import.meta.env.VITE_IMAGEKIT_URL_ENDPOINT': JSON.stringify(
      process.env.IMAGEKIT_URL_ENDPOINT || 'https://ik.imagekit.io/21rg7lvzo'
    ),
  },
})

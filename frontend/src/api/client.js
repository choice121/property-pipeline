import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

export const createProperty = (data) => api.post('/properties', data)
export const scrapeProperties = (data) => api.post('/scrape', data)
export const getProperties = (params) => api.get('/properties', { params })
export const getProperty = (id) => api.get('/properties/' + id)
export const updateProperty = (id, data) => api.put('/properties/' + id, data)
export const deleteProperty = (id) => api.delete('/properties/' + id)
export const deleteImage = (id, index) => api.delete('/properties/' + id + '/images/' + index)
export const reorderImages = (id, order) => api.put('/properties/' + id + '/images/reorder', { order })
export const bulkAction = (ids, action) => api.post('/properties/bulk-action', { ids, action })
export const publishProperty   = (id) => api.post('/publish/' + id)
export const refreshImages    = (id) => api.post('/publish/' + id + '/refresh-images')
export const syncFields       = (id) => api.post('/publish/' + id + '/sync-fields')
export const setListingStatus = (id, status) => api.post('/publish/' + id + '/set-listing-status', { status })
export const downloadProperty = (id) => api.get('/properties/' + id + '/download', { responseType: 'blob' })
export const searchProperties = (data) => api.post('/search', data)
export const saveProperty = (data) => api.post('/save-property', data)

export const aiRewriteDescription = (data) => api.post('/ai/rewrite-description', data)
export const aiDetectIssues = (data) => api.post('/ai/detect-issues', data)
export const aiSuggestField = (data) => api.post('/ai/suggest-field', data)
export const aiChat = (data) => api.post('/ai/chat', data)
export const aiAutoFill = (data) => api.post('/ai/autofill', data)

export const getLiveImages = (id) => api.get('/live-images/' + id)
export const deleteLiveImage = (id, fileId) => api.delete('/live-images/' + id + '/' + encodeURIComponent(fileId))
export const reorderLiveImages = (id, order) => api.put('/live-images/' + id + '/reorder', { order })
export const uploadLiveImage = (id, formData) => api.post('/live-images/' + id + '/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })

export const syncFromLive = () => api.post('/sync/from-live')
export const getSyncStatus = () => api.get('/sync/status')

export default api

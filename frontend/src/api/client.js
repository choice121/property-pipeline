import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const scrapeProperties = (data) => api.post('/scrape', data)
export const getProperties = (params) => api.get('/properties', { params })
export const getProperty = (id) => api.get('/properties/' + id)
export const updateProperty = (id, data) => api.put('/properties/' + id, data)
export const deleteProperty = (id) => api.delete('/properties/' + id)
export const deleteImage = (id, index) => api.delete('/properties/' + id + '/images/' + index)
export const reorderImages = (id, order) => api.put('/properties/' + id + '/images/reorder', { order })
export const publishProperty = (id) => api.post('/publish/' + id)

export default api

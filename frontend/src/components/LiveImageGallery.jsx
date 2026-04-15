import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getLiveImages, deleteLiveImage, reorderLiveImages, uploadLiveImage } from '../api/client'

export default function LiveImageGallery({ propertyId }) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef(null)
  const [dragIdx, setDragIdx] = useState(null)
  const [overIdx, setOverIdx] = useState(null)
  const [uploadError, setUploadError] = useState(null)

  const queryKey = ['live-images', propertyId]

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => getLiveImages(propertyId).then((r) => r.data),
  })

  const photos = data?.photos || []

  const invalidate = () => queryClient.invalidateQueries({ queryKey })

  const deleteMutation = useMutation({
    mutationFn: (fileId) => deleteLiveImage(propertyId, fileId).then((r) => r.data),
    onSuccess: invalidate,
  })

  const reorderMutation = useMutation({
    mutationFn: (order) => reorderLiveImages(propertyId, order).then((r) => r.data),
    onSuccess: invalidate,
  })

  const uploadMutation = useMutation({
    mutationFn: (file) => {
      const fd = new FormData()
      fd.append('file', file)
      return uploadLiveImage(propertyId, fd).then((r) => r.data)
    },
    onSuccess: () => {
      setUploadError(null)
      invalidate()
    },
    onError: (e) => {
      setUploadError(e?.response?.data?.detail || 'Upload failed')
    },
  })

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    uploadMutation.mutate(file)
    e.target.value = ''
  }

  function handleDragStart(idx) {
    setDragIdx(idx)
  }

  function handleDragOver(e, idx) {
    e.preventDefault()
    setOverIdx(idx)
  }

  function handleDrop(e, idx) {
    e.preventDefault()
    if (dragIdx === null || dragIdx === idx) {
      setDragIdx(null)
      setOverIdx(null)
      return
    }
    const order = photos.map((_, i) => i)
    order.splice(idx, 0, order.splice(dragIdx, 1)[0])
    reorderMutation.mutate(order)
    setDragIdx(null)
    setOverIdx(null)
  }

  function handleDragEnd() {
    setDragIdx(null)
    setOverIdx(null)
  }

  function handleDelete(fileId) {
    if (!window.confirm('Remove this photo from the live site?')) return
    deleteMutation.mutate(fileId)
  }

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading photos...</p>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-500">
          {photos.length} photo{photos.length !== 1 ? 's' : ''} · drag to reorder · changes go live instantly
        </p>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
          className="text-xs px-3 py-1.5 bg-gray-900 text-white rounded-md hover:bg-gray-700 disabled:opacity-50 transition-colors"
        >
          {uploadMutation.isPending ? 'Uploading...' : '+ Add Photo'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/jpg,image/png,image/webp"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {uploadError && (
        <div className="mb-3 text-xs text-red-600 bg-red-50 px-3 py-2 rounded">
          {uploadError}
        </div>
      )}

      {photos.length === 0 ? (
        <div className="border-2 border-dashed border-gray-200 rounded-lg py-10 text-center">
          <p className="text-sm text-gray-400">No photos yet.</p>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="mt-2 text-xs text-gray-500 underline hover:text-gray-700"
          >
            Upload the first photo
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {photos.map((photo, idx) => (
            <div
              key={photo.file_id}
              draggable
              onDragStart={() => handleDragStart(idx)}
              onDragOver={(e) => handleDragOver(e, idx)}
              onDrop={(e) => handleDrop(e, idx)}
              onDragEnd={handleDragEnd}
              className={`relative group rounded-md overflow-hidden aspect-[4/3] bg-gray-100 cursor-grab border-2 transition-colors ${
                overIdx === idx && dragIdx !== idx
                  ? 'border-blue-400'
                  : 'border-transparent'
              }`}
            >
              {idx === 0 && (
                <span className="absolute top-1 left-1 z-10 text-[10px] bg-gray-900 text-white px-1.5 py-0.5 rounded font-medium">
                  Cover
                </span>
              )}
              <img
                src={photo.url}
                alt={`Photo ${idx + 1}`}
                className="w-full h-full object-cover"
                draggable={false}
              />
              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <button
                  onClick={() => handleDelete(photo.file_id)}
                  disabled={deleteMutation.isPending}
                  className="bg-red-500 hover:bg-red-600 text-white text-xs px-2 py-1 rounded disabled:opacity-50"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {reorderMutation.isPending && (
        <p className="mt-2 text-xs text-gray-400">Saving order...</p>
      )}
    </div>
  )
}

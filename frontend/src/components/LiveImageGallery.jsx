import { useRef, useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getLiveImages, deleteLiveImage, reorderLiveImages, uploadLiveImages } from '../api/client'
import { transformImage } from '../utils/imageUrl'

export default function LiveImageGallery({ propertyId }) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef(null)
  const [dragIdx, setDragIdx] = useState(null)
  const [overIdx, setOverIdx] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const [lightbox, setLightbox] = useState(null)

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

  const uploadFiles = useCallback(async (files) => {
    if (!files || files.length === 0) return
    setUploadError(null)
    const validTypes = new Set(['image/jpeg', 'image/jpg', 'image/png', 'image/webp'])
    const valid = Array.from(files).filter((f) => validTypes.has(f.type))
    if (valid.length === 0) {
      setUploadError('No valid images. Use JPEG, PNG, or WebP.')
      return
    }
    const fd = new FormData()
    valid.forEach((f) => fd.append('files', f))
    setIsUploading(true)
    try {
      await uploadLiveImages(propertyId, fd)
      setUploadError(null)
      invalidate()
    } catch (e) {
      setUploadError(e?.response?.data?.detail || 'Upload failed — please try again.')
    } finally {
      setIsUploading(false)
    }
  }, [propertyId])

  function handleFileChange(e) {
    uploadFiles(e.target.files)
    e.target.value = ''
  }

  function handleDropZone(e) {
    e.preventDefault()
    setIsDragOver(false)
    uploadFiles(e.dataTransfer.files)
  }

  // Drag-to-reorder handlers (desktop only)
  function handleDragStart(idx) { setDragIdx(idx) }
  function handleDragOver(e, idx) { e.preventDefault(); setOverIdx(idx) }
  function handleDrop(e, idx) {
    e.preventDefault()
    if (dragIdx === null || dragIdx === idx) { setDragIdx(null); setOverIdx(null); return }
    const order = photos.map((_, i) => i)
    order.splice(idx, 0, order.splice(dragIdx, 1)[0])
    reorderMutation.mutate(order)
    setDragIdx(null); setOverIdx(null)
  }
  function handleDragEnd() { setDragIdx(null); setOverIdx(null) }

  // Mobile reorder: arrow buttons
  function movePhoto(from, to) {
    if (to < 0 || to >= photos.length) return
    const order = photos.map((_, i) => i)
    const [moved] = order.splice(from, 1)
    order.splice(to, 0, moved)
    reorderMutation.mutate(order)
  }

  function handleDelete(fileId, e) {
    e.stopPropagation()
    if (!window.confirm('Remove this photo from the live site?')) return
    deleteMutation.mutate(fileId)
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-gray-400">
        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        Loading photos…
      </div>
    )
  }

  return (
    <div>
      {/* ── Header row ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-500">
          {photos.length} photo{photos.length !== 1 ? 's' : ''}
          {photos.length > 0 && <span className="hidden sm:inline"> · drag to reorder · live instantly</span>}
        </p>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-xl active:scale-95 disabled:opacity-50 transition-all touch-manipulation min-h-[44px]"
        >
          {isUploading ? (
            <>
              <svg className="w-4 h-4 animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Uploading…
            </>
          ) : (
            <>
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
              </svg>
              Add Photos
            </>
          )}
        </button>
        {/* Hidden file input — multiple + image/* triggers native camera roll on mobile */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/jpg,image/png,image/webp"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {/* ── Error banner ────────────────────────────────────────────── */}
      {uploadError && (
        <div className="mb-3 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-100 px-4 py-3 rounded-xl">
          <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1-9v4h2V9H9zm0-4v2h2V5H9z" clipRule="evenodd"/>
          </svg>
          <span className="flex-1">{uploadError}</span>
          <button
            onClick={() => setUploadError(null)}
            className="text-red-400 hover:text-red-600 min-w-[24px] text-center font-bold"
          >×</button>
        </div>
      )}

      {/* ── Empty state — big tap/drop zone ────────────────────────── */}
      {photos.length === 0 ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true) }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDropZone}
          onClick={() => !isUploading && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl py-14 px-6 text-center cursor-pointer transition-colors touch-manipulation ${
            isDragOver
              ? 'border-gray-900 bg-gray-50'
              : 'border-gray-200 hover:border-gray-400 active:bg-gray-50'
          }`}
        >
          {isUploading ? (
            <div className="flex flex-col items-center gap-3">
              <svg className="w-8 h-8 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              <p className="text-sm text-gray-500 font-medium">Uploading photos…</p>
            </div>
          ) : (
            <>
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-gray-100 flex items-center justify-center">
                <svg className="w-7 h-7 text-gray-400" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"/>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z"/>
                </svg>
              </div>
              <p className="text-sm font-semibold text-gray-700">Tap to add photos</p>
              <p className="text-xs text-gray-400 mt-1">
                Choose from your camera roll or files<br className="hidden sm:block"/>
                <span className="sm:hidden"> · </span>
                <span className="hidden sm:inline">or drag &amp; drop · </span>
                JPEG, PNG, WebP · up to 15 MB each
              </p>
            </>
          )}
        </div>
      ) : (
        /* ── Photo grid ─────────────────────────────────────────────── */
        <>
          <div
            onDragOver={(e) => { if (dragIdx === null) { e.preventDefault(); setIsDragOver(true) } }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => { if (dragIdx === null) { setIsDragOver(false); handleDropZone(e) } }}
            className={`grid grid-cols-2 sm:grid-cols-3 gap-2.5 rounded-xl p-1 transition-colors ${isDragOver ? 'bg-blue-50 ring-2 ring-blue-200' : ''}`}
          >
            {photos.map((photo, idx) => (
              <div
                key={photo.file_id}
                draggable
                onDragStart={() => handleDragStart(idx)}
                onDragOver={(e) => handleDragOver(e, idx)}
                onDrop={(e) => handleDrop(e, idx)}
                onDragEnd={handleDragEnd}
                className={`relative rounded-xl overflow-hidden aspect-[4/3] bg-gray-100 border-2 transition-all ${
                  overIdx === idx && dragIdx !== idx
                    ? 'border-blue-400 scale-105'
                    : dragIdx === idx
                    ? 'border-gray-400 opacity-50'
                    : 'border-transparent'
                }`}
              >
                {/* Cover badge */}
                {idx === 0 && (
                  <span className="absolute top-2 left-2 z-10 text-[10px] font-bold bg-gray-900/80 text-white px-2 py-0.5 rounded-full backdrop-blur-sm">
                    Cover
                  </span>
                )}

                {/* Photo number */}
                <span className="absolute top-2 right-2 z-10 text-[10px] font-medium bg-black/50 text-white px-1.5 py-0.5 rounded-full backdrop-blur-sm">
                  {idx + 1}
                </span>

                {/* Tap to view */}
                <button
                  type="button"
                  onClick={() => setLightbox(idx)}
                  className="absolute inset-0 w-full h-full touch-manipulation"
                  aria-label={`View photo ${idx + 1}`}
                >
                  <img
                    src={transformImage(photo.url, { w: 400, q: 75 })}
                    srcSet={`${transformImage(photo.url, { w: 300, q: 70 })} 300w, ${transformImage(photo.url, { w: 500, q: 75 })} 500w`}
                    sizes="(max-width: 640px) 50vw, 33vw"
                    alt={`Photo ${idx + 1}`}
                    loading="lazy"
                    decoding="async"
                    className="w-full h-full object-cover"
                    draggable={false}
                  />
                </button>

                {/* Bottom action bar — always visible on mobile */}
                <div className="absolute bottom-0 inset-x-0 flex items-center justify-between px-1.5 py-1 bg-gradient-to-t from-black/70 to-transparent">
                  {/* Move left */}
                  <button
                    onClick={(e) => { e.stopPropagation(); movePhoto(idx, idx - 1) }}
                    disabled={idx === 0 || reorderMutation.isPending}
                    className="w-7 h-7 flex items-center justify-center rounded-full bg-white/20 text-white active:bg-white/40 disabled:opacity-0 transition-all touch-manipulation"
                    aria-label="Move left"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5"/>
                    </svg>
                  </button>

                  {/* Delete */}
                  <button
                    onClick={(e) => handleDelete(photo.file_id, e)}
                    disabled={deleteMutation.isPending}
                    className="w-7 h-7 flex items-center justify-center rounded-full bg-red-500/80 text-white active:bg-red-600 disabled:opacity-50 transition-all touch-manipulation"
                    aria-label="Delete photo"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
                    </svg>
                  </button>

                  {/* Move right */}
                  <button
                    onClick={(e) => { e.stopPropagation(); movePhoto(idx, idx + 1) }}
                    disabled={idx === photos.length - 1 || reorderMutation.isPending}
                    className="w-7 h-7 flex items-center justify-center rounded-full bg-white/20 text-white active:bg-white/40 disabled:opacity-0 transition-all touch-manipulation"
                    aria-label="Move right"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>
                    </svg>
                  </button>
                </div>
              </div>
            ))}

            {/* Add more tile */}
            <button
              type="button"
              onClick={() => !isUploading && fileInputRef.current?.click()}
              disabled={isUploading}
              className="relative rounded-xl aspect-[4/3] border-2 border-dashed border-gray-200 hover:border-gray-400 active:bg-gray-50 transition-all flex flex-col items-center justify-center gap-1 touch-manipulation disabled:opacity-50"
            >
              {isUploading ? (
                <svg className="w-5 h-5 text-gray-400 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
              ) : (
                <>
                  <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4"/>
                  </svg>
                  <span className="text-[10px] text-gray-400 font-medium">Add more</span>
                </>
              )}
            </button>
          </div>

          {reorderMutation.isPending && (
            <p className="mt-2 text-xs text-gray-400 text-center">Saving order…</p>
          )}
        </>
      )}

      {/* ── Lightbox ────────────────────────────────────────────────── */}
      {lightbox != null && (
        <div
          className="fixed inset-0 z-[70] bg-black/95 flex items-center justify-center"
          onClick={() => setLightbox(null)}
        >
          {/* Close */}
          <button
            onClick={() => setLightbox(null)}
            className="absolute top-4 right-4 z-10 w-10 h-10 flex items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 active:bg-white/30 touch-manipulation"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>

          {/* Prev */}
          {lightbox > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); setLightbox(lightbox - 1) }}
              className="absolute left-3 z-10 w-10 h-10 flex items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 active:bg-white/30 touch-manipulation"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5"/>
              </svg>
            </button>
          )}

          <img
            src={transformImage(photos[lightbox]?.url, { w: 1200, q: 90 })}
            alt={`Photo ${lightbox + 1}`}
            className="max-h-[90dvh] max-w-[95vw] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />

          {/* Next */}
          {lightbox < photos.length - 1 && (
            <button
              onClick={(e) => { e.stopPropagation(); setLightbox(lightbox + 1) }}
              className="absolute right-3 z-10 w-10 h-10 flex items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 active:bg-white/30 touch-manipulation"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>
              </svg>
            </button>
          )}

          {/* Counter */}
          <div className="absolute bottom-5 left-0 right-0 text-center text-white/60 text-sm">
            {lightbox + 1} / {photos.length}
          </div>
        </div>
      )}
    </div>
  )
}

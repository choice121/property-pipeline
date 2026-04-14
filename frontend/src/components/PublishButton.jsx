import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { publishProperty, syncFields, refreshImages } from '../api/client'

function parseArray(value) {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value || '[]') : value
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export default function PublishButton({ property, onPublished }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const [syncDone, setSyncDone] = useState(false)
  const [refreshDone, setRefreshDone] = useState(false)
  const missingFields = parseArray(property.missing_fields)
  const qualityScore = property.data_quality_score

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['properties'] })
    queryClient.invalidateQueries({ queryKey: ['property', property.id] })
  }

  const publishMutation = useMutation({
    mutationFn: () => publishProperty(property.id).then((r) => r.data),
    onSuccess: (data) => {
      setConfirming(false)
      invalidate()
      if (onPublished) onPublished(data)
    },
  })

  // PIPE-10 FIX: sync edited fields back to live Supabase record
  const syncMutation = useMutation({
    mutationFn: () => syncFields(property.id).then((r) => r.data),
    onSuccess: () => { setSyncDone(true); invalidate(); setTimeout(() => setSyncDone(false), 3000) },
  })

  // Refresh images on already-published listing
  const refreshMutation = useMutation({
    mutationFn: () => refreshImages(property.id).then((r) => r.data),
    onSuccess: () => { setRefreshDone(true); invalidate(); setTimeout(() => setRefreshDone(false), 3000) },
  })

  // ── Already published ──────────────────────────────────────────────────────
  if (property.status === 'published' || property.choice_property_id) {
    return (
      <div className="flex flex-col gap-2">
        {/* Published status badge */}
        <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
          <svg className="w-4 h-4 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <div>
            <p className="text-sm font-medium text-green-700">Published to Choice Properties</p>
            {property.choice_property_id && (
              <p className="text-xs text-green-500 font-mono">{property.choice_property_id}</p>
            )}
            {property.published_at && (
              <p className="text-xs text-green-500">{new Date(property.published_at).toLocaleString()}</p>
            )}
          </div>
        </div>

        {/* Sync fields button */}
        <div className="flex gap-2">
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 transition-colors"
          >
            {syncMutation.isPending ? (
              <><svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg> Syncing…</>
            ) : syncDone ? (
              <><svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg> Synced!</>
            ) : (
              <><svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Sync Fields to Live Site</>
            )}
          </button>

          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-gray-300 bg-gray-50 text-gray-700 hover:bg-gray-100 disabled:opacity-50 transition-colors"
          >
            {refreshMutation.isPending ? (
              <><svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg> Uploading…</>
            ) : refreshDone ? (
              <><svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg> Done!</>
            ) : (
              <><svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg> Refresh Photos</>
            )}
          </button>
        </div>

        {/* Error states */}
        {syncMutation.isError && (
          <p className="text-xs text-red-600">{syncMutation.error?.response?.data?.detail || 'Sync failed.'}</p>
        )}
        {refreshMutation.isError && (
          <p className="text-xs text-red-600">{refreshMutation.error?.response?.data?.detail || 'Refresh failed.'}</p>
        )}
      </div>
    )
  }

  // ── Not ready yet ──────────────────────────────────────────────────────────
  if (property.status !== 'ready') return null

  // ── Just published ─────────────────────────────────────────────────────────
  if (publishMutation.isSuccess) {
    const wasDuplicate = publishMutation.data?.was_duplicate
    return (
      <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
        <svg className="w-4 h-4 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <p className="text-sm font-medium text-green-700">
          {wasDuplicate
            ? 'Duplicate detected — linked to existing listing.'
            : 'Published successfully — listing is now live.'}
        </p>
      </div>
    )
  }

  // ── Confirm dialog ─────────────────────────────────────────────────────────
  if (confirming) {
    return (
      <div className="flex flex-col gap-2 p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <p className="text-sm font-medium text-amber-800">
          This will upload all images and push the listing live to Choice Properties immediately. Continue?
        </p>
        {(qualityScore != null || missingFields.length > 0) && (
          <div className="text-xs text-amber-700 bg-white/70 border border-amber-100 rounded-md px-3 py-2">
            {qualityScore != null && <p className="font-medium">Completeness: {qualityScore}%</p>}
            {missingFields.length > 0 && (
              <p className="mt-1">Still missing: {missingFields.slice(0, 8).join(', ')}{missingFields.length > 8 ? '…' : ''}</p>
            )}
          </div>
        )}
        <div className="flex gap-2">
          <button
            onClick={() => publishMutation.mutate()}
            disabled={publishMutation.isPending}
            className="bg-green-600 text-white px-4 py-1.5 rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {publishMutation.isPending ? 'Publishing…' : 'Yes, Publish Now'}
          </button>
          <button
            onClick={() => setConfirming(false)}
            disabled={publishMutation.isPending}
            className="bg-white border border-gray-300 text-gray-700 px-4 py-1.5 rounded-md text-sm font-medium hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
        </div>
        {publishMutation.isPending && (
          <p className="text-xs text-amber-600">Uploading images and publishing… this may take a moment.</p>
        )}
        {publishMutation.isError && (
          <p className="text-sm text-red-600 mt-1">
            {publishMutation.error?.response?.data?.detail || publishMutation.error?.message || 'Publish failed. Please try again.'}
          </p>
        )}
      </div>
    )
  }

  // ── Idle publish button ────────────────────────────────────────────────────
  return (
    <button
      onClick={() => setConfirming(true)}
      className="flex items-center gap-2 bg-green-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      Publish to Choice Properties
    </button>
  )
}

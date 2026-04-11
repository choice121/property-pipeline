import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { publishProperty } from '../api/client'

export default function PublishButton({ property, onPublished }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)

  const publishMutation = useMutation({
    mutationFn: () => publishProperty(property.id).then((r) => r.data),
    onSuccess: (data) => {
      setConfirming(false)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      queryClient.invalidateQueries({ queryKey: ['property', property.id] })
      if (onPublished) onPublished(data)
    },
  })

  if (property.status === 'published' || property.choice_property_id) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
        <svg className="w-4 h-4 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <div>
          <p className="text-sm font-medium text-green-700">Published to Choice Properties</p>
          {property.published_at && (
            <p className="text-xs text-green-500">
              {new Date(property.published_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>
    )
  }

  if (property.status !== 'ready') {
    return null
  }

  if (publishMutation.isSuccess) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
        <svg className="w-4 h-4 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <p className="text-sm font-medium text-green-700">Published successfully — listing is now live.</p>
      </div>
    )
  }

  if (confirming) {
    return (
      <div className="flex flex-col gap-2 p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <p className="text-sm font-medium text-amber-800">
          This will upload all images and push the listing live to Choice Properties immediately. Continue?
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => publishMutation.mutate()}
            disabled={publishMutation.isPending}
            className="bg-green-600 text-white px-4 py-1.5 rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {publishMutation.isPending ? 'Publishing...' : 'Yes, Publish Now'}
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
          <p className="text-xs text-amber-600">Uploading images and publishing... this may take a moment.</p>
        )}
        {publishMutation.isError && (
          <p className="text-sm text-red-600 mt-1">
            {publishMutation.error?.response?.data?.detail || publishMutation.error?.message || 'Publish failed. Please try again.'}
          </p>
        )}
      </div>
    )
  }

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

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSyncStatus, syncFromLive } from '../api/client'

function timeAgo(isoString) {
  if (!isoString) return null
  const diff = Math.floor((Date.now() - new Date(isoString + 'Z').getTime()) / 1000)
  if (diff < 10) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export default function SyncStatus() {
  const queryClient = useQueryClient()

  const { data: status } = useQuery({
    queryKey: ['sync-status'],
    queryFn: () => getSyncStatus().then((r) => r.data),
    refetchInterval: 30000,
  })

  const syncMutation = useMutation({
    mutationFn: () => syncFromLive().then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sync-status'] })
      queryClient.invalidateQueries({ queryKey: ['properties'] })
    },
  })

  const lastSync = status?.last_sync_at
  const hasError = !!status?.last_error
  const errorText = status?.last_error

  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      {hasError ? (
        <span className="text-red-500 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block" />
          Sync error
        </span>
      ) : lastSync ? (
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
          Synced {timeAgo(lastSync)}
        </span>
      ) : (
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-300 inline-block" />
          Not synced yet
        </span>
      )}
      <button
        onClick={() => syncMutation.mutate()}
        disabled={syncMutation.isPending}
        className="px-2 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
      >
        {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
      </button>
      {syncMutation.isSuccess && (
        <span className="text-green-600">
          +{syncMutation.data?.imported ?? 0} imported, {syncMutation.data?.updated ?? 0} updated
        </span>
      )}
      {(syncMutation.isError || errorText) && (
        <span className="text-red-600 max-w-md truncate" title={syncMutation.error?.response?.data?.detail || errorText}>
          {syncMutation.error?.response?.data?.detail || errorText}
        </span>
      )}
    </div>
  )
}

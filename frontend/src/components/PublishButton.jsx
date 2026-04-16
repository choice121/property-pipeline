import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { publishProperty, syncFields, refreshImages, setListingStatus, aiDetectIssues } from '../api/client'

const LIVE_SITE_BASE = 'https://choice-properties-site.pages.dev/property.html'

function parseArray(value) {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value || '[]') : value
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const LISTING_STATUS_OPTIONS = [
  { value: 'active',   label: 'Active',   color: 'text-green-700 bg-green-50 border-green-200' },
  { value: 'rented',   label: 'Rented',   color: 'text-purple-700 bg-purple-50 border-purple-200' },
  { value: 'archived', label: 'Archived', color: 'text-gray-600 bg-gray-50 border-gray-200' },
]

const SEVERITY_STYLES = {
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  suggestion: 'bg-blue-50 border-blue-200 text-blue-700',
}
const SEVERITY_ICON = { error: '✕', warning: '⚠', suggestion: '💡' }

function buildPropertyContext(property) {
  const tryParseArray = (val) => {
    try { return JSON.parse(val || '[]').join(', ') } catch { return val || '' }
  }
  return {
    address: property.address, city: property.city, state: property.state,
    bedrooms: property.bedrooms ? Number(property.bedrooms) : null,
    bathrooms: property.bathrooms ? Number(property.bathrooms) : null,
    square_footage: property.square_footage ? Number(property.square_footage) : null,
    year_built: property.year_built ? Number(property.year_built) : null,
    monthly_rent: property.monthly_rent ? Number(property.monthly_rent) : null,
    property_type: property.property_type,
    amenities: tryParseArray(property.amenities),
    appliances: tryParseArray(property.appliances),
    pets_allowed: property.pets_allowed ?? null,
    parking: property.parking,
    heating_type: property.heating_type, cooling_type: property.cooling_type,
    laundry_type: property.laundry_type,
    utilities_included: tryParseArray(property.utilities_included),
    description: property.description,
    lease_terms: tryParseArray(property.lease_terms),
    flooring: tryParseArray(property.flooring),
    has_basement: property.has_basement ?? null,
    has_central_air: property.has_central_air ?? null,
  }
}

export default function PublishButton({ property, onPublished, savedAfterPublish, onSynced }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const [syncDone, setSyncDone] = useState(false)
  const [refreshDone, setRefreshDone] = useState(false)
  const [statusDone, setStatusDone] = useState(false)

  const [gateChecking, setGateChecking] = useState(false)
  const [gateIssues, setGateIssues] = useState(null)
  const [gateOverride, setGateOverride] = useState(false)

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
      setGateIssues(null)
      setGateOverride(false)
      invalidate()
      if (onPublished) onPublished(data)
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => syncFields(property.id).then((r) => r.data),
    onSuccess: () => {
      setSyncDone(true)
      invalidate()
      if (onSynced) onSynced()
      setTimeout(() => setSyncDone(false), 3000)
    },
  })

  const refreshMutation = useMutation({
    mutationFn: () => refreshImages(property.id).then((r) => r.data),
    onSuccess: () => { setRefreshDone(true); invalidate(); setTimeout(() => setRefreshDone(false), 3000) },
  })

  const statusMutation = useMutation({
    mutationFn: (status) => setListingStatus(property.id, status).then((r) => r.data),
    onSuccess: () => { setStatusDone(true); invalidate(); setTimeout(() => setStatusDone(false), 3000) },
  })

  async function handlePublishClick() {
    setGateChecking(true)
    setGateIssues(null)
    setGateOverride(false)
    try {
      const res = await aiDetectIssues({ property: buildPropertyContext(property) })
      const issues = res.data.issues || []
      const errors = issues.filter(i => i.severity === 'error')
      const warnings = issues.filter(i => i.severity === 'warning')
      if (errors.length > 0 || warnings.length > 0) {
        setGateIssues({ errors, warnings, all: issues })
      } else {
        setConfirming(true)
      }
    } catch {
      setConfirming(true)
    } finally {
      setGateChecking(false)
    }
  }

  // ── Already published ──────────────────────────────────────────────────────
  if (property.status === 'published' || property.status === 'rented' || property.status === 'archived' || property.choice_property_id) {
    const liveUrl = property.choice_property_id
      ? `${LIVE_SITE_BASE}?id=${property.choice_property_id}`
      : null

    return (
      <div className="flex flex-col gap-2 w-full">
        {savedAfterPublish && (
          <div className="flex items-center justify-between px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-xs font-medium text-amber-800">Changes saved — push them to the live site</p>
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="text-xs font-semibold text-amber-700 hover:text-amber-900 underline disabled:opacity-50"
            >
              {syncMutation.isPending ? 'Syncing…' : 'Sync Now'}
            </button>
          </div>
        )}

        <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
          <svg className="w-4 h-4 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-green-700">Published to Choice Properties</p>
            {property.choice_property_id && (
              <p className="text-xs text-green-500 font-mono">{property.choice_property_id}</p>
            )}
            {property.published_at && (
              <p className="text-xs text-green-500">{new Date(property.published_at).toLocaleString()}</p>
            )}
          </div>
          {liveUrl && (
            <a
              href={liveUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-shrink-0 text-xs font-medium text-green-700 hover:text-green-900 underline"
            >
              View Live ↗
            </a>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-gray-500">Listing Status on Live Site</p>
          <div className="flex gap-2">
            {LISTING_STATUS_OPTIONS.map(opt => {
              const isCurrent = property.status === opt.value ||
                (opt.value === 'active' && property.status === 'published')
              return (
                <button
                  key={opt.value}
                  onClick={() => !isCurrent && statusMutation.mutate(opt.value)}
                  disabled={statusMutation.isPending || isCurrent}
                  className={`flex-1 text-xs font-medium px-2 py-1.5 rounded-md border transition-colors disabled:cursor-default
                    ${isCurrent
                      ? opt.color + ' opacity-100 font-semibold ring-1 ring-offset-0 ring-current'
                      : 'border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-50'
                    }`}
                >
                  {statusMutation.isPending && statusMutation.variables === opt.value ? '…' : opt.label}
                </button>
              )
            })}
          </div>
          {statusDone && <p className="text-xs text-green-600">Listing status updated on live site.</p>}
          {statusMutation.isError && (
            <p className="text-xs text-red-600">{statusMutation.error?.response?.data?.detail || 'Status update failed.'}</p>
          )}
        </div>

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
              <><svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Sync Fields</>
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

        {syncMutation.isError && (
          <p className="text-xs text-red-600">{syncMutation.error?.response?.data?.detail || 'Sync failed.'}</p>
        )}
        {refreshMutation.isError && (
          <p className="text-xs text-red-600">{refreshMutation.error?.response?.data?.detail || 'Refresh failed.'}</p>
        )}
      </div>
    )
  }

  if (property.status !== 'ready') return null

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

  // ── AI Gate: errors or warnings found ──────────────────────────────────────
  if (gateIssues && !gateOverride) {
    const { errors, warnings } = gateIssues
    const blocked = errors.length > 0
    return (
      <div className={`flex flex-col gap-3 p-4 rounded-lg border ${blocked ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
        <div className="flex items-start gap-2">
          <svg className={`w-4 h-4 mt-0.5 flex-shrink-0 ${blocked ? 'text-red-600' : 'text-amber-600'}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <div>
            <p className={`text-sm font-semibold ${blocked ? 'text-red-800' : 'text-amber-800'}`}>
              {blocked
                ? `AI found ${errors.length} critical issue${errors.length !== 1 ? 's' : ''} — fix before publishing`
                : `AI found ${warnings.length} warning${warnings.length !== 1 ? 's' : ''} — review before publishing`}
            </p>
            <p className={`text-xs mt-0.5 ${blocked ? 'text-red-600' : 'text-amber-600'}`}>
              {blocked ? 'Resolve these errors to ensure listing quality.' : "These won't block publishing, but are worth addressing."}
            </p>
          </div>
        </div>

        <div className="space-y-1.5 max-h-40 overflow-y-auto">
          {gateIssues.all.filter(i => i.severity === 'error' || i.severity === 'warning').map((issue, i) => (
            <div key={i} className={`text-xs px-2.5 py-1.5 rounded border ${SEVERITY_STYLES[issue.severity] || SEVERITY_STYLES.suggestion}`}>
              <span className="mr-1.5">{SEVERITY_ICON[issue.severity] || '•'}</span>
              <span className="font-medium">{issue.field && issue.field !== 'general' ? `${issue.field}: ` : ''}</span>
              {issue.message}
            </div>
          ))}
        </div>

        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => { setGateIssues(null); setGateOverride(false) }}
            className={`text-xs font-medium px-3 py-1.5 rounded-md border transition-colors ${
              blocked
                ? 'bg-white border-red-300 text-red-700 hover:bg-red-50'
                : 'bg-white border-amber-300 text-amber-700 hover:bg-amber-50'
            }`}
          >
            ← Go Back and Fix
          </button>
          {!blocked && (
            <button
              onClick={() => { setGateOverride(true); setConfirming(true) }}
              className="text-xs font-medium px-3 py-1.5 rounded-md border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Publish Anyway
            </button>
          )}
        </div>
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
            onClick={() => { setConfirming(false); setGateOverride(false) }}
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
      onClick={handlePublishClick}
      disabled={gateChecking}
      className="flex items-center gap-2 bg-green-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-green-700 disabled:opacity-60 transition-colors"
    >
      {gateChecking ? (
        <>
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          AI Checking…
        </>
      ) : (
        <>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Publish to Choice Properties
        </>
      )}
    </button>
  )
}

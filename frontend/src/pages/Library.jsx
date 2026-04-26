import { useState, useMemo, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, Link } from 'react-router-dom'
import { getProperties, bulkAction, aiBulkScan, aiBulkClean, aiBulkEnrich, getQualityStats, startBulkImageDownload, getBulkImageDownloadStatus, restoreLibrary, startBulkPublish, getBulkPublishStatus, watermarkScanStart, watermarkScanStatus, watermarkGetFlagged, watermarkUnflag, watermarkClearFlags } from '../api/client'
import PropertyCard from '../components/PropertyCard'
import SyncStatus from '../components/SyncStatus'
import ConfirmModal from '../components/ConfirmModal'
import PullToRefresh from '../components/PullToRefresh'
import { SkeletonCard } from '../components/Skeleton'
import RecentlyViewedStrip from '../components/RecentlyViewedStrip'
import { useLongPress } from '../utils/longPress'
import { computeCompleteness } from '../utils/completeness'

function buildContext(p) {
  const tryArr = (v) => { try { return JSON.parse(v || '[]').join(', ') } catch { return v || '' } }
  return {
    address: p.address, city: p.city, state: p.state,
    bedrooms: p.bedrooms != null ? Number(p.bedrooms) : null,
    bathrooms: p.bathrooms != null ? Number(p.bathrooms) : null,
    square_footage: p.square_footage ? Number(p.square_footage) : null,
    year_built: p.year_built ? Number(p.year_built) : null,
    monthly_rent: p.monthly_rent ? Number(p.monthly_rent) : null,
    property_type: p.property_type,
    amenities: tryArr(p.amenities), appliances: tryArr(p.appliances),
    pets_allowed: p.pets_allowed ?? null,
    parking: p.parking, heating_type: p.heating_type, cooling_type: p.cooling_type,
    laundry_type: p.laundry_type, utilities_included: tryArr(p.utilities_included),
    description: p.description, lease_terms: tryArr(p.lease_terms),
    flooring: tryArr(p.flooring),
    has_basement: p.has_basement ?? null, has_central_air: p.has_central_air ?? null,
  }
}

function LongPressPropertyCard({ property, selectMode, selected, onTap, onToggleSelect, onLongPressEnter, aiHealth }) {
  const lp = useLongPress(onLongPressEnter, { delay: 380 })
  return (
    <div
      onTouchStart={lp.onTouchStart}
      onTouchMove={lp.onTouchMove}
      onTouchEnd={lp.onTouchEnd}
      onTouchCancel={lp.onTouchCancel}
    >
      <PropertyCard
        property={property}
        onClick={() => { if (!lp.didFire()) onTap() }}
        selectable={selectMode}
        selected={selected}
        onSelect={onToggleSelect}
        aiHealth={aiHealth}
      />
    </div>
  )
}

export default function Library() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState('scraped_at')
  const [selectMode, setSelectMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [bulkResult, setBulkResult] = useState(null)

  const [scanning, setScanning] = useState(false)
  const [scanHealthMap, setScanHealthMap] = useState(null)
  const [scanError, setScanError] = useState(null)

  const [cleaning, setCleaning] = useState(false)
  const [cleanResult, setCleanResult] = useState(null)
  const [cleanError, setCleanError] = useState(null)

  const [enriching, setEnriching] = useState(false)
  const [enrichResult, setEnrichResult] = useState(null)
  const [enrichError, setEnrichError] = useState(null)
  const [showStats, setShowStats] = useState(false)

  const [imgDownloading, setImgDownloading] = useState(false)
  const [imgProgress, setImgProgress] = useState(null)
  const imgPollRef = useRef(null)

  const [bulkPublishing, setBulkPublishing] = useState(false)
  const [bulkPublishProgress, setBulkPublishProgress] = useState(null)
  const bulkPublishPollRef = useRef(null)

  const [restoring, setRestoring] = useState(false)
  const [restoreResult, setRestoreResult] = useState(null)
  const [restoreError, setRestoreError] = useState(null)
  const [restoreDismissed, setRestoreDismissed] = useState(false)

  const [wmScanning, setWmScanning] = useState(false)
  const [wmProgress, setWmProgress] = useState(null)
  const [wmFlagged, setWmFlagged] = useState(null)
  const [wmScanned, setWmScanned] = useState(0)
  const [wmDeleting, setWmDeleting] = useState(false)
  const [wmError, setWmError] = useState(null)
  const [wmDone, setWmDone] = useState(false)
  const [wmScannedAt, setWmScannedAt] = useState(null)
  const [wmFromPersisted, setWmFromPersisted] = useState(false)
  const wmPollRef = useRef(null)

  const [confirmModal, setConfirmModal] = useState(null)
  const [showOverflow, setShowOverflow] = useState(false)
  const overflowRef = useRef(null)

  const openConfirm = (opts) => setConfirmModal(opts)
  const closeConfirm = () => setConfirmModal(null)

  useEffect(() => {
    function handleClickOutside(e) {
      if (overflowRef.current && !overflowRef.current.contains(e.target)) {
        setShowOverflow(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Load persisted watermark flags on mount
  const { data: persistedWmData } = useQuery({
    queryKey: ['wm-flagged'],
    queryFn: () => watermarkGetFlagged().then(r => r.data),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (!persistedWmData || wmFlagged !== null || wmScanning) return
    if (persistedWmData.total > 0) {
      setWmFlagged(persistedWmData.flagged)
      setWmScannedAt(persistedWmData.scanned_at)
      setWmFromPersisted(true)
    }
  }, [persistedWmData])

  const { data: qualityStats } = useQuery({
    queryKey: ['quality-stats'],
    queryFn: () => getQualityStats().then(r => r.data),
    enabled: showStats,
    staleTime: 60000,
  })

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['properties'],
    queryFn: () => getProperties().then((r) => r.data),
    refetchInterval: (query) => {
      const props = query.state.data
      if (!props) return false
      const hasDownloading = props.some(
        (p) => p.status === 'scraped' && (!p.local_image_paths || p.local_image_paths === '[]')
      )
      return hasDownloading ? 4000 : false
    },
  })

  const bulkMutation = useMutation({
    mutationFn: ({ ids, action }) => bulkAction([...ids], action).then(r => r.data),
    onSuccess: (result) => {
      setBulkResult(result)
      setSelectedIds(new Set())
      setSelectMode(false)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      setTimeout(() => setBulkResult(null), 4000)
    },
  })

  useEffect(() => {
    if (!imgDownloading) return
    imgPollRef.current = setInterval(async () => {
      try {
        const res = await getBulkImageDownloadStatus()
        const s = res.data
        setImgProgress(s)
        if (!s.running) {
          setImgDownloading(false)
          clearInterval(imgPollRef.current)
          queryClient.invalidateQueries({ queryKey: ['properties'] })
        }
      } catch { /* ignore */ }
    }, 2500)
    return () => clearInterval(imgPollRef.current)
  }, [imgDownloading])

  useEffect(() => {
    if (!bulkPublishing) return
    bulkPublishPollRef.current = setInterval(async () => {
      try {
        const res = await getBulkPublishStatus()
        const s = res.data
        setBulkPublishProgress(s)
        if (!s.running) {
          setBulkPublishing(false)
          clearInterval(bulkPublishPollRef.current)
          queryClient.invalidateQueries({ queryKey: ['properties'] })
        }
      } catch { /* ignore */ }
    }, 3000)
    return () => clearInterval(bulkPublishPollRef.current)
  }, [bulkPublishing])

  useEffect(() => {
    if (!wmScanning) return
    wmPollRef.current = setInterval(async () => {
      try {
        const res = await watermarkScanStatus()
        const s = res.data
        setWmProgress(s)
        if (!s.running) {
          clearInterval(wmPollRef.current)
          setWmScanning(false)
          // Join flagged IDs with full property objects
          const flaggedList = s.flagged || []
          const metaById = Object.fromEntries(flaggedList.map(f => [f.id, f]))
          const flaggedIds = new Set(flaggedList.map(f => f.id))
          const fullProps = (data || [])
            .filter(p => flaggedIds.has(p.id))
            .map(p => ({ ...p, _wm: metaById[p.id] }))
          flaggedList.forEach(f => {
            if (!fullProps.find(p => p.id === f.id)) fullProps.push({ ...f, _wm: f })
          })
          setWmFlagged(fullProps)
          setWmScanned(s.scanned || 0)
          setWmFromPersisted(false)
          setWmScannedAt(new Date().toISOString())
          queryClient.invalidateQueries({ queryKey: ['wm-flagged'] })
        }
      } catch { /* ignore poll errors */ }
    }, 2000)
    return () => clearInterval(wmPollRef.current)
  }, [wmScanning])

  async function handleBulkPublish() {
    if (bulkPublishing) return
    const unpublished = (data || []).filter(p => !p.choice_property_id)
    const withImages = unpublished.filter(p => {
      try { return JSON.parse(p.local_image_paths || '[]').length > 0 } catch { return false }
    })
    if (withImages.length === 0) {
      openConfirm({
        title: 'No properties ready to publish',
        message: 'Download images first, then use Bulk Publish.',
        confirmLabel: 'OK',
        cancelLabel: null,
        onConfirm: () => {},
      })
      return
    }
    openConfirm({
      title: `Publish ${withImages.length} ${withImages.length === 1 ? 'property' : 'properties'}?`,
      message: 'This will upload images to ImageKit and push each listing live to Choice Properties.',
      confirmLabel: 'Publish',
      danger: false,
      onConfirm: async () => {
        try {
          const res = await startBulkPublish({ ids: withImages.map(p => p.id) })
          if (res.data.ok === false) { return }
          setBulkPublishProgress(res.data.state)
          setBulkPublishing(true)
        } catch { }
      },
    })
  }

  async function handleBulkImageDownload() {
    if (imgDownloading) return
    const missing = (data || []).filter(p => {
      try { return !JSON.parse(p.local_image_paths || '[]').length } catch { return true }
    })
    if (missing.length === 0) return
    openConfirm({
      title: `Download images for ${missing.length} ${missing.length === 1 ? 'property' : 'properties'}?`,
      message: 'This runs in the background and may take a while.',
      confirmLabel: 'Download',
      onConfirm: async () => {
        try {
          const res = await startBulkImageDownload()
          if (res.data.ok === false) return
          setImgProgress(res.data.state)
          setImgDownloading(true)
        } catch { }
      },
    })
  }

  const restoreNeeds = useMemo(() => {
    if (!data) return { noPhotos: 0, noAI: 0, total: 0 }
    let noPhotos = 0, noAI = 0
    data.forEach(p => {
      try { if (!JSON.parse(p.local_image_paths || '[]').length) noPhotos++ } catch { noPhotos++ }
      const inf = (() => { try { return JSON.parse(p.inferred_features || '[]') } catch { return [] } })()
      if (!inf.includes('enriched_sig') || !p.description || (p.data_quality_score || 0) < 60) noAI++
    })
    return { noPhotos, noAI, total: noPhotos + noAI }
  }, [data])

  async function handleRestoreLibrary() {
    if (restoring) return
    setRestoring(true)
    setRestoreResult(null)
    setRestoreError(null)
    setRestoreDismissed(false)
    try {
      const res = await restoreLibrary()
      setRestoreResult(res.data)
      setImgProgress({ running: true, total: res.data.images_queued, done: 0, failed: 0 })
      setImgDownloading(true)
    } catch (e) {
      setRestoreError(e.response?.data?.detail || e.message || 'Restore failed.')
      setTimeout(() => setRestoreError(null), 8000)
    } finally {
      setRestoring(false)
    }
  }

  async function handleWatermarkScan() {
    if (wmScanning) return
    setWmFlagged(null)
    setWmScanned(0)
    setWmProgress(null)
    setWmError(null)
    setWmDone(false)
    try {
      const res = await watermarkScanStart()
      if (!res.data.ok && res.data.message !== 'Scan already running.') {
        setWmError(res.data.message || 'Could not start scan.')
        return
      }
      setWmScanning(true)
    } catch (e) {
      setWmError(e.response?.data?.detail || e.message || 'Watermark scan failed to start.')
    }
  }

  async function handleWmUnmark(id) {
    setWmFlagged(prev => (prev || []).filter(p => p.id !== id))
    try {
      await watermarkUnflag(id)
      queryClient.invalidateQueries({ queryKey: ['wm-flagged'] })
    } catch { /* ignore */ }
  }

  async function handleWmDeleteAll() {
    if (!wmFlagged || wmFlagged.length === 0 || wmDeleting) return
    const count = wmFlagged.length
    openConfirm({
      title: `Delete ${count} ${count === 1 ? 'property' : 'properties'}?`,
      message: 'These listings have watermarked images. Permanently removing them cannot be undone.',
      confirmLabel: 'Delete All',
      danger: true,
      onConfirm: async () => {
        setWmDeleting(true)
        setWmError(null)
        try {
          const ids = wmFlagged.map(p => p.id)
          await bulkAction(ids, 'delete')
          // Clear persisted flags for the deleted properties
          await Promise.allSettled(ids.map(id => watermarkUnflag(id)))
          setWmDone(true)
          setWmFlagged([])
          queryClient.invalidateQueries({ queryKey: ['properties'] })
          queryClient.invalidateQueries({ queryKey: ['wm-flagged'] })
        } catch (e) {
          setWmError(e.response?.data?.detail || e.message || 'Delete failed.')
        } finally {
          setWmDeleting(false)
        }
      },
    })
  }

  function handleWmClose() {
    // Just hide the panel — persisted flags remain and will reload on next visit
    clearInterval(wmPollRef.current)
    setWmScanning(false)
    setWmFlagged(null)
    setWmScanned(0)
    setWmProgress(null)
    setWmError(null)
    setWmDone(false)
    setWmScannedAt(null)
    setWmFromPersisted(false)
  }

  async function handleWmClearResults() {
    // Explicitly clear persisted flags and close the panel
    handleWmClose()
    try {
      await watermarkClearFlags()
      queryClient.invalidateQueries({ queryKey: ['wm-flagged'] })
    } catch { /* ignore */ }
  }

  const filtered = useMemo(() => {
    if (!data) return []
    let list = [...data]

    if (statusFilter) {
      list = list.filter((p) => p.status === statusFilter)
    }

    if (search.trim()) {
      const term = search.toLowerCase()
      list = list.filter(
        (p) =>
          (p.address || '').toLowerCase().includes(term) ||
          (p.city || '').toLowerCase().includes(term)
      )
    }

    if (sort === 'scraped_at') {
      list.sort((a, b) => new Date(b.scraped_at) - new Date(a.scraped_at))
    } else if (sort === 'price_asc') {
      list.sort((a, b) => (a.monthly_rent || 0) - (b.monthly_rent || 0))
    } else if (sort === 'price_desc') {
      list.sort((a, b) => (b.monthly_rent || 0) - (a.monthly_rent || 0))
    } else if (sort === 'bedrooms') {
      list.sort((a, b) => (b.bedrooms || 0) - (a.bedrooms || 0))
    } else if (sort === 'completeness_asc') {
      list.sort((a, b) => computeCompleteness(a).score - computeCompleteness(b).score)
    } else if (sort === 'completeness_desc') {
      list.sort((a, b) => computeCompleteness(b).score - computeCompleteness(a).score)
    }

    return list
  }, [data, search, statusFilter, sort])

  function toggleSelect(id) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map(p => p.id)))
    }
  }

  function exitSelectMode() {
    setSelectMode(false)
    setSelectedIds(new Set())
  }

  function handleBulkAction(action) {
    if (selectedIds.size === 0) return
    const isDanger = action === 'delete'
    openConfirm({
      title: isDanger
        ? `Delete ${selectedIds.size} ${selectedIds.size === 1 ? 'property' : 'properties'}?`
        : `Apply "${action}" to ${selectedIds.size} ${selectedIds.size === 1 ? 'property' : 'properties'}?`,
      message: isDanger ? 'This cannot be undone.' : undefined,
      confirmLabel: isDanger ? 'Delete' : 'Apply',
      danger: isDanger,
      onConfirm: () => bulkMutation.mutate({ ids: selectedIds, action }),
    })
  }

  async function handleBulkClean() {
    if (!data || data.length === 0) return
    const toClean = data.filter(p => p.description && p.description.length > 20).map(p => p.id)
    if (toClean.length === 0) return
    openConfirm({
      title: `Clean descriptions for ${toClean.length} ${toClean.length === 1 ? 'property' : 'properties'}?`,
      message: 'AI will remove contact info, tour language, and gatekeeping text from each listing.',
      confirmLabel: 'Clean',
      onConfirm: async () => {
        setCleaning(true)
        setCleanResult(null)
        setCleanError(null)
        try {
          const res = await aiBulkClean({ property_ids: toClean })
          setCleanResult(res.data)
          queryClient.invalidateQueries({ queryKey: ['properties'] })
          setTimeout(() => setCleanResult(null), 8000)
        } catch (e) {
          setCleanError(e.response?.data?.detail || e.message || 'Bulk clean failed.')
          setTimeout(() => setCleanError(null), 6000)
        } finally {
          setCleaning(false)
        }
      },
    })
  }

  async function handleBulkEnrich() {
    if (enriching || !data || data.length === 0) return
    const eligible = data.filter(p => !p.description || (p.data_quality_score || 0) < 60)
    if (eligible.length === 0) return
    openConfirm({
      title: `Run AI enrichment on ${eligible.length} ${eligible.length === 1 ? 'property' : 'properties'}?`,
      message: 'This will fill in descriptions, extract features, and improve quality scores. It runs in the background.',
      confirmLabel: 'Enrich',
      onConfirm: async () => {
        setEnriching(true)
        setEnrichResult(null)
        setEnrichError(null)
        try {
          const res = await aiBulkEnrich({})
          setEnrichResult(res.data)
          setTimeout(() => setEnrichResult(null), 10000)
        } catch (e) {
          setEnrichError(e.response?.data?.detail || e.message || 'Enrichment failed.')
          setTimeout(() => setEnrichError(null), 6000)
        } finally {
          setEnriching(false)
        }
      },
    })
  }

  async function handleAiScan() {
    if (scanning || filtered.length === 0) return
    setScanning(true)
    setScanHealthMap(null)
    setScanError(null)
    try {
      const properties = filtered.map(p => ({ id: String(p.id), property: buildContext(p) }))
      const res = await aiBulkScan({ properties })
      const results = res.data.results || []
      const map = {}
      results.forEach(r => { map[r.id] = r })
      setScanHealthMap(map)
    } catch (e) {
      setScanError(e.response?.data?.detail || e.message || 'AI scan failed.')
    } finally {
      setScanning(false)
    }
  }

  const scanSummary = useMemo(() => {
    if (!scanHealthMap) return null
    let errors = 0, warnings = 0, clean = 0
    Object.values(scanHealthMap).forEach(r => {
      if (r.errors > 0) errors++
      else if (r.warnings > 0) warnings++
      else clean++
    })
    return { errors, warnings, clean, total: Object.keys(scanHealthMap).length }
  }, [scanHealthMap])

  return (
    <div>
      <div className="flex items-center justify-between mb-3 gap-2">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">
          Library
          <span className="ml-2 text-sm sm:text-base font-normal text-gray-500">
            ({filtered.length})
          </span>
        </h1>
        <div className="flex items-center gap-2 flex-shrink-0">

          {/* ── Mobile: primary actions always visible ────────────────── */}
          {/* Download Images */}
          <button
            onClick={handleBulkImageDownload}
            disabled={imgDownloading || !data || data.length === 0}
            title="Download all missing property images locally"
            className="flex items-center gap-1.5 text-sm px-2.5 sm:px-3 py-2 rounded-lg border border-orange-300 bg-orange-50 text-orange-700 hover:bg-orange-100 disabled:opacity-50 transition-colors touch-target"
          >
            <svg className={`w-4 h-4 flex-shrink-0 ${imgDownloading ? 'animate-pulse' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span className="hidden sm:inline">{imgDownloading ? `${imgProgress?.done ?? 0}/${imgProgress?.total ?? '…'}` : 'Images'}</span>
            <span className="sm:hidden text-xs font-medium">{imgDownloading ? `${imgProgress?.done ?? 0}/${imgProgress?.total ?? '…'}` : 'Imgs'}</span>
          </button>

          {/* Bulk Publish */}
          <button
            onClick={handleBulkPublish}
            disabled={bulkPublishing || !data || data.length === 0}
            title="Publish all unpublished properties with downloaded images"
            className="flex items-center gap-1.5 text-sm px-2.5 sm:px-3 py-2 rounded-lg border border-green-400 bg-green-50 text-green-700 hover:bg-green-100 disabled:opacity-50 transition-colors touch-target"
          >
            <svg className={`w-4 h-4 flex-shrink-0 ${bulkPublishing ? 'animate-pulse' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              {bulkPublishing
                ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></>
                : <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
              }
            </svg>
            <span className="hidden sm:inline">
              {bulkPublishing ? `${bulkPublishProgress?.done ?? 0}/${bulkPublishProgress?.total ?? '…'}` : 'Bulk Publish'}
            </span>
            <span className="sm:hidden text-xs font-medium">
              {bulkPublishing ? `${bulkPublishProgress?.done ?? 0}/${bulkPublishProgress?.total ?? '…'}` : 'Publish'}
            </span>
          </button>

          {/* ── Desktop: secondary actions always visible ─────────────── */}
          <div className="hidden sm:flex items-center gap-2">
            {/* Stats toggle */}
            <button
              onClick={() => setShowStats(s => !s)}
              title="Source quality stats"
              className={`flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border transition-colors touch-target ${showStats ? 'bg-blue-100 border-blue-300 text-blue-700' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
            >
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Stats
            </button>

            {/* Run AI Enrichment */}
            <button
              onClick={handleBulkEnrich}
              disabled={enriching || !data || data.length === 0}
              title="Run AI enrichment on all eligible properties"
              className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 transition-colors touch-target"
            >
              <svg className={`w-4 h-4 flex-shrink-0 ${enriching ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                {enriching
                  ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></>
                  : <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                }
              </svg>
              {enriching ? 'Queuing…' : 'Run AI'}
            </button>

            {/* Clean All */}
            <button
              onClick={handleBulkClean}
              disabled={cleaning || !data || data.length === 0}
              title="Clean all descriptions with AI"
              className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 transition-colors touch-target"
            >
              <svg className={`w-4 h-4 flex-shrink-0 ${cleaning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                {cleaning
                  ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></>
                  : <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                }
              </svg>
              {cleaning ? 'Cleaning…' : 'Clean All'}
            </button>

            {/* AI Scan */}
            <button
              onClick={handleAiScan}
              disabled={scanning || filtered.length === 0}
              title={`AI Scan (${filtered.length})`}
              className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border border-purple-300 bg-purple-50 text-purple-700 hover:bg-purple-100 disabled:opacity-50 transition-colors touch-target"
            >
              <svg className={`w-4 h-4 flex-shrink-0 ${scanning ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {scanning
                  ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></>
                  : <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                }
              </svg>
              {scanning ? 'Scanning…' : `AI Scan (${filtered.length})`}
            </button>

            {/* Watermark Scan */}
            <button
              onClick={handleWatermarkScan}
              disabled={wmScanning || !data || data.length === 0}
              title="Scan all properties for watermarked photos"
              className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-50 transition-colors touch-target"
            >
              <svg className={`w-4 h-4 flex-shrink-0 ${wmScanning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                {wmScanning
                  ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></>
                  : <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                }
              </svg>
              {wmScanning ? 'Scanning…' : 'Watermarks'}
            </button>
          </div>

          {/* ── Mobile: overflow "More" menu ──────────────────────────── */}
          <div className="relative sm:hidden" ref={overflowRef}>
            <button
              onClick={() => setShowOverflow(o => !o)}
              className={`flex items-center justify-center w-9 h-9 rounded-lg border transition-colors touch-target ${showOverflow ? 'bg-gray-100 border-gray-400 text-gray-800' : 'border-gray-300 text-gray-500 hover:bg-gray-50'}`}
              title="More actions"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/>
              </svg>
            </button>
            {showOverflow && (
              <div className="absolute right-0 top-11 z-50 w-52 bg-white rounded-xl shadow-xl border border-gray-100 py-1.5 overflow-hidden">
                <button onClick={() => { setShowStats(s => !s); setShowOverflow(false) }} className={`flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-left transition-colors ${showStats ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-50'}`}>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                  Stats
                </button>
                <button onClick={() => { handleBulkEnrich(); setShowOverflow(false) }} disabled={enriching || !data || data.length === 0} className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-left text-blue-700 hover:bg-blue-50 disabled:opacity-50 transition-colors">
                  <svg className={`w-4 h-4 ${enriching ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                  {enriching ? 'Queuing…' : 'Run AI Enrichment'}
                </button>
                <button onClick={() => { handleBulkClean(); setShowOverflow(false) }} disabled={cleaning || !data || data.length === 0} className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-left text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 transition-colors">
                  <svg className={`w-4 h-4 ${cleaning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
                  {cleaning ? 'Cleaning…' : 'Clean All'}
                </button>
                <button onClick={() => { handleAiScan(); setShowOverflow(false) }} disabled={scanning || filtered.length === 0} className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-left text-purple-700 hover:bg-purple-50 disabled:opacity-50 transition-colors">
                  <svg className={`w-4 h-4 ${scanning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
                  {scanning ? 'Scanning…' : `AI Scan (${filtered.length})`}
                </button>
                <button onClick={() => { handleWatermarkScan(); setShowOverflow(false) }} disabled={wmScanning || !data || data.length === 0} className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-left text-rose-700 hover:bg-rose-50 disabled:opacity-50 transition-colors">
                  <svg className={`w-4 h-4 ${wmScanning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z M15 13a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                  {wmScanning ? 'Scanning…' : 'Watermarks'}
                </button>
              </div>
            )}
          </div>

          {/* Select */}
          <button
            onClick={() => { setSelectMode(!selectMode); setSelectedIds(new Set()) }}
            className={`text-sm px-2.5 sm:px-3 py-2 rounded-lg border transition-colors touch-target ${selectMode ? 'bg-gray-900 text-white border-gray-900' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
          >
            {selectMode ? 'Cancel' : 'Select'}
          </button>

          {/* + Create and + Scrape — desktop only; bottom tab bar handles mobile */}
          <Link
            to="/create"
            className="hidden sm:block border border-gray-300 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            + Create
          </Link>
          <Link
            to="/scraper"
            className="hidden sm:block bg-gray-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-700 transition-colors"
          >
            + Scrape
          </Link>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <SyncStatus />
      </div>

      {/* Quality stats panel */}
      {showStats && (
        <div className="mb-4 bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-800">Source Quality Stats</span>
            <button onClick={() => setShowStats(false)} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
          </div>
          {!qualityStats ? (
            <div className="px-4 py-3 text-sm text-gray-400">Loading…</div>
          ) : qualityStats.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-400">No data yet.</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {qualityStats.map(row => (
                <div key={row.source} className="px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-1">
                  <span className="text-sm font-medium text-gray-800 capitalize w-24">{row.source}</span>
                  <span className="text-sm text-gray-500"><strong className="text-gray-800">{row.count}</strong> listings</span>
                  {row.avg_score != null && (
                    <span className="text-sm text-gray-500">
                      Avg score: <strong className={`${row.avg_score >= 70 ? 'text-green-700' : row.avg_score >= 40 ? 'text-amber-700' : 'text-red-700'}`}>{row.avg_score}</strong>
                    </span>
                  )}
                  <span className="text-sm text-gray-500">Range: {row.min_score ?? '—'} – {row.max_score ?? '—'}</span>
                  <div className="flex gap-2 flex-wrap ml-auto">
                    {Object.entries(row.by_status || {}).map(([status, cnt]) => (
                      <span key={status} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                        {status}: {cnt}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Enrichment banners */}
      {enrichError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>AI Enrichment failed: {enrichError}</span>
          <button onClick={() => setEnrichError(null)} className="text-red-400 hover:text-red-600 ml-3 text-lg leading-none">&times;</button>
        </div>
      )}
      {enrichResult && (
        <div className="mb-4 px-4 py-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-blue-900">
              AI Enrichment Queued — {enrichResult.queued} properties
            </span>
            <button onClick={() => setEnrichResult(null)} className="text-blue-400 hover:text-blue-600 text-lg leading-none">&times;</button>
          </div>
          <p className="text-sm text-blue-700 mt-1">{enrichResult.message}</p>
        </div>
      )}

      {/* Image download progress banner */}
      {imgProgress && (
        <div className="mb-4 px-4 py-3 bg-orange-50 border border-orange-200 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-orange-900">
              {imgProgress.running
                ? `Downloading images — ${imgProgress.done} / ${imgProgress.total} properties`
                : `Image download complete — ${imgProgress.done} saved, ${imgProgress.failed} failed`}
            </span>
            {!imgProgress.running && (
              <button onClick={() => setImgProgress(null)} className="text-orange-400 hover:text-orange-600 text-lg leading-none">&times;</button>
            )}
          </div>
          {imgProgress.running && (
            <div className="mt-2 h-1.5 bg-orange-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-orange-500 rounded-full transition-all duration-500"
                style={{ width: imgProgress.total ? `${Math.round(((imgProgress.done + imgProgress.failed) / imgProgress.total) * 100)}%` : '0%' }}
              />
            </div>
          )}
        </div>
      )}

      {/* Bulk Publish progress banner */}
      {bulkPublishProgress && (
        <div className="mb-4 px-4 py-3 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-green-900">
              {bulkPublishProgress.running
                ? `Publishing — ${bulkPublishProgress.done} / ${bulkPublishProgress.total} properties`
                : `Bulk publish complete — ${bulkPublishProgress.done} published, ${bulkPublishProgress.failed} failed, ${bulkPublishProgress.skipped} skipped`}
            </span>
            {!bulkPublishProgress.running && (
              <button onClick={() => setBulkPublishProgress(null)} className="text-green-400 hover:text-green-600 text-lg leading-none">&times;</button>
            )}
          </div>
          {bulkPublishProgress.running && (
            <div className="mt-2 h-1.5 bg-green-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 rounded-full transition-all duration-500"
                style={{ width: bulkPublishProgress.total ? `${Math.round(((bulkPublishProgress.done + bulkPublishProgress.failed + bulkPublishProgress.skipped) / bulkPublishProgress.total) * 100)}%` : '0%' }}
              />
            </div>
          )}
          {!bulkPublishProgress.running && bulkPublishProgress.errors?.length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-green-700 cursor-pointer hover:underline">{bulkPublishProgress.errors.length} error{bulkPublishProgress.errors.length !== 1 ? 's' : ''} — click to view</summary>
              <ul className="mt-1 space-y-0.5">
                {bulkPublishProgress.errors.slice(0, 10).map((e, i) => (
                  <li key={i} className="text-xs text-red-700 font-mono truncate">{e.id?.slice(0, 12)}… — {e.error}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* Library Restore Panel — auto-shows when photos or AI enrichment are missing */}
      {!restoreDismissed && !restoring && !restoreResult && restoreNeeds.total > 0 && !imgDownloading && (
        <div className="mb-4 bg-amber-50 border border-amber-300 rounded-lg px-4 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <svg className="w-4 h-4 text-amber-600 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="text-sm font-semibold text-amber-900">Your library needs attention</span>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-0.5 text-sm text-amber-800 mb-3 ml-6">
                {restoreNeeds.noPhotos > 0 && (
                  <span>{restoreNeeds.noPhotos} {restoreNeeds.noPhotos === 1 ? 'property is' : 'properties are'} missing local photos</span>
                )}
                {restoreNeeds.noAI > 0 && (
                  <span>{restoreNeeds.noAI} {restoreNeeds.noAI === 1 ? 'property needs' : 'properties need'} AI enrichment</span>
                )}
              </div>
              <div className="flex items-center gap-2 ml-6">
                <button
                  onClick={handleRestoreLibrary}
                  disabled={restoring}
                  className="inline-flex items-center gap-2 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Fix Everything
                </button>
                <span className="text-xs text-amber-700">Re-downloads all photos &amp; runs AI on every property</span>
              </div>
            </div>
            <button
              onClick={() => setRestoreDismissed(true)}
              className="text-amber-400 hover:text-amber-600 text-xl leading-none flex-shrink-0 mt-0.5"
              title="Dismiss"
            >
              &times;
            </button>
          </div>
        </div>
      )}

      {restoring && (
        <div className="mb-4 bg-amber-50 border border-amber-300 rounded-lg px-4 py-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
            <svg className="w-4 h-4 animate-spin text-amber-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Starting library restore…
          </div>
        </div>
      )}

      {restoreResult && (
        <div className="mb-4 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm font-semibold text-green-900">Library restore started</span>
              </div>
              <p className="text-sm text-green-800 ml-6">{restoreResult.message}</p>
            </div>
            <button onClick={() => setRestoreResult(null)} className="text-green-400 hover:text-green-600 text-xl leading-none flex-shrink-0">&times;</button>
          </div>
        </div>
      )}

      {restoreError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>Restore failed: {restoreError}</span>
          <button onClick={() => setRestoreError(null)} className="text-red-400 hover:text-red-600 ml-3 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Clean results banners */}
      {cleanError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>Clean failed: {cleanError}</span>
          <button onClick={() => setCleanError(null)} className="text-red-400 hover:text-red-600 ml-3 text-lg leading-none">&times;</button>
        </div>
      )}
      {cleanResult && (
        <div className="mb-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-emerald-900">
              Bulk Clean Complete — {cleanResult.cleaned} descriptions updated
            </span>
            <button onClick={() => setCleanResult(null)} className="text-emerald-400 hover:text-emerald-600 text-lg leading-none">&times;</button>
          </div>
          <div className="flex gap-4 mt-1">
            <span className="text-sm text-gray-600"><strong>{cleanResult.skipped}</strong> already clean</span>
            {cleanResult.errors > 0 && <span className="text-sm text-red-600"><strong>{cleanResult.errors}</strong> errors</span>}
          </div>
        </div>
      )}

      {/* AI Scan results banner */}
      {scanError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>AI scan failed: {scanError}</span>
          <button onClick={() => setScanError(null)} className="text-red-400 hover:text-red-600 ml-3 text-lg leading-none">&times;</button>
        </div>
      )}

      {scanSummary && (
        <div className="mb-4 px-4 py-3 bg-purple-50 border border-purple-200 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <svg className="w-4 h-4 text-purple-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              <span className="text-sm font-semibold text-purple-900">AI Scan Complete — {scanSummary.total} listings reviewed</span>
            </div>
            <button onClick={() => setScanHealthMap(null)} className="text-purple-400 hover:text-purple-600 text-lg leading-none">&times;</button>
          </div>
          <div className="flex gap-4 mt-2">
            {scanSummary.errors > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-red-700">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
                <strong>{scanSummary.errors}</strong> need fixes
              </span>
            )}
            {scanSummary.warnings > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-amber-700">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />
                <strong>{scanSummary.warnings}</strong> have warnings
              </span>
            )}
            {scanSummary.clean > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-green-700">
                <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
                <strong>{scanSummary.clean}</strong> look good
              </span>
            )}
          </div>
        </div>
      )}

      {/* Watermark scan results */}
      {wmError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>{wmError}</span>
          <button onClick={() => setWmError(null)} className="text-red-400 hover:text-red-600 ml-3 text-lg leading-none">&times;</button>
        </div>
      )}

      {(wmScanning || wmFlagged !== null) && (
        <div className="mb-6 bg-white border border-rose-200 rounded-xl shadow-sm overflow-hidden">
          {/* Header bar */}
          <div className="px-4 py-3 bg-rose-50 border-b border-rose-100 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0 flex-wrap">
              <svg className={`w-4 h-4 text-rose-600 flex-shrink-0 ${wmScanning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="text-sm font-semibold text-gray-900">
                {wmScanning ? 'Scanning for watermarks…' : 'Watermark Scan Results'}
              </span>
              {wmScanning && wmProgress && (
                <span className="text-xs text-gray-500">
                  {wmProgress.scanned} / {wmProgress.total} checked
                  {wmProgress.total_flagged > 0 && ` · ${wmProgress.total_flagged} flagged so far`}
                </span>
              )}
              {!wmScanning && wmFlagged !== null && (
                wmDone
                  ? <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">Done — deleted</span>
                  : wmFlagged.length > 0
                    ? <span className="text-xs bg-rose-600 text-white px-2 py-0.5 rounded-full font-medium">{wmFlagged.length} flagged</span>
                    : <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">All clean</span>
              )}
              {wmFromPersisted && wmScannedAt && (
                <span className="text-xs text-gray-400 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                  Saved · {new Date(wmScannedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {!wmScanning && wmFlagged && wmFlagged.length > 0 && !wmDone && (
                <button
                  onClick={handleWmDeleteAll}
                  disabled={wmDeleting}
                  className="flex items-center gap-1.5 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
                >
                  {wmDeleting
                    ? <><svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>Deleting…</>
                    : <><svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>Delete All {wmFlagged.length}</>
                  }
                </button>
              )}
              {!wmScanning && (
                <button
                  onClick={handleWmClearResults}
                  title="Clear all flagged results and dismiss"
                  className="text-xs text-gray-400 hover:text-rose-600 px-2 py-1 rounded hover:bg-rose-50 transition-colors"
                >
                  Clear
                </button>
              )}
              <button onClick={handleWmClose} title="Hide panel (results saved)" className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
            </div>
          </div>

          {/* Live progress bar while scanning */}
          {wmScanning && (
            <div className="px-4 py-3 border-b border-rose-100">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
                <span>Downloading and checking photos…</span>
                <span>{wmProgress?.scanned ?? 0} / {wmProgress?.total ?? '…'}</span>
              </div>
              <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-rose-500 rounded-full transition-all duration-500"
                  style={{ width: wmProgress?.total ? `${Math.round((wmProgress.scanned / wmProgress.total) * 100)}%` : '2%' }}
                />
              </div>
            </div>
          )}

          {/* Hint */}
          {wmFlagged && wmFlagged.length > 0 && !wmDone && (
            <div className="px-4 py-2.5 text-xs text-gray-500 bg-gray-50 border-b border-gray-100 flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>
                Results are <strong>automatically saved</strong> and will persist across refreshes.
                Click a card to edit, <strong>Unmark</strong> to exclude from deletion, or <strong>Delete All</strong> to remove flagged listings.
              </span>
            </div>
          )}

          {/* Empty / done states */}
          {wmFlagged && wmFlagged.length === 0 && !wmDone && (
            <div className="px-4 py-6 text-sm text-gray-600 text-center">
              No watermarked photos detected across {wmScanned} properties. Your library is clean.
            </div>
          )}
          {wmDone && (
            <div className="px-4 py-6 text-sm text-green-700 bg-green-50 text-center">
              All flagged properties were successfully deleted.
            </div>
          )}

          {/* Full property card grid */}
          {wmFlagged && wmFlagged.length > 0 && !wmDone && (
            <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 max-h-[70vh] overflow-y-auto">
              {wmFlagged.map(p => (
                <div key={p.id} className="relative group">
                  {/* Watermark badge */}
                  <div className="absolute top-2 left-2 z-20 bg-rose-600 text-white text-xs font-semibold px-2 py-0.5 rounded-full shadow">
                    {p._wm?.flagged ?? 0}/{p._wm?.checked ?? 0} watermarked
                  </div>
                  {/* Action buttons row */}
                  <div className="absolute top-2 right-2 z-20 flex gap-1.5">
                    <button
                      onClick={(e) => { e.stopPropagation(); navigate(`/edit/${p.id}`) }}
                      title="Edit this property"
                      className="bg-white/95 hover:bg-blue-600 hover:text-white text-gray-700 text-xs font-semibold px-2 py-1 rounded-lg shadow border border-gray-200 transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleWmUnmark(p.id) }}
                      title="Remove from flagged list"
                      className="bg-white/95 hover:bg-white text-gray-700 hover:text-gray-900 text-xs font-semibold px-2 py-1 rounded-lg shadow border border-gray-200 transition-colors"
                    >
                      Unmark
                    </button>
                  </div>
                  <PropertyCard
                    property={p}
                    onClick={() => navigate(`/edit/${p.id}`)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Bulk action bar */}
      {selectMode && (
        <div className="mb-4 flex flex-wrap items-center gap-3 bg-gray-900 text-white px-4 py-3 rounded-lg">
          <button
            onClick={toggleSelectAll}
            className="text-sm text-gray-300 hover:text-white underline"
          >
            {selectedIds.size === filtered.length ? 'Deselect All' : `Select All (${filtered.length})`}
          </button>
          <span className="text-gray-400 text-sm">{selectedIds.size} selected</span>
          <div className="flex gap-2 ml-auto flex-wrap">
            <button
              onClick={() => handleBulkAction('ready')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              className="text-xs bg-amber-500 hover:bg-amber-400 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Mark Ready
            </button>
            <button
              onClick={() => handleBulkAction('sync')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              title="Sync field changes to the live site for all selected published listings"
              className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Sync to Live
            </button>
            <button
              onClick={() => handleBulkAction('archive')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              className="text-xs bg-gray-600 hover:bg-gray-500 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Archive
            </button>
            <button
              onClick={() => handleBulkAction('delete')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              className="text-xs bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* Bulk action result */}
      {bulkResult && (
        <div className={`mb-4 px-4 py-2 rounded-lg text-sm ${bulkResult.failed > 0 ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-green-50 text-green-800 border border-green-200'}`}>
          {bulkResult.success} succeeded{bulkResult.failed > 0 ? `, ${bulkResult.failed} failed` : ''}
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 mb-6">
        <input
          type="text"
          placeholder="Search by address or city..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2.5 sm:py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-gray-400"
        />
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2.5 sm:py-2 flex-1 sm:flex-none focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="scraped">Scraped</option>
            <option value="edited">Edited</option>
            <option value="ready">Ready</option>
            <option value="published">Published</option>
            <option value="rented">Rented</option>
            <option value="archived">Archived</option>
          </select>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2.5 sm:py-2 flex-1 sm:flex-none focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white"
          >
            <option value="scraped_at">Newest First</option>
            <option value="price_asc">Price ↑</option>
            <option value="price_desc">Price ↓</option>
            <option value="bedrooms">Bedrooms</option>
            <option value="completeness_asc">Needs Attention</option>
            <option value="completeness_desc">Most Complete</option>
          </select>
        </div>
      </div>

      {!selectMode && data && data.length > 0 && (
        <RecentlyViewedStrip properties={data} />
      )}

      <PullToRefresh onRefresh={() => refetch()}>
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">No properties found.</p>
            <p className="text-sm mt-2">
              Try adjusting your filters or{' '}
              <Link to="/scraper" className="text-gray-700 underline">
                scrape new listings
              </Link>
              .
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((property) => (
              <LongPressPropertyCard
                key={property.id}
                property={property}
                selectMode={selectMode}
                selected={selectedIds.has(property.id)}
                onTap={() => navigate(`/edit/${property.id}`)}
                onToggleSelect={() => toggleSelect(property.id)}
                onLongPressEnter={() => {
                  if (!selectMode) setSelectMode(true)
                  toggleSelect(property.id)
                }}
                aiHealth={scanHealthMap ? (scanHealthMap[String(property.id)] || null) : null}
              />
            ))}
          </div>
        )}
      </PullToRefresh>

      {confirmModal && (
        <ConfirmModal
          {...confirmModal}
          onCancel={closeConfirm}
          onConfirm={() => {
            const fn = confirmModal.onConfirm
            closeConfirm()
            fn?.()
          }}
        />
      )}
    </div>
  )
}

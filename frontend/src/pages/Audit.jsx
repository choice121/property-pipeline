import { useState, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getProperties, aiBulkScan, aiBulkClean, getScrapeRuns } from '../api/client'
import StatusBadge from '../components/StatusBadge'
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

function formatRelativeTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const now = new Date()
  const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return '1 day ago'
  if (diffDays < 30) return `${diffDays}d ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
  return `${Math.floor(diffDays / 365)}y ago`
}

function SeverityDot({ count, color }) {
  if (!count) return null
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {count}
    </span>
  )
}

function SparkleIcon({ spin = false }) {
  return (
    <svg className={`w-4 h-4 ${spin ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
    </svg>
  )
}

function parseMeta(run) {
  const raw = run.meta_json || run.error_message || ''
  if (!raw) return {}
  try { return JSON.parse(raw) } catch { return {} }
}

function yieldPct(run) {
  if (!run.count_total || run.count_total === 0) return null
  return Math.round((run.count_new / run.count_total) * 100)
}

function yieldColor(pct) {
  if (pct === null) return { bg: 'bg-gray-300', text: 'text-gray-500', ring: 'ring-gray-200' }
  if (pct >= 60) return { bg: 'bg-emerald-500', text: 'text-emerald-700', ring: 'ring-emerald-200' }
  if (pct >= 30) return { bg: 'bg-amber-400', text: 'text-amber-700', ring: 'ring-amber-200' }
  return { bg: 'bg-rose-500', text: 'text-rose-700', ring: 'ring-rose-200' }
}

function ScoreChip({ score }) {
  if (score == null) return <span className="text-gray-300 text-xs">—</span>
  const cls = score >= 70 ? 'text-emerald-700 bg-emerald-50' : score >= 50 ? 'text-amber-700 bg-amber-50' : 'text-rose-700 bg-rose-50'
  return <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${cls}`}>{score}</span>
}

function MiniSparkline({ runs }) {
  const MAX_BARS = 12
  const items = [...runs].reverse().slice(-MAX_BARS)
  const pcts = items.map(yieldPct)
  const maxVal = Math.max(...pcts.filter(p => p !== null), 1)
  return (
    <div className="flex items-end gap-0.5 h-8">
      {pcts.map((pct, i) => {
        const col = yieldColor(pct)
        const h = pct === null ? 4 : Math.max(4, Math.round((pct / maxVal) * 28))
        return (
          <div
            key={i}
            title={pct === null ? 'No data' : `${pct}% yield`}
            className={`w-2 rounded-sm flex-shrink-0 ${col.bg}`}
            style={{ height: h }}
          />
        )
      })}
    </div>
  )
}

function SourceCard({ source, runs }) {
  const [expanded, setExpanded] = useState(false)
  const totalRuns = runs.length
  const totalScraped = runs.reduce((s, r) => s + (r.count_total || 0), 0)
  const totalNew = runs.reduce((s, r) => s + (r.count_new || 0), 0)
  const totalWm = runs.reduce((s, r) => s + (r.count_watermarked || 0), 0)
  const totalDup = runs.reduce((s, r) => s + (r.count_duplicate || 0), 0)
  const totalInv = runs.reduce((s, r) => s + (r.count_validation_rejected || 0), 0)
  const scores = runs.map(r => r.avg_score).filter(s => s != null)
  const avgScore = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null
  const overallYield = totalScraped > 0 ? Math.round((totalNew / totalScraped) * 100) : null
  const col = yieldColor(overallYield)
  const lastRun = runs[0]

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-gray-50 transition-colors"
      >
        <div className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${col.bg}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="font-mono text-sm font-semibold text-gray-900">{source}</span>
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span>{totalRuns} {totalRuns === 1 ? 'run' : 'runs'}</span>
              {overallYield !== null && (
                <span className={`font-semibold ${col.text}`}>{overallYield}% yield</span>
              )}
              {avgScore !== null && <ScoreChip score={avgScore} />}
            </div>
          </div>
          <div className="flex items-center justify-between gap-3 mt-2">
            <div className="flex gap-3 text-xs flex-wrap">
              <span className="text-gray-700"><strong>{totalNew.toLocaleString()}</strong> saved</span>
              <span className="text-gray-400">of {totalScraped.toLocaleString()} scraped</span>
              {totalWm > 0 && <span className="text-amber-600">🔍 {totalWm} wm</span>}
              {totalDup > 0 && <span className="text-gray-400">⟳ {totalDup} dup</span>}
              {totalInv > 0 && <span className="text-rose-600">✕ {totalInv} invalid</span>}
            </div>
            <div className="flex-shrink-0">
              <MiniSparkline runs={runs} />
            </div>
          </div>
          {lastRun?.completed_at && (
            <p className="text-[11px] text-gray-400 mt-1">
              Last run {formatRelativeTime(lastRun.completed_at)}
              {lastRun.location ? ` · ${lastRun.location}` : ''}
            </p>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Timeline strip — always visible */}
      <div className="px-4 pb-2 flex items-center gap-1.5 flex-wrap">
        {[...runs].reverse().map((run, i) => {
          const pct = yieldPct(run)
          const c = yieldColor(pct)
          const meta = parseMeta(run)
          const wm = run.count_watermarked ?? meta.watermarked_dropped ?? 0
          const dup = run.count_duplicate ?? meta.duplicate_skipped ?? 0
          const inv = run.count_validation_rejected ?? meta.validation_rejected ?? 0
          const tip = [
            run.completed_at ? new Date(run.completed_at).toLocaleDateString() : null,
            `${run.count_new ?? 0}/${run.count_total ?? 0} saved`,
            pct !== null ? `${pct}% yield` : null,
            wm > 0 ? `${wm} watermarked` : null,
            dup > 0 ? `${dup} duplicates` : null,
            inv > 0 ? `${inv} invalid` : null,
          ].filter(Boolean).join(' · ')
          return (
            <div
              key={run.id || i}
              title={tip}
              className={`w-3 h-3 rounded-full flex-shrink-0 ring-2 ${c.bg} ${c.ring} cursor-default`}
            />
          )
        })}
        <span className="text-[10px] text-gray-400 ml-1">older → newer</span>
      </div>

      {/* Expanded: per-run detail table */}
      {expanded && (
        <div className="border-t border-gray-100 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left border-b border-gray-100 bg-gray-50 text-gray-500">
                <th className="px-4 py-2 font-medium">When</th>
                <th className="px-4 py-2 font-medium">Location</th>
                <th className="px-4 py-2 font-medium text-right">Scraped</th>
                <th className="px-4 py-2 font-medium text-right">Saved</th>
                <th className="px-4 py-2 font-medium text-right">Yield</th>
                <th className="px-4 py-2 font-medium text-right">Wm</th>
                <th className="px-4 py-2 font-medium text-right">Dup</th>
                <th className="px-4 py-2 font-medium text-right">Invalid</th>
                <th className="px-4 py-2 font-medium text-right">Score</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run, i) => {
                const meta = parseMeta(run)
                const wm = run.count_watermarked ?? meta.watermarked_dropped ?? 0
                const dup = run.count_duplicate ?? meta.duplicate_skipped ?? 0
                const inv = run.count_validation_rejected ?? meta.validation_rejected ?? 0
                const pct = yieldPct(run)
                const c = yieldColor(pct)
                return (
                  <tr key={run.id || i} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                      {run.completed_at ? formatRelativeTime(run.completed_at) : '—'}
                    </td>
                    <td className="px-4 py-2 text-gray-600 max-w-[140px] truncate">{run.location || '—'}</td>
                    <td className="px-4 py-2 text-right font-semibold text-gray-900">{run.count_total ?? 0}</td>
                    <td className="px-4 py-2 text-right text-emerald-700 font-semibold">{run.count_new ?? 0}</td>
                    <td className="px-4 py-2 text-right">
                      {pct !== null
                        ? <span className={`font-semibold ${c.text}`}>{pct}%</span>
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-2 text-right">{wm > 0 ? <span className="text-amber-600">{wm}</span> : <span className="text-gray-300">—</span>}</td>
                    <td className="px-4 py-2 text-right">{dup > 0 ? <span className="text-gray-500">{dup}</span> : <span className="text-gray-300">—</span>}</td>
                    <td className="px-4 py-2 text-right">{inv > 0 ? <span className="text-rose-600">{inv}</span> : <span className="text-gray-300">—</span>}</td>
                    <td className="px-4 py-2 text-right"><ScoreChip score={run.avg_score} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ScrapeTrends({ runs }) {
  if (!runs || runs.length === 0) return null

  const bySource = {}
  runs.forEach(run => {
    const src = run.source || 'unknown'
    if (!bySource[src]) bySource[src] = []
    bySource[src].push(run)
  })

  const sources = Object.entries(bySource).sort((a, b) => b[1].length - a[1].length)

  const totalRuns = runs.length
  const totalScraped = runs.reduce((s, r) => s + (r.count_total || 0), 0)
  const totalNew = runs.reduce((s, r) => s + (r.count_new || 0), 0)
  const overallYield = totalScraped > 0 ? Math.round((totalNew / totalScraped) * 100) : null
  const scores = runs.map(r => r.avg_score).filter(s => s != null)
  const avgScore = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null

  return (
    <div className="mt-8 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">Scrape Run History</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {totalRuns} runs · {totalNew.toLocaleString()} saved of {totalScraped.toLocaleString()} scraped
            {overallYield !== null ? ` · ${overallYield}% overall yield` : ''}
            {avgScore !== null ? ` · avg score ${avgScore}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-gray-400">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />≥60% yield</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />30–59%</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />&lt;30%</span>
        </div>
      </div>
      {sources.map(([source, sourceRuns]) => (
        <SourceCard key={source} source={source} runs={sourceRuns} />
      ))}
    </div>
  )
}

export default function Audit() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [sort, setSort] = useState('errors_desc')
  const [statusFilter, setStatusFilter] = useState('')
  const [scanning, setScanning] = useState(false)
  const [healthMap, setHealthMap] = useState(null)
  const [scanError, setScanError] = useState(null)
  const [scannedAt, setScannedAt] = useState(null)

  const [cleaning, setCleaning] = useState(false)
  const [cleanResult, setCleanResult] = useState(null)
  const [cleanError, setCleanError] = useState(null)

  const { data: properties, isLoading } = useQuery({
    queryKey: ['properties'],
    queryFn: () => getProperties().then(r => r.data),
  })

  const { data: scrapeRuns } = useQuery({
    queryKey: ['scrapeRuns'],
    queryFn: () => getScrapeRuns(50).then(r => r.data),
    staleTime: 60_000,
  })

  const filtered = useMemo(() => {
    if (!properties) return []
    let list = [...properties]
    if (statusFilter) list = list.filter(p => p.status === statusFilter)
    return list
  }, [properties, statusFilter])

  const sorted = useMemo(() => {
    if (!filtered) return []
    const list = [...filtered]
    if (sort === 'errors_desc') {
      list.sort((a, b) => {
        const ae = (healthMap?.[a.id]?.errors || 0) + (healthMap?.[a.id]?.warnings || 0)
        const be = (healthMap?.[b.id]?.errors || 0) + (healthMap?.[b.id]?.warnings || 0)
        return be - ae
      })
    } else if (sort === 'completeness_asc') {
      list.sort((a, b) => computeCompleteness(a).score - computeCompleteness(b).score)
    } else if (sort === 'updated_desc') {
      list.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0))
    } else if (sort === 'rent_asc') {
      list.sort((a, b) => (a.monthly_rent || 0) - (b.monthly_rent || 0))
    }
    return list
  }, [filtered, sort, healthMap])

  const summary = useMemo(() => {
    if (!healthMap || !filtered) return null
    let errors = 0, warnings = 0, clean = 0, noScan = 0
    filtered.forEach(p => {
      const h = healthMap[String(p.id)]
      if (!h) { noScan++; return }
      if (h.errors > 0) errors++
      else if (h.warnings > 0) warnings++
      else clean++
    })
    return { errors, warnings, clean, noScan, total: filtered.length }
  }, [healthMap, filtered])

  const daysSinceUpdate = (iso) => {
    if (!iso) return 999
    return Math.floor((new Date() - new Date(iso)) / (1000 * 60 * 60 * 24))
  }

  async function handleScan() {
    if (scanning || filtered.length === 0) return
    setScanning(true)
    setScanError(null)
    try {
      const props = filtered.map(p => ({ id: String(p.id), property: buildContext(p) }))
      const res = await aiBulkScan({ properties: props })
      const map = {}
      ;(res.data.results || []).forEach(r => { map[r.id] = r })
      setHealthMap(map)
      setScannedAt(new Date())
    } catch (e) {
      setScanError(e.response?.data?.detail || e.message || 'Scan failed.')
    } finally {
      setScanning(false)
    }
  }

  async function handleBulkClean() {
    const toClean = filtered
      .filter(p => p.description && p.description.length > 20)
      .map(p => p.id)
    if (toClean.length === 0) return
    if (!window.confirm(`Clean descriptions for ${toClean.length} properties? This will use AI to strip contact info and gatekeeping language.`)) return
    setCleaning(true)
    setCleanResult(null)
    setCleanError(null)
    try {
      const res = await aiBulkClean({ property_ids: toClean })
      setCleanResult(res.data)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
    } catch (e) {
      setCleanError(e.response?.data?.detail || e.message || 'Bulk clean failed.')
    } finally {
      setCleaning(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-14 bg-gray-200 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Audit Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Library-wide quality check across all {filtered.length} listings</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
          <button
            onClick={handleBulkClean}
            disabled={cleaning || filtered.length === 0}
            className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 transition-colors"
          >
            <svg className={`w-4 h-4 ${cleaning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              {cleaning
                ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></>
                : <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              }
            </svg>
            {cleaning ? 'Cleaning…' : 'Clean All Descriptions'}
          </button>

          <button
            onClick={handleScan}
            disabled={scanning || filtered.length === 0}
            className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border border-purple-300 bg-purple-50 text-purple-700 hover:bg-purple-100 disabled:opacity-50 transition-colors"
          >
            <SparkleIcon spin={scanning} />
            {scanning ? 'Scanning…' : `Scan All (${filtered.length})`}
          </button>
        </div>
      </div>

      {scanError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex justify-between">
          <span>{scanError}</span>
          <button onClick={() => setScanError(null)} className="ml-3 text-red-400 hover:text-red-600">×</button>
        </div>
      )}

      {cleanError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex justify-between">
          <span>{cleanError}</span>
          <button onClick={() => setCleanError(null)} className="ml-3 text-red-400 hover:text-red-600">×</button>
        </div>
      )}

      {cleanResult && (
        <div className="mb-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg">
          <div className="flex justify-between items-start">
            <p className="text-sm font-semibold text-emerald-900">Bulk Clean Complete</p>
            <button onClick={() => setCleanResult(null)} className="text-emerald-400 hover:text-emerald-600">×</button>
          </div>
          <div className="flex gap-4 mt-1.5 text-sm">
            <span className="text-emerald-700"><strong>{cleanResult.cleaned}</strong> cleaned</span>
            <span className="text-gray-600"><strong>{cleanResult.skipped}</strong> already clean</span>
            {cleanResult.errors > 0 && <span className="text-red-600"><strong>{cleanResult.errors}</strong> errors</span>}
          </div>
        </div>
      )}

      {summary && (
        <div className="mb-4 px-4 py-3 bg-purple-50 border border-purple-200 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-purple-900">
              Scan results — {scannedAt?.toLocaleTimeString()}
            </span>
            <button onClick={() => setHealthMap(null)} className="text-purple-400 hover:text-purple-600">×</button>
          </div>
          <div className="flex gap-4 mt-2 flex-wrap">
            {summary.errors > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-red-700">
                <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
                <strong>{summary.errors}</strong> need fixes
              </span>
            )}
            {summary.warnings > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-amber-700">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                <strong>{summary.warnings}</strong> have warnings
              </span>
            )}
            {summary.clean > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-green-700">
                <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                <strong>{summary.clean}</strong> look good
              </span>
            )}
          </div>
        </div>
      )}

      <div className="flex gap-2 mb-4 flex-wrap">
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          <option value="">All Statuses</option>
          <option value="scraped">Scraped</option>
          <option value="edited">Edited</option>
          <option value="ready">Ready</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </select>
        <select
          value={sort}
          onChange={e => setSort(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          <option value="errors_desc">Most Issues First</option>
          <option value="completeness_asc">Least Complete First</option>
          <option value="updated_desc">Recently Updated</option>
          <option value="rent_asc">Rent ↑</option>
        </select>
      </div>

      {sorted.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">No properties found.</p>
        </div>
      ) : (
        <>
        {/* ── Mobile card list ── */}
        <div className="md:hidden space-y-2">
          {sorted.map(prop => {
            const health = healthMap ? (healthMap[String(prop.id)] || null) : null
            const { score } = computeCompleteness(prop)
            const days = daysSinceUpdate(prop.updated_at)
            const isStale = days > 30
            const hasErrors = health?.errors > 0
            const hasWarnings = health?.warnings > 0
            const accent = hasErrors
              ? 'border-l-red-500 bg-red-50/30'
              : hasWarnings
                ? 'border-l-amber-400 bg-amber-50/30'
                : health
                  ? 'border-l-green-500 bg-green-50/20'
                  : 'border-l-gray-300'
            return (
              <button
                key={prop.id}
                onClick={() => navigate(`/edit/${prop.id}`)}
                className={`w-full text-left bg-white rounded-lg border border-gray-200 border-l-4 ${accent} p-3 active:scale-[0.99] transition-transform shadow-sm`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">{prop.title || prop.address || 'No address'}</p>
                    <p className="text-xs text-gray-500 truncate mt-0.5">
                      {[prop.city, prop.state].filter(Boolean).join(', ')}
                      {prop.monthly_rent ? ` · $${Number(prop.monthly_rent).toLocaleString()}/mo` : ''}
                    </p>
                  </div>
                  <StatusBadge status={prop.status} />
                </div>

                <div className="flex items-center justify-between mt-2.5 gap-2">
                  <div className="flex items-center gap-2 flex-1">
                    <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden flex-shrink-0">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${score}%`,
                          backgroundColor: score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444',
                        }}
                      />
                    </div>
                    <span className="text-xs text-gray-500 font-medium">{score}%</span>
                  </div>
                  <span className="text-[11px] text-gray-400">{formatRelativeTime(prop.updated_at)}</span>
                </div>

                {(health || isStale) && (
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    {health?.errors > 0 && <SeverityDot count={health.errors} color="bg-red-100 text-red-700" />}
                    {health?.warnings > 0 && <SeverityDot count={health.warnings} color="bg-amber-100 text-amber-700" />}
                    {health?.suggestions > 0 && <SeverityDot count={health.suggestions} color="bg-blue-100 text-blue-700" />}
                    {health && health.errors === 0 && health.warnings === 0 && health.suggestions === 0 && (
                      <span className="text-[11px] text-green-700 font-medium bg-green-100 px-1.5 py-0.5 rounded-full">Clean</span>
                    )}
                    {isStale && (
                      <span className="text-[11px] font-medium text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full">
                        Stale {days}d
                      </span>
                    )}
                    {health?.top_issue && (
                      <span className="text-[11px] text-gray-500 truncate w-full">{health.top_issue}</span>
                    )}
                  </div>
                )}
              </button>
            )
          })}
        </div>

        {/* ── Desktop table ── */}
        <div className="hidden md:block bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <th className="px-4 py-3">Property</th>
                  <th className="px-4 py-3 hidden sm:table-cell">Status</th>
                  <th className="px-4 py-3 hidden md:table-cell">Completeness</th>
                  <th className="px-4 py-3">Issues</th>
                  <th className="px-4 py-3 hidden sm:table-cell">Last Updated</th>
                  <th className="px-4 py-3 hidden lg:table-cell">Freshness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sorted.map(prop => {
                  const health = healthMap ? (healthMap[String(prop.id)] || null) : null
                  const { score } = computeCompleteness(prop)
                  const days = daysSinceUpdate(prop.updated_at)
                  const isStale = days > 30
                  const hasErrors = health?.errors > 0
                  const hasWarnings = health?.warnings > 0

                  let rowBg = 'hover:bg-gray-50'
                  if (health) {
                    if (hasErrors) rowBg = 'bg-red-50/40 hover:bg-red-50'
                    else if (hasWarnings) rowBg = 'bg-amber-50/40 hover:bg-amber-50'
                    else rowBg = 'bg-green-50/30 hover:bg-green-50'
                  }

                  return (
                    <tr
                      key={prop.id}
                      onClick={() => navigate(`/edit/${prop.id}`)}
                      className={`cursor-pointer transition-colors ${rowBg}`}
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900 truncate max-w-xs">
                          {prop.title || prop.address || 'No address'}
                        </p>
                        <p className="text-xs text-gray-500 truncate">
                          {[prop.city, prop.state].filter(Boolean).join(', ')}
                          {prop.monthly_rent ? ` · $${Number(prop.monthly_rent).toLocaleString()}/mo` : ''}
                        </p>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <StatusBadge status={prop.status} />
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden flex-shrink-0">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${score}%`,
                                backgroundColor: score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444',
                              }}
                            />
                          </div>
                          <span className="text-xs text-gray-500">{score}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {health ? (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {health.errors > 0 && (
                              <SeverityDot count={health.errors} color="bg-red-100 text-red-700" />
                            )}
                            {health.warnings > 0 && (
                              <SeverityDot count={health.warnings} color="bg-amber-100 text-amber-700" />
                            )}
                            {health.suggestions > 0 && (
                              <SeverityDot count={health.suggestions} color="bg-blue-100 text-blue-700" />
                            )}
                            {health.errors === 0 && health.warnings === 0 && health.suggestions === 0 && (
                              <span className="text-xs text-green-700 font-medium">Clean</span>
                            )}
                            {health.top_issue && (
                              <span className="text-xs text-gray-500 hidden lg:inline truncate max-w-xs" title={health.top_issue}>
                                {health.top_issue}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">Not scanned</span>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell text-xs text-gray-500">
                        {formatRelativeTime(prop.updated_at)}
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell">
                        {isStale ? (
                          <span className="text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                            Stale ({days}d)
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">Fresh</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
        </>
      )}

      <ScrapeTrends runs={scrapeRuns} />
    </div>
  )
}

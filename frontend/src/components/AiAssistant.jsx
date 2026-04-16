import { useState, useRef, useEffect } from 'react'
import { aiRewriteDescription, aiDetectIssues, aiChat, aiAutoFill, aiScore, aiPricingIntel, aiSeoOptimize, aiCleanProperty, aiGenerateTitle } from '../api/client'

const SEVERITY_STYLES = {
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  suggestion: 'bg-blue-50 border-blue-200 text-blue-700',
}
const SEVERITY_ICON = { error: '✕', warning: '⚠', suggestion: '💡' }

const AUTOFILL_FIELDS = [
  'description', 'heating_type', 'cooling_type', 'laundry_type',
  'parking', 'flooring', 'lease_terms', 'showing_instructions',
  'pet_details', 'pet_types_allowed', 'amenities', 'appliances',
  'utilities_included', 'move_in_special',
]

const ARRAY_FIELDS = new Set([
  'flooring', 'lease_terms', 'pet_types_allowed',
  'amenities', 'appliances', 'utilities_included',
])

const FIELD_LABELS = {
  description: 'Description', heating_type: 'Heating Type',
  cooling_type: 'Cooling Type', laundry_type: 'Laundry Type',
  parking: 'Parking', flooring: 'Flooring',
  lease_terms: 'Lease Terms', showing_instructions: 'Showing Instructions',
  pet_details: 'Pet Details', pet_types_allowed: 'Pet Types Allowed',
  amenities: 'Amenities', appliances: 'Appliances',
  utilities_included: 'Utilities Included', move_in_special: 'Move-in Special',
}

function buildPropertyContext(form) {
  const tryParseArray = (val) => {
    try { return JSON.parse(val || '[]').join(', ') } catch { return val || '' }
  }
  return {
    address: form.address,
    city: form.city,
    state: form.state,
    bedrooms: form.bedrooms ? Number(form.bedrooms) : null,
    bathrooms: form.bathrooms ? Number(form.bathrooms) : null,
    square_footage: form.square_footage ? Number(form.square_footage) : null,
    year_built: form.year_built ? Number(form.year_built) : null,
    monthly_rent: form.monthly_rent ? Number(form.monthly_rent) : null,
    property_type: form.property_type,
    amenities: tryParseArray(form.amenities),
    appliances: tryParseArray(form.appliances),
    pets_allowed: form.pets_allowed ?? null,
    parking: form.parking,
    heating_type: form.heating_type,
    cooling_type: form.cooling_type,
    laundry_type: form.laundry_type,
    utilities_included: tryParseArray(form.utilities_included),
    description: form.description,
    lease_terms: tryParseArray(form.lease_terms),
    flooring: tryParseArray(form.flooring),
    has_basement: form.has_basement ?? null,
    has_central_air: form.has_central_air ?? null,
  }
}

function getEmptyFillableFields(form) {
  return AUTOFILL_FIELDS.filter((field) => {
    const val = form[field]
    if (!val) return true
    if (typeof val === 'string') {
      try {
        const parsed = JSON.parse(val)
        if (Array.isArray(parsed)) return parsed.length === 0
      } catch {}
      return val.trim() === ''
    }
    return false
  })
}

function SparkleIcon({ spin = false }) {
  return (
    <svg className={`w-4 h-4 ${spin ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
    </svg>
  )
}

const GRADE_COLOR = {
  A: 'text-green-700 bg-green-50 border-green-200',
  B: 'text-blue-700 bg-blue-50 border-blue-200',
  C: 'text-amber-700 bg-amber-50 border-amber-200',
  D: 'text-orange-700 bg-orange-50 border-orange-200',
  F: 'text-red-700 bg-red-50 border-red-200',
}

const PRICING_COLOR = {
  very_low: { bg: 'bg-blue-50 border-blue-200 text-blue-800', label: 'Very Low' },
  low:      { bg: 'bg-blue-50 border-blue-200 text-blue-800', label: 'Below Market' },
  fair:     { bg: 'bg-green-50 border-green-200 text-green-800', label: 'Fair Market' },
  high:     { bg: 'bg-amber-50 border-amber-200 text-amber-800', label: 'Above Market' },
  very_high:{ bg: 'bg-red-50 border-red-200 text-red-800', label: 'Very High' },
  unknown:  { bg: 'bg-gray-50 border-gray-200 text-gray-700', label: 'Unknown' },
}

export default function AiAssistant({ form, propertyId, onApplyDescription, onApplyFields }) {
  const [tab, setTab] = useState('autofill')
  const [tone, setTone] = useState('professional')

  const [rewriting, setRewriting] = useState(false)
  const [rewriteResult, setRewriteResult] = useState(null)
  const [rewriteError, setRewriteError] = useState(null)
  const [draftHistory, setDraftHistory] = useState([])
  const [viewingDraft, setViewingDraft] = useState(null)

  const [detecting, setDetecting] = useState(false)
  const [issues, setIssues] = useState(null)
  const [issuesError, setIssuesError] = useState(null)

  const [filling, setFilling] = useState(false)
  const [fillSuggestions, setFillSuggestions] = useState(null)
  const [fillError, setFillError] = useState(null)
  const [selected, setSelected] = useState({})

  const [chatHistory, setChatHistory] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef(null)

  const [scoring, setScoring] = useState(false)
  const [scoreResult, setScoreResult] = useState(null)
  const [scoreError, setScoreError] = useState(null)

  const [pricing, setPricing] = useState(false)
  const [pricingResult, setPricingResult] = useState(null)
  const [pricingError, setPricingError] = useState(null)

  const [seoing, setSeoing] = useState(false)
  const [seoResult, setSeoResult] = useState(null)
  const [seoError, setSeoError] = useState(null)

  const [cleaning, setCleaning] = useState(false)
  const [cleanResult, setCleanResult] = useState(null)
  const [cleanError, setCleanError] = useState(null)

  const [generatingTitle, setGeneratingTitle] = useState(false)
  const [titleResult, setTitleResult] = useState(null)
  const [titleError, setTitleError] = useState(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  async function handleRewrite() {
    setRewriting(true)
    setRewriteResult(null)
    setRewriteError(null)
    setViewingDraft(null)
    try {
      const res = await aiRewriteDescription({ property: buildPropertyContext(form), tone })
      const text = res.data.description
      setRewriteResult(text)
      setDraftHistory(prev => [{ text, tone, ts: new Date().toLocaleTimeString() }, ...prev].slice(0, 5))
    } catch (e) {
      setRewriteError(e.response?.data?.detail || e.message)
    } finally {
      setRewriting(false)
    }
  }

  async function handleDetectIssues() {
    setDetecting(true)
    setIssues(null)
    setIssuesError(null)
    try {
      const res = await aiDetectIssues({ property: buildPropertyContext(form) })
      setIssues(res.data.issues || [])
    } catch (e) {
      setIssuesError(e.response?.data?.detail || e.message)
    } finally {
      setDetecting(false)
    }
  }

  async function handleAutoFill() {
    const emptyFields = getEmptyFillableFields(form)
    if (emptyFields.length === 0) {
      setFillSuggestions({})
      return
    }
    setFilling(true)
    setFillSuggestions(null)
    setFillError(null)
    setSelected({})
    try {
      const res = await aiAutoFill({ property: buildPropertyContext(form), fields: emptyFields })
      const suggestions = res.data.suggestions || {}
      setFillSuggestions(suggestions)
      const allSelected = {}
      Object.keys(suggestions).forEach((k) => { allSelected[k] = true })
      setSelected(allSelected)
    } catch (e) {
      setFillError(e.response?.data?.detail || e.message)
    } finally {
      setFilling(false)
    }
  }

  function handleApplySelected() {
    const toApply = {}
    Object.entries(fillSuggestions).forEach(([field, value]) => {
      if (!selected[field]) return
      if (ARRAY_FIELDS.has(field)) {
        toApply[field] = JSON.stringify(
          value.split(',').map((s) => s.trim()).filter(Boolean)
        )
      } else {
        toApply[field] = value
      }
    })
    onApplyFields(toApply)
    setFillSuggestions(null)
    setSelected({})
  }

  async function handleChatSend() {
    const message = chatInput.trim()
    if (!message || chatLoading) return
    setChatInput('')
    const newHistory = [...chatHistory, { role: 'user', content: message }]
    setChatHistory(newHistory)
    setChatLoading(true)
    try {
      const res = await aiChat({ property: buildPropertyContext(form), message, history: chatHistory })
      setChatHistory([...newHistory, { role: 'assistant', content: res.data.reply }])
    } catch (e) {
      setChatHistory([...newHistory, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }])
    } finally {
      setChatLoading(false)
    }
  }

  async function handleScore() {
    setScoring(true)
    setScoreResult(null)
    setScoreError(null)
    try {
      const res = await aiScore({ property: buildPropertyContext(form) })
      setScoreResult(res.data)
    } catch (e) {
      setScoreError(e.response?.data?.detail || e.message)
    } finally {
      setScoring(false)
    }
  }

  async function handlePricing() {
    setPricing(true)
    setPricingResult(null)
    setPricingError(null)
    try {
      const res = await aiPricingIntel({ property: buildPropertyContext(form) })
      setPricingResult(res.data)
    } catch (e) {
      setPricingError(e.response?.data?.detail || e.message)
    } finally {
      setPricing(false)
    }
  }

  async function handleSeo() {
    setSeoing(true)
    setSeoResult(null)
    setSeoError(null)
    try {
      const res = await aiSeoOptimize({ property: buildPropertyContext(form), description: form.description || '' })
      setSeoResult(res.data)
    } catch (e) {
      setSeoError(e.response?.data?.detail || e.message)
    } finally {
      setSeoing(false)
    }
  }

  async function handleClean() {
    setCleaning(true)
    setCleanResult(null)
    setCleanError(null)
    try {
      const res = await aiCleanProperty({
        property_id: propertyId || null,
        property: buildPropertyContext(form),
      })
      setCleanResult(res.data)
    } catch (e) {
      setCleanError(e.response?.data?.detail || e.message)
    } finally {
      setCleaning(false)
    }
  }

  async function handleGenerateTitle() {
    setGeneratingTitle(true)
    setTitleResult(null)
    setTitleError(null)
    try {
      const res = await aiGenerateTitle({
        property_id: propertyId || null,
        property: buildPropertyContext(form),
      })
      setTitleResult(res.data.title)
    } catch (e) {
      setTitleError(e.response?.data?.detail || e.message)
    } finally {
      setGeneratingTitle(false)
    }
  }

  const tabCls = (t) =>
    `px-2.5 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
      tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
    }`

  const emptyCount = getEmptyFillableFields(form).length
  const displayDraft = viewingDraft !== null ? draftHistory[viewingDraft]?.text : rewriteResult

  return (
    <div className="bg-white rounded-lg border border-purple-200 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-purple-100">
        <span className="text-purple-600"><SparkleIcon /></span>
        <span className="text-sm font-semibold text-purple-900">AI Assistant</span>
        <span className="text-xs text-purple-400 ml-1">powered by DeepSeek</span>
      </div>

      <div className="p-1 border-b border-gray-100 bg-gray-50 flex gap-1 overflow-x-auto scrollbar-none">
        <button className={tabCls('autofill')} onClick={() => setTab('autofill')}>
          Auto-Fill
          {emptyCount > 0 && (
            <span className="ml-1.5 bg-purple-100 text-purple-700 text-xs px-1.5 py-0.5 rounded-full">{emptyCount}</span>
          )}
        </button>
        <button className={tabCls('rewrite')} onClick={() => setTab('rewrite')}>Rewrite</button>
        <button className={tabCls('clean')} onClick={() => setTab('clean')}>Clean</button>
        <button className={tabCls('title')} onClick={() => setTab('title')}>Title</button>
        <button className={tabCls('issues')} onClick={() => setTab('issues')}>Issues</button>
        <button className={tabCls('score')} onClick={() => setTab('score')}>Score</button>
        <button className={tabCls('pricing')} onClick={() => setTab('pricing')}>Pricing</button>
        <button className={tabCls('seo')} onClick={() => setTab('seo')}>SEO</button>
        <button className={tabCls('chat')} onClick={() => setTab('chat')}>Chat</button>
      </div>

      <div className="p-4">

        {tab === 'autofill' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">
              Scan the listing for empty fields and let AI suggest values based on what you've already filled in.
              {emptyCount > 0
                ? <span className="ml-1 font-medium text-purple-700">{emptyCount} fillable field{emptyCount !== 1 ? 's' : ''} detected as empty.</span>
                : <span className="ml-1 text-green-700 font-medium">All key fields are filled in.</span>
              }
            </p>
            <button
              onClick={handleAutoFill}
              disabled={filling || emptyCount === 0}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon spin={filling} />
              {filling ? 'Scanning & Generating...' : 'Auto-Fill Missing Fields'}
            </button>
            {fillError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{fillError}</p>
            )}
            {fillSuggestions !== null && (
              <div className="space-y-2">
                {Object.keys(fillSuggestions).length === 0 ? (
                  <p className="text-xs text-gray-500 bg-gray-50 px-3 py-2 rounded border border-gray-200">
                    AI couldn't confidently suggest values for the remaining fields based on the available data.
                  </p>
                ) : (
                  <>
                    <p className="text-xs font-medium text-gray-600">Review suggestions — uncheck any you don't want to apply:</p>
                    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                      {Object.entries(fillSuggestions).map(([field, value]) => (
                        <label key={field} className="flex items-start gap-2.5 p-2.5 rounded-lg border border-gray-200 hover:bg-gray-50 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={!!selected[field]}
                            onChange={(e) => setSelected((prev) => ({ ...prev, [field]: e.target.checked }))}
                            className="mt-0.5 accent-purple-600"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-gray-700">{FIELD_LABELS[field] || field}</p>
                            <p className="text-xs text-gray-500 mt-0.5 line-clamp-3 whitespace-pre-wrap">{value}</p>
                          </div>
                        </label>
                      ))}
                    </div>
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={handleApplySelected}
                        disabled={!Object.values(selected).some(Boolean)}
                        className="text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        Apply Selected ({Object.values(selected).filter(Boolean).length})
                      </button>
                      <button
                        onClick={handleAutoFill}
                        disabled={filling}
                        className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded hover:bg-gray-50 transition-colors"
                      >
                        Regenerate
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {tab === 'rewrite' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">Generate a polished listing description from the property data you've filled in.</p>
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-600">Tone:</label>
              {['professional', 'friendly', 'concise'].map((t) => (
                <button
                  key={t}
                  onClick={() => setTone(t)}
                  className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                    tone === t ? 'bg-purple-600 text-white border-purple-600' : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
            <button
              onClick={handleRewrite}
              disabled={rewriting}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon spin={rewriting} />
              {rewriting ? 'Writing...' : 'Generate Description'}
            </button>
            {rewriteError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{rewriteError}</p>
            )}

            {/* Draft history selector */}
            {draftHistory.length > 1 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-xs text-gray-400">Drafts:</span>
                {draftHistory.map((d, i) => (
                  <button
                    key={i}
                    onClick={() => setViewingDraft(i === viewingDraft ? null : i)}
                    className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                      viewingDraft === i
                        ? 'bg-purple-600 text-white border-purple-600'
                        : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    #{draftHistory.length - i} · {d.tone}
                  </button>
                ))}
              </div>
            )}

            {displayDraft && (
              <div className="space-y-2">
                <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-sm text-gray-800 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                  {displayDraft}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      onApplyDescription(displayDraft)
                      setRewriteResult(null)
                      setViewingDraft(null)
                    }}
                    className="text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 transition-colors"
                  >
                    Apply to Description
                  </button>
                  <button
                    onClick={handleRewrite}
                    disabled={rewriting}
                    className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded hover:bg-gray-50 transition-colors"
                  >
                    Regenerate
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'clean' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">
              Strip contact info, tour scheduling language, screening requirements, and "no pets" language from the description. Rewrites in Choice Properties' tenant-first brand voice.
            </p>
            {!form.description || form.description.trim().length < 20 ? (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded">
                No description to clean. Write or generate one first.
              </p>
            ) : (
              <button
                onClick={handleClean}
                disabled={cleaning}
                className="flex items-center gap-2 bg-emerald-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
              >
                <svg className={`w-4 h-4 ${cleaning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  {cleaning
                    ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></>
                    : <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                  }
                </svg>
                {cleaning ? 'Cleaning…' : 'Clean Description'}
              </button>
            )}
            {cleanError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{cleanError}</p>
            )}
            {cleanResult && (
              <div className="space-y-2">
                {!cleanResult.changes_made ? (
                  <p className="text-sm text-green-700 bg-green-50 border border-green-200 px-3 py-2 rounded">
                    Description looks clean — no problematic content detected.
                  </p>
                ) : (
                  <>
                    {cleanResult.changes_summary?.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-600 mb-1.5">What was changed:</p>
                        <ul className="space-y-1">
                          {cleanResult.changes_summary.map((c, i) => (
                            <li key={i} className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-2.5 py-1.5">✓ {c}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {cleanResult.cleaned_description && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-gray-600">Cleaned description:</p>
                        <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-sm text-gray-800 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                          {cleanResult.cleaned_description}
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              onApplyDescription(cleanResult.cleaned_description)
                              setCleanResult(null)
                            }}
                            className="text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 transition-colors"
                          >
                            Apply to Description
                          </button>
                          <button
                            onClick={handleClean}
                            disabled={cleaning}
                            className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded hover:bg-gray-50 transition-colors"
                          >
                            Re-clean
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {tab === 'title' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">
              Generate a compelling, specific listing title based on the property's data. Leads with the strongest feature, mentions the location, and stays under 80 characters.
            </p>
            {form.title && (
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Current title:</p>
                <p className="text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded px-3 py-2">
                  {form.title}
                </p>
              </div>
            )}
            <button
              onClick={handleGenerateTitle}
              disabled={generatingTitle}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon spin={generatingTitle} />
              {generatingTitle ? 'Generating…' : 'Generate Title'}
            </button>
            {titleError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{titleError}</p>
            )}
            {titleResult && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Generated title:</p>
                <div className="bg-gray-50 border border-gray-200 rounded-md px-3 py-2 text-sm font-medium text-gray-900">
                  {titleResult}
                  <span className={`ml-2 text-xs font-normal ${titleResult.length > 80 ? 'text-amber-600' : 'text-gray-400'}`}>
                    ({titleResult.length} chars)
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      onApplyFields({ title: titleResult })
                      setTitleResult(null)
                    }}
                    className="text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 transition-colors"
                  >
                    Apply Title
                  </button>
                  <button
                    onClick={handleGenerateTitle}
                    disabled={generatingTitle}
                    className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded hover:bg-gray-50 transition-colors"
                  >
                    Regenerate
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'issues' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">Scan the listing for missing info, inconsistencies, or quality issues before publishing.</p>
            <button
              onClick={handleDetectIssues}
              disabled={detecting}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon spin={detecting} />
              {detecting ? 'Scanning...' : 'Scan for Issues'}
            </button>
            {issuesError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{issuesError}</p>
            )}
            {issues !== null && (
              <div className="space-y-2">
                {issues.length === 0 ? (
                  <p className="text-sm text-green-700 bg-green-50 px-3 py-2 rounded border border-green-200">No issues found — this listing looks good!</p>
                ) : (
                  issues.map((issue, i) => (
                    <div key={i} className={`text-xs px-3 py-2 rounded border ${SEVERITY_STYLES[issue.severity] || SEVERITY_STYLES.suggestion}`}>
                      <span className="mr-1.5">{SEVERITY_ICON[issue.severity] || '•'}</span>
                      <span className="font-medium">{issue.field !== 'general' ? `${issue.field}: ` : ''}</span>
                      {issue.message}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}

        {tab === 'score' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">Get an AI quality score and written evaluation of how ready this listing is to publish.</p>
            <button
              onClick={handleScore}
              disabled={scoring}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon spin={scoring} />
              {scoring ? 'Evaluating...' : 'Evaluate Listing Quality'}
            </button>
            {scoreError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{scoreError}</p>
            )}
            {scoreResult && (
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className={`text-3xl font-bold px-3 py-1.5 rounded-lg border ${GRADE_COLOR[scoreResult.grade] || 'text-gray-700 bg-gray-50 border-gray-200'}`}>
                    {scoreResult.grade}
                  </div>
                  <div>
                    <p className="text-lg font-bold text-gray-900">{scoreResult.score}<span className="text-sm font-normal text-gray-400">/100</span></p>
                    <p className="text-xs text-gray-600 mt-0.5">{scoreResult.headline}</p>
                    {scoreResult.publish_ready
                      ? <span className="inline-block mt-1 text-xs font-medium text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 rounded-full">Publish Ready</span>
                      : <span className="inline-block mt-1 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">Not Yet Ready</span>
                    }
                  </div>
                </div>
                {scoreResult.critical_fixes?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-red-700 mb-1.5">Must fix before publishing:</p>
                    <ul className="space-y-1">
                      {scoreResult.critical_fixes.map((f, i) => (
                        <li key={i} className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2.5 py-1.5">✕ {f}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {scoreResult.strengths?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-green-700 mb-1.5">Strengths:</p>
                    <ul className="space-y-1">
                      {scoreResult.strengths.map((s, i) => (
                        <li key={i} className="text-xs text-green-700">✓ {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {scoreResult.improvements?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-600 mb-1.5">Improvements:</p>
                    <ul className="space-y-1">
                      {scoreResult.improvements.map((s, i) => (
                        <li key={i} className="text-xs text-blue-700">→ {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {tab === 'pricing' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">Evaluate how competitive this listing's rent is against the current US rental market.</p>
            <button
              onClick={handlePricing}
              disabled={pricing}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon spin={pricing} />
              {pricing ? 'Analyzing...' : 'Analyze Pricing'}
            </button>
            {pricingError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{pricingError}</p>
            )}
            {pricingResult && (() => {
              const style = PRICING_COLOR[pricingResult.assessment] || PRICING_COLOR.unknown
              return (
                <div className="space-y-2.5">
                  <div className={`flex items-center justify-between px-3 py-2.5 rounded-lg border ${style.bg}`}>
                    <span className="text-sm font-bold">{style.label}</span>
                    {pricingResult.comparable_range && (
                      <span className="text-xs font-medium opacity-75">Market: {pricingResult.comparable_range}</span>
                    )}
                  </div>
                  {pricingResult.market_context && (
                    <p className="text-xs text-gray-600 leading-relaxed">{pricingResult.market_context}</p>
                  )}
                  {pricingResult.verdict && (
                    <p className="text-xs text-gray-800 font-medium leading-relaxed">{pricingResult.verdict}</p>
                  )}
                  {pricingResult.recommendation && (
                    <div className="text-xs text-blue-700 bg-blue-50 border border-blue-200 px-3 py-2 rounded">
                      → {pricingResult.recommendation}
                    </div>
                  )}
                  <p className="text-xs text-gray-400">Confidence: {pricingResult.confidence || 'unknown'}</p>
                </div>
              )
            })()}
          </div>
        )}

        {tab === 'seo' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">Analyze how visible this listing will be in search engines and get keyword suggestions to improve reach.</p>
            <button
              onClick={handleSeo}
              disabled={seoing}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon spin={seoing} />
              {seoing ? 'Analyzing...' : 'Analyze SEO'}
            </button>
            {seoError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{seoError}</p>
            )}
            {seoResult && (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="text-2xl font-bold text-gray-900">{seoResult.score}<span className="text-sm font-normal text-gray-400">/100</span></div>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${seoResult.score}%`,
                        backgroundColor: seoResult.score >= 70 ? '#16a34a' : seoResult.score >= 45 ? '#f59e0b' : '#dc2626'
                      }}
                    />
                  </div>
                </div>
                {seoResult.title_suggestion && (
                  <div>
                    <p className="text-xs font-semibold text-gray-600 mb-1">Suggested title:</p>
                    <div className="text-xs text-gray-800 bg-gray-50 border border-gray-200 rounded px-2.5 py-2 leading-relaxed">
                      {seoResult.title_suggestion}
                    </div>
                  </div>
                )}
                {seoResult.missing_keywords?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-amber-700 mb-1.5">Missing high-value keywords:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {seoResult.missing_keywords.map((k, i) => (
                        <span key={i} className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full">{k}</span>
                      ))}
                    </div>
                  </div>
                )}
                {seoResult.present_keywords?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-green-700 mb-1.5">Keywords already present:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {seoResult.present_keywords.map((k, i) => (
                        <span key={i} className="text-xs bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded-full">✓ {k}</span>
                      ))}
                    </div>
                  </div>
                )}
                {seoResult.improvements?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-600 mb-1.5">Improvements:</p>
                    <ul className="space-y-1">
                      {seoResult.improvements.map((s, i) => (
                        <li key={i} className="text-xs text-blue-700">→ {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {seoResult.optimized_opening && (
                  <div>
                    <p className="text-xs font-semibold text-gray-600 mb-1">Optimized opening:</p>
                    <div className="text-xs text-gray-800 bg-gray-50 border border-gray-200 rounded px-2.5 py-2 leading-relaxed italic">
                      "{seoResult.optimized_opening}"
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {tab === 'chat' && (
          <div className="space-y-3">
            <div className="h-52 overflow-y-auto space-y-3 pr-1">
              {chatHistory.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-6">Ask anything about this property — editing tips, rewrites, missing info, or suggestions.</p>
              )}
              {chatHistory.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`text-sm px-3 py-2 rounded-xl max-w-[85%] whitespace-pre-wrap ${
                      msg.role === 'user'
                        ? 'bg-purple-600 text-white rounded-br-none'
                        : 'bg-gray-100 text-gray-800 rounded-bl-none'
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 text-gray-500 text-sm px-3 py-2 rounded-xl rounded-bl-none animate-pulse">Thinking...</div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
            <div className="flex gap-2">
              <input
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400"
                placeholder="e.g. Rewrite the description to be more concise..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend() } }}
                disabled={chatLoading}
              />
              <button
                onClick={handleChatSend}
                disabled={!chatInput.trim() || chatLoading}
                className="bg-purple-600 text-white px-3 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

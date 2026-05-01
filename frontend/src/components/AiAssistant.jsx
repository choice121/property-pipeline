import { useState, useRef, useEffect } from 'react'
import { aiRewriteDescription, aiDetectIssues, aiChat, aiAutoFill, aiScore, aiPricingIntel, aiSeoOptimize, aiCleanProperty, aiGenerateTitle, aiNeighborhoodContext, aiSaveFeedback, aiDescriptionHistory } from '../api/client'

const SEVERITY_STYLES = {
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  suggestion: 'bg-blue-50 border-blue-200 text-blue-700',
}
const SeverityIcon = ({ severity }) => {
  if (severity === 'error') return (
    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
  if (severity === 'warning') return (
    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  )
  return (
    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
    </svg>
  )
}

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

  const [neighborhood, setNeighborhood] = useState(false)
  const [neighborhoodResult, setNeighborhoodResult] = useState(null)
  const [neighborhoodError, setNeighborhoodError] = useState(null)

  const [feedbackSent, setFeedbackSent] = useState({})

  const [descHistory, setDescHistory] = useState(null)
  const [descHistoryLoading, setDescHistoryLoading] = useState(false)
  const [showDescHistory, setShowDescHistory] = useState(false)

  const streamingRewrite = useRef(false)
  const streamingChat = useRef(false)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  async function handleRewrite() {
    if (streamingRewrite.current) return
    streamingRewrite.current = true
    setRewriting(true)
    setRewriteResult('')
    setRewriteError(null)
    setViewingDraft(null)
    let fullText = ''
    try {
      const response = await fetch('/api/ai/rewrite-description/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ property: buildPropertyContext(form), tone }),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamDone = false
      while (!streamDone) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6)
          if (payload === '[DONE]') { streamDone = true; break }
          try {
            const parsed = JSON.parse(payload)
            if (parsed.error) throw new Error(parsed.error)
            if (parsed.content) {
              fullText += parsed.content
              setRewriteResult(fullText)
            }
          } catch (parseErr) {
            if (!(parseErr instanceof SyntaxError)) throw parseErr
          }
        }
      }
      if (fullText) {
        setDraftHistory(prev => [{ text: fullText, tone, ts: new Date().toLocaleTimeString() }, ...prev].slice(0, 5))
      }
    } catch (e) {
      setRewriteError(e.message)
      setRewriteResult(null)
    } finally {
      setRewriting(false)
      streamingRewrite.current = false
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
    if (!message || chatLoading || streamingChat.current) return
    setChatInput('')
    streamingChat.current = true
    const newHistory = [...chatHistory, { role: 'user', content: message }]
    setChatHistory(newHistory)
    setChatLoading(true)
    let assistantText = ''
    try {
      const response = await fetch('/api/ai/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          property: buildPropertyContext(form),
          history: chatHistory,
        }),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }
      setChatHistory([...newHistory, { role: 'assistant', content: '' }])
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamDone = false
      while (!streamDone) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6)
          if (payload === '[DONE]') { streamDone = true; break }
          try {
            const parsed = JSON.parse(payload)
            if (parsed.error) throw new Error(parsed.error)
            if (parsed.content) {
              assistantText += parsed.content
              setChatHistory(prev => {
                const next = [...prev]
                next[next.length - 1] = { role: 'assistant', content: assistantText }
                return next
              })
            }
          } catch (parseErr) {
            if (!(parseErr instanceof SyntaxError)) throw parseErr
          }
        }
      }
    } catch (e) {
      setChatHistory(prev => {
        const next = [...prev]
        next[next.length - 1] = { role: 'assistant', content: '⚠️ Error: ' + e.message }
        return next
      })
    } finally {
      setChatLoading(false)
      streamingChat.current = false
    }
  }

  async function handleNeighborhoodContext() {
    setNeighborhood(true)
    setNeighborhoodResult(null)
    setNeighborhoodError(null)
    try {
      const ctx = buildPropertyContext(form)
      const res = await aiNeighborhoodContext({
        city: ctx.city,
        state: ctx.state,
        property_type: ctx.property_type,
        address: ctx.address,
      })
      setNeighborhoodResult(res.data.neighborhood_context)
    } catch (e) {
      setNeighborhoodError(e.response?.data?.detail || e.message)
    } finally {
      setNeighborhood(false)
    }
  }

  async function handleFeedback(field, action, aiValue) {
    const key = `${field}_${action}`
    if (feedbackSent[key]) return
    setFeedbackSent(prev => ({ ...prev, [key]: true }))
    try {
      await aiSaveFeedback({ property_id: form.id, field, action, ai_value: aiValue })
    } catch (_) {}
  }

  async function handleLoadDescHistory() {
    if (descHistory !== null || descHistoryLoading) return
    setDescHistoryLoading(true)
    try {
      const res = await aiDescriptionHistory(form.id)
      setDescHistory(res.data.history || [])
    } catch (_) {
      setDescHistory([])
    } finally {
      setDescHistoryLoading(false)
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

  const emptyCount = getEmptyFillableFields(form).length
  const displayDraft = viewingDraft !== null ? draftHistory[viewingDraft]?.text : rewriteResult

  const AI_TABS = [
    {
      id: 'autofill', label: 'Fill',
      badge: emptyCount > 0 ? emptyCount : null,
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        </svg>
      ),
    },
    {
      id: 'rewrite', label: 'Rewrite',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
        </svg>
      ),
    },
    {
      id: 'clean', label: 'Clean',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
        </svg>
      ),
    },
    {
      id: 'title', label: 'Title',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z M6 6h.008v.008H6V6z" />
        </svg>
      ),
    },
    {
      id: 'neighborhood', label: 'Area',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
        </svg>
      ),
    },
    {
      id: 'issues', label: 'Issues',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      ),
    },
    {
      id: 'score', label: 'Score',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
        </svg>
      ),
    },
    {
      id: 'pricing', label: 'Price',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      id: 'seo', label: 'SEO',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
      ),
    },
    {
      id: 'chat', label: 'Chat',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
        </svg>
      ),
    },
  ]

  return (
    <div className="bg-white rounded-xl border border-purple-200 overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-purple-100">
        <span className="text-purple-600"><SparkleIcon /></span>
        <span className="text-sm font-semibold text-purple-900">AI Assistant</span>
        <span className="text-xs text-purple-400 ml-1">· DeepSeek</span>
      </div>

      <div className="grid grid-cols-5 border-b border-gray-100">
        {AI_TABS.map(({ id, label, icon, badge }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`relative flex flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-semibold transition-colors border-b-2 ${
              tab === id
                ? 'text-purple-700 bg-purple-50 border-purple-500'
                : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50 border-transparent'
            }`}
          >
            <span className={tab === id ? 'text-purple-600' : 'text-gray-400'}>{icon}</span>
            {label}
            {badge != null && (
              <span className="absolute top-1.5 right-1.5 min-w-[14px] h-3.5 px-0.5 bg-purple-600 text-white text-[9px] font-bold rounded-full flex items-center justify-center leading-none">
                {badge}
              </span>
            )}
          </button>
        ))}
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
                  {rewriting && <span className="inline-block w-1.5 h-4 ml-0.5 bg-purple-500 animate-pulse align-text-bottom" />}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => {
                      onApplyDescription(displayDraft)
                      handleFeedback('description', 'accept', displayDraft)
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
                  <div className="ml-auto flex items-center gap-1">
                    <span className="text-xs text-gray-400">Was this helpful?</span>
                    <button
                      title="Good result"
                      onClick={() => handleFeedback('description', 'accept', displayDraft)}
                      className={`p-1 rounded transition-colors ${feedbackSent['description_accept'] ? 'text-green-600' : 'text-gray-400 hover:text-green-600'}`}
                    >
                      👍
                    </button>
                    <button
                      title="Not helpful"
                      onClick={() => handleFeedback('description', 'reject', displayDraft)}
                      className={`p-1 rounded transition-colors ${feedbackSent['description_reject'] ? 'text-red-500' : 'text-gray-400 hover:text-red-500'}`}
                    >
                      👎
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Description History */}
            <div className="border-t border-gray-100 pt-3 mt-1">
              <button
                className="text-xs text-purple-600 hover:underline"
                onClick={() => {
                  setShowDescHistory(v => !v)
                  handleLoadDescHistory()
                }}
              >
                {showDescHistory ? 'Hide' : 'Show'} description history
              </button>
              {showDescHistory && (
                <div className="mt-2 space-y-2">
                  {descHistoryLoading && <p className="text-xs text-gray-400">Loading...</p>}
                  {!descHistoryLoading && descHistory !== null && descHistory.length === 0 && (
                    <p className="text-xs text-gray-400">No previous descriptions saved yet.</p>
                  )}
                  {!descHistoryLoading && descHistory && descHistory.map((entry, i) => (
                    <div key={entry.id || i} className="bg-gray-50 border border-gray-200 rounded p-2 space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs text-gray-400">
                          {entry.saved_at ? new Date(entry.saved_at).toLocaleString() : ''} · {entry.method}
                        </span>
                        <button
                          className="text-xs text-purple-600 hover:underline"
                          onClick={() => {
                            onApplyDescription(entry.description)
                          }}
                        >
                          Restore
                        </button>
                      </div>
                      <p className="text-xs text-gray-700 whitespace-pre-wrap line-clamp-3">{entry.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'neighborhood' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">
              Generate a short neighborhood context paragraph for this listing's location. Use it to enrich the description or give renters a sense of the area.
            </p>
            {(!form.city && !form.state) && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded">
                Add a city or state to this listing to generate neighborhood context.
              </p>
            )}
            <button
              onClick={handleNeighborhoodContext}
              disabled={neighborhood || (!form.city && !form.state)}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon spin={neighborhood} />
              {neighborhood ? 'Generating...' : 'Generate Neighborhood Context'}
            </button>
            {neighborhoodError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{neighborhoodError}</p>
            )}
            {neighborhoodResult && (
              <div className="space-y-2">
                <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                  {neighborhoodResult}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(neighborhoodResult)
                    }}
                    className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded hover:bg-gray-50 transition-colors"
                  >
                    Copy to Clipboard
                  </button>
                  <button
                    onClick={handleNeighborhoodContext}
                    disabled={neighborhood}
                    className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded hover:bg-gray-50 transition-colors"
                  >
                    Regenerate
                  </button>
                  <div className="ml-auto flex items-center gap-1">
                    <span className="text-xs text-gray-400">Helpful?</span>
                    <button
                      onClick={() => handleFeedback('neighborhood_context', 'accept', neighborhoodResult)}
                      className={`p-1 rounded transition-colors ${feedbackSent['neighborhood_context_accept'] ? 'text-green-600' : 'text-gray-400 hover:text-green-600'}`}
                    >
                      👍
                    </button>
                    <button
                      onClick={() => handleFeedback('neighborhood_context', 'reject', neighborhoodResult)}
                      className={`p-1 rounded transition-colors ${feedbackSent['neighborhood_context_reject'] ? 'text-red-500' : 'text-gray-400 hover:text-red-500'}`}
                    >
                      👎
                    </button>
                  </div>
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
                    <div key={i} className={`flex items-start gap-2 text-xs px-3 py-2.5 rounded-lg border ${SEVERITY_STYLES[issue.severity] || SEVERITY_STYLES.suggestion}`}>
                      <SeverityIcon severity={issue.severity} />
                      <span>
                        {issue.field && issue.field !== 'general' && <span className="font-semibold">{issue.field}: </span>}
                        {issue.message}
                      </span>
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
            <div className="h-64 sm:h-72 overflow-y-auto space-y-3 pr-1">
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

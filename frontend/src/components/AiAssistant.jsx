import { useState, useRef, useEffect } from 'react'
import { aiRewriteDescription, aiDetectIssues, aiChat } from '../api/client'

const SEVERITY_STYLES = {
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  suggestion: 'bg-blue-50 border-blue-200 text-blue-700',
}
const SEVERITY_ICON = { error: '✕', warning: '⚠', suggestion: '💡' }

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

function SparkleIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
    </svg>
  )
}

export default function AiAssistant({ form, onApplyDescription }) {
  const [tab, setTab] = useState('rewrite')
  const [tone, setTone] = useState('professional')
  const [rewriting, setRewriting] = useState(false)
  const [rewriteResult, setRewriteResult] = useState(null)
  const [rewriteError, setRewriteError] = useState(null)

  const [detecting, setDetecting] = useState(false)
  const [issues, setIssues] = useState(null)
  const [issuesError, setIssuesError] = useState(null)

  const [chatHistory, setChatHistory] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  async function handleRewrite() {
    setRewriting(true)
    setRewriteResult(null)
    setRewriteError(null)
    try {
      const res = await aiRewriteDescription({ property: buildPropertyContext(form), tone })
      setRewriteResult(res.data.description)
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

  async function handleChatSend() {
    const message = chatInput.trim()
    if (!message || chatLoading) return
    setChatInput('')
    const newHistory = [...chatHistory, { role: 'user', content: message }]
    setChatHistory(newHistory)
    setChatLoading(true)
    try {
      const res = await aiChat({
        property: buildPropertyContext(form),
        message,
        history: chatHistory,
      })
      setChatHistory([...newHistory, { role: 'assistant', content: res.data.reply }])
    } catch (e) {
      setChatHistory([...newHistory, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }])
    } finally {
      setChatLoading(false)
    }
  }

  const tabCls = (t) =>
    `px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
      tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
    }`

  return (
    <div className="bg-white rounded-lg border border-purple-200 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-purple-100">
        <span className="text-purple-600"><SparkleIcon /></span>
        <span className="text-sm font-semibold text-purple-900">AI Assistant</span>
        <span className="text-xs text-purple-400 ml-1">powered by Gemini</span>
      </div>

      <div className="p-1 border-b border-gray-100 bg-gray-50 flex gap-1">
        <button className={tabCls('rewrite')} onClick={() => setTab('rewrite')}>Rewrite Description</button>
        <button className={tabCls('issues')} onClick={() => setTab('issues')}>Detect Issues</button>
        <button className={tabCls('chat')} onClick={() => setTab('chat')}>Chat</button>
      </div>

      <div className="p-4">
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
              <SparkleIcon />
              {rewriting ? 'Writing...' : 'Generate Description'}
            </button>
            {rewriteError && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded border border-red-100">{rewriteError}</p>
            )}
            {rewriteResult && (
              <div className="space-y-2">
                <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                  {rewriteResult}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => { onApplyDescription(rewriteResult); setRewriteResult(null) }}
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

        {tab === 'issues' && (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">Scan the listing for missing info, inconsistencies, or quality issues before publishing.</p>
            <button
              onClick={handleDetectIssues}
              disabled={detecting}
              className="flex items-center gap-2 bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <SparkleIcon />
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

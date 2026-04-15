import { useState } from 'react'

function parseArray(value) {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value || '[]') : value
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export default function TagInput({ value, onChange, suggestions = [], placeholder = 'Type and press Enter to add...' }) {
  const [input, setInput] = useState('')
  const tags = parseArray(value)

  function addTag(tag) {
    const trimmed = tag.trim()
    if (!trimmed || tags.map(t => t.toLowerCase()).includes(trimmed.toLowerCase())) return
    onChange(JSON.stringify([...tags, trimmed]))
    setInput('')
  }

  function removeTag(tag) {
    onChange(JSON.stringify(tags.filter(t => t !== tag)))
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(input)
    }
    if (e.key === 'Backspace' && !input && tags.length > 0) {
      removeTag(tags[tags.length - 1])
    }
  }

  const unusedSuggestions = suggestions.filter(
    s => !tags.map(t => t.toLowerCase()).includes(s.toLowerCase())
  )

  return (
    <div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {tags.map(tag => (
            <span key={tag} className="flex items-center gap-1 bg-gray-100 text-gray-700 text-xs px-2.5 py-1 rounded-full">
              {tag}
              <button
                type="button"
                onClick={() => removeTag(tag)}
                className="text-gray-400 hover:text-red-500 transition-colors leading-none ml-0.5"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        type="text"
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => { if (input.trim()) addTag(input) }}
        placeholder={placeholder}
        className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
      />
      {unusedSuggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {unusedSuggestions.map(s => (
            <button
              key={s}
              type="button"
              onClick={() => addTag(s)}
              className="text-xs bg-gray-50 border border-gray-200 text-gray-500 hover:bg-gray-100 hover:text-gray-700 rounded-full px-2.5 py-0.5 transition-colors"
            >
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

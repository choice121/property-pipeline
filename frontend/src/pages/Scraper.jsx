import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { searchProperties, saveProperty } from '../api/client'
import SearchResultCard from '../components/SearchResultCard'
import PropertyPreviewModal from '../components/PropertyPreviewModal'

const PROPERTY_TYPES = [
  { value: 'single_family', label: 'Single Family' },
  { value: 'multi_family', label: 'Multi Family' },
  { value: 'condos', label: 'Condos' },
  { value: 'townhomes', label: 'Townhomes' },
  { value: 'duplex_triplex', label: 'Duplex / Triplex' },
  { value: 'condo_townhome', label: 'Condo / Townhome' },
  { value: 'mobile', label: 'Mobile Home' },
  { value: 'land', label: 'Land' },
  { value: 'farm', label: 'Farm' },
]

const LISTING_TYPES = [
  { value: 'for_rent', label: 'For Rent' },
  { value: 'for_sale', label: 'For Sale' },
  { value: 'sold', label: 'Sold' },
  { value: 'pending', label: 'Pending' },
  { value: 'off_market', label: 'Off Market' },
  { value: 'new_community', label: 'New Community' },
  { value: 'ready_to_build', label: 'Ready to Build' },
]

const SORT_FIELDS = [
  { value: '', label: 'Default' },
  { value: 'list_date', label: 'List Date' },
  { value: 'list_price', label: 'Price' },
  { value: 'sqft', label: 'Square Footage' },
  { value: 'beds', label: 'Bedrooms' },
  { value: 'baths', label: 'Bathrooms' },
  { value: 'last_update_date', label: 'Last Updated' },
  { value: 'sold_date', label: 'Sold Date' },
]

const TIME_MODE_OPTIONS = [
  { value: 'past_days', label: 'Past Days' },
  { value: 'past_hours', label: 'Past Hours' },
  { value: 'date_range', label: 'Date Range' },
]

const defaultForm = {
  location: '',
  listing_type: 'for_rent',
  property_types: [],
  min_price: '',
  max_price: '',
  beds_min: '',
  beds_max: '',
  baths_min: '',
  baths_max: '',
  sqft_min: '',
  sqft_max: '',
  lot_sqft_min: '',
  lot_sqft_max: '',
  year_built_min: '',
  year_built_max: '',
  time_mode: 'past_days',
  past_days: '',
  past_hours: '',
  date_from: '',
  date_to: '',
  radius: '',
  limit: '200',
  mls_only: false,
  foreclosure: false,
  exclude_pending: false,
  sort_by: '',
  sort_direction: 'desc',
}

function SectionLabel({ children }) {
  return <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 mt-1">{children}</p>
}

function FieldRow({ children, cols = 2 }) {
  return (
    <div className={`grid gap-3 ${cols === 3 ? 'grid-cols-3' : cols === 4 ? 'grid-cols-4' : 'grid-cols-2'}`}>
      {children}
    </div>
  )
}

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  )
}

function Input({ name, type = 'text', value, onChange, placeholder, min, step }) {
  return (
    <input
      name={name} type={type} value={value} onChange={onChange}
      placeholder={placeholder} min={min} step={step}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
    />
  )
}

function Select({ name, value, onChange, children }) {
  return (
    <select
      name={name} value={value} onChange={onChange}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white"
    >
      {children}
    </select>
  )
}

function Toggle({ name, checked, onChange, label, description }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer">
      <div className="relative mt-0.5 shrink-0">
        <input type="checkbox" name={name} checked={checked} onChange={onChange} className="sr-only" />
        <div className={`w-9 h-5 rounded-full transition-colors ${checked ? 'bg-gray-900' : 'bg-gray-300'}`} />
        <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-4' : ''}`} />
      </div>
      <div>
        <p className="text-sm font-medium text-gray-700">{label}</p>
        {description && <p className="text-xs text-gray-400">{description}</p>}
      </div>
    </label>
  )
}

export default function Scraper() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(defaultForm)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showForm, setShowForm] = useState(true)

  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState(null)
  const [searchResults, setSearchResults] = useState(null)

  const [selectedResult, setSelectedResult] = useState(null)
  const [savedIds, setSavedIds] = useState(new Set())
  const [savingIds, setSavingIds] = useState(new Set())

  function handleChange(e) {
    const { name, value, type, checked } = e.target
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }))
  }

  function togglePropertyType(val) {
    setForm((prev) => {
      const current = prev.property_types
      return {
        ...prev,
        property_types: current.includes(val) ? current.filter((v) => v !== val) : [...current, val],
      }
    })
  }

  function handleReset() {
    setForm(defaultForm)
    setSearchResults(null)
    setSearchError(null)
    setSavedIds(new Set())
    setSavingIds(new Set())
    setShowForm(true)
    setShowAdvanced(false)
  }

  function buildPayload() {
    const int = (v) => (v !== '' && v !== null ? parseInt(v) : null)
    const flt = (v) => (v !== '' && v !== null ? parseFloat(v) : null)
    const str = (v) => (v !== '' ? v : null)
    return {
      location: form.location,
      listing_type: form.listing_type || null,
      property_type: form.property_types.length > 0 ? form.property_types : null,
      min_price: int(form.min_price),
      max_price: int(form.max_price),
      beds_min: int(form.beds_min),
      beds_max: int(form.beds_max),
      baths_min: flt(form.baths_min),
      baths_max: flt(form.baths_max),
      sqft_min: int(form.sqft_min),
      sqft_max: int(form.sqft_max),
      lot_sqft_min: int(form.lot_sqft_min),
      lot_sqft_max: int(form.lot_sqft_max),
      year_built_min: int(form.year_built_min),
      year_built_max: int(form.year_built_max),
      past_days: form.time_mode === 'past_days' ? int(form.past_days) : null,
      past_hours: form.time_mode === 'past_hours' ? int(form.past_hours) : null,
      date_from: form.time_mode === 'date_range' ? str(form.date_from) : null,
      date_to: form.time_mode === 'date_range' ? str(form.date_to) : null,
      radius: flt(form.radius),
      limit: int(form.limit) || 200,
      mls_only: form.mls_only,
      foreclosure: form.foreclosure || null,
      exclude_pending: form.exclude_pending,
      sort_by: str(form.sort_by),
      sort_direction: form.sort_direction,
    }
  }

  async function handleSearch(e) {
    e.preventDefault()
    setSearchError(null)
    setSearchResults(null)
    setSavedIds(new Set())
    setSavingIds(new Set())
    setSearching(true)
    try {
      const res = await searchProperties(buildPayload())
      setSearchResults(res.data.results)
      setShowForm(false)
    } catch (err) {
      setSearchError(err.response?.data?.detail || err.message || 'Search failed.')
    } finally {
      setSearching(false)
    }
  }

  async function handleSave(result) {
    const key = result.temp_key
    if (savedIds.has(key) || savingIds.has(key)) return
    setSavingIds((prev) => new Set([...prev, key]))
    try {
      await saveProperty(result)
      setSavedIds((prev) => new Set([...prev, key]))
      queryClient.invalidateQueries({ queryKey: ['properties'] })
    } catch {
      alert('Could not save this property. Please try again.')
    } finally {
      setSavingIds((prev) => { const s = new Set(prev); s.delete(key); return s })
    }
  }

  async function handleSaveAll() {
    if (!searchResults) return
    const unsaved = searchResults.filter((r) => !savedIds.has(r.temp_key) && !savingIds.has(r.temp_key))
    await Promise.all(unsaved.map((r) => handleSave(r)))
  }

  const activeAdvancedCount = [
    form.sqft_min, form.sqft_max, form.lot_sqft_min, form.lot_sqft_max,
    form.year_built_min, form.year_built_max,
    form.time_mode === 'past_days' && form.past_days,
    form.time_mode === 'past_hours' && form.past_hours,
    form.time_mode === 'date_range' && (form.date_from || form.date_to),
    form.radius, form.mls_only, form.foreclosure, form.exclude_pending, form.sort_by,
  ].filter(Boolean).length

  const savedCount = savedIds.size
  const totalCount = searchResults?.length || 0

  return (
    <div className="max-w-5xl">

      {/* Page header */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Search Properties</h1>
        <p className="text-gray-500 text-sm">
          Search for listings, preview them in full, then choose which ones to save to your library.
        </p>
      </div>

      {/* Filter form */}
      {showForm ? (
        <form onSubmit={handleSearch} className="bg-white border border-gray-200 rounded-xl p-5 space-y-5 mb-6">
          <Field
            label="Location *"
            hint='City, state, zip code, or full address — e.g. "Austin, TX", "78701", "123 Main St, Dallas TX"'
          >
            <Input name="location" value={form.location} onChange={handleChange} placeholder='e.g. "Austin, TX" or "78701"' />
          </Field>

          <Field label="Listing Type">
            <Select name="listing_type" value={form.listing_type} onChange={handleChange}>
              {LISTING_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </Select>
          </Field>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Property Type <span className="text-gray-400 font-normal">(select any that apply, or leave blank for all)</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {PROPERTY_TYPES.map((pt) => {
                const active = form.property_types.includes(pt.value)
                return (
                  <button key={pt.value} type="button" onClick={() => togglePropertyType(pt.value)}
                    className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${active ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'}`}
                  >
                    {pt.label}
                  </button>
                )
              })}
            </div>
          </div>

          <div>
            <SectionLabel>Price</SectionLabel>
            <FieldRow>
              <Field label="Min Price"><Input name="min_price" type="number" value={form.min_price} onChange={handleChange} placeholder="No min" /></Field>
              <Field label="Max Price"><Input name="max_price" type="number" value={form.max_price} onChange={handleChange} placeholder="No max" /></Field>
            </FieldRow>
          </div>

          <div>
            <SectionLabel>Bedrooms &amp; Bathrooms</SectionLabel>
            <FieldRow cols={4}>
              <Field label="Min Beds"><Input name="beds_min" type="number" value={form.beds_min} onChange={handleChange} placeholder="Any" min="0" /></Field>
              <Field label="Max Beds"><Input name="beds_max" type="number" value={form.beds_max} onChange={handleChange} placeholder="Any" min="0" /></Field>
              <Field label="Min Baths"><Input name="baths_min" type="number" value={form.baths_min} onChange={handleChange} placeholder="Any" min="0" step="0.5" /></Field>
              <Field label="Max Baths"><Input name="baths_max" type="number" value={form.baths_max} onChange={handleChange} placeholder="Any" min="0" step="0.5" /></Field>
            </FieldRow>
          </div>

          <Field label="Result Limit" hint="Max number of listings to return. Type any number — e.g. 75, 300, 1000.">
            <Input name="limit" type="number" value={form.limit} onChange={handleChange} placeholder="e.g. 200" min="1" />
          </Field>

          {/* Advanced toggle */}
          <div className="border-t border-gray-200 pt-4">
            <button type="button" onClick={() => setShowAdvanced((v) => !v)}
              className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
            >
              <svg className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              Advanced Filters
              {activeAdvancedCount > 0 && (
                <span className="ml-1 bg-gray-900 text-white text-xs px-2 py-0.5 rounded-full">{activeAdvancedCount} active</span>
              )}
            </button>

            {showAdvanced && (
              <div className="mt-4 space-y-5">
                <div>
                  <SectionLabel>Square Footage</SectionLabel>
                  <FieldRow>
                    <Field label="Min Sqft"><Input name="sqft_min" type="number" value={form.sqft_min} onChange={handleChange} placeholder="No min" /></Field>
                    <Field label="Max Sqft"><Input name="sqft_max" type="number" value={form.sqft_max} onChange={handleChange} placeholder="No max" /></Field>
                  </FieldRow>
                </div>
                <div>
                  <SectionLabel>Lot Size (sqft)</SectionLabel>
                  <FieldRow>
                    <Field label="Min Lot Sqft"><Input name="lot_sqft_min" type="number" value={form.lot_sqft_min} onChange={handleChange} placeholder="No min" /></Field>
                    <Field label="Max Lot Sqft"><Input name="lot_sqft_max" type="number" value={form.lot_sqft_max} onChange={handleChange} placeholder="No max" /></Field>
                  </FieldRow>
                </div>
                <div>
                  <SectionLabel>Year Built</SectionLabel>
                  <FieldRow>
                    <Field label="Built After"><Input name="year_built_min" type="number" value={form.year_built_min} onChange={handleChange} placeholder="e.g. 1990" /></Field>
                    <Field label="Built Before"><Input name="year_built_max" type="number" value={form.year_built_max} onChange={handleChange} placeholder="e.g. 2024" /></Field>
                  </FieldRow>
                </div>
                <div>
                  <SectionLabel>Listing Date / Time Filter</SectionLabel>
                  <div className="flex gap-2 mb-3">
                    {TIME_MODE_OPTIONS.map((opt) => (
                      <button key={opt.value} type="button"
                        onClick={() => setForm((prev) => ({ ...prev, time_mode: opt.value }))}
                        className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${form.time_mode === opt.value ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'}`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                  {form.time_mode === 'past_days' && (
                    <Field label="Listed in the last N days" hint="Leave blank for no time restriction">
                      <Input name="past_days" type="number" value={form.past_days} onChange={handleChange} placeholder="e.g. 30" min="1" />
                    </Field>
                  )}
                  {form.time_mode === 'past_hours' && (
                    <Field label="Listed in the last N hours" hint="Great for catching fresh listings quickly">
                      <Input name="past_hours" type="number" value={form.past_hours} onChange={handleChange} placeholder="e.g. 6" min="1" />
                    </Field>
                  )}
                  {form.time_mode === 'date_range' && (
                    <FieldRow>
                      <Field label="From Date"><Input name="date_from" type="date" value={form.date_from} onChange={handleChange} /></Field>
                      <Field label="To Date"><Input name="date_to" type="date" value={form.date_to} onChange={handleChange} /></Field>
                    </FieldRow>
                  )}
                </div>
                <Field label="Radius (miles)" hint="Only works when location is a specific address, not a city or zip">
                  <Input name="radius" type="number" value={form.radius} onChange={handleChange} placeholder="e.g. 2.5" min="0" step="0.5" />
                </Field>
                <div>
                  <SectionLabel>Sort Results</SectionLabel>
                  <FieldRow>
                    <Field label="Sort By">
                      <Select name="sort_by" value={form.sort_by} onChange={handleChange}>
                        {SORT_FIELDS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </Select>
                    </Field>
                    <Field label="Direction">
                      <Select name="sort_direction" value={form.sort_direction} onChange={handleChange}>
                        <option value="desc">Descending</option>
                        <option value="asc">Ascending</option>
                      </Select>
                    </Field>
                  </FieldRow>
                </div>
                <div>
                  <SectionLabel>Listing Flags</SectionLabel>
                  <div className="space-y-3">
                    <Toggle name="mls_only" checked={form.mls_only} onChange={handleChange} label="MLS Listings Only" description="Only pull listings with a verified MLS ID" />
                    <Toggle name="foreclosure" checked={form.foreclosure} onChange={handleChange} label="Foreclosures Only" description="Only pull foreclosure listings" />
                    <Toggle name="exclude_pending" checked={form.exclude_pending} onChange={handleChange} label="Exclude Pending / Contingent" description="Skip properties already under contract" />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-3 pt-1">
            <button type="submit" disabled={searching || !form.location.trim()}
              className="flex-1 bg-gray-900 text-white py-2.5 rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
            >
              {searching ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Searching…
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <circle cx="11" cy="11" r="8" /><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35" />
                  </svg>
                  Search Properties
                </>
              )}
            </button>
            <button type="button" onClick={handleReset}
              className="px-4 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Reset
            </button>
          </div>

          {searchError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {searchError}
            </div>
          )}
        </form>
      ) : (
        /* Compact search bar when results are showing */
        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 mb-5 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-gray-800">
              {form.location}
              <span className="text-gray-400 font-normal ml-2">
                · {LISTING_TYPES.find(t => t.value === form.listing_type)?.label || form.listing_type}
                {form.beds_min ? ` · ${form.beds_min}+ beds` : ''}
                {form.min_price ? ` · $${Number(form.min_price).toLocaleString()}+` : ''}
                {form.max_price ? ` · up to $${Number(form.max_price).toLocaleString()}` : ''}
              </span>
            </p>
          </div>
          <button onClick={() => setShowForm(true)}
            className="text-sm text-blue-600 hover:underline shrink-0 ml-4"
          >
            Modify Search
          </button>
        </div>
      )}

      {/* Results section */}
      {searchResults !== null && (
        <div>
          {/* Results header */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">
                {totalCount === 0 ? 'No results found' : `${totalCount} ${totalCount === 1 ? 'property' : 'properties'} found`}
              </h2>
              {savedCount > 0 && (
                <p className="text-sm text-green-600 mt-0.5">
                  {savedCount} saved to your library
                </p>
              )}
            </div>
            {totalCount > 0 && (
              <div className="flex gap-2">
                <button onClick={handleSaveAll}
                  disabled={savedCount === totalCount}
                  className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-40 transition-colors"
                >
                  {savedCount === totalCount ? '✓ All Saved' : `Save All (${totalCount - savedCount})`}
                </button>
                <button onClick={handleReset}
                  className="px-4 py-2 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  New Search
                </button>
              </div>
            )}
          </div>

          {totalCount === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <p className="text-lg">No properties matched your filters.</p>
              <p className="text-sm mt-1">Try widening your search or adjusting the filters.</p>
              <button onClick={() => setShowForm(true)} className="mt-4 text-sm text-blue-600 hover:underline">
                Modify Search
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {searchResults.map((result) => (
                <SearchResultCard
                  key={result.temp_key}
                  result={result}
                  isSaved={savedIds.has(result.temp_key)}
                  isSaving={savingIds.has(result.temp_key)}
                  onSave={() => handleSave(result)}
                  onPreview={() => setSelectedResult(result)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Preview modal */}
      {selectedResult && (
        <PropertyPreviewModal
          result={selectedResult}
          isSaved={savedIds.has(selectedResult.temp_key)}
          isSaving={savingIds.has(selectedResult.temp_key)}
          onSave={() => handleSave(selectedResult)}
          onClose={() => setSelectedResult(null)}
        />
      )}
    </div>
  )
}

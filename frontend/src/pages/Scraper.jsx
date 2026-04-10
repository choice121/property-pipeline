import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { scrapeProperties } from '../api/client'

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
  return (
    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 mt-1">
      {children}
    </p>
  )
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
      name={name}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      min={min}
      step={step}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
    />
  )
}

function Select({ name, value, onChange, children }) {
  return (
    <select
      name={name}
      value={value}
      onChange={onChange}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white"
    >
      {children}
    </select>
  )
}

function Toggle({ name, checked, onChange, label, description }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <div className="relative mt-0.5 shrink-0">
        <input
          type="checkbox"
          name={name}
          checked={checked}
          onChange={onChange}
          className="sr-only"
        />
        <div
          className={`w-9 h-5 rounded-full transition-colors ${checked ? 'bg-gray-900' : 'bg-gray-300'}`}
        />
        <div
          className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-4' : ''}`}
        />
      </div>
      <div>
        <p className="text-sm font-medium text-gray-700">{label}</p>
        {description && <p className="text-xs text-gray-400">{description}</p>}
      </div>
    </label>
  )
}

export default function Scraper() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [form, setForm] = useState(defaultForm)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [result, setResult] = useState(null)

  const mutation = useMutation({
    mutationFn: (data) => scrapeProperties(data).then((r) => r.data),
    onSuccess: (data) => {
      setResult(data)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
    },
  })

  function handleChange(e) {
    const { name, value, type, checked } = e.target
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }))
  }

  function togglePropertyType(val) {
    setForm((prev) => {
      const current = prev.property_types
      return {
        ...prev,
        property_types: current.includes(val)
          ? current.filter((v) => v !== val)
          : [...current, val],
      }
    })
  }

  function handleReset() {
    setForm(defaultForm)
    setResult(null)
    setShowAdvanced(false)
  }

  function handleSubmit(e) {
    e.preventDefault()
    setResult(null)

    const int = (v) => (v !== '' && v !== null ? parseInt(v) : null)
    const flt = (v) => (v !== '' && v !== null ? parseFloat(v) : null)
    const str = (v) => (v !== '' ? v : null)

    const payload = {
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

    mutation.mutate(payload)
  }

  const activeAdvancedCount = [
    form.sqft_min, form.sqft_max,
    form.lot_sqft_min, form.lot_sqft_max,
    form.year_built_min, form.year_built_max,
    form.time_mode === 'past_days' && form.past_days,
    form.time_mode === 'past_hours' && form.past_hours,
    form.time_mode === 'date_range' && (form.date_from || form.date_to),
    form.radius,
    form.mls_only,
    form.foreclosure,
    form.exclude_pending,
    form.sort_by,
  ].filter(Boolean).length

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Scrape Listings</h1>
        <p className="text-gray-500 text-sm">
          Pull property listings and add them to your library.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">

        {/* Location */}
        <Field
          label="Location *"
          hint='City, state, zip code, or full address — e.g. "Austin, TX", "78701", "123 Main St, Dallas TX"'
        >
          <Input
            name="location"
            value={form.location}
            onChange={handleChange}
            placeholder='e.g. "Austin, TX" or "78701"'
          />
        </Field>

        {/* Listing Type */}
        <Field label="Listing Type">
          <Select name="listing_type" value={form.listing_type} onChange={handleChange}>
            {LISTING_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </Select>
        </Field>

        {/* Property Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Property Type <span className="text-gray-400 font-normal">(select any that apply, or leave blank for all)</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {PROPERTY_TYPES.map((pt) => {
              const active = form.property_types.includes(pt.value)
              return (
                <button
                  key={pt.value}
                  type="button"
                  onClick={() => togglePropertyType(pt.value)}
                  className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                    active
                      ? 'bg-gray-900 text-white border-gray-900'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
                  }`}
                >
                  {pt.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Price */}
        <div>
          <SectionLabel>Price</SectionLabel>
          <FieldRow>
            <Field label="Min Price">
              <Input name="min_price" type="number" value={form.min_price} onChange={handleChange} placeholder="No min" />
            </Field>
            <Field label="Max Price">
              <Input name="max_price" type="number" value={form.max_price} onChange={handleChange} placeholder="No max" />
            </Field>
          </FieldRow>
        </div>

        {/* Beds & Baths */}
        <div>
          <SectionLabel>Bedrooms &amp; Bathrooms</SectionLabel>
          <FieldRow cols={4}>
            <Field label="Min Beds">
              <Input name="beds_min" type="number" value={form.beds_min} onChange={handleChange} placeholder="Any" min="0" />
            </Field>
            <Field label="Max Beds">
              <Input name="beds_max" type="number" value={form.beds_max} onChange={handleChange} placeholder="Any" min="0" />
            </Field>
            <Field label="Min Baths">
              <Input name="baths_min" type="number" value={form.baths_min} onChange={handleChange} placeholder="Any" min="0" step="0.5" />
            </Field>
            <Field label="Max Baths">
              <Input name="baths_max" type="number" value={form.baths_max} onChange={handleChange} placeholder="Any" min="0" step="0.5" />
            </Field>
          </FieldRow>
        </div>

        {/* Result Limit */}
        <Field
          label="Result Limit"
          hint="Max results to pull. Use a lower number to keep your library focused. Maximum is 10,000."
        >
          <Select name="limit" value={form.limit} onChange={handleChange}>
            <option value="25">25 results</option>
            <option value="50">50 results</option>
            <option value="100">100 results</option>
            <option value="200">200 results</option>
            <option value="500">500 results</option>
            <option value="1000">1,000 results</option>
            <option value="5000">5,000 results</option>
            <option value="10000">10,000 results (max)</option>
          </Select>
        </Field>

        {/* Advanced Toggle */}
        <div className="border-t border-gray-200 pt-4">
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
          >
            <svg
              className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
              fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            Advanced Filters
            {activeAdvancedCount > 0 && (
              <span className="ml-1 bg-gray-900 text-white text-xs px-2 py-0.5 rounded-full">
                {activeAdvancedCount} active
              </span>
            )}
          </button>

          {showAdvanced && (
            <div className="mt-4 space-y-5">

              {/* Square Footage */}
              <div>
                <SectionLabel>Square Footage</SectionLabel>
                <FieldRow>
                  <Field label="Min Sqft">
                    <Input name="sqft_min" type="number" value={form.sqft_min} onChange={handleChange} placeholder="No min" />
                  </Field>
                  <Field label="Max Sqft">
                    <Input name="sqft_max" type="number" value={form.sqft_max} onChange={handleChange} placeholder="No max" />
                  </Field>
                </FieldRow>
              </div>

              {/* Lot Size */}
              <div>
                <SectionLabel>Lot Size (sqft)</SectionLabel>
                <FieldRow>
                  <Field label="Min Lot Sqft">
                    <Input name="lot_sqft_min" type="number" value={form.lot_sqft_min} onChange={handleChange} placeholder="No min" />
                  </Field>
                  <Field label="Max Lot Sqft">
                    <Input name="lot_sqft_max" type="number" value={form.lot_sqft_max} onChange={handleChange} placeholder="No max" />
                  </Field>
                </FieldRow>
              </div>

              {/* Year Built */}
              <div>
                <SectionLabel>Year Built</SectionLabel>
                <FieldRow>
                  <Field label="Built After">
                    <Input name="year_built_min" type="number" value={form.year_built_min} onChange={handleChange} placeholder="e.g. 1990" />
                  </Field>
                  <Field label="Built Before">
                    <Input name="year_built_max" type="number" value={form.year_built_max} onChange={handleChange} placeholder="e.g. 2024" />
                  </Field>
                </FieldRow>
              </div>

              {/* Time Filter */}
              <div>
                <SectionLabel>Listing Date / Time Filter</SectionLabel>
                <div className="flex gap-2 mb-3">
                  {TIME_MODE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setForm((prev) => ({ ...prev, time_mode: opt.value }))}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                        form.time_mode === opt.value
                          ? 'bg-gray-900 text-white border-gray-900'
                          : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
                      }`}
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
                    <Field label="From Date">
                      <Input name="date_from" type="date" value={form.date_from} onChange={handleChange} />
                    </Field>
                    <Field label="To Date">
                      <Input name="date_to" type="date" value={form.date_to} onChange={handleChange} />
                    </Field>
                  </FieldRow>
                )}
              </div>

              {/* Radius */}
              <Field
                label="Radius (miles)"
                hint="Only works when location is a specific address, not a city or zip"
              >
                <Input name="radius" type="number" value={form.radius} onChange={handleChange} placeholder="e.g. 2.5" min="0" step="0.5" />
              </Field>

              {/* Sort */}
              <div>
                <SectionLabel>Sort Results</SectionLabel>
                <FieldRow>
                  <Field label="Sort By">
                    <Select name="sort_by" value={form.sort_by} onChange={handleChange}>
                      {SORT_FIELDS.map((s) => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
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

              {/* Toggles */}
              <div>
                <SectionLabel>Listing Flags</SectionLabel>
                <div className="space-y-3">
                  <Toggle
                    name="mls_only"
                    checked={form.mls_only}
                    onChange={handleChange}
                    label="MLS Listings Only"
                    description="Only pull listings that have a verified MLS ID — filters out noise and duplicates"
                  />
                  <Toggle
                    name="foreclosure"
                    checked={form.foreclosure}
                    onChange={handleChange}
                    label="Foreclosures Only"
                    description="Only pull foreclosure listings"
                  />
                  <Toggle
                    name="exclude_pending"
                    checked={form.exclude_pending}
                    onChange={handleChange}
                    label="Exclude Pending / Contingent"
                    description="Skip properties that are already under contract"
                  />
                </div>
              </div>

            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <button
            type="submit"
            disabled={mutation.isPending || !form.location.trim()}
            className="flex-1 bg-gray-900 text-white py-2.5 rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {mutation.isPending ? 'Scraping… this may take a minute' : 'Start Scrape'}
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="px-4 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Reset
          </button>
        </div>
      </form>

      {mutation.isError && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {mutation.error?.response?.data?.detail || mutation.error?.message || 'An unknown error occurred.'}
        </div>
      )}

      {result && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-800 font-medium text-sm">
            Done — {result.count} {result.count === 1 ? 'property' : 'properties'} added to your library.
          </p>
          <p className="text-green-700 text-sm mt-1">
            Images are downloading in the background.
          </p>
          <button
            onClick={() => navigate('/')}
            className="mt-3 text-sm text-green-800 underline hover:no-underline"
          >
            Go to Library →
          </button>
        </div>
      )}
    </div>
  )
}

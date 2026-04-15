import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createProperty } from '../api/client'

const inputCls = 'w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400'
const selectCls = 'w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white'

const PROPERTY_TYPES = [
  '', 'house', 'apartment', 'condo', 'townhouse', 'duplex', 'studio',
  'multi_family', 'mobile', 'land', 'commercial',
]

function Field({ label, required, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}

const EMPTY = {
  title: '',
  property_type: '',
  address: '',
  city: '',
  state: '',
  zip: '',
  county: '',
  bedrooms: '',
  bathrooms: '',
  half_bathrooms: '',
  square_footage: '',
  year_built: '',
  monthly_rent: '',
  security_deposit: '',
  available_date: '',
  minimum_lease_months: '',
  parking: '',
  pets_allowed: false,
  smoking_allowed: false,
  has_basement: false,
  has_central_air: false,
  description: '',
  showing_instructions: '',
}

export default function CreateListing() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ ...EMPTY })
  const [errors, setErrors] = useState({})

  const createMutation = useMutation({
    mutationFn: (data) => createProperty(data).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      navigate(`/edit/${data.id}`)
    },
  })

  function set(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }))
    if (errors[key]) setErrors((prev) => { const e = { ...prev }; delete e[key]; return e })
  }

  function validate() {
    const e = {}
    if (!form.address.trim()) e.address = 'Address is required'
    if (!form.city.trim()) e.city = 'City is required'
    if (!form.monthly_rent) e.monthly_rent = 'Monthly rent is required'
    return e
  }

  function handleSubmit(e) {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }

    const payload = {}
    for (const [k, v] of Object.entries(form)) {
      if (v === '' || v === null || v === undefined) continue
      payload[k] = v
    }
    createMutation.mutate(payload)
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/" className="text-sm text-gray-500 hover:text-gray-700">← Back to Library</Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">Create Listing</h1>
          <p className="text-sm text-gray-500 mt-0.5">Add a property from scratch — no scraping needed.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Basic Info</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Field label="Listing Title">
                <input
                  className={inputCls}
                  placeholder="e.g. Bright 2BR in Downtown Austin"
                  value={form.title}
                  onChange={(e) => set('title', e.target.value)}
                />
              </Field>
            </div>
            <Field label="Property Type">
              <select className={selectCls} value={form.property_type} onChange={(e) => set('property_type', e.target.value)}>
                {PROPERTY_TYPES.map(t => (
                  <option key={t} value={t}>{t ? t.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) : '— Select type —'}</option>
                ))}
              </select>
            </Field>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Location</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Field label="Street Address" required>
                <input
                  className={`${inputCls} ${errors.address ? 'border-red-400' : ''}`}
                  placeholder="123 Main St"
                  value={form.address}
                  onChange={(e) => set('address', e.target.value)}
                />
                {errors.address && <p className="text-xs text-red-500 mt-0.5">{errors.address}</p>}
              </Field>
            </div>
            <Field label="City" required>
              <input
                className={`${inputCls} ${errors.city ? 'border-red-400' : ''}`}
                placeholder="Austin"
                value={form.city}
                onChange={(e) => set('city', e.target.value)}
              />
              {errors.city && <p className="text-xs text-red-500 mt-0.5">{errors.city}</p>}
            </Field>
            <Field label="State">
              <input className={inputCls} placeholder="TX" value={form.state} onChange={(e) => set('state', e.target.value)} />
            </Field>
            <Field label="ZIP Code">
              <input className={inputCls} placeholder="78701" value={form.zip} onChange={(e) => set('zip', e.target.value)} />
            </Field>
            <Field label="County">
              <input className={inputCls} placeholder="Travis" value={form.county} onChange={(e) => set('county', e.target.value)} />
            </Field>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Property Details</h2>
          <div className="grid grid-cols-3 gap-4">
            <Field label="Bedrooms">
              <input type="number" min="0" className={inputCls} value={form.bedrooms} onChange={(e) => set('bedrooms', e.target.value)} />
            </Field>
            <Field label="Bathrooms">
              <input type="number" min="0" step="0.5" className={inputCls} value={form.bathrooms} onChange={(e) => set('bathrooms', e.target.value)} />
            </Field>
            <Field label="Half Baths">
              <input type="number" min="0" className={inputCls} value={form.half_bathrooms} onChange={(e) => set('half_bathrooms', e.target.value)} />
            </Field>
            <Field label="Square Footage">
              <input type="number" min="0" className={inputCls} value={form.square_footage} onChange={(e) => set('square_footage', e.target.value)} />
            </Field>
            <Field label="Year Built">
              <input type="number" min="1800" max="2030" className={inputCls} value={form.year_built} onChange={(e) => set('year_built', e.target.value)} />
            </Field>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Pricing</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Monthly Rent ($)" required>
              <input
                type="number"
                min="0"
                className={`${inputCls} ${errors.monthly_rent ? 'border-red-400' : ''}`}
                placeholder="1500"
                value={form.monthly_rent}
                onChange={(e) => set('monthly_rent', e.target.value)}
              />
              {errors.monthly_rent && <p className="text-xs text-red-500 mt-0.5">{errors.monthly_rent}</p>}
            </Field>
            <Field label="Security Deposit ($)">
              <input type="number" min="0" className={inputCls} value={form.security_deposit} onChange={(e) => set('security_deposit', e.target.value)} />
            </Field>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Availability & Policies</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Available Date">
              <input type="date" className={inputCls} value={form.available_date} onChange={(e) => set('available_date', e.target.value)} />
            </Field>
            <Field label="Minimum Lease (months)">
              <input type="number" min="1" className={inputCls} value={form.minimum_lease_months} onChange={(e) => set('minimum_lease_months', e.target.value)} />
            </Field>
            <Field label="Parking">
              <input className={inputCls} placeholder="e.g. 1-car garage" value={form.parking} onChange={(e) => set('parking', e.target.value)} />
            </Field>
            <Field label="Showing Instructions">
              <input className={inputCls} placeholder="e.g. Call to schedule" value={form.showing_instructions} onChange={(e) => set('showing_instructions', e.target.value)} />
            </Field>
            <div className="col-span-2 grid grid-cols-2 gap-2 mt-1">
              {[
                ['pets_allowed', 'Pets Allowed'],
                ['smoking_allowed', 'Smoking Allowed'],
                ['has_basement', 'Basement'],
                ['has_central_air', 'Central Air'],
              ].map(([key, label]) => (
                <label key={key} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={!!form[key]} onChange={(e) => set(key, e.target.checked)} className="rounded" />
                  <span className="text-sm text-gray-700">{label}</span>
                </label>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Description</h2>
          <Field label="Property Description">
            <textarea
              className={`${inputCls} h-32 resize-y`}
              placeholder="Describe the property — highlights, neighborhood, unique features…"
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
            />
          </Field>
        </section>

        <div className="flex items-center gap-3 pb-8">
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-gray-900 text-white px-6 py-2 rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {createMutation.isPending ? 'Creating…' : 'Create Listing'}
          </button>
          <Link to="/" className="text-sm text-gray-500 hover:text-gray-700">Cancel</Link>
          {createMutation.isError && (
            <p className="text-sm text-red-600">
              {createMutation.error?.response?.data?.detail || 'Failed to create listing. Please try again.'}
            </p>
          )}
        </div>
      </form>
    </div>
  )
}

import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProperty, updateProperty, deleteProperty, deleteImage, reorderImages, downloadProperty } from '../api/client'
import ImageGallery from '../components/ImageGallery'
import StatusBadge from '../components/StatusBadge'
import PublishButton from '../components/PublishButton'
import AiAssistant from '../components/AiAssistant'

const FIELD_LABELS = {
  title: 'Title', property_type: 'Property Type', status: 'Status',
  address: 'Address', city: 'City', state: 'State', zip: 'Zip', county: 'County',
  bedrooms: 'Bedrooms', bathrooms: 'Bathrooms', half_bathrooms: 'Half Baths',
  total_bathrooms: 'Total Bathrooms', square_footage: 'Square Footage', lot_size_sqft: 'Lot Size (sqft)', year_built: 'Year Built',
  floors: 'Floors', unit_number: 'Unit Number', total_units: 'Total Units',
  monthly_rent: 'Monthly Rent', security_deposit: 'Security Deposit', last_months_rent: "Last Month's Rent",
  application_fee: 'Application Fee', pet_deposit: 'Pet Deposit', admin_fee: 'Admin / Move-in Fee', parking_fee: 'Parking Fee',
  parking: 'Parking', garage_spaces: 'Garage Spaces',
  pets_allowed: 'Pets Allowed', pet_details: 'Pet Details',
  smoking_allowed: 'Smoking Allowed', description: 'Description',
  virtual_tour_url: 'Virtual Tour URL', amenities: 'Amenities',
  available_date: 'Available Date', lease_terms: 'Lease Terms',
  minimum_lease_months: 'Minimum Lease Months', pet_types_allowed: 'Pet Types Allowed',
  pet_weight_limit: 'Pet Weight Limit', utilities_included: 'Utilities Included',
  appliances: 'Appliances', flooring: 'Flooring', heating_type: 'Heating Type',
  cooling_type: 'Cooling Type', laundry_type: 'Laundry Type',
  has_basement: 'Basement', has_central_air: 'Central Air',
  showing_instructions: 'Showing Instructions', move_in_special: 'Move-in Special',
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  )
}

const inputCls = 'w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400'

function arrayToInput(value) {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value || '[]') : value
    return Array.isArray(parsed) ? parsed.join(', ') : (value || '')
  } catch {
    return value || ''
  }
}

function inputToArrayJson(value) {
  return JSON.stringify(value.split(',').map((s) => s.trim()).filter(Boolean))
}

function parseArray(value) {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value || '[]') : value
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export default function Editor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [showOriginal, setShowOriginal] = useState(false)
  const [form, setForm] = useState(null)
  const [saved, setSaved] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const isDirty = useRef(false)

  const { data: property, isLoading } = useQuery({
    queryKey: ['property', id],
    queryFn: () => getProperty(id).then((r) => r.data),
  })

  useEffect(() => {
    if (property && !form) {
      setForm({ ...property })
      isDirty.current = false
    }
  }, [property])

  useEffect(() => {
    function handleBeforeUnload(e) {
      if (isDirty.current) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

  const saveMutation = useMutation({
    mutationFn: (data) => updateProperty(id, data).then((r) => r.data),
    onSuccess: (data) => {
      setForm(data)
      isDirty.current = false
      setSaved(true)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      queryClient.setQueryData(['property', id], data)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteProperty(id).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      navigate('/')
    },
  })

  const deleteImgMutation = useMutation({
    mutationFn: (index) => deleteImage(id, index).then((r) => r.data),
    onSuccess: (data) => {
      setForm(data)
      queryClient.setQueryData(['property', id], data)
    },
  })

  const reorderMutation = useMutation({
    mutationFn: (order) => reorderImages(id, order).then((r) => r.data),
    onSuccess: (data) => {
      setForm(data)
      queryClient.setQueryData(['property', id], data)
    },
  })

  if (isLoading || !form) {
    return <div className="text-gray-400 py-16 text-center">Loading property...</div>
  }

  function set(key, value) {
    isDirty.current = true
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function handleBackToLibrary() {
    if (isDirty.current && !window.confirm('You have unsaved changes. Leave without saving?')) {
      return
    }
    navigate('/')
  }

  function handleSave() {
    saveMutation.mutate(form)
  }

  function handleMarkReady() {
    saveMutation.mutate({ ...form, status: 'ready' })
  }

  function handleDelete() {
    if (window.confirm('Delete this property? This cannot be undone.')) {
      deleteMutation.mutate()
    }
  }

  async function handleDownload() {
    setDownloading(true)
    try {
      const res = await downloadProperty(id)
      const disposition = res.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : `${id}.zip`
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      alert('Download failed. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  const originalData = (() => {
    try { return JSON.parse(property.original_data || '{}') } catch { return {} }
  })()

  const editedFields = (() => {
    try { return JSON.parse(form.edited_fields || '[]') } catch { return [] }
  })()

  const images = (() => {
    try { return JSON.parse(form.local_image_paths || '[]') } catch { return [] }
  })()

  const missingFields = parseArray(form.missing_fields)
  const inferredFeatures = parseArray(form.inferred_features)

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-4">
        <button onClick={handleBackToLibrary} className="text-sm text-gray-500 hover:text-gray-700">← Back to Library</button>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowOriginal(!showOriginal)}
            className={`text-xs px-3 py-1.5 rounded border ${showOriginal ? 'bg-gray-900 text-white border-gray-900' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
          >
            {showOriginal ? 'Hide Original' : 'Compare with Original'}
          </button>
          <StatusBadge status={form.status} />
        </div>
      </div>

      {editedFields.length > 0 && (
        <div className="mb-4 text-xs text-blue-600 bg-blue-50 px-3 py-2 rounded">
          {editedFields.length} field{editedFields.length !== 1 ? 's' : ''} edited from original
        </div>
      )}

      {(form.data_quality_score != null || missingFields.length > 0 || inferredFeatures.length > 0) && (
        <section className="mb-4 bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Listing Completeness</h2>
              <p className="text-xs text-gray-500 mt-1">Use this to decide what should be reviewed before publishing.</p>
            </div>
            {form.data_quality_score != null && (
              <div className="text-right">
                <p className="text-2xl font-bold text-gray-900">{form.data_quality_score}%</p>
                <p className="text-xs text-gray-500">complete</p>
              </div>
            )}
          </div>
          {missingFields.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-medium text-amber-700 mb-2">Missing or unknown</p>
              <div className="flex flex-wrap gap-2">
                {missingFields.map((field) => (
                  <span key={field} className="text-xs bg-amber-50 text-amber-700 border border-amber-200 rounded-full px-2.5 py-1">{FIELD_LABELS[field] || field}</span>
                ))}
              </div>
            </div>
          )}
          {inferredFeatures.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-medium text-blue-700 mb-2">Inferred from scraped text</p>
              <div className="flex flex-wrap gap-2">
                {inferredFeatures.map((field) => (
                  <span key={field} className="text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-full px-2.5 py-1">{field}</span>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      <div className="space-y-6">
        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Basic Info</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Title">
              <input className={inputCls} value={form.title || ''} onChange={(e) => set('title', e.target.value)} />
              {showOriginal && <p className="text-xs text-gray-400 mt-0.5">Original: {originalData.title || '—'}</p>}
            </Field>
            <Field label="Property Type">
              <input className={inputCls} value={form.property_type || ''} onChange={(e) => set('property_type', e.target.value)} />
            </Field>
            <Field label="Status">
              {form.status === 'published' || form.choice_property_id ? (
                <div className={inputCls + ' bg-gray-50 text-green-700 font-medium'}>Published</div>
              ) : (
                <select className={inputCls} value={form.status || 'scraped'} onChange={(e) => set('status', e.target.value)}>
                  <option value="scraped">Scraped</option>
                  <option value="edited">Edited</option>
                  <option value="ready">Ready to Publish</option>
                </select>
              )}
            </Field>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Location</h2>
          <div className="grid grid-cols-2 gap-4">
            {['address', 'city', 'state', 'zip', 'county'].map((key) => (
              <Field key={key} label={FIELD_LABELS[key] || key}>
                <input className={inputCls} value={form[key] || ''} onChange={(e) => set(key, e.target.value)} />
                {showOriginal && <p className="text-xs text-gray-400 mt-0.5">Original: {originalData[key] || '—'}</p>}
              </Field>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Details</h2>
          <div className="grid grid-cols-3 gap-4">
            {['bedrooms', 'bathrooms', 'half_bathrooms', 'total_bathrooms', 'square_footage', 'lot_size_sqft', 'year_built', 'floors', 'unit_number', 'total_units'].map((key) => (
              <Field key={key} label={FIELD_LABELS[key] || key}>
                <input type={key === 'unit_number' ? 'text' : 'number'} className={inputCls} value={form[key] ?? ''} onChange={(e) => set(key, e.target.value)} />
                {showOriginal && <p className="text-xs text-gray-400 mt-0.5">Original: {originalData[key] ?? '—'}</p>}
              </Field>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Pricing</h2>
          <div className="grid grid-cols-2 gap-4">
            {['monthly_rent', 'security_deposit', 'last_months_rent', 'application_fee', 'admin_fee', 'pet_deposit', 'parking_fee'].map((key) => (
              <Field key={key} label={FIELD_LABELS[key] || key}>
                <input type="number" className={inputCls} value={form[key] ?? ''} onChange={(e) => set(key, e.target.value)} />
              </Field>
            ))}
            <Field label="Move-in Special">
              <input className={inputCls} value={form.move_in_special || ''} onChange={(e) => set('move_in_special', e.target.value)} />
            </Field>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Availability & Lease</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Available Date">
              <input type="date" className={inputCls} value={(form.available_date || '').slice(0, 10)} onChange={(e) => set('available_date', e.target.value)} />
            </Field>
            <Field label="Minimum Lease Months">
              <input type="number" className={inputCls} value={form.minimum_lease_months ?? ''} onChange={(e) => set('minimum_lease_months', e.target.value)} />
            </Field>
            <Field label="Lease Terms (comma-separated)">
              <input className={inputCls} value={arrayToInput(form.lease_terms)} onChange={(e) => set('lease_terms', inputToArrayJson(e.target.value))} />
            </Field>
            <Field label="Showing Instructions">
              <input className={inputCls} value={form.showing_instructions || ''} onChange={(e) => set('showing_instructions', e.target.value)} />
            </Field>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Policies</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Parking">
              <input className={inputCls} value={form.parking || ''} onChange={(e) => set('parking', e.target.value)} />
            </Field>
            <Field label="Garage Spaces">
              <input type="number" className={inputCls} value={form.garage_spaces ?? ''} onChange={(e) => set('garage_spaces', e.target.value)} />
            </Field>
            <Field label="Pet Details">
              <input className={inputCls} value={form.pet_details || ''} onChange={(e) => set('pet_details', e.target.value)} />
            </Field>
            <Field label="Pet Types Allowed (comma-separated)">
              <input className={inputCls} value={arrayToInput(form.pet_types_allowed)} onChange={(e) => set('pet_types_allowed', inputToArrayJson(e.target.value))} />
            </Field>
            <Field label="Pet Weight Limit">
              <input type="number" className={inputCls} value={form.pet_weight_limit ?? ''} onChange={(e) => set('pet_weight_limit', e.target.value)} />
            </Field>
            <div className="flex items-center gap-2 mt-1">
              <input type="checkbox" id="pets" checked={!!form.pets_allowed} onChange={(e) => set('pets_allowed', e.target.checked)} />
              <label htmlFor="pets" className="text-sm text-gray-700">Pets Allowed</label>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <input type="checkbox" id="smoking" checked={!!form.smoking_allowed} onChange={(e) => set('smoking_allowed', e.target.checked)} />
              <label htmlFor="smoking" className="text-sm text-gray-700">Smoking Allowed</label>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <input type="checkbox" id="basement" checked={!!form.has_basement} onChange={(e) => set('has_basement', e.target.checked)} />
              <label htmlFor="basement" className="text-sm text-gray-700">Basement</label>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <input type="checkbox" id="central-air" checked={!!form.has_central_air} onChange={(e) => set('has_central_air', e.target.checked)} />
              <label htmlFor="central-air" className="text-sm text-gray-700">Central Air</label>
            </div>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Description</h2>
          <Field label="Description">
            <textarea
              className={inputCls + ' h-32 resize-y'}
              value={form.description || ''}
              onChange={(e) => set('description', e.target.value)}
            />
            {showOriginal && <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">Original: {originalData.description || '—'}</p>}
          </Field>
          <div className="mt-3">
            <Field label="Virtual Tour URL">
              <input className={inputCls} value={form.virtual_tour_url || ''} onChange={(e) => set('virtual_tour_url', e.target.value)} />
            </Field>
          </div>
        </section>

        <AiAssistant
          form={form}
          onApplyDescription={(desc) => set('description', desc)}
        />

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Features</h2>
          <div className="grid grid-cols-2 gap-4">
            {['heating_type', 'cooling_type', 'laundry_type'].map((key) => (
              <Field key={key} label={FIELD_LABELS[key] || key}>
                <input className={inputCls} value={form[key] || ''} onChange={(e) => set(key, e.target.value)} />
              </Field>
            ))}
            {['amenities', 'appliances', 'utilities_included', 'flooring'].map((key) => (
              <Field key={key} label={`${FIELD_LABELS[key] || key} (comma-separated)`}>
                <input className={inputCls} value={arrayToInput(form[key])} onChange={(e) => set(key, inputToArrayJson(e.target.value))} />
              </Field>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Photos</h2>
          <ImageGallery
            propertyId={id}
            images={images}
            onDelete={(index) => deleteImgMutation.mutate(index)}
            onReorder={(order) => reorderMutation.mutate(order)}
          />
        </section>
      </div>

      <div className="mt-6 flex flex-wrap gap-3 items-start">
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="bg-gray-900 text-white px-5 py-2 rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
        >
          {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
        </button>
        {form.status !== 'published' && !form.choice_property_id && (
          <button
            onClick={handleMarkReady}
            disabled={saveMutation.isPending}
            className="bg-amber-500 text-white px-5 py-2 rounded-lg font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors"
          >
            Mark as Ready
          </button>
        )}
        <PublishButton
          property={form}
          onPublished={(data) => {
            queryClient.invalidateQueries({ queryKey: ['property', id] })
          }}
        />
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
          </svg>
          {downloading ? 'Preparing ZIP...' : 'Download ZIP'}
        </button>
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="bg-red-500 text-white px-5 py-2 rounded-lg font-medium hover:bg-red-600 disabled:opacity-50 transition-colors"
        >
          Delete Property
        </button>
      </div>

      {saved && (
        <div className="mt-3 text-sm text-green-600 bg-green-50 px-3 py-2 rounded">
          Saved successfully.
        </div>
      )}
      {saveMutation.isError && (
        <div className="mt-3 text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
          Save failed: {saveMutation.error?.response?.data?.detail || saveMutation.error?.message}
        </div>
      )}
    </div>
  )
}

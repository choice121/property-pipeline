import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProperty, updateProperty, deleteProperty, deleteImage, reorderImages, downloadProperty, aiDetectIssues } from '../api/client'
import ImageGallery from '../components/ImageGallery'
import LiveImageGallery from '../components/LiveImageGallery'
import StatusBadge from '../components/StatusBadge'
import PublishButton from '../components/PublishButton'
import AiAssistant from '../components/AiAssistant'
import TagInput from '../components/TagInput'
import ListingPreview from '../components/ListingPreview'
import ConfirmModal from '../components/ConfirmModal'
import BottomSheet from '../components/BottomSheet'
import { computeCompleteness, completenessColor } from '../utils/completeness'

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

const PROPERTY_TYPES = [
  '', 'house', 'apartment', 'condo', 'townhouse', 'duplex', 'studio',
  'multi_family', 'mobile', 'land', 'commercial',
]

const HEATING_OPTIONS = ['', 'Gas', 'Electric', 'Heat Pump', 'Radiant', 'Baseboard', 'Forced Air', 'Other']
const COOLING_OPTIONS = ['', 'Central Air', 'Window Units', 'Mini-Split', 'None', 'Other']
const LAUNDRY_OPTIONS = ['', 'In Unit', 'In Building', 'Hookups', 'Shared', 'None']

const AMENITY_SUGGESTIONS = [
  'Pool', 'Gym', 'Parking', 'Storage', 'Balcony', 'Patio', 'Yard', 'Garage',
  'Elevator', 'Doorman', 'Rooftop', 'Bike Storage', 'EV Charging', 'Concierge',
]
const APPLIANCE_SUGGESTIONS = [
  'Dishwasher', 'Refrigerator', 'Microwave', 'Oven', 'Stove', 'Washer', 'Dryer',
  'Garbage Disposal', 'Ice Maker', 'Wine Fridge',
]
const UTILITIES_SUGGESTIONS = [
  'Water', 'Trash', 'Gas', 'Electric', 'Internet', 'Cable', 'Sewer', 'Heat',
]
const FLOORING_SUGGESTIONS = [
  'Hardwood', 'Carpet', 'Tile', 'Laminate', 'Vinyl', 'Concrete', 'Bamboo',
]

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  )
}

const inputCls = 'w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400'
const selectCls = 'w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white'

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

const isPublished = (form) =>
  form.status === 'published' || form.status === 'rented' || form.status === 'archived' || !!form.choice_property_id

export default function Editor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [showOriginal, setShowOriginal] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [showAiSheet, setShowAiSheet] = useState(false)
  const [form, setForm] = useState(null)
  const [saved, setSaved] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [savedAfterPublish, setSavedAfterPublish] = useState(false)
  const [postSaveIssues, setPostSaveIssues] = useState(null)
  const [postSaveQualityScore, setPostSaveQualityScore] = useState(null)
  const [confirmModal, setConfirmModal] = useState(null)
  const isDirty = useRef(false)

  const openConfirm = (opts) => setConfirmModal(opts)
  const closeConfirm = () => setConfirmModal(null)

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
      const wasPublished = isPublished(form)
      setForm(data)
      isDirty.current = false
      setSaved(true)
      setPostSaveIssues(null)
      setPostSaveQualityScore(null)
      if (wasPublished) setSavedAfterPublish(true)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      queryClient.setQueryData(['property', id], data)
      setTimeout(() => setSaved(false), 3000)

      const tryParseArray = (v) => { try { return JSON.parse(v || '[]').join(', ') } catch { return v || '' } }
      const ctx = {
        address: data.address, city: data.city, state: data.state,
        bedrooms: data.bedrooms != null ? Number(data.bedrooms) : null,
        bathrooms: data.bathrooms != null ? Number(data.bathrooms) : null,
        square_footage: data.square_footage ? Number(data.square_footage) : null,
        monthly_rent: data.monthly_rent ? Number(data.monthly_rent) : null,
        property_type: data.property_type,
        amenities: tryParseArray(data.amenities),
        appliances: tryParseArray(data.appliances),
        pets_allowed: data.pets_allowed ?? null,
        parking: data.parking, heating_type: data.heating_type, cooling_type: data.cooling_type,
        laundry_type: data.laundry_type, utilities_included: tryParseArray(data.utilities_included),
        description: data.description, lease_terms: tryParseArray(data.lease_terms),
        flooring: tryParseArray(data.flooring),
        has_basement: data.has_basement ?? null, has_central_air: data.has_central_air ?? null,
      }
      aiDetectIssues({ property: ctx }).then(res => {
        const body = res.data
        const issueList = Array.isArray(body) ? body : (body.issues || [])
        const qs = body.quality_score ?? null
        setPostSaveIssues(issueList)
        setPostSaveQualityScore(qs)
      }).catch(() => {})
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
    if (isDirty.current) {
      openConfirm({
        title: 'Leave without saving?',
        message: 'You have unsaved changes that will be lost.',
        confirmLabel: 'Leave',
        cancelLabel: 'Stay',
        danger: false,
        onConfirm: () => navigate('/'),
      })
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
    openConfirm({
      title: 'Delete this property?',
      message: 'All local images and data for this listing will be permanently removed. This cannot be undone.',
      confirmLabel: 'Delete',
      danger: true,
      onConfirm: () => deleteMutation.mutate(),
    })
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

  const pricingAdjusted = !!(originalData._pricing_adjusted)
  const originalRent = originalData._original_rent
  const rentDiscountRate = originalData._rent_discount_rate
  const originalFee = originalData.application_fee

  const editedFields = (() => {
    try { return JSON.parse(form.edited_fields || '[]') } catch { return [] }
  })()

  const images = (() => {
    try { return JSON.parse(form.local_image_paths || '[]') } catch { return [] }
  })()

  const missingFields = parseArray(form.missing_fields)
  const inferredFeatures = parseArray(form.inferred_features)
  const published = isPublished(form)
  const isLive = !!(form.choice_property_id)

  return (
    <div className="max-w-3xl pb-28 sm:pb-0">

      {/* ── Sticky mobile save bar — always visible on mobile while scrolling ── */}
      <div
        className="sm:hidden fixed bottom-0 left-0 right-0 z-50 bg-white/95 border-t border-gray-200 px-4 py-3 flex items-center gap-3 backdrop-blur-sm"
        style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 0px), 12px)' }}
      >
        <button
          onClick={handleBackToLibrary}
          className="flex items-center gap-1 text-sm text-gray-500 touch-target px-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
        <div className="flex-1" />
        {saved && (
          <span className="text-xs text-green-600 font-medium">Saved ✓</span>
        )}
        <StatusBadge status={form.status} />
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="bg-gray-900 text-white px-5 py-2 rounded-lg text-sm font-semibold disabled:opacity-50 transition-colors"
        >
          {saveMutation.isPending ? 'Saving…' : isLive ? 'Save & Sync' : 'Save'}
        </button>
      </div>

      {/* ── Desktop header ── */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <button onClick={handleBackToLibrary} className="hidden sm:block text-sm text-gray-500 hover:text-gray-700 touch-target">← Back to Library</button>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setShowPreview(true)}
            className="text-xs px-3 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 flex items-center gap-1.5 touch-target"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            Preview
          </button>
          <button
            onClick={() => setShowOriginal(!showOriginal)}
            className={`text-xs px-3 py-1.5 rounded border touch-target ${showOriginal ? 'bg-gray-900 text-white border-gray-900' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
          >
            {showOriginal ? 'Hide Original' : 'Original'}
          </button>
          {isLive && (
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">
              LIVE
            </span>
          )}
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
              <select
                className={selectCls}
                value={form.property_type || ''}
                onChange={(e) => set('property_type', e.target.value)}
              >
                {PROPERTY_TYPES.map(t => (
                  <option key={t} value={t}>{t ? t.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) : '— Select type —'}</option>
                ))}
              </select>
            </Field>
            <Field label="Status">
              {published ? (
                <div className={inputCls + ' bg-gray-50 text-green-700 font-medium capitalize'}>{form.status}</div>
              ) : (
                <select className={selectCls} value={form.status || 'draft'} onChange={(e) => set('status', e.target.value)}>
                  <option value="draft">Draft</option>
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

            {/* Monthly Rent — with scraped vs platform comparison */}
            <div className="col-span-2">
              <Field label="Monthly Rent">
                <input
                  type="number"
                  className={inputCls}
                  value={form.monthly_rent ?? ''}
                  onChange={(e) => set('monthly_rent', e.target.value)}
                />
              </Field>
              {pricingAdjusted && originalRent != null && (
                <div className="mt-2 flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 text-xs text-amber-800">
                  <svg className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-amber-500" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 110 20A10 10 0 0112 2z" />
                  </svg>
                  <span>
                    <strong>Platform price applied.</strong>{' '}
                    Scraped listing: <span className="line-through">${Number(originalRent).toLocaleString()}/mo</span>
                    {' '}→ {rentDiscountRate != null ? `${Math.round(rentDiscountRate * 100)}% discount` : 'reduced'} to{' '}
                    <strong>${Number(form.monthly_rent).toLocaleString()}/mo</strong>
                  </span>
                </div>
              )}
            </div>

            {/* Application Fee — with platform floor note */}
            <div>
              <Field label="Application Fee">
                <input
                  type="number"
                  className={inputCls}
                  value={form.application_fee ?? ''}
                  onChange={(e) => set('application_fee', e.target.value)}
                />
              </Field>
              {Number(form.application_fee) === 50 && (originalFee == null || Number(originalFee) < 50) && (
                <p className="mt-1 text-xs text-blue-600 flex items-center gap-1">
                  <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Platform minimum applied
                  {originalFee != null && ` (scraped: $${Number(originalFee).toLocaleString()})`}
                  {originalFee == null && ' (none on original listing)'}
                </p>
              )}
            </div>

            {/* Remaining pricing fields */}
            {['security_deposit', 'last_months_rent', 'admin_fee', 'pet_deposit', 'parking_fee'].map((key) => (
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

        {/* Desktop: inline AI Assistant */}
        <div className="hidden sm:block">
          <AiAssistant
            form={form}
            propertyId={id}
            onApplyDescription={(desc) => set('description', desc)}
            onApplyFields={(fields) => {
              isDirty.current = true
              setForm((prev) => ({ ...prev, ...fields }))
            }}
          />
        </div>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Features</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Heating Type">
              <select className={selectCls} value={form.heating_type || ''} onChange={(e) => set('heating_type', e.target.value)}>
                {HEATING_OPTIONS.map(o => <option key={o} value={o}>{o || '— Select —'}</option>)}
              </select>
            </Field>
            <Field label="Cooling Type">
              <select className={selectCls} value={form.cooling_type || ''} onChange={(e) => set('cooling_type', e.target.value)}>
                {COOLING_OPTIONS.map(o => <option key={o} value={o}>{o || '— Select —'}</option>)}
              </select>
            </Field>
            <Field label="Laundry">
              <select className={selectCls} value={form.laundry_type || ''} onChange={(e) => set('laundry_type', e.target.value)}>
                {LAUNDRY_OPTIONS.map(o => <option key={o} value={o}>{o || '— Select —'}</option>)}
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 mt-4">
            <Field label="Amenities">
              <TagInput
                value={form.amenities}
                onChange={(v) => set('amenities', v)}
                suggestions={AMENITY_SUGGESTIONS}
                placeholder="Type an amenity and press Enter…"
              />
            </Field>
            <Field label="Appliances">
              <TagInput
                value={form.appliances}
                onChange={(v) => set('appliances', v)}
                suggestions={APPLIANCE_SUGGESTIONS}
                placeholder="Type an appliance and press Enter…"
              />
            </Field>
            <Field label="Utilities Included">
              <TagInput
                value={form.utilities_included}
                onChange={(v) => set('utilities_included', v)}
                suggestions={UTILITIES_SUGGESTIONS}
                placeholder="Type a utility and press Enter…"
              />
            </Field>
            <Field label="Flooring">
              <TagInput
                value={form.flooring}
                onChange={(v) => set('flooring', v)}
                suggestions={FLOORING_SUGGESTIONS}
                placeholder="Type a flooring type and press Enter…"
              />
            </Field>
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Photos</h2>
          {isLive ? (
            <LiveImageGallery propertyId={id} />
          ) : (
            <ImageGallery
              propertyId={id}
              images={images}
              onDelete={(index) => deleteImgMutation.mutate(index)}
              onReorder={(order) => reorderMutation.mutate(order)}
            />
          )}
        </section>
      </div>

      <div className="mt-6 flex flex-wrap gap-3 items-start">
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="bg-gray-900 text-white px-5 py-2 rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
        >
          {saveMutation.isPending ? 'Saving...' : isLive ? 'Save & Sync' : 'Save Changes'}
        </button>
        {!published && !isLive && (
          <button
            onClick={handleMarkReady}
            disabled={saveMutation.isPending}
            className="bg-amber-500 text-white px-5 py-2 rounded-lg font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors"
          >
            Mark as Ready
          </button>
        )}
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
          Delete
        </button>
      </div>

      {/* Publish Readiness Bar (Phase 5A) */}
      {(() => {
        const { score, missing } = computeCompleteness(form)
        const { bar, text } = completenessColor(score)
        return (
          <div className="mt-6 space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-gray-600">Publish Readiness</span>
              <span style={{ color: text }} className="font-semibold">{score}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              <div
                className="h-2 rounded-full transition-all duration-500"
                style={{ width: `${score}%`, backgroundColor: bar }}
              />
            </div>
            {missing.length > 0 && (
              <p className="text-xs text-gray-400">
                Missing: {missing.join(', ')}
              </p>
            )}
          </div>
        )
      })()}

      <div className="mt-4">
        <PublishButton
          property={form}
          savedAfterPublish={savedAfterPublish}
          onSynced={() => setSavedAfterPublish(false)}
          onPublished={(data) => {
            setSavedAfterPublish(false)
            queryClient.invalidateQueries({ queryKey: ['property', id] })
          }}
        />
      </div>

      {saved && (
        <div className="mt-3 text-sm text-green-600 bg-green-50 px-3 py-2 rounded">
          {isLive ? 'Saved & synced to live site.' : `Saved successfully.${published ? ' Use "Sync Fields" to push changes to the live site.' : ''}`}
        </div>
      )}

      {postSaveIssues !== null && (
        <div className={`mt-3 px-3 py-2 rounded border text-sm ${postSaveIssues.filter(i => i.severity === 'error').length > 0 ? 'bg-red-50 border-red-200 text-red-800' : postSaveIssues.filter(i => i.severity === 'warning').length > 0 ? 'bg-amber-50 border-amber-200 text-amber-800' : 'bg-green-50 border-green-200 text-green-700'}`}>
          <div className="flex items-center justify-between">
            <span className="font-medium">
              {postSaveIssues.length === 0
                ? 'Quality check: looks good!'
                : `Quality check: ${postSaveIssues.filter(i => i.severity === 'error').length} error${postSaveIssues.filter(i => i.severity === 'error').length !== 1 ? 's' : ''}, ${postSaveIssues.filter(i => i.severity === 'warning').length} warning${postSaveIssues.filter(i => i.severity === 'warning').length !== 1 ? 's' : ''}${postSaveQualityScore != null ? ` · Score ${postSaveQualityScore}/100` : ''}`}
            </span>
            <button onClick={() => setPostSaveIssues(null)} className="ml-3 opacity-50 hover:opacity-100 text-lg leading-none">&times;</button>
          </div>
          {postSaveIssues.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {postSaveIssues.slice(0, 4).map((issue, i) => (
                <li key={i} className="text-xs opacity-90 flex items-start gap-1">
                  <span className="mt-px">
                    {issue.severity === 'error' ? '✗' : issue.severity === 'warning' ? '!' : '→'}
                  </span>
                  <span>
                    {issue.field && issue.field !== 'general' ? <strong>{issue.field}: </strong> : null}{issue.message}
                  </span>
                </li>
              ))}
              {postSaveIssues.length > 4 && <li className="text-xs opacity-60">+{postSaveIssues.length - 4} more — check the Issues tab in AI Assistant</li>}
            </ul>
          )}
        </div>
      )}

      {saveMutation.isError && (
        <div className="mt-3 text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
          Save failed: {saveMutation.error?.response?.data?.detail || saveMutation.error?.message}
        </div>
      )}

      {showPreview && (
        <ListingPreview property={form} onClose={() => setShowPreview(false)} />
      )}

      {/* Mobile AI floating action button */}
      <button
        type="button"
        onClick={() => setShowAiSheet(true)}
        className="sm:hidden fixed right-4 z-40 w-14 h-14 rounded-full bg-gradient-to-br from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-500/40 flex items-center justify-center active:scale-95 transition-transform"
        style={{ bottom: 'calc(env(safe-area-inset-bottom, 0px) + 80px)' }}
        aria-label="Open AI Assistant"
      >
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        </svg>
      </button>

      {/* Mobile AI Assistant bottom sheet */}
      <BottomSheet open={showAiSheet} onClose={() => setShowAiSheet(false)} title="AI Assistant" maxHeightVh={88}>
        <div className="p-2">
          <AiAssistant
            form={form}
            propertyId={id}
            onApplyDescription={(desc) => { set('description', desc); setShowAiSheet(false) }}
            onApplyFields={(fields) => {
              isDirty.current = true
              setForm((prev) => ({ ...prev, ...fields }))
              setShowAiSheet(false)
            }}
          />
        </div>
      </BottomSheet>

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

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { scrapeProperties } from '../api/client'

export default function Scraper() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [form, setForm] = useState({
    location: '',
    source: 'realtor',
    listing_type: 'for_rent',
    min_price: '',
    max_price: '',
    bedrooms: '',
  })

  const [result, setResult] = useState(null)

  const mutation = useMutation({
    mutationFn: (data) => scrapeProperties(data).then((r) => r.data),
    onSuccess: (data) => {
      setResult(data)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
    },
  })

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  function handleSubmit(e) {
    e.preventDefault()
    setResult(null)
    const payload = {
      location: form.location,
      listing_type: form.listing_type,
      min_price: form.min_price ? parseInt(form.min_price) : null,
      max_price: form.max_price ? parseInt(form.max_price) : null,
      bedrooms: form.bedrooms ? parseInt(form.bedrooms) : null,
    }
    mutation.mutate(payload)
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Scrape Listings</h1>
      <p className="text-gray-500 text-sm mb-6">
        Pull property listings and add them to your library.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Location *</label>
          <input
            name="location"
            value={form.location}
            onChange={handleChange}
            placeholder='e.g. "Austin, TX" or "78701"'
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
            <select
              name="source"
              value={form.source}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
            >
              <option value="realtor">Realtor.com</option>
              <option value="zillow" disabled>Zillow (unavailable)</option>
              <option value="redfin" disabled>Redfin (unavailable)</option>
            </select>
            <p className="text-xs text-gray-400 mt-1">Only Realtor.com is supported by the current scraping library</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Listing Type</label>
            <select
              name="listing_type"
              value={form.listing_type}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
            >
              <option value="for_rent">For Rent</option>
              <option value="for_sale">For Sale</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Min Price</label>
            <input
              name="min_price"
              type="number"
              value={form.min_price}
              onChange={handleChange}
              placeholder="$"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Price</label>
            <input
              name="max_price"
              type="number"
              value={form.max_price}
              onChange={handleChange}
              placeholder="$"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Bedrooms</label>
            <input
              name="bedrooms"
              type="number"
              value={form.bedrooms}
              onChange={handleChange}
              placeholder="Any"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full bg-gray-900 text-white py-2.5 rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? 'Scraping... (this may take a minute)' : 'Start Scrape'}
        </button>
      </form>

      {mutation.isError && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          Error: {mutation.error?.response?.data?.detail || mutation.error?.message || 'Unknown error'}
        </div>
      )}

      {result && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-800 font-medium">
            Done! Found {result.count} {result.count === 1 ? 'property' : 'properties'}.
          </p>
          <p className="text-green-700 text-sm mt-1">
            Images are downloading in the background. Check your Library in a moment.
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

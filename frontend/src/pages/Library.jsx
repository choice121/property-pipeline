import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, Link } from 'react-router-dom'
import { getProperties } from '../api/client'
import PropertyCard from '../components/PropertyCard'

export default function Library() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState('scraped_at')

  const { data, isLoading } = useQuery({
    queryKey: ['properties'],
    queryFn: () => getProperties().then((r) => r.data),
    refetchInterval: 5000,
  })

  const filtered = useMemo(() => {
    if (!data) return []
    let list = [...data]

    if (statusFilter) {
      list = list.filter((p) => p.status === statusFilter)
    }

    if (search.trim()) {
      const term = search.toLowerCase()
      list = list.filter(
        (p) =>
          (p.address || '').toLowerCase().includes(term) ||
          (p.city || '').toLowerCase().includes(term)
      )
    }

    if (sort === 'scraped_at') {
      list.sort((a, b) => new Date(b.scraped_at) - new Date(a.scraped_at))
    } else if (sort === 'price_asc') {
      list.sort((a, b) => (a.monthly_rent || 0) - (b.monthly_rent || 0))
    } else if (sort === 'price_desc') {
      list.sort((a, b) => (b.monthly_rent || 0) - (a.monthly_rent || 0))
    } else if (sort === 'bedrooms') {
      list.sort((a, b) => (b.bedrooms || 0) - (a.bedrooms || 0))
    }

    return list
  }, [data, search, statusFilter, sort])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Property Library
          <span className="ml-2 text-base font-normal text-gray-500">
            ({filtered.length} {filtered.length === 1 ? 'property' : 'properties'})
          </span>
        </h1>
        <Link
          to="/scraper"
          className="bg-gray-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-700 transition-colors"
        >
          + Scrape More
        </Link>
      </div>

      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="text"
          placeholder="Search by address or city..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1 min-w-48 focus:outline-none focus:ring-2 focus:ring-gray-400"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          <option value="">All Statuses</option>
          <option value="scraped">Scraped</option>
          <option value="edited">Edited</option>
          <option value="ready">Ready</option>
          <option value="published">Published</option>
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          <option value="scraped_at">Newest First</option>
          <option value="price_asc">Price: Low to High</option>
          <option value="price_desc">Price: High to Low</option>
          <option value="bedrooms">Most Bedrooms</option>
        </select>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-gray-200 rounded-lg h-64 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">No properties found.</p>
          <p className="text-sm mt-2">
            Try adjusting your filters or{' '}
            <Link to="/scraper" className="text-gray-700 underline">
              scrape new listings
            </Link>
            .
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((property) => (
            <PropertyCard
              key={property.id}
              property={property}
              onClick={() => navigate(`/edit/${property.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

const STATUS_STYLES = {
  scraped:  'bg-gray-200 text-gray-700',
  edited:   'bg-blue-100 text-blue-700',
  ready:    'bg-amber-100 text-amber-700',
  published:'bg-green-100 text-green-700',
  rented:   'bg-purple-100 text-purple-700',
  archived: 'bg-gray-100 text-gray-500',
}

const STATUS_LABELS = {
  scraped:  'Scraped',
  edited:   'Edited',
  ready:    'Ready',
  published:'Published',
  rented:   'Rented',
  archived: 'Archived',
}

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || 'bg-gray-100 text-gray-500'
  const label = STATUS_LABELS[status] || status
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {label}
    </span>
  )
}

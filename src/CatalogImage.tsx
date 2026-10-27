import { useState } from 'react'
import { Coffee } from 'lucide-react'
import { publicApiUrl } from './api'

export default function CatalogImage({ src, alt, className = '' }: { src?: string; alt: string; className?: string }) {
  const [failed, setFailed] = useState('')
  const url = src?.startsWith('/api/images/') ? publicApiUrl(src) : src
  return url && failed !== url
    ? <img src={url} alt={alt} loading="lazy" onError={() => setFailed(url)} className={className} />
    : <span role="img" aria-label={alt} className={`inline-grid place-items-center bg-stone-100 text-stone-500 ${className}`}><Coffee className="size-8" /></span>
}

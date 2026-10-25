import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { WEB_VERSION } from './version'

type VersionInfo = { webVersion: string }
export default function UpdateNotice({ pendingCount }: { pendingCount: number }) {
  const [available, setAvailable] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const check = async () => {
      try {
        const response = await fetch('/version.json', { cache: 'no-store' })
        if (!response.ok) return
        const data = await response.json() as VersionInfo
        if (active && typeof data.webVersion === 'string' && data.webVersion !== WEB_VERSION) setAvailable(true)
      } catch { /* Offline is expected in cafés. */ }
    }
    void check()
    const onFocus = () => void check()
    window.addEventListener('focus', onFocus)
    return () => { active = false; window.removeEventListener('focus', onFocus) }
  }, [])
  if (!available) return null
  const update = async () => {
    if (pendingCount > 0) { setError('Serverga yuborilmagan buyurtmalar bor. Avval sinxronlashni tugating.'); return }
    if (!window.confirm('Yangi versiyani yuklash uchun oynani qayta ochamiz. Faol buyurtma yoki to‘lov oynasi yo‘qligini tekshiring.')) return
    try {
      const reg = await navigator.serviceWorker?.getRegistration()
      await reg?.update()
    } catch { /* Continue with fresh navigation. */ }
    window.location.reload()
  }
  return <div className="flex flex-wrap items-center justify-center gap-2 bg-amber-100 px-3 py-2 text-sm text-stone-900" role="status">
    <strong>CoffeePOS yangilanishi mavjud</strong>
    <button onClick={() => void update()} className="inline-flex items-center gap-1 rounded-lg bg-stone-900 px-3 py-1.5 font-bold text-white"><RefreshCw className="size-4"/>Yangilash</button>
    {error && <span className="text-red-700">{error}</span>}
  </div>
}

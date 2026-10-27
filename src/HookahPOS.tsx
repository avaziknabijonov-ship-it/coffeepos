import { useEffect, useState } from 'react'
import { api } from './api'
import { t } from './i18n'
import Kassa from './Kassa'
import Admin from './Admin'

export default function HookahPOS({ onShift, admin = false }: { onShift: () => void; admin?: boolean }) {
  const [started, setStarted] = useState(false)
  const [allowed, setAllowed] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const check = () => api('/api/modules/hookah').then(() => { if (active) { setAllowed(true); setStarted(true); setError('') } }).catch(e => { if (active) { setAllowed(false); setError((e as Error).message) } })
    void check()
    const timer = window.setInterval(() => void check(), 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  return <>{!allowed && <div className="p-6" role={error ? 'alert' : undefined}>{error || t('Yuklanmoqda…')}</div>}{started && <div hidden={!allowed} className="h-full">{admin ? <Admin hookah /> : <Kassa hookah onShift={onShift} />}</div>}</>
}

import { useState } from 'react'
import { api, publicApiUrl } from './api'
import { getLang, t } from './i18n'

export default function ReceiptLink({ orderId }: { orderId: string }) {
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const create = async () => {
    setBusy(true); setError(''); setLink(''); setNotice('')
    try {
      const result = await api<{ path: string }>('/api/orders/' + orderId + '/receipt-link', { method: 'POST' })
      setLink(publicApiUrl(result.path) + '?lang=' + getLang())
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  const revoke = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      await api('/api/orders/' + orderId + '/receipt-links', { method: 'DELETE' })
      setLink(''); setNotice(t('Chekning barcha faol havolalari bekor qilindi'))
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="mt-3 space-y-2 rounded-lg border p-3">
    <button disabled={busy} onClick={() => void create()} className="rounded-lg border px-3 py-2 disabled:opacity-50">{t('Elektron chek havolasi')}</button>
    <p className="text-xs text-stone-600">{t('Havola 15 daqiqa amal qiladi. Havolasi bor shaxs chekni ochishi mumkin. Fiskal chek emas.')}</p>
    <button disabled={busy} onClick={() => void revoke()} className="rounded-lg border px-3 py-2 disabled:opacity-50">{t('Chekning barcha havolalarini bekor qilish')}</button>
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {link && <div><a className="break-all text-blue-700 underline" href={link} target="_blank" rel="noopener noreferrer">{t('Elektron chekni ochish')}</a><input aria-label={t('Elektron chek havolasi')} className="mt-2 block w-full rounded border p-2 text-xs" readOnly value={link} onFocus={e => e.target.select()} /></div>}
  </div>
}

import { useEffect, useState } from 'react'
import { api, ApiError } from './api'
import { t } from './i18n'
import { fmt, PAYMENT_LABEL, type Order } from './data'

type Refund = { id: number; amount: number; method: string; reason: string; staff: string; createdAt: number }
type Payload = { clientKey: string; amount: number; method: string; reason: string; externalConfirmed: boolean }

export default function RefundPanel({ order }: { order: Order }) {
  const [rows, setRows] = useState<Refund[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const parts = order.paymentParts ?? (order.payment === 'split' ? [] : [{ method: order.payment, amount: order.total }])
  const [method, setMethod] = useState<string>(parts[0]?.method ?? '')
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  // Keep the exact request across network failures and page reloads. A retry
  // must never silently acquire a new key and record a second refund.
  const storageKey = `coffeepos-refund-attempt-${order.id}`
  const [attempt, setAttempt] = useState<Payload | null>(() => {
    try { return JSON.parse(sessionStorage.getItem(storageKey) ?? 'null') as Payload | null } catch { return null }
  })
  useEffect(() => {
    let active = true
    api<Refund[]>(`/api/orders/${order.id}/refunds`).then(result => {
      if (active) { setRows(result); setLoaded(true) }
    }).catch(err => { if (active) setError(String(err.message)) })
    return () => { active = false }
  }, [order.id])
  const remaining = (parts.find(p => p.method === method)?.amount ?? 0) - rows.filter(r => r.method === method).reduce((sum, r) => sum + r.amount, 0)
  const submit = async () => {
    if (busy || !loaded) return
    const payload = attempt ?? { clientKey: crypto.randomUUID().replaceAll('-', ''), amount: Number(amount), method, reason: reason.trim(), externalConfirmed: confirmed }
    if (!attempt && (!Number.isSafeInteger(payload.amount) || payload.amount <= 0 || payload.amount > remaining || payload.reason.length < 3 || !confirmed)) {
      setError(t('Summa, sabab va tashqi tasdiqni tekshiring')); return
    }
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(payload))
      setAttempt(payload); setBusy(true); setError('')
      const saved = await api<Refund>(`/api/orders/${order.id}/refunds`, { method: 'POST', body: payload })
      sessionStorage.removeItem(storageKey)
      setRows(prev => prev.some(r => r.id === saved.id) ? prev : [...prev, saved])
      setAttempt(null); setAmount(''); setReason(''); setConfirmed(false)
    } catch (err) {
      if (err instanceof ApiError && [400, 401, 403, 404, 422].includes(err.status)) {
        sessionStorage.removeItem(storageKey); setAttempt(null)
      }
      setError(err instanceof Error ? err.message : t('Xato'))
    }
    finally { setBusy(false) }
  }
  return <section className="mt-4 space-y-3 rounded-xl border border-stone-300 p-3">
    <h4 className="font-semibold">{t('Pul qaytarish yozuvlari')}</h4>
    <p className="text-sm text-stone-600">{t('Bu amal pul yubormaydi. Faqat tashqarida bajarilgan qaytarishni qayd etadi. Ombor va bonus avtomatik qaytarilmaydi.')}</p>
    {rows.map(r => <div key={r.id} className="border-b py-2 text-sm">{fmt(r.amount)} · {t(PAYMENT_LABEL[r.method as keyof typeof PAYMENT_LABEL])} · {r.reason} · {r.staff} · {new Date(r.createdAt).toLocaleString()}</div>)}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {order.status !== 'cancelled' && <div className="space-y-2">
      <label className="block">{t("To'lov")}<select className="ml-2 rounded border p-2" value={attempt?.method ?? method} disabled={!!attempt || busy} onChange={e => setMethod(e.target.value)}>{parts.map(p => <option key={p.method} value={p.method}>{t(PAYMENT_LABEL[p.method])}</option>)}</select></label>
      <p>{t('Qaytarish uchun qolgan summa')}: {fmt(remaining)}</p>
      <label className="block">{t('Summa')}<input className="ml-2 rounded border p-2" type="number" min="1" max={remaining} step="1" value={attempt?.amount ?? amount} disabled={!!attempt || busy} onChange={e => setAmount(e.target.value)} /></label>
      <label className="block">{t('Sabab')}<input className="ml-2 rounded border p-2" maxLength={256} value={attempt?.reason ?? reason} disabled={!!attempt || busy} onChange={e => setReason(e.target.value)} /></label>
      <label className="block"><input type="checkbox" checked={attempt?.externalConfirmed ?? confirmed} disabled={!!attempt || busy} onChange={e => setConfirmed(e.target.checked)} /> {t('Pul tashqarida qaytarilganini tasdiqlayman')}</label>
      {attempt && <p>{t('Avvalgi so‘rov saqlangan. Qayta urinish aynan shu yozuvni tekshiradi.')}</p>}
      <button className="rounded-lg bg-stone-800 px-3 py-2 text-white disabled:opacity-50" disabled={busy || !loaded} onClick={() => void submit()}>{attempt ? t('Qayta urinish') : t('Qaytarishni qayd etish')}</button>
    </div>}
  </section>
}

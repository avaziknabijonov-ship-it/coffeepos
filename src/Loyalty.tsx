import { useEffect, useState } from 'react'
import { api } from './api'
import { som } from './data'
import { t } from './i18n'

type Config = { enabled: boolean; earnPct: number; redeemPct: number }
type Customer = { id: number; name: string; phone: string; balance: number }
type Entry = { orderId: string; earned: number; spent: number; balance: number; createdAt: number }
export type BonusSelection = { customerId?: number; spend: number }
const input = 'w-full rounded-xl border border-stone-200 bg-white p-3'

function CustomerSearch({ onSelect }: { onSelect: (c: Customer | null) => void }) {
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [missing, setMissing] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const find = async (create = false) => {
    setBusy(true); setError('')
    try {
      const c = create ? await api<Customer>('/api/loyalty/customers', { body: { phone, name } }) : (await api<{ customer: Customer | null }>(`/api/loyalty/customers?phone=${encodeURIComponent(phone)}`)).customer
      onSelect(c); setMissing(!c)
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="space-y-2">
    <div className="flex gap-2"><input aria-label={t('Mijoz telefoni')} type="tel" value={phone} placeholder="+998 90 123 45 67" className={input} onChange={e => { setPhone(e.target.value); onSelect(null); setMissing(false); setError('') }} disabled={busy} /><button type="button" disabled={busy || !phone.trim()} onClick={() => void find()} className="rounded-xl bg-stone-200 px-4 disabled:opacity-50">{t('Qidirish')}</button></div>
    {missing && <><p className="text-sm">{t('Mijoz topilmadi. Roziligi bilan bonus hisobini oching.')}</p><input maxLength={64} value={name} onChange={e => setName(e.target.value)} placeholder={t('Mijoz ismi')} className={input} /><button type="button" disabled={busy} onClick={() => void find(true)} className="rounded-xl bg-amber-100 p-3">{t('Bonus hisobini ochish')}</button></>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </div>
}

export function BonusPicker({ total, onChange }: { total: number; onChange: (s: BonusSelection) => void }) {
  const [config, setConfig] = useState<Config | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [spend, setSpend] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => { api<Config>('/api/loyalty/config').then(setConfig).catch(e => setError((e as Error).message)) }, [])
  const max = customer && config ? Math.min(customer.balance, Math.floor(total * config.redeemPct / 100)) : 0
  useEffect(() => { onChange({ customerId: customer?.id, spend: Math.min(spend, max) }) }, [customer, spend, max, onChange])
  if (error) return <p className="text-sm text-red-700">{t('Bonus tizimini yuklab bo‘lmadi')}: {error}</p>
  if (!config?.enabled) return null
  return <section className="space-y-2 rounded-xl bg-amber-50 p-3">
    <h3 className="font-semibold">{t('Mijoz bonuslari')}</h3>
    <CustomerSearch onSelect={c => { setCustomer(c); setSpend(0) }} />
    {customer && <><p>{customer.name || customer.phone} · {t('Balans')}: <b>{som(customer.balance)}</b></p><label className="block text-sm">{t('Ishlatiladigan bonus')} ({t('Ko‘pi bilan')} {som(max)})<input type="number" min={0} max={max} step={1} value={spend} onChange={e => setSpend(Math.min(max, Math.max(0, Math.floor(Number(e.target.value) || 0))))} className={input} /></label><p className="text-sm">{t('Yig‘iladigan bonus')}: {som(Math.floor((total - Math.min(spend, max)) * config.earnPct / 100))}</p></>}
  </section>
}

export default function LoyaltyAdmin() {
  const [config, setConfig] = useState<Config | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [history, setHistory] = useState<Entry[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { api<Config>('/api/loyalty/config').then(setConfig).catch(e => setMessage((e as Error).message)) }, [])
  useEffect(() => { let active = true; if (customer) api<Entry[]>(`/api/loyalty/customers/${customer.id}/history`).then(h => { if (active) setHistory(h) }).catch(e => { if (active) setMessage((e as Error).message) }); return () => { active = false } }, [customer])
  const save = async () => {
    if (!config) return
    setBusy(true); setMessage('')
    try { setConfig(await api<Config>('/api/loyalty/config', { method: 'PUT', body: config })); setMessage(t('Saqlandi')) }
    catch (e) { setMessage((e as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="space-y-4 rounded-2xl border bg-white p-5">
    <h2 className="text-xl font-bold">{t('Bonus tizimi')}</h2>
    <p>{t('1 bonus = 1 so‘m. Bonus chegirmadan keyingi to‘langan summadan yig‘iladi. Qarz savdosiga bonus berilmaydi. Bonus muddatsiz saqlanadi.')}</p>
    {config && <div className="space-y-3"><label className="flex gap-2"><input type="checkbox" checked={config.enabled} onChange={e => setConfig({ ...config, enabled: e.target.checked })} />{t('Bonus tizimini yoqish')}</label><div className="grid gap-3 sm:grid-cols-2"><label>{t('Xariddan yig‘iladigan bonus (%)')}<input className={input} type="number" min={0} max={100} value={config.earnPct} onChange={e => setConfig({ ...config, earnPct: Number(e.target.value) })} /></label><label>{t('Xaridning bonus bilan to‘lanadigan qismi (%)')}<input className={input} type="number" min={0} max={100} value={config.redeemPct} onChange={e => setConfig({ ...config, redeemPct: Number(e.target.value) })} /></label></div><button disabled={busy} onClick={() => void save()} className="rounded-xl bg-amber-600 px-5 py-3 font-bold text-white disabled:opacity-50">{t('Saqlash')}</button></div>}
    {message && <p role="status">{message}</p>}
    <h3 className="font-semibold">{t('Mijoz va bonus tarixi')}</h3>
    <CustomerSearch onSelect={c => { setCustomer(c); setHistory([]) }} />
    {customer && <><p>{customer.name} · {customer.phone} · {t('Balans')}: <b>{som(customer.balance)}</b></p><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['Sana', 'Buyurtma', 'Yig‘ildi', 'Ishlatildi', 'Balans'].map(s => <th key={s} className="p-2">{t(s)}</th>)}</tr></thead><tbody>{history.map(h => <tr key={h.orderId}><td className="p-2">{new Date(h.createdAt).toLocaleString()}</td><td>{h.orderId}</td><td>+{som(h.earned)}</td><td>−{som(h.spent)}</td><td>{som(h.balance)}</td></tr>)}</tbody></table></div></>}
  </section>
}

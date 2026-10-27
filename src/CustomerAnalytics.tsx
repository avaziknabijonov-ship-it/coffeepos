import { useEffect, useState } from 'react'
import { api } from './api'
import { t } from './i18n'
import { som, STATUS_LABEL, type Status } from './data'
import { exportExcel } from './exportExcel'

type Customer = { id: number; name: string; phoneMasked: string; analyticsConsent: boolean }
type Purchase = { id: string; number: number; createdAt: number; total: number; status: string }
type Report = { consentingCustomers: number; purchasingCustomers: number; repeatCustomers: number; orders: number; revenue: number; cohorts: { cohort: string; month: string; customers: number; orders: number; revenue: number }[] }
export default function CustomerAnalytics() {
  const [days, setDays] = useState(30)
  const [revision, setRevision] = useState(0)
  const [report, setReport] = useState<Report | null>(null)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [cursor, setCursor] = useState<number | null>(null)
  const [next, setNext] = useState<number | null>(null)
  const [history, setHistory] = useState<{ customerId: number; rows: Purchase[]; nextCursor: number | null } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const load = async () => {
      setBusy(true); setError(''); setHistory(null)
      try {
        const [r, c] = await Promise.all([api<Report>('/api/reports/customers?days=' + days), api<{ items: Customer[]; nextCursor: number | null }>('/api/customers' + (cursor ? '?before_id=' + cursor : ''))])
        if (active) { setReport(r); setCustomers(c.items); setNext(c.nextCursor) }
      } catch (err) { if (active) { setError((err as Error).message); setReport(null); setCustomers([]) } }
      finally { if (active) setBusy(false) }
    }
    void load(); return () => { active = false }
  }, [days, revision, cursor])
  const consent = async (customer: Customer) => {
    if (!customer.analyticsConsent && !window.confirm(t('Mijoz tahlil uchun rozilik berganini tasdiqlaysizmi?'))) return
    setBusy(true); setError(''); setHistory(null)
    try {
      await api('/api/customers/' + customer.id + '/analytics-consent', { method: 'PUT', body: { granted: !customer.analyticsConsent, operatorConfirmed: true } })
      // Immediately clear previously consented data, including on failed refresh.
      setReport(null); setRevision(v => v + 1)
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  const purchases = async (customerId: number, before?: number) => {
    setBusy(true); setError(''); setHistory(null)
    try {
      const result = await api<{ items: Purchase[]; nextCursor: number | null }>(`/api/customers/${customerId}/purchases` + (before ? '?before_id=' + before : ''))
      setHistory({ customerId, rows: result.items, nextCursor: result.nextCursor })
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <h2 className="text-xl font-semibold">{t('Mijozlar tahlili')}</h2>
    <p className="text-sm text-stone-600">{t('Faqat roziligi qayd etilgan mijozlar. Takroriy xarid — davrda kamida 2 ta faol chek. Tushum refund ayrilmagan summa.')}</p>
    <div className="flex flex-wrap gap-3"><select aria-label={t('Davr')} className="rounded border p-2" value={days} onChange={e => setDays(Number(e.target.value))}><option value={7}>{t('Oxirgi 7 kun')}</option><option value={30}>{t('Oxirgi 30 kun')}</option><option value={90}>{t('Oxirgi 90 kun')}</option></select><button disabled={busy} className="rounded border px-3" onClick={() => { setCursor(null); setRevision(v => v + 1) }}>{t('Yangilash')}</button></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {report && <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{[[t('Rozilik bergan mijozlar'), report.consentingCustomers], [t('Xarid qilgan mijozlar'), report.purchasingCustomers], [t('Takroriy xarid qilganlar'), report.repeatCustomers], [t('Tushum'), som(report.revenue)]].map(([label, value]) => <div key={String(label)} className="rounded-lg border p-3"><p className="text-sm">{label}</p><b>{value}</b></div>)}</div>
      <h3 className="font-semibold">{t('Ro‘yxatdan o‘tgan oy / xarid oyi')}</h3>
      <button className="rounded border px-3 py-2" onClick={() => exportExcel('coffeepos-customer-cohorts', ['Ro‘yxatdan o‘tgan oy', 'Xarid oyi', 'Mijozlar', 'Cheklar', 'Tushum'].map(label => t(label)), report.cohorts.map(c => [c.cohort, c.month, c.customers, c.orders, c.revenue]))}>{t('Excelga eksport')}</button>
      <div className="overflow-x-auto"><table className="w-full text-sm"><tbody>{report.cohorts.map(c => <tr key={c.cohort + c.month} className="border-b"><td className="p-2">{c.cohort} / {c.month}</td><td>{c.customers} · {c.orders}</td><td>{som(c.revenue)}</td></tr>)}</tbody></table></div>
    </>}
    <h3 className="font-semibold">{t('Mijoz roziligini boshqarish')}</h3>
    <div className="space-y-2">{customers.map(c => <div key={c.id} className="flex flex-wrap items-center gap-3 rounded border p-3"><span>#{c.id} · {c.name} · {c.phoneMasked}</span><button disabled={busy} className="rounded border p-2" onClick={() => void consent(c)}>{c.analyticsConsent ? t('Rozilikni bekor qilish') : t('Rozilikni qayd etish')}</button>{c.analyticsConsent && <button disabled={busy} className="rounded border p-2" onClick={() => void purchases(c.id)}>{t('Xaridlar tarixi')}</button>}</div>)}</div>
    <button disabled={busy || !next} className="rounded border p-2 disabled:opacity-50" onClick={() => setCursor(next)}>{t('Oldingi yozuvlar')}</button>
    {history && <div className="space-y-2 rounded border p-3"><h3>#{history.customerId} · {t('Xaridlar tarixi')}</h3>{history.rows.map(p => <p key={p.id}>№{p.number} · {new Date(p.createdAt).toLocaleString()} · {som(p.total)} · {t(STATUS_LABEL[p.status as Status])}</p>)}<button disabled={busy || !history.nextCursor} className="rounded border p-2" onClick={() => void purchases(history.customerId, history.nextCursor ?? undefined)}>{t('Oldingi yozuvlar')}</button></div>}
  </section>
}

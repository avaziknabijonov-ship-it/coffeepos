import { useEffect, useState } from 'react'
import { api } from './api'
import { som } from './data'
import { t } from './i18n'

type Row = { staffId: number; name: string; role: string; monthlySalary: number; standardDays: number
  workedDays: number; deductions: number; paid: number; earned: number; toPay: number; overpaid: number; note: string }
type Report = { month: string; items: Row[] }
type Payment = { id: number; staffId: number; amount: number; note: string; createdAt: number; recordedBy: string }
const localMonth = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset()*60000).toISOString().slice(0,7) }
const num = (v: string) => Number(v) || 0
const control = 'w-full min-w-[76px] rounded-lg border border-stone-200 bg-white px-2 py-2 text-sm'

export default function Payroll() {
  const [month, setMonth] = useState(localMonth)
  const [rows, setRows] = useState<Row[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [staffId, setStaffId] = useState(0)
  const [amount, setAmount] = useState('')
  const [note, setNote] = useState('Avans')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    try {
      const [payroll, history] = await Promise.all([
        api<Report>('/api/payroll?month=' + encodeURIComponent(month)),
        api<Payment[]>('/api/staff-payments'),
      ])
      setRows(payroll.items); setPayments(history)
    } catch (e) { setError((e as Error).message) }
  }
  useEffect(() => { void load() }, [month])
  const patch = (id: number, updates: Partial<Row>) => setRows(v => v.map(x => x.staffId === id ? { ...x, ...updates } : x))

  async function save(row: Row) {
    setBusy(true); setError('')
    try {
      await api('/api/payroll/' + row.staffId + '/' + month, { method: 'PUT', body: {
        monthly_salary: row.monthlySalary, standard_days: row.standardDays,
        worked_days: row.workedDays, deductions: row.deductions, note: row.note,
      }})
      await load()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function addPayment() {
    if (!staffId || !Number.isSafeInteger(num(amount)) || num(amount) <= 0) {
      setError(t('Summani to‘g‘ri kiriting')); return
    }
    if (!window.confirm(t('Xodimga to‘lov yozilsinmi?'))) return
    setBusy(true); setError('')
    try {
      await api('/api/staff-payments', { method: 'POST', body: { staff_id: staffId, amount: num(amount), note } })
      setAmount(''); await load()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <div className="space-y-4">
    <section className="rounded-2xl border bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-lg font-semibold">{t('Oylik hisobi')}</h2>
          <p className="text-sm text-stone-500">{t('Ishlangan kunlar qo‘lda belgilanadi. Avans va to‘lovlar qoldiqdan ayriladi.')}</p></div>
        <label className="text-sm">{t('Oy')}<input type="month" className="ml-2 rounded-lg border p-2" value={month}
          onChange={e=>setMonth(e.target.value)} /></label>
      </div>
      {error && <p className="mt-3 text-sm text-red-700" role="alert">{error}</p>}
    </section>
    <section className="rounded-2xl border bg-white p-4">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] text-sm">
          <thead className="text-left text-stone-500">
            <tr>
              <th className="p-2">{t('Xodim')}</th><th className="p-2">{t('Oylik stavka')}</th>
              <th className="p-2">{t('Me’yor kun')}</th><th className="p-2">{t('Ishlangan kun')}</th>
              <th className="p-2">{t('Ushlanmalar')}</th><th className="p-2">{t('Hisoblangan')}</th>
              <th className="p-2">{t('staff:To‘langan')}</th><th className="p-2">{t('Qoldiq')}</th><th className="p-2">{t('Amal')}</th>
            </tr>
          </thead>
          <tbody>{rows.map(r => {
            const earned = Math.round(r.monthlySalary * r.workedDays / (r.standardDays || 1))
            const balance = earned - r.deductions - r.paid
            return <tr key={r.staffId} className="border-t align-middle">
              <td className="p-2 font-semibold">{r.name}</td>
              <td className="p-2"><input aria-label={r.name + ' salary'} className={control} type="number" min={0} value={r.monthlySalary} onChange={e=>patch(r.staffId,{monthlySalary:num(e.target.value)})}/></td>
              <td className="p-2"><input className={control} type="number" min={1} max={31} value={r.standardDays} onChange={e=>patch(r.staffId,{standardDays:num(e.target.value)})}/></td>
              <td className="p-2"><input className={control} type="number" min={0} step={0.5} max={r.standardDays} value={r.workedDays} onChange={e=>patch(r.staffId,{workedDays:num(e.target.value)})}/></td>
              <td className="p-2"><input className={control} type="number" min={0} value={r.deductions} onChange={e=>patch(r.staffId,{deductions:num(e.target.value)})}/></td>
              <td className="p-2 tabular-nums">{som(earned)}</td>
              <td className="p-2 tabular-nums">{som(r.paid)}</td>
              <td className="p-2 font-semibold tabular-nums">{balance >= 0 ? som(balance) : '−' + som(-balance)}</td>
              <td className="p-2"><button disabled={busy} onClick={()=>save(r)}
                className="rounded-lg bg-stone-900 px-3 py-2 text-white disabled:opacity-40">{t('Saqlash')}</button></td>
            </tr>
          })}</tbody>
        </table>
      </div>
    </section>
    <section className="rounded-2xl border bg-white p-4">
      <h3 className="mb-3 font-semibold">{t('Avans yoki oylik to‘lovi')}</h3>
      <div className="flex flex-wrap gap-2">
        <select className={control} value={staffId} onChange={e=>setStaffId(num(e.target.value))}>
          <option value={0}>{t('Xodimni tanlang')}</option>
          {rows.map(r=><option key={r.staffId} value={r.staffId}>{r.name}</option>)}
        </select>
        <input className={control} type="number" inputMode="numeric" min={1} placeholder={t('Summa')} value={amount} onChange={e=>setAmount(e.target.value)}/>
        <input className={control} maxLength={256} value={note} onChange={e=>setNote(e.target.value)} placeholder={t('Izoh')}/>
        <button onClick={addPayment} disabled={busy} className="rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{t('To‘lovni saqlash')}</button>
      </div>
      <h4 className="my-3 text-sm font-semibold">{t('So‘nggi to‘lovlar')}</h4>
      <div className="space-y-2">{payments.slice(0,30).map(p=><div key={p.id} className="flex flex-wrap justify-between gap-2 border-b py-2 text-sm">
        <span>{new Date(p.createdAt).toLocaleDateString()} · {rows.find(r=>r.staffId===p.staffId)?.name ?? String(p.staffId)} · {p.note}</span>
        <b>{som(p.amount)}</b>
      </div>)}</div>
    </section>
  </div>
}

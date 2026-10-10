import { useEffect, useState } from 'react'
import { api } from './api'
import { fmt } from './data'

type Salary = { staffId: number; name: string; salaryType: 'monthly' | 'daily'; salaryRate: number; days: number; earned: number; paid: number; remaining: number }
type Debt = { id: number; customer: string; phone: string; note: string; total: number; paid: number; remaining: number }
type Payment = { id: number; amount: number; method: string; note: string; createdAt: number }
const field = 'rounded-lg border border-stone-200 px-3 py-2'
const button = 'rounded-lg bg-amber-600 px-3 py-2 font-semibold text-white disabled:opacity-50'

export function SalaryView() {
  const [month, setMonth] = useState(() => new Date().toLocaleDateString('sv-SE').slice(0, 7))
  const [list, setList] = useState<Salary[]>([])
  const [error, setError] = useState('')
  const load = () => api<Salary[]>('/api/salary?month=' + month).then(setList).catch((e: Error) => setError(e.message))
  useEffect(() => { void load() }, [month])
  const setConfig = async (s: Salary, salaryType: 'monthly' | 'daily', salaryRate: number) => {
    try { await api('/api/staff/' + s.staffId + '/salary', { method: 'PATCH', body: { salaryType, salaryRate } }); await load() } catch (e) { alert((e as Error).message) }
  }
  const add = async (s: Salary, kind: string) => {
    const raw = prompt(kind === 'day' ? 'Necha kun ishladi?' : 'Summani kiriting')
    if (!raw) return
    const amount = Number(raw.replace(/\s/g, ''))
    if (!Number.isInteger(amount) || amount <= 0) return alert('Musbat butun son kiriting')
    const note = prompt('Izoh (ixtiyoriy)') ?? ''
    try { await api('/api/salary/entries', { body: { staffId: s.staffId, kind, amount, note } }); await load() } catch (e) { alert((e as Error).message) }
  }
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <div className="flex flex-wrap items-center gap-3"><h2 className="font-bold">Xodimlar oyligi</h2><input type="month" className={field} value={month} onChange={e => setMonth(e.target.value)} /></div>
    {error && <p className="text-red-600">{error}</p>}
    {list.map(s => <div key={s.staffId} className="space-y-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center gap-3"><strong className="flex-1">{s.name}</strong>
        <select className={field} value={s.salaryType} onChange={e => void setConfig(s, e.target.value as 'monthly' | 'daily', s.salaryRate)}>
          <option value="monthly">Oylik</option><option value="daily">Kunlik</option>
        </select>
        <label className="text-sm">Stavka <input className={field + ' ml-2 w-36'} type="number" min="0" defaultValue={s.salaryRate} key={s.staffId + ':' + s.salaryRate} onBlur={e => { const n = Number(e.target.value); if (Number.isInteger(n) && n >= 0 && n !== s.salaryRate) void setConfig(s, s.salaryType, n) }} /></label>
      </div>
      <div className="grid gap-2 text-sm sm:grid-cols-4"><span>Ish kunlari: {s.days}</span><span>Hisoblandi: {fmt(s.earned)} so‘m</span><span>To‘landi: {fmt(s.paid)} so‘m</span><strong>Qoldiq: {fmt(s.remaining)} so‘m</strong></div>
      <div className="flex flex-wrap gap-2">
        {s.salaryType === 'daily' && <button className={button} onClick={() => void add(s, 'day')}>+ Ish kuni</button>}
        <button className={button} onClick={() => void add(s, 'bonus')}>+ Bonus</button>
        <button className={button} onClick={() => void add(s, 'deduction')}>Ushlanma</button>
        <button className={button} onClick={() => void add(s, 'advance')}>Avans</button>
        <button className={button} onClick={() => void add(s, 'payment')}>Oylik to‘landi</button>
      </div>
    </div>)}
    <p className="text-xs text-stone-500">Kunlik ish kunlari qo‘lda kiritiladi. Oylik stavka tanlangan oy uchun to‘liq hisoblanadi. Hozircha ishga kirish sanasi bo‘yicha proporsional hisoblash yo‘q.</p>
  </section>
}

export function DebtsView() {
  const [list, setList] = useState<Debt[]>([])
  const [history, setHistory] = useState<Record<number, Payment[]>>({})
  const [error, setError] = useState('')
  const load = () => api<Debt[]>('/api/debts').then(setList).catch((e: Error) => setError(e.message))
  useEffect(() => { void load() }, [])
  const pay = async (d: Debt) => {
    const raw = prompt('Qaytarilgan summa (so‘m)')
    if (!raw) return
    const amount = Number(raw.replace(/\s/g, ''))
    if (!Number.isInteger(amount) || amount <= 0 || amount > d.remaining) return alert('Summa qarz qoldig‘idan oshmasin')
    const method = prompt('To‘lov usuli: naqd, karta, payme, click', 'naqd')
    if (!['naqd', 'karta', 'payme', 'click'].includes(method ?? '')) return alert('To‘lov usuli noto‘g‘ri')
    const note = prompt('Izoh (ixtiyoriy)') ?? ''
    try { await api('/api/debts/' + d.id + '/payments', { body: { amount, method, note } }); await load(); const h = await api<Payment[]>('/api/debts/' + d.id + '/payments'); setHistory(old => ({ ...old, [d.id]: h })) } catch (e) { alert((e as Error).message) }
  }
  const toggle = async (id: number) => {
    if (history[id]) return setHistory(old => { const next = { ...old }; delete next[id]; return next })
    try { const h = await api<Payment[]>('/api/debts/' + id + '/payments'); setHistory(old => ({ ...old, [id]: h })) } catch (e) { alert((e as Error).message) }
  }
  return <section className="space-y-3 rounded-2xl border bg-white p-4">
    <h2 className="font-bold">Qarzlar ro‘yxati</h2>
    {error && <p className="text-red-600">{error}</p>}
    {list.map(d => <div key={d.id} className="space-y-2 rounded-xl border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><strong>{d.customer}</strong><span>{d.phone}</span><span className="font-semibold">Qoldiq: {fmt(d.remaining)} so‘m</span></div>
      {d.note && <p className="text-sm text-stone-600">Izoh: {d.note}</p>}
      <p className="text-sm">Jami {fmt(d.total)} · Qaytarildi {fmt(d.paid)}</p>
      <div className="flex gap-2"><button className={button} disabled={d.remaining <= 0} onClick={() => void pay(d)}>Qarz to‘lash</button><button className={field} onClick={() => void toggle(d.id)}>To‘lovlar tarixi</button></div>
      {history[d.id] && <div className="space-y-1 text-sm">{history[d.id].map(p => <p key={p.id}>{new Date(p.createdAt).toLocaleDateString('ru-RU')} · {fmt(p.amount)} so‘m · {p.method} · {p.note}</p>)}{history[d.id].length === 0 && 'To‘lovlar yo‘q'}</div>}
    </div>)}
    {list.length === 0 && <p className="text-stone-500">Hozircha qarz yo‘q.</p>}
  </section>
}


type Expense = { id: number; amount: number; category: string; note: string; method: string; staffName: string; createdAt: number }

export function ExpensesView() {
  const [list, setList] = useState<Expense[]>([])
  const [error, setError] = useState('')
  const [amount, setAmount] = useState('')
  const [category, setCategory] = useState('Boshqa')
  const [note, setNote] = useState('')
  const [method, setMethod] = useState('naqd')
  const [busy, setBusy] = useState(false)
  const [date, setDate] = useState(() => new Date().toLocaleDateString('sv-SE'))
  const load = () => api<Expense[]>('/api/expenses').then(setList).catch((e: Error) => setError(e.message))
  useEffect(() => { void load() }, [])
  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    const value = Number(amount)
    if (!Number.isSafeInteger(value) || value <= 0) return setError('To‘g‘ri summa kiriting')
    setBusy(true); setError('')
    try {
      await api('/api/expenses', { body: { amount: value, category, note, method } })
      setAmount(''); setNote(''); await load()
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  const filtered = list.filter(e => new Date(e.createdAt).toLocaleDateString('sv-SE') === date)
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <h2 className="font-bold">Kunlik chiqimlar</h2>
    <form className="flex flex-wrap items-end gap-2" onSubmit={e => void save(e)}>
      <label className="text-sm">Summa (so‘m)<input required type="number" min="1" max="1000000000" className={field + ' block w-40'} value={amount} onChange={e => setAmount(e.target.value)} /></label>
      <label className="text-sm">Sabab<select className={field + ' block'} value={category} onChange={e => setCategory(e.target.value)}>
        {['Boshqa', 'Xomashyo', 'Transport', 'Tozalash', 'Kommunal', 'Ta’mirlash'].map(x => <option key={x}>{x}</option>)}
      </select></label>
      <label className="text-sm">To‘lov turi<select className={field + ' block'} value={method} onChange={e => setMethod(e.target.value)}>
        <option value="naqd">Naqd</option><option value="karta">Karta</option><option value="payme">Payme</option><option value="click">Click</option>
      </select></label>
      <label className="text-sm">Izoh<input className={field + ' block'} maxLength={500} value={note} onChange={e => setNote(e.target.value)} placeholder="Nimaga sarflandi?" /></label>
      <button disabled={busy} className={button}>Chiqimni saqlash</button>
    </form>
    {error && <p className="text-sm text-red-600">{error}</p>}
    <div className="flex flex-wrap items-center justify-between gap-2"><label className="text-sm">Sana <input className={field + ' ml-2'} type="date" value={date} onChange={e => setDate(e.target.value)} /></label><strong>Jami: {fmt(filtered.reduce((a, e) => a + e.amount, 0))} so‘m</strong></div>
    <div className="divide-y">{filtered.map(e => <div key={e.id} className="flex flex-wrap justify-between gap-2 py-2 text-sm"><div><strong>{e.category}</strong> · {e.note || 'Izohsiz'}<p className="text-stone-500">{e.staffName} · {e.method} · {new Date(e.createdAt).toLocaleTimeString('uz-UZ')}</p></div><strong>{fmt(e.amount)} so‘m</strong></div>)}</div>
    {filtered.length === 0 && <p className="text-sm text-stone-500">Bu kunda chiqim yo‘q.</p>}
    <p className="text-xs text-stone-500">Naqd chiqim ochiq smenadan ayriladi. Bu xarajat ombor qoldig‘ini avtomatik oshirmaydi.</p>
  </section>
}

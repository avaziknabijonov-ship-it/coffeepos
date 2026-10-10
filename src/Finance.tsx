import { useEffect, useState } from 'react'
import { api } from './api'
import { getLang, t } from './i18n'
import { fmt } from './data'
import { useAppState } from './store'

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
    const raw = prompt(t(kind === 'day' ? 'Necha kun ishladi?' : 'Summani kiriting'))
    if (!raw) return
    const amount = Number(raw.replace(/\s/g, ''))
    if (!Number.isInteger(amount) || amount <= 0) return alert(t('Musbat butun son kiriting'))
    const note = prompt(t('Izoh (ixtiyoriy)')) ?? ''
    try { await api('/api/salary/entries', { body: { staffId: s.staffId, kind, amount, note } }); await load() } catch (e) { alert((e as Error).message) }
  }
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <div className="flex flex-wrap items-center gap-3"><h2 className="font-bold">{t('Xodimlar oyligi')}</h2><input type="month" className={field} value={month} onChange={e => setMonth(e.target.value)} /></div>
    {error && <p className="text-red-600">{error}</p>}
    {list.map(s => <div key={s.staffId} className="space-y-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center gap-3"><strong className="flex-1">{s.name}</strong>
        <select className={field} value={s.salaryType} onChange={e => void setConfig(s, e.target.value as 'monthly' | 'daily', s.salaryRate)}>
          <option value="monthly">{t('Oylik')}</option><option value="daily">{t('Kunlik')}</option>
        </select>
        <label className="text-sm">{t('Stavka')} <input className={field + ' ml-2 w-36'} type="number" min="0" defaultValue={s.salaryRate} key={s.staffId + ':' + s.salaryRate} onBlur={e => { const n = Number(e.target.value); if (Number.isInteger(n) && n >= 0 && n !== s.salaryRate) void setConfig(s, s.salaryType, n) }} /></label>
      </div>
      <div className="grid gap-2 text-sm sm:grid-cols-4"><span>{t('Ish kunlari:')} {s.days}</span><span>{t('Hisoblandi:')} {fmt(s.earned)} {t("so'm")}</span><span>{t('To‘landi:')} {fmt(s.paid)} {t("so'm")}</span><strong>{t('Qoldiq:')} {fmt(s.remaining)} {t("so'm")}</strong></div>
      <div className="flex flex-wrap gap-2">
        {s.salaryType === 'daily' && <button className={button} onClick={() => void add(s, 'day')}>{t('+ Ish kuni')}</button>}
        <button className={button} onClick={() => void add(s, 'bonus')}>{t('+ Bonus')}</button>
        <button className={button} onClick={() => void add(s, 'deduction')}>{t('Ushlanma')}</button>
        <button className={button} onClick={() => void add(s, 'advance')}>{t('Avans')}</button>
        <button className={button} onClick={() => void add(s, 'payment')}>{t('Oylik to‘landi')}</button>
      </div>
    </div>)}
    <p className="text-xs text-stone-500">{t('Kunlik ish kunlari qo‘lda kiritiladi. Kunlik xodimning qoldig‘i avvalgi oylardan yig‘ilgan qarzni ham hisobga oladi; to‘lovlar shu qoldiqdan ayriladi. Oylik stavka tanlangan oy uchun to‘liq hisoblanadi. Stavkani o‘zgartirish avvalgi kunlar hisobiga ham ta’sir qiladi.')}</p>
  </section>
}

export function DebtsView() {
  const [list, setList] = useState<Debt[]>([])
  const [history, setHistory] = useState<Record<number, Payment[]>>({})
  const [error, setError] = useState('')
  const load = () => api<Debt[]>('/api/debts').then(setList).catch((e: Error) => setError(e.message))
  useEffect(() => { void load() }, [])
  const pay = async (d: Debt) => {
    const raw = prompt(t('Qaytarilgan summa (so‘m)'))
    if (!raw) return
    const amount = Number(raw.replace(/\s/g, ''))
    if (!Number.isInteger(amount) || amount <= 0 || amount > d.remaining) return alert(t('Summa qarz qoldig‘idan oshmasin'))
    const method = prompt(t('To‘lov usuli: naqd, karta, payme, click'), 'naqd')
    if (!['naqd', 'karta', 'payme', 'click'].includes(method ?? '')) return alert(t('To‘lov usuli noto‘g‘ri'))
    const note = prompt('Izoh (ixtiyoriy)') ?? ''
    try { await api('/api/debts/' + d.id + '/payments', { body: { amount, method, note } }); await load(); const h = await api<Payment[]>('/api/debts/' + d.id + '/payments'); setHistory(old => ({ ...old, [d.id]: h })) } catch (e) { alert((e as Error).message) }
  }
  const toggle = async (id: number) => {
    if (history[id]) return setHistory(old => { const next = { ...old }; delete next[id]; return next })
    try { const h = await api<Payment[]>('/api/debts/' + id + '/payments'); setHistory(old => ({ ...old, [id]: h })) } catch (e) { alert((e as Error).message) }
  }
  return <section className="space-y-3 rounded-2xl border bg-white p-4">
    <h2 className="font-bold">{t('Qarzlar ro‘yxati')}</h2>
    {error && <p className="text-red-600">{error}</p>}
    {list.map(d => <div key={d.id} className="space-y-2 rounded-xl border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><strong>{d.customer}</strong><span>{d.phone}</span><span className="font-semibold">{t('Qoldiq:')} {fmt(d.remaining)} {t("so'm")}</span></div>
      {d.note && <p className="text-sm text-stone-600">{t('Izoh')}: {d.note}</p>}
      <p className="text-sm">{t('Jami')} {fmt(d.total)} · {t('Qaytarildi')} {fmt(d.paid)}</p>
      <div className="flex gap-2"><button className={button} disabled={d.remaining <= 0} onClick={() => void pay(d)}>{t('Qarz to‘lash')}</button><button className={field} onClick={() => void toggle(d.id)}>{t('To‘lovlar tarixi')}</button></div>
      {history[d.id] && <div className="space-y-1 text-sm">{history[d.id].map(p => <p key={p.id}>{new Date(p.createdAt).toLocaleDateString(getLang() === 'ru' ? 'ru-RU' : 'uz-UZ')} · {fmt(p.amount)} {t("so'm")} · {t(p.method)} · {p.note}</p>)}{history[d.id].length === 0 && t('To‘lovlar yo‘q')}</div>}
    </div>)}
    {list.length === 0 && <p className="text-stone-500">{t('Hozircha qarz yo‘q.')}</p>}
  </section>
}


type Expense = { id: number; amount: number; category: string; note: string; method: string; staffName: string; createdAt: number }

export function ExpensesView() {
  const { session } = useAppState()
  const [staffList, setStaffList] = useState<{ id: number; name: string }[]>([])
  const [salaryStaffId, setSalaryStaffId] = useState<number>(0)
  const [list, setList] = useState<Expense[]>([])
  const [error, setError] = useState('')
  const [amount, setAmount] = useState('')
  const [category, setCategory] = useState('Boshqa')
  const [note, setNote] = useState('')
  const [method, setMethod] = useState('naqd')
  const [busy, setBusy] = useState(false)
  const [date, setDate] = useState(() => new Date().toLocaleDateString('sv-SE'))
  const load = () => api<Expense[]>('/api/expenses').then(setList).catch((e: Error) => setError(e.message))
  useEffect(() => { void load(); void api<{ id: number; name: string }[]>('/api/staff/expense-recipients').then(setStaffList).catch(() => {}) }, [session?.staff.role])
  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    const value = Number(amount)
    if (!Number.isSafeInteger(value) || value <= 0) return setError(t('To‘g‘ri summa kiriting'))
    setBusy(true); setError('')
    try {
      const targetId = salaryStaffId
      if (category === 'Oylik' && !targetId) { setBusy(false); return setError(t('Xodimni tanlang')) }
      await api('/api/expenses', { body: { amount: value, category, note, method, salaryStaffId: category === 'Oylik' ? targetId : null } })
      setAmount(''); setNote(''); await load()
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  const filtered = list.filter(e => new Date(e.createdAt).toLocaleDateString('sv-SE') === date)
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <h2 className="font-bold">{t('Kunlik chiqimlar')}</h2>
    <form className="flex flex-wrap items-end gap-2" onSubmit={e => void save(e)}>
      <label className="text-sm">{t('Summa (so‘m)')}<input required type="number" min="1" max="1000000000" className={field + ' block w-40'} value={amount} onChange={e => setAmount(e.target.value)} /></label>
      <label className="text-sm">{t('Sabab')}<select className={field + ' block'} value={category} onChange={e => setCategory(e.target.value)}>
        {['Boshqa', 'Xomashyo', 'Transport', 'Tozalash', 'Kommunal', 'Ta’mirlash', 'Oylik'].map(x => <option key={x} value={x}>{t(x === 'Tozalash' ? 'expense:Tozalash' : x)}</option>)}
      </select></label>
      {category === 'Oylik' && <label className="text-sm">{t('Xodim')}<select required className={field + ' block'} value={salaryStaffId} onChange={e => setSalaryStaffId(Number(e.target.value))}><option value={0}>{t('Xodimni tanlang')}</option>{staffList.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>}
      <label className="text-sm">{t('To‘lov turi')}<select className={field + ' block'} value={method} onChange={e => setMethod(e.target.value)}>
        <option value="naqd">{t('Naqd')}</option><option value="karta">{t('Karta')}</option><option value="payme">Payme</option><option value="click">Click</option>
      </select></label>
      <label className="text-sm">{t('Izoh')}<input className={field + ' block'} maxLength={500} value={note} onChange={e => setNote(e.target.value)} placeholder={t('Nimaga sarflandi?')} /></label>
      <button disabled={busy} className={button}>{t('Chiqimni saqlash')}</button>
    </form>
    {error && <p className="text-sm text-red-600">{error}</p>}
    <div className="flex flex-wrap items-center justify-between gap-2"><label className="text-sm">{t('Sana')} <input className={field + ' ml-2'} type="date" value={date} onChange={e => setDate(e.target.value)} /></label><strong>{t('Jami')}: {fmt(filtered.reduce((a, e) => a + e.amount, 0))} {t("so'm")}</strong></div>
    <div className="divide-y">{filtered.map(e => <div key={e.id} className="flex flex-wrap justify-between gap-2 py-2 text-sm"><div><strong>{t(e.category)}</strong> · {e.note || t('Izohsiz')}<p className="text-stone-500">{e.staffName} · {t(e.method)} · {new Date(e.createdAt).toLocaleTimeString('uz-UZ')}</p></div><strong>{fmt(e.amount)} {t("so'm")}</strong></div>)}</div>
    {filtered.length === 0 && <p className="text-sm text-stone-500">{t('Bu kunda chiqim yo‘q.')}</p>}
    <p className="text-xs text-stone-500">{t('Naqd chiqim ochiq smenadan ayriladi. Bu xarajat ombor qoldig‘ini avtomatik oshirmaydi.')}</p>
  </section>
}

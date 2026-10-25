import { useEffect, useState } from 'react'
import { api } from './api'
import { exportExcel } from './exportExcel'
import { fmt } from './data'
import { t } from './i18n'
type Expense = { id: number; amount: number; category: string; description: string; payment: string; staff: string; createdAt: number }
export default function Expenses() {
  const [items, setItems] = useState<Expense[]>([])
  const [amount, setAmount] = useState('')
  const [category, setCategory] = useState('Boshqa')
  const [description, setDescription] = useState('')
  const [payment, setPayment] = useState('cash')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const load = () => api<Expense[]>('/api/expenses').then(setItems).catch(e => setError((e as Error).message))
  useEffect(() => { void load() }, [])
  async function save() {
    if (!Number.isSafeInteger(Number(amount)) || Number(amount) <= 0) { setError(t('Summani to‘g‘ri kiriting')); return }
    setSaving(true); setError('')
    try {
      await api('/api/expenses', { body: { amount: Number(amount), category, description, payment } })
      setAmount(''); setDescription(''); await load()
    } catch (e) { setError((e as Error).message) } finally { setSaving(false) }
  }
  const field = 'w-full rounded-xl border border-stone-200 px-3 py-2.5 text-sm'
  return <div className="space-y-4">
    <section className="rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="mb-4 text-lg font-bold">{t('Xarajat kiritish')}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label>{t('Summa')}<input className={field} type="number" min="1" step="1" value={amount} onChange={e=>setAmount(e.target.value)} /></label>
        <label>{t('Sabab')}<select className={field} value={category} onChange={e=>setCategory(e.target.value)}>{['Boshqa','Ijara','Kommunal','Transport','Ta’mirlash','Xo‘jalik'].map(x=><option key={x} value={x}>{t(x)}</option>)}</select></label>
        <label>{t('To‘lov turi')}<select className={field} value={payment} onChange={e=>setPayment(e.target.value)}><option value="cash">{t('Naqd')}</option><option value="card">{t('Karta')}</option><option value="bank">{t('Bank o‘tkazmasi')}</option></select></label>
        <label>{t('Izoh')}<input className={field} value={description} maxLength={256} onChange={e=>setDescription(e.target.value)} /></label>
      </div>
      <button disabled={saving} onClick={save} className="mt-4 rounded-xl bg-stone-900 px-5 py-2.5 font-semibold text-white disabled:opacity-50">{t('Saqlash')}</button>
      {error && <p className="mt-2 text-red-600">{error}</p>}
    </section>
    <section className="rounded-2xl border border-stone-200 bg-white p-5"><div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 className="font-bold">{t('Xarajatlar tarixi')}</h2><button className="rounded-lg border px-3 py-2 text-sm" onClick={() => exportExcel('coffeepos-xarajatlar',['Sana','Sabab','Summa','To‘lov','Xodim','Izoh'],items.map(x=>[new Date(x.createdAt).toLocaleString(),x.category,x.amount,x.payment,x.staff,x.description]))}>{t('Excelga eksport')}</button></div>
      <div className="space-y-2">{items.map(x=><div key={x.id} className="flex items-center justify-between gap-3 border-b py-2 text-sm"><div><b>{t(x.category)}</b><p className="text-stone-500">{new Date(x.createdAt).toLocaleString()} · {x.description || x.staff}</p></div><b>{fmt(x.amount)} {t("so'm")}</b></div>)}</div>
    </section>
  </div>
}

import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from './api'
import { fmt, som } from './data'
import { t } from './i18n'

export type Recurring = {
  id: number; name: string; amount: number; category: string; payment: 'cash' | 'card' | 'bank'
  day: number; active: boolean; lastPaidMonth: string; paidThisMonth: boolean; due: boolean
}
type Draft = { id?: number; name: string; amount: string; category: string; payment: Recurring['payment']; day: string; active: boolean }

const input = 'rounded-lg border border-stone-200 px-2.5 py-2 outline-none focus:border-amber-500'
const btn = 'rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-stone-300'
const PAY_LABEL = { cash: 'Naqd (kassadan)', card: 'Karta', bank: "Bank o'tkazmasi" } as const

/** Small banner for the dashboard: payments whose day has come this month. */
export function DueRecurringBanner({ onOpen }: { onOpen: () => void }) {
  const [due, setDue] = useState<Recurring[]>([])
  useEffect(() => { api<Recurring[]>('/api/recurring').then((l) => setDue(l.filter((r) => r.due))).catch(() => setDue([])) }, [])
  if (due.length === 0) return null
  return <button onClick={onOpen} className="flex w-full items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-left text-sm text-amber-900">
    <b>{t('{n} ta doimiy to‘lov muddati keldi:', { n: due.length })}</b> {due.map((r) => `${r.name} (${fmt(r.amount)})`).join(', ')}
  </button>
}

export default function RecurringPayments() {
  const [list, setList] = useState<Recurring[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => api<Recurring[]>('/api/recurring').then(setList).catch((e) => setError((e as Error).message))
  useEffect(() => { void load() }, [])

  const save = async () => {
    if (!draft) return
    setBusy(true); setError('')
    const body = { name: draft.name.trim(), amount: Number(draft.amount) || 0, category: draft.category.trim() || draft.name.trim(),
      payment: draft.payment, day: Math.max(1, Math.min(28, Number(draft.day) || 1)), active: draft.active }
    try { await api(draft.id ? `/api/recurring/${draft.id}` : '/api/recurring', { method: draft.id ? 'PUT' : 'POST', body }); setDraft(null); await load() }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const pay = async (r: Recurring) => {
    const raw = window.prompt(t('{name}: to‘langan summa', { name: r.name }), String(r.amount))
    if (raw === null) return
    const amount = Number(raw.replace(/\D/g, ''))
    if (!amount) return
    setError('')
    try { await api(`/api/recurring/${r.id}/pay`, { body: { amount } }); await load() } catch (e) { setError((e as Error).message) }
  }
  const remove = async (r: Recurring) => {
    if (!window.confirm(t('O‘chirilsinmi?') + ' ' + r.name)) return
    try { await api(`/api/recurring/${r.id}`, { method: 'DELETE' }); await load() } catch (e) { setError((e as Error).message) }
  }

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t("Doimiy to'lovlar")}</h2>
        <button className={`${btn} flex items-center gap-1`} onClick={() => setDraft({ name: '', amount: '', category: '', payment: 'bank', day: '1', active: true })}><Plus className="size-4" />{t("Qo'shish")}</button>
      </div>
      <p className="mb-4 text-sm text-stone-600">{t('Ijara, kommunal, internet kabi har oy takrorlanadigan to‘lovlar. «To‘landi» bosilganda xarajatlarga yoziladi; bir oyda ikki marta yozilmaydi.')}</p>
      {error && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      {list.length === 0 ? <p className="rounded-xl bg-stone-50 p-4 text-sm text-stone-500">{t("Hali doimiy to'lov yo'q.")}</p> :
        <div className="divide-y divide-stone-100 rounded-xl border border-stone-200">{list.map((r) => <div key={r.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm">
          <div className={`min-w-48 flex-1 ${r.active ? '' : 'opacity-50'}`}>
            <div className="font-medium">{r.name} · {som(r.amount)}</div>
            <div className="text-xs text-stone-500">{t('Har oy {d}-sanada', { d: r.day })} · {r.category} · {t(PAY_LABEL[r.payment])}</div>
          </div>
          {r.paidThisMonth ? <span className="rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800">{t("Bu oy to'langan")}</span>
            : r.active && <button onClick={() => void pay(r)} className={`rounded-lg px-3 py-1.5 text-xs font-semibold text-white ${r.due ? 'bg-red-600' : 'bg-amber-600'}`}>{t("To'landi")}</button>}
          <button aria-label={t('Tahrirlash')} className="rounded-lg p-2 hover:bg-stone-100" onClick={() => setDraft({ id: r.id, name: r.name, amount: String(r.amount), category: r.category, payment: r.payment, day: String(r.day), active: r.active })}><Pencil className="size-4" /></button>
          <button aria-label={t("O'chirish")} className="rounded-lg p-2 text-stone-400 hover:text-red-600" onClick={() => void remove(r)}><Trash2 className="size-4" /></button>
        </div>)}</div>}
      {draft && <div className="mt-5 space-y-3 rounded-xl border border-amber-300 bg-amber-50/40 p-4 text-sm">
        <div className="flex flex-wrap gap-2">
          <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder={t('Nomi (masalan Ijara)')} className={`${input} min-w-48 flex-1`} />
          <input value={draft.amount} onChange={(e) => setDraft({ ...draft, amount: e.target.value.replace(/\D/g, '') })} placeholder={t('Summa')} inputMode="numeric" className={`${input} w-36`} />
          <input value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })} placeholder={t('Xarajat kategoriyasi')} className={`${input} w-44`} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5">{t('Har oy')} <input value={draft.day} onChange={(e) => setDraft({ ...draft, day: e.target.value.replace(/\D/g, '').slice(0, 2) })} inputMode="numeric" className={`${input} w-16 text-center`} /> {t('-sanada (1–28)')}</label>
          <select value={draft.payment} onChange={(e) => setDraft({ ...draft, payment: e.target.value as Recurring['payment'] })} className={input}>
            {(Object.keys(PAY_LABEL) as Recurring['payment'][]).map((k) => <option key={k} value={k}>{t(PAY_LABEL[k])}</option>)}
          </select>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={draft.active} onChange={(e) => setDraft({ ...draft, active: e.target.checked })} />{t('Faol')}</label>
        </div>
        <div className="flex gap-2">
          <button disabled={busy || !draft.name.trim() || !Number(draft.amount)} onClick={() => void save()} className={btn}>{t('Saqlash')}</button>
          <button onClick={() => setDraft(null)} className="rounded-lg border px-3 py-2">{t('Bekor qilish')}</button>
        </div>
      </div>}
    </section>
  )
}

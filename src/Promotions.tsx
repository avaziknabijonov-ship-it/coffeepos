import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from './api'
import { CATEGORIES, PRODUCTS } from './data'
import type { Promotion } from './data'
import { t, tCatalogName } from './i18n'
import { refreshMenu } from './store'

const input = 'rounded-lg border border-stone-200 px-2.5 py-2 outline-none focus:border-amber-500'
const btn = 'rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-stone-300'
export const WEEKDAYS = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']

type Draft = Omit<Promotion, 'id'> & { id?: number }
const empty = (): Draft => ({ name: '', pct: 10, target: 'all', keys: [], days: [], startTime: '00:00', endTime: '00:00', dateFrom: '', dateTo: '', active: true })

function describe(p: Promotion): string {
  const parts: string[] = []
  if (p.target === 'all') parts.push(t('Butun menyu'))
  else if (p.target === 'category') parts.push(p.keys.map((k) => tCatalogName(CATEGORIES.find((c) => c.id === k)?.name ?? k)).join(', '))
  else parts.push(p.keys.map((k) => tCatalogName(PRODUCTS.find((x) => x.id === k)?.name ?? k)).join(', '))
  parts.push(p.days.length ? p.days.map((d) => t(WEEKDAYS[d])).join(' ') : t('Har kuni'))
  parts.push(p.startTime === p.endTime ? t('Kun bo‘yi') : `${p.startTime}–${p.endTime}`)
  if (p.dateFrom || p.dateTo) parts.push(`${p.dateFrom || '…'} — ${p.dateTo || '…'}`)
  return parts.join(' · ')
}

export default function Promotions() {
  const [list, setList] = useState<Promotion[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => api<Promotion[]>('/api/promotions').then(setList).catch((e) => setError((e as Error).message))
  useEffect(() => { void load() }, [])

  const save = async () => {
    if (!draft) return
    setBusy(true); setError('')
    const { id, ...body } = draft
    try {
      await api(id ? `/api/promotions/${id}` : '/api/promotions', { method: id ? 'PUT' : 'POST', body })
      setDraft(null)
      await Promise.all([load(), refreshMenu()])
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const toggle = async (p: Promotion) => {
    try { const { id, ...body } = p; await api(`/api/promotions/${id}`, { method: 'PUT', body: { ...body, active: !p.active } }); await Promise.all([load(), refreshMenu()]) }
    catch (e) { setError((e as Error).message) }
  }
  const remove = async (p: Promotion) => {
    if (!window.confirm(t('Aksiya o‘chirilsinmi?') + ' ' + p.name)) return
    try { await api(`/api/promotions/${p.id}`, { method: 'DELETE' }); await Promise.all([load(), refreshMenu()]) }
    catch (e) { setError((e as Error).message) }
  }
  const toggleKey = (k: string) => draft && setDraft({ ...draft, keys: draft.keys.includes(k) ? draft.keys.filter((x) => x !== k) : [...draft.keys, k] })
  const toggleDay = (d: number) => draft && setDraft({ ...draft, days: draft.days.includes(d) ? draft.days.filter((x) => x !== d) : [...draft.days, d].sort() })

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('Aksiyalar')}</h2>
        <button className={`${btn} flex items-center gap-1`} onClick={() => { setError(''); setDraft(empty()) }}><Plus className="size-4" />{t('Yangi aksiya')}</button>
      </div>
      <p className="mb-4 text-sm text-stone-600">{t('Aksiya kassada avtomatik qo‘llanadi. Bir mahsulotga bir nechta aksiya to‘g‘ri kelsa, eng kattasi olinadi. Qo‘lda chegirma qolgan summaga qo‘shiladi.')}</p>
      {error && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      {list.length === 0 ? <p className="rounded-xl bg-stone-50 p-4 text-sm text-stone-500">{t('Hali aksiya yo‘q.')}</p> :
        <div className="divide-y divide-stone-100 rounded-xl border border-stone-200">
          {list.map((p) => <div key={p.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
            <span className="rounded-lg bg-emerald-100 px-2 py-1 text-sm font-bold text-emerald-800">−{p.pct}%</span>
            <div className={`min-w-48 flex-1 ${p.active ? '' : 'opacity-50'}`}>
              <div className="font-medium">{p.name}</div>
              <div className="text-xs text-stone-500">{describe(p)}</div>
            </div>
            <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" className="size-4" checked={p.active} onChange={() => void toggle(p)} />{t('Faol')}</label>
            <button aria-label={t('Tahrirlash')} className="rounded-lg p-2 hover:bg-stone-100" onClick={() => { setError(''); setDraft({ ...p }) }}><Pencil className="size-4" /></button>
            <button aria-label={t("O'chirish")} className="rounded-lg p-2 text-stone-400 hover:text-red-600" onClick={() => void remove(p)}><Trash2 className="size-4" /></button>
          </div>)}
        </div>}

      {draft && <div className="mt-5 space-y-4 rounded-xl border border-amber-300 bg-amber-50/40 p-4 text-sm">
        <div className="flex flex-wrap gap-2">
          <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder={t('Aksiya nomi (masalan Happy hour)')} className={`${input} min-w-56 flex-1`} />
          <label className="flex items-center gap-1">−<input value={draft.pct} onChange={(e) => setDraft({ ...draft, pct: Math.max(0, Math.min(90, Number(e.target.value.replace(/\D/g, '')) || 0)) })} inputMode="numeric" className={`${input} w-20 text-center`} />%</label>
        </div>
        <div className="space-y-2">
          <div className="font-semibold">{t('Nimaga')}</div>
          <div className="flex flex-wrap gap-2">
            {(['all', 'category', 'product'] as const).map((k) => <button key={k} type="button" onClick={() => setDraft({ ...draft, target: k, keys: [] })}
              className={`rounded-lg border px-3 py-1.5 ${draft.target === k ? 'border-amber-600 bg-amber-100 font-semibold' : 'border-stone-200 bg-white'}`}>
              {t(k === 'all' ? 'Butun menyu' : k === 'category' ? 'Kategoriyalar' : 'Mahsulotlar')}</button>)}
          </div>
          {draft.target !== 'all' && <div className="flex max-h-48 flex-wrap gap-2 overflow-y-auto rounded-lg border border-stone-200 bg-white p-2">
            {((draft.target === 'category' ? CATEGORIES : PRODUCTS) as { id: string; name: string }[]).map((x) => <label key={x.id} className="flex items-center gap-1.5 rounded-lg bg-stone-50 px-2 py-1">
              <input type="checkbox" checked={draft.keys.includes(x.id)} onChange={() => toggleKey(x.id)} />{tCatalogName(x.name)}</label>)}
          </div>}
        </div>
        <div className="space-y-2">
          <div className="font-semibold">{t('Qachon')}</div>
          <div className="flex flex-wrap gap-1.5">
            {WEEKDAYS.map((d, i) => <button key={d} type="button" onClick={() => toggleDay(i)}
              className={`w-10 rounded-lg border py-1.5 ${draft.days.includes(i) ? 'border-amber-600 bg-amber-100 font-semibold' : 'border-stone-200 bg-white'}`}>{t(d)}</button>)}
            <span className="self-center pl-2 text-xs text-stone-500">{t('Hech biri tanlanmasa — har kuni')}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input type="time" value={draft.startTime} onChange={(e) => setDraft({ ...draft, startTime: e.target.value || '00:00' })} className={input} />
            —
            <input type="time" value={draft.endTime} onChange={(e) => setDraft({ ...draft, endTime: e.target.value || '00:00' })} className={input} />
            <span className="text-xs text-stone-500">{t('Bir xil vaqt — kun bo‘yi')}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input type="date" value={draft.dateFrom} onChange={(e) => setDraft({ ...draft, dateFrom: e.target.value })} className={input} />
            —
            <input type="date" value={draft.dateTo} onChange={(e) => setDraft({ ...draft, dateTo: e.target.value })} className={input} />
            <span className="text-xs text-stone-500">{t('Ixtiyoriy')}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button disabled={busy || !draft.name.trim() || draft.pct < 1 || (draft.target !== 'all' && draft.keys.length === 0)} onClick={() => void save()} className={btn}>{t('Saqlash')}</button>
          <button onClick={() => setDraft(null)} className="rounded-lg border px-3 py-2">{t('Bekor qilish')}</button>
        </div>
      </div>}
    </section>
  )
}

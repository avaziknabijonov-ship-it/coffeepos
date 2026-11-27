import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from './api'
import { CATEGORIES, WORKSHOPS } from './data'
import type { HallInfo } from './data'
import { t, tCatalogName } from './i18n'
import { refreshMenu, useAppState } from './store'

const input = 'rounded-lg border border-stone-200 px-2.5 py-2 outline-none focus:border-amber-500'
const btn = 'rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-stone-300'

export default function RestaurantSettings() {
  useAppState()
  const [halls, setHalls] = useState<HallInfo[]>([])
  const [error, setError] = useState('')
  const [wsName, setWsName] = useState('')
  const [hallName, setHallName] = useState('')
  const [newTable, setNewTable] = useState<Record<number, { name: string; seats: string }>>({})
  const loadHalls = () => api<HallInfo[]>('/api/halls').then(setHalls).catch((e) => setError((e as Error).message))
  useEffect(() => { void loadHalls() }, [])

  const run = async (fn: () => Promise<unknown>, reloadHalls = false) => {
    setError('')
    try { await fn(); await refreshMenu(); if (reloadHalls) await loadHalls(); return true }
    catch (e) { setError((e as Error).message); return false }
  }
  const rename = (path: string, current: string, reloadHalls = false) => {
    const name = window.prompt(t('Yangi nom'), current)
    if (name && name.trim() && name.trim() !== current) void run(() => api(path, { method: 'PUT', body: { name: name.trim() } }), reloadHalls)
  }

  return (
    <div className="space-y-5">
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
        <h2 className="mb-2 text-lg font-semibold">{t('Sexlar')}</h2>
        <p className="mb-4 text-sm text-stone-600">{t('Sex — taom tayyorlanadigan joy (bar, oshxona, qandolat). Har bir kategoriya sexga biriktiriladi; oshxona ekranida sex bo‘yicha filtr chiqadi. Biriktirilmagan kategoriyalar «Bar (asosiy)» ga boradi.')}</p>
        <div className="mb-4 flex flex-wrap gap-2">
          {WORKSHOPS.map((w) => <span key={w.id} className="flex items-center gap-1 rounded-lg bg-stone-100 px-3 py-1.5 text-sm">
            {w.name}
            <button aria-label={t('Nomini o‘zgartirish')} onClick={() => rename(`/api/workshops/${encodeURIComponent(w.id)}`, w.name)} className="p-1 text-stone-500 hover:text-stone-900"><Pencil className="size-3.5" /></button>
            <button aria-label={t("O'chirish")} onClick={() => window.confirm(t('Sex o‘chirilsinmi?') + ' ' + w.name) && void run(() => api(`/api/workshops/${encodeURIComponent(w.id)}`, { method: 'DELETE' }))} className="p-1 text-stone-400 hover:text-red-600"><Trash2 className="size-3.5" /></button>
          </span>)}
        </div>
        <form className="mb-5 flex gap-2" onSubmit={(e) => { e.preventDefault(); void run(() => api('/api/workshops', { body: { name: wsName.trim() } })).then((ok) => ok && setWsName('')) }}>
          <input required value={wsName} onChange={(e) => setWsName(e.target.value)} placeholder={t('Yangi sex nomi (masalan Oshxona)')} className={`${input} flex-1`} />
          <button className={btn}>{t("Qo'shish")}</button>
        </form>
        {WORKSHOPS.length > 0 && <div className="grid gap-2 sm:grid-cols-2">
          {CATEGORIES.map((c) => <label key={c.id} className="flex items-center justify-between gap-2 rounded-lg border border-stone-200 px-3 py-2 text-sm">
            <span className="font-medium">{tCatalogName(c.name)}</span>
            <select value={c.workshop ?? ''} onChange={(e) => void run(() => api(`/api/categories/${encodeURIComponent(c.id)}/workshop`, { method: 'PATCH', body: { workshop: e.target.value } }))} className={input}>
              <option value="">{t('Bar (asosiy)')}</option>
              {WORKSHOPS.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </label>)}
        </div>}
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
        <h2 className="mb-2 text-lg font-semibold">{t('Zal va stollar')}</h2>
        <p className="mb-4 text-sm text-stone-600">{t('Kamida bitta stol qo‘shilsa, kassir va ofitsiantlarda «Zal» oynasi paydo bo‘ladi: stolga hisob ochish, taomni oshxonaga yuborish va keyin to‘lov.')}</p>
        <div className="space-y-4">
          {halls.map((h) => {
            const draft = newTable[h.id] ?? { name: '', seats: '4' }
            return <div key={h.id} className="rounded-xl border border-stone-200 p-3">
              <div className="mb-2 flex items-center gap-2">
                <b className="flex-1">{h.name}</b>
                <button aria-label={t('Nomini o‘zgartirish')} onClick={() => rename(`/api/halls/${h.id}`, h.name, true)} className="rounded-lg p-1.5 hover:bg-stone-100"><Pencil className="size-4" /></button>
                {h.tables.length === 0 && <button aria-label={t("O'chirish")} onClick={() => void run(() => api(`/api/halls/${h.id}`, { method: 'DELETE' }), true)} className="rounded-lg p-1.5 text-stone-400 hover:text-red-600"><Trash2 className="size-4" /></button>}
              </div>
              <div className="mb-3 flex flex-wrap gap-2">
                {h.tables.map((tb) => <span key={tb.id} className={`flex items-center gap-1 rounded-lg border px-2 py-1 text-sm ${tb.active ? 'border-stone-200' : 'border-dashed border-stone-300 opacity-50'}`}>
                  <b>{tb.name}</b><span className="text-xs text-stone-500">· {tb.seats} {t('o‘rin')}</span>
                  <button aria-label={t('Tahrirlash')} className="p-1 text-stone-500" onClick={() => {
                    const name = window.prompt(t('Stol nomi'), tb.name)
                    if (!name || !name.trim()) return
                    const seats = Number(window.prompt(t('O‘rinlar soni'), String(tb.seats)) || tb.seats)
                    void run(() => api(`/api/tables/${tb.id}`, { method: 'PUT', body: { hallId: h.id, name: name.trim(), seats: Math.max(1, Math.min(100, seats || 1)), active: tb.active } }), true)
                  }}><Pencil className="size-3.5" /></button>
                  <button aria-label={t("O'chirish")} className="p-1 text-stone-400 hover:text-red-600" onClick={() => void run(() => api(`/api/tables/${tb.id}`, { method: 'DELETE' }), true)}><Trash2 className="size-3.5" /></button>
                </span>)}
              </div>
              <form className="flex flex-wrap gap-2" onSubmit={(e) => {
                e.preventDefault()
                void run(() => api('/api/tables', { body: { hallId: h.id, name: draft.name.trim(), seats: Math.max(1, Math.min(100, Number(draft.seats) || 1)) } }), true)
                  .then((ok) => ok && setNewTable({ ...newTable, [h.id]: { name: '', seats: draft.seats } }))
              }}>
                <input required value={draft.name} onChange={(e) => setNewTable({ ...newTable, [h.id]: { ...draft, name: e.target.value } })} placeholder={t('Stol nomi yoki raqami')} className={`${input} w-40`} />
                <input value={draft.seats} onChange={(e) => setNewTable({ ...newTable, [h.id]: { ...draft, seats: e.target.value.replace(/\D/g, '') } })} inputMode="numeric" className={`${input} w-20`} aria-label={t('O‘rinlar soni')} />
                <button className={`${btn} flex items-center gap-1`}><Plus className="size-4" />{t('Stol')}</button>
              </form>
            </div>
          })}
        </div>
        <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); void run(() => api('/api/halls', { body: { name: hallName.trim() } }), true).then((ok) => ok && setHallName('')) }}>
          <input required value={hallName} onChange={(e) => setHallName(e.target.value)} placeholder={t('Yangi zal nomi (masalan Asosiy zal, Terrasa)')} className={`${input} flex-1`} />
          <button className={btn}>{t("Zal qo'shish")}</button>
        </form>
      </section>
    </div>
  )
}

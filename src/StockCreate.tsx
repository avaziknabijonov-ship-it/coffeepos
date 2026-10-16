import { useState } from 'react'
import { api } from './api'
import { t } from './i18n'
import { refreshMenu, sync } from './store'
import type { Unit } from './data'

const field = 'w-full rounded-xl border border-stone-200 px-3 py-2.5'
export default function StockCreate({ mode, categories, selected, onClose, onSaved }: {
  mode: 'category' | 'ingredient'; categories: string[]; selected: string; onClose: () => void; onSaved: (category: string) => void
}) {
  const [name, setName] = useState('')
  const [category, setCategory] = useState(selected || categories[0] || 'Boshqa')
  const [unit, setUnit] = useState<Unit>('g')
  const [cost, setCost] = useState('')
  const [stock, setStock] = useState('')
  const [minimum, setMinimum] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const save = async (e: React.FormEvent) => {
    e.preventDefault(); if (busy) return
    const clean = name.trim()
    if (!clean) { setError(t('Nomini kiriting')); return }
    if (mode === 'category' && categories.some(c => c.toLowerCase() === clean.toLowerCase())) { setError(t('Kategoriya allaqachon mavjud')); return }
    setBusy(true); setError('')
    try {
      if (mode === 'category') await api('/api/stock-categories', { body: { name: clean } })
      else await api('/api/ingredients', { body: { name: clean, category, unit, cost: Number(cost), min: Number(minimum), initialStock: Number(stock) } })
      await refreshMenu(); await sync(); onSaved(mode === 'category' ? clean : category)
    } catch (e) { setError((e as Error).message); setBusy(false) }
  }
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <form role="dialog" aria-modal="true" aria-label={t(mode === 'category' ? "Yangi bo'lim" : 'Yangi ombor mahsuloti')} onSubmit={e => void save(e)} className="max-h-[90dvh] w-full max-w-lg space-y-4 overflow-auto rounded-2xl bg-white p-6">
      <h2 className="text-xl font-bold">{t(mode === 'category' ? "Yangi bo'lim" : 'Yangi ombor mahsuloti')}</h2>
      <label className="block space-y-1"><span>{t('Nomi')}</span><input autoFocus disabled={busy} required maxLength={mode === 'category' ? 64 : 128} value={name} onChange={e => setName(e.target.value)} className={field} /></label>
      {mode === 'ingredient' && <>
        <label className="block space-y-1"><span>{t('Kategoriya')}</span><select disabled={busy} value={category} onChange={e => setCategory(e.target.value)} className={field}>{categories.map(c => <option key={c} value={c}>{t(c)}</option>)}</select></label>
        <label className="block space-y-1"><span>{t('Birlik')}</span><select disabled={busy} value={unit} onChange={e => setUnit(e.target.value as Unit)} className={field}>{(['g', 'ml', 'dona'] as const).map(u => <option key={u} value={u}>{t(u)}</option>)}</select></label>
        {[
          { label: '1 birlik narxi', value: cost, set: setCost },
          { label: "Boshlang'ich qoldiq", value: stock, set: setStock },
          { label: 'Min qoldiq', value: minimum, set: setMinimum },
        ].map(f => <label key={f.label} className="block space-y-1"><span>{t(f.label)} ({t(unit)})</span><input disabled={busy} required type="number" min="0" step="any" value={f.value} onChange={e => f.set(e.target.value)} className={field} /></label>)}
        <p className="text-xs text-stone-500">{t("Narx 1 g, 1 ml yoki 1 dona uchun yoziladi. Masalan: 1 kg kofe 260 000 so'm bo'lsa, 1 g = 260.")}</p>
      </>}
      {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
      <div className="flex gap-2"><button type="button" disabled={busy} onClick={onClose} className="flex-1 rounded-xl border p-3">{t('Bekor')}</button><button disabled={busy} className="flex-1 rounded-xl bg-amber-600 p-3 font-semibold text-white disabled:opacity-50">{t(busy ? 'Saqlanmoqda…' : 'Saqlash')}</button></div>
    </form>
  </div>
}

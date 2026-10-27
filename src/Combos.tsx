import { useEffect, useState } from 'react'
import { api } from './api'
import { t, tCatalogName } from './i18n'
import { CATEGORIES, PRODUCTS, som } from './data'
import { refreshMenu, useAppState } from './store'

type Component = { productId: string; size: string; qty: number }
type Combo = { id: string; name: string; cat: string; active: boolean; sizes: { price: number }[]; comboComponents: Component[] }
export default function Combos() {
  const { menuVersion } = useAppState()
  void menuVersion
  const [list, setList] = useState<Combo[]>([])
  const [editing, setEditing] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [cat, setCat] = useState(CATEGORIES[0]?.id ?? '')
  const [price, setPrice] = useState(0)
  const [components, setComponents] = useState<Component[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const products = PRODUCTS.filter(p => !p.comboComponents?.length)
  useEffect(() => { let active = true; api<Combo[]>('/api/combos').then(r => { if (active) setList(r) }).catch(e => { if (active) setError(e.message) }); return () => { active = false } }, [])
  const reset = () => { setEditing(null); setName(''); setPrice(0); setComponents([]) }
  const save = async () => {
    setBusy(true); setError('')
    try {
      const existing = list.find(c => c.id === editing)
      await api('/api/combos' + (editing ? '/' + editing : ''), { method: editing ? 'PUT' : 'POST', body: { name, cat, price, components, active: existing?.active ?? true } })
      await refreshMenu(); setList(await api<Combo[]>('/api/combos')); reset()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  const toggle = async (combo: Combo) => {
    setBusy(true); setError('')
    try { await api('/api/products/' + combo.id + '/active', { method: 'PATCH', body: { active: !combo.active } }); await refreshMenu(); setList(await api<Combo[]>('/api/combos')) }
    catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  const change = (index: number, patch: Partial<Component>) => setComponents(prev => prev.map((c, i) => i === index ? { ...c, ...patch } : c))
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <h2 className="text-xl font-semibold">{t('Combo mahsulotlar')}</h2>
    <p className="text-sm text-stone-600">{t('Tarkib oddiy mahsulotlardan tuziladi. Qo‘shimcha modifikator va ichma-ich combo yo‘q. Ombor sarfi bir marta yoziladi.')}</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <form className="space-y-3" onSubmit={e => { e.preventDefault(); void save() }}>
      <div className="flex flex-wrap gap-3"><label>{t('Nomi')}<input className="block rounded border p-2" required maxLength={128} value={name} onChange={e => setName(e.target.value)} /></label><label>{t('Kategoriya')}<select className="block rounded border p-2" value={cat} onChange={e => setCat(e.target.value)}>{CATEGORIES.map(c => <option key={c.id} value={c.id}>{t(c.name)}</option>)}</select></label><label>{t('Narx')}<input className="block rounded border p-2" required type="number" min="0" step="1" value={price} onChange={e => setPrice(Number(e.target.value))} /></label></div>
      {components.map((c, index) => <div key={index} className="flex flex-wrap gap-2">
        <select aria-label={t('Mahsulot')} className="rounded border p-2" value={c.productId} onChange={e => change(index, { productId: e.target.value, size: products.find(p => p.id === e.target.value)?.sizes[0]?.code ?? '-' })}>{products.map(p => <option key={p.id} value={p.id}>{tCatalogName(p.name)}</option>)}</select>
        <select aria-label={t('O‘lcham')} className="rounded border p-2" value={c.size} onChange={e => change(index, { size: e.target.value })}>{products.find(p => p.id === c.productId)?.sizes.map(s => <option key={s.code} value={s.code}>{s.label}</option>)}</select>
        <input aria-label={t('Miqdor')} className="w-20 rounded border p-2" type="number" min="1" max="10" step="1" required value={c.qty} onChange={e => change(index, { qty: Number(e.target.value) })} />
        <button type="button" className="rounded border p-2" onClick={() => setComponents(prev => prev.filter((_, i) => i !== index))}>{t('Olib tashlash')}</button>
      </div>)}
      <div className="flex gap-2"><button type="button" className="rounded border px-3 py-2" disabled={components.length >= 10 || !products.length} onClick={() => setComponents(prev => [...prev, { productId: products[0].id, size: products[0].sizes[0].code, qty: 1 }])}>{t('Tarkib qo‘shish')}</button><button disabled={busy || components.length < 2} className="rounded bg-stone-800 px-3 py-2 text-white disabled:opacity-50">{t('Saqlash')}</button>{editing && <button type="button" onClick={reset} className="rounded border px-3 py-2">{t('Bekor qilish')}</button>}</div>
    </form>
    {list.map(c => <div key={c.id} className="flex flex-wrap items-center justify-between gap-3 rounded border p-3"><span>{c.name} · {som(c.sizes[0]?.price ?? 0)} · {c.comboComponents.length}</span><div className="flex gap-2"><button className="rounded border p-2" disabled={busy} onClick={() => { setEditing(c.id); setName(c.name); setCat(c.cat); setPrice(c.sizes[0]?.price ?? 0); setComponents(c.comboComponents.map(part => ({ ...part }))) }}>{t('Tahrirlash')}</button><button className="rounded border p-2" disabled={busy} onClick={() => void toggle(c)}>{c.active ? t('Faol') : t('Nofaol')}</button></div></div>)}
  </section>
}

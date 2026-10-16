import { useState } from 'react'
import { t } from './i18n'
import { som } from './data'

import type { Draft, Table } from './floorState'

export default function FloorMap({ tables, drafts, onSelect, onTables, canEdit }: {
  tables: Table[]; drafts: Record<string, Draft>; onSelect: (id: string) => void; onTables: (tables: Table[]) => void; canEdit: boolean
}) {
  const [zone, setZone] = useState('')
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [newZone, setNewZone] = useState('Zal')
  const [shape, setShape] = useState<Table['shape']>('round')
  const zones = [...new Set(tables.map(x => x.zone))]
  const activeZone = zones.includes(zone) ? zone : zones[0]
  return <div className="h-full overflow-auto bg-stone-100 p-3 sm:p-4">
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <h1 className="mr-auto text-lg font-bold sm:text-xl">{t('Zal xaritasi')}</h1>
      <span className="text-sm text-stone-500">{t('Band stollar')}: {tables.filter(x => drafts[x.id]?.cart.length).length} / {tables.length}</span>
      {canEdit && <button className="min-h-11 rounded-xl border bg-white px-3 py-2 text-sm" onClick={() => setEditing(!editing)}>{t('Tahrirlash')}</button>}
      <button className="min-h-11 rounded-xl bg-amber-600 px-3 py-2 text-sm font-semibold text-white" onClick={() => onSelect('takeaway')}>{t('Olib ketish')}</button>
    </div>
    <div className="mb-4 flex flex-wrap gap-2">{zones.map(z => <button key={z} onClick={() => setZone(z)} className={`min-h-11 rounded-xl px-4 py-2 text-sm ${z === activeZone ? 'bg-stone-900 text-white' : 'bg-white'}`}>{t(z)}</button>)}</div>
    {editing && <form className="mb-6 flex flex-wrap gap-2 rounded-2xl bg-white p-4" onSubmit={e => {
      e.preventDefault(); if (!name.trim() || !newZone.trim()) return
      onTables([...tables, { id: crypto.randomUUID(), name: name.trim(), zone: newZone.trim(), shape }]); setZone(newZone.trim()); setName('')
    }}>
      <input aria-label={t('Stol nomi')} placeholder={t('Stol nomi')} required maxLength={30} value={name} onChange={e => setName(e.target.value)} className="rounded-lg border p-3" />
      <input aria-label={t('Zal nomi')} placeholder={t('Zal nomi')} required maxLength={30} value={newZone} onChange={e => setNewZone(e.target.value)} className="rounded-lg border p-3" />
      <select aria-label={t('Shakl')} value={shape} onChange={e => setShape(e.target.value as Table['shape'])} className="rounded-lg border p-3">
        <option value="round">{t('Dumaloq')}</option><option value="square">{t('Kvadrat')}</option><option value="long">{t('Uzun')}</option>
      </select><button className="rounded-lg bg-amber-600 px-4 text-white">{t("Qo'shish")}</button>
    </form>}
    <div className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-x-2 gap-y-4 sm:grid-cols-[repeat(auto-fill,minmax(108px,1fr))]">{tables.filter(x => x.zone === activeZone).map(table => {
      const draft = drafts[table.id]; const busy = !!draft?.cart.length
      const subtotal = draft?.cart.reduce((s, i) => s + i.unitPrice * i.qty, 0) || 0
      const total = subtotal - Math.round(subtotal * (draft?.discountPct || 0) / 100 / 100) * 100
      return <div key={table.id} className="flex min-w-0 flex-col items-center gap-1.5">
        <button onClick={() => onSelect(table.id)} aria-label={`${t('Stol')} ${table.name}, ${t(busy ? 'Band' : "Bo'sh")}`} className={`flex h-24 w-24 shrink-0 touch-manipulation flex-col items-center justify-center gap-0.5 p-2 shadow-sm sm:h-26 sm:w-26 ${table.shape === 'round' ? 'rounded-full' : table.shape === 'long' ? 'rounded-[2rem]' : 'rounded-xl'} ${busy ? 'bg-sky-600 text-white' : 'bg-stone-800 text-white hover:bg-stone-700'}`}>
          <span className="max-w-full truncate px-1 text-xl font-bold" title={table.name}>{table.name}</span><span className="text-[11px] opacity-80">{t(busy ? 'Band' : "Bo'sh")}</span>
          {busy && <strong className="text-[11px] leading-tight">{som(total)}</strong>}
        </button>
        {busy && draft.customer && <span className="w-full truncate text-center text-xs text-stone-500" title={draft.customer}>{draft.customer}</span>}
        {editing && <button disabled={busy} className="min-h-11 px-2 text-xs text-red-600 disabled:opacity-30" onClick={() => { if (confirm(t('Stol o‘chirilsinmi?'))) onTables(tables.filter(x => x.id !== table.id)) }}>{t("O'chirish")}</button>}
      </div>
    })}</div>
    <p className="mt-5 text-xs text-stone-500">{t('Stolni bosing va buyurtma kiriting. Savatlar shu qurilmada saqlanadi.')}</p>
  </div>
}

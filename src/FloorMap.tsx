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
  return <div className="h-full overflow-auto bg-stone-100 p-4 sm:p-7">
    <div className="mb-6 flex flex-wrap items-center gap-3">
      <h1 className="mr-auto text-2xl font-bold">{t('Zal xaritasi')}</h1>
      <span className="text-sm text-stone-500">{t('Band stollar')}: {tables.filter(x => drafts[x.id]?.cart.length).length} / {tables.length}</span>
      {canEdit && <button className="rounded-xl border bg-white px-4 py-3" onClick={() => setEditing(!editing)}>{t('Tahrirlash')}</button>}
      <button className="rounded-xl bg-amber-600 px-5 py-3 font-semibold text-white" onClick={() => onSelect('takeaway')}>{t('Olib ketish')}</button>
    </div>
    <div className="mb-6 flex gap-2">{zones.map(z => <button key={z} onClick={() => setZone(z)} className={`rounded-xl px-5 py-3 ${z === activeZone ? 'bg-stone-900 text-white' : 'bg-white'}`}>{t(z)}</button>)}</div>
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
    <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-5">{tables.filter(x => x.zone === activeZone).map(table => {
      const draft = drafts[table.id]; const busy = !!draft?.cart.length
      const subtotal = draft?.cart.reduce((s, i) => s + i.unitPrice * i.qty, 0) || 0
      const total = subtotal - Math.round(subtotal * (draft?.discountPct || 0) / 100 / 100) * 100
      return <div key={table.id} className="flex flex-col items-center gap-2">
        <button onClick={() => onSelect(table.id)} aria-label={`${t('Stol')} ${table.name}, ${t(busy ? 'Band' : "Bo'sh")}`} className={`flex min-h-36 w-full max-w-48 flex-col items-center justify-center gap-1 p-4 shadow-sm ${table.shape === 'round' ? 'rounded-full' : table.shape === 'long' ? 'rounded-[3rem]' : 'rounded-2xl'} ${busy ? 'bg-sky-600 text-white' : 'bg-stone-800 text-white hover:bg-stone-700'}`}>
          <span className="text-3xl font-bold">{table.name}</span><span className="text-xs opacity-80">{t(busy ? 'Band' : "Bo'sh")}</span>
          {busy && <><span className="max-w-full truncate text-sm">{draft.customer}</span><strong>{som(total)}</strong></>}
        </button>
        {editing && <button disabled={busy} className="text-sm text-red-600 disabled:opacity-30" onClick={() => { if (confirm(t('Stol o‘chirilsinmi?'))) onTables(tables.filter(x => x.id !== table.id)) }}>{t("O'chirish")}</button>}
      </div>
    })}</div>
    <p className="mt-8 text-sm text-stone-500">{t('Stolni bosing va buyurtma kiriting. Savatlar shu qurilmada saqlanadi.')}</p>
  </div>
}

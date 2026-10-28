import { t } from './i18n'

import { defaultLayout } from './floorLayout'
import type { MapTable } from './floorLayout'

export default function FloorMap({ tables, onSelect, selected }: { tables: MapTable[]; onSelect: (table: MapTable) => void; selected?: number }) {
  const height = Math.max(600, ...tables.map((table, index) => { const layout = table.layout ?? defaultLayout(table, index); return layout.y + layout.height + 20 }))
  return <div className="overflow-auto rounded-xl border border-slate-200 bg-white"><div className="relative min-w-[700px]" style={{ width: 1000, height }}>
    {tables.map((table, index) => {
      const layout = table.layout ?? defaultLayout(table, index)
      return <button key={table.id} aria-label={`${table.name} · ${table.occupied ? t('Band') : t('Bo‘sh')}`} onClick={() => onSelect(table)} className={`absolute flex flex-col items-center justify-center overflow-hidden border-2 px-2 text-center text-white shadow-sm transition-colors ${table.occupied ? 'border-sky-600 bg-sky-600 hover:bg-sky-700' : 'border-slate-500 bg-slate-500 hover:bg-slate-600'} ${selected === table.id ? 'ring-4 ring-amber-400 ring-offset-2' : ''}`} style={{ left: layout.x, top: layout.y, width: layout.width, height: layout.height, borderRadius: layout.shape === 'vip' ? 999 : layout.shape === 'round' ? '45%' : layout.shape === 'bar' ? 8 : 10 }}>
        <strong className="max-w-full break-words text-xl leading-tight">{table.name}</strong><span className="mt-1 text-xs">{table.occupied ? t('Band') : t('Bo‘sh')}</span>{table.drafts[0]?.staff && <span className="mt-1 max-w-full truncate text-xs">{table.drafts[0].staff}</span>}
      </button>
    })}
  </div></div>
}

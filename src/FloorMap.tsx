import { t } from './i18n'

export type TableLayout = { x: number; y: number; width: number; height: number; shape: 'round' | 'rectangle' | 'bar' | 'vip' }
export type MapTable = { id: number; name: string; occupied: boolean; layout?: TableLayout | null; layoutVersion?: number; drafts: { staff: string }[] }
export function defaultLayout(table: MapTable, index: number): TableLayout {
  const name = table.name.toLowerCase().trim()
  if (['bar', 'бар'].includes(name)) return { x: 20, y: 60, width: 90, height: 460, shape: 'bar' }
  if (name.includes('vip')) return { x: 890, y: 160, width: 90, height: 300, shape: 'vip' }
  const n = Number(name)
  if (n >= 1 && n <= 4) return { x: 180 + (n - 1) * 175, y: 65, width: 110, height: 130, shape: 'round' }
  if (n >= 5 && n <= 9) return { x: 150 + (9 - n) * 145, y: 430, width: 105, height: 90, shape: 'round' }
  if (n >= 10 && n <= 14) return { x: 150 + (n - 10) * 145, y: 280, width: 100, height: 80, shape: 'rectangle' }
  return { x: 140 + (index % 5) * 145, y: 50 + Math.floor(index / 5) * 160, width: 110, height: 110, shape: 'round' }
}
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

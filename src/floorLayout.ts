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

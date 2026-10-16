import type { OrderItem } from './data'
export interface Draft { cart: OrderItem[]; customer: string; discountPct: number }
export interface Table { id: string; name: string; zone: string; shape: 'round' | 'square' | 'long' }
export function readSaved<T>(key: string, fallback: T): T {
  try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback } catch { return fallback }
}
export const defaultTables: Table[] = Array.from({ length: 15 }, (_, i) => ({
  id: String(i + 1), name: i === 14 ? 'VIP' : String(i + 1), zone: i === 14 ? 'VIP' : 'Zal',
  shape: i === 14 ? 'long' : i > 8 ? 'square' : 'round',
}))


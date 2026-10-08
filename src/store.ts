import { useSyncExternalStore } from 'react'
import { INGREDIENTS, PRODUCTS, MODIFIERS, buildItem } from './data'
import type { Order, OrderItem, Payment, Status } from './data'

export interface State { day: number; orders: Order[]; stock: Record<string, number> }

const KEY = 'coffeepos-demo-v1'
export const BARISTA = 'Dilnoza'
const NAMES = ['Aziz', 'Malika', 'Bekzod', 'Nilufar', 'Sardor', 'Madina', 'Javohir', 'Zarina', 'Otabek', 'Kamola', 'Timur', 'Sevara', 'Rustam', 'Lola', 'Islom', 'Dilshod', '']

export const startOfToday = () => {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

function rng(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function makeOrder(number: number, items: OrderItem[], o: { customer: string; discountPct: number; payment: Payment; cashGiven?: number; status: Status; createdAt: number }): Order {
  const subtotal = items.reduce((s, i) => s + i.unitPrice * i.qty, 0)
  const discount = Math.round((subtotal * o.discountPct) / 100 / 100) * 100
  return {
    id: `${o.createdAt}-${number}`,
    number,
    customer: o.customer,
    items,
    subtotal,
    discount,
    total: subtotal - discount,
    cost: items.reduce((s, i) => s + i.unitCost * i.qty, 0),
    payment: o.payment,
    cashGiven: o.cashGiven,
    status: o.status,
    createdAt: o.createdAt,
    readyAt: o.status === 'ready' || o.status === 'done' ? o.createdAt + 4 * 60_000 : undefined,
    barista: BARISTA,
  }
}

function seed(): State {
  const r = rng(42)
  const pick = <T,>(a: T[]) => a[Math.floor(r() * a.length)]
  const randomItem = () => {
    const p = pick(PRODUCTS)
    const mods: string[] = []
    if (p.mods.includes('milk') && r() < 0.2) mods.push(pick(MODIFIERS.filter((m) => m.group === 'milk' && m.price > 0)).id)
    if (p.mods.includes('syrup') && r() < 0.25) mods.push(pick(MODIFIERS.filter((m) => m.group === 'syrup')).id)
    return buildItem(p, pick(p.sizes), mods, 1)
  }
  const randomItems = () => {
    const n = r() < 0.7 ? 1 : r() < 0.85 ? 2 : 3
    const list: OrderItem[] = []
    for (let i = 0; i < n; i++) {
      const it = randomItem()
      const same = list.find((x) => x.key === it.key)
      if (same) same.qty++
      else list.push(it)
    }
    return list
  }
  const payment = (): Payment => {
    const x = r()
    return x < 0.45 ? 'karta' : x < 0.7 ? 'naqd' : x < 0.85 ? 'payme' : 'click'
  }

  const now = Date.now()
  const today8 = startOfToday() + 8 * 3600_000
  const start = now - today8 > 3600_000 ? today8 : now - 3 * 3600_000
  const orders: Order[] = []
  let n = 0
  for (let t = start; t < now - 8 * 60_000; t += (3 + r() * 8) * 60_000) {
    orders.push(makeOrder(++n, randomItems(), { customer: pick(NAMES), discountPct: r() < 0.08 ? 10 : 0, payment: payment(), status: 'done', createdAt: t }))
  }
  const active: [Status, number][] = [['ready', 5], ['preparing', 3], ['new', 1.5], ['new', 0.5]]
  for (const [status, minAgo] of active) {
    orders.push(makeOrder(++n, randomItems(), { customer: pick(NAMES.filter(Boolean)), discountPct: 0, payment: payment(), status, createdAt: now - minAgo * 60_000 }))
  }
  return { day: startOfToday(), orders, stock: Object.fromEntries(INGREDIENTS.map((i) => [i.id, i.stock])) }
}

function load(): State {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      const s = JSON.parse(raw) as State
      if (s.day === startOfToday() && Array.isArray(s.orders)) return s
    }
  } catch {
    /* fall through to a fresh seed */
  }
  const s = seed()
  localStorage.setItem(KEY, JSON.stringify(s))
  return s
}

let state: State = load()
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

function save(next: State) {
  state = next
  localStorage.setItem(KEY, JSON.stringify(next))
  emit()
}

window.addEventListener('storage', (e) => {
  if (e.key === KEY && e.newValue) {
    state = JSON.parse(e.newValue) as State
    emit()
  }
})

export function useAppState() {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => {
        listeners.delete(cb)
      }
    },
    () => state,
  )
}

export const nextNumber = () => state.orders.reduce((m, o) => Math.max(m, o.number), 0) + 1

export function placeOrder(items: OrderItem[], o: { customer: string; discountPct: number; payment: Payment; cashGiven?: number }): Order {
  const order = makeOrder(nextNumber(), items, { ...o, status: 'new', createdAt: Date.now() })
  const stock = { ...state.stock }
  for (const it of items) for (const l of it.consumption) stock[l.ing] = (stock[l.ing] ?? 0) - l.qty * it.qty
  save({ ...state, orders: [...state.orders, order], stock })
  return order
}

export function setStatus(id: string, status: Status) {
  save({
    ...state,
    orders: state.orders.map((o) => (o.id === id ? { ...o, status, readyAt: status === 'ready' ? Date.now() : o.readyAt } : o)),
  })
}

export function addStock(ing: string, qty: number) {
  save({ ...state, stock: { ...state.stock, [ing]: (state.stock[ing] ?? 0) + qty } })
}

export function resetDemo() {
  save(seed())
}

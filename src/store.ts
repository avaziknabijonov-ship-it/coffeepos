import { useSyncExternalStore } from 'react'
import { setMenu } from './data'
import type { Menu, Order, OrderItem, Payment, Role, Status } from './data'
import { ApiError, api, getToken, setToken } from './api'
import { getLang, setLangValue } from './i18n'
import type { Lang } from './i18n'

export interface Session { staff: { id: number; name: string; role: Role }; company: { slug: string; name: string } }
export interface ShiftInfo {
  shift: { id: number; staff: string; openedAt: number; openingCash: number; closedAt?: number | null; closingCash?: number | null; expectedCash?: number | null }
  orders: number
  revenue: number
  byPayment: Partial<Record<Payment, number>>
  expectedCash: number
  difference?: number
}
export interface State {
  phase: 'loading' | 'login' | 'ready'
  session: Session | null
  menuVersion: number
  orders: Order[]
  stock: Record<string, number>
  shift: ShiftInfo | null
  online: boolean
  lang: Lang
}

export const startOfToday = () => {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

let state: State = { phase: 'loading', session: null, menuVersion: 0, orders: [], stock: {}, shift: null, online: true, lang: getLang() }
const listeners = new Set<() => void>()
const set = (patch: Partial<State>) => {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
}

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

export function setLang(lang: Lang) {
  setLangValue(lang)
  set({ lang })
}

let timer: ReturnType<typeof setInterval> | undefined

export async function sync() {
  try {
    const d = await api<{ orders: Order[]; stock: Record<string, number>; shift: ShiftInfo | null }>(`/api/sync?since=${startOfToday()}`)
    set({ orders: d.orders, stock: d.stock, shift: d.shift, online: true })
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) logout()
    else set({ online: false })
  }
}

export async function refreshMenu() {
  setMenu(await api<Menu>('/api/menu'))
  set({ menuVersion: state.menuVersion + 1 })
}

async function start(session: Session) {
  await refreshMenu()
  await sync()
  set({ session, phase: 'ready' })
  clearInterval(timer)
  timer = setInterval(sync, 2500)
}

export async function bootstrap() {
  if (!getToken()) return set({ phase: 'login' })
  try {
    await start(await api<Session>('/api/me'))
  } catch {
    setToken(null)
    set({ phase: 'login' })
  }
}

export async function login(company: string, pin: string) {
  const r = await api<Session & { token: string }>('/api/auth/login', { body: { company, pin } })
  setToken(r.token)
  localStorage.setItem('coffeepos-company', r.company.slug)
  await start(r)
}

export async function register(body: { companyName: string; slug: string; ownerName: string; ownerPin: string }) {
  const r = await api<Session & { token: string }>('/api/auth/register', { body })
  setToken(r.token)
  localStorage.setItem('coffeepos-company', r.company.slug)
  await start(r)
}

export function logout() {
  clearInterval(timer)
  setToken(null)
  set({ phase: 'login', session: null, orders: [], stock: {}, shift: null })
}

export const nextNumber = () =>
  state.orders.filter((o) => o.createdAt >= startOfToday()).reduce((m, o) => Math.max(m, o.number), 0) + 1

export async function placeOrder(items: OrderItem[], o: { customer: string; discountPct: number; payment: Payment; cashGiven?: number; debtPhone?: string; debtNote?: string }) {
  const order = await api<Order>('/api/orders', {
    body: { ...o, items: items.map((i) => ({ productId: i.productId, size: i.key.split('|')[1], modIds: i.modIds, qty: i.qty })) },
  })
  set({ orders: [...state.orders, order] })
  void sync()
  return order
}

export async function setStatus(id: string, status: Status) {
  set({ orders: state.orders.map((o) => (o.id === id ? { ...o, status, readyAt: status === 'ready' ? Date.now() : o.readyAt } : o)) })
  try {
    await api(`/api/orders/${id}`, { method: 'PATCH', body: { status } })
  } finally {
    void sync()
  }
}

export async function stockMove(ing: string, qty: number, reason: 'intake' | 'writeoff' | 'count', note?: string) {
  await api('/api/stock', { body: { ing, qty, reason, note } })
  await Promise.all([sync(), refreshMenu()])
}

export async function openShift(openingCash: number) {
  await api('/api/shifts/open', { body: { openingCash } })
  await sync()
}

export async function closeShift(closingCash: number) {
  const r = await api<ShiftInfo>('/api/shifts/close', { body: { closingCash } })
  await sync()
  return r
}

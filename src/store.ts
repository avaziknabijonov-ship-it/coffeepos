import { useSyncExternalStore } from 'react'
import { getQueuedSales, queueCashSale, removeQueuedSale } from './offline'
import { setMenu, discountAmount } from './data'
import type { Menu, Order, OrderItem, Payment, Role, Status } from './data'
import { ApiError, api, getToken, setToken } from './api'
import { getLang, setLangValue } from './i18n'
import type { Lang } from './i18n'

export interface Session { staff: { id: number; name: string; role: Role; canBarista?: boolean; canCancelOrders?: boolean; canReprintReceipts?: boolean }; company: { slug: string; name: string } }
export interface ShiftInfo {
  shift: { id: number; staff: string; openedAt: number; openingCash: number; closedAt?: number | null; closingCash?: number | null; expectedCash?: number | null }
  orders: number
  revenue: number
  byPayment: Partial<Record<Payment, number>>
  expectedCash: number
  cashExpenses?: number
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
  pendingCount: number
  pendingError: string
  lang: Lang
}

export const startOfToday = () => {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

let state: State = { phase: 'loading', session: null, menuVersion: 0, orders: [], stock: {}, shift: null, online: true, pendingCount: 0, pendingError: '', lang: getLang() }
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

const menuCache = (slug: string) => 'coffeepos-menu-cache:' + slug
const syncCache = (slug: string) => 'coffeepos-sync-cache:' + slug
let pushing = false

async function pushPendingSales() {
  if (pushing || !state.session) return
  pushing = true
  const company = state.session.company.slug
  try {
    for (const sale of getQueuedSales(company)) {
      try {
        await api<Order>('/api/orders', { body: sale.body })
        removeQueuedSale(company, sale.clientKey)
        set({ pendingError: '' })
      } catch (e) {
        set({ pendingError: (e as Error).message })
        break
      }
    }
  } finally {
    set({ pendingCount: getQueuedSales(company).length })
    pushing = false
  }
}

export async function sync() {
  try {
    await pushPendingSales()
    const d = await api<{ orders: Order[]; stock: Record<string, number>; shift: ShiftInfo | null }>(`/api/sync?since=${startOfToday()}`)
    const company = state.session?.company.slug
    if (company) {
      try { localStorage.setItem(syncCache(company), JSON.stringify(d)) } catch { /* cache is optional */ }
    }
    set({ orders: d.orders, stock: d.stock, shift: d.shift, online: true })
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) logout()
    else set({ online: false })
  }
}

export async function refreshMenu(company = state.session?.company.slug) {
  try {
    const menu = await api<Menu>('/api/menu')
    setMenu(menu)
    if (company) {
      try { localStorage.setItem(menuCache(company), JSON.stringify(menu)) } catch { /* cache is optional */ }
    }
  } catch (e) {
    const cached = company ? localStorage.getItem(menuCache(company)) : null
    if (!(e instanceof ApiError && e.status === 0 && cached)) throw e
    setMenu(JSON.parse(cached) as Menu)
    set({ online: false })
  }
  set({ menuVersion: state.menuVersion + 1 })
}

async function start(session: Session) {
  set({ session, pendingCount: getQueuedSales(session.company.slug).length })
  try { localStorage.setItem('coffeepos-last-session', JSON.stringify(session)) } catch { /* optional */ }
  const cachedSync = localStorage.getItem(syncCache(session.company.slug))
  if (cachedSync) {
    try {
      const d = JSON.parse(cachedSync) as { orders: Order[]; stock: Record<string, number>; shift: ShiftInfo | null }
      set({ orders: d.orders, stock: d.stock, shift: d.shift })
    } catch { /* invalid cache */ }
  }
  await refreshMenu(session.company.slug)
  await sync()
  set({ phase: 'ready' })
  clearInterval(timer)
  timer = setInterval(sync, 2500)
}

export async function bootstrap() {
  if (!getToken()) return set({ phase: 'login' })
  try {
    await start(await api<Session>('/api/me'))
  } catch (e) {
    if (e instanceof ApiError && e.status === 0) {
      try {
        const cached = JSON.parse(localStorage.getItem('coffeepos-last-session') ?? 'null') as Session | null
        if (cached && cached.company.slug === localStorage.getItem('coffeepos-company')) {
          await start(cached)
          return
        }
      } catch { /* offline session not available */ }
      set({ phase: 'login', online: false })
      return
    }
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

export async function placeOrder(items: OrderItem[], o: { customer: string; discountPct: number; expectedTotal?: number; automaticDiscount?: boolean; payment: Payment; paymentParts?: { method: Exclude<Payment, 'split'>; amount: number }[]; cashGiven?: number; customerPhone?: string; bonusRedeem?: number }) {
  const clientKey = crypto.randomUUID()
  const payload = { ...o, clientKey, items: items.map((i) => ({
    productId: i.productId, size: i.key.split('|')[1], modIds: i.modIds, qty: i.qty,
  })) }
  let order: Order
  try {
    order = await api<Order>('/api/orders', { body: payload })
  } catch (e) {
    if (!(e instanceof ApiError && (e.status === 0 || [502, 503, 504].includes(e.status)) && !o.automaticDiscount && o.payment === 'naqd' && !o.customerPhone && !o.bonusRedeem && state.shift && state.session)) throw e
    const company = state.session.company.slug
    const sale = queueCashSale(company, {
      clientKey, customer: o.customer, items: payload.items, discountPct: o.discountPct,
      payment: 'naqd', cashGiven: o.cashGiven, expectedTotal: o.expectedTotal,
    })
    const subtotal = items.reduce((sum, item) => sum + item.qty * item.unitPrice, 0)
    const discount = discountAmount(subtotal, o.discountPct)
    order = {
      id: 'offline:' + clientKey, number: nextNumber(), customer: o.customer,
      items, subtotal, discount, total: subtotal - discount,
      cost: items.reduce((sum, item) => sum + item.qty * item.unitCost, 0),
      payment: 'naqd', cashGiven: o.cashGiven, status: 'new',
      createdAt: sale.createdAt, readyAt: null, barista: state.session.staff.name,
      pendingSync: true,
    }
    set({ online: false, pendingCount: getQueuedSales(company).length, orders: [...state.orders, order] })
    return order
  }
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

import { t } from './i18n'

export type Unit = 'g' | 'ml' | 'dona'
export interface Ingredient { id: string; name: string; unit: Unit; cost: number; stock: number; min: number; recipe?: RecipeLine[]; yieldQty?: number; semi?: boolean }
export interface RecipeLine { ing: string; qty: number }
export interface Size { code: string; label: string; volume?: string; price: number; recipe: RecipeLine[]; barcode?: string }
export type ModGroupId = 'milk' | 'syrup' | 'shot'
export interface Product { id: string; cat: string; name: string; sizes: Size[]; mods: ModGroupId[]; active: boolean; imageUrl?: string; weighted?: boolean }
export interface Category { id: string; name: string; workshop?: string }
export interface Workshop { id: string; name: string }
export type Effect = { type: 'none' } | { type: 'swap'; from: string; to: string } | { type: 'add'; ing: string; qty: number }
export interface Modifier { id: string; group: ModGroupId; name: string; price: number; effect: Effect }
export interface MenuSettings { autoStoplist: boolean }
export interface Promotion {
  id: number; name: string; pct: number; target: 'all' | 'category' | 'product'; keys: string[]
  days: number[]; startTime: string; endTime: string; dateFrom: string; dateTo: string; active: boolean
}
export interface Menu { categories: Category[]; products: Product[]; modifiers: Modifier[]; ingredients: Ingredient[]; settings?: MenuSettings; promotions?: Promotion[]; workshops?: Workshop[]; restaurant?: boolean }

export interface CheckLine extends OrderItem { sent?: number }
export interface OpenCheck {
  id: number; tableId: number | null; tableName: string; guests: number; waiter: string; comment: string
  items: CheckLine[]; total: number; status: 'open' | 'paid' | 'void'; orderId: string | null
  createdAt: number; updatedAt: number; closedAt: number | null; unsent: number
}
export interface KitchenTicket {
  id: number; checkId: number; workshop: string; tableName: string; waiter: string; comment: string
  items: { name: string; size: string; mods: string[]; qty: number }[]
  status: 'new' | 'preparing' | 'ready' | 'done'; createdAt: number; readyAt: number | null
}
export interface HallInfo { id: number; name: string; tables: { id: number; name: string; seats: number; active: boolean }[] }

export type Payment = 'naqd' | 'karta' | 'payme' | 'click'
export type Status = 'new' | 'preparing' | 'ready' | 'done' | 'cancelled'
export interface OrderItem {
  key: string; productId: string; name: string; size: string; modIds: string[]; mods: string[]
  qty: number; unitPrice: number; unitCost: number; consumption: RecipeLine[]
  promo?: string; promoPct?: number; promoDiscount?: number; weight?: number
}
export interface Order {
  id: string; number: number; customer: string; items: OrderItem[]
  subtotal: number; discount: number; total: number; cost: number
  payment: Payment; cashGiven?: number | null; status: Status; createdAt: number; readyAt?: number | null; barista: string; cancelledAt?: number | null; cancelledBy?: string | null; cancelReason?: string | null; pendingSync?: boolean
}

export const fmt = (n: number) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
export const som = (n: number) => `${fmt(n)} ${t("so'm")}`
export const time = (t: number) => new Date(t).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })

export const PAYMENT_LABEL: Record<Payment, string> = { naqd: 'Naqd', karta: 'Karta', payme: 'Payme', click: 'Click' }
export const STATUS_LABEL: Record<Status, string> = { new: 'Yangi', preparing: 'Tayyorlanmoqda', ready: 'Tayyor', done: 'Berildi', cancelled: 'Bekor qilingan' }
export const UNIT_LABEL: Record<Unit, string> = { g: 'g', ml: 'ml', dona: 'dona' }

export type Role = 'owner' | 'admin' | 'kassir' | 'barista' | 'ofitsiant'
export const ROLE_LABEL: Record<Role, string> = { owner: 'Rahbar', admin: 'Administrator', kassir: 'Kassir', barista: 'Barista / oshpaz', ofitsiant: 'Ofitsiant' }

// Menu is loaded from the API; these live bindings are replaced by setMenu().
export let INGREDIENTS: Ingredient[] = []
export let ING: Record<string, Ingredient> = {}
export let CATEGORIES: Category[] = []
export let PRODUCTS: Product[] = []
export let MODIFIERS: Modifier[] = []
export let MOD: Record<string, Modifier> = {}
export let SETTINGS: MenuSettings = { autoStoplist: false }
export let PROMOTIONS: Promotion[] = []
export let WORKSHOPS: Workshop[] = []
export let RESTAURANT = false

export function setMenu(m: Menu) {
  INGREDIENTS = m.ingredients
  ING = Object.fromEntries(m.ingredients.map((i) => [i.id, i]))
  CATEGORIES = m.categories
  PRODUCTS = m.products
  MODIFIERS = m.modifiers
  MOD = Object.fromEntries(m.modifiers.map((x) => [x.id, x]))
  SETTINGS = m.settings ?? { autoStoplist: false }
  PROMOTIONS = m.promotions ?? []
  WORKSHOPS = m.workshops ?? []
  RESTAURANT = Boolean(m.restaurant)
}

export const DEFAULT_MILK = 'milk-regular'

const applyEffect = (lines: RecipeLine[], e: Effect): RecipeLine[] => {
  if (e.type === 'swap') return lines.map((l) => (l.ing === e.from ? { ...l, ing: e.to } : l))
  if (e.type === 'add') return [...lines, { ing: e.ing, qty: e.qty }]
  return lines
}

export const recipeCost = (lines: RecipeLine[]) => lines.reduce((s, l) => s + (ING[l.ing]?.cost ?? 0) * l.qty, 0)

export function buildItem(p: Product, size: Size, modIds: string[], qty: number, weight?: number): OrderItem {
  const mods = modIds.filter((id) => id !== DEFAULT_MILK && MOD[id]).map((id) => MOD[id])
  let consumption = mods.reduce((lines, m) => applyEffect(lines, m.effect), size.recipe)
  const base = size.price + mods.reduce((s, m) => s + m.price, 0)
  const w = p.weighted && weight ? Math.round(weight * 1000) / 1000 : undefined
  if (w !== undefined) consumption = consumption.map((l) => ({ ...l, qty: l.qty * w }))
  const item: OrderItem = {
    key: [p.id, size.code, ...mods.map((m) => m.id).sort()].join('|') + (w !== undefined ? `|w${w.toFixed(3)}` : ''),
    productId: p.id,
    name: p.name,
    size: w !== undefined ? `${w.toFixed(3)} kg` : size.label,
    modIds: mods.map((m) => m.id),
    mods: mods.map((m) => (m.group === 'syrup' ? `${m.name} sirop` : m.name)),
    qty,
    unitPrice: w !== undefined ? Math.floor(base * w + 0.5) : base,
    unitCost: Math.round(recipeCost(consumption)),
    consumption,
  }
  if (w !== undefined) item.weight = w
  return item
}

/** Resolve a scanned code: a size barcode, or an EAN-13 scale label (2X + 5-digit PLU + 5-digit grams + check). */
export function findByBarcode(code: string): { product: Product; size: Size; weight?: number } | null {
  const c = code.trim()
  if (!c) return null
  for (const p of PRODUCTS) for (const s of p.sizes) if (s.barcode && s.barcode === c) return { product: p, size: s }
  if (/^2[0-9]{12}$/.test(c)) {
    const plu = c.slice(2, 7)
    const grams = Number(c.slice(7, 12))
    for (const p of PRODUCTS) {
      if (!p.weighted) continue
      for (const s of p.sizes) {
        if (s.barcode && s.barcode.padStart(5, '0') === plu && grams > 0) return { product: p, size: s, weight: grams / 1000 }
      }
    }
  }
  return null
}

/** Automatic stop-list: true when at least one size can be made from current stock. */
export function canMake(p: Product, stock: Record<string, number>): boolean {
  if (p.weighted) return p.sizes.some((size) => size.recipe.every((l) => !(l.ing in stock) || stock[l.ing] > 0.000001))
  return p.sizes.some((size) => size.recipe.every((l) => !(l.ing in stock) || stock[l.ing] + 0.000001 >= l.qty))
}

/** Ingredients that are short for this exact item (after modifiers), multiplied by qty. */
export function missingFor(consumption: RecipeLine[], qty: number, stock: Record<string, number>): string[] {
  const need: Record<string, number> = {}
  for (const l of consumption) need[l.ing] = (need[l.ing] ?? 0) + l.qty * qty
  return Object.entries(need).filter(([ing, q]) => ing in stock && stock[ing] + 0.000001 < q).map(([ing]) => ING[ing]?.name ?? ing)
}

// ---------- promotions: same rules as backend/app/logic.py ----------
const minutes = (hhmm: string) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m }
const pad = (n: number) => String(n).padStart(2, '0')
export const round100 = (x: number) => Math.floor(x / 100 + 0.5) * 100

export function promoApplies(p: Promotion, productId: string, cat: string, at: Date): boolean {
  if (!p.active) return false
  const day = `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`
  if (p.dateFrom && day < p.dateFrom) return false
  if (p.dateTo && day > p.dateTo) return false
  if (p.days.length && !p.days.includes((at.getDay() + 6) % 7)) return false
  const start = minutes(p.startTime), end = minutes(p.endTime), now = at.getHours() * 60 + at.getMinutes()
  if (start < end && !(start <= now && now < end)) return false
  if (start > end && !(now >= start || now < end)) return false
  if (p.target === 'category') return p.keys.includes(cat)
  if (p.target === 'product') return p.keys.includes(productId)
  return true
}

export interface CartTotals { items: OrderItem[]; subtotal: number; promo: number; manual: number; discount: number; total: number }

/** Attach the best active promotion to each line and compute receipt totals (before bonus). */
export function cartTotals(cart: OrderItem[], discountPct: number, at = new Date()): CartTotals {
  const cats = Object.fromEntries(PRODUCTS.map((p) => [p.id, p.cat]))
  const items = cart.map((it) => {
    let best: Promotion | null = null
    for (const p of PROMOTIONS) if (promoApplies(p, it.productId, cats[it.productId] ?? '', at) && (!best || p.pct > best.pct)) best = p
    if (!best) return { ...it, promo: undefined, promoPct: undefined, promoDiscount: 0 }
    return { ...it, promo: best.name, promoPct: best.pct, promoDiscount: round100(it.unitPrice * it.qty * best.pct / 100) }
  })
  const subtotal = items.reduce((s, i) => s + i.unitPrice * i.qty, 0)
  const promo = items.reduce((s, i) => s + (i.promoDiscount ?? 0), 0)
  const manual = round100((subtotal - promo) * discountPct / 100)
  return { items, subtotal, promo, manual, discount: promo + manual, total: subtotal - promo - manual }
}

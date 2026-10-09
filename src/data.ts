import { t } from './i18n'

export type Unit = 'g' | 'ml' | 'dona'
export interface Ingredient { id: string; name: string; unit: Unit; cost: number; stock: number; min: number }
export interface RecipeLine { ing: string; qty: number }
export interface Size { code: string; label: string; volume?: string; price: number; recipe: RecipeLine[] }
export type ModGroupId = 'milk' | 'syrup' | 'shot'
export interface Product { id: string; cat: string; name: string; sizes: Size[]; mods: ModGroupId[]; active: boolean; imageUrl?: string | null }
export interface Category { id: string; name: string }
export type Effect = { type: 'none' } | { type: 'swap'; from: string; to: string } | { type: 'add'; ing: string; qty: number }
export interface Modifier { id: string; group: ModGroupId; name: string; price: number; effect: Effect }
export interface Menu { categories: Category[]; products: Product[]; modifiers: Modifier[]; ingredients: Ingredient[] }

export type Payment = 'naqd' | 'karta' | 'payme' | 'click' | 'qarz'
export type Status = 'new' | 'preparing' | 'ready' | 'done'
export interface OrderItem {
  key: string; productId: string; name: string; size: string; modIds: string[]; mods: string[]
  qty: number; unitPrice: number; unitCost: number; consumption: RecipeLine[]
}
export interface Order {
  id: string; number: number; customer: string; items: OrderItem[]
  subtotal: number; discount: number; total: number; cost: number
  payment: Payment; cashGiven?: number | null; status: Status; createdAt: number; readyAt?: number | null; barista: string
}

export const fmt = (n: number) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
export const som = (n: number) => `${fmt(n)} ${t("so'm")}`
export const time = (t: number) => new Date(t).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })

export const PAYMENT_LABEL: Record<Payment, string> = { naqd: 'Naqd', karta: 'Karta', payme: 'Payme', click: 'Click', qarz: 'Qarz' }
export const STATUS_LABEL: Record<Status, string> = { new: 'Yangi', preparing: 'Tayyorlanmoqda', ready: 'Tayyor', done: 'Berildi' }
export const UNIT_LABEL: Record<Unit, string> = { g: 'g', ml: 'ml', dona: 'dona' }

export type Role = 'owner' | 'admin' | 'kassir' | 'barista'
export const ROLE_LABEL: Record<Role, string> = { owner: 'Rahbar', admin: 'Administrator', kassir: 'Kassir', barista: 'Barista' }

// Menu is loaded from the API; these live bindings are replaced by setMenu().
export let INGREDIENTS: Ingredient[] = []
export let ING: Record<string, Ingredient> = {}
export let CATEGORIES: Category[] = []
export let PRODUCTS: Product[] = []
export let MODIFIERS: Modifier[] = []
export let MOD: Record<string, Modifier> = {}

export function setMenu(m: Menu) {
  INGREDIENTS = m.ingredients
  ING = Object.fromEntries(m.ingredients.map((i) => [i.id, i]))
  CATEGORIES = m.categories
  PRODUCTS = m.products
  MODIFIERS = m.modifiers
  MOD = Object.fromEntries(m.modifiers.map((x) => [x.id, x]))
}

export const DEFAULT_MILK = 'milk-regular'

const applyEffect = (lines: RecipeLine[], e: Effect): RecipeLine[] => {
  if (e.type === 'swap') return lines.map((l) => (l.ing === e.from ? { ...l, ing: e.to } : l))
  if (e.type === 'add') return [...lines, { ing: e.ing, qty: e.qty }]
  return lines
}

export const recipeCost = (lines: RecipeLine[]) => lines.reduce((s, l) => s + (ING[l.ing]?.cost ?? 0) * l.qty, 0)

export function buildItem(p: Product, size: Size, modIds: string[], qty: number): OrderItem {
  const mods = modIds.filter((id) => id !== DEFAULT_MILK && MOD[id]).map((id) => MOD[id])
  const consumption = mods.reduce((lines, m) => applyEffect(lines, m.effect), size.recipe)
  return {
    key: [p.id, size.code, ...mods.map((m) => m.id).sort()].join('|'),
    productId: p.id,
    name: p.name,
    size: size.label,
    modIds: mods.map((m) => m.id),
    mods: mods.map((m) => (m.group === 'syrup' ? `${m.name} sirop` : m.name)),
    qty,
    unitPrice: size.price + mods.reduce((s, m) => s + m.price, 0),
    unitCost: Math.round(recipeCost(consumption)),
    consumption,
  }
}

export type Unit = 'g' | 'ml' | 'dona'
export interface Ingredient { id: string; name: string; unit: Unit; cost: number; stock: number; min: number }
export interface RecipeLine { ing: string; qty: number }
export interface Size { code: string; label: string; volume?: string; price: number; recipe: RecipeLine[] }
export type ModGroupId = 'milk' | 'syrup' | 'shot'
export interface Product { id: string; cat: string; name: string; sizes: Size[]; mods: ModGroupId[] }
export interface Category { id: string; name: string }
export interface Modifier { id: string; group: ModGroupId; name: string; price: number; apply: (lines: RecipeLine[]) => RecipeLine[] }

export type Payment = 'naqd' | 'karta' | 'payme' | 'click'
export type Status = 'new' | 'preparing' | 'ready' | 'done'
export interface OrderItem {
  key: string; productId: string; name: string; size: string; modIds: string[]; mods: string[]
  qty: number; unitPrice: number; unitCost: number; consumption: RecipeLine[]
}
export interface Order {
  id: string; number: number; customer: string; items: OrderItem[]
  subtotal: number; discount: number; total: number; cost: number
  payment: Payment; cashGiven?: number; status: Status; createdAt: number; readyAt?: number; barista: string
}

export const fmt = (n: number) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
export const som = (n: number) => `${fmt(n)} so'm`
export const time = (t: number) => new Date(t).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })

export const PAYMENT_LABEL: Record<Payment, string> = { naqd: 'Naqd', karta: 'Karta', payme: 'Payme', click: 'Click' }
export const STATUS_LABEL: Record<Status, string> = { new: 'Yangi', preparing: 'Tayyorlanmoqda', ready: 'Tayyor', done: 'Berildi' }
export const UNIT_LABEL: Record<Unit, string> = { g: 'g', ml: 'ml', dona: 'dona' }

export const INGREDIENTS: Ingredient[] = [
  { id: 'beans', name: 'Kofe doni (arabika)', unit: 'g', cost: 260, stock: 4200, min: 1000 },
  { id: 'milk', name: 'Sut 3,2%', unit: 'ml', cost: 14, stock: 18000, min: 5000 },
  { id: 'almond', name: 'Bodom suti', unit: 'ml', cost: 48, stock: 2500, min: 1000 },
  { id: 'coconut', name: 'Kokos suti', unit: 'ml', cost: 46, stock: 1800, min: 1000 },
  { id: 'lactfree', name: 'Laktozasiz sut', unit: 'ml', cost: 22, stock: 3000, min: 1000 },
  { id: 'cream', name: 'Qaymoq 10%', unit: 'ml', cost: 30, stock: 2000, min: 500 },
  { id: 'syr-caramel', name: 'Karamel sirop', unit: 'ml', cost: 170, stock: 1400, min: 300 },
  { id: 'syr-vanilla', name: 'Vanil sirop', unit: 'ml', cost: 170, stock: 260, min: 300 },
  { id: 'syr-hazelnut', name: 'Findiq sirop', unit: 'ml', cost: 170, stock: 1100, min: 300 },
  { id: 'choc', name: 'Shokolad sousi', unit: 'ml', cost: 120, stock: 900, min: 300 },
  { id: 'matcha', name: 'Matcha kukuni', unit: 'g', cost: 900, stock: 300, min: 100 },
  { id: 'tea-black', name: 'Qora choy (paket)', unit: 'dona', cost: 900, stock: 120, min: 30 },
  { id: 'tea-green', name: "Ko'k choy (paket)", unit: 'dona', cost: 900, stock: 24, min: 30 },
  { id: 'ice', name: 'Muz', unit: 'g', cost: 2, stock: 10000, min: 2000 },
  { id: 'cup-s', name: 'Stakan S (250 ml)', unit: 'dona', cost: 650, stock: 400, min: 100 },
  { id: 'cup-m', name: 'Stakan M (350 ml)', unit: 'dona', cost: 750, stock: 350, min: 100 },
  { id: 'cup-l', name: 'Stakan L (450 ml)', unit: 'dona', cost: 850, stock: 80, min: 100 },
  { id: 'cup-cold', name: 'Sovuq ichimlik stakani', unit: 'dona', cost: 900, stock: 300, min: 100 },
  { id: 'lid', name: 'Qopqoq', unit: 'dona', cost: 300, stock: 900, min: 200 },
  { id: 'straw', name: 'Trubochka', unit: 'dona', cost: 100, stock: 800, min: 200 },
  { id: 'croissant', name: 'Kruassan', unit: 'dona', cost: 9000, stock: 18, min: 5 },
  { id: 'cheesecake', name: "Chizkeyk (bo'lak)", unit: 'dona', cost: 15000, stock: 10, min: 4 },
  { id: 'brownie', name: 'Brauni', unit: 'dona', cost: 8000, stock: 14, min: 5 },
]
export const ING: Record<string, Ingredient> = Object.fromEntries(INGREDIENTS.map((i) => [i.id, i]))

export const CATEGORIES: Category[] = [
  { id: 'espresso', name: 'Espresso' },
  { id: 'milk', name: 'Sutli kofe' },
  { id: 'cold', name: 'Sovuq' },
  { id: 'tea', name: 'Choy' },
  { id: 'dessert', name: 'Desert' },
]

const L = (ing: string, qty: number): RecipeLine => ({ ing, qty })
const hot = (cup: string, ...lines: RecipeLine[]) => [...lines, L(cup, 1), L('lid', 1)]
const cold = (...lines: RecipeLine[]) => [...lines, L('cup-cold', 1), L('straw', 1)]
const S = (price: number, recipe: RecipeLine[]): Size => ({ code: 'S', label: 'S', volume: '250 ml', price, recipe })
const M = (price: number, recipe: RecipeLine[]): Size => ({ code: 'M', label: 'M', volume: '350 ml', price, recipe })
const Lg = (price: number, recipe: RecipeLine[]): Size => ({ code: 'L', label: 'L', volume: '450 ml', price, recipe })
const one = (price: number, recipe: RecipeLine[]): Size => ({ code: '-', label: '', price, recipe })

export const PRODUCTS: Product[] = [
  { id: 'espresso', cat: 'espresso', name: 'Espresso', mods: [], sizes: [one(15000, [L('beans', 9)])] },
  { id: 'doppio', cat: 'espresso', name: 'Doppio', mods: [], sizes: [one(20000, [L('beans', 18)])] },
  { id: 'americano', cat: 'espresso', name: 'Amerikano', mods: ['syrup', 'shot'], sizes: [
    S(18000, hot('cup-s', L('beans', 9))), M(22000, hot('cup-m', L('beans', 18))), Lg(26000, hot('cup-l', L('beans', 18)))] },
  { id: 'cappuccino', cat: 'milk', name: 'Kapuchino', mods: ['milk', 'syrup', 'shot'], sizes: [
    S(24000, hot('cup-s', L('beans', 9), L('milk', 150))), M(28000, hot('cup-m', L('beans', 18), L('milk', 200))), Lg(32000, hot('cup-l', L('beans', 18), L('milk', 280)))] },
  { id: 'latte', cat: 'milk', name: 'Latte', mods: ['milk', 'syrup', 'shot'], sizes: [
    S(26000, hot('cup-s', L('beans', 9), L('milk', 180))), M(30000, hot('cup-m', L('beans', 18), L('milk', 240))), Lg(34000, hot('cup-l', L('beans', 18), L('milk', 320)))] },
  { id: 'flatwhite', cat: 'milk', name: 'Flat uayt', mods: ['milk', 'syrup'], sizes: [S(30000, hot('cup-s', L('beans', 18), L('milk', 150)))] },
  { id: 'raf', cat: 'milk', name: 'Raf', mods: ['syrup', 'shot'], sizes: [
    M(34000, hot('cup-m', L('beans', 18), L('cream', 200), L('syr-vanilla', 10))), Lg(38000, hot('cup-l', L('beans', 18), L('cream', 280), L('syr-vanilla', 15)))] },
  { id: 'mocha', cat: 'milk', name: 'Mokko', mods: ['milk', 'syrup', 'shot'], sizes: [
    S(28000, hot('cup-s', L('beans', 9), L('milk', 130), L('choc', 20))), M(32000, hot('cup-m', L('beans', 18), L('milk', 180), L('choc', 25))), Lg(36000, hot('cup-l', L('beans', 18), L('milk', 250), L('choc', 30)))] },
  { id: 'icelatte', cat: 'cold', name: 'Ays latte', mods: ['milk', 'syrup', 'shot'], sizes: [
    M(32000, cold(L('beans', 18), L('milk', 200), L('ice', 150))), Lg(36000, cold(L('beans', 18), L('milk', 280), L('ice', 180)))] },
  { id: 'iceamericano', cat: 'cold', name: 'Ays amerikano', mods: ['syrup', 'shot'], sizes: [
    M(24000, cold(L('beans', 18), L('ice', 200))), Lg(28000, cold(L('beans', 18), L('ice', 250)))] },
  { id: 'frappe', cat: 'cold', name: 'Frappe karamel', mods: ['milk', 'syrup'], sizes: [
    one(38000, cold(L('beans', 18), L('milk', 150), L('ice', 200), L('cream', 30), L('syr-caramel', 20)))] },
  { id: 'blacktea', cat: 'tea', name: 'Qora choy', mods: [], sizes: [
    S(12000, hot('cup-s', L('tea-black', 1))), Lg(15000, hot('cup-l', L('tea-black', 2)))] },
  { id: 'greentea', cat: 'tea', name: "Ko'k choy", mods: [], sizes: [
    S(12000, hot('cup-s', L('tea-green', 1))), Lg(15000, hot('cup-l', L('tea-green', 2)))] },
  { id: 'matcha', cat: 'tea', name: 'Matcha latte', mods: ['milk', 'syrup'], sizes: [
    M(34000, hot('cup-m', L('matcha', 4), L('milk', 240))), Lg(38000, hot('cup-l', L('matcha', 6), L('milk', 320)))] },
  { id: 'croissant', cat: 'dessert', name: 'Kruassan', mods: [], sizes: [one(20000, [L('croissant', 1)])] },
  { id: 'cheesecake', cat: 'dessert', name: 'Chizkeyk', mods: [], sizes: [one(32000, [L('cheesecake', 1)])] },
  { id: 'brownie', cat: 'dessert', name: 'Brauni', mods: [], sizes: [one(22000, [L('brownie', 1)])] },
]

const swapMilk = (to: string) => (lines: RecipeLine[]) => lines.map((l) => (l.ing === 'milk' ? { ...l, ing: to } : l))
const add = (ing: string, qty: number) => (lines: RecipeLine[]) => [...lines, L(ing, qty)]

export const DEFAULT_MILK = 'milk-regular'
export const MODIFIERS: Modifier[] = [
  { id: DEFAULT_MILK, group: 'milk', name: 'Oddiy sut', price: 0, apply: (l) => l },
  { id: 'milk-almond', group: 'milk', name: 'Bodom suti', price: 6000, apply: swapMilk('almond') },
  { id: 'milk-coconut', group: 'milk', name: 'Kokos suti', price: 6000, apply: swapMilk('coconut') },
  { id: 'milk-lactfree', group: 'milk', name: 'Laktozasiz', price: 4000, apply: swapMilk('lactfree') },
  { id: 'syr-caramel', group: 'syrup', name: 'Karamel', price: 4000, apply: add('syr-caramel', 15) },
  { id: 'syr-vanilla', group: 'syrup', name: 'Vanil', price: 4000, apply: add('syr-vanilla', 15) },
  { id: 'syr-hazelnut', group: 'syrup', name: 'Findiq', price: 4000, apply: add('syr-hazelnut', 15) },
  { id: 'shot1', group: 'shot', name: '+1 shot', price: 5000, apply: add('beans', 9) },
  { id: 'shot2', group: 'shot', name: '+2 shot', price: 10000, apply: add('beans', 18) },
]
export const MOD: Record<string, Modifier> = Object.fromEntries(MODIFIERS.map((m) => [m.id, m]))
export const PROD: Record<string, Product> = Object.fromEntries(PRODUCTS.map((p) => [p.id, p]))

export const recipeCost = (lines: RecipeLine[]) => lines.reduce((s, l) => s + (ING[l.ing]?.cost ?? 0) * l.qty, 0)

export function buildItem(p: Product, size: Size, modIds: string[], qty: number): OrderItem {
  const mods = modIds.filter((id) => id !== DEFAULT_MILK).map((id) => MOD[id])
  const consumption = mods.reduce((lines, m) => m.apply(lines), size.recipe)
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

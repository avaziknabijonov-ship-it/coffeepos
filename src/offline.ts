// Device-local retry queue. Cash-only while disconnected; server validates every sale.
// Orders are NOT considered settled until the server acknowledges their clientKey.
export interface QueuedSale {
  clientKey: string
  createdAt: number
  body: {
    customer: string
    items: { productId: string; size: string; modIds: string[]; qty: number }[]
    discountPct: number
    payment: 'naqd'
    expectedTotal?: number
    cashGiven?: number
    clientKey: string
  }
}
const prefix = 'coffeepos-pending-sales-v1:'
const scoped = (company: string) => prefix + company

function validSale(x: unknown): x is QueuedSale {
  if (typeof x !== 'object' || x === null) return false
  const sale = x as QueuedSale
  return typeof sale.clientKey === 'string' && Number.isFinite(sale.createdAt) &&
    typeof sale.body === 'object' && sale.body !== null && sale.body.clientKey === sale.clientKey &&
    sale.body.payment === 'naqd' && Array.isArray(sale.body.items)
}

// A separate storage entry per sale prevents two tabs from overwriting each other's
// read/modify/write of an array. Acknowledgement removes only that sale's entry.
const itemPrefix = (company: string) => scoped(company) + ':sale:'
const itemKey = (company: string, key: string) => itemPrefix(company) + encodeURIComponent(key)

function migrateLegacy(company: string): void {
  const raw = localStorage.getItem(scoped(company))
  if (raw === null) return
  const legacy: unknown = JSON.parse(raw)
  if (!Array.isArray(legacy) || !legacy.every(validSale)) throw new Error('Invalid offline queue')
  for (const sale of legacy) {
    const key = itemKey(company, sale.clientKey)
    if (localStorage.getItem(key) === null) localStorage.setItem(key, JSON.stringify(sale))
  }
  // If storage fills up, keep the legacy array so the migration can be retried.
  localStorage.removeItem(scoped(company))
}

export function getQueuedSales(company: string): QueuedSale[] {
  migrateLegacy(company)
  const found: QueuedSale[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (!key?.startsWith(itemPrefix(company))) continue
    const raw = localStorage.getItem(key)
    if (raw === null) continue
    const sale: unknown = JSON.parse(raw)
    if (!validSale(sale)) throw new Error('Invalid offline queue')
    found.push(sale)
  }
  return found.sort((a, b) => a.createdAt - b.createdAt)
}

export function queueCashSale(company: string, body: QueuedSale['body']): QueuedSale {
  const existing = getQueuedSales(company)
  const duplicate = existing.find(sale => sale.clientKey === body.clientKey)
  if (duplicate) return duplicate
  if (existing.length >= 200) throw new Error('Offline buyurtmalar limiti (200) tugadi. Internetga ulaning.')
  const item: QueuedSale = { clientKey: body.clientKey, createdAt: Date.now(), body }
  if (!validSale(item)) throw new Error('Invalid offline sale')
  // Never claim success unless the record is durably written.
  localStorage.setItem(itemKey(company, body.clientKey), JSON.stringify(item))
  return item
}

/** Server accepted the replay as a reviewable conflict: it must leave the retry queue. */
export function isOfflineConflict(e: unknown): boolean {
  if (typeof e !== 'object' || e === null) return false
  const { status, detail } = e as { status?: number; detail?: { code?: string } }
  return status === 409 && detail?.code === 'offline_conflict'
}

export function removeQueuedSale(company: string, clientKey: string): void {
  migrateLegacy(company)
  localStorage.removeItem(itemKey(company, clientKey))
}

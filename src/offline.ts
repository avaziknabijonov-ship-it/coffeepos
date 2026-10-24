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
    cashGiven?: number
    clientKey: string
  }
}
const prefix = 'coffeepos-pending-sales-v1:'
const scoped = (company: string) => prefix + company

export function getQueuedSales(company: string): QueuedSale[] {
  try {
    const found: unknown = JSON.parse(localStorage.getItem(scoped(company)) || '[]')
    if (!Array.isArray(found)) return []
    return found.filter((x): x is QueuedSale =>
      typeof x === 'object' && x !== null &&
      typeof x.clientKey === 'string' && typeof x.createdAt === 'number' &&
      typeof x.body === 'object' && x.body !== null && x.body.clientKey === x.clientKey
    )
  } catch {
    return []
  }
}

export function queueCashSale(company: string, body: QueuedSale['body']): QueuedSale {
  const existing = getQueuedSales(company)
  if (existing.length >= 200) throw new Error('Offline buyurtmalar limiti (200) tugadi. Internetga ulaning.')
  const item: QueuedSale = { clientKey: body.clientKey, createdAt: Date.now(), body }
  // Never claim success unless the record is durably written.
  localStorage.setItem(scoped(company), JSON.stringify([...existing, item]))
  return item
}

export function removeQueuedSale(company: string, clientKey: string): void {
  const existing = getQueuedSales(company)
  // Acknowledge only the exact transaction returned by the backend.
  localStorage.setItem(scoped(company), JSON.stringify(existing.filter(x => x.clientKey !== clientKey)))
}

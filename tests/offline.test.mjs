import { test } from 'node:test'
import assert from 'node:assert/strict'

const store = new Map()
globalThis.localStorage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k), get length() { return store.size }, key: i => [...store.keys()][i] ?? null }
const { getQueuedSales, isOfflineConflict, queueCashSale, removeQueuedSale } = await import('../src/offline.ts')

const body = key => ({ clientKey: key, customer: '', items: [{ productId: 'latte', size: 'M', modIds: [], qty: 1 }], discountPct: 0, payment: 'naqd' })

test('queue is company scoped, durable and acknowledged per clientKey', () => {
  queueCashSale('a', body('k1aaaaaaaaaaaa'))
  queueCashSale('a', body('k2aaaaaaaaaaaa'))
  queueCashSale('b', body('k3aaaaaaaaaaaa'))
  assert.equal(getQueuedSales('a').length, 2)
  removeQueuedSale('a', 'k1aaaaaaaaaaaa')
  assert.deepEqual(getQueuedSales('a').map(s => s.clientKey), ['k2aaaaaaaaaaaa'])
  assert.equal(getQueuedSales('b').length, 1)
})

test('corrupted storage never yields fake sales', () => {
  store.set('coffeepos-pending-sales-v1:c', '{"not":"array"}')
  assert.throws(() => getQueuedSales('c'))
  store.set('coffeepos-pending-sales-v1:c', '[{"clientKey":"x","createdAt":1,"body":{"clientKey":"y"}}]')
  assert.throws(() => getQueuedSales('c'))
})

test('only explicit server conflicts leave the retry queue', () => {
  assert.equal(isOfflineConflict({ status: 409, detail: { code: 'offline_conflict' } }), true)
  assert.equal(isOfflineConflict({ status: 409, detail: 'Draft clientKey already used' }), false)
  assert.equal(isOfflineConflict({ status: 503, detail: { code: 'offline_conflict' } }), false)
  assert.equal(isOfflineConflict(null), false)
})


test('legacy queue migrates once and acknowledged sales do not reappear', () => {
  const sale = { clientKey: 'legacy-sale', createdAt: 1, body: body('legacy-sale') }
  store.set('coffeepos-pending-sales-v1:legacy', JSON.stringify([sale]))
  assert.equal(getQueuedSales('legacy').length, 1)
  assert.equal(store.has('coffeepos-pending-sales-v1:legacy'), false)
  removeQueuedSale('legacy', sale.clientKey)
  assert.deepEqual(getQueuedSales('legacy'), [])
})

test('acknowledging one tab sale preserves a newly enqueued sale in another tab', () => {
  queueCashSale('tabs', body('tab-a'))
  const tabASnapshot = getQueuedSales('tabs')
  queueCashSale('tabs', body('tab-b'))
  removeQueuedSale('tabs', tabASnapshot[0].clientKey)
  assert.deepEqual(getQueuedSales('tabs').map(x => x.clientKey), ['tab-b'])
  assert.equal([...store.keys()].filter(k => k.startsWith('coffeepos-pending-sales-v1:tabs:sale:')).length, 1)
})

test('retrying enqueue with the same clientKey preserves original sale', () => {
  queueCashSale('dedupe', body('same-key'))
  queueCashSale('dedupe', { ...body('same-key'), discountPct: 50 })
  assert.equal(getQueuedSales('dedupe').length, 1)
  assert.equal(getQueuedSales('dedupe')[0].body.discountPct, 0)
})

test('storage quota failure is surfaced and legacy data survives incomplete migration', () => {
  const key = 'coffeepos-pending-sales-v1:full'
  const raw = JSON.stringify([{ clientKey: 'migrate', createdAt: 1, body: body('migrate') }])
  store.set(key, raw)
  const write = localStorage.setItem
  localStorage.setItem = () => { throw new Error('QuotaExceededError') }
  try {
    assert.throws(() => getQueuedSales('full'), /QuotaExceededError/)
    assert.equal(store.get(key), raw)
    assert.throws(() => queueCashSale('empty-full', body('no-room')), /QuotaExceededError/)
  } finally { localStorage.setItem = write }
  assert.equal(getQueuedSales('full').length, 1)
})

test('invalid legacy data is preserved and never overwritten by a new sale', () => {
  const key = 'coffeepos-pending-sales-v1:broken'
  store.set(key, '{bad json')
  assert.throws(() => queueCashSale('broken', body('new-sale')))
  assert.equal(store.get(key), '{bad json')
})

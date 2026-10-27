import { test } from 'node:test'
import assert from 'node:assert/strict'

const store = new Map()
globalThis.localStorage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) }
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
  assert.deepEqual(getQueuedSales('c'), [])
  store.set('coffeepos-pending-sales-v1:c', '[{"clientKey":"x","createdAt":1,"body":{"clientKey":"y"}}]')
  assert.deepEqual(getQueuedSales('c'), [])
})

test('only explicit server conflicts leave the retry queue', () => {
  assert.equal(isOfflineConflict({ status: 409, detail: { code: 'offline_conflict' } }), true)
  assert.equal(isOfflineConflict({ status: 409, detail: 'Draft clientKey already used' }), false)
  assert.equal(isOfflineConflict({ status: 503, detail: { code: 'offline_conflict' } }), false)
  assert.equal(isOfflineConflict(null), false)
})

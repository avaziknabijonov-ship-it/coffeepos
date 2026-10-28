import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'

test('a logout during replay cannot send the rest of the old queue under a new token', async () => {
  const storage = new Map()
  globalThis.localStorage = {
    getItem: k => storage.get(k) ?? null,
    setItem: (k, v) => storage.set(k, String(v)),
    removeItem: k => storage.delete(k),
    get length() { return storage.size }, key: i => [...storage.keys()][i] ?? null,
  }
  globalThis.document = { documentElement: {} }
  const originalFetch = globalThis.fetch
  const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  let store
  try {
    const reply = data => new Response(JSON.stringify(data), { status: 200 })
    const calls = []
    let replayStarted
    let finishReplay
    const started = new Promise(resolve => { replayStarted = resolve })
    globalThis.fetch = async (path, init) => {
      if (path === '/api/auth/login') return reply({ token: 'old-token', staff: { id: 1, name: 'A', role: 'owner' }, company: { slug: 'a', name: 'A' } })
      if (path === '/api/menu') return reply({ ingredients: [], products: [], modifiers: [], categories: [] })
      if (path.startsWith('/api/sync')) return reply({ orders: [], stock: {}, shift: null })
      if (path === '/api/orders') {
        calls.push({ token: init.headers.Authorization, key: JSON.parse(init.body).clientKey })
        replayStarted()
        return new Promise(resolve => { finishReplay = () => resolve(reply({ id: 'accepted' })) })
      }
      throw new Error('Unexpected ' + path)
    }
    store = await server.ssrLoadModule('/src/store.ts')
    const queue = await server.ssrLoadModule('/src/offline.ts')
    await store.login('a', '1111')
    const body = key => ({ clientKey: key, customer: '', items: [], discountPct: 0, payment: 'naqd' })
    queue.queueCashSale('a', body('sale-one'))
    queue.queueCashSale('a', body('sale-two'))
    const syncing = store.sync()
    await started
    store.logout()
    localStorage.setItem('coffeepos-token', 'new-token')
    finishReplay()
    await syncing
    assert.deepEqual(calls, [{ token: 'Bearer old-token', key: 'sale-one' }])
    assert.deepEqual(queue.getQueuedSales('a').map(x => x.clientKey), ['sale-two'])
    assert.equal(localStorage.getItem('coffeepos-token'), 'new-token')
  } finally {
    store?.logout()
    globalThis.fetch = originalFetch
    await server.close()
  }
})

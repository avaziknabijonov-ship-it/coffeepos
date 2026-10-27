/** Local test stack only. npm ci; npx playwright install chromium;
 * UI_BASE_URL=http://127.0.0.1:5173 node scripts/browser_regression.mjs
 * CHROMIUM_EXECUTABLE_PATH optionally selects an installed browser.
 * Seeds a disposable tenant; never point this script at production.
 */
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { chromium, request } from 'playwright'

const base = process.env.UI_BASE_URL || 'http://127.0.0.1:5173'
const url = new URL(base)
assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), 'Only a local test stack is allowed')
const http = await request.newContext({ baseURL: base })
const slug = 'browser-' + crypto.randomUUID().slice(0, 8)
const call = async (path, data, headers) => {
  const response = await http.post(path, { data, headers })
  assert.ok(response.ok(), `${path}: ${response.status()} ${await response.text()}`)
  return response.json()
}
const auth = await call('/api/auth/register', { companyName: 'Browser Test', slug, ownerName: 'Tester', ownerPin: '1111' })
const headers = { Authorization: 'Bearer ' + auth.token }
await call('/api/shifts/open', { openingCash: 0 }, headers)
const menu = await (await http.get('/api/menu', { headers })).json()
await call('/api/inventories', { lines: menu.ingredients.map(i => ({ ing: i.id, counted: 10000 })) }, headers)
const area = await call('/api/areas', { name: 'Test Hall' }, headers)
const table = await call('/api/tables', { areaId: area.id, name: 'Test Table', seats: 2 }, headers)
await call('/api/drafts', { clientKey: crypto.randomUUID().replaceAll('-', ''), customer: 'Test Guest',
  items: [{ productId: 'latte', size: 'M', modIds: [], qty: 1 }], tableId: table.id, service: 'dine_in' }, headers)
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || undefined,
  args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--disable-software-rasterizer'],
})
const contexts = []
const errors = []
const checked = []
async function pageFor(lang, theme) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  contexts.push(context)
  await context.addInitScript(({ token, slug, lang, theme }) => {
    localStorage.setItem('coffeepos-token', token)
    localStorage.setItem('coffeepos-company', slug)
    localStorage.setItem('coffeepos-lang', lang)
    localStorage.setItem('coffeepos-theme', theme)
  }, { token: auth.token, slug, lang, theme })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(base + '/#admin')
  await page.getByRole('button', { name: lang === 'uz' ? 'Zal va stollar' : 'Залы и столы', exact: true }).waitFor()
  return page
}
async function contrast(locator) {
  return locator.evaluate(el => {
    const ctx = document.createElement('canvas').getContext('2d')
    const rgb = color => {
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1)
      return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3)
    }
    const luminance = color => rgb(color).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
      .reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0)
    let parent = el.parentElement
    while (parent.parentElement && getComputedStyle(parent).backgroundColor === 'rgba(0, 0, 0, 0)') parent = parent.parentElement
    const a = luminance(getComputedStyle(el).color)
    const b = luminance(getComputedStyle(parent).backgroundColor)
    return (Math.max(a, b) + .05) / (Math.min(a, b) + .05)
  })
}
async function screenshot(page, name) {
  if (!process.env.UI_SCREENSHOT_DIR) return
  await mkdir(process.env.UI_SCREENSHOT_DIR, { recursive: true })
  await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, name + '.png'), mask: [page.locator('code')] })
}
async function waitFor(test, label) {
  for (let i = 0; i < 100; i++) {
    if (await test()) return
    await new Promise(r => setTimeout(r, 100))
  }
  assert.fail(label)
}
try {
  for (const lang of ['uz', 'ru']) for (const theme of ['light', 'dark']) {
    const page = await pageFor(lang, theme)
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme)
    const themeText = lang === 'uz' ? (theme === 'dark' ? 'Tun' : 'Kun') : (theme === 'dark' ? 'Тёмная' : 'Светлая')
    assert.ok(await page.getByRole('button', { name: themeText, exact: true }).isVisible())
    await page.getByRole('button', { name: lang === 'uz' ? 'Zal va stollar' : 'Залы и столы', exact: true }).click()
    const occupied = page.locator('main div.font-medium').filter({ hasText: 'Test Table' })
    await occupied.waitFor()
    assert.match(await occupied.innerText(), lang === 'uz' ? /Band/ : /Занят/)
    // Regression for light occupied-card background receiving light dark-theme text.
    await screenshot(page, `${lang}-${theme}-floor-before`)
    assert.ok(await contrast(occupied) >= 4.5, 'occupied table contrast')
    await screenshot(page, `${lang}-${theme}-floor`)
    checked.push(`${lang}/${theme}: occupied floor`)
    await page.getByRole('button', { name: lang === 'uz' ? 'Qurilmalar va oflayn' : 'Устройства и офлайн', exact: true }).click()
    await page.getByPlaceholder(lang === 'uz' ? 'Qurilma nomi' : 'Название устройства').fill('UI Test POS')
    await page.getByRole('button', { name: lang === 'uz' ? 'Ro‘yxatdan o‘tkazish' : 'Зарегистрировать', exact: true }).click()
    await page.locator('main code').waitFor()
    assert.ok(await contrast(page.locator('main code')) >= 4.5, 'device token banner contrast')
    await screenshot(page, `${lang}-${theme}-device`)
    checked.push(`${lang}/${theme}: device enrollment banner`)
    await page.getByRole('button', { name: lang === 'uz' ? 'Ishchi kassa oynasi' : 'Рабочая касса', exact: true }).click()
    await waitFor(() => page.evaluate(() => location.hash === '#kassa'), 'cashier navigation')
    await page.locator('.app-cashier').waitFor()
    const motto = await page.locator('.cashier-categories').getAttribute('data-motto')
    assert.equal(motto, lang === 'uz' ? 'Yaxshi qahva — yaxshi kun' : 'Хороший кофе — хороший день')
    await screenshot(page, `${lang}-${theme}-cashier`)
    checked.push(`${lang}/${theme}: cashier`)
  }
  // Two independent browser storages, with backend outage followed by reconnect.
  const a = await pageFor('uz', 'light')
  const b = await pageFor('uz', 'dark')
  for (const page of [a, b]) {
    await page.evaluate(async () => {
      window.testStore = await import('/src/store.ts')
      window.testData = await import('/src/data.ts')
      window.testQueue = await import('/src/offline.ts')
    })
    await page.route('**/api/**', route => route.abort())
  }
  const keys = []
  for (const page of [a, b]) {
    const key = await page.evaluate(async () => {
      const data = window.testData
      const p = data.PRODUCTS.find(p => p.id === 'latte')
      const item = data.buildItem(p, p.sizes.find(s => s.code === 'M'), [], 1)
      const order = await window.testStore.placeOrder([item], { customer: 'Offline Test', discountPct: 0,
        payment: 'naqd', expectedTotal: item.unitPrice, cashGiven: 100000 })
      if (!order.pendingSync) throw new Error('Expected a pending sale')
      return order.id.slice('offline:'.length)
    })
    keys.push(key)
    assert.equal(await page.evaluate(slug => window.testQueue.getQueuedSales(slug).length, slug), 1)
  }
  assert.notEqual(keys[0], keys[1])
  // Reload with UI assets available but all API traffic still unavailable.
  await a.reload()
  await a.getByRole('button', { name: 'Zal va stollar', exact: true }).waitFor()
  assert.equal(await a.evaluate(async slug => (await import('/src/offline.ts')).getQueuedSales(slug).length, slug), 1)
  checked.push('two browser contexts: durable cash queue and API-outage reload')
  for (const page of [a, b]) {
    await page.unroute('**/api/**')
    await page.evaluate(async () => (await import('/src/store.ts')).sync())
    await waitFor(() => page.evaluate(async slug => (await import('/src/offline.ts')).getQueuedSales(slug).length === 0, slug), 'queue drained')
    await page.evaluate(async () => (await import('/src/store.ts')).sync())
  }
  const state = await (await http.get('/api/sync', { headers })).json()
  assert.equal(state.orders.filter(o => o.customer === 'Offline Test').length, 2, 'no duplicate sales after repeated sync')
  checked.push('reconnect and repeated sync: exactly two server orders')
  assert.deepEqual(errors, [], 'browser runtime errors')
  console.log(JSON.stringify({ passed: checked.length, checks: checked }, null, 2))
} finally {
  await Promise.all(contexts.map(context => context.close()))
  await browser.close()
  await http.dispose()
}

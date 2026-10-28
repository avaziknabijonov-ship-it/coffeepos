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
    if (!localStorage.getItem('coffeepos-theme')) localStorage.setItem('coffeepos-theme', theme)
  }, { token: auth.token, slug, lang, theme })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(base + '/#admin')
  await page.locator('.admin-shell').waitFor()
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
  // Upload through the same picker used by managers for categories and products.
  const imagePage = await pageFor('uz', 'light')
  await imagePage.getByRole('button', { name: 'Menyu', exact: true }).click()
  await imagePage.getByRole('button', { name: 'Rasm', exact: true }).first().click()
  const picture = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGxkAAAAASUVORK5CYII=', 'base64')
  await imagePage.getByLabel('Qurilmadan rasm tanlash', { exact: true }).setInputFiles({ name: 'category.png', mimeType: 'image/png', buffer: picture })
  await waitFor(async () => (await imagePage.getByRole('textbox', { name: 'Rasm URL (https://...)', exact: true }).inputValue()).startsWith('/api/images/'), 'image uploaded')
  await imagePage.getByRole('button', { name: 'Saqlash', exact: true }).click()
  await imagePage.getByRole('dialog').waitFor({ state: 'hidden' })
  await imagePage.getByRole('button', { name: 'Yangi mahsulot', exact: true }).click()
  await imagePage.getByLabel('Qurilmadan rasm tanlash', { exact: true }).setInputFiles({ name: 'product.png', mimeType: 'image/png', buffer: picture })
  await waitFor(async () => (await imagePage.getByRole('textbox', { name: 'Rasm URL (https://...)', exact: true }).inputValue()).startsWith('/api/images/'), 'product image uploaded')
  await imagePage.getByRole('button', { name: 'Yopish', exact: true }).click()
  await imagePage.evaluate(() => { location.hash = 'kassa' })
  await imagePage.getByRole('region', { name: 'Zal xaritasi', exact: true }).getByRole('button', { name: 'Olib ketish', exact: true }).click()
  await imagePage.locator('.cashier-categories img').first().waitFor()
  assert.ok(await imagePage.locator('.cashier-categories img').first().evaluate(el => el.complete && el.naturalWidth > 0))
  await imagePage.reload()
  await imagePage.getByRole('region', { name: 'Zal xaritasi', exact: true }).getByRole('button', { name: 'Olib ketish', exact: true }).click()
  await imagePage.locator('.cashier-categories img').first().waitFor()
  await screenshot(imagePage, 'category-upload')
  checked.push('category upload persisted through reload; product file picker upload')
  const layoutPage = await pageFor('uz', 'light')
  await layoutPage.getByRole('button', { name: 'Zal va stollar', exact: true }).click()
  await layoutPage.getByRole('button', { name: 'Test Table · Band', exact: true }).click()
  await layoutPage.getByRole('combobox', { name: 'Shakl', exact: true }).selectOption('rectangle')
  await layoutPage.getByRole('spinbutton', { name: 'Chapdan', exact: true }).fill('220')
  await layoutPage.getByRole('button', { name: 'Saqlash', exact: true }).click()
  await layoutPage.getByRole('spinbutton', { name: 'Chapdan', exact: true }).waitFor({ state: 'hidden' })
  await layoutPage.reload()
  await layoutPage.getByRole('button', { name: 'Zal va stollar', exact: true }).click()
  const layoutButton = layoutPage.getByRole('button', { name: 'Test Table · Band', exact: true })
  await layoutButton.waitFor()
  assert.equal(await layoutButton.evaluate(el => el.style.left), '220px')
  await screenshot(layoutPage, 'floor-layout-editor')
  await layoutPage.evaluate(() => { location.hash = 'kassa' })
  await layoutPage.getByRole('region', { name: 'Zal xaritasi', exact: true }).waitFor()
  assert.equal(await layoutPage.getByRole('dialog', { name: 'Zal xaritasi', exact: true }).count(), 0)
  assert.equal(await layoutPage.locator('.cashier-checkout').count(), 0, 'floor replaces checkout, without a modal backdrop')
  const floorBounds = await layoutPage.getByRole('region', { name: 'Zal xaritasi', exact: true }).boundingBox()
  assert.equal(floorBounds.x, 0)
  assert.equal(floorBounds.width, 1440)
  const cashierTable = layoutPage.getByRole('button', { name: 'Test Table · Band', exact: true })
  await cashierTable.waitFor()
  assert.equal(await cashierTable.evaluate(el => el.style.left), '220px')
  await screenshot(layoutPage, 'floor-layout-cashier')
  await cashierTable.click()
  await layoutPage.getByText('Stol: Test Table', { exact: true }).waitFor()
  const restoredCount = await layoutPage.locator('.cashier-cart-row').count()
  await layoutPage.getByRole('button', { name: 'Zal xaritasi', exact: true }).click()
  await layoutPage.getByRole('region', { name: 'Zal xaritasi', exact: true }).getByRole('button', { name: 'Yopish', exact: true }).click()
  assert.equal(await layoutPage.locator('.cashier-cart-row').count(), restoredCount, 'return from floor preserves the open order')
  checked.push('floor is the main full-width view; table selection and return preserve the order')
  const sampleArea = await call('/api/areas', { name: 'Layout sample' }, headers)
  for (const name of [...Array.from({ length: 14 }, (_, i) => String(i + 1)), 'Bar', 'VIP']) {
    await call('/api/tables', { areaId: sampleArea.id, name, seats: 2 }, headers)
  }
  await layoutPage.reload()
  await layoutPage.getByRole('region', { name: 'Zal xaritasi', exact: true }).waitFor()
  await layoutPage.getByRole('button', { name: 'Layout sample', exact: true }).click()
  await layoutPage.getByRole('button', { name: 'VIP · Bo‘sh', exact: true }).waitFor()
  await screenshot(layoutPage, 'floor-reference-layout')
  await layoutPage.getByRole('button', { name: 'VIP · Bo‘sh', exact: true }).click()
  const opening = layoutPage.getByRole('dialog', { name: 'Mehmonlar soni', exact: true })
  await opening.getByRole('button', { name: '3', exact: true }).click()
  await opening.getByRole('button', { name: 'Davom ettirish', exact: true }).click()
  await layoutPage.getByText('Stol: VIP', { exact: true }).waitFor()
  await layoutPage.locator('.cashier-checkout').getByRole('button', { name: 'Mehmon 3', exact: true }).waitFor()
  checked.push('empty table asks guest count before menu and creates the selected guest tabs')
  const guestPage = await pageFor('uz', 'light')
  await guestPage.evaluate(() => { location.hash = 'kassa' })
  await guestPage.getByRole('region', { name: 'Zal xaritasi', exact: true }).getByRole('button', { name: 'Olib ketish', exact: true }).click()
  await guestPage.locator('.cashier-categories button').filter({ hasText: 'Espresso' }).first().click()
  await guestPage.locator('.cashier-product-card').filter({ hasText: 'Espresso' }).first().click()
  await guestPage.getByRole('button', { name: '+ Mehmon qo‘shish', exact: true }).click()
  await guestPage.locator('.cashier-product-card').filter({ hasText: 'Espresso' }).first().click()
  assert.equal(await guestPage.locator('.cashier-checkout').getByText('Mehmon 2', { exact: true }).count(), 2)
  await guestPage.getByRole('button', { name: 'Chek amallari', exact: true }).click()
  await guestPage.getByRole('button', { name: 'Saqlab qo‘yish', exact: true }).click()
  await guestPage.locator('.cashier-checkout').getByText("Savat bo'sh. Mahsulotni tanlang.", { exact: true }).waitFor()
  await guestPage.getByRole('button', { name: 'Chek amallari', exact: true }).click()
  await guestPage.getByRole('button', { name: 'Saqlangan buyurtmalar', exact: true }).click()
  const draftRow = guestPage.locator('div.flex.flex-wrap.items-center.gap-3.rounded-xl.border.p-3').filter({ hasText: 'Mijoz' }).last()
  await draftRow.getByRole('button', { name: 'Davom ettirish', exact: true }).click()
  await guestPage.locator('.cashier-checkout').getByRole('button', { name: 'Mehmon 2', exact: true }).waitFor()
  await screenshot(guestPage, 'guest-order-cashier')
  checked.push('two guests add same product separately, parked draft restores guest labels')
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1024, height: 600 }]) {
    await guestPage.setViewportSize(viewport)
    const list = await guestPage.locator('.cashier-checkout .cashier-cart-items').boundingBox()
    const pay = await guestPage.locator('.cashier-checkout .cashier-cart-footer').boundingBox()
    assert.ok(list.height >= 160, 'cart keeps space for products at laptop heights')
    assert.ok(pay.y + pay.height <= viewport.height + 1, 'payment stays in viewport')
    await guestPage.locator('.cashier-checkout .cashier-cart-row').first().getByRole('button', { name: "Ko'paytirish", exact: true }).click()
    await screenshot(guestPage, `compact-cart-${viewport.width}`)
  }
  await guestPage.setViewportSize({ width: 1440, height: 1000 })
  checked.push('compact cart: product controls and payment usable at 1366x768 and 1024x600')

  await guestPage.getByRole('button', { name: 'Chek amallari', exact: true }).click()
  await guestPage.getByRole('textbox', { name: 'Chekka izoh', exact: true }).fill('UI order note')
  await guestPage.getByRole('spinbutton', { name: 'Mehmonlar soni', exact: true }).fill('4')
  await screenshot(guestPage, 'order-actions-menu')
  const staffSelect = guestPage.getByRole('combobox', { name: 'Mas’ul xodimni almashtirish', exact: true })
  await waitFor(async () => (await staffSelect.locator('option').count()) > 1, 'staff choices loaded')
  await staffSelect.selectOption(await staffSelect.locator('option').nth(1).getAttribute('value'))
  await guestPage.getByRole('dialog').waitFor({ state: 'hidden' })
  await guestPage.getByRole('button', { name: 'Chek amallari', exact: true }).click()
  await guestPage.getByRole('button', { name: 'Chekni ajratish · Mehmon 1', exact: true }).click()
  await waitFor(async () => {
    const drafts = await (await http.get('/api/drafts', { headers })).json()
    return drafts.filter(d => d.note === 'UI order note').length === 2
  }, 'split saved both drafts with metadata')
  checked.push('order actions: note, guest count, assignment and guest split persisted')

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
    await page.getByRole('region', { name: lang === 'uz' ? 'Zal xaritasi' : 'Карта зала', exact: true }).getByRole('button', { name: lang === 'uz' ? 'Olib ketish' : 'С собой', exact: true }).click()
    const motto = await page.locator('.cashier-categories').getAttribute('data-motto')
    assert.equal(motto, lang === 'uz' ? 'Yaxshi qahva — yaxshi kun' : 'Хороший кофе — хороший день')
    await screenshot(page, `${lang}-${theme}-cashier`)
    checked.push(`${lang}/${theme}: cashier`)
    const surface = page.locator('.cashier-checkout')
    const beforeTheme = await surface.evaluate(el => getComputedStyle(el).backgroundColor)
    const modeButton = page.getByRole('button', { name: lang === 'uz' ? (theme === 'dark' ? 'Tun' : 'Kun') : (theme === 'dark' ? 'Тёмная' : 'Светлая'), exact: true })
    await modeButton.click()
    const nextMode = theme === 'dark' ? 'system' : 'dark'
    await waitFor(() => page.evaluate(mode => localStorage.getItem('coffeepos-theme') === mode, nextMode), 'theme setting saved')
    if (theme === 'dark') {
      // System resolves light in this browser; test the explicit cycle to light too.
      await page.getByRole('button', { name: lang === 'uz' ? 'Avto' : 'Авто', exact: true }).click()
    }
    const afterTheme = await surface.evaluate(el => getComputedStyle(el).backgroundColor)
    assert.notEqual(beforeTheme, afterTheme, 'theme must change the actual cashier surface')
    const resolved = await page.evaluate(() => document.documentElement.dataset.theme)
    await page.reload()
    await waitFor(() => page.evaluate(expected => document.documentElement.dataset.theme === expected, resolved), 'theme survives reload')
    await page.getByRole('region', { name: lang === 'uz' ? 'Zal xaritasi' : 'Карта зала', exact: true }).getByRole('button', { name: lang === 'uz' ? 'Olib ketish' : 'С собой', exact: true }).click()
    assert.equal(await surface.evaluate(el => getComputedStyle(el).backgroundColor), afterTheme)
    assert.ok(await contrast(surface) >= 4.5, 'cart text contrast in the toggled theme')
    await screenshot(page, `${lang}-${theme}-theme-toggled`)
    checked.push(`${lang}/${theme}: actual cashier theme toggles and persists on reload`)

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
  // Older responses must never replace the report selected by a newer filter.
  const financePage = await pageFor('uz', 'light')
  const financeReport = await (await http.get('/api/reports/finance?days=30', { headers })).json()
  let releaseOldFinance
  let oldFinanceSeen = false
  const oldFinance = new Promise(resolve => { releaseOldFinance = resolve })
  await financePage.route('**/api/reports/finance?days=*', async route => {
    if (route.request().url().endsWith('days=30')) { oldFinanceSeen = true; await oldFinance }
    const current = route.request().url().endsWith('days=7')
    await route.fulfill({ json: { ...financeReport, revenue: current ? 777777 : 999999, daily: [] } })
  })
  await financePage.getByRole('button', { name: 'Moliya hisoboti', exact: true }).click()
  await waitFor(async () => oldFinanceSeen, 'old finance request started')
  await financePage.getByRole('combobox', { name: 'Davr', exact: true }).selectOption('7')
  await financePage.getByText("777 777 so'm", { exact: true }).waitFor()
  const oldFinanceResponse = financePage.waitForResponse(response => response.url().endsWith('/api/reports/finance?days=30'))
  releaseOldFinance()
  await oldFinanceResponse
  await financePage.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  assert.equal(await financePage.getByText("999 999 so'm", { exact: true }).count(), 0)
  assert.ok(await financePage.getByText("777 777 so'm", { exact: true }).isVisible())
  checked.push('finance: delayed old period cannot replace the new period report')

  const keyPage = await pageFor('uz', 'light')
  await keyPage.goto(base + '/#superadmin')
  let releaseOldKey
  let oldKeySeen = false
  const oldKey = new Promise(resolve => { releaseOldKey = resolve })
  await keyPage.route('**/api/superadmin/companies?*', async route => {
    oldKeySeen = true; await oldKey
    await route.fulfill({ json: { items: [], offset: 0, limit: 100 } })
  })
  await keyPage.locator('input[type="password"]').fill('disposable-old-key-for-regression-only')
  await keyPage.getByRole('button', { name: 'Kirish', exact: true }).click()
  await waitFor(async () => oldKeySeen, 'old platform-key request started')
  await keyPage.locator('input[type="password"]').fill('disposable-new-key-for-regression-only')
  const oldKeyResponse = keyPage.waitForResponse(response => response.url().includes('/api/superadmin/companies?'))
  releaseOldKey()
  await oldKeyResponse
  await keyPage.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  assert.equal(await keyPage.getByRole('heading', { name: 'Qahvaxonalar va litsenziyalar', exact: true }).count(), 0)
  checked.push('superadmin: response for an old key cannot restore authenticated UI')
  const licensePage = await pageFor('uz', 'light')
  await licensePage.goto(base + '/#superadmin')
  await licensePage.locator('input[type="password"]').fill(process.env.SUPERADMIN_KEY)
  await licensePage.getByRole('button', { name: 'Kirish', exact: true }).click()
  const companyRow = licensePage.locator('div.flex.flex-wrap.items-center.justify-between.gap-3.rounded-lg.border.p-3').filter({ hasText: slug })
  await companyRow.getByRole('checkbox', { name: 'Kalyanxona moduli · ' + slug, exact: true }).check()
  licensePage.on('dialog', dialog => dialog.accept())
  await companyRow.getByRole('button', { name: 'Berish', exact: true }).click()
  await waitFor(async () => (await (await http.get('/api/me', { headers })).json()).company.modules.includes('hookah'), 'licensed module enabled')
  const hookahPage = await pageFor('uz', 'light')
  await hookahPage.getByRole('button', { name: 'Kalyan va bar menyusi', exact: true }).click()
  await hookahPage.getByRole('heading', { name: 'Kalyanxona boshqaruvi', exact: true }).waitFor()
  await screenshot(hookahPage, 'licensed-hookah-admin')
  await hookahPage.getByRole('button', { name: 'Kalyanxona kassasi', exact: true }).click()
  await hookahPage.getByRole('region', { name: 'Zal xaritasi', exact: true }).getByRole('button', { name: 'Olib ketish', exact: true }).click()
  await hookahPage.getByRole('button', { name: 'Kalyanxona', exact: true }).click()
  await hookahPage.getByText('Stollar, mehmonlar va alohida cheklar', { exact: false }).waitFor()
  await screenshot(hookahPage, 'licensed-hookah-pos')
  const platformHeaders = { 'X-Superadmin-Key': process.env.SUPERADMIN_KEY }
  await call('/api/superadmin/companies/' + slug + '/subscription', { action: 'renew', modules: [] }, platformHeaders)
  assert.equal((await http.get('/api/modules/hookah', { headers })).status(), 403)
  await hookahPage.reload()
  await hookahPage.evaluate(() => { location.hash = 'kassa' })
  await hookahPage.getByRole('region', { name: 'Zal xaritasi', exact: true }).waitFor()
  assert.equal(await hookahPage.getByRole('button', { name: 'Kalyanxona', exact: true }).count(), 0)
  checked.push('superadmin checkbox grants hookah POS; removing license module hides workspace and denies API')
  assert.deepEqual(errors, [], 'browser runtime errors')
  console.log(JSON.stringify({ passed: checked.length, checks: checked }, null, 2))
} finally {
  await Promise.all(contexts.map(context => context.close()))
  await browser.close()
  await http.dispose()
}

import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import CashExpense from './CashExpense'
import CatalogImage from './CatalogImage'
import FloorMap from './FloorMap'
import type { TableLayout } from './floorLayout'
import { t, tCatalogName } from './i18n'
import { Banknote, CakeSlice, Check, Coffee, CreditCard, Leaf, Milk, Minus, Plus, Printer, Search, ShoppingBag, Smartphone, Snowflake, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { CATEGORIES, DEFAULT_MILK, MODIFIERS, PAYMENT_LABEL, PRODUCTS, buildItem, discountAmount, fmt, som, time } from './data'
import type { ModGroupId, Order, OrderItem, Payment, Product } from './data'
import { nextNumber, placeOrder, useAppState, sync } from './store'
import { OpenShift } from './Shift'

const CAT_ICON: Record<string, LucideIcon> = { espresso: Coffee, milk: Milk, cold: Snowflake, tea: Leaf, dessert: CakeSlice }
const CAT_TINT: Record<string, string> = {
  espresso: 'bg-amber-100 text-amber-800',
  milk: 'bg-orange-100 text-orange-800',
  cold: 'bg-sky-100 text-sky-800',
  tea: 'bg-emerald-100 text-emerald-800',
  dessert: 'bg-rose-100 text-rose-800',
}
type ParkedItem = { guest?: number; productId: string; size: string; modIds: string[]; qty: number }
type ParkedOrder = { note?: string; guestCount?: number; waiter?: string; id: number; clientKey: string; items: ParkedItem[]; customer: string; staff: string; version: number; updatedAt: number; tableId: number | null; service: 'takeaway' | 'dine_in' }
type FloorData = { areas: { id: number; name: string; active: boolean }[]; tables: { id: number; areaId: number; name: string; active: boolean; occupied: boolean; layout?: TableLayout | null; layoutVersion?: number; drafts: { id: number; staff: string }[] }[] }
const parkedItems = (items: OrderItem[]): ParkedItem[] => items.map(i => ({
  productId: i.productId, size: i.key.split('|')[1], modIds: i.modIds, qty: i.qty, guest: i.guest ?? 1,
}))
const restoreParkedItems = (items: ParkedItem[]): OrderItem[] => items.map(i => {
  const product = PRODUCTS.find(p => p.id === i.productId && p.active)
  const size = product?.sizes.find(s => s.code === i.size)
  if (!product || !size) throw new Error(t('Mahsulot mavjud emas yoki faol emas'))
  const item = buildItem(product, size, i.modIds, i.qty)
  const guest = i.guest ?? 1
  return { ...item, guest, key: guest > 1 ? item.key + '|guest:' + guest : item.key }
})

type BonusSnapshot = { phone: string; name: string; balance: number; enabled: boolean; earnPercent: number; redemptionLimitPercent: number }
const needsModal = (p: Product) => p.sizes.length > 1 || p.mods.length > 0

export default function Kassa({ onShift, hookah = false }: { onShift: () => void; hookah?: boolean }) {
  const { shift, menuVersion, orders, session } = useAppState()
  const [cat, setCat] = useState(() => hookah ? CATEGORIES.find(c => /kalyan|кальян|hookah/i.test(c.name))?.id ?? '' : '')
  const [note, setNote] = useState('')
  const [actionsOpen, setActionsOpen] = useState(false)
  const [actionFloor, setActionFloor] = useState<FloorData>({ areas: [], tables: [] })
  const [actionStaff, setActionStaff] = useState<{ id: number; name: string }[]>([])
  const [guest, setGuest] = useState(1)
  const [guests, setGuests] = useState(1)
  const [query, setQuery] = useState('')
  const [cart, setCart] = useState<OrderItem[]>([])
  const [customer, setCustomer] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [bonusInfo, setBonusInfo] = useState<BonusSnapshot | null>(null)
  const [bonusError, setBonusError] = useState('')
  const [bonusRedeem, setBonusRedeem] = useState(0)
  const [discountPct, setDiscountPct] = useState(0)
  const [promotion, setPromotion] = useState<{ name: string; percent: number } | null>(null)
  useEffect(() => {
    let active = true
    const refresh = () => api<{ promotion: { name: string; percent: number } | null }>('/api/promotions/active')
      .then(result => { if (active) setPromotion(result.promotion) }).catch(() => { /* Expected total protects stale pricing. */ })
    void refresh()
    const timer = window.setInterval(() => void refresh(), 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [session?.company.slug])

  const [modal, setModal] = useState<Product | null>(null)
  const [paying, setPaying] = useState(false)
  const [receipt, setReceipt] = useState<Order | null>(null)
  const [returnToFloor, setReturnToFloor] = useState(false)
  const [cartOpen, setCartOpen] = useState(false)
  const [expenseOpen, setExpenseOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [draftsOpen, setDraftsOpen] = useState(false)
  const [drafts, setDrafts] = useState<ParkedOrder[]>([])
  const [activeDraft, setActiveDraft] = useState<ParkedOrder | null>(null)
  const [draftError, setDraftError] = useState('')
  const [draftBusy, setDraftBusy] = useState(false)
  const [floorOpen, setFloorOpen] = useState(true)
  const [floorLoading, setFloorLoading] = useState(true)
  const [functionsOpen, setFunctionsOpen] = useState(false)
  const [floor, setFloor] = useState<FloorData>({ areas: [], tables: [] })
  const [areaId, setAreaId] = useState<number | null>(null)
  const [openingTable, setOpeningTable] = useState<{ id: number; name: string } | null>(null)
  const [openingGuests, setOpeningGuests] = useState('1')
  const [selectedTable, setSelectedTable] = useState<{ id: number; name: string } | null>(null)
  const openFloor = () => {
    setDraftError(''); setFloorLoading(true); setFloorOpen(true)
  }
  useEffect(() => {
    if (!floorOpen) return
    let active = true
    const refresh = () => api<FloorData>('/api/floor').then(result => {
      if (active) { setFloor(result); setFloorLoading(false); setDraftError('') }
    }).catch(e => { if (active) { setDraftError((e as Error).message); setFloorLoading(false) } })
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 10000)
    return () => { active = false; window.clearInterval(timer) }
  }, [floorOpen, session?.company.slug])
  const selectTable = async (table: FloorData['tables'][number]) => {
    if (draftBusy) return
    if (cart.length && !window.confirm(t('Joriy savat almashtirilsinmi?'))) return
    setDraftError(''); setDraftBusy(true)
    try {
      const available = await api<ParkedOrder[]>('/api/drafts')
      const matches = available.filter(d => d.tableId === table.id)
      if (matches.length > 1) { setDrafts(matches); setDraftsOpen(true); setFloorOpen(false); return }
      const draft = matches[0]
      if (!draft) { setOpeningGuests('1'); setOpeningTable({ id: table.id, name: table.name }); return }
      const items = draft ? restoreParkedItems(draft.items) : []
      clear(); setGuests(Math.max(draft?.guestCount ?? 1, ...items.map(i => i.guest ?? 1))); setNote(draft?.note ?? ''); setCart(items); setCustomer(draft?.customer ?? ''); setActiveDraft(draft ?? null)
      setSelectedTable({ id: table.id, name: table.name }); setFloorOpen(false)
    } catch (e) { setDraftError((e as Error).message) }
    finally { setDraftBusy(false) }
  }
  const loadDrafts = async () => {
    setDraftError('')
    try { setDrafts(await api<ParkedOrder[]>('/api/drafts')); setDraftsOpen(true) }
    catch (e) { setDraftError((e as Error).message); setDraftsOpen(true) }
  }
  const persistDraft = async () => {
    const body = { items: parkedItems(cart), customer: customer.trim(), note, guestCount: guests }
    const saved = activeDraft
      ? await api<ParkedOrder>('/api/drafts/' + activeDraft.id, { method: 'PATCH', body: { ...body, version: activeDraft.version } })
      : await api<ParkedOrder>('/api/drafts', { method: 'POST', body: { ...body, tableId: selectedTable?.id ?? null, service: selectedTable ? 'dine_in' : 'takeaway', clientKey: 'park_' + crypto.randomUUID().replace(/-/g, '') } })
    setActiveDraft(saved)
    return saved
  }
  const saveDraft = async () => {
    if (!cart.length || draftBusy) return
    setDraftBusy(true); setDraftError('')
    try {
      const saved = await persistDraft()
      setActiveDraft(null); setSelectedTable(null); clear()
      setDrafts(prev => [saved, ...prev.filter(d => d.id !== saved.id)])
      setCartOpen(false)
    } catch (e) { setDraftError((e as Error).message) }
    finally { setDraftBusy(false) }
  }
  const draftAction = async (action: string, body: object) => {
    if (!cart.length || draftBusy) return
    setDraftBusy(true); setDraftError('')
    try {
      const saved = await persistDraft()
      await api(`/api/drafts/${saved.id}/${action}`, { body: { ...body, version: saved.version } })
      const updated = (await api<ParkedOrder[]>('/api/drafts')).find(d => d.id === saved.id)
      if (!updated) throw new Error(t('Qoralama topilmadi'))
      setActiveDraft(updated); setCart(restoreParkedItems(updated.items))
      if (action === 'move') { setSelectedTable(actionFloor.tables.find(tb => tb.id === updated.tableId) ?? null) }
      setActionsOpen(false)
      if (action === 'split') { setDrafts(await api<ParkedOrder[]>('/api/drafts')); setDraftsOpen(true) }
    } catch (e) { setDraftError((e as Error).message) }
    finally { setDraftBusy(false) }
  }
  const clearOrder = async () => {
    if (draftBusy || !window.confirm(t('Buyurtma tozalansinmi?'))) return
    setDraftBusy(true); setDraftError('')
    try {
      if (activeDraft) await api('/api/drafts/' + activeDraft.id + '?version=' + activeDraft.version, { method: 'DELETE' })
      clear(); setActiveDraft(null); setSelectedTable(null); setActionsOpen(false)
    } catch (e) { setDraftError((e as Error).message) }
    finally { setDraftBusy(false) }
  }
  const openActions = async () => {
    setActionsOpen(true); setDraftError('')
    try {
      const latestFloor = await api<FloorData>('/api/floor'); setActionFloor(latestFloor); setFloor(latestFloor)
      if (session?.staff.role === 'owner' || session?.staff.role === 'admin') setActionStaff(await api<{ id: number; name: string }[]>('/api/staff'))
    } catch (e) { setDraftError((e as Error).message) }
  }
  const resumeDraft = (draft: ParkedOrder) => {
    if (cart.length && !window.confirm(t('Joriy savat almashtirilsinmi?'))) return
    try {
      const items = restoreParkedItems(draft.items)
      clear(); setGuests(Math.max(draft?.guestCount ?? 1, ...items.map(i => i.guest ?? 1))); setNote(draft?.note ?? ''); setCart(items); setCustomer(draft.customer); setActiveDraft(draft); setSelectedTable(floor.tables.find(tb => tb.id === draft.tableId) ?? null)
      setDraftsOpen(false); setCartOpen(true); setDraftError('')
    } catch (e) { setDraftError((e as Error).message) }
  }
  const removeDraft = async (draft: ParkedOrder) => {
    setDraftBusy(true); setDraftError('')
    try {
      await api('/api/drafts/' + draft.id + '?version=' + draft.version, { method: 'DELETE' })
      setDrafts(prev => prev.filter(d => d.id !== draft.id))
      if (activeDraft?.id === draft.id) setActiveDraft(null)
    } catch (e) { setDraftError((e as Error).message) }
    finally { setDraftBusy(false) }
  }
  const canCancel = session?.staff.role === 'owner' || session?.staff.role === 'admin' || Boolean(session?.staff.canCancelOrders)
  const canReprint = session?.staff.role === 'owner' || session?.staff.role === 'admin' || Boolean(session?.staff.canReprintReceipts)
  const cancelReceipt = async (o: Order) => {
    const reason = window.prompt(t('Otmena sababi (kamida 3 ta belgi):'))
    if (!reason || reason.trim().length < 3) return
    try { setHistoryError(''); await api('/api/orders/' + o.id + '/cancel', { method: 'POST', body: { reason: reason.trim() } }); await sync() }
    catch (e) { setHistoryError((e as Error).message) }
  }

  const products = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? PRODUCTS.filter((p) => (p.name.toLowerCase().includes(q) || tCatalogName(p.name).toLowerCase().includes(q))) : PRODUCTS.filter((p) => p.cat === cat)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cat, query, menuVersion])

  const subtotal = cart.reduce((s, i) => s + i.unitPrice * i.qty, 0)
  const effectivePercent = Math.max(discountPct, promotion?.percent ?? 0)
  const discount = discountAmount(subtotal, effectivePercent)
  const maxRedeem = bonusInfo?.enabled ? Math.min(bonusInfo.balance, Math.floor((subtotal - discount) * bonusInfo.redemptionLimitPercent / 100)) : 0
  const effectiveBonus = Math.min(bonusRedeem, maxRedeem)
  const total = subtotal - discount - effectiveBonus
  const count = cart.reduce((s, i) => s + i.qty, 0)

  const addToCart = (original: OrderItem) => {
    const item = { ...original, guest, key: guest > 1 ? original.key + '|guest:' + guest : original.key }
    setCart((c) => {
      const same = c.find((x) => x.key === item.key)
      return same ? c.map((x) => (x.key === item.key ? { ...x, qty: x.qty + item.qty } : x)) : [...c, item]
    })
  }
  const changeQty = (key: string, d: number) =>
    setCart((c) => c.map((x) => (x.key === key ? { ...x, qty: x.qty + d } : x)).filter((x) => x.qty > 0))
  const clear = () => {
    setCart([])
    setGuest(1); setGuests(1); setNote('')
    setCustomer('')
    setDiscountPct(0)
    setCustomerPhone('')
    setBonusInfo(null)
    setBonusRedeem(0)
    setBonusError('')
  }
  const onTile = (p: Product) => (needsModal(p) ? setModal(p) : addToCart(buildItem(p, p.sizes[0], [], 1)))

  const confirmPayment = async (payment: Payment, cashGiven?: number, paymentParts?: { method: Exclude<Payment, "split">; amount: number }[]) => {
    let checkoutDraft = activeDraft
    if (selectedTable && !checkoutDraft) {
      checkoutDraft = await api<ParkedOrder>('/api/drafts', { method: 'POST', body: { items: parkedItems(cart), customer: customer.trim(), note, guestCount: guests, tableId: selectedTable.id, service: 'dine_in', clientKey: 'park_' + crypto.randomUUID().replace(/-/g, '') } })
      setActiveDraft(checkoutDraft)
    }
    const order = await placeOrder(cart, { customer: customer.trim(), note, guestCount: guests, discountPct, expectedTotal: total, automaticDiscount: !!promotion, payment, cashGiven, paymentParts,
      customerPhone: bonusInfo?.enabled ? customerPhone.trim() : '', bonusRedeem: effectiveBonus, ...(checkoutDraft ? { draftId: checkoutDraft.id, draftVersion: checkoutDraft.version } : {}) })
    setPaying(false)
    setCartOpen(false)
    clear()
    setReturnToFloor(selectedTable !== null)
    setReceipt(order)
    setActiveDraft(null)
    setSelectedTable(null)
  }

  const loadBonus = async () => {
    setBonusError(''); setBonusInfo(null); setBonusRedeem(0)
    try { setBonusInfo(await api<BonusSnapshot>('/api/bonus/customers/' + encodeURIComponent(customerPhone.trim()))) }
    catch (e) { setBonusError((e as Error).message) }
  }
  const cartPanel = (
    <Cart
      hookah={hookah} onActions={openActions} guest={guest} guests={guests} setGuest={setGuest} addGuest={() => { if (guests < 50) { setGuests(guests + 1); setGuest(guests + 1) } }} number={nextNumber()} cart={cart} customer={customer} setCustomer={setCustomer}
      customerPhone={customerPhone} setCustomerPhone={v => { setCustomerPhone(v); setBonusInfo(null); setBonusRedeem(0) }}
      bonusInfo={bonusInfo} bonusError={bonusError} bonusRedeem={effectiveBonus} setBonusRedeem={setBonusRedeem} loadBonus={loadBonus} maxRedeem={maxRedeem}
      appliedDiscountPct={effectivePercent} subtotal={subtotal} discount={discount} total={total}
      changeQty={changeQty} draftError={draftError} onPay={() => setPaying(true)} onClose={cartOpen ? () => setCartOpen(false) : undefined}
    />
  )

  if (!shift) return <OpenShift canOpen />

  return (
    <div className={`cashier-warm cashier-reference ${hookah ? 'hookah-cashier' : ''} flex h-full min-h-0`}>


      {!floorOpen && <>
      <main className="cashier-products flex min-w-0 flex-1 flex-col">
        {hookah && <div className="border-b bg-sky-50 px-4 py-3 text-sm font-semibold text-sky-900">{t('Kalyanxona')} · {t('Stollar, mehmonlar va alohida cheklar')}</div>}
        {promotion && <p className="bg-amber-100 p-2 text-sm font-semibold">{t('Happy Hour')}: {promotion.name} · {promotion.percent}% · {t('Chegirmalar qo‘shilmaydi; kattarog‘i olinadi')}</p>}
        <div className="space-y-3 border-b border-stone-200 bg-white p-3">
          <div className="flex flex-wrap gap-2">
          <button onClick={() => { setCat(''); setQuery('') }} className="rounded-xl border px-3 py-2 text-sm font-bold">{t('Barcha kategoriyalar')}</button>
          <button onClick={openFloor} className="rounded-xl bg-sky-700 px-4 py-2 text-sm font-bold text-white">{t('Zal xaritasi')}</button>
          <button onClick={() => setFunctionsOpen(true)} className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-bold">{t('Funksiyalar')}</button>
          {selectedTable && <span className="self-center rounded-lg bg-sky-100 px-3 py-2 text-sm font-bold text-sky-900">{t('Stol')}: {selectedTable.name}</span>}
          <label className="flex flex-1 items-center gap-2 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2.5 focus-within:border-amber-500">
            <Search className="size-4 text-stone-400" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('Mahsulot qidirish')} className="w-full bg-transparent outline-none" />
            {query && <button onClick={() => setQuery('')} aria-label={t('Tozalash')}><X className="size-4 text-stone-400" /></button>}
          </label>
          </div>
          <div className="-mx-3 flex gap-2 overflow-x-auto px-3 md:hidden">
            {CATEGORIES.map((c) => (
              <button key={c.id} onClick={() => { setCat(c.id); setQuery('') }}
                className={`shrink-0 rounded-full px-4 py-2 text-sm font-medium ${!query && cat === c.id ? 'bg-stone-900 text-white' : 'bg-stone-100 text-stone-700'}`}>
                {tCatalogName(c.name)}
              </button>
            ))}
          </div>
        </div>
      {!cat && !query && <>      <aside data-motto={t('Yaxshi qahva — yaxshi kun')} className="cashier-categories grid grid-cols-2 gap-3 border-b border-stone-200 bg-stone-100 p-3 sm:grid-cols-3 lg:grid-cols-4">
        {CATEGORIES.map((c) => {
          const active = !query && cat === c.id
          return (
            <button key={c.id} onClick={() => { setCat(c.id); setQuery('') }}
              className={`flex flex-col items-start gap-2 overflow-hidden rounded-xl p-2 text-left font-medium ${active ? 'bg-stone-900 text-white shadow' : 'bg-white text-stone-700 hover:bg-stone-200'}`}>
              <CatalogImage src={c.imageUrl} alt={tCatalogName(c.name)} className="h-20 w-full rounded-lg object-cover" />{tCatalogName(c.name)}
            </button>
          )
        })}
      </aside></>}
        <div className="cashier-product-grid grid flex-1 grid-cols-2 content-start gap-3 overflow-y-auto p-3 pb-24 sm:grid-cols-3 md:pb-3 xl:grid-cols-4">
          {products.map((p) => {
            const Icon = CAT_ICON[p.cat] ?? Coffee
            const minPrice = Math.min(...p.sizes.map((s) => s.price))
            return (
              <button key={p.id} onClick={() => onTile(p)} disabled={!p.active}
                className="cashier-product-card group relative flex min-h-60 flex-col justify-between overflow-hidden rounded-2xl border border-stone-200 bg-white p-3 text-left shadow-sm transition-all duration-150 hover:-translate-y-0.5 hover:border-amber-400 hover:shadow-lg active:scale-[0.98] disabled:opacity-40">
                 {p.imageUrl ? <CatalogImage src={p.imageUrl} alt={tCatalogName(p.name)} className="cashier-product-photo mb-2 h-36 w-full rounded-xl object-cover transition-transform duration-200 group-hover:scale-[1.02]" /> :
                   <span className="cashier-product-fallback mb-2 grid h-36 w-full place-items-center rounded-xl"><span className={`cashier-fallback-icon grid size-16 place-items-center rounded-full ${CAT_TINT[p.cat] ?? 'bg-stone-100 text-stone-700'}`}><Icon className="size-9" /></span></span>}
                {!p.active && <span className="absolute right-2 top-2 rounded bg-red-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">{t('Stop')}</span>}
                <span>
                  <span className="block text-[15px] font-bold leading-tight text-stone-900">{tCatalogName(p.name)}</span>
                  <span className="mt-1 block text-sm font-medium text-amber-700">
                    {p.sizes.length > 1 ? t('{p} dan', { p: fmt(minPrice) }) : som(minPrice)}
                    {p.sizes.length > 1 && <span className="ml-1 text-xs text-stone-400">· {p.sizes.map((s) => s.label).join('/')}</span>}
                  </span>
                  <span className="cashier-add-button mt-3 flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-bold"><Plus className="size-4" />{t("Qo'shish")}</span>
                </span>
              </button>
            )
          })}
          {products.length === 0 && cat && <p className="col-span-full py-12 text-center text-stone-500">{t('Hech narsa topilmadi.')}</p>}
        </div>
      </main>

      <aside className="cashier-checkout order-first hidden w-80 shrink-0 border-l border-stone-200 bg-white md:flex lg:w-96">{cartPanel}</aside>

      {count > 0 && !cartOpen && (
        <div className="fixed inset-x-0 bottom-0 z-30 p-3 md:hidden">
          <button onClick={() => setCartOpen(true)} className="flex w-full items-center justify-between rounded-2xl bg-stone-900 px-4 py-4 font-semibold text-white shadow-lg">
            <span className="flex items-center gap-2"><ShoppingBag className="size-5" />{t('Savat')} · {t('{n} ta', { n: count })}</span>
            <span>{som(total)}</span>
          </button>
        </div>
      )}
      {cartOpen && <div className="fixed inset-0 z-40 flex bg-white md:hidden">{cartPanel}</div>}

      </>}
      {floorOpen && <section role="region" aria-label={t('Zal xaritasi')} className="cashier-floor flex h-full min-h-0 w-full flex-col overflow-hidden bg-white text-stone-900">
        <div className="flex shrink-0 items-center justify-between border-b p-4"><h2 className="text-xl font-bold">{t('Zal xaritasi')}</h2><button onClick={() => setFunctionsOpen(true)} className="ml-auto mr-3 rounded-lg border px-4 py-2 font-semibold">{t('Funksiyalar')}</button>{!selectedTable && !cart.length ? <button onClick={() => setFloorOpen(false)} className="rounded-lg border px-4 py-2">{t('Olib ketish')}</button> : <button onClick={() => setFloorOpen(false)} aria-label={t('Yopish')}><X /></button>}</div>
        <div className="flex shrink-0 flex-wrap gap-2 border-b p-3"><button onClick={() => setAreaId(null)} className={`rounded-lg px-4 py-2 ${areaId === null ? 'bg-slate-800 text-white' : 'bg-stone-100'}`}>{t('Barcha zallar')}</button>{floor.areas.filter(a => a.active).map(a => <button key={a.id} onClick={() => setAreaId(a.id)} className={`rounded-lg px-4 py-2 ${areaId === a.id ? 'bg-slate-800 text-white' : 'bg-stone-100'}`}>{a.name}</button>)}</div>
        <div className="min-h-0 flex-1 overflow-y-auto bg-slate-100 p-5"><p className="mb-4 text-sm text-slate-600">{t('Stolni tanlang')} · <span className="text-sky-700">● {t('Band')}</span> · ● {t('Bo‘sh')}</p>{draftError && <p role="alert" className="mb-3 text-red-700">{draftError}</p>}
          {floor.areas.filter(a => a.active && (areaId === null || a.id === areaId)).map(a => <section key={a.id} className="mb-4"><h3 className="mb-2 font-semibold">{a.name}</h3><FloorMap tables={floor.tables.filter(tb => tb.active && tb.areaId === a.id)} onSelect={tb => { const table = floor.tables.find(x => x.id === tb.id); if (table) void selectTable(table) }} /></section>)}
          {floorLoading && <p role="status" className="py-6 text-center">{t('Yuklanmoqda…')}</p>}
          {!floorLoading && !draftError && !floor.tables.some(tb => tb.active) && <p className="py-8 text-center text-slate-600">{t('Stollar hali yaratilmagan. Admin bo‘limida zal va stollarni qo‘shing.')}</p>}
        </div></section>}
      {openingTable && <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4"><form role="dialog" aria-modal="true" aria-label={t('Mehmonlar soni')} className="w-full max-w-sm space-y-5 rounded-2xl bg-white p-6 text-stone-900 shadow-xl" onSubmit={e => {
        e.preventDefault()
        const count = Number(openingGuests)
        if (!Number.isInteger(count) || count < 1 || count > 50) return
        clear(); setGuests(count); setActiveDraft(null); setSelectedTable(openingTable)
        setOpeningTable(null); setFloorOpen(false)
      }}>
        <h2 className="text-xl font-bold">{t('Stol')}: {openingTable.name}</h2>
        <label className="block font-semibold">{t('Mehmonlar soni')}<input autoFocus type="number" min={1} max={50} step={1} required value={openingGuests} onChange={e => setOpeningGuests(e.target.value)} className="mt-2 w-full rounded-xl border p-4 text-2xl" /></label>
        <div className="grid grid-cols-4 gap-2">{[1, 2, 3, 4, 5, 6, 7, 8].map(n => <button type="button" key={n} onClick={() => setOpeningGuests(String(n))} className={`rounded-lg border py-3 text-lg font-bold ${Number(openingGuests) === n ? 'bg-sky-700 text-white' : 'bg-stone-50'}`}>{n}</button>)}</div>
        <div className="flex gap-3"><button type="button" onClick={() => setOpeningTable(null)} className="rounded-xl border px-4 py-3">{t('Yopish')}</button><button type="submit" className="flex-1 rounded-xl bg-sky-700 px-4 py-3 font-bold text-white">{t('Davom ettirish')}</button></div>
      </form></div>}
      {actionsOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3"><div role="dialog" aria-modal="true" aria-label={t('Chek amallari')} className="max-h-[90vh] w-full max-w-lg space-y-4 overflow-y-auto rounded-2xl bg-white p-5 text-stone-900"><div className="flex items-center justify-between"><h2 className="text-xl font-bold">{t('Chek amallari')}</h2><button onClick={() => setActionsOpen(false)} aria-label={t('Yopish')}><X /></button></div>
        <div className="grid grid-cols-2 gap-2"><button disabled={!cart.length || draftBusy} onClick={() => { setActionsOpen(false); void saveDraft() }} className="rounded-xl border p-3 font-semibold disabled:opacity-40">{t('Saqlab qo‘yish')}</button><button onClick={() => { setActionsOpen(false); void loadDrafts() }} className="rounded-xl border p-3 font-semibold">{t('Saqlangan buyurtmalar')}</button></div>
        <label className="block text-sm font-semibold">{t('Chegirma')} %<input aria-label={t('Chegirma foizi')} type="number" min={0} max={50} step={1} value={discountPct} onChange={e => setDiscountPct(Math.max(0, Math.min(50, Math.round(Number(e.target.value) || 0))))} className="ml-3 w-24 rounded-lg border p-2" /></label>
        <label className="block text-sm font-semibold">{t('Chekka izoh')}<textarea maxLength={500} value={note} onChange={e => setNote(e.target.value)} className="mt-1 w-full rounded-xl border p-3" /></label>
        <label className="block text-sm font-semibold">{t('Mehmonlar soni')}<input aria-label={t('Mehmonlar soni')} type="number" min={Math.max(1, ...cart.map(i => i.guest ?? 1))} max={50} value={guests} onChange={e => { const n = Math.max(1, ...cart.map(i => i.guest ?? 1), Math.min(50, Number(e.target.value) || 1)); setGuests(n); setGuest(g => Math.min(g, n)) }} className="ml-3 w-24 rounded-lg border p-2" /></label>
        <label className="block text-sm font-semibold">{t('Stolni almashtirish')}<select aria-label={t('Stolni almashtirish')} disabled={draftBusy || !cart.length} value="" onChange={e => void draftAction('move', e.target.value === 'takeaway' ? { tableId: null, service: 'takeaway' } : { tableId: Number(e.target.value), service: 'dine_in' })} className="mt-1 w-full rounded-lg border p-3"><option value="">{t('Tanlang')}</option><option value="takeaway">{t('Olib ketish')}</option>{actionFloor.tables.filter(tb => tb.active && !tb.occupied).map(tb => <option key={tb.id} value={tb.id}>{tb.name}</option>)}</select></label>
        <button disabled={draftBusy || new Set(cart.map(i => i.guest ?? 1)).size < 2} onClick={() => void draftAction('split', { guest })} className="w-full rounded-lg border p-3 text-left font-semibold disabled:opacity-40">{t('Chekni ajratish')} · {t('Mehmon')} {guest}</button>
        {actionStaff.length > 0 && <label className="block text-sm font-semibold">{t('Mas’ul xodimni almashtirish')}<select aria-label={t('Mas’ul xodimni almashtirish')} disabled={draftBusy || !cart.length} value="" onChange={e => void draftAction('assign', { staffId: Number(e.target.value) })} className="mt-1 w-full rounded-lg border p-3"><option value="">{t('Tanlang')}</option>{actionStaff.map(staff => <option key={staff.id} value={staff.id}>{staff.name}</option>)}</select></label>}
        <button disabled={draftBusy} onClick={clearOrder} className="w-full rounded-lg border border-red-300 p-3 text-left font-semibold text-red-700">{t('Buyurtmani tozalash')}</button>
        {draftError && <p role="alert" className="text-sm text-red-700">{draftError}</p>}
        <button onClick={() => setActionsOpen(false)} className="w-full rounded-lg bg-sky-700 p-3 font-bold text-white">{t('Tayyor')}</button>
      </div></div>}
      {functionsOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3"><div className="w-full max-w-xl rounded-2xl bg-white p-5 text-stone-900"><div className="mb-4 flex justify-between"><h2 className="text-xl font-bold">{t('Funksiyalar')}</h2><button onClick={() => setFunctionsOpen(false)} aria-label={t('Yopish')}><X /></button></div><div className="grid gap-3 sm:grid-cols-2">
        <button className="rounded-xl border p-4 text-left font-semibold" onClick={() => { setFunctionsOpen(false); setExpenseOpen(true) }}>{t('Xarajat')}</button>
        <button className="rounded-xl border p-4 text-left font-semibold" onClick={() => { setFunctionsOpen(false); onShift() }}>{t('Smena')}</button>
        <button className="rounded-xl border p-4 text-left font-semibold" onClick={() => { setFunctionsOpen(false); void loadDrafts() }}>{t('Saqlangan buyurtmalar')}</button>
        {(canCancel || canReprint) && <button className="rounded-xl border p-4 text-left font-semibold" onClick={() => { setFunctionsOpen(false); setHistoryOpen(true) }}>{t('Cheklar tarixi')}</button>}
        {(session?.staff.role === 'admin' || session?.staff.role === 'owner') && <button className="rounded-xl border p-4 text-left font-semibold" onClick={() => { window.location.hash = 'admin' }}>{t('Admin')}</button>}
        </div></div></div>}
      {draftsOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3"><div className="max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white p-5 text-stone-900 shadow-xl">
        <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-bold">{t('Saqlangan buyurtmalar')}</h2><button onClick={() => setDraftsOpen(false)} aria-label={t('Yopish')}><X className="size-6" /></button></div>
        {draftError && <p role="alert" className="mb-3 text-sm text-red-700">{draftError}</p>}
        {!drafts.length && <p className="text-sm text-stone-500">{t('Saqlangan buyurtmalar yo‘q')}</p>}
        <div className="space-y-2">{drafts.map(d => <div key={d.id} className="flex flex-wrap items-center gap-3 rounded-xl border p-3">
          <div className="min-w-0 flex-1"><b>#{d.id} · {d.customer || t('Mijoz')}</b><div className="text-xs text-sky-700">{t('Mehmon')}: {[...new Set(d.items.map(i => i.guest ?? 1))].join(', ')}{d.waiter ? ' · ' + d.waiter : ''}</div><div className="text-xs text-stone-500">{d.items.length} · {new Date(d.updatedAt).toLocaleString()}</div></div>
          <button onClick={() => resumeDraft(d)} className="rounded-lg bg-amber-600 px-3 py-2 text-sm font-bold text-white">{t('Davom ettirish')}</button>
          <button disabled={draftBusy} onClick={() => removeDraft(d)} className="rounded-lg border px-3 py-2 text-sm text-red-700 disabled:opacity-40">{t('O‘chirish')}</button>
        </div>)}</div>
      </div></div>}
      {modal && <ProductModal product={modal} onClose={() => setModal(null)} onAdd={(it) => { addToCart(it); setModal(null) }} />}
      {paying && <PaymentModal total={total} onClose={() => setPaying(false)} onConfirm={confirmPayment} />}
      {receipt && <ReceiptModal order={receipt} onClose={() => { setReceipt(null); if (returnToFloor) openFloor(); setReturnToFloor(false) }} />}
      {historyOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3"><div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-5 text-stone-900 shadow-xl"><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-bold">{t('Cheklar tarixi')} · {t('Otmena')} / {t('Perechek')}</h2><button onClick={() => setHistoryOpen(false)} aria-label={t('Yopish')}><X className="size-6" /></button></div><p className="mb-3 text-sm text-red-700">{t('Otmena')}: {orders.filter(o => o.status === 'cancelled').length}</p>{historyError && <p role="alert" className="mb-2 rounded-lg bg-red-100 p-2 text-red-800">{historyError}</p>}<div className="space-y-2">{[...orders].sort((a,b) => b.createdAt-a.createdAt).slice(0,80).map(o => <div key={o.id} className={`flex flex-wrap items-center gap-3 rounded-xl border p-3 text-sm ${o.status === 'cancelled' ? 'border-red-300 bg-red-50' : 'border-stone-200'}`}><div className="min-w-0 flex-1"><b>№ {o.number}</b> · {new Date(o.createdAt).toLocaleString()} · {som(o.total)}<div className="text-xs text-stone-500">{o.status === 'cancelled' ? `${t('Otmena')} · ${o.cancelledBy || ''} · ${o.cancelReason || ''}` : o.items.map(i=>tCatalogName(i.name)).join(', ')}</div></div>{canReprint && <button onClick={() => { setHistoryOpen(false); setReceipt(o) }} className="rounded-lg border px-3 py-2">{t('Perechek')}</button>}{canCancel && o.status === 'new' && !o.pendingSync && <button onClick={() => cancelReceipt(o)} className="rounded-lg bg-red-600 px-3 py-2 font-semibold text-white">{t('Otmena')}</button>}</div>)}</div></div></div>}
      {expenseOpen && <CashExpense onClose={() => setExpenseOpen(false)} />}
    </div>
  )
}

function Cart(props: {
  hookah?: boolean
  onActions: () => void
  guest: number; guests: number; setGuest: (n: number) => void; addGuest: () => void
  number: number; cart: OrderItem[]; customer: string; setCustomer: (v: string) => void
  customerPhone: string; setCustomerPhone: (v: string) => void
  bonusInfo: BonusSnapshot | null; bonusError: string; bonusRedeem: number; maxRedeem: number
  setBonusRedeem: (v: number) => void; loadBonus: () => void
  appliedDiscountPct: number; subtotal: number; discount: number; total: number
  changeQty: (key: string, d: number) => void; draftError: string; onPay: () => void; onClose?: () => void
}) {
  const { cart } = props
  return (
    <div className="cashier-cart flex min-h-0 w-full flex-col overflow-y-auto">
      <div className="flex shrink-0 items-center justify-between border-b border-stone-200 px-4 py-2">
        <div>
          <div className="text-xs text-stone-500">{t('Yangi buyurtma')}</div>
          <div className="text-lg font-bold">#{props.number}</div>
        </div>
        <div className="flex items-center gap-1">
          {props.onClose && <button onClick={props.onClose} aria-label={t('Yopish')} className="rounded-lg p-2 hover:bg-stone-100"><X className="size-5" /></button>}
        </div>
      </div>
      <details className="cashier-customer shrink-0 border-b px-4 py-2"><summary className="cursor-pointer text-sm font-semibold">{t('Mijoz')}{props.customer ? ` · ${props.customer}` : ''}{props.bonusInfo?.enabled ? ` · ${som(props.bonusInfo.balance)}` : ''}</summary>
      <div className="pt-3">
        <input value={props.customer} onChange={(e) => props.setCustomer(e.target.value)} placeholder={t(props.hookah ? 'Mijoz ismi' : 'Mijoz ismi (stakan uchun)')}
          className="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2.5 outline-none focus:border-amber-500" />
      </div>
      <div className="space-y-2 px-4 pt-2">
        <div className="flex gap-2">
          <input value={props.customerPhone} onChange={e=>props.setCustomerPhone(e.target.value)}
            placeholder={t('Mijoz telefoni (bonus)')} inputMode="tel" autoComplete="off"
            className="min-w-0 flex-1 rounded-xl border border-stone-200 px-3 py-2 text-sm" />
          <button onClick={props.loadBonus} disabled={!props.customerPhone.trim()}
            className="rounded-xl border px-3 py-2 text-xs font-medium disabled:opacity-40">{t('Tekshirish')}</button>
        </div>
        {props.bonusError && <p role="alert" className="text-xs text-red-600">{props.bonusError}</p>}
        {props.bonusInfo?.enabled && <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-amber-50 p-2 text-xs">
          <span>{t('Bonus qoldig‘i')}: {som(props.bonusInfo.balance)}</span>
          <span>{t('Bu savdodan bonus')}: {som(Math.floor(Math.max(0, props.subtotal - props.discount - props.bonusRedeem) * props.bonusInfo.earnPercent / 100))}</span>
          <label>{t('Ishlatish')} <input className="w-24 rounded border bg-white p-1" type="number" min={0} max={props.maxRedeem} step={1} value={props.bonusRedeem} onChange={e => props.setBonusRedeem(Math.max(0, Math.min(Number(e.target.value) || 0, props.maxRedeem)))} /></label>
        </div>}
      </div>
      </details>
      <div className="cashier-guests flex shrink-0 gap-2 overflow-x-auto border-b px-4 py-2">{Array.from({ length: props.guests }, (_, index) => index + 1).map(n => <button key={n} onClick={() => props.setGuest(n)} className={`shrink-0 rounded-lg px-3 py-2 text-sm font-bold ${n === props.guest ? 'bg-sky-600 text-white' : 'bg-stone-100 text-stone-700'}`}>{t('Mehmon')} {n}</button>)}<button disabled={props.guests >= 50} onClick={props.addGuest} className="shrink-0 rounded-lg border px-3 py-2 text-sm font-bold text-sky-700">+ {t('Mehmon qo‘shish')}</button></div>
      <div role="region" aria-label={t('Savat')} className="cashier-cart-items min-h-40 flex-1 space-y-2 overflow-y-auto px-3 py-2">
        {cart.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-2 py-10 text-center text-stone-400">
            <ShoppingBag className="size-10" />{t("Savat bo'sh. Mahsulotni tanlang.")}
          </div>
        )}
        {cart.map((it) => (
          <div key={it.key} className="cashier-cart-row rounded-xl border border-stone-200 p-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-xs text-sky-700">{t('Mehmon')} {it.guest ?? 1}</div><div className="font-semibold">{tCatalogName(it.name)}{it.size && <span className="ml-1.5 rounded bg-stone-100 px-1.5 text-sm font-medium text-stone-600">{it.size}</span>}</div>
                {it.mods.length > 0 && <div className="mt-0.5 text-sm text-stone-500">{it.mods.map(tCatalogName).join(', ')}</div>}
              </div>
              <div className="shrink-0 font-semibold">{fmt(it.unitPrice * it.qty)}</div>
            </div>
            <div className="mt-2 flex items-center gap-3">
              <button onClick={() => props.changeQty(it.key, -1)} aria-label={t('Kamaytirish')} className="grid size-9 place-items-center rounded-lg bg-stone-100 hover:bg-stone-200"><Minus className="size-4" /></button>
              <span className="w-6 text-center font-semibold">{it.qty}</span>
              <button onClick={() => props.changeQty(it.key, 1)} aria-label={t("Ko'paytirish")} className="grid size-9 place-items-center rounded-lg bg-stone-100 hover:bg-stone-200"><Plus className="size-4" /></button>
              <span className="ml-auto text-xs text-stone-400">{fmt(it.unitPrice)} × {it.qty}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="cashier-cart-footer shrink-0 space-y-2 border-t border-stone-200 p-3">
        {props.bonusRedeem > 0 && <div className="flex justify-between text-sm text-amber-700"><span>{t('Bonus ishlatildi')}</span><span>−{som(props.bonusRedeem)}</span></div>}
        {props.discount > 0 && (
          <div className="space-y-1 text-sm text-stone-500">
            <div className="flex justify-between"><span>{t('Oraliq summa')}</span><span>{som(props.subtotal)}</span></div>
            <div className="flex justify-between"><span>{t('Chegirma')} {props.appliedDiscountPct}%</span><span>−{som(props.discount)}</span></div>
          </div>
        )}
        {props.draftError && <p role="alert" className="text-sm text-red-700">{props.draftError}</p>}
        <div className="flex gap-2"><button onClick={props.onActions} aria-label={t('Chek amallari')} className="shrink-0 rounded-xl border px-4 text-xl font-bold">⋯</button>
        <button disabled={cart.length === 0} onClick={props.onPay}
          className="flex min-w-0 flex-1 items-center justify-between rounded-2xl bg-amber-600 px-5 py-4 text-lg font-bold text-white shadow hover:bg-amber-700 disabled:bg-stone-300">
          <span>{t("To'lov")}</span><span>{som(props.total)}</span>
        </button></div>
      </div>
    </div>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`rounded-xl border-2 px-3 py-2.5 text-left text-sm font-medium ${active ? 'border-amber-600 bg-amber-50 text-amber-900' : 'border-stone-200 bg-white text-stone-700'}`}>
      {children}
    </button>
  )
}

function ProductModal({ product, onClose, onAdd }: { product: Product; onClose: () => void; onAdd: (it: OrderItem) => void }) {
  const defaultSize = Math.max(0, product.sizes.findIndex((s) => s.code === 'M'))
  const [sizeIdx, setSizeIdx] = useState(defaultSize)
  const [milk, setMilk] = useState(DEFAULT_MILK)
  const [syrups, setSyrups] = useState<string[]>([])
  const [shot, setShot] = useState('')
  const [qty, setQty] = useState(1)
  const has = (g: ModGroupId) => product.mods.includes(g)
  const group = (g: ModGroupId) => MODIFIERS.filter((m) => m.group === g)
  const modIds = [...(has('milk') ? [milk] : []), ...syrups, ...(shot ? [shot] : [])]
  const item = buildItem(product, product.sizes[sizeIdx], modIds, qty)

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4" onClick={onClose}>
      <div className="flex max-h-[92dvh] w-full flex-col rounded-t-3xl bg-white sm:max-w-lg sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-stone-200 px-5 py-4">
          <h2 className="text-xl font-bold">{product.name}</h2>
          <button onClick={onClose} aria-label={t('Yopish')} className="rounded-lg p-2 hover:bg-stone-100"><X className="size-5" /></button>
        </div>
        <div className="space-y-5 overflow-y-auto px-5 py-4">
          {product.sizes.length > 1 && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-stone-500">{t('Hajm')}</h3>
              <div className="grid grid-cols-3 gap-2">
                {product.sizes.map((s, i) => (
                  <Chip key={s.code} active={i === sizeIdx} onClick={() => setSizeIdx(i)}>
                    <span className="block text-lg font-bold">{s.label}</span>
                    <span className="block text-xs text-stone-500">{s.volume}</span>
                    <span className="block">{fmt(s.price)}</span>
                  </Chip>
                ))}
              </div>
            </section>
          )}
          {has('milk') && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-stone-500">{t('Sut turi')}</h3>
              <div className="grid grid-cols-2 gap-2">
                {group('milk').map((m) => (
                  <Chip key={m.id} active={milk === m.id} onClick={() => setMilk(m.id)}>
                    {tCatalogName(m.name)}{m.price > 0 && <span className="text-stone-500"> +{fmt(m.price)}</span>}
                  </Chip>
                ))}
              </div>
            </section>
          )}
          {has('syrup') && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-stone-500">{t('Sirop')} <span className="font-normal">({t('bir nechtasini tanlash mumkin')})</span></h3>
              <div className="grid grid-cols-3 gap-2">
                {group('syrup').map((m) => (
                  <Chip key={m.id} active={syrups.includes(m.id)} onClick={() => setSyrups((s) => (s.includes(m.id) ? s.filter((x) => x !== m.id) : [...s, m.id]))}>
                    {tCatalogName(m.name)}<span className="block text-stone-500">+{fmt(m.price)}</span>
                  </Chip>
                ))}
              </div>
            </section>
          )}
          {has('shot') && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-stone-500">{t("Qo'shimcha espresso")}</h3>
              <div className="grid grid-cols-3 gap-2">
                <Chip active={shot === ''} onClick={() => setShot('')}>{t("Yo'q")}</Chip>
                {group('shot').map((m) => (
                  <Chip key={m.id} active={shot === m.id} onClick={() => setShot(m.id)}>
                    {tCatalogName(m.name)}<span className="block text-stone-500">+{fmt(m.price)}</span>
                  </Chip>
                ))}
              </div>
            </section>
          )}
        </div>
        <div className="flex items-center gap-3 border-t border-stone-200 p-4">
          <div className="flex items-center gap-2">
            <button onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label={t('Kamaytirish')} className="grid size-12 place-items-center rounded-xl bg-stone-100"><Minus className="size-5" /></button>
            <span className="w-6 text-center text-lg font-bold">{qty}</span>
            <button onClick={() => setQty((q) => q + 1)} aria-label={t("Ko'paytirish")} className="grid size-12 place-items-center rounded-xl bg-stone-100"><Plus className="size-5" /></button>
          </div>
          <button onClick={() => onAdd(item)} className="flex flex-1 items-center justify-between gap-2 rounded-xl bg-amber-600 px-4 py-3.5 font-bold text-white hover:bg-amber-700">
            <span>{t("Qo'shish")}</span><span>{som(item.unitPrice * qty)}</span>
          </button>
        </div>
      </div>
    </div>
  )
}

const PAY_OPTIONS: { id: Exclude<Payment, 'split'>; icon: LucideIcon }[] = [
  { id: 'naqd', icon: Banknote }, { id: 'karta', icon: CreditCard }, { id: 'payme', icon: Smartphone }, { id: 'click', icon: Smartphone },
]

function PaymentModal({ total, onClose, onConfirm }: { total: number; onClose: () => void; onConfirm: (p: Payment, cash?: number, parts?: { method: Exclude<Payment, "split">; amount: number }[]) => Promise<void> }) {
  const [method, setMethod] = useState<Exclude<Payment, 'split'>>('karta')
  const [split, setSplit] = useState(false)
  const [splitA, setSplitA] = useState<Exclude<Payment, 'split'>>('naqd')
  const [splitB, setSplitB] = useState<Exclude<Payment, 'split'>>('karta')
  const [firstAmount, setFirstAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const confirm = async () => {
    setBusy(true)
    setError('')
    try {
      if (split) {
        await onConfirm('split', splitCash > 0 ? given : undefined, [
          { method: splitA, amount: first }, { method: splitB, amount: total - first },
        ])
      } else {
        await onConfirm(method, method === 'naqd' ? given : undefined)
      }
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
    }
  }
  const [cash, setCash] = useState('')
  const given = Number(cash.replace(/\D/g, '')) || 0
  const first = Number(firstAmount.replace(/\D/g, '')) || 0
  const splitCash = split ? (splitA === 'naqd' ? first : splitB === 'naqd' ? total - first : 0) : 0
  const cashDue = split ? splitCash : total
  const quick = [...new Set([cashDue, ...[50000, 100000, 200000].map((step) => Math.ceil(cashDue / step) * step)])].filter(q => q > 0).sort((a, b) => a - b)
  const ok = split ? (first > 0 && first < total && splitA !== splitB && (!splitCash || given >= splitCash))
    : (method !== 'naqd' || given >= total)

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4" onClick={onClose}>
      <div className="w-full rounded-t-3xl bg-white sm:max-w-md sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-stone-200 px-5 py-4">
          <div>
            <div className="text-sm text-stone-500">{t("To'lanadigan summa")}</div>
            <div className="text-2xl font-bold">{som(total)}</div>
          </div>
          <button onClick={onClose} aria-label={t('Yopish')} className="rounded-lg p-2 hover:bg-stone-100"><X className="size-5" /></button>
        </div>
        <div className="space-y-4 p-5">
          <button type="button" onClick={() => { setSplit(v => !v); setCash('') }}
            className="w-full rounded-xl border border-amber-500 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">{split ? t('Oddiy to‘lov') : t('Bo‘lingan to‘lov')}</button>
          {!split && <div className="grid grid-cols-2 gap-2">
            {PAY_OPTIONS.map(({ id, icon: Icon }) => (
              <Chip key={id} active={method === id} onClick={() => setMethod(id)}>
                <span className="flex items-center gap-2 py-1 text-base"><Icon className="size-5" />{t(PAYMENT_LABEL[id])}</span>
              </Chip>
            ))}
          </div>}
          {split && <div className="space-y-3 rounded-xl border border-stone-200 p-3">
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-stone-600">{t('Birinchi usul')}
                <select value={splitA} onChange={e => setSplitA(e.target.value as Exclude<Payment, 'split'>)} className="mt-1 w-full rounded-lg border p-2 text-sm">
                  {PAY_OPTIONS.map(o => <option key={o.id} value={o.id}>{t(PAYMENT_LABEL[o.id])}</option>)}
                </select>
              </label>
              <label className="text-xs text-stone-600">{t('Ikkinchi usul')}
                <select value={splitB} onChange={e => setSplitB(e.target.value as Exclude<Payment, 'split'>)} className="mt-1 w-full rounded-lg border p-2 text-sm">
                  {PAY_OPTIONS.map(o => <option key={o.id} value={o.id}>{t(PAYMENT_LABEL[o.id])}</option>)}
                </select>
              </label>
            </div>
            <label className="block text-xs text-stone-600">{t('Birinchi summa')}
              <input inputMode="numeric" value={firstAmount} onChange={e => setFirstAmount(e.target.value.replace(/\D/g, ''))}
                className="mt-1 w-full rounded-lg border p-2 text-base" placeholder="0" />
            </label>
            <p className="text-sm font-semibold">{t('Ikkinchi summa')}: {som(Math.max(0, total - first))}</p>
            {splitA === splitB && <p role="alert" className="text-sm text-red-700">{t('Ikki xil to‘lov usulini tanlang')}</p>}
          </div>}
          {(split ? splitCash > 0 : method === 'naqd') && (
            <div className="space-y-2">
              <input inputMode="numeric" autoFocus value={cash ? fmt(given) : ''} onChange={(e) => setCash(e.target.value)} placeholder={t('Mijoz bergan summa')}
                className="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-3 text-lg outline-none focus:border-amber-500" />
              <div className="flex flex-wrap gap-2">
                {quick.map((q) => (
                  <button key={q} onClick={() => setCash(String(q))} className="rounded-lg bg-stone-100 px-3 py-2 text-sm font-medium hover:bg-stone-200">{fmt(q)}</button>
                ))}
              </div>
              {given > 0 && (
                <div className={`flex justify-between rounded-xl px-4 py-3 font-semibold ${given >= cashDue ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-700'}`}>
                  <span>{given >= cashDue ? t('Qaytim') : t('Yetmaydi')}</span><span>{som(Math.abs(given - cashDue))}</span>
                </div>
              )}
            </div>
          )}
          {(split ? (splitA === 'payme' || splitA === 'click' || splitB === 'payme' || splitB === 'click') : (method === 'payme' || method === 'click')) && (
            <p className="rounded-xl bg-stone-100 px-4 py-3 text-sm text-stone-600">{t("To'lovni ilovada tekshirib, qo'lda tasdiqlang. QR va avtomatik tasdiqlash keyingi versiyada.")}</p>
          )}
          {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
          <button disabled={!ok || busy} onClick={confirm}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 py-4 text-lg font-bold text-white hover:bg-emerald-700 disabled:bg-stone-300">
            <Check className="size-5" />{t('Tasdiqlash')}
          </button>
        </div>
      </div>
    </div>
  )
}

function ReceiptModal({ order, onClose }: { order: Order; onClose: () => void }) {
  const company = useAppState().session?.company.name ?? 'CoffeePOS'
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="flex max-h-[92dvh] w-full max-w-sm flex-col rounded-3xl bg-white" onClick={(e) => e.stopPropagation()}>
        <div className="flex flex-col items-center gap-1 px-5 pt-5 text-center">
          <span className="grid size-12 place-items-center rounded-full bg-emerald-100 text-emerald-700"><Check className="size-7" /></span>
          <div className="text-lg font-bold">{order.pendingSync ? t('Offline buyurtma saqlandi') : t('Buyurtma #{n} qabul qilindi', { n: order.number })}</div>
          <div className="text-sm text-stone-500">{order.pendingSync ? t('Internet qaytgach serverga yuboriladi. Bu fiskal chek emas.') : t('Barista ekraniga yuborildi')}</div>
        </div>
        <div className="print-area mx-5 my-4 overflow-y-auto rounded-xl border border-dashed border-stone-300 bg-stone-50 p-4 font-mono text-xs">
          <div className="text-center font-bold">{company}</div>
          {order.pendingSync && <div className="my-2 border-2 border-dashed border-amber-700 p-2 text-center font-bold">{t('OFFLINE — SERVER TASDIQLAMAGAN. FISKAL CHEK EMAS.')}</div>}
          <div className="text-center text-stone-500">{new Date(order.createdAt).toLocaleDateString('ru-RU')} {time(order.createdAt)} · #{order.number}</div>
          {order.note && <div className="mt-1">{t('Chekka izoh')}: {order.note}</div>}
          {order.waiter && <div>{t('Mas’ul xodim')}: {order.waiter}</div>}
          {order.customer && <div className="mt-1 text-center">{t('Mijoz')}: {order.customer}</div>}
          <div className="my-2 border-t border-dashed border-stone-300" />
          {order.items.map((it) => (
            <div key={it.key} className="mb-1">
              <div className="flex justify-between gap-2"><span>{t('Mehmon')} {it.guest ?? 1} · {it.qty}× {tCatalogName(it.name)} {it.size}</span><span>{fmt(it.unitPrice * it.qty)}</span></div>
              {it.mods.length > 0 && <div className="pl-3 text-stone-500">{it.mods.map(tCatalogName).join(', ')}</div>}
            </div>
          ))}
          <div className="my-2 border-t border-dashed border-stone-300" />
          {order.discount > 0 && <div className="flex justify-between"><span>{t('Chegirma')}</span><span>−{fmt(order.discount)}</span></div>}
          <div className="flex justify-between text-sm font-bold"><span>{t('JAMI')}</span><span>{som(order.total)}</span></div>
          {order.paymentParts && order.paymentParts.length > 1 ? order.paymentParts.map(p =>
            <div key={p.method} className="flex justify-between"><span>{t(PAYMENT_LABEL[p.method])}</span><span>{som(p.amount)}</span></div>
          ) : <div className="flex justify-between"><span>{t("To'lov")}</span><span>{t(PAYMENT_LABEL[order.payment])}</span></div>}
          {order.cashGiven != null && (
            <>
              <div className="flex justify-between"><span>{t('cash:Berildi')}</span><span>{fmt(order.cashGiven)}</span></div>
              <div className="flex justify-between"><span>{t('Qaytim')}</span><span>{fmt(order.cashGiven - (order.paymentParts?.find(p => p.method === 'naqd')?.amount ?? order.total))}</span></div>
            </>
          )}
          <div className="mt-2 text-center text-stone-500">{t('Rahmat! Yana keling.')}</div>
          <div className="mt-2 border-t border-dashed border-stone-300 pt-2 text-center text-[10px] font-bold">{t('Bu fiskal chek emas.')} </div>
        </div>
        <div className="flex gap-2 p-5 pt-0">
          <button onClick={() => window.print()} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-stone-100 py-3 font-semibold hover:bg-stone-200"><Printer className="size-4" />{t('Chek')}</button>
          <button onClick={onClose} className="flex-[2] rounded-xl bg-stone-900 py-3 font-semibold text-white">{t('Yangi buyurtma')}</button>
        </div>
      </div>
    </div>
  )
}

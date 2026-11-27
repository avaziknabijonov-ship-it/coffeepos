import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Minus, Plus, Search, Send, Users, X } from 'lucide-react'
import { api } from './api'
import { CATEGORIES, PRODUCTS, SETTINGS, buildItem, canMake, cartTotals, fmt, som, time } from './data'
import type { CheckLine, HallInfo, OpenCheck, Order, OrderItem, Payment, Product, Size } from './data'
import { t, tCatalogName } from './i18n'
import { PaymentModal, ProductModal, ReceiptModal } from './Kassa'
import { sync, useAppState } from './store'
import { OpenShift } from './Shift'
import { WeightModal } from './Shop'

const needsModal = (p: Product) => p.sizes.length > 1 || p.mods.length > 0
const toBody = (items: CheckLine[]) => items.map((i) => ({ productId: i.productId, size: i.key.split('|')[1], modIds: i.modIds, qty: i.qty, weight: i.weight }))
const since = (ms: number, now: number) => `${Math.max(0, Math.floor((now - ms) / 60000))} ${t('daq')}`

export default function Hall() {
  const { checks, shift, session, menuVersion } = useAppState()
  const [halls, setHalls] = useState<HallInfo[]>([])
  const [hallId, setHallId] = useState<number | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [now, setNow] = useState(() => Date.now())
  const [receipt, setReceipt] = useState<Order | null>(null)
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(id) }, [])
  useEffect(() => {
    api<HallInfo[]>('/api/halls').then((h) => { setHalls(h); setHallId((cur) => cur ?? h[0]?.id ?? null) }).catch((e) => setError((e as Error).message))
  }, [menuVersion])

  const role = session?.staff.role
  if (receipt) return <ReceiptModal order={receipt} onClose={() => { setReceipt(null); setOpenId(null) }} />
  if (!shift) return <OpenShift canOpen={role !== 'ofitsiant'} />
  const current = checks.find((c) => c.id === openId)
  if (openId !== null && current) return <CheckEditor check={current} onBack={() => setOpenId(null)} onPaid={setReceipt} />

  const open = async (tableId: number | null) => {
    setError('')
    try {
      const c = await api<OpenCheck>('/api/checks', { body: { tableId, guests: 1 } })
      await sync()
      setOpenId(c.id)
    } catch (e) { setError((e as Error).message) }
  }
  const hall = halls.find((h) => h.id === hallId)
  const noTable = checks.filter((c) => c.tableId === null)

  return (
    <div className="h-full overflow-y-auto bg-stone-50 p-3 sm:p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {halls.map((h) => <button key={h.id} onClick={() => setHallId(h.id)}
          className={`rounded-xl px-4 py-2 font-medium ${h.id === hallId ? 'bg-stone-900 text-white' : 'bg-white text-stone-700'}`}>{h.name}</button>)}
        <button onClick={() => void open(null)} className="ml-auto rounded-xl border border-amber-600 bg-amber-50 px-4 py-2 font-semibold text-amber-900">{t('Stolsiz hisob')}</button>
      </div>
      {error && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      {halls.length === 0 && <p className="rounded-xl bg-white p-6 text-center text-stone-500">{t('Rahbar Admin → Zal va sexlar bo‘limida zal va stollarni qo‘shishi kerak.')}</p>}
      {hall && <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {hall.tables.filter((x) => x.active).map((tb) => {
          const list = checks.filter((c) => c.tableId === tb.id)
          const busy = list.length > 0
          return <div key={tb.id} className={`flex min-h-32 flex-col rounded-2xl border-2 p-3 ${busy ? 'border-amber-500 bg-amber-50' : 'border-stone-200 bg-white'}`}>
            <div className="flex items-center justify-between"><span className="text-2xl font-bold">{tb.name}</span><span className="flex items-center gap-1 text-xs text-stone-500"><Users className="size-3.5" />{tb.seats}</span></div>
            {list.map((c) => <button key={c.id} onClick={() => setOpenId(c.id)} className="mt-2 rounded-lg bg-white p-2 text-left text-sm shadow-sm">
              <div className="flex justify-between font-semibold"><span>{fmt(c.total)}</span><span className="text-stone-500">{since(c.createdAt, now)}</span></div>
              <div className="text-xs text-stone-500">{c.waiter}{c.unsent > 0 && <span className="ml-1 font-semibold text-red-600">· {t('{n} ta yuborilmagan', { n: c.unsent })}</span>}</div>
            </button>)}
            <button onClick={() => void open(tb.id)} className={`mt-auto pt-2 text-sm font-semibold ${busy ? 'text-amber-800' : 'text-emerald-700'}`}>{busy ? t('+ Yana hisob') : t('Hisob ochish')}</button>
          </div>
        })}
      </div>}
      {noTable.length > 0 && <div className="mt-5">
        <h3 className="mb-2 font-semibold">{t('Stolsiz hisoblar')}</h3>
        <div className="flex flex-wrap gap-2">{noTable.map((c) => <button key={c.id} onClick={() => setOpenId(c.id)} className="rounded-xl border border-amber-500 bg-amber-50 px-3 py-2 text-left text-sm">
          <b>#{c.id}</b> · {fmt(c.total)} · {c.waiter} · {time(c.createdAt)}</button>)}</div>
      </div>}
    </div>
  )
}

function CheckEditor({ check, onBack, onPaid }: { check: OpenCheck; onBack: () => void; onPaid: (o: Order) => void }) {
  const { session, stock, menuVersion } = useAppState()
  const role = session?.staff.role
  const canPay = role === 'owner' || role === 'admin' || role === 'kassir'
  const canVoidSent = role === 'owner' || role === 'admin' || Boolean(session?.staff.canCancelOrders)
  const [lines, setLines] = useState<CheckLine[]>(check.items)
  const [cat, setCat] = useState(CATEGORIES[0]?.id ?? '')
  const [query, setQuery] = useState('')
  const [modal, setModal] = useState<Product | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [paying, setPaying] = useState(false)
  const [discountPct, setDiscountPct] = useState(0)
  const [mobileMenu, setMobileMenu] = useState(false)
  const [weighing, setWeighing] = useState<{ product: Product; size: Size } | null>(null)
  useEffect(() => { if (!busy) setLines(check.items) }, [check.updatedAt]) // eslint-disable-line react-hooks/exhaustive-deps

  const products = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? PRODUCTS.filter((p) => p.name.toLowerCase().includes(q) || tCatalogName(p.name).toLowerCase().includes(q)) : PRODUCTS.filter((p) => p.cat === cat)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cat, query, menuVersion])
  const totals = cartTotals(lines, discountPct)
  const unsent = lines.reduce((s, l) => s + Math.max(0, l.qty - (l.sent ?? 0)), 0)

  const save = async (next: CheckLine[]) => {
    const prev = lines
    setLines(next); setBusy(true); setError('')
    try {
      await api<OpenCheck>(`/api/checks/${check.id}/items`, { method: 'PUT', body: { items: toBody(next) } })
      await sync()
    } catch (e) { setLines(prev); setError((e as Error).message) } finally { setBusy(false) }
  }
  const add = (item: OrderItem) => {
    const same = lines.find((l) => l.key === item.key)
    void save(same ? lines.map((l) => (l.key === item.key ? { ...l, qty: l.qty + item.qty } : l)) : [...lines, { ...item, sent: 0 }])
  }
  const change = (key: string, d: number) => void save(lines.map((l) => (l.key === key ? { ...l, qty: l.qty + d } : l)).filter((l) => l.qty > 0))
  const onTile = (p: Product) => (p.weighted ? setWeighing({ product: p, size: p.sizes[0] }) : needsModal(p) ? setModal(p) : add(buildItem(p, p.sizes[0], [], 1)))

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('')
    try { await fn(); await sync() } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const send = () => act(() => api(`/api/checks/${check.id}/send`, { body: {} }))
  const voidCheck = () => {
    const reason = window.prompt(t('Bekor qilish sababi (kamida 3 ta belgi):'))
    if (!reason || reason.trim().length < 3) return
    void act(async () => { await api(`/api/checks/${check.id}/void`, { body: { reason: reason.trim() } }); onBack() })
  }
  const setGuests = (guests: number) => act(() => api(`/api/checks/${check.id}`, { method: 'PATCH', body: { tableId: check.tableId, guests, comment: check.comment } }))
  const setComment = () => {
    const comment = window.prompt(t('Oshxona uchun izoh'), check.comment)
    if (comment === null) return
    void act(() => api(`/api/checks/${check.id}`, { method: 'PATCH', body: { tableId: check.tableId, guests: check.guests, comment: comment.slice(0, 200) } }))
  }
  const pay = async (payment: Payment, cashGiven?: number) => {
    const order = await api<Order>(`/api/checks/${check.id}/pay`, { body: { payment, cashGiven, discountPct, clientKey: 'check-' + check.id + '-' + crypto.randomUUID().slice(0, 8) } })
    setPaying(false)
    onPaid(order)
    await sync()
  }

  const picker = (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="space-y-2 border-b border-stone-200 bg-white p-3">
        <label className="flex items-center gap-2 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2.5">
          <Search className="size-4 text-stone-400" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('Mahsulot qidirish')} className="w-full bg-transparent outline-none" />
          {query && <button onClick={() => setQuery('')} aria-label={t('Tozalash')}><X className="size-4 text-stone-400" /></button>}
        </label>
        <div className="-mx-3 flex gap-2 overflow-x-auto px-3">
          {CATEGORIES.map((c) => <button key={c.id} onClick={() => { setCat(c.id); setQuery('') }}
            className={`shrink-0 rounded-full px-4 py-2 text-sm font-medium ${!query && cat === c.id ? 'bg-stone-900 text-white' : 'bg-stone-100 text-stone-700'}`}>{tCatalogName(c.name)}</button>)}
        </div>
      </div>
      <div className="grid flex-1 grid-cols-2 content-start gap-2 overflow-y-auto p-3 sm:grid-cols-3 xl:grid-cols-4">
        {products.map((p) => {
          const out = !p.active || (SETTINGS.autoStoplist && !canMake(p, stock))
          return <button key={p.id} disabled={out || busy} onClick={() => { onTile(p); setMobileMenu(false) }}
            className="rounded-xl border border-stone-200 bg-white p-3 text-left shadow-sm hover:border-amber-400 disabled:opacity-40">
            <div className="font-semibold leading-tight">{tCatalogName(p.name)}</div>
            <div className="mt-1 text-sm text-amber-700">{som(Math.min(...p.sizes.map((s) => s.price)))}</div>
            {out && <div className="mt-1 text-xs font-bold uppercase text-red-600">{t(p.active ? 'Tugadi' : 'Stop')}</div>}
          </button>
        })}
      </div>
    </div>
  )

  return (
    <div className="flex h-full min-h-0 bg-stone-50">
      <div className="hidden min-w-0 flex-1 md:flex">{picker}</div>
      {mobileMenu && <div className="fixed inset-0 z-40 flex flex-col bg-white md:hidden">
        <div className="flex items-center justify-between border-b p-3"><b>{t('Menyu')}</b><button onClick={() => setMobileMenu(false)} aria-label={t('Yopish')}><X className="size-6" /></button></div>
        {picker}
      </div>}
      <aside className="flex w-full flex-col border-l border-stone-200 bg-white md:w-96">
        <div className="flex items-center gap-2 border-b border-stone-200 p-3">
          <button onClick={onBack} aria-label={t('Orqaga')} className="rounded-lg p-2 hover:bg-stone-100"><ArrowLeft className="size-5" /></button>
          <div className="min-w-0 flex-1">
            <div className="truncate font-bold">{check.tableName || t('Stolsiz hisob')} · #{check.id}</div>
            <div className="text-xs text-stone-500">{check.waiter} · {time(check.createdAt)}</div>
          </div>
          <label className="flex items-center gap-1 text-sm"><Users className="size-4" />
            <select value={check.guests} onChange={(e) => void setGuests(Number(e.target.value))} className="rounded border px-1 py-0.5">
              {Array.from({ length: 20 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        </div>
        <div className="flex-1 space-y-2 overflow-y-auto p-3">
          {lines.length === 0 && <p className="py-10 text-center text-stone-400">{t("Hisob bo'sh. Menyudan taom tanlang.")}</p>}
          {totals.items.map((l, i) => {
            const sent = lines[i]?.sent ?? 0
            return <div key={l.key} className="rounded-xl border border-stone-200 p-2.5">
              <div className="flex justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold">{tCatalogName(l.name)} {l.size && <span className="rounded bg-stone-100 px-1 text-xs">{l.size}</span>}</div>
                  {l.mods.length > 0 && <div className="text-xs text-stone-500">{l.mods.map(tCatalogName).join(', ')}</div>}
                  {l.promo && <div className="text-xs font-semibold text-emerald-700">{t('Aksiya')}: {l.promo} −{l.promoPct}%</div>}
                </div>
                <div className="shrink-0 text-right font-semibold">{fmt(l.unitPrice * l.qty)}</div>
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <button disabled={busy || (l.qty <= sent && !canVoidSent)} onClick={() => change(l.key, -1)} aria-label={t('Kamaytirish')} className="grid size-8 place-items-center rounded-lg bg-stone-100 disabled:opacity-30"><Minus className="size-4" /></button>
                <span className="w-6 text-center font-semibold">{l.qty}</span>
                <button disabled={busy} onClick={() => change(l.key, 1)} aria-label={t("Ko'paytirish")} className="grid size-8 place-items-center rounded-lg bg-stone-100"><Plus className="size-4" /></button>
                <span className={`ml-auto text-xs ${sent >= l.qty ? 'text-emerald-700' : 'font-semibold text-red-600'}`}>{sent >= l.qty ? t('Yuborilgan') : t('{n} ta yuborilmagan', { n: l.qty - sent })}</span>
              </div>
            </div>
          })}
        </div>
        {error && <p role="alert" className="mx-3 mb-2 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        <div className="space-y-2 border-t border-stone-200 p-3">
          <div className="flex items-center gap-2 text-sm">
            <button onClick={() => setMobileMenu(true)} className="rounded-lg border px-3 py-2 font-semibold md:hidden">{t('+ Taom')}</button>
            <button onClick={setComment} className="rounded-lg border px-3 py-2">{check.comment ? t('Izoh') + ' ✓' : t('Izoh')}</button>
            {canPay && <label className="ml-auto flex items-center gap-1">{t('Chegirma')}
              <input type="number" min={0} max={50} value={discountPct} onChange={(e) => setDiscountPct(Math.max(0, Math.min(50, Math.round(Number(e.target.value) || 0))))} className="w-16 rounded-lg border px-2 py-1.5 text-center" />%</label>}
          </div>
          {totals.discount > 0 && <div className="flex justify-between text-sm text-stone-500"><span>{t('Chegirma')}</span><span>−{som(totals.discount)}</span></div>}
          <div className="flex justify-between text-lg font-bold"><span>{t('Jami')}</span><span>{som(totals.total)}</span></div>
          <div className="grid grid-cols-2 gap-2">
            <button disabled={busy || unsent === 0} onClick={() => void send()} className="flex items-center justify-center gap-2 rounded-xl bg-amber-600 py-3 font-bold text-white disabled:bg-stone-300"><Send className="size-4" />{t('Oshxonaga')}{unsent > 0 && ` (${unsent})`}</button>
            {canPay ? <button disabled={busy || lines.length === 0} onClick={() => setPaying(true)} className="rounded-xl bg-emerald-600 py-3 font-bold text-white disabled:bg-stone-300">{t("To'lov")}</button>
              : <span className="grid place-items-center rounded-xl bg-stone-100 px-2 text-center text-xs text-stone-500">{t('To‘lovni kassir qabul qiladi')}</span>}
          </div>
          <button disabled={busy} onClick={voidCheck} className="w-full rounded-lg py-2 text-sm text-red-600 hover:bg-red-50">{t('Hisobni bekor qilish')}</button>
        </div>
      </aside>
      {modal && <ProductModal product={modal} onClose={() => setModal(null)} onAdd={(it) => { add(it); setModal(null) }} />}
      {paying && <PaymentModal total={totals.total} onClose={() => setPaying(false)} onConfirm={pay} />}
      {weighing && <WeightModal product={weighing.product} size={weighing.size} onClose={() => setWeighing(null)} onAdd={(kg) => { add(buildItem(weighing.product, weighing.size, [], 1, kg)); setWeighing(null) }} />}
    </div>
  )
}

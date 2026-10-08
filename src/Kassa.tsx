import { useMemo, useState } from 'react'
import { Banknote, CakeSlice, Check, Coffee, CreditCard, Leaf, Milk, Minus, Plus, Printer, Search, ShoppingBag, Smartphone, Snowflake, Trash2, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { CATEGORIES, DEFAULT_MILK, MODIFIERS, PAYMENT_LABEL, PRODUCTS, buildItem, fmt, som, time } from './data'
import type { ModGroupId, Order, OrderItem, Payment, Product } from './data'
import { nextNumber, placeOrder, useAppState } from './store'

const CAT_ICON: Record<string, LucideIcon> = { espresso: Coffee, milk: Milk, cold: Snowflake, tea: Leaf, dessert: CakeSlice }
const CAT_TINT: Record<string, string> = {
  espresso: 'bg-amber-100 text-amber-800',
  milk: 'bg-orange-100 text-orange-800',
  cold: 'bg-sky-100 text-sky-800',
  tea: 'bg-emerald-100 text-emerald-800',
  dessert: 'bg-rose-100 text-rose-800',
}
const needsModal = (p: Product) => p.sizes.length > 1 || p.mods.length > 0

export default function Kassa() {
  useAppState()
  const [cat, setCat] = useState('milk')
  const [query, setQuery] = useState('')
  const [cart, setCart] = useState<OrderItem[]>([])
  const [customer, setCustomer] = useState('')
  const [discountPct, setDiscountPct] = useState(0)
  const [modal, setModal] = useState<Product | null>(null)
  const [paying, setPaying] = useState(false)
  const [receipt, setReceipt] = useState<Order | null>(null)
  const [cartOpen, setCartOpen] = useState(false)

  const products = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? PRODUCTS.filter((p) => p.name.toLowerCase().includes(q)) : PRODUCTS.filter((p) => p.cat === cat)
  }, [cat, query])

  const subtotal = cart.reduce((s, i) => s + i.unitPrice * i.qty, 0)
  const discount = Math.round((subtotal * discountPct) / 100 / 100) * 100
  const total = subtotal - discount
  const count = cart.reduce((s, i) => s + i.qty, 0)

  const addToCart = (item: OrderItem) =>
    setCart((c) => {
      const same = c.find((x) => x.key === item.key)
      return same ? c.map((x) => (x.key === item.key ? { ...x, qty: x.qty + item.qty } : x)) : [...c, item]
    })
  const changeQty = (key: string, d: number) =>
    setCart((c) => c.map((x) => (x.key === key ? { ...x, qty: x.qty + d } : x)).filter((x) => x.qty > 0))
  const clear = () => {
    setCart([])
    setCustomer('')
    setDiscountPct(0)
  }
  const onTile = (p: Product) => (needsModal(p) ? setModal(p) : addToCart(buildItem(p, p.sizes[0], [], 1)))

  const confirmPayment = (payment: Payment, cashGiven?: number) => {
    const order = placeOrder(cart, { customer: customer.trim(), discountPct, payment, cashGiven })
    setPaying(false)
    setCartOpen(false)
    clear()
    setReceipt(order)
  }

  const cartPanel = (
    <Cart
      number={nextNumber()} cart={cart} customer={customer} setCustomer={setCustomer}
      discountPct={discountPct} setDiscountPct={setDiscountPct} subtotal={subtotal} discount={discount} total={total}
      changeQty={changeQty} clear={clear} onPay={() => setPaying(true)} onClose={cartOpen ? () => setCartOpen(false) : undefined}
    />
  )

  return (
    <div className="flex h-full min-h-0">
      <aside className="hidden w-40 shrink-0 flex-col gap-2 overflow-y-auto border-r border-stone-200 bg-stone-100 p-3 md:flex lg:w-48">
        {CATEGORIES.map((c) => {
          const Icon = CAT_ICON[c.id]
          const active = !query && cat === c.id
          return (
            <button key={c.id} onClick={() => { setCat(c.id); setQuery('') }}
              className={`flex items-center gap-3 rounded-xl px-3 py-4 text-left font-medium ${active ? 'bg-stone-900 text-white shadow' : 'bg-white text-stone-700 hover:bg-stone-200'}`}>
              <Icon className="size-5 shrink-0" />{c.name}
            </button>
          )
        })}
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="space-y-3 border-b border-stone-200 bg-white p-3">
          <label className="flex items-center gap-2 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2.5 focus-within:border-amber-500">
            <Search className="size-4 text-stone-400" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Mahsulot qidirish" className="w-full bg-transparent outline-none" />
            {query && <button onClick={() => setQuery('')} aria-label="Tozalash"><X className="size-4 text-stone-400" /></button>}
          </label>
          <div className="-mx-3 flex gap-2 overflow-x-auto px-3 md:hidden">
            {CATEGORIES.map((c) => (
              <button key={c.id} onClick={() => { setCat(c.id); setQuery('') }}
                className={`shrink-0 rounded-full px-4 py-2 text-sm font-medium ${!query && cat === c.id ? 'bg-stone-900 text-white' : 'bg-stone-100 text-stone-700'}`}>
                {c.name}
              </button>
            ))}
          </div>
        </div>
        <div className="grid flex-1 grid-cols-2 content-start gap-3 overflow-y-auto p-3 pb-24 sm:grid-cols-3 md:pb-3 xl:grid-cols-4">
          {products.map((p) => {
            const Icon = CAT_ICON[p.cat]
            const minPrice = Math.min(...p.sizes.map((s) => s.price))
            return (
              <button key={p.id} onClick={() => onTile(p)}
                className="flex min-h-32 flex-col justify-between rounded-2xl border border-stone-200 bg-white p-3 text-left shadow-sm transition active:scale-[0.97] hover:border-amber-400">
                <span className={`grid size-10 place-items-center rounded-xl ${CAT_TINT[p.cat]}`}><Icon className="size-5" /></span>
                <span>
                  <span className="block font-semibold leading-tight">{p.name}</span>
                  <span className="mt-1 block text-sm text-stone-500">
                    {p.sizes.length > 1 ? `${fmt(minPrice)} dan` : som(minPrice)}
                    {p.sizes.length > 1 && <span className="ml-1 text-xs text-stone-400">· {p.sizes.map((s) => s.label).join('/')}</span>}
                  </span>
                </span>
              </button>
            )
          })}
          {products.length === 0 && <p className="col-span-full py-12 text-center text-stone-500">Hech narsa topilmadi.</p>}
        </div>
      </main>

      <aside className="hidden w-80 shrink-0 border-l border-stone-200 bg-white md:flex lg:w-96">{cartPanel}</aside>

      {count > 0 && !cartOpen && (
        <div className="fixed inset-x-0 bottom-0 z-30 p-3 md:hidden">
          <button onClick={() => setCartOpen(true)} className="flex w-full items-center justify-between rounded-2xl bg-stone-900 px-4 py-4 font-semibold text-white shadow-lg">
            <span className="flex items-center gap-2"><ShoppingBag className="size-5" />Savat · {count} ta</span>
            <span>{som(total)}</span>
          </button>
        </div>
      )}
      {cartOpen && <div className="fixed inset-0 z-40 flex bg-white md:hidden">{cartPanel}</div>}

      {modal && <ProductModal product={modal} onClose={() => setModal(null)} onAdd={(it) => { addToCart(it); setModal(null) }} />}
      {paying && <PaymentModal total={total} onClose={() => setPaying(false)} onConfirm={confirmPayment} />}
      {receipt && <ReceiptModal order={receipt} onClose={() => setReceipt(null)} />}
    </div>
  )
}

function Cart(props: {
  number: number; cart: OrderItem[]; customer: string; setCustomer: (v: string) => void
  discountPct: number; setDiscountPct: (v: number) => void; subtotal: number; discount: number; total: number
  changeQty: (key: string, d: number) => void; clear: () => void; onPay: () => void; onClose?: () => void
}) {
  const { cart } = props
  return (
    <div className="flex min-h-0 w-full flex-col">
      <div className="flex items-center justify-between border-b border-stone-200 px-4 py-3">
        <div>
          <div className="text-xs text-stone-500">Yangi buyurtma</div>
          <div className="text-lg font-bold">#{props.number}</div>
        </div>
        <div className="flex items-center gap-1">
          {cart.length > 0 && (
            <button onClick={props.clear} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-stone-500 hover:bg-stone-100">
              <Trash2 className="size-4" />Tozalash
            </button>
          )}
          {props.onClose && <button onClick={props.onClose} aria-label="Yopish" className="rounded-lg p-2 hover:bg-stone-100"><X className="size-5" /></button>}
        </div>
      </div>
      <div className="px-4 pt-3">
        <input value={props.customer} onChange={(e) => props.setCustomer(e.target.value)} placeholder="Mijoz ismi (stakan uchun)"
          className="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2.5 outline-none focus:border-amber-500" />
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto px-4 py-3">
        {cart.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-2 py-10 text-center text-stone-400">
            <ShoppingBag className="size-10" />Savat bo'sh. Mahsulotni tanlang.
          </div>
        )}
        {cart.map((it) => (
          <div key={it.key} className="rounded-xl border border-stone-200 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold">{it.name}{it.size && <span className="ml-1.5 rounded bg-stone-100 px-1.5 text-sm font-medium text-stone-600">{it.size}</span>}</div>
                {it.mods.length > 0 && <div className="mt-0.5 text-sm text-stone-500">{it.mods.join(', ')}</div>}
              </div>
              <div className="shrink-0 font-semibold">{fmt(it.unitPrice * it.qty)}</div>
            </div>
            <div className="mt-2 flex items-center gap-3">
              <button onClick={() => props.changeQty(it.key, -1)} aria-label="Kamaytirish" className="grid size-9 place-items-center rounded-lg bg-stone-100 hover:bg-stone-200"><Minus className="size-4" /></button>
              <span className="w-6 text-center font-semibold">{it.qty}</span>
              <button onClick={() => props.changeQty(it.key, 1)} aria-label="Ko'paytirish" className="grid size-9 place-items-center rounded-lg bg-stone-100 hover:bg-stone-200"><Plus className="size-4" /></button>
              <span className="ml-auto text-xs text-stone-400">{fmt(it.unitPrice)} × {it.qty}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="space-y-3 border-t border-stone-200 p-4">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-stone-500">Chegirma</span>
          {[0, 5, 10].map((p) => (
            <button key={p} onClick={() => props.setDiscountPct(p)}
              className={`rounded-lg px-3 py-1.5 font-medium ${props.discountPct === p ? 'bg-stone-900 text-white' : 'bg-stone-100 text-stone-700'}`}>
              {p === 0 ? "Yo'q" : `${p}%`}
            </button>
          ))}
        </div>
        {props.discount > 0 && (
          <div className="space-y-1 text-sm text-stone-500">
            <div className="flex justify-between"><span>Oraliq summa</span><span>{som(props.subtotal)}</span></div>
            <div className="flex justify-between"><span>Chegirma {props.discountPct}%</span><span>−{som(props.discount)}</span></div>
          </div>
        )}
        <button disabled={cart.length === 0} onClick={props.onPay}
          className="flex w-full items-center justify-between rounded-2xl bg-amber-600 px-5 py-4 text-lg font-bold text-white shadow hover:bg-amber-700 disabled:bg-stone-300">
          <span>To'lov</span><span>{som(props.total)}</span>
        </button>
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
          <button onClick={onClose} aria-label="Yopish" className="rounded-lg p-2 hover:bg-stone-100"><X className="size-5" /></button>
        </div>
        <div className="space-y-5 overflow-y-auto px-5 py-4">
          {product.sizes.length > 1 && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-stone-500">Hajm</h3>
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
              <h3 className="mb-2 text-sm font-semibold text-stone-500">Sut turi</h3>
              <div className="grid grid-cols-2 gap-2">
                {group('milk').map((m) => (
                  <Chip key={m.id} active={milk === m.id} onClick={() => setMilk(m.id)}>
                    {m.name}{m.price > 0 && <span className="text-stone-500"> +{fmt(m.price)}</span>}
                  </Chip>
                ))}
              </div>
            </section>
          )}
          {has('syrup') && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-stone-500">Sirop <span className="font-normal">(bir nechtasini tanlash mumkin)</span></h3>
              <div className="grid grid-cols-3 gap-2">
                {group('syrup').map((m) => (
                  <Chip key={m.id} active={syrups.includes(m.id)} onClick={() => setSyrups((s) => (s.includes(m.id) ? s.filter((x) => x !== m.id) : [...s, m.id]))}>
                    {m.name}<span className="block text-stone-500">+{fmt(m.price)}</span>
                  </Chip>
                ))}
              </div>
            </section>
          )}
          {has('shot') && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-stone-500">Qo'shimcha espresso</h3>
              <div className="grid grid-cols-3 gap-2">
                <Chip active={shot === ''} onClick={() => setShot('')}>Yo'q</Chip>
                {group('shot').map((m) => (
                  <Chip key={m.id} active={shot === m.id} onClick={() => setShot(m.id)}>
                    {m.name}<span className="block text-stone-500">+{fmt(m.price)}</span>
                  </Chip>
                ))}
              </div>
            </section>
          )}
        </div>
        <div className="flex items-center gap-3 border-t border-stone-200 p-4">
          <div className="flex items-center gap-2">
            <button onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="Kamaytirish" className="grid size-12 place-items-center rounded-xl bg-stone-100"><Minus className="size-5" /></button>
            <span className="w-6 text-center text-lg font-bold">{qty}</span>
            <button onClick={() => setQty((q) => q + 1)} aria-label="Ko'paytirish" className="grid size-12 place-items-center rounded-xl bg-stone-100"><Plus className="size-5" /></button>
          </div>
          <button onClick={() => onAdd(item)} className="flex flex-1 items-center justify-between gap-2 rounded-xl bg-amber-600 px-4 py-3.5 font-bold text-white hover:bg-amber-700">
            <span>Qo'shish</span><span>{som(item.unitPrice * qty)}</span>
          </button>
        </div>
      </div>
    </div>
  )
}

const PAY_OPTIONS: { id: Payment; icon: LucideIcon }[] = [
  { id: 'naqd', icon: Banknote }, { id: 'karta', icon: CreditCard }, { id: 'payme', icon: Smartphone }, { id: 'click', icon: Smartphone },
]

function PaymentModal({ total, onClose, onConfirm }: { total: number; onClose: () => void; onConfirm: (p: Payment, cash?: number) => void }) {
  const [method, setMethod] = useState<Payment>('karta')
  const [cash, setCash] = useState('')
  const given = Number(cash.replace(/\D/g, '')) || 0
  const quick = [...new Set([total, ...[50000, 100000, 200000].map((step) => Math.ceil(total / step) * step)])].sort((a, b) => a - b)
  const ok = method !== 'naqd' || given >= total

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4" onClick={onClose}>
      <div className="w-full rounded-t-3xl bg-white sm:max-w-md sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-stone-200 px-5 py-4">
          <div>
            <div className="text-sm text-stone-500">To'lanadigan summa</div>
            <div className="text-2xl font-bold">{som(total)}</div>
          </div>
          <button onClick={onClose} aria-label="Yopish" className="rounded-lg p-2 hover:bg-stone-100"><X className="size-5" /></button>
        </div>
        <div className="space-y-4 p-5">
          <div className="grid grid-cols-2 gap-2">
            {PAY_OPTIONS.map(({ id, icon: Icon }) => (
              <Chip key={id} active={method === id} onClick={() => setMethod(id)}>
                <span className="flex items-center gap-2 py-1 text-base"><Icon className="size-5" />{PAYMENT_LABEL[id]}</span>
              </Chip>
            ))}
          </div>
          {method === 'naqd' && (
            <div className="space-y-2">
              <input inputMode="numeric" autoFocus value={cash ? fmt(given) : ''} onChange={(e) => setCash(e.target.value)} placeholder="Mijoz bergan summa"
                className="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-3 text-lg outline-none focus:border-amber-500" />
              <div className="flex flex-wrap gap-2">
                {quick.map((q) => (
                  <button key={q} onClick={() => setCash(String(q))} className="rounded-lg bg-stone-100 px-3 py-2 text-sm font-medium hover:bg-stone-200">{fmt(q)}</button>
                ))}
              </div>
              {given > 0 && (
                <div className={`flex justify-between rounded-xl px-4 py-3 font-semibold ${given >= total ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-700'}`}>
                  <span>{given >= total ? 'Qaytim' : 'Yetmaydi'}</span><span>{som(Math.abs(given - total))}</span>
                </div>
              )}
            </div>
          )}
          {(method === 'payme' || method === 'click') && (
            <p className="rounded-xl bg-stone-100 px-4 py-3 text-sm text-stone-600">Demo: to'lov qo'lda tasdiqlanadi. QR va avtomatik tasdiqlash keyingi versiyada.</p>
          )}
          <button disabled={!ok} onClick={() => onConfirm(method, method === 'naqd' ? given : undefined)}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 py-4 text-lg font-bold text-white hover:bg-emerald-700 disabled:bg-stone-300">
            <Check className="size-5" />Tasdiqlash
          </button>
        </div>
      </div>
    </div>
  )
}

function ReceiptModal({ order, onClose }: { order: Order; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="flex max-h-[92dvh] w-full max-w-sm flex-col rounded-3xl bg-white" onClick={(e) => e.stopPropagation()}>
        <div className="flex flex-col items-center gap-1 px-5 pt-5 text-center">
          <span className="grid size-12 place-items-center rounded-full bg-emerald-100 text-emerald-700"><Check className="size-7" /></span>
          <div className="text-lg font-bold">Buyurtma #{order.number} qabul qilindi</div>
          <div className="text-sm text-stone-500">Barista ekraniga yuborildi</div>
        </div>
        <div className="print-area mx-5 my-4 overflow-y-auto rounded-xl border border-dashed border-stone-300 bg-stone-50 p-4 font-mono text-xs">
          <div className="text-center font-bold">COFFEEPOS DEMO</div>
          <div className="text-center text-stone-500">{new Date(order.createdAt).toLocaleDateString('ru-RU')} {time(order.createdAt)} · #{order.number}</div>
          {order.customer && <div className="mt-1 text-center">Mijoz: {order.customer}</div>}
          <div className="my-2 border-t border-dashed border-stone-300" />
          {order.items.map((it) => (
            <div key={it.key} className="mb-1">
              <div className="flex justify-between gap-2"><span>{it.qty}× {it.name} {it.size}</span><span>{fmt(it.unitPrice * it.qty)}</span></div>
              {it.mods.length > 0 && <div className="pl-3 text-stone-500">{it.mods.join(', ')}</div>}
            </div>
          ))}
          <div className="my-2 border-t border-dashed border-stone-300" />
          {order.discount > 0 && <div className="flex justify-between"><span>Chegirma</span><span>−{fmt(order.discount)}</span></div>}
          <div className="flex justify-between text-sm font-bold"><span>JAMI</span><span>{som(order.total)}</span></div>
          <div className="flex justify-between"><span>To'lov</span><span>{PAYMENT_LABEL[order.payment]}</span></div>
          {order.cashGiven !== undefined && (
            <>
              <div className="flex justify-between"><span>Berildi</span><span>{fmt(order.cashGiven)}</span></div>
              <div className="flex justify-between"><span>Qaytim</span><span>{fmt(order.cashGiven - order.total)}</span></div>
            </>
          )}
          <div className="mt-2 text-center text-stone-500">Rahmat! Yana keling.</div>
        </div>
        <div className="flex gap-2 p-5 pt-0">
          <button onClick={() => window.print()} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-stone-100 py-3 font-semibold hover:bg-stone-200"><Printer className="size-4" />Chek</button>
          <button onClick={onClose} className="flex-[2] rounded-xl bg-stone-900 py-3 font-semibold text-white">Yangi buyurtma</button>
        </div>
      </div>
    </div>
  )
}

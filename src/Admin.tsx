import { useEffect, useMemo, useState } from 'react'
import { t } from './i18n'
import { TriangleAlert } from 'lucide-react'
import { INGREDIENTS, ING, MOD, PAYMENT_LABEL, PRODUCTS, STATUS_LABEL, UNIT_LABEL, fmt, recipeCost, som, time } from './data'
import type { Payment } from './data'
import { api } from './api'
import { refreshMenu, startOfToday, stockMove, useAppState } from './store'
import { MenuEditor, ProductForm, ShiftsView, StaffView } from './AdminExtra'
import { InventoryView } from './Inventory'

type View = 'dashboard' | 'stock' | 'inventory' | 'menu' | 'recipes' | 'orders' | 'staff' | 'shifts'
const VIEWS: { id: View; label: string }[] = [
  { id: 'stock', label: 'Ombor' },
  { id: 'inventory', label: 'Inventarizatsiya' },
  { id: 'menu', label: 'Menyu' },
  { id: 'recipes', label: 'Texkarta' },
  { id: 'orders', label: 'Buyurtmalar' },
  { id: 'staff', label: 'Xodimlar' },
  { id: 'shifts', label: 'Smenalar' },
]
const WEEKDAY = ['Ya', 'Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh']
const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0)

export default function Admin({ initialView = 'stock' }: { initialView?: View }) {
  const [view, setView] = useState<View>(initialView)
  const { orders, stock, menuVersion } = useAppState()
  void menuVersion
  const today = useMemo(() => orders.filter((o) => o.createdAt >= startOfToday()), [orders])
  const low = INGREDIENTS.filter((i) => (stock[i.id] ?? 0) < i.min)

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-5 p-3 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-1 overflow-x-auto rounded-xl bg-stone-200/70 p-1">
            {initialView !== 'dashboard' && VIEWS.map((v) => (
              <button key={v.id} onClick={() => setView(v.id)}
                className={`shrink-0 rounded-lg px-3 py-2 text-sm font-medium sm:px-4 ${view === v.id ? 'bg-white shadow-sm' : 'text-stone-600'}`}>
                {t(v.label)}{v.id === 'stock' && low.length > 0 && <span className="ml-1.5 rounded-full bg-red-500 px-1.5 text-xs text-white">{low.length}</span>}
              </button>
            ))}
          </div>
        </div>
        {initialView === 'dashboard' && <Dashboard today={today} low={low.map((i) => i.name)} goStock={() => { window.location.hash = 'admin' }} />}
        {view === 'stock' && <Stock stock={stock} today={today} />}
        {view === 'inventory' && <InventoryView />}
        {view === 'menu' && <MenuEditor />}
        {view === 'recipes' && <Recipes />}
        {view === 'orders' && <Orders today={today} />}
        {view === 'staff' && <StaffView />}
        {view === 'shifts' && <ShiftsView />}
      </div>
    </div>
  )
}

type Orders = ReturnType<typeof useAppState>['orders']

function Card({ title, children, className = '' }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-stone-200 bg-white p-4 sm:p-5 ${className}`}>
      {title && <h2 className="mb-4 font-semibold">{title}</h2>}
      {children}
    </section>
  )
}

function Dashboard({ today, low, goStock }: { today: Orders; low: string[]; goStock: () => void }) {
  const revenue = today.reduce((s, o) => s + o.total, 0)
  const cost = today.reduce((s, o) => s + o.cost, 0)
  const profit = revenue - cost
  const avg = today.length ? revenue / today.length : 0

  const orderHours = today.map((o) => new Date(o.createdAt).getHours())
  const firstHour = Math.min(8, ...orderHours)
  const lastHour = Math.max(22, ...orderHours)
  const hours = Array.from({ length: lastHour - firstHour + 1 }, (_, i) => firstHour + i)
  const byHour = hours.map((h) => today.filter((o) => new Date(o.createdAt).getHours() === h).reduce((s, o) => s + o.total, 0))
  const maxHour = Math.max(1, ...byHour)

  const [daily, setDaily] = useState<{ day: number; revenue: number }[]>([])
  useEffect(() => {
    api<{ day: number; revenue: number }[]>('/api/reports/daily?days=7').then(setDaily).catch(() => setDaily([]))
  }, [revenue])
  const week = daily.map((d, i) => ({ label: i === daily.length - 1 ? t('Bugun') : t(WEEKDAY[new Date(d.day).getDay()]), value: d.revenue }))
  const maxWeek = Math.max(1, ...week.map((w) => w.value))

  const top = Object.values(
    today.flatMap((o) => o.items).reduce<Record<string, { name: string; qty: number; revenue: number; profit: number }>>((acc, it) => {
      const r = (acc[it.productId] ??= { name: it.name, qty: 0, revenue: 0, profit: 0 })
      r.qty += it.qty
      r.revenue += it.unitPrice * it.qty
      r.profit += (it.unitPrice - it.unitCost) * it.qty
      return acc
    }, {}),
  ).sort((a, b) => b.qty - a.qty).slice(0, 6)

  const payments = (Object.keys(PAYMENT_LABEL) as Payment[]).map((p) => ({ p, sum: today.filter((o) => o.payment === p).reduce((s, o) => s + o.total, 0) }))

  return (
    <div className="space-y-5">
      {low.length > 0 && (
        <button onClick={goStock} className="flex w-full items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-left text-red-800">
          <TriangleAlert className="mt-0.5 size-5 shrink-0" />
          <span><b>{t('{n} ta mahsulot tugayapti:', { n: low.length })}</b> {low.join(', ')}. <span className="underline">{t("Omborga o'tish")}</span></span>
        </button>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: t('Bugungi tushum'), value: som(revenue) },
          { label: t('Buyurtmalar'), value: String(today.length) },
          { label: t("O'rtacha chek"), value: som(avg) },
          { label: t('Yalpi foyda'), value: som(profit), sub: `${t('marja')} ${pct(profit, revenue)}%` },
        ].map((m) => (
          <div key={m.label} className="rounded-2xl border border-stone-200 bg-white p-4">
            <div className="text-sm text-stone-500">{m.label}</div>
            <div className="mt-1 text-xl font-bold sm:text-2xl">{m.value}</div>
            {m.sub && <div className="text-sm text-emerald-700">{m.sub}</div>}
          </div>
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t("Soatlar bo'yicha tushum (bugun)")}>
          <div className="flex h-44 items-end gap-1">
            {byHour.map((v, i) => (
              <div key={hours[i]} className="group relative flex h-full flex-1 flex-col justify-end">
                <div className="rounded-t bg-amber-500 group-hover:bg-amber-600" style={{ height: `${(v / maxHour) * 100}%`, minHeight: v ? 3 : 0 }} title={`${hours[i]}:00 — ${som(v)}`} />
              </div>
            ))}
          </div>
          <div className="mt-1 flex gap-1 text-[10px] text-stone-400">
            {hours.map((h) => <span key={h} className="flex-1 text-center">{h % 2 === 0 ? h : ''}</span>)}
          </div>
        </Card>
        <Card title={t('Haftalik tushum')}>
          <div className="flex h-44 items-end gap-2">
            {week.map((w) => (
              <div key={w.label} className="flex h-full flex-1 flex-col justify-end text-center">
                <span className="mb-1 text-[10px] text-stone-500">{fmt(w.value / 1000)}k</span>
                <div className={`rounded-t ${w.label === t('Bugun') ? 'bg-amber-500' : 'bg-stone-300'}`} style={{ height: `${(w.value / maxWeek) * 100}%` }} />
              </div>
            ))}
          </div>
          <div className="mt-1 flex gap-2 text-xs text-stone-500">{week.map((w) => <span key={w.label} className="flex-1 text-center">{w.label}</span>)}</div>
          <p className="mt-2 text-xs text-stone-400">{t("O'tgan kunlar — namuna ma'lumot.")}</p>
        </Card>
        <Card title={t('Top mahsulotlar (bugun)')}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-stone-500"><tr><th className="pb-2 font-medium">{t('Mahsulot')}</th><th className="pb-2 text-right font-medium">{t('Soni')}</th><th className="pb-2 text-right font-medium">{t('Tushum')}</th><th className="pb-2 text-right font-medium">{t('Foyda')}</th></tr></thead>
              <tbody>
                {top.map((t) => (
                  <tr key={t.name} className="border-t border-stone-100">
                    <td className="py-2">{t.name}</td><td className="py-2 text-right">{t.qty}</td><td className="py-2 text-right">{fmt(t.revenue)}</td><td className="py-2 text-right text-emerald-700">{fmt(t.profit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title={t("To'lov turlari (bugun)")}>
          <div className="space-y-3">
            {payments.map(({ p, sum }) => (
              <div key={p}>
                <div className="mb-1 flex justify-between text-sm"><span>{t(PAYMENT_LABEL[p])}</span><span className="text-stone-500">{som(sum)} · {pct(sum, revenue)}%</span></div>
                <div className="h-2.5 rounded-full bg-stone-100"><div className="h-full rounded-full bg-stone-800" style={{ width: `${pct(sum, revenue)}%` }} /></div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

function perBulk(cost: number, unit: string) {
  return unit === 'g' ? `${fmt(cost * 1000)} / kg` : unit === 'ml' ? `${fmt(cost * 1000)} / l` : `${fmt(cost)} / ${t('dona')}`
}

function Stock({ stock, today }: { stock: Record<string, number>; today: Orders }) {
  const [amounts, setAmounts] = useState<Record<string, string>>({})
  const [editingCost, setEditingCost] = useState<string | null>(null)
  const [newCost, setNewCost] = useState('')
  const [savingCost, setSavingCost] = useState(false)
  const role = useAppState().session?.staff.role
  const canEditCost = role === 'owner' || role === 'admin'
  const saveCost = async (i: typeof INGREDIENTS[number]) => {
    const cost = Number(newCost.replace(',', '.'))
    if (!newCost.trim() || !Number.isFinite(cost) || cost < 0) { alert('Narx 0 yoki undan katta son bo‘lishi kerak'); return }
    setSavingCost(true)
    try {
      await api(`/api/ingredients/${encodeURIComponent(i.id)}`, { method: 'PUT', body: { name: i.name, unit: i.unit, cost, min: i.min } })
      await refreshMenu()
      setEditingCost(null)
    } catch (e) { alert((e as Error).message) }
    finally { setSavingCost(false) }
  }
  const used: Record<string, number> = {}
  for (const o of today) for (const it of o.items) for (const l of it.consumption) used[l.ing] = (used[l.ing] ?? 0) + l.qty * it.qty

  return (
    <Card title={t('Ombor qoldiqlari')}>
      <p className="-mt-2 mb-4 text-sm text-stone-500">{t("Har bir sotuvda texkarta bo'yicha avtomatik ayiriladi. Kirim qilish uchun miqdorni yozing.")}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-sm">
          <thead className="text-left text-stone-500">
            <tr><th className="pb-2 font-medium">{t('Xomashyo')}</th><th className="pb-2 text-right font-medium">{t('Qoldiq')}</th><th className="pb-2 text-right font-medium">{t('Bugun sarf')}</th><th className="pb-2 text-right font-medium">{t('Tannarx')}</th><th className="pb-2 font-medium pl-4">{t('Holat')}</th><th className="pb-2 font-medium">{t('Kirim')}</th></tr>
          </thead>
          <tbody>
            {INGREDIENTS.map((i) => {
              const q = stock[i.id] ?? 0
              const isLow = q < i.min
              const amount = Number(amounts[i.id]) || 0
              return (
                <tr key={i.id} className="border-t border-stone-100">
                  <td className="py-2">{i.name}</td>
                  <td className={`py-2 text-right font-semibold tabular-nums ${isLow ? 'text-red-600' : ''}`}>{fmt(q)} {t(UNIT_LABEL[i.unit])}</td>
                  <td className="py-2 text-right tabular-nums text-stone-500">{fmt(used[i.id] ?? 0)}</td>
                  <td className="py-2 text-right text-stone-500">
                    {editingCost === i.id ? (
                      <div className="flex flex-wrap items-center justify-end gap-1">
                        <input aria-label="Bir birlik tannarxi" type="number" min="0" step="any" value={newCost} onChange={(e) => setNewCost(e.target.value)}
                          className="w-24 rounded-lg border border-stone-300 px-2 py-1.5 text-right" />
                        <button disabled={savingCost} onClick={() => void saveCost(i)} className="rounded-lg bg-stone-900 px-2 py-1.5 text-white disabled:opacity-50">Saqlash</button>
                        <button disabled={savingCost} onClick={() => setEditingCost(null)} className="rounded-lg border px-2 py-1.5">Bekor</button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-end gap-2">
                        <span>{perBulk(i.cost, i.unit)}</span>
                        {canEditCost && <button onClick={() => { setEditingCost(i.id); setNewCost(String(i.cost)) }} className="rounded-lg border border-stone-200 px-2 py-1 text-xs">Tahrirlash</button>}
                      </div>
                    )}
                  </td>
                  <td className="py-2 pl-4">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${isLow ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>{isLow ? t('Kam (min {n})', { n: fmt(i.min) }) : t('Yetarli')}</span>
                  </td>
                  <td className="py-2">
                    <div className="flex gap-1">
                      <input inputMode="numeric" value={amounts[i.id] ?? ''} onChange={(e) => setAmounts((a) => ({ ...a, [i.id]: e.target.value.replace(/\D/g, '') }))}
                        placeholder={t(UNIT_LABEL[i.unit])} className="w-20 rounded-lg border border-stone-200 px-2 py-1.5 outline-none focus:border-amber-500" />
                      <button disabled={!amount} onClick={() => { stockMove(i.id, amount, 'intake').then(() => setAmounts((a) => ({ ...a, [i.id]: '' }))).catch((e: Error) => alert(e.message)) }}
                        className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-semibold text-white disabled:bg-stone-200 disabled:text-stone-400">{t("Qo'shish")}</button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Recipes() {
  const [pid, setPid] = useState('cappuccino')
  const [editing, setEditing] = useState(false)
  const { menuVersion, session } = useAppState()
  void menuVersion
  const p = PRODUCTS.find((x) => x.id === pid) ?? PRODUCTS[0]
  if (!p) return <Card><p className="text-stone-500">{t("Menyu bo'sh.")}</p></Card>
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">{t("Texkarta")}</h2>
        <button onClick={() => setEditing(true)} className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-semibold text-white">{t("Tahrirlash")}</button>
      </div>
      <div className="flex flex-wrap gap-2">
        {PRODUCTS.map((x) => (
          <button key={x.id} onClick={() => setPid(x.id)} className={`rounded-full px-3 py-1.5 text-sm font-medium ${x.id === pid ? 'bg-stone-900 text-white' : 'border border-stone-200 bg-white text-stone-700'}`}>{x.name}</button>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {p.sizes.map((s) => {
          const cost = recipeCost(s.recipe)
          return (
            <Card key={s.code} title={`${p.name}${s.label ? ` ${s.label}` : ''}${s.volume ? ` · ${s.volume}` : ''}`}>
              <table className="w-full text-sm">
                <tbody>
                  {s.recipe.map((l, li) => (
                    <tr key={li} className="border-t border-stone-100">
                      <td className="py-1.5">{ING[l.ing]?.name ?? l.ing}</td>
                      <td className="py-1.5 text-right text-stone-500">{l.qty} {ING[l.ing] ? t(UNIT_LABEL[ING[l.ing].unit]) : ''}</td>
                      <td className="py-1.5 text-right tabular-nums">{fmt((ING[l.ing]?.cost ?? 0) * l.qty)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <dl className="mt-3 space-y-1 border-t border-stone-200 pt-3 text-sm">
                <div className="flex justify-between"><dt className="text-stone-500">{t('Tannarx')}</dt><dd className="font-semibold">{som(cost)}</dd></div>
                <div className="flex justify-between"><dt className="text-stone-500">{t('Sotuv narxi')}</dt><dd className="font-semibold">{som(s.price)}</dd></div>
                <div className="flex justify-between"><dt className="text-stone-500">{t('Marja')}</dt><dd className="font-semibold text-emerald-700">{pct(s.price - cost, s.price)}%</dd></div>
              </dl>
            </Card>
          )
        })}
      </div>
      {editing && <ProductForm key={p.id} product={p} canDelete={false} onClose={() => { setEditing(false); void refreshMenu() }} />}
      {p.mods.length > 0 && (
        <p className="text-sm text-stone-500">
          {t("Qo'shimchalar texkartani avtomatik o'zgartiradi:")} {Object.values(MOD).filter((m) => p.mods.includes(m.group) && m.price > 0).map((m) => m.name).join(', ')}.
          {t("Masalan, bodom suti oddiy sut o'rniga ayiriladi, sirop +15 ml, +1 shot +9 g kofe.")}
        </p>
      )}
    </div>
  )
}

function Orders({ today }: { today: Orders }) {
  const list = [...today].sort((a, b) => b.createdAt - a.createdAt)
  return (
    <Card title={t('Bugungi buyurtmalar ({n})', { n: list.length })}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-stone-500">
            <tr><th className="pb-2 font-medium">#</th><th className="pb-2 font-medium">{t('Vaqt')}</th><th className="pb-2 font-medium">{t('Mijoz')}</th><th className="pb-2 font-medium">{t('Tarkib')}</th><th className="pb-2 font-medium">{t("To'lov")}</th><th className="pb-2 text-right font-medium">{t('Summa')}</th><th className="pb-2 pl-4 font-medium">{t('Holat')}</th></tr>
          </thead>
          <tbody>
            {list.map((o) => (
              <tr key={o.id} className="border-t border-stone-100 align-top">
                <td className="py-2 font-semibold">{o.number}</td>
                <td className="py-2 text-stone-500">{time(o.createdAt)}</td>
                <td className="py-2">{o.customer || '—'}</td>
                <td className="py-2 text-stone-600">{o.items.map((it) => `${it.qty}× ${it.name}${it.size ? ' ' + it.size : ''}`).join(', ')}</td>
                <td className="py-2">{t(PAYMENT_LABEL[o.payment])}</td>
                <td className="py-2 text-right font-semibold tabular-nums">{fmt(o.total)}</td>
                <td className="py-2 pl-4"><span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs">{t(STATUS_LABEL[o.status])}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

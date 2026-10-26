import { Fragment, useEffect, useMemo, useState } from 'react'
import { t, tCatalogName } from './i18n'
import { exportExcel } from './exportExcel'
import { TriangleAlert, TrendingUp, ShoppingCart, Receipt, CircleDollarSign, LayoutDashboard, Warehouse, ClipboardCheck, Coffee, BookOpen, ReceiptText, PackagePlus, Users, CalendarClock, Wallet, Gift, ChartNoAxesCombined, BadgeDollarSign, Printer } from 'lucide-react'
import { INGREDIENTS, ING, MOD, PAYMENT_LABEL, PRODUCTS, STATUS_LABEL, UNIT_LABEL, fmt, recipeCost, som } from './data'
import type { Payment } from './data'
import { api } from './api'
import { startOfToday, useAppState, sync, refreshMenu } from './store'
import PurchaseInvoices from './PurchaseInvoices'
import Expenses from './Expenses'
import BonusSettings from './BonusSettings'
import Finance from './Finance'
import Payroll from './Payroll'
import CashierReport from './CashierReport'
import PrinterSettings from './PrinterSettings'
import { MenuEditor, ShiftsView, StaffView } from './AdminExtra'
import { InventoryView } from './Inventory'

type View = 'dashboard' | 'receiving' | 'stock' | 'inventory' | 'menu' | 'recipes' | 'orders' | 'cashierReport' | 'staff' | 'shifts' | 'expenses' | 'bonus' | 'finance' | 'payroll' | 'printer'
const VIEWS: { id: View; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'stock', label: 'Ombor' },
  { id: 'receiving', label: 'Prixod' },
  { id: 'inventory', label: 'Inventarizatsiya' },
  { id: 'menu', label: 'Menyu' },
  { id: 'recipes', label: 'Texkarta' },
  { id: 'orders', label: 'Cheklar tarixi' },
  { id: 'cashierReport', label: 'Kassirlar hisoboti' },
  { id: 'staff', label: 'Xodimlar' },
  { id: 'shifts', label: 'Smenalar' },
  { id: 'expenses', label: 'Xarajatlar' },
  { id: 'finance', label: 'Moliya hisoboti' },
  { id: 'payroll', label: 'Oylik hisobi' },
  { id: 'printer', label: 'Chek printer sozlamasi' },
  { id: 'bonus', label: 'Bonuslar' },
]
const VIEW_ICONS = { dashboard: LayoutDashboard, stock: Warehouse, receiving: PackagePlus, inventory: ClipboardCheck, menu: Coffee, recipes: BookOpen, orders: ReceiptText, cashierReport: ChartNoAxesCombined, staff: Users, shifts: CalendarClock, expenses: Wallet, bonus: Gift, finance: ChartNoAxesCombined, payroll: BadgeDollarSign, printer: Printer }
const WEEKDAY = ['Ya', 'Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh']
const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0)

export default function Admin() {
  const [view, setView] = useState<View>('dashboard')
  const { orders, stock, menuVersion } = useAppState()
  void menuVersion
  const today = useMemo(() => orders.filter((o) => o.createdAt >= startOfToday()), [orders])
  const low = INGREDIENTS.filter((i) => i.min > 0 && (stock[i.id] ?? 0) <= i.min)

  return (
    <div className="admin-shell h-full overflow-y-auto bg-stone-50">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 p-3 md:flex-row md:gap-5 md:p-5">
        <aside className="shrink-0 self-start rounded-2xl border border-stone-200 bg-white p-3 shadow-sm md:sticky md:top-4 md:w-56 lg:w-60">
          <div className="mb-3 hidden px-3 pt-2 md:block">
            <p className="text-xs font-semibold uppercase tracking-widest text-stone-400">{t('Boshqaruv')}</p>
            <h2 className="mt-1 text-lg font-bold text-stone-900">{t('Admin panel')}</h2>
          </div>
          <nav aria-label={t('Admin bo‘limlari')} className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
            {VIEWS.map((v) => {
              const Icon = VIEW_ICONS[v.id]
              return <button key={v.id} onClick={() => setView(v.id)} aria-current={view === v.id ? 'page' : undefined}
                className={`flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors md:w-full ${view === v.id ? 'bg-stone-900 text-white shadow-sm' : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'}`}>
                <Icon className="size-[18px] shrink-0" />
                <span className="flex-1 whitespace-nowrap">{t(v.label)}</span>
                {v.id === 'stock' && low.length > 0 && <span className="rounded-full bg-red-500 px-1.5 text-xs text-white">{low.length}</span>}
              </button>
            })}
          </nav>
        </aside>
        <main className="min-w-0 flex-1 space-y-5">
          {view === 'dashboard' && <Dashboard today={today} low={low.map((i) => ({ name: i.name, stock: stock[i.id] ?? 0, min: i.min, unit: i.unit }))} goStock={() => setView('stock')} />}
          {view === 'stock' && <StockOverview />}
          {view === 'receiving' && <PurchaseInvoices />}
          {view === 'inventory' && <InventoryView />}
          {view === 'menu' && <MenuEditor />}
          {view === 'recipes' && <Recipes onEdit={() => setView('menu')} />}
          {view === 'orders' && <Orders today={today} />}
          {view === 'cashierReport' && <CashierReport />}
          {view === 'staff' && <StaffView />}
          {view === 'shifts' && <ShiftsView />}
          {view === 'expenses' && <Expenses />}
          {view === 'bonus' && <BonusSettings />}
          {view === 'finance' && <Finance />}
          {view === 'payroll' && <Payroll />}
          {view === 'printer' && <PrinterSettings />}
        </main>
      </div>
    </div>
  )
}

function StockOverview() {
  const { stock } = useAppState()
  const [removeError, setRemoveError] = useState('')
  const [removing, setRemoving] = useState<string | null>(null)
  const remove = async (id: string, name: string) => {
    if (!window.confirm(t('Mahsulot o‘chirilsinmi?') + ' ' + name)) return
    setRemoving(id); setRemoveError('')
    try { await api('/api/ingredients/' + encodeURIComponent(id), { method: 'DELETE' }); await refreshMenu() }
    catch (e) { setRemoveError((e as Error).message) }
    finally { setRemoving(null) }
  }
  const download = () => exportExcel('coffeepos-ombor', ['Xomashyo', 'Birlik', 'Qoldiq', 'Minimal qoldiq', 'Tannarx', 'Qoldiq qiymati'],
    INGREDIENTS.map(i => [tCatalogName(i.name), t(UNIT_LABEL[i.unit]), stock[i.id] ?? 0, i.min, i.cost, Math.round((stock[i.id] ?? 0) * i.cost)]))
  return <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-lg font-semibold">{t('Xomashyo')}</h2>
      <button onClick={download} className="rounded-lg border px-3 py-2 text-sm font-semibold">{t('Excelga eksport')}</button>
    </div>
    <div className="overflow-x-auto"><table className="w-full min-w-[530px] text-sm">
      <thead><tr className="text-left text-stone-500"><th className="py-2">{t('Xomashyo')}</th><th>{t('Birlik')}</th><th>{t('Qoldiq')}</th><th>{t('Min qoldiq')}</th><th>{t('Tannarx')}</th><th>{t('Amallar')}</th></tr></thead>
      <tbody>{INGREDIENTS.map(i => <tr key={i.id} className="border-t">
        <td className="py-2 font-medium">{tCatalogName(i.name)}</td><td>{t(UNIT_LABEL[i.unit])}</td>
        <td className={i.min > 0 && (stock[i.id] ?? 0) <= i.min ? 'font-bold text-red-600' : ''}>{fmt(stock[i.id] ?? 0)}</td>
        <td>{fmt(i.min)}</td><td>{som(Math.round((stock[i.id] ?? 0) * i.cost))}</td><td><button type="button" title={t('Mahsulotni o‘chirish')} aria-label={t('Mahsulotni o‘chirish')} disabled={removing !== null || Math.abs(stock[i.id] ?? 0) > 0.000001} onClick={() => void remove(i.id, i.name)} className="rounded-lg border border-red-300 px-2 py-1 text-xs text-red-500 disabled:cursor-not-allowed disabled:opacity-30">{t('O‘chirish')}</button></td>
      </tr>)}</tbody>
    </table></div>
    {removeError && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{removeError}</p>}
    <p className="mt-2 text-xs text-stone-500">{t('Faqat qoldig‘i nol bo‘lgan, tarix va texkartalarda ishlatilmagan tovarni o‘chirish mumkin.')}</p>
  </section>
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

function Dashboard({ today, low, goStock }: { today: Orders; low: { name: string; stock: number; min: number; unit: string }[]; goStock: () => void }) {
  const active = today.filter(o => o.status !== 'cancelled' && !o.pendingSync)
  const revenue = active.reduce((s, o) => s + o.total, 0)
  const cost = active.reduce((s, o) => s + o.cost, 0)
  const profit = revenue - cost
  const avg = active.length ? revenue / active.length : 0

  const orderHours = active.map((o) => new Date(o.createdAt).getHours())
  const firstHour = Math.min(8, ...orderHours)
  const lastHour = Math.max(22, ...orderHours)
  const hours = Array.from({ length: lastHour - firstHour + 1 }, (_, i) => firstHour + i)
  const byHour = hours.map((h) => active.filter((o) => new Date(o.createdAt).getHours() === h).reduce((s, o) => s + o.total, 0))
  const maxHour = Math.max(1, ...byHour)

  const [daily, setDaily] = useState<{ day: number; revenue: number }[]>([])
  useEffect(() => {
    api<{ day: number; revenue: number }[]>('/api/reports/daily?days=7').then(setDaily).catch(() => setDaily([]))
  }, [revenue])
  const week = daily.map((d, i) => ({ label: i === daily.length - 1 ? t('Bugun') : t(WEEKDAY[new Date(d.day).getDay()]), value: d.revenue }))
  const maxWeek = Math.max(1, ...week.map((w) => w.value))

  const top = Object.values(
    active.flatMap((o) => o.items).reduce<Record<string, { name: string; qty: number; revenue: number; profit: number }>>((acc, it) => {
      const r = (acc[it.productId] ??= { name: it.name, qty: 0, revenue: 0, profit: 0 })
      r.qty += it.qty
      r.revenue += it.unitPrice * it.qty
      r.profit += (it.unitPrice - it.unitCost) * it.qty
      return acc
    }, {}),
  ).sort((a, b) => b.qty - a.qty).slice(0, 6)

  const payments = (['naqd', 'karta', 'payme', 'click'] as const).map((p) => ({
    p, sum: active.reduce((s, o) => s + (o.paymentParts
      ? o.paymentParts.filter(part => part.method === p).reduce((v, part) => v + part.amount, 0)
      : o.payment === p ? o.total : 0), 0),
  }))

  return (
    <div className="premium-dashboard space-y-5">
      <div className="premium-titlebar"><div><p className="premium-eyebrow">COFFEEPOS · {t('Analitika')}</p><h1 className="text-2xl font-extrabold">{t("Admin panel")}</h1><p className="text-sm text-stone-500">{t("Bugungi ko‘rsatkichlar va savdo tahlili")}</p></div><div className="premium-date">{new Date().toLocaleDateString()} · {t("Bugun")}</div></div>
      {low.length > 0 && (
        <button onClick={goStock} className="flex w-full items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-left text-red-800">
          <TriangleAlert className="mt-0.5 size-5 shrink-0" />
          <span><b>{t('{n} ta mahsulot tugayapti:', { n: low.length })}</b> {low.map(i => `${tCatalogName(i.name)} (${fmt(i.stock)}/${fmt(i.min)} ${t(i.unit)})`).join(', ')}. <span className="underline">{t("Omborga o'tish")}</span></span>
        </button>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: t('Bugungi tushum'), value: som(revenue), icon: CircleDollarSign },
          { label: t('Buyurtmalar'), value: String(active.length), icon: ShoppingCart },
          { label: t("O'rtacha chek"), value: som(avg), icon: Receipt },
          { label: t('Yalpi foyda'), value: som(profit), icon: TrendingUp, sub: `${t('marja')} ${pct(profit, revenue)}%` },
        ].map((m) => (
          <div key={m.label} className="premium-kpi rounded-2xl border border-stone-200 bg-white p-4">
            <div className="premium-kpi-icon"><m.icon className="size-6"/></div>
            <div className="text-sm text-stone-500">{m.label}</div>
            <div className="mt-2 text-xl font-extrabold tracking-tight sm:text-2xl">{m.value}</div>
            {m.sub && <div className="mt-2 text-sm font-semibold text-emerald-700">{m.sub}</div>}
          </div>
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t("Soatlar bo'yicha tushum (bugun)")} className="premium-chart premium-chart-hour">
          <div className="premium-plot flex h-52 items-end gap-1">
            {byHour.map((v, i) => (
              <div key={hours[i]} className="group relative flex h-full flex-1 flex-col justify-end">
                <div className="premium-bar rounded-t bg-amber-500 group-hover:bg-amber-600" style={{ height: `${(v / maxHour) * 100}%`, minHeight: v ? 3 : 0 }} title={`${hours[i]}:00 — ${som(v)}`} />
              </div>
            ))}
          </div>
          <div className="mt-1 flex gap-1 text-[10px] text-stone-400">
            {hours.map((h) => <span key={h} className="flex-1 text-center">{h % 2 === 0 ? h : ''}</span>)}
          </div>
        </Card>
        <Card title={t('Haftalik tushum')} className="premium-chart premium-chart-week">
          <div className="premium-plot flex h-52 items-end gap-2">
            {week.map((w) => (
              <div key={w.label} className="flex h-full flex-1 flex-col justify-end text-center">
                <span className="mb-1 text-[10px] text-stone-500">{fmt(w.value / 1000)}k</span>
                <div className={`premium-bar rounded-t ${w.label === t('Bugun') ? 'bg-amber-500' : 'bg-stone-300'}`} style={{ height: `${(w.value / maxWeek) * 100}%` }} />
              </div>
            ))}
          </div>
          <div className="mt-1 flex gap-2 text-xs text-stone-500">{week.map((w) => <span key={w.label} className="flex-1 text-center">{w.label}</span>)}</div>
          <p className="mt-2 text-xs text-stone-400">{t("O'tgan kunlar — namuna ma'lumot.")}</p>
        </Card>
        <Card title={t('Top mahsulotlar (bugun)')} className="premium-chart premium-top">
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
        <Card title={t("To'lov turlari (bugun)")} className="premium-chart premium-payments">
          <div className="premium-payments-layout"><div className="premium-donut" style={{ background: revenue ? `conic-gradient(#eeb458 0 ${pct(payments[0].sum,revenue)}%, #b8753c ${pct(payments[0].sum,revenue)}% ${pct(payments[0].sum+payments[1].sum,revenue)}%, #f5dfb6 ${pct(payments[0].sum+payments[1].sum,revenue)}% ${pct(payments[0].sum+payments[1].sum+payments[2].sum,revenue)}%, #696263 ${pct(payments[0].sum+payments[1].sum+payments[2].sum,revenue)}% 100%)` : undefined }}><span>{som(revenue)}</span></div><div className="space-y-3 flex-1">
            {payments.map(({ p, sum }) => (
              <div key={p}>
                <div className="mb-1 flex justify-between text-sm"><span>{t(PAYMENT_LABEL[p])}</span><span className="text-stone-500">{som(sum)} · {pct(sum, revenue)}%</span></div>
                <div className="h-2.5 rounded-full bg-stone-100"><div className="h-full rounded-full bg-stone-800" style={{ width: `${pct(sum, revenue)}%` }} /></div>
              </div>
            ))}
          </div></div>
        </Card>
      </div>
    </div>
  )
}

function Recipes({ onEdit }: { onEdit: () => void }) {
  const [pid, setPid] = useState('cappuccino')
  const p = PRODUCTS.find((x) => x.id === pid) ?? PRODUCTS[0]
  if (!p) return <Card><p className="text-stone-500">{t("Menyu bo'sh.")}</p></Card>
  return (
    <div className="space-y-4">
      <div className="flex justify-end gap-2"><button onClick={onEdit} className="rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white">{t('Texkartani qo‘lda tahrirlash')}</button><button className="rounded-lg border px-3 py-2 text-sm" onClick={() => exportExcel('coffeepos-texkarta',
        ['Mahsulot','O‘lcham','Hajm','Xomashyo','Miqdor','Birlik','Xomashyo tannarxi','Sotuv narxi'],
        PRODUCTS.flatMap(product => product.sizes.flatMap(size => size.recipe.map(line =>
          [product.name,size.label,size.volume ?? '',ING[line.ing]?.name ?? line.ing,line.qty,
           ING[line.ing] ? UNIT_LABEL[ING[line.ing].unit] : '',Math.round(line.qty*(ING[line.ing]?.cost ?? 0)),size.price]))))}
        >{t('Excelga eksport')}</button></div>
      <div className="flex flex-wrap gap-2">
        {PRODUCTS.map((x) => (
          <button key={x.id} onClick={() => setPid(x.id)} className={`rounded-full px-3 py-1.5 text-sm font-medium ${x.id === pid ? 'bg-stone-900 text-white' : 'border border-stone-200 bg-white text-stone-700'}`}>{tCatalogName(x.name)}</button>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {p.sizes.map((s) => {
          const cost = recipeCost(s.recipe)
          return (
            <Card key={s.code} title={`${tCatalogName(p.name)}${s.label ? ` ${s.label}` : ''}${s.volume ? ` · ${s.volume}` : ''}`}>
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
      {p.mods.length > 0 && (
        <p className="text-sm text-stone-500">
          {t("Qo'shimchalar texkartani avtomatik o'zgartiradi:")} {Object.values(MOD).filter((m) => p.mods.includes(m.group) && m.price > 0).map((m) => tCatalogName(m.name)).join(', ')}.
          {t("Masalan, bodom suti oddiy sut o'rniga ayiriladi, sirop +15 ml, +1 shot +9 g kofe.")}
        </p>
      )}
    </div>
  )
}

type HistoricalOrder = Orders[number] & { shiftId?: number; cancelledAt?: number | null; cancelledBy?: string | null; cancelReason?: string | null }
type HistoricalShift = { shift: { id: number; staff: string; openedAt: number; closedAt?: number | null } }
const localDate = (d: Date) => [d.getFullYear(), String(d.getMonth()+1).padStart(2,'0'), String(d.getDate()).padStart(2,'0')].join('-')
function Orders({ today }: { today: Orders }) {
  const [from, setFrom] = useState(() => localDate(new Date()))
  const [to, setTo] = useState(() => localDate(new Date()))
  const [staff, setStaff] = useState('')
  const [shiftId, setShiftId] = useState('')
  const [shifts, setShifts] = useState<HistoricalShift[]>([])
  const [history, setHistory] = useState<HistoricalOrder[]>(today)
  const [selected, setSelected] = useState<string | null>(null)
  const [printing, setPrinting] = useState<HistoricalOrder | null>(null)
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const reload = async () => {
    setBusy(true); setActionError('')
    try {
      const start = new Date(from + 'T00:00:00').getTime()
      const end = new Date(to + 'T00:00:00').getTime() + 86400000
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) throw new Error(t('Sana oralig‘ini to‘g‘ri tanlang'))
      const params = new URLSearchParams({ from_ms: String(start), to_ms: String(end) })
      if (staff) params.set('staff', staff)
      if (shiftId) params.set('shift_id', shiftId)
      setHistory(await api<HistoricalOrder[]>('/api/orders/history?' + params.toString()))
    } catch(e) { setActionError((e as Error).message) } finally { setBusy(false) }
  }
  useEffect(() => { void api<HistoricalShift[]>('/api/shifts').then(setShifts).catch(()=>{} ) }, [])
  useEffect(() => { void reload() }, [from, to, staff, shiftId])
  const list = [...history].sort((a,b)=>b.createdAt-a.createdAt)
  const cancelled = list.filter(o=>o.status === 'cancelled')
  const actual = list.filter(o=>o.status !== 'cancelled')
  const cashierNames = [...new Set(shifts.map(s=>s.shift.staff).concat(history.map(o=>o.barista)).filter(Boolean))]
  const cancel = async (o: HistoricalOrder) => {
    const reason = window.prompt(t('Otmena sababi (kamida 3 ta belgi):'))
    if (!reason || reason.trim().length < 3) return
    try { await api('/api/orders/' + o.id + '/cancel', { method:'POST', body:{ reason:reason.trim() } }); await sync(); await reload() }
    catch(e) { setActionError((e as Error).message) }
  }
  const reprint = (o: HistoricalOrder) => { setPrinting(o); window.setTimeout(()=>window.print(),100) }
  return <Card title={t('Cheklar tarixi · batafsil hisobot')}>
    <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <label className="text-sm">{t("Boshlanish sanasi")}<input aria-label={t("Boshlanish sanasi")} className="mt-1 w-full rounded-lg border p-2" type="date" value={from} onChange={e=>setFrom(e.target.value)} /></label>
      <label className="text-sm">{t("Tugash sanasi")}<input aria-label={t("Tugash sanasi")} className="mt-1 w-full rounded-lg border p-2" type="date" value={to} onChange={e=>setTo(e.target.value)} /></label>
      <label className="text-sm">{t("Kassir / xodim")}<select className="mt-1 w-full rounded-lg border p-2" value={staff} onChange={e=>setStaff(e.target.value)}><option value="">{t("Barcha xodimlar")}</option>{cashierNames.map(n=><option key={n}>{n}</option>)}</select></label>
      <label className="text-sm">{t("Smena")}<select className="mt-1 w-full rounded-lg border p-2" value={shiftId} onChange={e=>setShiftId(e.target.value)}><option value="">{t("Barcha smenalar")}</option>{shifts.map(s=><option key={s.shift.id} value={s.shift.id}>№{s.shift.id} · {s.shift.staff} · {new Date(s.shift.openedAt).toLocaleDateString()}</option>)}</select></label>
    </div>
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="rounded-lg bg-stone-100 px-3 py-2 text-sm font-semibold">{t('Cheklar')}: {list.length}</span>
      <span className="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800">{t('Sotuv')}: {fmt(actual.reduce((v,o)=>v+o.total,0))} {t("so'm")}</span>
      <span className="rounded-lg bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{t('Otmena')}: {cancelled.length} · {fmt(cancelled.reduce((v,o)=>v+o.total,0))} {t("so'm")}</span>
      <button disabled={busy} onClick={()=>void reload()} className="rounded-lg border px-3 py-2 text-sm">{t(busy?'Yuklanmoqda…':'Yangilash')}</button>
      <button className="rounded-lg border px-3 py-2 text-sm" onClick={()=>exportExcel('coffeepos-cheklar-tarixi',['Chek','Sana','Kassir','Smena','Mijoz','Mahsulotlar','To‘lov','Summa','Status','Otmena xodimi','Sabab'].map(label => t(label)),list.map(o=>[o.number,new Date(o.createdAt).toLocaleString(),o.barista,o.shiftId||'',o.customer,o.items.map(i=>i.qty+' × '+i.name+' '+i.size).join('; '),o.payment,o.total,o.status,o.cancelledBy||'',o.cancelReason||'']))}>{t("Excelga eksport")}</button>
    </div>
    {printing && <div className="print-area hidden print:block bg-white p-4 font-mono text-black"><h2>CoffeePOS · №{printing.number}</h2><p>{new Date(printing.createdAt).toLocaleString()}</p>{printing.items.map((i,k)=><p key={k}>{i.qty} × {tCatalogName(i.name)} {i.size} — {fmt(i.qty*i.unitPrice)}</p>)}<b>{t('Jami')}: {fmt(printing.total)} {t("so'm")}</b></div>}
    {actionError && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-2 text-red-700">{actionError}</p>}
    <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-sm"><thead><tr className="border-b text-left text-stone-500"><th className="p-2">№</th><th className="p-2">{t("Sana, vaqt")}</th><th className="p-2">{t("Kassir / Smena")}</th><th className="p-2">{t("Mijoz")}</th><th className="p-2">{t("Summa")}</th><th className="p-2">{t("Holat")}</th><th className="p-2">{t("Amallar")}</th></tr></thead><tbody>{list.map(o=><Fragment key={o.id}><tr className={o.status==='cancelled'?'border-b border-red-200 bg-red-50 text-red-900':'border-b border-stone-100'}><td className="p-2 font-bold">№{o.number}</td><td className="p-2">{new Date(o.createdAt).toLocaleString()}</td><td className="p-2">{o.barista||'—'}<span className="block text-xs opacity-70">{t('Smena')} №{o.shiftId||'—'}</span></td><td className="p-2">{o.customer||'—'}</td><td className="p-2 font-semibold">{fmt(o.total)}</td><td className="p-2">{o.status==='cancelled'?<span className="rounded-full bg-red-600 px-2 py-1 text-white">{t('Otmena')}</span>:t(STATUS_LABEL[o.status])}</td><td className="p-2"><div className="flex gap-2"><button className="rounded-lg border px-2 py-1" onClick={()=>setSelected(selected===o.id?null:o.id)}>{t("Batafsil")}</button><button className="rounded-lg border px-2 py-1" onClick={()=>reprint(o)}>{t("Perechek")}</button>{o.status==='new'&&!o.pendingSync&&<button className="rounded-lg border border-red-300 px-2 py-1 text-red-700" onClick={()=>void cancel(o)}>{t("Otmena")}</button>}</div></td></tr>{selected===o.id&&<tr key={o.id+'-details'}><td colSpan={7} className="border-b bg-stone-50 p-4"><div className="mb-2 font-semibold">{t('Chek')} №{o.number} · {t("To'lov")}: {t(PAYMENT_LABEL[o.payment])} · {t('Jami')}: {fmt(o.total)} {t("so'm")}</div><div className="space-y-1">{o.items.map((item,i)=><div key={i} className="flex flex-wrap justify-between gap-2 border-b border-stone-200 py-1"><span>{item.qty} × {tCatalogName(item.name)} {item.size} {item.mods?.join(', ')}</span><span>{fmt(item.unitPrice)} × {item.qty} = {fmt(item.unitPrice*item.qty)} so‘m</span></div>)}</div><div className="mt-2 text-sm">{t('Chegirma')}: {fmt(o.discount)} {t("so'm")} · {t('Tannarx')}: {fmt(o.cost)} {t("so'm")}</div>{o.status==='cancelled'&&<div className="mt-2 rounded-lg bg-red-100 p-2 text-red-800">{t('Otmena qilgan')}: {o.cancelledBy||'—'} · {o.cancelReason||t('Sabab ko‘rsatilmagan')} · {o.cancelledAt?new Date(o.cancelledAt).toLocaleString():''}</div>}</td></tr>}</Fragment>)}</tbody></table>{!busy&&list.length===0&&<p className="p-5 text-center text-stone-500">{t("Tanlangan filtr bo‘yicha cheklar topilmadi.")}</p>}</div>
  </Card>
}

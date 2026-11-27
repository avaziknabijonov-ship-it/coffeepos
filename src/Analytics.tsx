import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { PAYMENT_LABEL, fmt, som } from './data'
import type { Order, Payment } from './data'
import { exportExcel } from './exportExcel'
import { t, tCatalogName } from './i18n'

type Row = { id: string; name: string; qty: number; revenue: number; cost: number; profit: number; share?: number; abc?: 'A' | 'B' | 'C' }
type StaffRow = { name: string; orders: number; revenue: number; cancelled: number; discount: number; avg: number }
type Sales = {
  totals: { orders: number; revenue: number; cost: number; profit: number; avg: number; cancelled: number; discount: number }
  products: Row[]; categories: Row[]; staff: StaffRow[]; payments: Partial<Record<Payment, number>>
  hours: { hour: number; orders: number; revenue: number }[]
}
type Risky = { receipts: (Order & { flags: string[]; manualDiscount: number })[]; staff: { name: string; receipts: number; amount: number }[] }
type Tab = 'abc' | 'categories' | 'staff' | 'payments' | 'hours' | 'risky'

const TABS: { id: Tab; label: string }[] = [
  { id: 'abc', label: 'ABC-tahlil' }, { id: 'categories', label: 'Kategoriyalar' }, { id: 'staff', label: 'Xodimlar' },
  { id: 'payments', label: "To'lov turlari" }, { id: 'hours', label: 'Soatlar' }, { id: 'risky', label: 'Shubhali cheklar' },
]
const FLAG_LABEL: Record<string, string> = {
  cancelled: 'Bekor qilingan', late_cancel: '15 daqiqadan keyin bekor', self_cancel: 'O‘zi bekor qilgan',
  big_discount: 'Katta chegirma (20%+)', zero_total: '0 so‘mlik chek', big_bonus: 'Katta bonus (50%+)',
}
const ABC_TINT = { A: 'bg-emerald-100 text-emerald-800', B: 'bg-amber-100 text-amber-800', C: 'bg-stone-200 text-stone-700' }
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0)
const th = 'p-2 text-left font-medium text-stone-500'

export default function Analytics() {
  const [from, setFrom] = useState(() => iso(new Date(Date.now() - 29 * 86400000)))
  const [to, setTo] = useState(() => iso(new Date()))
  const [tab, setTab] = useState<Tab>('abc')
  const [sales, setSales] = useState<Sales | null>(null)
  const [risky, setRisky] = useState<Risky | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setBusy(true); setError('')
    const q = `?date_from=${from}&date_to=${to}`
    try {
      const [s, r] = await Promise.all([api<Sales>('/api/reports/sales' + q), api<Risky>('/api/reports/risky' + q)])
      setSales(s); setRisky(r)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }, [from, to])
  useEffect(() => { void load() }, [load])

  const exportAbc = () => sales && exportExcel('coffeepos-abc', ['Mahsulot', 'ABC', 'Soni', 'Tushum', 'Ulush %', 'Tannarx', 'Foyda'],
    sales.products.map((p) => [tCatalogName(p.name), p.abc ?? '', p.qty, p.revenue, p.share ?? 0, p.cost, p.profit]))
  const maxHour = Math.max(1, ...(sales?.hours.map((h) => h.revenue) ?? [0]))

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="mr-auto text-lg font-semibold">{t('Savdo tahlili')}</h2>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="rounded-lg border border-stone-200 px-2.5 py-2" />
          —
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="rounded-lg border border-stone-200 px-2.5 py-2" />
        </div>
        {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        {sales && <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {[
            [t('Tushum'), som(sales.totals.revenue)], [t('Foyda'), som(sales.totals.profit)],
            [t('Cheklar'), fmt(sales.totals.orders)], [t("O'rtacha chek"), som(sales.totals.avg)],
            [t('Chegirmalar'), som(sales.totals.discount)], [t('Otmena'), fmt(sales.totals.cancelled)],
          ].map(([label, value]) => <div key={label} className="rounded-xl bg-stone-50 p-3"><div className="text-xs text-stone-500">{label}</div><div className="mt-1 font-bold">{value}</div></div>)}
        </div>}
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
        <div className="mb-4 flex gap-1 overflow-x-auto">
          {TABS.map((x) => <button key={x.id} onClick={() => setTab(x.id)}
            className={`shrink-0 rounded-lg px-3 py-2 text-sm font-medium ${tab === x.id ? 'bg-stone-900 text-white' : 'bg-stone-100 text-stone-700'}`}>
            {t(x.label)}{x.id === 'risky' && risky && risky.receipts.length > 0 && <span className="ml-1.5 rounded-full bg-red-500 px-1.5 text-xs text-white">{risky.receipts.length}</span>}
          </button>)}
        </div>
        {busy && !sales && <p className="text-sm text-stone-500">{t('Yuklanmoqda...')}</p>}

        {sales && tab === 'abc' && <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-stone-600">{t('A — tushumning 80% ini beradigan asosiy mahsulotlar, B — keyingi 15%, C — qolgan 5%. C guruhini menyudan olib tashlash yoki narxini qayta ko‘rish mumkin.')}</p>
            <button onClick={exportAbc} className="rounded-lg border px-3 py-2 text-sm font-semibold">{t('Excelga eksport')}</button>
          </div>
          <Table head={['Mahsulot', 'ABC', 'Soni', 'Tushum', 'Ulush', 'Foyda', 'Marja']} empty={sales.products.length === 0}>
            {sales.products.map((p) => <tr key={p.id} className="border-t">
              <td className="p-2 font-medium">{tCatalogName(p.name)}</td>
              <td className="p-2">{p.abc && <span className={`rounded px-2 py-0.5 text-xs font-bold ${ABC_TINT[p.abc]}`}>{p.abc}</span>}</td>
              <td className="p-2">{fmt(p.qty)}</td><td className="p-2">{fmt(p.revenue)}</td><td className="p-2">{p.share}%</td>
              <td className="p-2">{fmt(p.profit)}</td><td className="p-2">{pct(p.profit, p.revenue)}%</td>
            </tr>)}
          </Table>
        </>}

        {sales && tab === 'categories' && <Table head={['Kategoriya', 'Soni', 'Tushum', 'Ulush', 'Foyda', 'Marja']} empty={sales.categories.length === 0}>
          {sales.categories.map((c) => <tr key={c.id} className="border-t">
            <td className="p-2 font-medium">{tCatalogName(c.name)}</td><td className="p-2">{fmt(c.qty)}</td><td className="p-2">{fmt(c.revenue)}</td>
            <td className="p-2">{pct(c.revenue, sales.totals.revenue)}%</td><td className="p-2">{fmt(c.profit)}</td><td className="p-2">{pct(c.profit, c.revenue)}%</td>
          </tr>)}
        </Table>}

        {sales && tab === 'staff' && <Table head={['Xodim', 'Cheklar', 'Tushum', "O'rtacha chek", 'Chegirmalar', 'Otmena']} empty={sales.staff.length === 0}>
          {sales.staff.map((s) => <tr key={s.name} className="border-t">
            <td className="p-2 font-medium">{s.name}</td><td className="p-2">{fmt(s.orders)}</td><td className="p-2">{fmt(s.revenue)}</td>
            <td className="p-2">{fmt(s.avg)}</td><td className="p-2">{fmt(s.discount)}</td>
            <td className={`p-2 ${s.cancelled ? 'font-semibold text-red-700' : ''}`}>{fmt(s.cancelled)}</td>
          </tr>)}
        </Table>}

        {sales && tab === 'payments' && <Table head={["To'lov turi", 'Summa', 'Ulush']} empty={Object.keys(sales.payments).length === 0}>
          {(Object.keys(PAYMENT_LABEL) as Payment[]).filter((p) => sales.payments[p]).map((p) => <tr key={p} className="border-t">
            <td className="p-2 font-medium">{t(PAYMENT_LABEL[p])}</td><td className="p-2">{fmt(sales.payments[p] ?? 0)}</td>
            <td className="p-2">{pct(sales.payments[p] ?? 0, sales.totals.revenue)}%</td>
          </tr>)}
        </Table>}

        {sales && tab === 'hours' && <div className="space-y-1.5">
          {sales.hours.filter((h) => h.orders > 0).map((h) => <div key={h.hour} className="flex items-center gap-3 text-sm">
            <span className="w-12 shrink-0 tabular-nums text-stone-500">{String(h.hour).padStart(2, '0')}:00</span>
            <div className="h-6 flex-1 rounded bg-stone-100"><div className="h-6 rounded bg-amber-500" style={{ width: `${(h.revenue / maxHour) * 100}%` }} /></div>
            <span className="w-40 shrink-0 text-right tabular-nums">{fmt(h.revenue)} · {h.orders} {t('chek')}</span>
          </div>)}
          {sales.hours.every((h) => h.orders === 0) && <p className="p-5 text-center text-sm text-stone-500">{t('Tanlangan davrda savdo yo‘q.')}</p>}
        </div>}

        {risky && tab === 'risky' && <>
          {risky.staff.length > 0 && <div className="mb-4 flex flex-wrap gap-2">
            {risky.staff.map((s) => <span key={s.name} className="rounded-lg bg-red-50 px-3 py-1.5 text-sm text-red-800"><b>{s.name}</b>: {s.receipts} {t('chek')} · {fmt(s.amount)}</span>)}
          </div>}
          <Table head={['№', 'Sana, vaqt', 'Xodim', 'Summa', 'Sabab']} empty={risky.receipts.length === 0}>
            {risky.receipts.map((o) => <tr key={o.id} className="border-t align-top">
              <td className="p-2 font-bold">№{o.number}</td><td className="p-2">{new Date(o.createdAt).toLocaleString()}</td>
              <td className="p-2">{o.barista}{o.cancelledBy && o.cancelledBy !== o.barista && <span className="block text-xs text-stone-500">{t('Otmena qilgan')}: {o.cancelledBy}</span>}</td>
              <td className="p-2">{fmt(o.subtotal)}{o.manualDiscount > 0 && <span className="block text-xs text-red-700">−{fmt(o.manualDiscount)}</span>}</td>
              <td className="p-2"><div className="flex flex-wrap gap-1">{o.flags.map((f) => <span key={f} className="rounded bg-red-100 px-1.5 py-0.5 text-xs text-red-800">{t(FLAG_LABEL[f] ?? f)}</span>)}</div>
                {o.cancelReason && <div className="mt-1 text-xs text-stone-500">{o.cancelReason}</div>}</td>
            </tr>)}
          </Table>
        </>}
      </section>
    </div>
  )
}

function Table({ head, empty, children }: { head: string[]; empty: boolean; children: React.ReactNode }) {
  return <div className="overflow-x-auto">
    <table className="w-full min-w-[560px] text-sm">
      <thead><tr>{head.map((h) => <th key={h} className={th}>{t(h)}</th>)}</tr></thead>
      <tbody>{children}</tbody>
    </table>
    {empty && <p className="p-5 text-center text-sm text-stone-500">{t('Tanlangan davrda savdo yo‘q.')}</p>}
  </div>
}

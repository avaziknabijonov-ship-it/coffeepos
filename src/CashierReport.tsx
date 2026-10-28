import { useEffect, useState } from 'react'
import { api } from './api'
import { exportExcel } from './exportExcel'
import { fmt, PAYMENT_LABEL, type Payment } from './data'
import { t } from './i18n'

type StaffRow = { name: string; count: number; revenue: number; discounts: number; refunds: number; netRevenue: number; shifts: number; voidCount: number; voidSum: number; processedRefunds: number; byPayment: Record<string, number>; refundsByPayment: Record<string, number> }
const dateText = (d: Date) => [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-')
export default function CashierReport() {
  const [from, setFrom] = useState(() => dateText(new Date()))
  const [to, setTo] = useState(() => dateText(new Date()))
  const [staffRows, setStaffRows] = useState<StaffRow[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    let active = true
    const load = async () => {
      setLoading(true); setError('')
      try {
        const start = new Date(from + 'T00:00:00').getTime()
        const end = new Date(to + 'T00:00:00').getTime() + 86400000
        const params = new URLSearchParams({ from_ms: String(start), to_ms: String(end) })
        const result = await api<{ rows: StaffRow[] }>('/api/reports/staff?' + params)
        if (active) setStaffRows(result.rows)
      } catch (e) { if (active) { setError((e as Error).message); setStaffRows([]) } }
      finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false }
  }, [from, to])
  const rows = staffRows.map(r => ({ ...r, methods: ([...new Set([...Object.keys(r.byPayment), ...Object.keys(r.refundsByPayment)])]).map(method => `${t(PAYMENT_LABEL[method as Payment])}: ${fmt(r.byPayment[method] ?? 0)} / ${t('Qaytarilgan mablag‘')}: ${fmt(r.refundsByPayment[method] ?? 0)}`).join('; ') }))
  return <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
    <h2 className="mb-1 text-xl font-bold">{t("Kassirlar hisoboti")}</h2>
    <p className="mb-4 text-sm text-stone-500">{t("Kassir bo‘yicha sotuvlar, smenalar, otmenalar va to‘lov usullari. Otmena summalari sotuvdan chiqarilgan.")}</p>
    <p className="mb-3 text-sm text-stone-500">{t("Refund asl kassirga qaytarish sanasi bo‘yicha yoziladi. Bir xil ismli xodimlar birlashtiriladi.")}</p>
    <div className="mb-4 flex flex-wrap items-end gap-3"><label className="text-sm">{t("Dan")}<input type="date" className="mt-1 block rounded-lg border p-2" value={from} onChange={e=>setFrom(e.target.value)}/></label><label className="text-sm">{t("Gacha")}<input type="date" className="mt-1 block rounded-lg border p-2" value={to} onChange={e=>setTo(e.target.value)}/></label><button onClick={()=>exportExcel('coffeepos-kassirlar',['Kassir','Sotuvlar','Summa','Chegirma','Qaytarilgan mablag‘','Qaytarishdan keyingi tushum','Smenalar','Otmenalar','Otmena summasi','To‘lov turlari'].map(label => t(label)),rows.map(r=>[r.name,r.count,r.revenue,r.discounts,r.refunds,r.netRevenue,r.shifts,r.voidCount,r.voidSum,r.methods]))} className="rounded-lg border px-3 py-2 text-sm">{t("Excelga eksport")}</button></div>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-700">{error}</p>}
    {loading && <p className="text-sm text-stone-500">{t("Yuklanmoqda…")}</p>}
    <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead><tr className="border-b text-stone-500"><th className="p-2">{t("Kassir")}</th><th className="p-2">{t("Sotuv")}</th><th className="p-2">{t("Summa")}</th><th className="p-2">{t("Chegirma")}</th><th className="p-2">{t("Qaytarilgan mablag‘")}</th><th className="p-2">{t("Qaytarishdan keyingi tushum")}</th><th className="p-2">{t("Smena")}</th><th className="p-2">{t("Otmena")}</th><th className="p-2">{t("To‘lovlar")}</th></tr></thead><tbody>{rows.map(r=><tr key={r.name} className="border-b border-stone-100"><td className="p-2 font-semibold">{r.name}</td><td className="p-2">{r.count}</td><td className="p-2 font-semibold">{fmt(r.revenue)} so‘m</td><td className="p-2">{fmt(r.discounts)}</td><td className="p-2">{fmt(r.refunds)}</td><td className="p-2">{fmt(r.netRevenue)}</td><td className="p-2">{r.shifts}</td><td className="p-2 text-red-700">{r.voidCount} ta · {fmt(r.voidSum)} so‘m</td><td className="p-2">{r.methods || '—'}</td></tr>)}</tbody></table>{!loading && !error && rows.length===0 && <p className="p-4 text-center text-stone-500">{t("Tanlangan sanada savdo topilmadi.")}</p>}</div>
  </section>
}

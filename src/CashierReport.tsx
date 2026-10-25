import { useEffect, useState } from 'react'
import { api } from './api'
import { exportExcel } from './exportExcel'
import { fmt } from './data'

type Sale = { id: string; number: number; barista: string; shiftId?: number; createdAt: number; total: number; status: string; payment: string; cancelledBy?: string | null }
const dateText = (d: Date) => [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-')
export default function CashierReport() {
  const [from, setFrom] = useState(() => dateText(new Date()))
  const [to, setTo] = useState(() => dateText(new Date()))
  const [sales, setSales] = useState<Sale[]>([])
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
        const result = await api<Sale[]>('/api/orders/history?' + params)
        if (active) setSales(result)
      } catch (e) { if (active) { setError((e as Error).message); setSales([]) } }
      finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false }
  }, [from, to])
  const names = [...new Set(sales.map(o => o.barista).filter(Boolean))].sort()
  const rows = names.map(name => {
    const orders = sales.filter(o => o.barista === name)
    const done = orders.filter(o => o.status !== 'cancelled')
    const voids = orders.filter(o => o.status === 'cancelled')
    const methods = [...new Set(done.map(o => o.payment))].map(p => p + ': ' + fmt(done.filter(o=>o.payment===p).reduce((a,o)=>a+o.total,0))).join('; ')
    return { name, count: done.length, revenue: done.reduce((a,o)=>a+o.total,0), shifts: new Set(orders.map(o=>o.shiftId).filter(Boolean)).size, voidCount: voids.length, voidSum: voids.reduce((a,o)=>a+o.total,0), methods }
  })
  return <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
    <h2 className="mb-1 text-xl font-bold">Kassirlar hisoboti</h2>
    <p className="mb-4 text-sm text-stone-500">Kassir bo‘yicha sotuvlar, smenalar, otmenalar va to‘lov usullari. Otmena summalari sotuvdan chiqarilgan.</p>
    <div className="mb-4 flex flex-wrap items-end gap-3"><label className="text-sm">Dan<input type="date" className="mt-1 block rounded-lg border p-2" value={from} onChange={e=>setFrom(e.target.value)}/></label><label className="text-sm">Gacha<input type="date" className="mt-1 block rounded-lg border p-2" value={to} onChange={e=>setTo(e.target.value)}/></label><button onClick={()=>exportExcel('coffeepos-kassirlar',['Kassir','Sotuvlar','Summa','Smenalar','Otmenalar','Otmena summasi','To‘lov turlari'],rows.map(r=>[r.name,r.count,r.revenue,r.shifts,r.voidCount,r.voidSum,r.methods]))} className="rounded-lg border px-3 py-2 text-sm">Excelga eksport</button></div>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-700">{error}</p>}
    {loading && <p className="text-sm text-stone-500">Yuklanmoqda…</p>}
    <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead><tr className="border-b text-stone-500"><th className="p-2">Kassir</th><th className="p-2">Sotuv</th><th className="p-2">Summa</th><th className="p-2">Smena</th><th className="p-2">Otmena</th><th className="p-2">To‘lovlar</th></tr></thead><tbody>{rows.map(r=><tr key={r.name} className="border-b border-stone-100"><td className="p-2 font-semibold">{r.name}</td><td className="p-2">{r.count}</td><td className="p-2 font-semibold">{fmt(r.revenue)} so‘m</td><td className="p-2">{r.shifts}</td><td className="p-2 text-red-700">{r.voidCount} ta · {fmt(r.voidSum)} so‘m</td><td className="p-2">{r.methods || '—'}</td></tr>)}</tbody></table>{!loading && !error && rows.length===0 && <p className="p-4 text-center text-stone-500">Tanlangan sanada savdo topilmadi.</p>}</div>
  </section>
}

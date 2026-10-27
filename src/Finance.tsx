import { useEffect, useState } from 'react'
import { api } from './api'
import { exportExcel } from './exportExcel'
import { som, PAYMENT_LABEL } from './data'
import type { Payment } from './data'
import { t } from './i18n'

type FinanceDay = {
  day: number; orders: number; revenue: number; refunds: number; netRevenue: number; cogs: number; grossProfit: number
  expenses: number; staffPayments: number; operatingBalance: number
}
type FinanceReport = {
  days: number; orders: number; revenue: number; refunds: number; netRevenue: number; cogs: number; grossProfit: number
  expenses: number; staffPayments: number; operatingBalance: number
  byPayment: Record<string, number>; refundsByPayment: Record<string, number>; daily: FinanceDay[]; note: string
}
export default function Finance() {
  const [days, setDays] = useState(30)
  const [report, setReport] = useState<FinanceReport | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const refresh = async () => {
    setLoading(true); setError('')
    try { setReport(await api<FinanceReport>('/api/reports/finance?days=' + days)) }
    catch(e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }
  useEffect(() => { void refresh() }, [days])
  const box = 'rounded-xl border border-stone-200 bg-white p-4'
  const cards = report ? [
    [t('Tushum'), report.revenue],
    [t('Qaytarilgan mablag‘'), report.refunds],
    [t('Qaytarishdan keyingi tushum'), report.netRevenue],
    [t('Mahsulot tannarxi'), report.cogs],
    [t('Yalpi foyda'), report.grossProfit],
    [t('Xarajatlar'), report.expenses],
    [t('Xodimlarga to‘lovlar'), report.staffPayments],
    [t('Operatsion qoldiq'), report.operatingBalance],
  ] as const : []
  return <div className="space-y-4">
    <section className={box}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-lg font-semibold">{t('Moliya hisoboti')}</h2>
          <p className="text-sm text-stone-500">{t('Sotuv, tannarx, xarajat va berilgan oylik/avanslar')}</p></div>
        <div className="flex items-center gap-2">
          <select aria-label={t('Davr')} value={days} onChange={e=>setDays(Number(e.target.value))} className="rounded-lg border px-3 py-2 text-sm">
            <option value={7}>{t('Oxirgi 7 kun')}</option><option value={30}>{t('Oxirgi 30 kun')}</option>
            <option value={90}>{t('Oxirgi 90 kun')}</option>
          </select>
          <button disabled={!report} onClick={() => report && exportExcel('coffeepos-moliya-' + days, ['Sana','Cheklar','Tushum','Qaytarilgan mablag‘','Qaytarishdan keyingi tushum','Tannarx','Yalpi foyda','Xarajat','Oylik-avans','Operatsion qoldiq'].map(label => t(label)),
            report.daily.map(d => [new Date(d.day).toLocaleDateString(),d.orders,d.revenue,d.refunds,d.netRevenue,d.cogs,d.grossProfit,d.expenses,d.staffPayments,d.operatingBalance]))}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">{t('Excelga eksport')}</button>
          <button disabled={loading} onClick={refresh} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">{t('Yangilash')}</button>
        </div>
      </div>
      {error && <p role="alert" className="mt-3 text-red-600">{error}</p>}
    </section>
    {report && <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        {cards.map(([label, value])=><div className={box} key={label}>
          <p className="mb-1 text-xs text-stone-500">{label}</p>
          <p className="text-lg font-bold tabular-nums sm:text-2xl">{som(value)}</p>
        </div>)}
      </div>
      <section className={box}><h3 className="mb-3 font-semibold">{t('To‘lov turlari')}</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(Object.keys(PAYMENT_LABEL) as Payment[]).filter(p => p !== 'split').map(p=><div key={p} className="rounded-xl bg-stone-50 p-3">
            <p className="text-xs text-stone-500">{t(PAYMENT_LABEL[p])}</p>
            <p className="text-sm">{t('Tushum')}: {som(report.byPayment[p] ?? 0)}</p>
            <p className="text-sm">{t('Qaytarilgan mablag‘')}: {som(report.refundsByPayment[p] ?? 0)}</p>
            <p className="font-semibold">{t('Qaytarishdan keyingi tushum')}: {som((report.byPayment[p] ?? 0) - (report.refundsByPayment[p] ?? 0))}</p>
          </div>)}
        </div>
      </section>
      <section className={box}><h3 className="mb-3 font-semibold">{t('Kunlik ko‘rsatkichlar')}</h3>
        <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-sm">
          <thead className="text-left text-stone-500"><tr>
            <th className="px-2 py-2">{t('Sana')}</th>
            <th className="px-2 py-2 text-right">{t('Buyurtma')}</th>
            <th className="px-2 py-2 text-right">{t('Tushum')}</th>
            <th className="px-2 py-2 text-right">{t('Qaytarilgan mablag‘')}</th>
            <th className="px-2 py-2 text-right">{t('Qaytarishdan keyingi tushum')}</th>
            <th className="px-2 py-2 text-right">{t('Tannarx')}</th>
            <th className="px-2 py-2 text-right">{t('Xarajatlar')}</th>
            <th className="px-2 py-2 text-right">{t('Oylik/avans')}</th>
            <th className="px-2 py-2 text-right">{t('Operatsion qoldiq')}</th>
          </tr></thead><tbody>
            {[...report.daily].reverse().map(d=><tr className="border-t" key={d.day}>
              <td className="px-2 py-2">{new Date(d.day).toLocaleDateString()}</td>
              <td className="px-2 py-2 text-right">{d.orders}</td>
              <td className="px-2 py-2 text-right">{som(d.revenue)}</td>
              <td className="px-2 py-2 text-right">{som(d.refunds)}</td>
              <td className="px-2 py-2 text-right">{som(d.netRevenue)}</td>
              <td className="px-2 py-2 text-right">{som(d.cogs)}</td>
              <td className="px-2 py-2 text-right">{som(d.expenses)}</td>
              <td className="px-2 py-2 text-right">{som(d.staffPayments)}</td>
              <td className="px-2 py-2 text-right font-semibold">{som(d.operatingBalance)}</td>
            </tr>)}
          </tbody></table></div>
      </section>
      <p className="text-sm text-stone-500">{t('Bu operatsion hisob: soliqlar, yetkazib beruvchi qarzlari va to‘lanmagan majburiyatlar hisobga olinmagan.')} {t('Pul qaytarish tannarx va omborni avtomatik tiklamaydi.')}</p>
    </>}
  </div>
}

import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { INGREDIENTS, UNIT_LABEL, fmt } from './data'
import { refreshMenu, sync, useAppState } from './store'
import { t } from './i18n'
import { Plus, Trash2, FileText } from 'lucide-react'

type Line = { ing: string; qty: string; unitPrice: string }
type Invoice = { id: number; number: string; supplier: string; receivedAt: number; paymentStatus: string; total: number; lines: { name: string; qty: number; unit: string; unitPrice: number; subtotal: number }[]; note: string }
const newLine = (): Line => ({ ing: '', qty: '', unitPrice: '' })
const localDate = () => { const d = new Date(); const offset = d.getTimezoneOffset() * 60000; return new Date(d.getTime() - offset).toISOString().slice(0, 10) }

export default function PurchaseInvoices() {
  const { stock } = useAppState()
  const [number, setNumber] = useState('')
  const [supplier, setSupplier] = useState('')
  const [date, setDate] = useState(localDate)
  const [paymentStatus, setPaymentStatus] = useState('unpaid')
  const [note, setNote] = useState('')
  const [lines, setLines] = useState<Line[]>([newLine()])
  const [history, setHistory] = useState<Invoice[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [opened, setOpened] = useState<number | null>(null)
  const load = () => api<Invoice[]>('/api/purchases').then(setHistory).catch((e: Error) => setError(e.message))
  useEffect(() => { void load() }, [])
  const amount = (l: Line) => Number(l.qty) * Number(l.unitPrice)
  const total = useMemo(() => lines.reduce((s, l) => s + (Number.isFinite(amount(l)) ? amount(l) : 0), 0), [lines])
  const edit = (idx: number, patch: Partial<Line>) => setLines(v => v.map((l, i) => i === idx ? { ...l, ...patch } : l))
  const save = async () => {
    setError('')
    if (!number.trim() || !supplier.trim() || !date || lines.some(l => !l.ing || Number(l.qty) <= 0 || l.unitPrice === '' || Number(l.unitPrice) < 0)) {
      setError('Hujjat raqami, yetkazib beruvchi, sana va mahsulot satrlarini to‘ldiring.'); return
    }
    if (new Set(lines.map(l => l.ing)).size !== lines.length) { setError('Bir xil mahsulotni takrorlamang.'); return }
    setBusy(true)
    try {
      await api('/api/purchases', { body: { number: number.trim(), supplier: supplier.trim(), received_at: new Date(date + 'T12:00:00').getTime(), payment_status: paymentStatus, note, lines: lines.map(l => ({ ing: l.ing, qty: Number(l.qty), unit_price: Number(l.unitPrice) })) } })
      setNumber(''); setSupplier(''); setNote(''); setLines([newLine()])
      await Promise.all([load(), sync(), refreshMenu()])
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const input = 'w-full min-w-0 rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-amber-500'
  return <div className="space-y-5">
    <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="mb-5 flex items-center gap-2"><FileText className="size-5 text-amber-600" /><h2 className="text-lg font-bold">{t('Bozorlik — kirim nakladnoyi')}</h2></div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="space-y-1 text-sm">{t('Nakladnoy raqami')}<input className={input} value={number} onChange={e => setNumber(e.target.value)} placeholder="NK-001" /></label>
        <label className="space-y-1 text-sm">{t('Yetkazib beruvchi')}<input className={input} value={supplier} onChange={e => setSupplier(e.target.value)} placeholder="Firma / do‘kon" /></label>
        <label className="space-y-1 text-sm">{t('Kelgan sana')}<input type="date" className={input} value={date} onChange={e => setDate(e.target.value)} /></label>
        <label className="space-y-1 text-sm">{t("To'lov holati")}<select className={input} value={paymentStatus} onChange={e => setPaymentStatus(e.target.value)}><option value="unpaid">Qarz</option><option value="paid">To‘langan</option><option value="partial">Qisman to‘langan</option></select></label>
      </div>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[650px] text-sm">
          <thead><tr className="border-b text-left text-stone-500"><th className="p-2">Mahsulot</th><th className="p-2">Miqdor</th><th className="p-2">Narx / birlik (so‘m)</th><th className="p-2 text-right">Summa</th><th className="p-2"></th></tr></thead>
          <tbody>{lines.map((l, idx) => {
            const ing = INGREDIENTS.find(i => i.id === l.ing)
            return <tr key={idx} className="border-b border-stone-100"><td className="p-2"><select className={input} value={l.ing} onChange={e => edit(idx, { ing: e.target.value })}><option value="">Tanlang</option>{INGREDIENTS.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}</select></td><td className="p-2"><div className="flex items-center gap-1"><input className={input} type="number" min="0.001" step="any" value={l.qty} onChange={e => edit(idx, { qty: e.target.value })} /><span className="text-stone-400">{ing ? t(UNIT_LABEL[ing.unit]) : ''}</span></div></td><td className="p-2"><input className={input} type="number" min="0" step="any" value={l.unitPrice} onChange={e => edit(idx, { unitPrice: e.target.value })} /></td><td className="p-2 text-right font-semibold">{fmt(amount(l) || 0)}</td><td className="p-2"><button aria-label="Satrni olib tashlash" disabled={lines.length === 1} onClick={() => setLines(v => v.filter((_, i) => i !== idx))} className="rounded-lg p-2 text-red-600 disabled:opacity-30"><Trash2 className="size-4" /></button></td></tr>
          })}</tbody>
        </table>
      </div>
      <button onClick={() => setLines(v => [...v, newLine()])} className="mt-3 inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"><Plus className="size-4" /> Mahsulot qo‘shish</button>
      <label className="mt-4 block space-y-1 text-sm">Izoh<input className={input} value={note} onChange={e => setNote(e.target.value)} placeholder="Ixtiyoriy izoh" /></label>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><div className="text-lg font-bold">Jami: {fmt(total)} so‘m</div><button disabled={busy} onClick={save} className="rounded-xl bg-stone-900 px-5 py-3 font-semibold text-white disabled:opacity-50">{busy ? 'Saqlanmoqda...' : 'Nakladnoyni saqlash va omborga kirim qilish'}</button></div>
      {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    </section>
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <h2 className="mb-3 font-semibold">Kirim hujjatlari tarixi</h2>
      {history.length === 0 ? <p className="text-sm text-stone-500">Hozircha nakladnoy yo‘q.</p> : <div className="space-y-2">{history.map(p => <div key={p.id} className="rounded-xl border border-stone-200">
        <button className="flex w-full flex-wrap items-center justify-between gap-2 p-3 text-left text-sm" onClick={() => setOpened(v => v === p.id ? null : p.id)}><span><b>№ {p.number}</b> · {p.supplier} · {new Date(p.receivedAt).toLocaleDateString()}</span><span className="font-semibold">{fmt(p.total)} so‘m · {p.paymentStatus === 'paid' ? 'To‘langan' : p.paymentStatus === 'partial' ? 'Qisman' : 'Qarz'}</span></button>
        {opened === p.id && <div className="border-t p-3 text-sm">{p.lines.map((l, i) => <div key={i} className="flex justify-between gap-3 py-1"><span>{l.name} — {l.qty} {l.unit} × {fmt(l.unitPrice)}</span><b>{fmt(l.subtotal)}</b></div>)}{p.note && <p className="mt-2 text-stone-500">{p.note}</p>}</div>}
      </div>)}</div>}
    </section>
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <h2 className="mb-3 font-semibold">Ombor qoldiqlari</h2>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{INGREDIENTS.map(i => <div key={i.id} className="flex justify-between rounded-lg bg-stone-50 px-3 py-2 text-sm"><span>{i.name}</span><b>{fmt(stock[i.id] ?? 0)} {t(UNIT_LABEL[i.unit])}</b></div>)}</div>
    </section>
  </div>
}

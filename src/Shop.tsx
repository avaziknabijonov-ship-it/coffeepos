import { useEffect, useRef, useState } from 'react'
import { Printer, X } from 'lucide-react'
import { api } from './api'
import { CATEGORIES, PRODUCTS, fmt, som } from './data'
import type { Order, Product, Size } from './data'
import { t, tCatalogName } from './i18n'
import { sync } from './store'

const input = 'rounded-lg border border-stone-200 px-2.5 py-2 outline-none focus:border-amber-500'

/** Ask the cashier for the weight (kg) of a weighted product. */
export function WeightModal({ product, size, onClose, onAdd }: { product: Product; size: Size; onClose: () => void; onAdd: (kg: number) => void }) {
  const [grams, setGrams] = useState('')
  const kg = Number(grams.replace(',', '.')) / 1000
  const ok = kg >= 0.001 && kg <= 1000
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <form className="w-full max-w-sm rounded-2xl bg-white p-5 text-stone-900 shadow-xl" onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => { e.preventDefault(); if (ok) onAdd(kg) }}>
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-bold">{tCatalogName(product.name)}</h2><button type="button" onClick={onClose} aria-label={t('Yopish')}><X className="size-5" /></button></div>
        <p className="mb-3 text-sm text-stone-500">{som(size.price)} / kg</p>
        <label className="block text-sm font-medium">{t('Vazn (gramm)')}
          <input autoFocus value={grams} onChange={(e) => setGrams(e.target.value.replace(/[^\d.,]/g, ''))} inputMode="decimal" className={`${input} mt-1 w-full text-2xl font-bold`} />
        </label>
        <div className="mt-2 flex flex-wrap gap-2">{[100, 250, 500, 1000].map((g) => <button key={g} type="button" onClick={() => setGrams(String(g))} className="rounded-lg border px-3 py-1.5 text-sm">{g} g</button>)}</div>
        <div className="mt-4 flex items-center justify-between text-lg font-bold"><span>{t('Jami')}</span><span>{ok ? som(Math.floor(size.price * kg + 0.5)) : '—'}</span></div>
        <button disabled={!ok} className="mt-4 w-full rounded-xl bg-emerald-600 py-3 font-bold text-white disabled:bg-stone-300">{t("Qo'shish")}</button>
      </form>
    </div>
  )
}

/** Keyboard-wedge barcode scanners type fast and end with Enter; catch that when no input has focus. */
export function useBarcodeScanner(onScan: (code: string) => void) {
  const cb = useRef(onScan)
  cb.current = onScan
  useEffect(() => {
    let buf = ''
    let last = 0
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT')) return
      const now = Date.now()
      if (now - last > 80) buf = ''
      last = now
      if (e.key === 'Enter') {
        if (buf.length >= 4) { e.preventDefault(); cb.current(buf) }
        buf = ''
      } else if (e.key.length === 1) {
        buf += e.key
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}

type RefundInfo = { refundedAmount: number; remaining: Record<string, number>; refunds: { id: number; amount: number; reason: string; staff: string; createdAt: number }[] }

/** Return goods from a paid receipt (partial or full). */
export function RefundModal({ order, onClose, onDone }: { order: Order; onClose: () => void; onDone?: () => void }) {
  const [info, setInfo] = useState<RefundInfo | null>(null)
  const [qty, setQty] = useState<Record<string, number>>({})
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { api<RefundInfo>(`/api/orders/${order.id}/refunds`).then(setInfo).catch((e) => setError((e as Error).message)) }, [order.id])
  const ratio = order.subtotal ? order.total / order.subtotal : 0
  const lines = Object.entries(qty).filter(([, q]) => q > 0)
  const amount = lines.reduce((s, [k, q]) => s + Math.round((order.items.find((i) => i.key === k)?.unitPrice ?? 0) * q * ratio), 0)
  const submit = async () => {
    setBusy(true); setError('')
    try {
      await api(`/api/orders/${order.id}/refund`, { body: { lines: lines.map(([key, q]) => ({ key, qty: q })), reason: reason.trim() } })
      await sync()
      onDone?.()
      onClose()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-3">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 text-stone-900 shadow-xl">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-bold">{t('Tovar qaytarish')} · №{order.number}</h2><button onClick={onClose} aria-label={t('Yopish')}><X className="size-6" /></button></div>
        {info && info.refundedAmount > 0 && <p className="mb-3 rounded-lg bg-amber-50 p-2 text-sm text-amber-900">{t('Avval qaytarilgan')}: {som(info.refundedAmount)}</p>}
        {info && <div className="space-y-2">
          {order.items.map((it) => {
            const left = info.remaining[it.key] ?? 0
            const q = qty[it.key] ?? 0
            return <div key={it.key} className="flex items-center gap-3 rounded-xl border border-stone-200 p-2.5 text-sm">
              <div className="min-w-0 flex-1"><div className="font-medium">{tCatalogName(it.name)} {it.size}</div><div className="text-xs text-stone-500">{fmt(it.unitPrice)} × {it.qty} · {t('qaytarish mumkin')}: {left}</div></div>
              <button disabled={q <= 0} onClick={() => setQty({ ...qty, [it.key]: q - 1 })} className="size-8 rounded-lg bg-stone-100 disabled:opacity-30">−</button>
              <span className="w-6 text-center font-semibold">{q}</span>
              <button disabled={q >= left} onClick={() => setQty({ ...qty, [it.key]: q + 1 })} className="size-8 rounded-lg bg-stone-100 disabled:opacity-30">+</button>
            </div>
          })}
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t('Qaytarish sababi (kamida 3 ta belgi)')} className={`${input} w-full`} />
          <div className="flex justify-between font-bold"><span>{t('Mijozga qaytariladi')}</span><span>{som(amount)}</span></div>
          <p className="text-xs text-stone-500">{t('Pul joriy smenadan chiqadi, tovar omborga qaytadi.')}</p>
        </div>}
        {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        <button disabled={busy || lines.length === 0 || reason.trim().length < 3} onClick={() => void submit()} className="mt-4 w-full rounded-xl bg-red-600 py-3 font-bold text-white disabled:bg-stone-300">{t('Qaytarishni tasdiqlash')}</button>
      </div>
    </div>
  )
}

// ---------- Code 128 (set B) barcode, drawn as SVG ----------
const C128 = ['212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213', '221312', '231212', '112232', '122132', '122231', '113222', '123122', '123221', '223211', '221132', '221231', '213212', '223112', '312131', '311222', '321122', '321221', '312212', '322112', '322211', '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313', '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331', '231131', '213113', '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111', '314111', '221411', '431111', '111224', '111422', '121124', '121421', '141122', '141221', '112214', '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111', '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141', '214121', '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141', '114131', '311141', '411131', '211412', '211214', '211232']
const STOP = '2331112'

export function code128(text: string): string[] {
  const values = [...text].map((ch) => ch.charCodeAt(0) - 32)
  if (values.some((v) => v < 0 || v > 94)) return []
  const check = (104 + values.reduce((s, v, i) => s + v * (i + 1), 0)) % 103
  return [C128[104], ...values.map((v) => C128[v]), C128[check], STOP]
}

export function Barcode({ value, height = 40 }: { value: string; height?: number }) {
  const patterns = code128(value)
  if (!patterns.length) return null
  const bars: { x: number; w: number }[] = []
  let x = 10
  for (const p of patterns) [...p].forEach((d, i) => { const w = Number(d); if (i % 2 === 0) bars.push({ x, w }); x += w })
  const width = x + 10
  return <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none" role="img" aria-label={value}>
    <rect width={width} height={height} fill="#fff" />
    {bars.map((b, i) => <rect key={i} x={b.x} y={0} width={b.w} height={height} fill="#000" />)}
  </svg>
}

/** Admin: printable price tags with name, price and barcode. */
export function PriceTags() {
  const [cat, setCat] = useState('')
  const [picked, setPicked] = useState<Record<string, number>>({})
  const rows = PRODUCTS.filter((p) => !cat || p.cat === cat).flatMap((p) => p.sizes.map((s) => ({ key: p.id + '|' + s.code, p, s })))
  const tags = PRODUCTS.flatMap((p) => p.sizes.flatMap((s) => Array.from({ length: picked[p.id + '|' + s.code] ?? 0 }, (_, i) => ({ id: `${p.id}|${s.code}|${i}`, p, s }))))
  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5 print:hidden">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto text-lg font-semibold">{t('Narx yorliqlari')}</h2>
          <select value={cat} onChange={(e) => setCat(e.target.value)} className={input}>
            <option value="">{t('Hammasi')}</option>
            {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{tCatalogName(c.name)}</option>)}
          </select>
          <button onClick={() => setPicked(Object.fromEntries(rows.map((r) => [r.key, 1])))} className="rounded-lg border px-3 py-2 text-sm">{t('Hammasini tanlash')}</button>
          <button disabled={tags.length === 0} onClick={() => window.print()} className="flex items-center gap-1 rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-stone-300"><Printer className="size-4" />{t('Chop etish')} ({tags.length})</button>
        </div>
        <div className="max-h-80 divide-y divide-stone-100 overflow-y-auto rounded-xl border border-stone-200 text-sm">
          {rows.map((r) => <label key={r.key} className="flex items-center gap-3 px-3 py-2">
            <span className="flex-1">{tCatalogName(r.p.name)} {r.s.label} <span className="text-stone-500">· {som(r.s.price)}{r.p.weighted ? ' / kg' : ''}</span>{!r.s.barcode && <span className="ml-1 text-xs text-amber-700">({t('shtrix-kodsiz')})</span>}</span>
            <input type="number" min={0} max={100} value={picked[r.key] ?? 0} onChange={(e) => setPicked({ ...picked, [r.key]: Math.max(0, Math.min(100, Number(e.target.value) || 0)) })} className={`${input} w-20`} />
          </label>)}
        </div>
      </section>
      <div className="price-tags grid grid-cols-2 gap-2 sm:grid-cols-3 print:grid-cols-3">
        {tags.map(({ id, p, s }) => <div key={id} className="break-inside-avoid rounded border border-stone-400 p-2" style={{ background: '#fff', color: '#000' }}>
          <div className="line-clamp-2 text-sm font-bold leading-tight">{tCatalogName(p.name)} {s.label}</div>
          <div className="my-1 text-xl font-extrabold">{fmt(s.price)} <span className="text-xs font-semibold">{t("so'm")}{p.weighted ? ' / kg' : ''}</span></div>
          {s.barcode && !p.weighted && <><Barcode value={s.barcode} /><div className="text-center font-mono text-[10px]">{s.barcode}</div></>}
        </div>)}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { t } from './i18n'
import { getReceiptWidth, setReceiptWidth } from './printer'
import type { ReceiptWidth } from './printer'

export default function PrinterSettings() {
  const [width, setWidth] = useState<ReceiptWidth>(getReceiptWidth)
  function update(next: ReceiptWidth) { setWidth(next); setReceiptWidth(next) }
  return <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
    <h2 className="mb-3 text-lg font-semibold">{t('Chek printer sozlamasi')}</h2>
    <p className="mb-3 text-sm text-stone-500">{t('Bu sozlama faqat shu qurilmada saqlanadi. Browser chop etishi haqiqiy printer integratsiyasi emas.')}</p>
    <div className="flex flex-wrap items-center gap-4">
      <label className="text-sm font-semibold">{t('Chek qog‘ozi')}
        <select value={width} onChange={e=>update(Number(e.target.value) as ReceiptWidth)}
          className="ml-3 rounded-lg border border-stone-200 bg-white p-2.5">
          <option value={58}>58 mm</option><option value={80}>80 mm</option>
        </select>
      </label>
      <button onClick={() => window.print()} className="rounded-lg bg-stone-900 px-4 py-2.5 text-sm font-semibold text-white">
        {t('Test chek chiqarish')}
      </button>
    </div>
    <div className="print-area mt-5 rounded-xl border border-dashed bg-stone-50 p-4 text-center font-mono text-xs">
      <b>CoffeePOS · {t('Test chek')}</b>
      <p>----------------------</p>
      <p>Cappuccino 1 × 25000</p>
      <p>----------------------</p>
      <b>25 000 so'm</b>
      <p className="mt-2 text-stone-500">{t('Bu fiskal chek emas.')}</p>
    </div>
  </section>
}

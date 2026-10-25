import { useState } from 'react'
import { t } from './i18n'
import { getReceiptWidth, setReceiptWidth } from './printer'
import type { ReceiptWidth } from './printer'

export default function PrinterSettings() {
  const [width, setWidth] = useState<ReceiptWidth>(getReceiptWidth)
  const [connection, setConnection] = useState<'windows' | 'lan' | 'bluetooth'>('windows')
  function update(next: ReceiptWidth) { setWidth(next); setReceiptWidth(next) }
  return <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
    <h2 className="mb-3 text-lg font-semibold">{t('Chek printer sozlamasi')}</h2>
    <p className="mb-3 text-sm text-stone-500">{t('Bu sozlama faqat shu qurilmada saqlanadi. Browser chop etishi haqiqiy printer integratsiyasi emas.')}</p>
    <div className="mb-4 grid gap-3 sm:grid-cols-3">
      <button className={`rounded-xl border p-3 text-left text-sm ${connection === 'windows' ? 'border-amber-500 bg-amber-50' : ''}`} onClick={() => setConnection('windows')}>{t('Windows USB printer')}</button>
      <button className={`rounded-xl border p-3 text-left text-sm ${connection === 'lan' ? 'border-amber-500 bg-amber-50' : ''}`} onClick={() => setConnection('lan')}>{t('Wi-Fi / LAN printer')}</button>
      <button className={`rounded-xl border p-3 text-left text-sm ${connection === 'bluetooth' ? 'border-amber-500 bg-amber-50' : ''}`} onClick={() => setConnection('bluetooth')}>{t('Bluetooth printer')}</button>
    </div>
    <p className="mb-4 rounded-lg bg-stone-100 p-3 text-sm text-stone-700">
      {connection === 'windows' ? t('Printerni Windows drayveri orqali o‘rnating, uni tizimning standart printeri sifatida tanlang va test chek chiqaring.') :
       connection === 'lan' ? t('Printerni Wi-Fi yoki LAN tarmog‘iga ulang. Avtomatik ESC/POS chop etish uchun mahalliy print bridge kerak; brauzer faqat chop etish oynasini ochadi.') :
       t('Bluetooth printerni Windows yoki Android sozlamalarida juftlang. Avtomatik chop etish uchun Bluetooth ruxsati va nativ printer integratsiyasi kerak.')}
    </p>
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

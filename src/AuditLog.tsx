import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { exportExcel } from './exportExcel'
import { t } from './i18n'

type Entry = { id: number; staff: string; action: string; entity: string; entityId: string; details: Record<string, unknown>; createdAt: number }

const ACTIONS: { id: string; label: string }[] = [
  { id: '', label: 'Barcha amallar' },
  { id: 'order.', label: 'Buyurtmalar (chegirma, otmena, qaytarish)' },
  { id: 'shift.', label: 'Smenalar' },
  { id: 'stock.', label: 'Ombor' },
  { id: 'staff', label: 'Xodimlar va to‘lovlar' },
  { id: 'product.', label: 'Menyu narxlari' },
  { id: 'auth.', label: 'Kirishlar' },
]

const ACTION_LABEL: Record<string, string> = {
  'auth.login': 'Tizimga kirdi',
  'order.discount': 'Chegirma berildi',
  'order.cancel': 'Buyurtma bekor qilindi',
  'order.refund': 'Pul qaytarildi',
  'shift.open': 'Smena ochildi',
  'shift.close': 'Smena yopildi',
  'stock.writeoff': 'Spisaniye',
  'stock.count': 'Qoldiq tuzatildi',
  'inventory.create': 'Inventarizatsiya',
  'purchase.cancel': 'Nakladnoy bekor qilindi',
  'expense.create': 'Xarajat kiritildi',
  'staff_payment.create': 'Xodimga to‘lov',
  'payroll.update': 'Oylik o‘zgartirildi',
  'staff.create': 'Xodim qo‘shildi',
  'staff.update': 'Xodim o‘zgartirildi',
  'bonus.config': 'Bonus sozlamasi',
  'product.price': 'Narx o‘zgartirildi',
  'product.delete': 'Mahsulot o‘chirildi',
}

const details = (d: Record<string, unknown>) =>
  Object.entries(d).filter(([, v]) => v !== null && v !== '' && v !== undefined)
    .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(' · ')

export default function AuditLog() {
  const [items, setItems] = useState<Entry[]>([])
  const [action, setAction] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = useCallback(async () => {
    setBusy(true); setError('')
    try {
      const q = new URLSearchParams({ limit: '500' })
      if (action) q.set('action', action)
      setItems((await api<{ items: Entry[] }>('/api/audit?' + q.toString())).items)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }, [action])
  useEffect(() => { void load() }, [load])

  return <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
    <h2 className="mb-1 text-xl font-bold">{t('Audit jurnali')}</h2>
    <p className="mb-4 text-sm text-stone-500">{t('Muhim amallar: chegirma, otmena, qaytarish, smena, ombor, xodim va pul harakatlari. Yozuvlarni o‘chirib bo‘lmaydi.')}</p>
    <div className="mb-4 flex flex-wrap items-end gap-2">
      <label className="text-sm">{t('Turi')}<select className="mt-1 block rounded-lg border p-2" value={action} onChange={e => setAction(e.target.value)}>{ACTIONS.map(a => <option key={a.id} value={a.id}>{t(a.label)}</option>)}</select></label>
      <button disabled={busy} onClick={() => void load()} className="rounded-lg border px-3 py-2 text-sm">{t(busy ? 'Yuklanmoqda…' : 'Yangilash')}</button>
      <button className="rounded-lg border px-3 py-2 text-sm" onClick={() => exportExcel('coffeepos-audit', ['Sana, vaqt', 'Xodim', 'Amal', 'Obyekt', 'Tafsilotlar'].map(x => t(x)),
        items.map(a => [new Date(a.createdAt).toLocaleString(), a.staff, t(ACTION_LABEL[a.action] ?? a.action), `${a.entity} ${a.entityId}`, details(a.details)]))}>{t('Excel')}</button>
    </div>
    {error && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-2 text-red-700">{error}</p>}
    <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm">
      <thead><tr className="border-b text-stone-500"><th className="p-2">{t('Sana, vaqt')}</th><th className="p-2">{t('Xodim')}</th><th className="p-2">{t('Amal')}</th><th className="p-2">{t('Tafsilotlar')}</th></tr></thead>
      <tbody>{items.map(a => <tr key={a.id} className="border-b border-stone-100 align-top">
        <td className="whitespace-nowrap p-2">{new Date(a.createdAt).toLocaleString()}</td>
        <td className="p-2">{a.staff}</td>
        <td className="p-2 font-medium">{t(ACTION_LABEL[a.action] ?? a.action)}</td>
        <td className="break-all p-2 text-stone-600">{details(a.details)}</td>
      </tr>)}</tbody>
    </table>{!busy && items.length === 0 && <p className="p-5 text-center text-stone-500">{t('Yozuvlar yo‘q')}</p>}</div>
  </section>
}

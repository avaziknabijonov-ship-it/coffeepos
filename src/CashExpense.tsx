import { useState } from 'react'
import { api } from './api'
import { fmt } from './data'
import { t } from './i18n'
import { sync } from './store'

type Props = { onClose: () => void }
type Payment = 'cash' | 'card' | 'bank'
export default function CashExpense({ onClose }: Props) {
  const [amount, setAmount] = useState('')
  const [category, setCategory] = useState('Boshqa')
  const [description, setDescription] = useState('')
  const [payment, setPayment] = useState<Payment>('cash')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function save() {
    const number = Number(amount)
    if (!Number.isSafeInteger(number) || number <= 0) { setError(t('Summani to‘g‘ri kiriting')); return }
    setError(''); setBusy(true)
    try {
      await api('/api/expenses', { method: 'POST', body: { amount: number, category, description, payment } })
      await sync()
      onClose()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
    onClick={onClose}>
    <div className="w-full max-w-md rounded-t-3xl bg-white p-5 shadow-xl sm:rounded-3xl" onClick={e => e.stopPropagation()}>
      <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-bold">{t('Xarajat kiritish')}</h2>
        <button aria-label={t('Yopish')} className="rounded-lg px-3 py-1.5 text-sm" onClick={onClose}>✕</button></div>
      <div className="space-y-3">
        <label className="block text-sm">{t('Summa')} ({t("so'm")})
          <input autoFocus type="number" min={1} inputMode="numeric" value={amount} onChange={e => setAmount(e.target.value)}
            className="mt-1 w-full rounded-xl border p-3 text-base" />
        </label>
        <label className="block text-sm">{t('Sabab')}
          <select value={category} onChange={e=>setCategory(e.target.value)} className="mt-1 w-full rounded-xl border p-3">
            {['Boshqa','Transport','Ijara','Kommunal','Ta’mirlash','Xo‘jalik'].map(v=><option key={v} value={v}>{t(v)}</option>)}
          </select>
        </label>
        <label className="block text-sm">{t('To‘lov turi')}
          <select value={payment} onChange={e=>setPayment(e.target.value as Payment)} className="mt-1 w-full rounded-xl border p-3">
            <option value="cash">{t('Naqd')}</option><option value="card">{t('Karta')}</option><option value="bank">{t('Bank o‘tkazmasi')}</option>
          </select>
        </label>
        <label className="block text-sm">{t('Izoh')}<input value={description} onChange={e=>setDescription(e.target.value)} maxLength={256}
          className="mt-1 w-full rounded-xl border p-3" /></label>
        {payment === 'cash' && <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">{t('Naqd xarajat smena kassasidan ayriladi.')}</p>}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button disabled={busy || !amount} onClick={save} className="w-full rounded-xl bg-stone-900 py-3 font-semibold text-white disabled:opacity-40">
          {busy ? t('Saqlanmoqda...') : `${t('Saqlash')} · ${fmt(Number(amount) || 0)}`}
        </button>
      </div>
    </div>
  </div>
}

import { useState } from 'react'
import { t } from './i18n'
import { Lock, X } from 'lucide-react'
import { PAYMENT_LABEL, fmt, som, time } from './data'
import type { Payment } from './data'
import { closeShift, openShift, useAppState } from './store'
import type { ShiftInfo } from './store'

const digits = (v: string) => v.replace(/\D/g, '')

export function OpenShift({ canOpen }: { canOpen: boolean }) {
  const [cash, setCash] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      await openShift(Number(cash) || 0)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="grid h-full place-items-center p-4">
      <div className="w-full max-w-sm space-y-4 rounded-3xl border border-stone-200 bg-white p-6 text-center shadow-sm">
        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-amber-100 text-amber-700"><Lock className="size-7" /></span>
        <h2 className="text-xl font-bold">{t('Smena yopiq')}</h2>
        {canOpen ? (
          <>
            <label className="block text-left text-sm font-medium text-stone-600">
              {t("Kassadagi boshlang'ich naqd pul")}
              <input inputMode="numeric" value={cash ? fmt(Number(cash)) : ''} onChange={(e) => setCash(digits(e.target.value))} placeholder="0"
                className="mt-1 w-full rounded-xl border border-stone-200 px-3 py-3 text-lg outline-none focus:border-amber-500" />
            </label>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button disabled={busy} onClick={submit} className="w-full rounded-xl bg-amber-600 py-3.5 font-semibold text-white disabled:bg-stone-300">{t('Smenani ochish')}</button>
          </>
        ) : (
          <p className="text-stone-500">{t('Smenani kassir yoki administrator ochadi.')}</p>
        )}
      </div>
    </div>
  )
}

function Summary({ s }: { s: ShiftInfo }) {
  return (
    <dl className="space-y-1.5 text-sm">
      <div className="flex justify-between"><dt className="text-stone-500">{t('Ochilgan')}</dt><dd>{time(s.shift.openedAt)} · {s.shift.staff}</dd></div>
      <div className="flex justify-between"><dt className="text-stone-500">{t('Buyurtmalar')}</dt><dd>{t('{n} ta', { n: s.orders })}</dd></div>
      <div className="flex justify-between"><dt className="text-stone-500">{t('Tushum')}</dt><dd className="font-semibold">{som(s.revenue)}</dd></div>
      {(Object.keys(PAYMENT_LABEL) as Payment[]).map((p) => (
        <div key={p} className="flex justify-between pl-3"><dt className="text-stone-500">{t(PAYMENT_LABEL[p])}</dt><dd>{som(s.byPayment[p] ?? 0)}</dd></div>
      ))}
      <div className="flex justify-between border-t border-stone-200 pt-1.5"><dt className="text-stone-500">{t("Boshlang'ich naqd")}</dt><dd>{som(s.shift.openingCash)}</dd></div>
      <div className="flex justify-between border-t border-stone-200 pt-1.5"><dt className="font-medium">{t('Qarzdan qaytarilgan')}</dt><dd>{som(s.debtRepayments ?? 0)}</dd></div>
      {(['naqd', 'karta', 'payme', 'click'] as const).map(p => <div key={p} className="flex justify-between pl-3"><dt className="text-stone-500">{t(PAYMENT_LABEL[p])}</dt><dd>{som(s.debtRepaymentsByMethod?.[p] ?? 0)}</dd></div>)}
      <div className="flex justify-between"><dt className="text-stone-500">{t('Kunlik chiqimlar')}</dt><dd>{som(s.expenses ?? 0)}</dd></div>
      <div className="flex justify-between pl-3"><dt className="text-stone-500">{t('Naqd chiqimlar')}</dt><dd>{som(s.cashExpenses ?? 0)}</dd></div>
      <div className="flex justify-between"><dt className="font-medium">{t("Kassada bo'lishi kerak")}</dt><dd className="font-bold">{som(s.expectedCash)}</dd></div>
    </dl>
  )
}

export function CloseShiftModal({ onClose }: { onClose: () => void }) {
  const { shift } = useAppState()
  const [cash, setCash] = useState('')
  const [result, setResult] = useState<ShiftInfo | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const s = result ?? shift
  const submit = async () => {
    if (!confirm(t('Smena yopilsinmi?'))) return
    setBusy(true)
    setError('')
    try {
      setResult(await closeShift(Number(cash) || 0))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4" onClick={onClose}>
      <div className="max-h-[92dvh] w-full space-y-4 overflow-y-auto rounded-t-3xl bg-white p-5 sm:max-w-md sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">{result ? t('Smena yopildi') : t('Smena (X-hisobot)')}</h2>
          <button onClick={onClose} aria-label={t('Yopish')} className="rounded-lg p-2 hover:bg-stone-100"><X className="size-5" /></button>
        </div>
        {s ? <Summary s={s} /> : <p className="text-stone-500">{t("Ochiq smena yo'q.")}</p>}
        {result ? (
          <div className={`rounded-xl px-4 py-3 text-sm font-medium ${result.difference === 0 ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-700'}`}>
            {t('Sanalgan')}: {som(result.shift.closingCash ?? 0)} · {t('Farq')}: {(result.difference ?? 0) > 0 ? '+' : ''}{som(result.difference ?? 0)}
          </div>
        ) : s && (
          <>
            <label className="block text-sm font-medium text-stone-600">
              {t('Kassada sanalgan naqd pul')}
              <input inputMode="numeric" value={cash ? fmt(Number(cash)) : ''} onChange={(e) => setCash(digits(e.target.value))} placeholder="0"
                className="mt-1 w-full rounded-xl border border-stone-200 px-3 py-3 text-lg outline-none focus:border-amber-500" />
            </label>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button disabled={busy || !cash} onClick={submit} className="w-full rounded-xl bg-stone-900 py-3.5 font-semibold text-white disabled:bg-stone-300">{t('Smenani yopish (Z-hisobot)')}</button>
          </>
        )}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { t } from './i18n'
import LangSwitch from './LangSwitch'
import { Coffee, Delete } from 'lucide-react'
import { login } from './store'

export default function Login() {
  return (
    <div className="grid min-h-dvh place-items-center bg-stone-900 p-4">
      <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-xl">
        <div className="mb-6 flex items-center gap-2 text-xl font-bold">
          <span className="grid size-10 place-items-center rounded-xl bg-amber-600 text-white"><Coffee className="size-6" /></span>
          CoffeePOS
          <span className="ml-auto"><LangSwitch light /></span>
        </div>
        <PinLogin />
      </div>
    </div>
  )
}

const input = 'w-full rounded-xl border border-stone-200 px-3 py-2.5 outline-none focus:border-amber-500'

function PinLogin() {
  const [company, setCompany] = useState(() => localStorage.getItem('coffeepos-company') ?? 'demo')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (p = pin) => {
    if (busy || p.length < 4) return
    setBusy(true)
    setError('')
    try {
      await login(company.trim().toLowerCase(), p)
    } catch (e) {
      setError((e as Error).message)
      setPin('')
    } finally {
      setBusy(false)
    }
  }
  const press = (d: string) => {
    if (pin.length >= 6) return
    const next = pin + d
    setPin(next)
    if (next.length === 6) void submit(next)
  }

  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium text-stone-600">
        {t('Kofe bar logini')}
        <input value={company} onChange={(e) => setCompany(e.target.value)} className={`${input} mt-1`} autoCapitalize="none" />
      </label>
      <div>
        <div className="mb-3 text-center text-sm font-medium text-stone-600">{t('PIN-kod')}</div>
        <div className="mb-4 flex justify-center gap-3">
          {Array.from({ length: Math.max(4, pin.length) }, (_, i) => (
            <span key={i} className={`size-4 rounded-full ${i < pin.length ? 'bg-stone-900' : 'bg-stone-200'}`} />
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
            <button key={d} onClick={() => press(d)} className="h-14 rounded-xl bg-stone-100 text-xl font-semibold active:bg-stone-200">{d}</button>
          ))}
          <button onClick={() => setPin('')} className="h-14 rounded-xl text-sm text-stone-500">{t('Tozalash')}</button>
          <button onClick={() => press('0')} className="h-14 rounded-xl bg-stone-100 text-xl font-semibold active:bg-stone-200">0</button>
          <button onClick={() => setPin((p) => p.slice(0, -1))} aria-label={t("O'chirish")} className="grid h-14 place-items-center rounded-xl text-stone-500"><Delete className="size-6" /></button>
        </div>
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <button disabled={busy || pin.length < 4} onClick={() => submit()}
        className="w-full rounded-xl bg-amber-600 py-3.5 font-semibold text-white disabled:bg-stone-200 disabled:text-stone-400">
        {busy ? t('Kirilmoqda…') : t('Kirish')}
      </button>
    </div>
  )
}


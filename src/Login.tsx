import { useState } from 'react'
import { t } from './i18n'
import LangSwitch from './LangSwitch'
import { Coffee, Delete } from 'lucide-react'
import { login, register } from './store'

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  return (
    <div className="grid min-h-dvh place-items-center bg-stone-900 p-4">
      <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-xl">
        <div className="mb-6 flex items-center gap-2 text-xl font-bold">
          <span className="grid size-10 place-items-center rounded-xl bg-amber-600 text-white"><Coffee className="size-6" /></span>
          CoffeePOS
          <span className="ml-auto"><LangSwitch light /></span>
        </div>
        {mode === 'login' ? <PinLogin onRegister={() => setMode('register')} /> : <Register onBack={() => setMode('login')} />}
      </div>
    </div>
  )
}

const input = 'w-full rounded-xl border border-stone-200 px-3 py-2.5 outline-none focus:border-amber-500'

function PinLogin({ onRegister }: { onRegister: () => void }) {
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
      {company === 'demo' && (
        <p className="text-center text-xs text-stone-500">{t('Demo PIN: 1111 rahbar · 2222 kassir · 3333 barista')}</p>
      )}
      <button onClick={onRegister} className="w-full text-sm font-medium text-amber-700">{t("Yangi kofe barni ro'yxatdan o'tkazish")}</button>
    </div>
  )
}

function Register({ onBack }: { onBack: () => void }) {
  const [f, setF] = useState({ companyName: '', slug: '', ownerName: '', ownerPin: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const upd = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => {
    let v = e.target.value
    if (k === 'slug') v = v.toLowerCase().replace(/[^a-z0-9-]/g, '')
    if (k === 'ownerPin') v = v.replace(/\D/g, '').slice(0, 6)
    setF((x) => ({ ...x, [k]: v }))
  }
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await register(f)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3">
      <h2 className="font-semibold">{t('Yangi kofe bar')}</h2>
      <input required placeholder={t('Kofe bar nomi')} value={f.companyName} onChange={upd('companyName')} className={input} />
      <div>
        <input required minLength={3} placeholder={t('Login (masalan: bek-coffee)')} value={f.slug} onChange={upd('slug')} className={input} />
        <p className="mt-1 text-xs text-stone-500">{t('Kirishda ishlatiladi: lotin harflari, raqam va "-"')}</p>
      </div>
      <input required placeholder={t('Rahbar ismi')} value={f.ownerName} onChange={upd('ownerName')} className={input} />
      <input required minLength={4} inputMode="numeric" type="password" placeholder={t('Rahbar PIN-kodi (4–6 raqam)')} value={f.ownerPin} onChange={upd('ownerPin')} className={input} />
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <button disabled={busy} className="w-full rounded-xl bg-amber-600 py-3.5 font-semibold text-white disabled:bg-stone-300">
        {busy ? t('Yaratilmoqda…') : t('Yaratish')}
      </button>
      <p className="text-xs text-stone-500">{t("Standart kofe menyusi, texkartalar va ombor avtomatik qo'shiladi, keyin Admin bo'limida o'zgartirasiz.")}</p>
      <button type="button" onClick={onBack} className="w-full text-sm font-medium text-stone-600">{t('Orqaga')}</button>
    </form>
  )
}

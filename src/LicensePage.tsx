import { useEffect, useState } from 'react'
import { api } from './api'
import { useAppState } from './store'
import { t } from './i18n'

type License = {
  status: 'trial' | 'active' | 'grace' | 'expired' | 'suspended' | 'unconfigured'
  plan: 'monthly' | 'yearly' | null
  canWrite: boolean
  expiresAt: number | null
  trialEndsAt: number | null
  currentPeriodEndsAt: number | null
  graceEndsAt: number | null
  serverTime: number
}

const statusName: Record<License['status'], string> = {
  trial: 'Sinov muddati',
  active: 'Faol',
  grace: 'Imtiyozli muddat',
  expired: 'Muddati tugagan',
  suspended: 'To‘xtatilgan',
  unconfigured: 'Sozlanmagan',
}

const format = (ms: number | null) => ms ? new Date(ms).toLocaleDateString('ru-RU') : '—'

export default function LicensePage() {
  const { session } = useAppState()
  const [license, setLicense] = useState<License | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = () => {
    setLoading(true)
    setError('')
    void api<License>('/api/license/status').then(setLicense).catch((e: Error) => setError(e.message)).finally(() => setLoading(false))
  }
  useEffect(() => { refresh() }, [])

  const rows = license ? [
    [t('Tarif'), license.plan === 'monthly' ? t('Oylik') : license.plan === 'yearly' ? t('Yillik') : t('Belgilanmagan')],
    [t('Sinov muddati tugaydi'), format(license.trialEndsAt)],
    [t('Faol obuna tugaydi'), format(license.currentPeriodEndsAt)],
    [t('Imtiyozli muddat tugaydi'), format(license.graceEndsAt)],
  ] : []

  return <div className="mx-auto max-w-2xl space-y-5 p-4 sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-bold">{t('Litsenziya')}</h1>
      <button onClick={refresh} disabled={loading} className="rounded-lg border border-stone-300 px-4 py-2 text-sm disabled:opacity-50">{t('Yangilash')}</button>
    </div>
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-stone-500">{t('Qahvaxona nomi')}</p>
      <p className="mb-1 font-semibold">{session?.company.name || '—'}</p>
      <p className="mb-5 font-mono text-sm text-stone-500">{session?.company.slug || '—'}</p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {!license && !error && <p>{t('Yuklanmoqda…')}</p>}
      {license && <>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-3 py-1 text-sm font-semibold ${license.canWrite ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {t(statusName[license.status])}
          </span>
          <span className="text-sm text-stone-600">
            {license.canWrite ? t('Savdo qilish mumkin') : t('Faqat ko‘rish mumkin — yangi amallar bloklangan')}
          </span>
        </div>
        {license.expiresAt && <p className="mb-4 text-sm font-medium text-amber-800">
          {t('Litsenziya muddati')}: {format(license.expiresAt)} · {t('Qolgan kunlar')}: {Math.max(0, Math.ceil((license.expiresAt - license.serverTime) / 86_400_000))}
        </p>}
        <dl className="divide-y divide-stone-100 text-sm">
          {rows.map(([name, value]) => <div key={name} className="flex flex-wrap justify-between gap-2 py-3">
            <dt className="text-stone-600">{name}</dt><dd className="font-semibold">{value}</dd>
          </div>)}
        </dl>
      </>}
    </div>
    <div className="rounded-2xl border border-stone-200 bg-white p-5 text-sm text-stone-700">
      <p className="font-semibold">{t('Obunani uzaytirish')}</p>
      <p className="mt-2">{t('Litsenziyani uzaytirish uchun CoffeePOS platforma administratoriga qahvaxona loginini yuboring. To‘lovni tasdiqlash va muddat berish administrator tomonidan amalga oshiriladi.')}</p>
      <p className="mt-2 text-stone-500">{t('To‘lov hali ilova orqali avtomatik qabul qilinmaydi.')}</p>
    </div>
  </div>
}

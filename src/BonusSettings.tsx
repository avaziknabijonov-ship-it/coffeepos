import { useEffect, useState } from 'react'
import { api } from './api'
import { t } from './i18n'

type Rules = { enabled: boolean; earnPercent: number; redemptionLimitPercent: number }
export default function BonusSettings() {
  const [rules, setRules] = useState<Rules | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  useEffect(() => { api<Rules>('/api/bonus/config').then(setRules).catch(e => setError((e as Error).message)) }, [])
  const field = 'w-full rounded-xl border border-stone-200 bg-white p-2.5 text-sm'
  async function save() {
    if (!rules) return
    setBusy(true); setSaved(false); setError('')
    try {
      const r = await api<Rules>('/api/bonus/config', { method: 'PUT', body: {
        enabled: rules.enabled,
        earn_percent: rules.earnPercent,
        redemption_limit_percent: rules.redemptionLimitPercent,
      } })
      setRules(r); setSaved(true)
    } catch(e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <section className="rounded-2xl border border-stone-200 bg-white p-5">
    <h2 className="text-lg font-semibold">{t('Bonus tizimi')}</h2>
    <p className="my-3 text-sm text-stone-600">{t('Mijoz telefon raqami bo‘yicha bonus yig‘iladi va ishlatiladi.')}</p>
    {rules && <div className="max-w-xl space-y-4">
      <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={rules.enabled} onChange={e=>setRules({...rules,enabled:e.target.checked})}/>{t('Bonus tizimi faol')}</label>
      <label className="block text-sm">{t('Bonus yig‘ish foizi')} (0–20%)
        <input className={field} type="number" min={0} max={20} value={rules.earnPercent} onChange={e=>setRules({...rules,earnPercent:Number(e.target.value)})} />
      </label>
      <label className="block text-sm">{t('Chekni bonus bilan to‘lash limiti')} (0–50%)
        <input className={field} type="number" min={0} max={50} value={rules.redemptionLimitPercent} onChange={e=>setRules({...rules,redemptionLimitPercent:Number(e.target.value)})} />
      </label>
      <button disabled={busy} onClick={save} className="rounded-xl bg-stone-900 px-5 py-2.5 font-semibold text-white disabled:opacity-50">{t('Saqlash')}</button>
      {saved && <p className="text-sm text-emerald-700">{t('Saqlandi')}</p>}
    </div>}
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
  </section>
}

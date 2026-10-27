import { useEffect, useState } from 'react'
import { api, setToken } from './api'
import { forgetDeviceSecret, saveDeviceSecret } from './device'
import { logout, useAppState } from './store'
import { t } from './i18n'

type Device = { id: number; name: string; active: boolean; createdAt: number; lastSeenAt: number; revokedAt: number | null }
type Page = { items: Device[]; required: boolean; currentDeviceId: number | null }
export default function DeviceManagement() {
  const { session } = useAppState()
  const [page, setPage] = useState<Page | null>(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    api<Page>('/api/devices').then(result => { if (active) setPage(result) }).catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [])
  const act = async (action: () => Promise<void>) => {
    setBusy(true); setError('')
    try { await action() }
    catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  const enroll = () => act(async () => {
    if (!session) return
    const result = await api<{ deviceSecret: string; token: string }>('/api/devices', { body: { name } })
    saveDeviceSecret(session.company.slug, result.deviceSecret)
    setToken(result.token)
    setName(''); setPage(await api<Page>('/api/devices'))
  })
  const revoke = (device: Device) => act(async () => {
    await api('/api/devices/' + device.id + '/revoke', { method: 'POST' })
    if (device.id === page?.currentDeviceId && session) {
      forgetDeviceSecret(session.company.slug); logout(); return
    }
    setPage(await api<Page>('/api/devices'))
  })
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <h2 className="text-xl font-semibold">{t('Qurilmalar')}</h2>
    <p className="text-sm text-stone-600">{t('Rahbar shu brauzerni ro‘yxatga oladi, so‘ng xodim o‘z PIN kodi bilan kiradi. Ruxsat bekor qilinsa, shu qurilmaga bog‘langan sessiyalar yopiladi.')}</p>
    <p className="text-sm text-stone-600">{t('Majburiy tartib kassir va baristaga qo‘llanadi. Rahbar va administrator PIN orqali tiklash uchun kira oladi.')}</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {session?.staff.role === 'owner' && page && <label className="flex items-start gap-2 rounded border p-3">
      <input type="checkbox" checked={page.required} disabled={busy} onChange={e => { const required = e.target.checked; void act(async () => { await api('/api/devices/policy', { method: 'PUT', body: { required } }); setPage(await api<Page>('/api/devices')) }) }} />
      {t('Kassir va barista faqat ro‘yxatdan o‘tgan qurilmada ishlasin')}
    </label>}
    {!page?.currentDeviceId && <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); void enroll() }}>
      <input aria-label={t('Qurilma nomi')} placeholder={t('Qurilma nomi')} className="rounded border p-2" maxLength={64} required value={name} onChange={e => setName(e.target.value)} />
      <button disabled={busy || !name.trim()} className="rounded bg-stone-800 px-3 py-2 text-white disabled:opacity-50">{t('Bu brauzerni ro‘yxatga olish')}</button>
    </form>}
    <button className="rounded border px-3 py-2" disabled={busy} onClick={() => void act(async () => setPage(await api<Page>('/api/devices')))}>{t('Yangilash')}</button>
    {!page ? <p>{t('Yuklanmoqda…')}</p> : <div className="space-y-2">{page.items.map(device => <article className="flex flex-wrap items-center justify-between gap-3 rounded border p-3" key={device.id}>
      <div><p className="font-semibold">{device.name} {device.id === page.currentDeviceId && <span>· {t('Joriy qurilma')}</span>}</p><p className="text-sm">{device.active ? t('Faol') : t('Bekor qilingan')} · {t('Oxirgi faollik')}: {new Date(device.lastSeenAt).toLocaleString()}</p></div>
      {device.active && <button disabled={busy} className="rounded border border-red-300 px-3 py-2 text-red-700 disabled:opacity-50" onClick={() => void revoke(device)}>{t('Qurilma ruxsatini bekor qilish')}</button>}
    </article>)}</div>}
  </section>
}

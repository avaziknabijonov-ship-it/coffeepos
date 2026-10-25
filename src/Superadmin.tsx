import { useEffect, useState } from 'react'
import { t, tServer } from './i18n'
import LangSwitch from './LangSwitch'
import { useAppState } from './store'
type Subscription = { plan: string; status: string; expiresAt: number }
type Company = { id: number; slug: string; name: string; createdAt: number; subscription: Subscription | null }
type Result = { items: Company[]; offset: number; limit: number }
type Action = 'grant' | 'renew' | 'suspend'

export default function Superadmin() {
  const { lang } = useAppState()
  void lang
  const [key, setKey] = useState('')
  const [authenticated, setAuthenticated] = useState(false)
  const [companies, setCompanies] = useState<Company[]>([])
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [slug, setSlug] = useState('')
  const [name, setName] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [ownerPin, setOwnerPin] = useState('')
  const [plan, setPlan] = useState<'monthly' | 'yearly'>('monthly')
  const [days, setDays] = useState(30)
  const limit = 100

  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const res = await fetch('/api/superadmin' + path, {
      method,
      headers: { 'X-Superadmin-Key': key, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      cache: 'no-store',
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(typeof data.detail === 'string' ? tServer(data.detail) : Array.isArray(data.detail) ? t("Ma'lumotlar noto'g'ri to'ldirilgan") : t('Xatolik: ') + res.status)
    }
    return res.json() as Promise<T>
  }

  async function load(nextOffset = offset) {
    setError('')
    try {
      const r = await request<Result>('/companies?limit=' + limit + '&offset=' + nextOffset)
      setCompanies(r.items); setOffset(nextOffset); setAuthenticated(true)
    } catch (e) { setAuthenticated(false); setError((e as Error).message) }
  }
  // Deliberately never persist the platform key in browser storage.
  useEffect(() => { setAuthenticated(false); setCompanies([]) }, [key])
  async function create() {
    setBusy(true); setError('')
    try {
      await request('/companies', 'POST', { slug, name, owner_name: ownerName, owner_pin: ownerPin, plan, days })
      setOwnerPin(''); setSlug(''); setName(''); setOwnerName('')
      await load(0)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function update(slugValue: string, action: Action) {
    if (!window.confirm(slugValue + ' — ' + t(action === 'grant' ? 'Berish' : action === 'renew' ? 'Uzaytirish' : 'To‘xtatish') + '?')) return
    setBusy(true); setError('')
    try { await request('/companies/' + encodeURIComponent(slugValue) + '/subscription', 'POST', { action, plan, days }); await load() }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const field = 'w-full min-w-0 rounded-lg border border-stone-300 bg-white p-2 text-sm'
  return <main className="min-h-screen bg-stone-100 p-4 text-stone-900">
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex items-center justify-between"><h1 className="text-2xl font-bold">{t("CoffeePOS · Superadmin")}</h1><div className="flex items-center gap-3"><LangSwitch light /><a className="text-sm underline" href="/#admin">CoffeePOS</a></div></header>
      <section className="rounded-xl bg-white p-5">
        <label className="block text-sm font-semibold">{t("Maxfiy superadmin kaliti (faqat shu sahifada)")}</label>
        <div className="mt-2 flex gap-2"><input className={field} type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} placeholder="SUPERADMIN_KEY" /><button className="rounded-lg bg-stone-900 px-4 text-white" onClick={() => load(0)}>{t("Kirish")}</button></div>
        <p className="mt-2 text-xs text-stone-500">{t("Kalit brauzer xotirasiga saqlanmaydi. Hech kimga yubormang.")}</p>
        {error && <p className="mt-2 text-sm text-red-600" role="alert">{error}</p>}
      </section>
      {authenticated && <>
        <section className="rounded-xl bg-white p-5">
          <h2 className="mb-3 text-lg font-semibold">{t("Yangi qahvaxona yaratish")}</h2>
          <form onSubmit={e => { e.preventDefault(); void create() }} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-sm">{t("Login")}<input className={field} value={slug} onChange={e => setSlug(e.target.value)} required minLength={3} maxLength={41} pattern="[a-z0-9][a-z0-9-]{2,40}" /></label>
            <label className="text-sm">{t("Qahvaxona nomi")}<input className={field} value={name} onChange={e => setName(e.target.value)} required /></label>
            <label className="text-sm">{t("Rahbar ismi")}<input className={field} value={ownerName} onChange={e => setOwnerName(e.target.value)} required /></label>
            <label className="text-sm">{t("Rahbar PIN")}<input className={field} type="password" inputMode="numeric" autoComplete="new-password" value={ownerPin} onChange={e => setOwnerPin(e.target.value)} required pattern="[0-9]{4,6}" /></label>
            <label className="text-sm">{t("Tarif")}<select className={field} value={plan} onChange={e => setPlan(e.target.value as 'monthly' | 'yearly')}><option value="monthly">{t("Oylik")}</option><option value="yearly">{t("Yillik")}</option></select></label>
            <label className="text-sm">{t("Obuna davomiyligi, kun")}<input className={field} type="number" min="1" max="730" value={days} onChange={e => setDays(Number(e.target.value))} required /></label>
            <button className="self-end rounded-lg bg-stone-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={busy}>{t("Qahvaxona yaratish")}</button>
          </form>
        </section>
        <section className="rounded-xl bg-white p-5">
          <h2 className="mb-3 text-lg font-semibold">{t("Qahvaxonalar va litsenziyalar")}</h2>
          <div className="space-y-2">{companies.map(c => <div key={c.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
            <div className="text-sm"><b>{c.name}</b> <span className="text-stone-500">({c.slug})</span><p className="text-stone-500">{c.subscription ? (t(c.subscription.plan === 'monthly' ? 'Oylik' : 'Yillik') + ' · ' + (c.subscription.status === 'active' ? (t('Faol')) : c.subscription.status === 'suspended' ? t('To‘xtatilgan') : c.subscription.status) + ' · ' + new Date(c.subscription.expiresAt).toLocaleDateString()) : t('Obuna yo‘q')}</p></div>
            <div className="flex flex-wrap gap-2"><button className="rounded-lg border px-3 py-1.5 text-sm" onClick={() => update(c.slug, 'grant')} disabled={busy}>{t("Berish")}</button><button className="rounded-lg border px-3 py-1.5 text-sm" onClick={() => update(c.slug, 'renew')} disabled={busy}>{t("Uzaytirish")}</button><button className="rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-700" onClick={() => update(c.slug, 'suspend')} disabled={busy || !c.subscription}>{t("To‘xtatish")}</button></div>
          </div>)}</div>
          <div className="mt-3 flex items-center gap-3"><button disabled={offset === 0} onClick={() => load(Math.max(0, offset-limit))} className="rounded-lg border px-3 py-1.5 disabled:opacity-40">{t("Oldingi")}</button><span className="text-sm">{offset+1}–{offset+companies.length}</span><button disabled={companies.length < limit} onClick={() => load(offset+limit)} className="rounded-lg border px-3 py-1.5 disabled:opacity-40">{t("Keyingi")}</button></div>
        </section>
      </>}
    </div>
  </main>
}

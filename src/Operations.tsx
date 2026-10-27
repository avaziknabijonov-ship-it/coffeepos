import { useEffect, useState } from 'react'
import { api, getBranch, setBranch, setDeviceToken } from './api'
import { t, tCatalogName } from './i18n'
import { INGREDIENTS, som } from './data'
import { sync } from './store'

const box = 'space-y-3 rounded-2xl border bg-white p-4'
const input = 'rounded border p-2'
const btn = 'rounded border px-3 py-2 disabled:opacity-50'
const primary = 'rounded bg-stone-800 px-3 py-2 text-white disabled:opacity-50'
const when = (ms?: number | null) => (ms ? new Date(ms).toLocaleString() : '—')
const key = () => crypto.randomUUID().replaceAll('-', '')

function useLoad<T>(path: string, initial: T): [T, () => Promise<void>, string, (e: string) => void] {
  const [data, setData] = useState<T>(initial)
  const [error, setError] = useState('')
  const load = async () => {
    try { setData(await api<T>(path)); setError('') } catch (e) { setError((e as Error).message) }
  }
  useEffect(() => { void load() }, [path])
  return [data, load, error, setError]
}

async function run(setError: (e: string) => void, fn: () => Promise<unknown>, after: () => Promise<void>) {
  setError('')
  try { await fn(); await after() } catch (e) { setError((e as Error).message) }
}

type Branch = { id: number; name: string; isDefault: boolean; active: boolean }
type Line = { ing: string; qty: number }
type Transfer = { id: number; fromBranchId: number; toBranchId: number; status: string; lines: Line[]; note: string; dispatchedBy: string; dispatchedAt: number }
type Notice = { id: number; name: string; unit: string; stock: number; min: number; openedAt: number }

export function BranchesPanel() {
  const [branches, loadBranches, error, setError] = useLoad<{ current: number; items: Branch[] }>('/api/branches', { current: 0, items: [] })
  const [transfers, loadTransfers] = useLoad<Transfer[]>('/api/transfers', [])
  const [notices, loadNotices] = useLoad<{ items: Notice[] }>('/api/stock/notifications', { items: [] })
  const [name, setName] = useState('')
  const [to, setTo] = useState('')
  const [ing, setIng] = useState(INGREDIENTS[0]?.id ?? '')
  const [qty, setQty] = useState(1)
  const reload = async () => { await Promise.all([loadBranches(), loadTransfers(), loadNotices()]) }
  const branchName = (id: number) => branches.items.find(b => b.id === id)?.name ?? '#' + id
  const others = branches.items.filter(b => b.id !== branches.current && b.active)
  const choose = async (id: string) => { setBranch(id); await reload(); await sync() }
  return <section className={box}>
    <h2 className="text-xl font-semibold">{t('Filiallar va transfer')}</h2>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <label className="block">{t('Faol filial')}
      <select className={'block ' + input} value={String(getBranch() ?? branches.current)} onChange={e => void choose(e.target.value)}>
        {branches.items.map(b => <option key={b.id} value={b.id}>{b.name}{b.isDefault ? ' ★' : ''}</option>)}
      </select>
    </label>
    <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); void run(setError, () => api('/api/branches', { body: { name } }), async () => { setName(''); await reload() }) }}>
      <input className={input} required maxLength={64} placeholder={t('Yangi filial nomi')} value={name} onChange={e => setName(e.target.value)} />
      <button className={primary}>{t('Filial qo‘shish')}</button>
    </form>
    <h3 className="font-semibold">{t('Kam qoldiq ogohlantirishlari')}</h3>
    {notices.items.length === 0 ? <p className="text-sm text-stone-500">{t('Ogohlantirish yo‘q')}</p> :
      <ul className="text-sm">{notices.items.map(n => <li key={n.id}>{tCatalogName(n.name)}: {n.stock} / {n.min} {n.unit} · {when(n.openedAt)}</li>)}</ul>}
    <h3 className="font-semibold">{t('Filiallararo transfer')}</h3>
    <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); void run(setError, () => api('/api/transfers', { body: { clientKey: key(), toBranchId: Number(to), lines: [{ ing, qty }] } }), reload) }}>
      <select aria-label={t('Qabul qiluvchi filial')} className={input} required value={to} onChange={e => setTo(e.target.value)}>
        <option value="">{t('Qabul qiluvchi filial')}</option>
        {others.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
      </select>
      <select aria-label={t('Xomashyo')} className={input} value={ing} onChange={e => setIng(e.target.value)}>{INGREDIENTS.map(i => <option key={i.id} value={i.id}>{tCatalogName(i.name)}</option>)}</select>
      <input aria-label={t('Miqdor')} className={'w-24 ' + input} type="number" min="0.001" step="any" value={qty} onChange={e => setQty(Number(e.target.value))} />
      <button className={primary} disabled={!to}>{t('Jo‘natish')}</button>
    </form>
    {transfers.map(tr => <div key={tr.id} className="flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm">
      <span>#{tr.id} {branchName(tr.fromBranchId)} → {branchName(tr.toBranchId)} · {tr.lines.map(l => `${l.ing} ${l.qty}`).join(', ')} · {t(tr.status === 'in_transit' ? 'Yo‘lda' : tr.status === 'received' ? 'Qabul qilindi' : 'Bekor qilindi')}</span>
      {tr.status === 'in_transit' && <span className="flex gap-2">
        {tr.toBranchId === branches.current && <button className={btn} onClick={() => void run(setError, () => api(`/api/transfers/${tr.id}/receive`, { body: {} }), reload)}>{t('Qabul qilish')}</button>}
        {tr.fromBranchId === branches.current && <button className={btn} onClick={() => void run(setError, () => api(`/api/transfers/${tr.id}/cancel`, { body: {} }), reload)}>{t('Bekor qilish')}</button>}
      </span>}
    </div>)}
  </section>
}

type DraftRef = { id: number; version: number; items: number; staff: string }
type Floor = { areas: { id: number; name: string }[]; tables: { id: number; areaId: number; name: string; seats: number; active: boolean; occupied: boolean; drafts: DraftRef[] }[]; takeaway: DraftRef[] }

export function FloorPanel() {
  const [floor, load, error, setError] = useLoad<Floor>('/api/floor', { areas: [], tables: [], takeaway: [] })
  const [area, setArea] = useState('')
  const [table, setTable] = useState({ areaId: '', name: '', seats: 2 })
  const move = (d: DraftRef, value: string) => run(setError, () => api(`/api/drafts/${d.id}/move`, { body: value === 'takeaway' ? { version: d.version, service: 'takeaway' } : { version: d.version, tableId: Number(value), service: 'dine_in' } }), load)
  const allDrafts = [...floor.tables.flatMap(tb => tb.drafts), ...floor.takeaway]
  const merge = (d: DraftRef, target: string) => {
    const other = allDrafts.find(x => x.id === Number(target))
    if (other) void run(setError, () => api(`/api/drafts/${d.id}/merge`, { body: { version: d.version, targetId: other.id, targetVersion: other.version } }), load)
  }
  const draftRow = (d: DraftRef) => <div key={d.id} className="flex flex-wrap items-center gap-2 text-sm">
    <span>{t('Draft')} #{d.id} · {d.items} · {d.staff}</span>
    <select aria-label={t('Ko‘chirish')} className={input} value="" onChange={e => void move(d, e.target.value)}>
      <option value="">{t('Ko‘chirish')}</option><option value="takeaway">{t('Olib ketish')}</option>
      {floor.tables.filter(tb => tb.active).map(tb => <option key={tb.id} value={tb.id}>{tb.name}</option>)}
    </select>
    <select aria-label={t('Birlashtirish')} className={input} value="" onChange={e => merge(d, e.target.value)}>
      <option value="">{t('Birlashtirish')}</option>
      {allDrafts.filter(x => x.id !== d.id).map(x => <option key={x.id} value={x.id}>#{x.id}</option>)}
    </select>
  </div>
  return <section className={box}>
    <h2 className="text-xl font-semibold">{t('Zal va stollar')}</h2>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); void run(setError, () => api('/api/areas', { body: { name: area } }), async () => { setArea(''); await load() }) }}>
      <input className={input} required maxLength={64} placeholder={t('Zal nomi')} value={area} onChange={e => setArea(e.target.value)} />
      <button className={primary}>{t('Zal qo‘shish')}</button>
    </form>
    <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); void run(setError, () => api('/api/tables', { body: { areaId: Number(table.areaId), name: table.name, seats: table.seats } }), async () => { setTable({ ...table, name: '' }); await load() }) }}>
      <select aria-label={t('Zal')} className={input} required value={table.areaId} onChange={e => setTable({ ...table, areaId: e.target.value })}><option value="">{t('Zal')}</option>{floor.areas.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select>
      <input className={input} required maxLength={64} placeholder={t('Stol nomi')} value={table.name} onChange={e => setTable({ ...table, name: e.target.value })} />
      <input aria-label={t('O‘rinlar')} className={'w-20 ' + input} type="number" min="1" max="50" value={table.seats} onChange={e => setTable({ ...table, seats: Number(e.target.value) })} />
      <button className={primary}>{t('Stol qo‘shish')}</button>
    </form>
    {floor.areas.map(a => <div key={a.id}><h3 className="font-semibold">{a.name}</h3>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{floor.tables.filter(tb => tb.areaId === a.id).map(tb => <div key={tb.id} className={`rounded border p-2 ${tb.occupied ? 'border-amber-500 bg-amber-50 text-stone-900' : ''}`}>
        <div className="font-medium">{tb.name} · {tb.seats} · {tb.occupied ? t('Band') : t('Bo‘sh')}</div>{tb.drafts.map(draftRow)}
      </div>)}</div></div>)}
    {floor.takeaway.length > 0 && <div><h3 className="font-semibold">{t('Olib ketish')}</h3>{floor.takeaway.map(draftRow)}</div>}
  </section>
}

type CashRow = { shiftId: number; openedBy: string; closedBy: string; closedAt: number; openingCash: number; cashSales: number; cashRefunds: number; cashExpenses: number; expectedCash: number; closingCash: number; difference: number }
type Inv = { id: number; staff: string; status: string; shortage: number; surplus: number; createdAt: number }

export function CashControlPanel() {
  const [days, setDays] = useState(7)
  const [cash, , error, setError] = useLoad<{ items: CashRow[]; shortage: number; surplus: number }>('/api/reports/cash-variance?days=' + days, { items: [], shortage: 0, surplus: 0 })
  const [invs, loadInvs] = useLoad<Inv[]>('/api/inventories', [])
  const pending = invs.filter(i => i.status === 'pending')
  return <section className={box}>
    <h2 className="text-xl font-semibold">{t('Kassa va inventar nazorati')}</h2>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <label>{t('Davr (kun)')} <input className={'w-20 ' + input} type="number" min="1" max="92" value={days} onChange={e => setDays(Number(e.target.value))} /></label>
    <p>{t('Kamomad')}: <b>{som(cash.shortage)}</b> · {t('Ortiqcha')}: <b>{som(cash.surplus)}</b></p>
    <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left">
      <th>{t('Smena')}</th><th>{t('Ochdi / yopdi')}</th><th>{t('Boshlang‘ich')}</th><th>{t('Naqd savdo')}</th><th>{t('Naqd qaytarish')}</th><th>{t('Naqd xarajat')}</th><th>{t('Kutilgan')}</th><th>{t('Sanaldi')}</th><th>{t('Farq')}</th>
    </tr></thead><tbody>{cash.items.map(r => <tr key={r.shiftId} className="border-t">
      <td>#{r.shiftId} {when(r.closedAt)}</td><td>{r.openedBy} / {r.closedBy}</td><td>{som(r.openingCash)}</td><td>{som(r.cashSales)}</td><td>{som(r.cashRefunds)}</td><td>{som(r.cashExpenses)}</td><td>{som(r.expectedCash)}</td><td>{som(r.closingCash)}</td>
      <td className={r.difference < 0 ? 'text-red-700' : r.difference > 0 ? 'text-amber-700' : ''}>{som(r.difference)}</td>
    </tr>)}</tbody></table></div>
    <h3 className="font-semibold">{t('Tasdiq kutayotgan inventarizatsiyalar')}</h3>
    {pending.length === 0 ? <p className="text-sm text-stone-500">{t('Tasdiq kutayotgan hujjat yo‘q')}</p> : pending.map(i => <div key={i.id} className="flex flex-wrap items-center gap-2 text-sm">
      <span>#{i.id} · {i.staff} · {t('Kamomad')} {som(i.shortage)} · {t('Ortiqcha')} {som(i.surplus)}</span>
      <button className={btn} onClick={() => void run(setError, () => api(`/api/inventories/${i.id}/approve`, { body: {} }), loadInvs)}>{t('Tasdiqlash')}</button>
      <button className={btn} onClick={() => void run(setError, () => api(`/api/inventories/${i.id}/reject`, { body: {} }), loadInvs)}>{t('Rad etish')}</button>
    </div>)}
  </section>
}

type FiscalCfg = { tin: string; provider: string; terminalId: string; operator: string; enabled: boolean; mandatory: boolean; hasCredentials: boolean; providers: string[]; certified: boolean }
type Outbox = { id: number; key: string; status: string; attempts: number; lastError: string; sentAt: number | null }

export function IntegrationsPanel() {
  const [cfg, loadCfg, error, setError] = useLoad<FiscalCfg | null>('/api/fiscal/config', null)
  const [tg, loadTg] = useLoad<{ enabled: boolean; chatId: string; hasToken: boolean }>('/api/telegram/config', { enabled: false, chatId: '', hasToken: false })
  const [outbox, loadOutbox] = useLoad<Outbox[]>('/api/telegram/outbox', [])
  const [form, setForm] = useState<FiscalCfg | null>(null)
  const [credentials, setCredentials] = useState('')
  const [chat, setChat] = useState<string | null>(null)
  const [token, setToken] = useState('')
  const f = form ?? cfg
  const saveFiscal = () => f && run(setError, () => api('/api/fiscal/config', { method: 'PUT', body: { tin: f.tin, provider: f.provider, terminalId: f.terminalId, operator: f.operator, enabled: f.enabled, mandatory: f.mandatory, ...(credentials ? { credentials } : {}) } }), async () => { setForm(null); setCredentials(''); await loadCfg() })
  const saveTg = (enabled: boolean) => run(setError, () => api('/api/telegram/config', { method: 'PUT', body: { enabled, chatId: chat ?? tg.chatId, ...(token ? { token } : {}) } }), async () => { setToken(''); setChat(null); await loadTg() })
  return <section className={box}>
    <h2 className="text-xl font-semibold">{t('Fiskal va Telegram')}</h2>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {f && <form className="space-y-2" onSubmit={e => { e.preventDefault(); void saveFiscal() }}>
      {!f.certified && <p className="rounded bg-amber-50 p-2 text-sm text-amber-900">{t('Sertifikatlangan fiskal provayder ulanmagan. Sandbox cheklar fiskal hisoblanmaydi.')}</p>}
      <div className="flex flex-wrap gap-2">
        <input aria-label={t('STIR')} className={input} placeholder={t('STIR')} pattern="\d{9}" required value={f.tin} onChange={e => setForm({ ...f, tin: e.target.value })} />
        <select aria-label={t('Provayder')} className={input} value={f.provider} onChange={e => setForm({ ...f, provider: e.target.value })}><option value="">{t('Provayder')}</option>{f.providers.map(p => <option key={p} value={p}>{p}</option>)}</select>
        <input aria-label={t('Terminal ID')} className={input} placeholder={t('Terminal ID')} required value={f.terminalId} onChange={e => setForm({ ...f, terminalId: e.target.value })} />
        <input aria-label={t('Operator')} className={input} placeholder={t('Operator')} value={f.operator} onChange={e => setForm({ ...f, operator: e.target.value })} />
        <input aria-label={t('Provayder kaliti')} className={input} type="password" autoComplete="off" placeholder={f.hasCredentials ? t('Kalit saqlangan (shifrlangan)') : t('Provayder kaliti')} value={credentials} onChange={e => setCredentials(e.target.value)} />
      </div>
      <label className="mr-4"><input type="checkbox" checked={f.enabled} onChange={e => setForm({ ...f, enabled: e.target.checked })} /> {t('Fiskal yoqilgan')}</label>
      <label><input type="checkbox" checked={f.mandatory} onChange={e => setForm({ ...f, mandatory: e.target.checked })} /> {t('Majburiy: provayder ishlamasa savdo to‘xtaydi')}</label>
      <div><button className={primary}>{t('Saqlash')}</button></div>
    </form>}
    <h3 className="font-semibold">{t('Direktor uchun Telegram hisobot')}</h3>
    <div className="flex flex-wrap gap-2">
      <input aria-label={t('Chat ID')} className={input} placeholder={t('Chat ID')} value={chat ?? tg.chatId} onChange={e => setChat(e.target.value)} />
      <input aria-label={t('Bot token')} className={input} type="password" autoComplete="off" placeholder={tg.hasToken ? t('Token saqlangan (shifrlangan)') : t('Bot token')} value={token} onChange={e => setToken(e.target.value)} />
      <button className={primary} onClick={() => void saveTg(true)}>{t('Yoqish')}</button>
      {tg.enabled && <button className={btn} onClick={() => void saveTg(false)}>{t('O‘chirish')}</button>}
      {tg.enabled && <button className={btn} onClick={() => void run(setError, async () => { await api('/api/telegram/digest', { body: {} }); await api('/api/telegram/dispatch', { body: {} }) }, loadOutbox)}>{t('Bugungi hisobotni yuborish')}</button>}
    </div>
    <ul className="text-sm">{outbox.map(m => <li key={m.id}>{m.key} · {t(m.status === 'sent' ? 'Yuborildi' : m.status === 'failed' ? 'Yuborilmadi' : 'Navbatda')} · {m.attempts}{m.lastError ? ' · ' + m.lastError : ''}</li>)}</ul>
  </section>
}

type DeviceRow = { id: number; name: string; kind: string; branchId: number | null; appVersion: string; lastSeenAt: number | null; revokedAt: number | null }
type Conflict = { id: number; reason: string; staff: string; createdAt: number; expectedTotal: number | null; items: unknown[] }

export function DevicesPanel() {
  const [devices, loadDevices, error, setError] = useLoad<DeviceRow[]>('/api/devices', [])
  const [conflicts, loadConflicts] = useLoad<Conflict[]>('/api/offline/conflicts', [])
  const [branches] = useLoad<{ items: Branch[] }>('/api/branches', { items: [] })
  const [name, setName] = useState('')
  const [kind, setKind] = useState('pos')
  const [branchId, setBranchId] = useState('')
  const [issued, setIssued] = useState('')
  const register = () => run(setError, async () => {
    const d = await api<{ token: string }>('/api/devices', { body: { name, kind, branchId: branchId ? Number(branchId) : null } })
    setIssued(d.token)
  }, async () => { setName(''); await loadDevices() })
  return <section className={box}>
    <h2 className="text-xl font-semibold">{t('Qurilmalar va oflayn')}</h2>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); void register() }}>
      <input className={input} required maxLength={64} placeholder={t('Qurilma nomi')} value={name} onChange={e => setName(e.target.value)} />
      <select aria-label={t('Turi')} className={input} value={kind} onChange={e => setKind(e.target.value)}>{['pos', 'kds', 'apk', 'admin'].map(k => <option key={k} value={k}>{k.toUpperCase()}</option>)}</select>
      <select aria-label={t('Filial')} className={input} value={branchId} onChange={e => setBranchId(e.target.value)}><option value="">{t('Filialga biriktirilmagan')}</option>{branches.items.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
      <button className={primary}>{t('Ro‘yxatdan o‘tkazish')}</button>
    </form>
    {issued && <div className="rounded border border-amber-500 bg-amber-50 p-2 text-sm text-stone-900">{t('Kalit faqat bir marta ko‘rsatiladi')}: <code className="break-all">{issued}</code>
      <button className={'ml-2 ' + btn} onClick={() => { setDeviceToken(issued); setIssued('') }}>{t('Shu qurilmada saqlash')}</button></div>}
    {devices.map(d => <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm">
      <span>{d.name} · {d.kind.toUpperCase()} · {t('Filial')}: {d.branchId ? branches.items.find(b => b.id === d.branchId)?.name ?? '#' + d.branchId : t('Filialga biriktirilmagan')} · {t('Versiya')}: {d.appVersion || '—'} · {t('Oxirgi faollik')}: {when(d.lastSeenAt)}{d.revokedAt ? ' · ' + t('Bloklangan') : ''}</span>
      {!d.revokedAt && <button className={btn} onClick={() => { if (confirm(t('Qurilma bloklansinmi?'))) void run(setError, () => api(`/api/devices/${d.id}/revoke`, { body: {} }), loadDevices) }}>{t('Bloklash')}</button>}
    </div>)}
    <h3 className="font-semibold">{t('Oflayn savdo ziddiyatlari')}</h3>
    {conflicts.length === 0 ? <p className="text-sm text-stone-500">{t('Ziddiyat yo‘q')}</p> : conflicts.map(c => <div key={c.id} className="flex flex-wrap items-center gap-2 text-sm">
      <span>#{c.id} · {c.staff} · {when(c.createdAt)} · {c.reason}{c.expectedTotal != null ? ' · ' + som(c.expectedTotal) : ''}</span>
      <button className={btn} onClick={() => void run(setError, () => api(`/api/offline/conflicts/${c.id}/resolve`, { body: {} }), loadConflicts)}>{t('Ko‘rib chiqildi')}</button>
    </div>)}
  </section>
}

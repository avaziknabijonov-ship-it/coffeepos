import { useEffect, useState } from 'react'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { api } from './api'
import { t } from './i18n'

export type Checklist = { id: number; name: string; kind: 'open' | 'close' | 'any'; items: string[]; active: boolean }
type Run = { id: number; name: string; staff: string; shiftId: number | null; items: { text: string; done: boolean }[]; done: number; total: number; createdAt: number }

const input = 'rounded-lg border border-stone-200 px-2.5 py-2 outline-none focus:border-amber-500'
const btn = 'rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-stone-300'
const KIND_LABEL = { open: 'Smena ochilishi', close: 'Smena yopilishi', any: 'Istalgan vaqt' } as const

/** Cashier / barista: tick a checklist and submit it for the open shift. */
export function ChecklistDialog({ onClose }: { onClose: () => void }) {
  const [lists, setLists] = useState<Checklist[] | null>(null)
  const [current, setCurrent] = useState<Checklist | null>(null)
  const [done, setDone] = useState<boolean[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState('')
  useEffect(() => { api<Checklist[]>('/api/checklists').then((l) => setLists(l.filter((x) => x.active))).catch((e) => setError((e as Error).message)) }, [])
  const pick = (c: Checklist) => { setCurrent(c); setDone(c.items.map(() => false)); setSent('') }
  const submit = async () => {
    if (!current) return
    setBusy(true); setError('')
    try {
      await api(`/api/checklists/${current.id}/runs`, { body: { done } })
      setSent(current.name); setCurrent(null)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 text-stone-900 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold">{current ? current.name : t('Checklistlar')}</h2>
          <button onClick={onClose} aria-label={t('Yopish')}><X className="size-6" /></button>
        </div>
        {error && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        {sent && <p className="mb-3 rounded-lg bg-emerald-50 p-2 text-sm text-emerald-800">{t('Saqlandi')}: {sent}</p>}
        {!current && lists && (lists.length === 0 ? <p className="text-sm text-stone-500">{t('Rahbar hali checklist qo‘shmagan.')}</p> :
          <div className="space-y-2">{lists.map((c) => <button key={c.id} onClick={() => pick(c)}
            className="flex w-full items-center justify-between rounded-xl border border-stone-200 p-3 text-left hover:border-amber-400">
            <span className="font-medium">{c.name}</span><span className="text-xs text-stone-500">{t(KIND_LABEL[c.kind])} · {c.items.length}</span>
          </button>)}</div>)}
        {current && <div className="space-y-2">
          {current.items.map((text, i) => <label key={i} className={`flex items-center gap-3 rounded-xl border p-3 ${done[i] ? 'border-emerald-400 bg-emerald-50' : 'border-stone-200'}`}>
            <input type="checkbox" className="size-5 accent-emerald-600" checked={done[i] ?? false} onChange={(e) => setDone(done.map((d, j) => (j === i ? e.target.checked : d)))} />
            <span>{text}</span>
          </label>)}
          <div className="flex gap-2 pt-2">
            <button disabled={busy} onClick={() => void submit()} className={`${btn} flex flex-1 items-center justify-center gap-2 py-3`}><Check className="size-4" />{t('Yakunlash')} ({done.filter(Boolean).length}/{done.length})</button>
            <button onClick={() => setCurrent(null)} className="rounded-lg border px-3">{t('Orqaga')}</button>
          </div>
        </div>}
      </div>
    </div>
  )
}

type Draft = { id?: number; name: string; kind: Checklist['kind']; items: string; active: boolean }

/** Manager: edit checklist templates and review submitted ones. */
export default function ChecklistsAdmin() {
  const [lists, setLists] = useState<Checklist[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [error, setError] = useState('')
  const load = () => Promise.all([api<Checklist[]>('/api/checklists').then(setLists), api<Run[]>('/api/checklist-runs?days=30').then(setRuns)])
    .catch((e) => setError((e as Error).message))
  useEffect(() => { void load() }, [])
  const save = async () => {
    if (!draft) return
    setError('')
    const body = { name: draft.name.trim(), kind: draft.kind, active: draft.active, items: draft.items.split('\n').map((x) => x.trim()).filter(Boolean) }
    try { await api(draft.id ? `/api/checklists/${draft.id}` : '/api/checklists', { method: draft.id ? 'PUT' : 'POST', body }); setDraft(null); await load() }
    catch (e) { setError((e as Error).message) }
  }
  const remove = async (c: Checklist) => {
    if (!window.confirm(t('Checklist o‘chirilsinmi?') + ' ' + c.name)) return
    try { await api(`/api/checklists/${c.id}`, { method: 'DELETE' }); await load() } catch (e) { setError((e as Error).message) }
  }
  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">{t('Checklistlar')}</h2>
          <button className={`${btn} flex items-center gap-1`} onClick={() => setDraft({ name: '', kind: 'open', items: '', active: true })}><Plus className="size-4" />{t('Yangi checklist')}</button>
        </div>
        <p className="mb-4 text-sm text-stone-600">{t('Xodim kassadagi «Checklist» tugmasi orqali smena ochish/yopishda bajarilgan ishlarni belgilaydi.')}</p>
        {error && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        {lists.length === 0 ? <p className="rounded-xl bg-stone-50 p-4 text-sm text-stone-500">{t('Hali checklist yo‘q.')}</p> :
          <div className="divide-y divide-stone-100 rounded-xl border border-stone-200">{lists.map((c) => <div key={c.id} className="flex items-center gap-3 px-3 py-2.5">
            <div className={`flex-1 ${c.active ? '' : 'opacity-50'}`}><div className="font-medium">{c.name}</div><div className="text-xs text-stone-500">{t(KIND_LABEL[c.kind])} · {c.items.length} {t('band')}</div></div>
            <button aria-label={t('Tahrirlash')} className="rounded-lg p-2 hover:bg-stone-100" onClick={() => setDraft({ id: c.id, name: c.name, kind: c.kind, items: c.items.join('\n'), active: c.active })}><Pencil className="size-4" /></button>
            <button aria-label={t("O'chirish")} className="rounded-lg p-2 text-stone-400 hover:text-red-600" onClick={() => void remove(c)}><Trash2 className="size-4" /></button>
          </div>)}</div>}
        {draft && <div className="mt-5 space-y-3 rounded-xl border border-amber-300 bg-amber-50/40 p-4 text-sm">
          <div className="flex flex-wrap gap-2">
            <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder={t('Nomi')} className={`${input} min-w-48 flex-1`} />
            <select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as Checklist['kind'] })} className={input}>
              {(Object.keys(KIND_LABEL) as Checklist['kind'][]).map((k) => <option key={k} value={k}>{t(KIND_LABEL[k])}</option>)}
            </select>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={draft.active} onChange={(e) => setDraft({ ...draft, active: e.target.checked })} />{t('Faol')}</label>
          </div>
          <textarea value={draft.items} onChange={(e) => setDraft({ ...draft, items: e.target.value })} rows={7} placeholder={t('Har bir band alohida qatorda, masalan:\nKofemashinani yoqish\nSut muddatini tekshirish\nKassada mayda pul')} className={`${input} w-full`} />
          <div className="flex gap-2">
            <button disabled={!draft.name.trim() || !draft.items.trim()} onClick={() => void save()} className={btn}>{t('Saqlash')}</button>
            <button onClick={() => setDraft(null)} className="rounded-lg border px-3 py-2">{t('Bekor qilish')}</button>
          </div>
        </div>}
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
        <h2 className="mb-3 font-semibold">{t('Oxirgi 30 kun')}</h2>
        {runs.length === 0 ? <p className="text-sm text-stone-500">{t('Hali to‘ldirilmagan.')}</p> :
          <div className="divide-y divide-stone-100 text-sm">{runs.map((r) => <div key={r.id} className="py-2">
            <button className="flex w-full flex-wrap items-center gap-3 text-left" onClick={() => setOpen(open === r.id ? null : r.id)}>
              <span className="w-36 text-stone-500">{new Date(r.createdAt).toLocaleString()}</span>
              <span className="flex-1 font-medium">{r.name}</span><span>{r.staff}</span>
              <span className={`rounded px-2 py-0.5 text-xs font-bold ${r.done === r.total ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>{r.done}/{r.total}</span>
            </button>
            {open === r.id && <ul className="mt-2 space-y-1 pl-4">{r.items.map((it, i) => <li key={i} className={it.done ? 'text-emerald-700' : 'text-red-700'}>{it.done ? '✓' : '✗'} {it.text}</li>)}</ul>}
          </div>)}</div>}
      </section>
    </div>
  )
}

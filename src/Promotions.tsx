import { useEffect, useState } from 'react'
import { api } from './api'
import { t } from './i18n'

type Rule = { id: number; name: string; startTime: string; endTime: string; weekdays: number[]; percent: number; priority: number; active: boolean }
const days = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']
export default function Promotions() {
  const [rules, setRules] = useState<Rule[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState<Omit<Rule, 'id'>>({ name: '', startTime: '14:00', endTime: '17:00', weekdays: [0, 1, 2, 3, 4], percent: 10, priority: 0, active: true })
  useEffect(() => { let active = true; api<Rule[]>('/api/promotions').then(r => { if (active) setRules(r) }).catch(e => { if (active) setError(e.message) }); return () => { active = false } }, [])
  const save = async (rule?: Rule) => {
    setBusy(true); setError('')
    try {
      await api('/api/promotions' + (rule ? '/' + rule.id : ''), { method: rule ? 'PUT' : 'POST', body: rule ? { ...rule, active: !rule.active } : draft })
      setRules(await api<Rule[]>('/api/promotions'))
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <h2 className="text-xl font-semibold">{t('Happy Hour')}</h2>
    <p className="text-sm text-stone-600">{t('Server mahalliy vaqti qo‘llanadi. Ustuvorlik kattasi tanlanadi; teng bo‘lsa oldin yaratilgan aksiya. Chegirmalar qo‘shilmaydi.')}</p>
    <p className="text-sm text-stone-600">{t('Yarim tundan o‘tgan jadvalda hafta kuni aksiya boshlangan kunni bildiradi. Aksiya paytida offline savdo cheklangan.')}</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <form className="flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void save() }}>
      <label>{t('Nomi')}<input required maxLength={64} className="block rounded border p-2" value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
      <label>{t('Boshlanish')}<input required type="time" className="block rounded border p-2" value={draft.startTime} onChange={e => setDraft({ ...draft, startTime: e.target.value })} /></label>
      <label>{t('Tugash')}<input required type="time" className="block rounded border p-2" value={draft.endTime} onChange={e => setDraft({ ...draft, endTime: e.target.value })} /></label>
      <label>{t('Chegirma')} %<input required type="number" min="1" max="50" className="block w-24 rounded border p-2" value={draft.percent} onChange={e => setDraft({ ...draft, percent: Number(e.target.value) })} /></label>
      <label>{t('Ustuvorlik')}<input required type="number" min="0" max="100" className="block w-24 rounded border p-2" value={draft.priority} onChange={e => setDraft({ ...draft, priority: Number(e.target.value) })} /></label>
      <fieldset className="flex flex-wrap gap-2"><legend>{t('Hafta kunlari')}</legend>{days.map((day, index) => <label key={day}><input type="checkbox" checked={draft.weekdays.includes(index)} onChange={e => setDraft({ ...draft, weekdays: e.target.checked ? [...draft.weekdays, index] : draft.weekdays.filter(d => d !== index) })} /> {t(day)}</label>)}</fieldset>
      <button disabled={busy} className="rounded bg-stone-800 px-3 py-2 text-white">{t('Saqlash')}</button>
    </form>
    {rules.map(rule => <div key={rule.id} className="flex flex-wrap items-center justify-between gap-3 rounded border p-3">
      <span>{rule.name} · {rule.startTime}–{rule.endTime} · {rule.percent}% · {rule.weekdays.map(d => t(days[d])).join(', ')} · {t('Ustuvorlik')}: {rule.priority}</span>
      <button disabled={busy} className="rounded border px-3 py-2" onClick={() => void save(rule)}>{rule.active ? t('Faol') : t('Nofaol')}</button>
    </div>)}
  </section>
}

import { useEffect, useState } from 'react'
import { t } from './i18n'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { ING, INGREDIENTS, UNIT_LABEL, fmt, som, time } from './data'
import type { Unit } from './data'
import { api } from './api'
import { refreshMenu, stockMove, sync, useAppState } from './store'

type Tab = 'count' | 'writeoff' | 'history' | 'report'
const TABS: { id: Tab; label: string }[] = [
  { id: 'count', label: 'Sanash' },
  { id: 'writeoff', label: 'Hisobdan chiqarish' },
  { id: 'history', label: 'Tarix' },
  { id: 'report', label: 'Kamomad hisoboti' },
]
const WRITEOFF_LABEL: Record<string, string> = {
  spill: "To'kildi / isrof", expired: "Muddati o'tdi", staff: 'Xodim ichdi', broken: 'Buzildi / sindi', other: 'Boshqa',
}

interface InvLine { ing: string; name: string; unit: Unit; expected: number; counted: number; diff: number; value: number }
interface Inv { id: number; staff: string; note: string; lines: InvLine[]; shortage: number; surplus: number; createdAt: number }
interface Move { id: number; ing: string; qty: number; reason: string; note: string | null; staff: string; createdAt: number }
interface Losses {
  writeoffTotal: number; byNote: Record<string, number>; inventories: number; shortage: number; surplus: number
  items: { ing: string; name: string; unit: Unit; writeoffQty: number; writeoffValue: number; countQty: number; countValue: number }[]
}

const input = 'rounded-lg border border-stone-200 px-2.5 py-2 outline-none focus:border-amber-500'
const btn = 'rounded-lg bg-stone-900 px-4 py-2 text-sm font-semibold text-white disabled:bg-stone-300'
const date = (t: number) => `${new Date(t).toLocaleDateString('ru-RU')} ${time(t)}`
const qty = (n: number) => (Number.isInteger(n) ? fmt(n) : n.toFixed(1))
const signed = (n: number) => (n > 0 ? `+${qty(n)}` : qty(n))
const tone = (n: number) => (n < 0 ? 'text-red-600' : n > 0 ? 'text-emerald-700' : 'text-stone-400')

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <h2 className="font-semibold">{title}</h2>
      {hint && <p className="mt-1 text-sm text-stone-500">{hint}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

function Stat({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="rounded-xl bg-stone-100 px-4 py-3">
      <div className="text-xs text-stone-500">{label}</div>
      <div className={`mt-0.5 text-lg font-bold tabular-nums ${className}`}>{value}</div>
    </div>
  )
}

export function InventoryView() {
  const [tab, setTab] = useState<Tab>('count')
  return (
    <div className="space-y-4">
      <div className="flex gap-2 overflow-x-auto">
        {TABS.map((x) => (
          <button key={x.id} onClick={() => setTab(x.id)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium ${tab === x.id ? 'bg-stone-900 text-white' : 'border border-stone-200 bg-white text-stone-700'}`}>{t(x.label)}</button>
        ))}
      </div>
      {tab === 'count' && <CountForm onSaved={() => setTab('history')} />}
      {tab === 'writeoff' && <WriteOff />}
      {tab === 'history' && <History />}
      {tab === 'report' && <Report />}
    </div>
  )
}

function CountForm({ onSaved }: { onSaved: () => void }) {
  const { stock } = useAppState()
  const [counts, setCounts] = useState<Record<string, string>>({})
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const lines = INGREDIENTS.filter((i) => counts[i.id] !== undefined && counts[i.id] !== '').map((i) => {
    const counted = Number(counts[i.id])
    const diff = counted - (stock[i.id] ?? 0)
    return { ing: i.id, counted, diff, value: diff * i.cost }
  })
  const shortage = lines.reduce((s, l) => s + (l.value < 0 ? -l.value : 0), 0)
  const surplus = lines.reduce((s, l) => s + (l.value > 0 ? l.value : 0), 0)
  const fillRest = () => setCounts((c) => Object.fromEntries(INGREDIENTS.map((i) => [i.id, c[i.id] || String(stock[i.id] ?? 0)])))

  const save = async () => {
    if (!confirm(t("{n} ta xomashyo qoldig'i sanalgan miqdorga to'g'rilanadi. Davom etamizmi?", { n: lines.length }))) return
    setBusy(true)
    try {
      await api('/api/inventories', { body: { lines: lines.map(({ ing, counted }) => ({ ing, counted })), note } })
      await Promise.all([sync(), refreshMenu()])
      setCounts({}); setNote('')
      onSaved()
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title={t('Inventarizatsiya: sanash')} hint={t("Har bir xomashyoning haqiqiy qoldig'ini sanab yozing. Bo'sh qolgan qatorlar o'zgarmaydi.")}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-stone-500">
            <tr><th className="pb-2 font-medium">{t('Xomashyo')}</th><th className="pb-2 text-right font-medium">{t('Dasturda')}</th><th className="pb-2 pl-4 font-medium">{t('Sanaldi')}</th><th className="pb-2 text-right font-medium">{t('Farq')}</th><th className="pb-2 text-right font-medium">{t('Summa')}</th></tr>
          </thead>
          <tbody>
            {INGREDIENTS.map((i) => {
              const expected = stock[i.id] ?? 0
              const filled = counts[i.id] !== undefined && counts[i.id] !== ''
              const diff = filled ? Number(counts[i.id]) - expected : 0
              return (
                <tr key={i.id} className="border-t border-stone-100">
                  <td className="py-2">{i.name}</td>
                  <td className="py-2 text-right tabular-nums text-stone-500">{qty(expected)} {t(UNIT_LABEL[i.unit])}</td>
                  <td className="py-2 pl-4">
                    <input inputMode="decimal" aria-label={`${i.name} sanaldi`} value={counts[i.id] ?? ''} placeholder={t(UNIT_LABEL[i.unit])}
                      onChange={(e) => setCounts((c) => ({ ...c, [i.id]: e.target.value.replace(',', '.').replace(/[^\d.]/g, '') }))}
                      className="w-28 rounded-lg border border-stone-200 px-2 py-1.5 outline-none focus:border-amber-500" />
                  </td>
                  <td className={`py-2 text-right font-medium tabular-nums ${tone(diff)}`}>{filled ? `${signed(diff)} ${t(UNIT_LABEL[i.unit])}` : '—'}</td>
                  <td className={`py-2 text-right tabular-nums ${tone(diff)}`}>{filled && diff ? som(diff * i.cost) : '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Stat label={t('Sanalgan xomashyo')} value={`${lines.length} / ${INGREDIENTS.length}`} />
        <Stat label={t('Kamomad')} value={som(shortage)} className={shortage ? 'text-red-600' : ''} />
        <Stat label={t('Ortiqcha')} value={som(surplus)} className={surplus ? 'text-emerald-700' : ''} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder={t('Izoh (masalan: oy oxiri)')} className={`${input} min-w-0 flex-1`} />
        <button onClick={fillRest} className="rounded-lg border border-stone-200 px-3 py-2 text-sm font-medium">{t("Qolganini dasturdagidek to'ldirish")}</button>
        <button disabled={!lines.length || busy} onClick={save} className={btn}>{t('Saqlash')}</button>
      </div>
    </Section>
  )
}

function WriteOff() {
  const { stock } = useAppState()
  const [ing, setIng] = useState(INGREDIENTS[0]?.id ?? '')
  const [amount, setAmount] = useState('')
  const [note, setNote] = useState('spill')
  const [moves, setMoves] = useState<Move[]>([])
  const load = () => api<Move[]>('/api/stock/moves?days=30').then((m) => setMoves(m.filter((x) => x.reason === 'writeoff'))).catch(() => setMoves([]))
  useEffect(() => { load() }, [])
  const i = ING[ing]
  const n = Number(amount) || 0

  const submit = async () => {
    try {
      await stockMove(ing, n, 'writeoff', note)
      setAmount('')
      load()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  return (
    <div className="space-y-4">
      <Section title={t('Hisobdan chiqarish')} hint={t("To'kilgan, buzilgan yoki muddati o'tgan xomashyoni sababi bilan yozing.")}>
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label={t('Xomashyo')} value={ing} onChange={(e) => setIng(e.target.value)} className={`${input} min-w-0 flex-1`}>
            {INGREDIENTS.map((x) => <option key={x.id} value={x.id}>{x.name} ({qty(stock[x.id] ?? 0)} {t(UNIT_LABEL[x.unit])})</option>)}
          </select>
          <input aria-label={t('Miqdor')} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(',', '.').replace(/[^\d.]/g, ''))}
            placeholder={i ? t(UNIT_LABEL[i.unit]) : ''} className={`${input} w-28`} />
          <select aria-label={t('Sabab')} value={note} onChange={(e) => setNote(e.target.value)} className={input}>
            {Object.entries(WRITEOFF_LABEL).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
          </select>
          <button disabled={!n} onClick={submit} className={btn}>{t('Chiqarish')}</button>
        </div>
        {i && n > 0 && <p className="mt-2 text-sm text-stone-500">{t('Zarar')}: <b className="text-red-600">{som(n * i.cost)}</b></p>}
      </Section>
      <Section title={t('Oxirgi 30 kun')}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="text-left text-stone-500"><tr><th className="pb-2 font-medium">{t('Sana')}</th><th className="pb-2 font-medium">{t('Xomashyo')}</th><th className="pb-2 text-right font-medium">{t('Miqdor')}</th><th className="pb-2 pl-4 font-medium">{t('Sabab')}</th><th className="pb-2 font-medium">{t('Kim')}</th><th className="pb-2 text-right font-medium">{t('Summa')}</th></tr></thead>
            <tbody>
              {moves.map((m) => {
                const x = ING[m.ing]
                return (
                  <tr key={m.id} className="border-t border-stone-100">
                    <td className="py-2 text-stone-500">{date(m.createdAt)}</td>
                    <td className="py-2">{x?.name ?? m.ing}</td>
                    <td className="py-2 text-right tabular-nums">{qty(-m.qty)} {x ? t(UNIT_LABEL[x.unit]) : ''}</td>
                    <td className="py-2 pl-4">{t(WRITEOFF_LABEL[m.note ?? 'other']) ?? m.note}</td>
                    <td className="py-2 text-stone-500">{m.staff}</td>
                    <td className="py-2 text-right tabular-nums text-red-600">{x ? som(-m.qty * x.cost) : '—'}</td>
                  </tr>
                )
              })}
              {moves.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-stone-500">{t("Hisobdan chiqarish yo'q.")}</td></tr>}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  )
}

function History() {
  const [list, setList] = useState<Inv[] | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  useEffect(() => { api<Inv[]>('/api/inventories?days=365').then(setList).catch((e: Error) => { alert(e.message); setList([]) }) }, [])
  return (
    <Section title={t('Inventarizatsiyalar tarixi')}>
      {list === null && <p className="text-stone-500">{t('Yuklanmoqda…')}</p>}
      {list?.length === 0 && <p className="py-4 text-center text-stone-500">{t("Hali inventarizatsiya o'tkazilmagan.")}</p>}
      <div className="divide-y divide-stone-100">
        {list?.map((inv) => {
          const changed = inv.lines.filter((l) => l.diff !== 0)
          const isOpen = open === inv.id
          return (
            <div key={inv.id} className="py-2">
              <button onClick={() => setOpen(isOpen ? null : inv.id)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 py-1 text-left text-sm">
                {isOpen ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                <span className="font-medium">#{inv.id} · {date(inv.createdAt)}</span>
                <span className="text-stone-500">{inv.staff}{inv.note && ` · ${inv.note}`}</span>
                <span className="text-stone-500">{t('{n} ta sanaldi, {m} tasida farq', { n: inv.lines.length, m: changed.length })}</span>
                <span className="ml-auto flex gap-3 tabular-nums">
                  <span className={inv.shortage ? 'text-red-600' : 'text-stone-400'}>−{fmt(inv.shortage)}</span>
                  <span className={inv.surplus ? 'text-emerald-700' : 'text-stone-400'}>+{fmt(inv.surplus)}</span>
                </span>
              </button>
              {isOpen && (
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full min-w-[560px] text-sm">
                    <thead className="text-left text-stone-500"><tr><th className="pb-1 font-medium">{t('Xomashyo')}</th><th className="pb-1 text-right font-medium">{t('Dasturda')}</th><th className="pb-1 text-right font-medium">{t('Sanaldi')}</th><th className="pb-1 text-right font-medium">{t('Farq')}</th><th className="pb-1 text-right font-medium">{t('Summa')}</th></tr></thead>
                    <tbody>
                      {inv.lines.map((l) => (
                        <tr key={l.ing} className="border-t border-stone-100">
                          <td className="py-1.5">{l.name}</td>
                          <td className="py-1.5 text-right tabular-nums text-stone-500">{qty(l.expected)} {t(UNIT_LABEL[l.unit])}</td>
                          <td className="py-1.5 text-right tabular-nums">{qty(l.counted)} {t(UNIT_LABEL[l.unit])}</td>
                          <td className={`py-1.5 text-right font-medium tabular-nums ${tone(l.diff)}`}>{signed(l.diff)}</td>
                          <td className={`py-1.5 text-right tabular-nums ${tone(l.value)}`}>{l.value ? som(l.value) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Section>
  )
}

function Report() {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<Losses | null>(null)
  useEffect(() => { api<Losses>(`/api/reports/losses?days=${days}`).then(setData).catch((e: Error) => alert(e.message)) }, [days])
  const notes = Object.entries(data?.byNote ?? {}).sort((a, b) => b[1] - a[1])
  const maxNote = Math.max(1, ...notes.map((n) => n[1]))
  const net = data ? data.writeoffTotal + data.shortage - data.surplus : 0

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {[7, 30, 90].map((d) => (
          <button key={d} onClick={() => setDays(d)} className={`rounded-full px-3 py-1.5 text-sm font-medium ${days === d ? 'bg-amber-600 text-white' : 'border border-stone-200 bg-white text-stone-700'}`}>{t('{n} kun', { n: d })}</button>
        ))}
      </div>
      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label={t('Hisobdan chiqarildi')} value={som(data.writeoffTotal)} className={data.writeoffTotal ? 'text-red-600' : ''} />
            <Stat label={t('Kamomad ({n} ta inventarizatsiya)', { n: data.inventories })} value={som(data.shortage)} className={data.shortage ? 'text-red-600' : ''} />
            <Stat label={t('Ortiqcha')} value={som(data.surplus)} className={data.surplus ? 'text-emerald-700' : ''} />
            <Stat label={t("Jami yo'qotish")} value={som(net)} className={net > 0 ? 'text-red-600' : ''} />
          </div>
          <Section title={t('Hisobdan chiqarish sabablari')}>
            {notes.length === 0 && <p className="text-stone-500">{t("Bu davrda hisobdan chiqarish yo'q.")}</p>}
            <div className="space-y-2">
              {notes.map(([k, v]) => (
                <div key={k} className="flex items-center gap-3 text-sm">
                  <span className="w-28 shrink-0 sm:w-36">{t(WRITEOFF_LABEL[k]) ?? k}</span>
                  <div className="h-3 flex-1 rounded-full bg-stone-100"><div className="h-3 rounded-full bg-red-400" style={{ width: `${(v / maxNote) * 100}%` }} /></div>
                  <span className="w-24 shrink-0 text-right tabular-nums sm:w-28">{som(v)}</span>
                </div>
              ))}
            </div>
          </Section>
          <Section title={t("Xomashyo bo'yicha")} hint={t("Sanashdagi farq: manfiy bo'lsa kamomad, musbat bo'lsa ortiqcha.")}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-sm">
                <thead className="text-left text-stone-500"><tr><th className="pb-2 font-medium">{t('Xomashyo')}</th><th className="pb-2 text-right font-medium">{t('Chiqarildi')}</th><th className="pb-2 text-right font-medium">{t('Summa')}</th><th className="pb-2 text-right font-medium">{t('Sanashdagi farq')}</th><th className="pb-2 text-right font-medium">{t('Summa')}</th></tr></thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.ing} className="border-t border-stone-100">
                      <td className="py-2">{r.name}</td>
                      <td className="py-2 text-right tabular-nums">{r.writeoffQty ? `${qty(r.writeoffQty)} ${t(UNIT_LABEL[r.unit]) ?? ''}` : '—'}</td>
                      <td className="py-2 text-right tabular-nums text-red-600">{r.writeoffValue ? som(r.writeoffValue) : '—'}</td>
                      <td className={`py-2 text-right tabular-nums ${tone(r.countQty)}`}>{r.countQty ? `${signed(r.countQty)} ${t(UNIT_LABEL[r.unit]) ?? ''}` : '—'}</td>
                      <td className={`py-2 text-right tabular-nums ${tone(r.countValue)}`}>{r.countValue ? som(r.countValue) : '—'}</td>
                    </tr>
                  ))}
                  {data.items.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-stone-500">{t("Ma'lumot yo'q.")}</td></tr>}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}
    </div>
  )
}

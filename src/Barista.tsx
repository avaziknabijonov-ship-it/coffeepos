import { useState } from 'react'
import { Clock } from 'lucide-react'
import { STATUS_LABEL } from './data'
import type { Order, Status } from './data'
import { setStatus, useAppState } from './store'
import { useNow } from './useNow'

const COLUMNS: { status: Status; next: Status; action: string; tone: string }[] = [
  { status: 'new', next: 'preparing', action: 'Boshlash', tone: 'bg-amber-600 hover:bg-amber-700' },
  { status: 'preparing', next: 'ready', action: 'Tayyor', tone: 'bg-emerald-600 hover:bg-emerald-700' },
  { status: 'ready', next: 'done', action: 'Berildi', tone: 'bg-stone-800 hover:bg-stone-900' },
]

const elapsed = (ms: number) => {
  const s = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function Barista() {
  const { orders } = useAppState()
  const now = useNow()
  const [mobileCol, setMobileCol] = useState<Status>('new')
  const byStatus = (s: Status) => orders.filter((o) => o.status === s).sort((a, b) => a.createdAt - b.createdAt)

  return (
    <div className="flex h-full flex-col">
      <div className="flex gap-1 border-b border-stone-200 bg-white p-2 md:hidden">
        {COLUMNS.map((c) => (
          <button key={c.status} onClick={() => setMobileCol(c.status)}
            className={`flex-1 rounded-lg py-2 text-sm font-medium ${mobileCol === c.status ? 'bg-stone-900 text-white' : 'text-stone-600'}`}>
            {STATUS_LABEL[c.status]} ({byStatus(c.status).length})
          </button>
        ))}
      </div>
      <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto p-3 md:grid-cols-3 md:overflow-hidden md:p-4">
        {COLUMNS.map((c) => {
          const list = byStatus(c.status)
          return (
            <section key={c.status} className={`min-h-0 flex-col rounded-2xl bg-stone-100 ${mobileCol === c.status ? 'flex' : 'hidden md:flex'}`}>
              <h2 className="hidden items-center justify-between px-4 py-3 font-semibold md:flex">
                {STATUS_LABEL[c.status]}<span className="rounded-full bg-white px-2.5 py-0.5 text-sm">{list.length}</span>
              </h2>
              <div className="space-y-3 overflow-y-auto p-3 md:pt-0">
                {list.length === 0 && <p className="py-10 text-center text-sm text-stone-400">Buyurtma yo'q</p>}
                {list.map((o) => <Ticket key={o.id} order={o} now={now} action={c.action} tone={c.tone} onAction={() => setStatus(o.id, c.next)} />)}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}

function Ticket({ order, now, action, tone, onAction }: { order: Order; now: number; action: string; tone: string; onAction: () => void }) {
  const waited = (order.status === 'ready' && order.readyAt ? order.readyAt : now) - order.createdAt
  const mins = waited / 60000
  const badge = order.status === 'ready' ? 'bg-stone-200 text-stone-700' : mins >= 8 ? 'bg-red-100 text-red-700' : mins >= 5 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
  return (
    <article className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-2xl font-bold">#{order.number}</div>
          {order.customer && <div className="text-lg font-semibold text-amber-700">{order.customer}</div>}
        </div>
        <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums ${badge}`}><Clock className="size-3.5" />{elapsed(waited)}</span>
      </div>
      <ul className="my-3 space-y-1.5">
        {order.items.map((it) => (
          <li key={it.key}>
            <span className="font-semibold">{it.qty}× {it.name}</span>{it.size && <span className="ml-1 rounded bg-stone-100 px-1.5 text-sm font-semibold">{it.size}</span>}
            {it.mods.length > 0 && <div className="text-sm text-stone-600">{it.mods.join(' · ')}</div>}
          </li>
        ))}
      </ul>
      <button onClick={onAction} className={`w-full rounded-xl py-3 font-bold text-white ${tone}`}>{action}</button>
    </article>
  )
}

import { useState } from 'react'
import { t, tCatalogName } from './i18n'
import { Clock } from 'lucide-react'
import { CATEGORIES, PRODUCTS, STATUS_LABEL, WORKSHOPS } from './data'
import type { KitchenTicket, Order, Status } from './data'
import { setStatus, setTicketStatus, useAppState } from './store'
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

const WS_KEY = 'coffeepos-workshop'
const ALL = '*'

/** Workshop of a product through its category; "" is the default (bar) screen. */
function workshopOf(productId: string): string {
  const cat = PRODUCTS.find((p) => p.id === productId)?.cat
  return CATEGORIES.find((c) => c.id === cat)?.workshop ?? ''
}

export default function Barista() {
  const { orders, tickets } = useAppState()
  const now = useNow()
  const [mobileCol, setMobileCol] = useState<Status>('new')
  const [ws, setWs] = useState(() => localStorage.getItem(WS_KEY) ?? ALL)
  const pickWs = (v: string) => { setWs(v); try { localStorage.setItem(WS_KEY, v) } catch { /* optional */ } }
  const visible = (o: Order): Order | null => {
    if (ws === ALL) return o
    const items = o.items.filter((i) => workshopOf(i.productId) === ws)
    return items.length ? { ...o, items } : null
  }
  const byStatus = (s: Status) => orders.filter((o) => o.status === s && !o.pendingSync).map(visible)
    .filter((o): o is Order => o !== null).sort((a, b) => a.createdAt - b.createdAt)
  const ticketsBy = (s: Status) => tickets.filter((x) => x.status === s && (ws === ALL || x.workshop === ws)).sort((a, b) => a.createdAt - b.createdAt)

  return (
    <div className="flex h-full flex-col">
      {WORKSHOPS.length > 0 && <div className="flex gap-1 overflow-x-auto border-b border-stone-200 bg-white p-2">
        {[{ id: ALL, name: t('Hammasi') }, { id: '', name: t('Bar (asosiy)') }, ...WORKSHOPS].map((w) => <button key={w.id || '_'} onClick={() => pickWs(w.id)}
          className={`shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium ${ws === w.id ? 'bg-amber-600 text-white' : 'bg-stone-100 text-stone-700'}`}>{w.name}</button>)}
      </div>}
      <div className="flex gap-1 border-b border-stone-200 bg-white p-2 md:hidden">
        {COLUMNS.map((c) => (
          <button key={c.status} onClick={() => setMobileCol(c.status)}
            className={`flex-1 rounded-lg py-2 text-sm font-medium ${mobileCol === c.status ? 'bg-stone-900 text-white' : 'text-stone-600'}`}>
            {t(STATUS_LABEL[c.status])} ({byStatus(c.status).length + ticketsBy(c.status).length})
          </button>
        ))}
      </div>
      <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto p-3 md:grid-cols-3 md:overflow-hidden md:p-4">
        {COLUMNS.map((c) => {
          const list = byStatus(c.status)
          const tlist = ticketsBy(c.status)
          return (
            <section key={c.status} className={`min-h-0 flex-col rounded-2xl bg-stone-100 ${mobileCol === c.status ? 'flex' : 'hidden md:flex'}`}>
              <h2 className="hidden items-center justify-between px-4 py-3 font-semibold md:flex">
                {t(STATUS_LABEL[c.status])}<span className="rounded-full bg-white px-2.5 py-0.5 text-sm">{list.length + tlist.length}</span>
              </h2>
              <div className="space-y-3 overflow-y-auto p-3 md:pt-0">
                {tlist.map((x) => <TicketCard key={'t' + x.id} ticket={x} now={now} action={c.action} tone={c.tone} onAction={() => setTicketStatus(x.id, c.next as KitchenTicket['status'])} />)}
                {list.length === 0 && tlist.length === 0 && <p className="py-10 text-center text-sm text-stone-400">{t("Buyurtma yo'q")}</p>}
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
            <span className="font-semibold">{it.qty}× {tCatalogName(it.name)}</span>{it.size && <span className="ml-1 rounded bg-stone-100 px-1.5 text-sm font-semibold">{it.size}</span>}
            {it.mods.length > 0 && <div className="text-sm text-stone-600">{it.mods.join(' · ')}</div>}
          </li>
        ))}
      </ul>
      <button onClick={onAction} className={`w-full rounded-xl py-3 font-bold text-white ${tone}`}>{t(action)}</button>
    </article>
  )
}

function TicketCard({ ticket, now, action, tone, onAction }: { ticket: KitchenTicket; now: number; action: string; tone: string; onAction: () => void }) {
  const waited = (ticket.status === 'ready' && ticket.readyAt ? ticket.readyAt : now) - ticket.createdAt
  const mins = waited / 60000
  const badge = ticket.status === 'ready' ? 'bg-stone-200 text-stone-700' : mins >= 15 ? 'bg-red-100 text-red-700' : mins >= 8 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
  return (
    <article className="rounded-xl border-2 border-sky-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xl font-bold">{ticket.tableName || t('Stolsiz hisob')}</div>
          <div className="text-sm text-stone-500">{ticket.waiter} · #{ticket.checkId}</div>
        </div>
        <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums ${badge}`}><Clock className="size-3.5" />{elapsed(waited)}</span>
      </div>
      <ul className="my-3 space-y-1.5">
        {ticket.items.map((it, i) => (
          <li key={i}>
            <span className="font-semibold">{it.qty}× {tCatalogName(it.name)}</span>{it.size && <span className="ml-1 rounded bg-stone-100 px-1.5 text-sm font-semibold">{it.size}</span>}
            {it.mods.length > 0 && <div className="text-sm text-stone-600">{it.mods.join(' · ')}</div>}
          </li>
        ))}
      </ul>
      {ticket.comment && <p className="mb-3 rounded-lg bg-amber-50 p-2 text-sm text-amber-900">{ticket.comment}</p>}
      <button onClick={onAction} className={`w-full rounded-xl py-3 font-bold text-white ${tone}`}>{t(action)}</button>
    </article>
  )
}

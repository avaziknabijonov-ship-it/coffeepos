import { useAppState } from './store'

export default function Display() {
  const { orders } = useAppState()
  const preparing = orders.filter((o) => o.status === 'new' || o.status === 'preparing').sort((a, b) => a.createdAt - b.createdAt)
  const ready = orders.filter((o) => o.status === 'ready').sort((a, b) => (b.readyAt ?? 0) - (a.readyAt ?? 0))
  const label = (o: { number: number; customer: string }) => (o.customer ? `${o.customer}` : `#${o.number}`)

  return (
    <div className="grid h-full grid-rows-2 bg-stone-950 text-white md:grid-cols-2 md:grid-rows-1">
      <section className="flex min-h-0 flex-col border-b border-white/10 p-6 md:border-b-0 md:border-r md:p-10">
        <h2 className="mb-6 text-lg font-semibold uppercase tracking-widest text-stone-400 md:text-2xl">Tayyorlanmoqda</h2>
        <ul className="grid content-start gap-3 overflow-y-auto sm:grid-cols-2">
          {preparing.map((o) => (
            <li key={o.id} className="text-2xl font-semibold text-stone-300 md:text-4xl">{label(o)} <span className="text-base text-stone-500 md:text-xl">#{o.number}</span></li>
          ))}
          {preparing.length === 0 && <li className="text-stone-500">—</li>}
        </ul>
      </section>
      <section className="flex min-h-0 flex-col p-6 md:p-10">
        <h2 className="mb-6 text-lg font-semibold uppercase tracking-widest text-amber-400 md:text-2xl">Tayyor — olib keting</h2>
        <ul className="grid content-start gap-4 overflow-y-auto">
          {ready.map((o, i) => (
            <li key={o.id} className={`rounded-2xl px-5 py-4 font-bold ${i === 0 ? 'bg-amber-500 text-stone-950 text-4xl md:text-6xl' : 'bg-white/10 text-3xl md:text-5xl'}`}>
              {label(o)} <span className="text-xl font-semibold opacity-70 md:text-3xl">#{o.number}</span>
            </li>
          ))}
          {ready.length === 0 && <li className="text-stone-500">—</li>}
        </ul>
      </section>
    </div>
  )
}

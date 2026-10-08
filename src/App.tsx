import { useEffect, useState } from 'react'
import { ChefHat, Coffee, LayoutDashboard, Monitor, Store } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import Kassa from './Kassa'
import Barista from './Barista'
import Display from './Display'
import Admin from './Admin'
import { BARISTA, useAppState } from './store'

type Tab = 'kassa' | 'barista' | 'display' | 'admin'
const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: 'kassa', label: 'Kassa', icon: Store },
  { id: 'barista', label: 'Barista', icon: ChefHat },
  { id: 'display', label: 'Mijoz ekrani', icon: Monitor },
  { id: 'admin', label: 'Admin', icon: LayoutDashboard },
]
const fromHash = (): Tab => {
  const h = window.location.hash.slice(1)
  return TABS.some((t) => t.id === h) ? (h as Tab) : 'kassa'
}

export default function App() {
  const [tab, setTab] = useState<Tab>(fromHash)
  const { orders } = useAppState()
  const waiting = orders.filter((o) => o.status === 'new').length

  useEffect(() => {
    const onHash = () => setTab(fromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex shrink-0 items-center gap-2 bg-stone-900 px-3 py-2 text-white sm:gap-4 sm:px-4">
        <div className="flex items-center gap-2 font-semibold">
          <span className="grid size-8 place-items-center rounded-lg bg-amber-600"><Coffee className="size-5" /></span>
          <span className="hidden sm:inline">CoffeePOS</span>
          <span className="hidden rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300 lg:inline">demo</span>
        </div>
        <nav className="flex flex-1 justify-center gap-1 sm:justify-start">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { window.location.hash = id }}
              className={`relative flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[11px] font-medium sm:flex-row sm:gap-2 sm:text-sm ${tab === id ? 'bg-white text-stone-900' : 'text-stone-300 hover:bg-white/10'}`}
            >
              <Icon className="size-5 sm:size-4" />
              {label}
              {id === 'barista' && waiting > 0 && (
                <span className="absolute -right-1 -top-1 grid size-5 place-items-center rounded-full bg-amber-500 text-[11px] font-bold text-white">{waiting}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="hidden text-right text-xs leading-tight text-stone-300 md:block">
          <div className="flex items-center justify-end gap-1.5"><span className="size-2 rounded-full bg-emerald-400" />Smena ochiq</div>
          <div>Barista: <span className="text-white">{BARISTA}</span></div>
        </div>
      </header>
      <div className="min-h-0 flex-1">
        {tab === 'kassa' && <Kassa />}
        {tab === 'barista' && <Barista />}
        {tab === 'display' && <Display />}
        {tab === 'admin' && <Admin />}
      </div>
    </div>
  )
}

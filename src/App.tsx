import { useEffect, useState } from 'react'
import { t } from './i18n'
import LangSwitch from './LangSwitch'
import { ChefHat, Coffee, LayoutDashboard, LogOut, Monitor, Store, WifiOff } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import Kassa from './Kassa'
import Barista from './Barista'
import Display from './Display'
import Admin from './Admin'
import Login from './Login'
import { CloseShiftModal } from './Shift'
import { ROLE_LABEL } from './data'
import type { Role } from './data'
import { bootstrap, logout, useAppState } from './store'

type Tab = 'kassa' | 'barista' | 'display' | 'admin'
const TABS: { id: Tab; label: string; icon: LucideIcon; roles: Role[] }[] = [
  { id: 'kassa', label: 'Kassa', icon: Store, roles: ['owner', 'admin', 'kassir'] },
  { id: 'barista', label: 'Barista', icon: ChefHat, roles: ['owner', 'admin', 'kassir', 'barista'] },
  { id: 'display', label: 'Mijoz ekrani', icon: Monitor, roles: ['owner', 'admin', 'kassir', 'barista'] },
  { id: 'admin', label: 'Admin', icon: LayoutDashboard, roles: ['owner', 'admin'] },
]
const fromHash = (): Tab | null => {
  const h = window.location.hash.slice(1)
  return TABS.some((t) => t.id === h) ? (h as Tab) : null
}

void bootstrap()

export default function App() {
  const { phase, session } = useAppState()
  if (phase === 'loading') return <div className="grid h-dvh place-items-center text-stone-500">{t('Yuklanmoqda…')}</div>
  if (phase === 'login' || !session) return <Login />
  return <Main role={session.staff.role} />
}

function Main({ role }: { role: Role }) {
  const tabs = TABS.filter((t) => t.roles.includes(role))
  const pick = (t: Tab | null) => (t && tabs.some((x) => x.id === t) ? t : tabs[0].id)
  const [tab, setTab] = useState<Tab>(() => pick(fromHash()))
  const [shiftOpen, setShiftOpen] = useState(false)
  const { orders, shift, session, online } = useAppState()
  const waiting = orders.filter((o) => o.status === 'new').length

  useEffect(() => {
    const onHash = () => setTab(pick(fromHash()))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex shrink-0 items-center gap-2 bg-stone-900 px-3 py-2 text-white sm:gap-4 sm:px-4">
        <div className="flex items-center gap-2 font-semibold">
          <span className="grid size-8 place-items-center rounded-lg bg-amber-600"><Coffee className="size-5" /></span>
          <span className="hidden sm:inline">CoffeePOS</span>
          <span className="hidden max-w-40 truncate rounded bg-white/10 px-1.5 py-0.5 text-xs font-medium text-amber-300 lg:inline">{session?.company.name}</span>
        </div>
        <nav className="flex flex-1 justify-center gap-1 sm:justify-start">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { window.location.hash = id }}
              className={`relative flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[11px] font-medium sm:flex-row sm:gap-2 sm:text-sm ${tab === id ? 'bg-white text-stone-900' : 'text-stone-300 hover:bg-white/10'}`}
            >
              <Icon className="size-5 sm:size-4" />
              {t(label)}
              {id === 'barista' && waiting > 0 && (
                <span className="absolute -right-1 -top-1 grid size-5 place-items-center rounded-full bg-amber-500 text-[11px] font-bold text-white">{waiting}</span>
              )}
            </button>
          ))}
        </nav>
        {!online && <span title={t("Server bilan aloqa yo'q")} className="flex items-center gap-1 rounded-lg bg-red-600 px-2 py-1 text-xs"><WifiOff className="size-4" /><span className="hidden sm:inline">{t("Aloqa yo'q")}</span></span>}
        <button onClick={() => role !== 'barista' && setShiftOpen(true)} className="hidden rounded-lg px-2 py-1 text-right text-xs leading-tight text-stone-300 hover:bg-white/10 md:block">
          <div className="flex items-center justify-end gap-1.5"><span className={`size-2 rounded-full ${shift ? 'bg-emerald-400' : 'bg-red-400'}`} />{shift ? t('Smena ochiq') : t('Smena yopiq')}</div>
          <div><span className="text-white">{session?.staff.name}</span> · {t(ROLE_LABEL[role])}</div>
        </button>
        <LangSwitch />
        <button onClick={() => { if (confirm(t('Tizimdan chiqilsinmi?'))) logout() }} aria-label={t('Chiqish')} title={t('Chiqish')} className="rounded-lg p-2 text-stone-300 hover:bg-white/10"><LogOut className="size-5" /></button>
      </header>
      <div className="min-h-0 flex-1">
        {tab === 'kassa' && <Kassa onShift={() => setShiftOpen(true)} />}
        {tab === 'barista' && <Barista />}
        {tab === 'display' && <Display />}
        {tab === 'admin' && <Admin />}
      </div>
      {shiftOpen && <CloseShiftModal onClose={() => setShiftOpen(false)} />}
    </div>
  )
}

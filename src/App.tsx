import { lazy, Suspense, useEffect, useState } from 'react'
import { t } from './i18n'
import LangSwitch from './LangSwitch'
import ThemeSwitch from './ThemeSwitch'
import UpdateNotice from './UpdateNotice'
import { ChefHat, Coffee, LayoutDashboard, LogOut, Store, WifiOff } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import Kassa from './Kassa'
const HookahPOS = lazy(() => import('./HookahPOS'))
const Barista = lazy(() => import('./Barista'))
const Admin = lazy(() => import('./Admin'))
import Login from './Login'
const Superadmin = lazy(() => import('./Superadmin'))
import { CloseShiftModal } from './Shift'
import { ROLE_LABEL } from './data'
import type { Role } from './data'
import { bootstrap, logout, useAppState } from './store'

type Tab = 'kassa' | 'barista' | 'admin' | 'hookah'
const TABS: { id: Tab; label: string; icon: LucideIcon; roles: Role[] }[] = [
  { id: 'hookah', label: 'Kalyanxona', icon: Coffee, roles: ['owner', 'admin', 'kassir'] },
  { id: 'kassa', label: 'Kassa', icon: Store, roles: ['owner', 'admin', 'kassir'] },
  { id: 'barista', label: 'Barista', icon: ChefHat, roles: ['owner', 'admin', 'barista'] },
  { id: 'admin', label: 'Admin', icon: LayoutDashboard, roles: ['owner', 'admin'] },
]
const fromHash = (): Tab | null => {
  const h = window.location.hash.slice(1)
  return TABS.some((t) => t.id === h) ? (h as Tab) : null
}

void bootstrap()

export default function App() {
  const [platform, setPlatform] = useState(() => window.location.hash === '#superadmin')
  useEffect(() => { const onHash = () => setPlatform(window.location.hash === '#superadmin'); window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash) }, [])
  const { phase, session } = useAppState()
  if (platform) return <Suspense fallback={<Loading />}><Superadmin /></Suspense>
  if (phase === 'loading') return <div className="grid h-dvh place-items-center text-stone-500">{t('Yuklanmoqda…')}</div>
  if (phase === 'login' || !session) return <Login />
  return <Suspense fallback={<Loading />}><Main role={session.staff.role} /></Suspense>
}

function Loading() { return <div role="status" className="grid h-dvh place-items-center text-stone-500">{t('Yuklanmoqda…')}</div> }

function Main({ role }: { role: Role }) {
  const { orders, shift, session, online, pendingCount, pendingError } = useAppState()
  const hasHookah = Boolean(session?.company.modules?.includes('hookah'))
  const canBarista = Boolean(session?.staff.canBarista)
  const tabs = TABS.filter((t) => (!hasHookah || t.id !== 'kassa') && (t.id !== 'hookah' || session?.company.modules?.includes('hookah')) && (t.roles.includes(role) || (t.id === 'barista' && role === 'kassir' && canBarista)))
  const pick = (t: Tab | null): Tab => (hasHookah && t === 'kassa' && role !== 'barista' ? 'hookah' : t && tabs.some((x) => x.id === t) ? t : (role === 'owner' || role === 'admin' ? 'admin' : tabs[0].id))
  const [tab, setTab] = useState<Tab>(() => pick(fromHash()))
  const [shiftOpen, setShiftOpen] = useState(false)
  const waiting = orders.filter((o) => o.status === 'new' && !o.pendingSync).length
  const manager = role === 'owner' || role === 'admin'
  const inAdmin = tab === 'admin' && manager
  const visibleTabs = manager ? (inAdmin ? tabs.filter(t => t.id === 'admin') : tabs.filter(t => t.id !== 'admin')) : tabs

  useEffect(() => {
    const onHash = () => setTab(pick(fromHash()))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, canBarista, hasHookah])

  return (
    <div className={`app-shell ${hasHookah ? 'app-hookah' : ''} flex h-dvh flex-col ${inAdmin ? "app-admin" : tab === "kassa" ? "app-cashier" : "app-barista"}`}>
      <header className={`premium-app-header flex shrink-0 items-center gap-2 px-3 py-2 text-white sm:gap-4 sm:px-4 ${inAdmin ? 'bg-slate-950' : 'bg-stone-900'}`}>
        <div className="premium-app-brand flex items-center gap-2 font-semibold">
          <span className="grid size-8 place-items-center rounded-lg bg-amber-600"><Coffee className="size-5" /></span>
          <span className="hidden sm:inline">CoffeePOS</span>
          <span className="hidden max-w-40 truncate rounded bg-white/10 px-1.5 py-0.5 text-xs font-medium text-amber-300 lg:inline">{session?.company.name}</span>
        </div>
        <nav className="premium-app-nav flex flex-1 justify-center gap-1 sm:justify-start">
          {visibleTabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { window.location.hash = id }}
              className={`premium-nav-tab relative flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[11px] font-medium sm:flex-row sm:gap-2 sm:text-sm ${tab === id ? 'bg-white text-stone-900' : 'text-stone-300 hover:bg-white/10'}`}
            >
              <Icon className="size-5 sm:size-4" />
              {t(hasHookah && id === 'barista' ? 'Tayyorlash ekrani' : label)}
              {id === 'barista' && waiting > 0 && (
                <span className="absolute -right-1 -top-1 grid size-5 place-items-center rounded-full bg-amber-500 text-[11px] font-bold text-white">{waiting}</span>
              )}
            </button>
          ))}
        </nav>
        {manager && <button onClick={() => { window.location.hash = inAdmin ? (hasHookah ? 'hookah' : 'kassa') : 'admin' }}
          className="admin-return rounded-lg border border-white/30 px-2 py-2 text-xs font-semibold text-white hover:bg-white/10 sm:px-3">
          {inAdmin ? t(hasHookah ? 'Kalyanxona kassasi' : 'Ishchi kassa oynasi') : t('Admin boshqaruviga qaytish')}
        </button>}
        {!online && <span title={t("Server bilan aloqa yo'q")} className="flex items-center gap-1 rounded-lg bg-red-600 px-2 py-1 text-xs"><WifiOff className="size-4" /><span className="hidden sm:inline">{t("Aloqa yo'q")}</span></span>}
        {pendingCount > 0 && <span className="rounded-lg bg-amber-500 px-2 py-1 text-xs font-bold text-stone-950" title={pendingError || t('Serverga yuborilmagan buyurtmalar')}>
          {t('Navbatda')}: {pendingCount}
        </span>}
        <button onClick={() => (tab === 'kassa' || tab === 'hookah') && setShiftOpen(true)} className="hidden rounded-lg px-2 py-1 text-right text-xs leading-tight text-stone-300 hover:bg-white/10 md:block">
          <div className="flex items-center justify-end gap-1.5"><span className={`size-2 rounded-full ${shift ? 'bg-emerald-400' : 'bg-red-400'}`} />{shift ? t('Smena ochiq') : t('Smena yopiq')}</div>
          <div><span className="text-white">{session?.staff.name}</span> · {t(hasHookah && role === 'barista' ? 'Kalyanchi' : ROLE_LABEL[role])}</div>
        </button>
        <ThemeSwitch />
        <LangSwitch />
        <button onClick={() => { if (confirm(t('Tizimdan chiqilsinmi?'))) logout() }} aria-label={t('Chiqish')} title={t('Chiqish')} className="rounded-lg p-2 text-stone-300 hover:bg-white/10"><LogOut className="size-5" /></button>
      </header>
      <UpdateNotice pendingCount={pendingCount} />
      {pendingError && <div role="alert" className="bg-red-50 px-3 py-2 text-center text-xs text-red-800">
        {t('Sinxronlashda xato')}: {pendingError}
      </div>}
      <div className="min-h-0 flex-1">
        {tab === 'hookah' && <HookahPOS onShift={() => setShiftOpen(true)} />}
        {tab === 'kassa' && <Kassa onShift={() => setShiftOpen(true)} />}
        {tab === 'barista' && <Barista />}

        {tab === 'admin' && (hasHookah ? <HookahPOS admin onShift={() => setShiftOpen(true)} /> : <Admin />)}
      </div>
      {shiftOpen && (tab === 'kassa' || tab === 'hookah') && <CloseShiftModal onClose={() => setShiftOpen(false)} />}
    </div>
  )
}

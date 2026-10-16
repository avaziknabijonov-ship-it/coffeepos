import { useEffect, useState } from 'react'
import { t } from './i18n'
import LangSwitch from './LangSwitch'
import { Coffee, LayoutDashboard, LogOut, Settings, Store, ClipboardList, WifiOff, KeyRound, Menu, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import Kassa from './Kassa'
import OrdersScreen from './OrdersScreen'
import Admin from './Admin'
import { ExpensesView } from './Finance'
import Login from './Login'
import LicenseBanner from './LicenseBanner'
import LicensePage from './LicensePage'
import { CloseShiftModal } from './Shift'
import { ROLE_LABEL } from './data'
import type { Role } from './data'
import { bootstrap, logout, useAppState } from './store'

type Tab = 'kassa' | 'orders' | 'dashboard' | 'admin' | 'expenses' | 'license'
const TABS: { id: Tab; label: string; icon: LucideIcon; roles: Role[] }[] = [
  { id: 'kassa', label: 'Kassa', icon: Store, roles: ['owner', 'admin', 'kassir', 'barista'] },
  { id: 'orders', label: 'Buyurtmalar', icon: ClipboardList, roles: ['owner', 'admin', 'kassir', 'barista'] },
  { id: 'expenses', label: 'Kunlik chiqimlar', icon: Store, roles: ['kassir'] },
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['owner', 'admin'] },
  { id: 'admin', label: 'Admin', icon: Settings, roles: ['owner', 'admin'] },
  { id: 'license', label: 'Litsenziya', icon: KeyRound, roles: ['owner', 'admin'] },
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
  const [functionsOpen, setFunctionsOpen] = useState(false)
  const [adminView, setAdminView] = useState<'stock' | 'inventory' | 'shifts' | 'expenses'>('stock')
  const { shift, session, online } = useAppState()

  useEffect(() => {
    const onHash = () => setTab(pick(fromHash()))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  return (
    <div className="flex min-h-dvh flex-col overflow-hidden">
      <header className="flex shrink-0 flex-wrap items-center gap-2 bg-stone-900 px-3 py-2 text-white sm:flex-nowrap sm:gap-4 sm:px-4">
        <div className="flex items-center gap-2 font-semibold">
          <span className="grid size-8 place-items-center rounded-lg bg-amber-600"><Coffee className="size-5" /></span>
          <span className="hidden sm:inline">CoffeePOS</span>
          <span className="hidden max-w-40 truncate rounded bg-white/10 px-1.5 py-0.5 text-xs font-medium text-amber-300 lg:inline">{session?.company.name}</span>
        </div>
        <nav className="order-3 flex w-full justify-start gap-1 overflow-x-auto border-t border-white/10 pt-2 sm:order-none sm:w-auto sm:flex-1 sm:border-0 sm:pt-0">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { window.location.hash = id }}
              className={`relative flex flex-col items-center gap-0.5 min-h-11 min-w-18 touch-manipulation rounded-lg px-3 py-1.5 text-[11px] font-medium sm:flex-row sm:gap-2 sm:text-sm ${tab === id ? 'bg-white text-stone-900' : 'text-stone-300 hover:bg-white/10'}`}
            >
              <Icon className="size-5 sm:size-4" />
              {t(label)}
            </button>
          ))}
        </nav>
        {!online && <span title={t("Server bilan aloqa yo'q")} className="flex items-center gap-1 rounded-lg bg-red-600 px-2 py-1 text-xs"><WifiOff className="size-4" /><span className="hidden sm:inline">{t("Aloqa yo'q")}</span></span>}
        <button onClick={() => role !== 'barista' && setShiftOpen(true)} className="hidden rounded-lg px-2 py-1 text-right text-xs leading-tight text-stone-300 hover:bg-white/10 md:block">
          <div className="flex items-center justify-end gap-1.5"><span className={`size-2 rounded-full ${shift ? 'bg-emerald-400' : 'bg-red-400'}`} />{shift ? t('Smena ochiq') : t('Smena yopiq')}</div>
          <div><span className="text-white">{session?.staff.name}</span> · {t(ROLE_LABEL[role])}</div>
        </button>
        <button aria-label={t('Funksiyalar')} onClick={() => setFunctionsOpen(true)} className="rounded-lg p-2 hover:bg-white/10"><Menu className="size-5" /></button>
        <LangSwitch />
        <button onClick={() => { if (confirm(t('Tizimdan chiqilsinmi?'))) logout() }} aria-label={t('Chiqish')} title={t('Chiqish')} className="rounded-lg p-2 text-stone-300 hover:bg-white/10"><LogOut className="size-5" /></button>
      </header>
      <LicenseBanner role={role} />
      <div className="min-h-0 flex-1 overflow-auto">
        {tab === 'kassa' && <Kassa key={session?.company.slug} onShift={() => setShiftOpen(true)} />}
        {tab === 'orders' && <OrdersScreen />}
        {tab === 'expenses' && <div className="mx-auto max-w-5xl p-4"><ExpensesView /></div>}
        {tab === 'dashboard' && <Admin key="dashboard" initialView="dashboard" />}
        {tab === 'admin' && <Admin key={adminView} initialView={adminView} />}
        {tab === 'license' && <LicensePage />}
      </div>
      {functionsOpen && <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={() => setFunctionsOpen(false)}>
        <div role="dialog" aria-modal="true" aria-label={t('Funksiyalar')} className="max-h-[90dvh] w-full max-w-3xl overflow-auto rounded-2xl bg-white p-6" onClick={e => e.stopPropagation()}>
          <div className="mb-6 flex items-center justify-between"><h2 className="text-xl font-bold">{t('Funksiyalar')}</h2><button aria-label={t('Yopish')} onClick={() => setFunctionsOpen(false)}><X /></button></div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {[
              { label: 'Smena (X-hisobot)', color: 'bg-amber-500', action: () => setShiftOpen(true), allowed: role !== 'barista' },
              { label: 'Buyurtmalar arxivi', color: 'bg-sky-600', action: () => { window.location.hash = 'orders' }, allowed: true },
              { label: 'Kunlik chiqimlar', color: 'bg-amber-500', action: () => { setAdminView('expenses'); window.location.hash = role === 'kassir' ? 'expenses' : 'admin' }, allowed: role !== 'barista' },
              ...(['inventory', 'stock', 'shifts'] as const).map((view, i) => ({ label: ['Inventarizatsiya', 'Ombor', 'Smenalar'][i], color: i === 2 ? 'bg-emerald-600' : 'bg-violet-600', action: () => { setAdminView(view); window.location.hash = 'admin' }, allowed: role === 'owner' || role === 'admin' })),
              { label: 'Chiqish', color: 'bg-stone-500', action: () => { if (confirm(t('Tizimdan chiqilsinmi?'))) logout() }, allowed: true },
            ].filter(x => x.allowed).map(item => <button key={item.label} className="flex min-h-24 items-center gap-4 rounded-xl border border-stone-200 p-4 text-left font-medium hover:bg-stone-50" onClick={() => { setFunctionsOpen(false); item.action() }}><span className={`grid size-14 shrink-0 place-items-center rounded-xl text-white ${item.color}`}><Menu /></span>{t(item.label)}</button>)}
          </div>
        </div>
      </div>}
      {shiftOpen && <CloseShiftModal onClose={() => setShiftOpen(false)} />}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'
import { applyTheme, getThemeMode, saveThemeMode } from './theme'
import type { ThemeMode } from './theme'
import { t } from './i18n'

const modes: ThemeMode[] = ['light', 'dark', 'system']
const icons = { light: Sun, dark: Moon, system: Monitor }
export default function ThemeSwitch() {
  const labels: Record<ThemeMode, string> = { light: t('Kun'), dark: t('Tun'), system: t('Avto') }
  const [mode, setMode] = useState<ThemeMode>(getThemeMode)
  useEffect(() => {
    applyTheme(mode)
    if (mode !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const refresh = () => applyTheme('system')
    media.addEventListener('change', refresh)
    return () => media.removeEventListener('change', refresh)
  }, [mode])
  const change = () => {
    const next = modes[(modes.indexOf(mode) + 1) % modes.length]
    saveThemeMode(next)
    setMode(next)
  }
  const Icon = icons[mode]
  return <button type="button" onClick={change} title={labels[mode] + ' · ' + t('Rejimni almashtirish')} aria-label={labels[mode]}
    className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-white/25 px-2 py-1.5 text-xs font-semibold text-white hover:bg-white/10">
    <Icon className="size-4" /><span className="hidden lg:inline">{labels[mode]}</span>
  </button>
}

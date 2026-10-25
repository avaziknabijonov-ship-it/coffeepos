import { useEffect, useState } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'
import { applyTheme, getThemeMode, saveThemeMode } from './theme'
import type { ThemeMode } from './theme'

const modes: ThemeMode[] = ['light', 'dark', 'system']
const labels: Record<ThemeMode, string> = { light: 'Kun / Светлая', dark: 'Tun / Тёмная', system: 'Avto / Система' }
const icons = { light: Sun, dark: Moon, system: Monitor }
export default function ThemeSwitch() {
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
  return <button type="button" onClick={change} title={labels[mode] + ' · click to change'} aria-label={labels[mode]}
    className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-white/25 px-2 py-1.5 text-xs font-semibold text-white hover:bg-white/10">
    <Icon className="size-4" /><span className="hidden lg:inline">{mode === 'dark' ? 'Tun' : mode === 'light' ? 'Kun' : 'Avto'}</span>
  </button>
}

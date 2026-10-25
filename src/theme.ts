export type ThemeMode = 'dark' | 'light' | 'system'
const KEY = 'coffeepos-theme'
export function getThemeMode(): ThemeMode {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' || value === 'system' ? value : 'dark'
  } catch { return 'dark' }
}
export function resolveTheme(mode: ThemeMode): 'dark' | 'light' {
  return mode === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : mode
}
export function applyTheme(mode: ThemeMode) {
  const resolved = resolveTheme(mode)
  document.documentElement.dataset.theme = resolved
  document.documentElement.style.colorScheme = resolved
}
export function saveThemeMode(mode: ThemeMode) {
  try { localStorage.setItem(KEY, mode) } catch { /* storage may be unavailable */ }
  applyTheme(mode)
}

import type { Lang } from './i18n'
import { setLang, useAppState } from './store'

export default function LangSwitch({ light = false }: { light?: boolean }) {
  const { lang } = useAppState()
  return (
    <div className={`flex rounded-lg p-0.5 text-xs font-semibold ${light ? 'bg-stone-100' : 'bg-white/10'}`}>
      {(['uz', 'ru'] as Lang[]).map((l) => (
        <button key={l} onClick={() => setLang(l)} aria-pressed={lang === l}
          className={`rounded-md px-2 py-1 ${lang === l ? (light ? 'bg-white text-stone-900 shadow-sm' : 'bg-white text-stone-900') : light ? 'text-stone-500' : 'text-stone-300'}`}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  )
}

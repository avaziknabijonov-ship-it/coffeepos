import { useState } from 'react'
import { uploadImage } from './api'
import { t } from './i18n'
import CatalogImage from './CatalogImage'

export default function ImagePicker({ value, onChange, onBusyChange }: { value: string; onChange: (url: string) => void; onBusyChange?: (busy: boolean) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  return <div className="space-y-2">
    <label className="block rounded-lg border border-stone-300 p-2 text-sm">{busy ? t('Yuklanmoqda…') : t('Qurilmadan rasm tanlash')}
      <input aria-label={t('Qurilmadan rasm tanlash')} type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} className="mt-2 block w-full text-xs" onChange={async e => {
        const file = e.target.files?.[0]; e.target.value = ''; if (!file) return
        setError(''); setBusy(true); onBusyChange?.(true)
        try { onChange(await uploadImage(file)) } catch (err) { setError((err as Error).message) } finally { setBusy(false); onBusyChange?.(false) }
      }} />
    </label>
    <input aria-label={t('Rasm URL (https://...)')} value={value} onChange={e => onChange(e.target.value)} placeholder={t('Rasm URL (https://...)')} maxLength={512} className="w-full rounded-lg border border-stone-300 px-3 py-2" />
    {value && <div className="flex items-center gap-2"><CatalogImage src={value} alt={t('Rasm')} className="h-20 w-20 rounded-lg object-cover" /><button type="button" onClick={() => onChange('')} className="text-sm text-red-700">{t('Rasmni olib tashlash')}</button></div>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    <p className="text-xs text-stone-500">{t('JPG, PNG yoki WebP. Eng katta hajm: 3 MB. Google ulashish havolasi o‘rniga rasm faylini yuklang.')}</p>
  </div>
}

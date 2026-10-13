import { useEffect, useState } from 'react'
import { api } from './api'
import { t } from './i18n'
import type { Role } from './data'

type License = {
  status: 'trial' | 'active' | 'grace' | 'expired' | 'suspended' | 'unconfigured'
  canWrite: boolean
  expiresAt: number | null
  serverTime: number
}

export default function LicenseBanner({ role }: { role: Role }) {
  const [license, setLicense] = useState<License | null>(null)

  useEffect(() => {
    let mounted = true
    const refresh = () => {
      void api<License>('/api/license/status').then((info) => {
        if (mounted) setLicense(info)
      }).catch(() => { /* Offline state is already shown in App header. */ })
    }
    refresh()
    const interval = setInterval(refresh, 60_000)
    return () => { mounted = false; clearInterval(interval) }
  }, [])

  if (!license) return null

  const days = license.expiresAt == null ? null
    : Math.max(0, Math.ceil((license.expiresAt - license.serverTime) / 86_400_000))
  const manager = role === 'owner' || role === 'admin'
  const expiring = days != null && days <= 7

  if (license.status === 'active' && !expiring) return null
  if (license.status === 'trial' && !manager) return null
  if (license.status === 'active' && !manager) return null

  let message = ''
  switch (license.status) {
    case 'trial':
      message = t('Sinov litsenziyasi. Qolgan kunlar: {n}', { n: days ?? 0 })
      break
    case 'active':
      message = t('Litsenziya tugashiga {n} kun qoldi', { n: days ?? 0 })
      break
    case 'grace':
      message = t('Obuna muddati tugagan. Imtiyozli muddat: {n} kun', { n: days ?? 0 })
      break
    case 'suspended':
      message = t('Litsenziya administrator tomonidan to‘xtatilgan. Yangi amallarga ruxsat yo‘q.')
      break
    case 'unconfigured':
      message = t('Litsenziya sozlanmagan. Yangi amallarga ruxsat yo‘q.')
      break
    default:
      message = t('Litsenziya muddati tugagan. Ma’lumotlarni ko‘rish mumkin, savdo va o‘zgartirishlar bloklangan.')
  }

  return <div role="status" className={`border-b px-4 py-2 text-center text-sm font-medium ${license.canWrite ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-red-200 bg-red-50 text-red-800'}`}>
    {message}
  </div>
}

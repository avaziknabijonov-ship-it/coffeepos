import { useEffect, useState } from 'react'
import { api } from './api'
import { t } from './i18n'

type Event = { id: number; actorId: number; actor: string; action: string; entityId: number; before: unknown; after: unknown; createdAt: number }
type Page = { items: Event[]; nextCursor: number | null }
const labels: Record<string, string> = { 'device.enroll': 'Qurilmani ro‘yxatga olish', 'device.revoke': 'Qurilma ruxsatini bekor qilish', 'device.policy': 'Qurilmalar kirish tartibini o‘zgartirish', 'receipt.issue': 'Elektron chek havolasini yaratish', 'receipt.revoke': 'Elektron chek havolalarini bekor qilish', 'customer.analytics_consent': 'Mijoz roziligini boshqarish', 'order.refund': 'Pul qaytarish', 'order.cancel': 'Buyurtmani bekor qilish', 'inventory.count': 'Inventarizatsiya' }
export default function AuditLog() {
  const [cursor, setCursor] = useState<number | null>(null)
  const [page, setPage] = useState<Page>({ items: [], nextCursor: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    const load = async () => {
      setLoading(true); setError('')
      try {
        const result = await api<Page>('/api/audit?limit=50' + (cursor ? `&before_id=${cursor}` : ''))
        if (active) setPage(result)
      } catch (err) { if (active) { setError((err as Error).message); setPage({ items: [], nextCursor: null }) } }
      finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false }
  }, [cursor, revision])
  return <section className="space-y-4 rounded-2xl border bg-white p-4">
    <h2 className="text-xl font-semibold">{t('Audit jurnali')}</h2>
    <p className="text-sm text-stone-600">{t('Jurnal serverda qayd etilgan amallarni ko‘rsatadi. Eski amallar avtomatik tiklanmaydi.')}</p>
    <button disabled={loading} className="rounded border px-3 py-2" onClick={() => { setCursor(null); setRevision(v => v + 1) }}>{t('Yangilash')}</button>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {loading ? <p>{t('Yuklanmoqda…')}</p> : <div className="space-y-3">{page.items.map(e => <article key={e.id} className="rounded-lg border p-3 text-sm">
      <p className="font-semibold">#{e.id} · {t(labels[e.action] ?? e.action)} · #{e.entityId}</p>
      <p>{e.actor} (#{e.actorId}) · {new Date(e.createdAt).toLocaleString()}</p>
      <details className="mt-2"><summary>{t('Batafsil')}</summary><pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-stone-50 p-2">{JSON.stringify({ before: e.before, after: e.after }, null, 2)}</pre></details>
    </article>)}</div>}
    <button disabled={loading || !page.nextCursor} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => setCursor(page.nextCursor)}>{t('Oldingi yozuvlar')}</button>
  </section>
}

import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2, X } from 'lucide-react'
import { api } from './api'
import { INGREDIENTS, ING, UNIT_LABEL, fmt, som } from './data'
import type { Ingredient, RecipeLine, Unit } from './data'
import { t, tCatalogName } from './i18n'
import { produceSemi, refreshMenu, useAppState } from './store'

const input = 'rounded-lg border border-stone-200 px-2.5 py-2 outline-none focus:border-amber-500'
const btn = 'rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-stone-300'
const num = (v: string) => Number(v.replace(',', '.')) || 0

/** Cashier/manager dialog: make a batch of a semi-finished item from raw stock. */
export function ProduceDialog({ onClose, initial }: { onClose: () => void; initial?: string }) {
  const { stock } = useAppState()
  const semis = INGREDIENTS.filter((i) => i.semi)
  const [ing, setIng] = useState(initial ?? semis[0]?.id ?? '')
  const [qty, setQty] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const semi = ING[ing]
  const amount = num(qty)
  const factor = semi?.yieldQty ? amount / semi.yieldQty : 0
  const lines = (semi?.recipe ?? []).map((l) => ({ ...l, need: l.qty * factor, have: stock[l.ing] ?? 0 }))

  const submit = async () => {
    if (!semi || amount <= 0) return
    setBusy(true); setError('')
    try { await produceSemi(semi.id, amount); onClose() }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 text-stone-900 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold">{t('Polufabrikat tayyorlash')}</h2>
          <button onClick={onClose} aria-label={t('Yopish')}><X className="size-6" /></button>
        </div>
        {semis.length === 0 ? <p className="text-sm text-stone-500">{t('Hali polufabrikat qo‘shilmagan.')}</p> : <div className="space-y-3">
          <select value={ing} onChange={(e) => setIng(e.target.value)} className={`${input} w-full`}>
            {semis.map((s) => <option key={s.id} value={s.id}>{tCatalogName(s.name)} ({fmt(stock[s.id] ?? 0)} {t(UNIT_LABEL[s.unit])})</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm">
            {t('Miqdor')}
            <input autoFocus value={qty} onChange={(e) => setQty(e.target.value.replace(/[^\d.,]/g, ''))} inputMode="decimal" className={`${input} w-32`} />
            {semi && <span>{t(UNIT_LABEL[semi.unit])}</span>}
            {semi?.yieldQty ? <button type="button" className="rounded-lg border px-2 py-1 text-xs" onClick={() => setQty(String(semi.yieldQty))}>{t('1 partiya')} = {fmt(semi.yieldQty)}</button> : null}
          </label>
          {amount > 0 && <table className="w-full text-sm">
            <thead><tr className="text-left text-stone-500"><th className="py-1">{t('Xomashyo')}</th><th>{t('Sarflanadi')}</th><th>{t('Qoldiq')}</th></tr></thead>
            <tbody>{lines.map((l) => <tr key={l.ing} className="border-t">
              <td className="py-1">{tCatalogName(ING[l.ing]?.name ?? l.ing)}</td>
              <td>{fmt(l.need)} {t(UNIT_LABEL[ING[l.ing]?.unit ?? 'g'])}</td>
              <td className={l.have < l.need ? 'font-bold text-red-600' : ''}>{fmt(l.have)}</td>
            </tr>)}</tbody>
          </table>}
          {error && <p role="alert" className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
          <button disabled={busy || amount <= 0} onClick={() => void submit()} className={`${btn} w-full py-3`}>{t('Tayyorlandi')}</button>
        </div>}
      </div>
    </div>
  )
}

type Draft = { id?: string; name: string; unit: Unit; min: string; yieldQty: string; recipe: RecipeLine[] }
const emptyDraft = (): Draft => ({ name: '', unit: 'ml', min: '', yieldQty: '', recipe: [] })

/** Admin: list, create and edit semi-finished items (polufabrikatlar). */
export function SemiProductsView() {
  const { stock } = useAppState()
  const [draft, setDraft] = useState<Draft | null>(null)
  const [produce, setProduce] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const semis = INGREDIENTS.filter((i) => i.semi)
  const raws = INGREDIENTS.filter((i) => !i.semi && i.id !== draft?.id)

  const edit = (i: Ingredient) => setDraft({ id: i.id, name: i.name, unit: i.unit, min: String(i.min), yieldQty: String(i.yieldQty ?? ''), recipe: (i.recipe ?? []).map((l) => ({ ...l })) })
  const setLine = (n: number, patch: Partial<RecipeLine>) => draft && setDraft({ ...draft, recipe: draft.recipe.map((l, i) => (i === n ? { ...l, ...patch } : l)) })
  const batchCost = (d: Draft) => d.recipe.reduce((s, l) => s + (ING[l.ing]?.cost ?? 0) * l.qty, 0)

  const save = async () => {
    if (!draft) return
    setBusy(true); setError('')
    const body = { name: draft.name.trim(), unit: draft.unit, cost: 0, min: num(draft.min), yieldQty: num(draft.yieldQty),
      recipe: draft.recipe.filter((l) => l.ing && l.qty > 0) }
    try {
      await api(draft.id ? '/api/ingredients/' + encodeURIComponent(draft.id) : '/api/ingredients', { method: draft.id ? 'PUT' : 'POST', body })
      await refreshMenu()
      setDraft(null)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('Polufabrikatlar')}</h2>
        <button className={`${btn} flex items-center gap-1`} onClick={() => { setError(''); setDraft(emptyDraft()) }}><Plus className="size-4" />{t('Yangi polufabrikat')}</button>
      </div>
      <p className="mb-4 text-sm text-stone-600">{t('Sirop, krem, sovuq damlama kabi oldindan tayyorlanadigan mahsulotlar. Tayyorlanganda tarkibidagi xomashyo ombordan chiqadi, polufabrikat omborga kiradi va texkartada oddiy xomashyo kabi ishlatiladi.')}</p>
      {semis.length === 0 ? <p className="rounded-xl bg-stone-50 p-4 text-sm text-stone-500">{t('Hali polufabrikat qo‘shilmagan.')}</p> :
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-sm">
          <thead><tr className="text-left text-stone-500"><th className="py-2">{t('Nomi')}</th><th>{t('Tarkib')}</th><th>{t('1 partiya')}</th><th>{t('Qoldiq')}</th><th>{t('Tannarx')}</th><th /></tr></thead>
          <tbody>{semis.map((s) => <tr key={s.id} className="border-t align-top">
            <td className="py-2 font-medium">{tCatalogName(s.name)}</td>
            <td className="text-xs text-stone-600">{(s.recipe ?? []).map((l) => `${tCatalogName(ING[l.ing]?.name ?? l.ing)} ${fmt(l.qty)}`).join(', ')}</td>
            <td>{fmt(s.yieldQty ?? 0)} {t(UNIT_LABEL[s.unit])}</td>
            <td className={(stock[s.id] ?? 0) < s.min ? 'font-bold text-red-600' : ''}>{fmt(stock[s.id] ?? 0)}</td>
            <td>{som(s.cost)} / {t(UNIT_LABEL[s.unit])}</td>
            <td className="whitespace-nowrap text-right">
              <button className="mr-2 rounded-lg bg-amber-600 px-2 py-1 text-xs font-semibold text-white" onClick={() => setProduce(s.id)}>{t('Tayyorlash')}</button>
              <button aria-label={t('Tahrirlash')} className="rounded-lg p-1.5 hover:bg-stone-100" onClick={() => { setError(''); edit(s) }}><Pencil className="size-4" /></button>
            </td>
          </tr>)}</tbody>
        </table></div>}

      {draft && <div className="mt-5 space-y-3 rounded-xl border border-amber-300 bg-amber-50/40 p-4">
        <div className="flex flex-wrap gap-2">
          <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder={t('Nomi')} className={`${input} min-w-48 flex-1`} />
          <select value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value as Unit })} className={input}>
            {(Object.keys(UNIT_LABEL) as Unit[]).map((u) => <option key={u} value={u}>{t(UNIT_LABEL[u])}</option>)}
          </select>
          <input value={draft.yieldQty} onChange={(e) => setDraft({ ...draft, yieldQty: e.target.value.replace(/[^\d.,]/g, '') })} placeholder={t('1 partiyadan chiqadi')} inputMode="decimal" className={`${input} w-40`} />
          <input value={draft.min} onChange={(e) => setDraft({ ...draft, min: e.target.value.replace(/[^\d.,]/g, '') })} placeholder={t('Min qoldiq')} inputMode="decimal" className={`${input} w-28`} />
        </div>
        <div className="space-y-2">
          <div className="text-sm font-semibold">{t('Tarkib (1 partiya uchun)')}</div>
          {draft.recipe.map((l, n) => <div key={`${n}-${draft.recipe.length}`} className="flex gap-2">
            <select value={l.ing} onChange={(e) => setLine(n, { ing: e.target.value })} className={`${input} flex-1`}>
              {raws.map((x) => <option key={x.id} value={x.id}>{tCatalogName(x.name)} ({t(UNIT_LABEL[x.unit])})</option>)}
            </select>
            <input defaultValue={l.qty || ''} onChange={(e) => setLine(n, { qty: num(e.target.value) })} inputMode="decimal" className={`${input} w-28`} />
            <button aria-label={t("O'chirish")} onClick={() => setDraft({ ...draft, recipe: draft.recipe.filter((_, i) => i !== n) })} className="px-2 text-stone-400 hover:text-red-600"><Trash2 className="size-4" /></button>
          </div>)}
          <button onClick={() => setDraft({ ...draft, recipe: [...draft.recipe, { ing: raws[0]?.id ?? '', qty: 0 }] })} className="text-sm font-medium text-amber-700">{t("+ Xomashyo qo'shish")}</button>
        </div>
        <p className="text-sm text-stone-600">{t('Partiya tannarxi')}: <b>{som(batchCost(draft))}</b>{num(draft.yieldQty) > 0 && <> · {som(batchCost(draft) / num(draft.yieldQty))} / {t(UNIT_LABEL[draft.unit])}</>}</p>
        {error && <p role="alert" className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button disabled={busy || !draft.name.trim() || num(draft.yieldQty) <= 0 || draft.recipe.length === 0} onClick={() => void save()} className={btn}>{t('Saqlash')}</button>
          <button onClick={() => setDraft(null)} className="rounded-lg border px-3 py-2 text-sm">{t('Bekor qilish')}</button>
        </div>
      </div>}

      {produce && <ProduceDialog initial={produce} onClose={() => setProduce(null)} />}
    </section>
  )
}

type StockConfig = { autoStoplist: boolean; telegramChat: string; telegramConfigured: boolean }

/** Admin: automatic stop-list and Telegram low-stock alerts. */
export function StockAutomationSettings() {
  const [config, setConfig] = useState<StockConfig | null>(null)
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  useEffect(() => { api<StockConfig>('/api/stock/config').then(setConfig).catch((e) => setError((e as Error).message)) }, [])

  const save = async (removeToken = false) => {
    if (!config) return
    setBusy(true); setError(''); setSaved(false)
    try {
      const r = await api<StockConfig>('/api/stock/config', { method: 'PUT', body: {
        autoStoplist: config.autoStoplist, telegramChat: config.telegramChat.trim(),
        telegramToken: removeToken ? '' : token.trim() || null,
      } })
      setConfig(r); setToken(''); setSaved(true)
      await refreshMenu()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <h2 className="mb-3 text-lg font-semibold">{t('Ombor avtomatikasi')}</h2>
      {!config ? (error ? <p className="text-sm text-red-700">{error}</p> : null) : <div className="max-w-xl space-y-4 text-sm">
        <label className="flex items-start gap-3">
          <input type="checkbox" className="mt-0.5 size-4" checked={config.autoStoplist} onChange={(e) => setConfig({ ...config, autoStoplist: e.target.checked })} />
          <span><b>{t('Avtomatik stop-list')}</b><span className="block text-stone-600">{t('Texkarta bo‘yicha xomashyo yetmasa, mahsulot kassada «Tugadi» bo‘ladi va sotilmaydi. Internet yo‘qligida qilingan sotuvlar baribir qabul qilinadi.')}</span></span>
        </label>
        <div className="space-y-2 rounded-xl border border-stone-200 p-3">
          <b>{t('Telegram ogohlantirish')}</b>
          <p className="text-stone-600">{t('Xomashyo minimal qoldiqdan kamayganda Telegram guruhga xabar yuboriladi. @BotFather orqali bot yarating, uni guruhga qo‘shing va guruh ID raqamini kiriting.')}</p>
          <input value={config.telegramChat} onChange={(e) => setConfig({ ...config, telegramChat: e.target.value })} placeholder={t('Chat ID (masalan -1001234567890)')} className={`${input} w-full`} />
          <input value={token} onChange={(e) => setToken(e.target.value)} placeholder={config.telegramConfigured ? t('Bot token saqlangan (o‘zgartirish uchun yangisini kiriting)') : t('Bot token')} className={`${input} w-full`} autoComplete="off" />
          {config.telegramConfigured && <button type="button" disabled={busy} onClick={() => void save(true)} className="text-xs text-red-600 underline">{t('Bot tokenni o‘chirish')}</button>}
        </div>
        {error && <p role="alert" className="rounded-lg bg-red-50 p-2 text-red-700">{error}</p>}
        {saved && <p className="text-emerald-700">{t('Saqlandi')}</p>}
        <button disabled={busy} onClick={() => void save()} className={btn}>{t('Saqlash')}</button>
      </div>}
    </section>
  )
}

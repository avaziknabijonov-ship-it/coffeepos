import { useEffect, useState } from 'react'
import { t } from './i18n'
import { Pencil, Plus, Trash2, X } from 'lucide-react'
import { CATEGORIES, INGREDIENTS, MODIFIERS, PAYMENT_LABEL, PRODUCTS, ROLE_LABEL, UNIT_LABEL, fmt, recipeCost, som, time } from './data'
import type { ModGroupId, Payment, Product, Role, Size, Unit } from './data'
import { api } from './api'
import { refreshMenu, useAppState } from './store'
import type { ShiftInfo } from './store'

const input = 'rounded-lg border border-stone-200 px-2.5 py-2 outline-none focus:border-amber-500'
const btn = 'rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-stone-300'
const GROUP_LABEL: Record<ModGroupId, string> = { milk: 'Sut turi', syrup: 'Sirop', shot: "Qo'shimcha shot" }

async function run(fn: () => Promise<unknown>) {
  try {
    await fn()
    await refreshMenu()
    return true
  } catch (e) {
    alert((e as Error).message)
    return false
  }
}

function Section({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-3"><h2 className="font-semibold">{title}</h2>{action}</div>
      {children}
    </section>
  )
}

export function MenuEditor() {
  useAppState()
  const [editing, setEditing] = useState<Product | 'new' | null>(null)
  const [catName, setCatName] = useState('')
  const [ing, setIng] = useState({ name: '', unit: 'g' as Unit, cost: '', min: '' })
  const role = useAppState().session?.staff.role

  return (
    <div className="space-y-5">
      <Section title={t('Mahsulotlar')} action={<button className={`${btn} flex items-center gap-1`} onClick={() => setEditing('new')}><Plus className="size-4" />{t('Yangi mahsulot')}</button>}>
        <div className="space-y-5">
          {CATEGORIES.map((c) => {
            const list = PRODUCTS.filter((p) => p.cat === c.id)
            return (
              <div key={c.id}>
                <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-stone-500">
                  {c.name}
                  {list.length === 0 && (
                    <button aria-label={t("Kategoriyani o'chirish")} onClick={() => run(() => api(`/api/categories/${c.id}`, { method: 'DELETE' }))} className="text-stone-400 hover:text-red-600"><Trash2 className="size-4" /></button>
                  )}
                </div>
                <div className="divide-y divide-stone-100 rounded-xl border border-stone-100">
                  {list.map((p) => (
                    <div key={p.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                      <span className={`min-w-32 flex-1 font-medium ${p.active ? '' : 'text-stone-400 line-through'}`}>{p.name}</span>
                      <span className="text-sm text-stone-500">{p.sizes.map((s) => `${s.label ? s.label + ' ' : ''}${fmt(s.price)}`).join(' · ')}</span>
                      <label className="flex items-center gap-1.5 text-sm">
                        <input type="checkbox" checked={!p.active} onChange={(e) => run(() => api(`/api/products/${p.id}/active`, { method: 'PATCH', body: { active: !e.target.checked } }))} className="size-4 accent-red-600" />
                        {t('Stop')}
                      </label>
                      <button onClick={() => setEditing(p)} aria-label={t('Tahrirlash')} className="rounded-lg p-2 hover:bg-stone-100"><Pencil className="size-4" /></button>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
        <form className="mt-5 flex gap-2" onSubmit={(e) => { e.preventDefault(); void run(() => api('/api/categories', { body: { name: catName } })).then((ok) => ok && setCatName('')) }}>
          <input required value={catName} onChange={(e) => setCatName(e.target.value)} placeholder={t('Yangi kategoriya nomi')} className={`${input} flex-1`} />
          <button className={btn}>{t("Qo'shish")}</button>
        </form>
      </Section>

      <Section title={t("Qo'shimchalar narxi")}>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {MODIFIERS.filter((m) => m.id !== 'milk-regular').map((m) => (
            <label key={m.id} className="flex items-center gap-2 text-sm">
              <span className="flex-1">{m.name} <span className="text-stone-400">({t(GROUP_LABEL[m.group])})</span></span>
              <input key={m.price} defaultValue={m.price} inputMode="numeric" className={`${input} w-24`}
                onBlur={(e) => { const price = Number(e.target.value.replace(/\D/g, '')); if (price !== m.price) void run(() => api(`/api/modifiers/${m.id}`, { method: 'PUT', body: { name: m.name, price } })) }} />
            </label>
          ))}
        </div>
      </Section>

      <Section title={t('Yangi xomashyo')}>
        <form className="flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault()
          void run(() => api('/api/ingredients', { body: { name: ing.name, unit: ing.unit, cost: Number(ing.cost) || 0, min: Number(ing.min) || 0 } }))
            .then((ok) => ok && setIng({ name: '', unit: 'g', cost: '', min: '' }))
        }}>
          <input required value={ing.name} onChange={(e) => setIng({ ...ing, name: e.target.value })} placeholder={t('Nomi')} className={`${input} min-w-40 flex-1`} />
          <select value={ing.unit} onChange={(e) => setIng({ ...ing, unit: e.target.value as Unit })} className={input}>
            {(Object.keys(UNIT_LABEL) as Unit[]).map((u) => <option key={u} value={u}>{t(UNIT_LABEL[u])}</option>)}
          </select>
          <input value={ing.cost} onChange={(e) => setIng({ ...ing, cost: e.target.value.replace(/[^\d.]/g, '') })} placeholder={t('1 birlik narxi')} inputMode="decimal" className={`${input} w-32`} />
          <input value={ing.min} onChange={(e) => setIng({ ...ing, min: e.target.value.replace(/\D/g, '') })} placeholder={t('Min qoldiq')} inputMode="numeric" className={`${input} w-28`} />
          <button className={btn}>{t("Qo'shish")}</button>
        </form>
        <p className="mt-2 text-xs text-stone-500">{t("Narx 1 g, 1 ml yoki 1 dona uchun yoziladi. Masalan: 1 kg kofe 260 000 so'm bo'lsa, 1 g = 260.")}</p>
      </Section>

      {editing && <ProductForm product={editing === 'new' ? null : editing} canDelete={role === 'owner' || role === 'admin'} onClose={() => setEditing(null)} />}
    </div>
  )
}

const emptySize = (): Size => ({ code: '-', label: '', price: 0, recipe: [] })

function ProductForm({ product, canDelete, onClose }: { product: Product | null; canDelete: boolean; onClose: () => void }) {
  const [name, setName] = useState(product?.name ?? '')
  const [cat, setCat] = useState(product?.cat ?? CATEGORIES[0]?.id ?? '')
  const [mods, setMods] = useState<ModGroupId[]>(product?.mods ?? [])
  const [sizes, setSizes] = useState<Size[]>(product?.sizes.map((s) => ({ ...s, recipe: s.recipe.map((l) => ({ ...l })) })) ?? [emptySize()])
  const [busy, setBusy] = useState(false)

  const updSize = (i: number, patch: Partial<Size>) => setSizes((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)))
  const save = async () => {
    setBusy(true)
    const body = { name, cat, mods, active: product?.active ?? true, sizes: sizes.map((s) => ({ ...s, code: s.label || '-', recipe: s.recipe.filter((l) => l.ing && l.qty > 0) })) }
    const ok = await run(() => (product ? api(`/api/products/${product.id}`, { method: 'PUT', body }) : api('/api/products', { body })))
    setBusy(false)
    if (ok) onClose()
  }
  const remove = async () => {
    if (product && confirm(t("{name} o'chirilsinmi?", { name: product.name })) && (await run(() => api(`/api/products/${product.id}`, { method: 'DELETE' })))) onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4" onClick={onClose}>
      <div className="flex max-h-[94dvh] w-full flex-col rounded-t-3xl bg-white sm:max-w-2xl sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-stone-200 px-5 py-4">
          <h2 className="text-lg font-bold">{product ? t('Mahsulotni tahrirlash') : t('Yangi mahsulot')}</h2>
          <button onClick={onClose} aria-label={t('Yopish')} className="rounded-lg p-2 hover:bg-stone-100"><X className="size-5" /></button>
        </div>
        <div className="space-y-4 overflow-y-auto px-5 py-4">
          <div className="grid gap-2 sm:grid-cols-2">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('Nomi')} className={input} />
            <select value={cat} onChange={(e) => setCat(e.target.value)} className={input}>
              {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            {(Object.keys(GROUP_LABEL) as ModGroupId[]).map((g) => (
              <label key={g} className="flex items-center gap-1.5">
                <input type="checkbox" className="size-4 accent-amber-600" checked={mods.includes(g)} onChange={(e) => setMods((m) => (e.target.checked ? [...m, g] : m.filter((x) => x !== g)))} />
                {t(GROUP_LABEL[g])}
              </label>
            ))}
          </div>
          {sizes.map((s, i) => {
            const cost = recipeCost(s.recipe)
            return (
              <div key={i} className="space-y-2 rounded-xl border border-stone-200 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <input value={s.label} onChange={(e) => updSize(i, { label: e.target.value.toUpperCase().slice(0, 4) })} placeholder={t("O'lcham (S/M/L)")} className={`${input} w-32`} />
                  <input value={s.volume ?? ''} onChange={(e) => updSize(i, { volume: e.target.value })} placeholder={t('Hajm (350 ml)')} className={`${input} w-32`} />
                  <input value={s.price || ''} onChange={(e) => updSize(i, { price: Number(e.target.value.replace(/\D/g, '')) })} placeholder={t('Narx')} inputMode="numeric" className={`${input} w-28`} />
                  <span className="text-xs text-stone-500">{t('Tannarx')} {fmt(cost)} · {t('marja')} {s.price ? Math.round(((s.price - cost) / s.price) * 100) : 0}%</span>
                  {sizes.length > 1 && <button onClick={() => setSizes((all) => all.filter((_, j) => j !== i))} aria-label={t("O'lchamni o'chirish")} className="ml-auto p-1 text-stone-400 hover:text-red-600"><Trash2 className="size-4" /></button>}
                </div>
                {s.recipe.map((l, li) => (
                  <div key={li} className="flex gap-2">
                    <select value={l.ing} onChange={(e) => updSize(i, { recipe: s.recipe.map((x, k) => (k === li ? { ...x, ing: e.target.value } : x)) })} className={`${input} min-w-0 flex-1`}>
                      {INGREDIENTS.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                    </select>
                    <input value={l.qty || ''} onChange={(e) => updSize(i, { recipe: s.recipe.map((x, k) => (k === li ? { ...x, qty: Number(e.target.value.replace(/[^\d.]/g, '')) } : x)) })} inputMode="decimal" className={`${input} w-20`} />
                    <button onClick={() => updSize(i, { recipe: s.recipe.filter((_, k) => k !== li) })} aria-label={t("Qatorni o'chirish")} className="p-1 text-stone-400 hover:text-red-600"><X className="size-4" /></button>
                  </div>
                ))}
                <button onClick={() => updSize(i, { recipe: [...s.recipe, { ing: INGREDIENTS[0]?.id ?? '', qty: 0 }] })} className="text-sm font-medium text-amber-700">{t("+ Xomashyo qo'shish")}</button>
              </div>
            )
          })}
          <button onClick={() => setSizes((all) => [...all, emptySize()])} className="text-sm font-medium text-amber-700">{t("+ O'lcham qo'shish")}</button>
        </div>
        <div className="flex gap-2 border-t border-stone-200 p-4">
          {product && canDelete && <button onClick={remove} className="rounded-xl px-4 py-3 text-sm font-medium text-red-600 hover:bg-red-50">{t("O'chirish")}</button>}
          <button disabled={busy || !name.trim() || !cat || sizes.some((s) => !s.price)} onClick={save} className="flex-1 rounded-xl bg-emerald-600 py-3 font-semibold text-white disabled:bg-stone-300">{t('Saqlash')}</button>
        </div>
      </div>
    </div>
  )
}

interface StaffRow { id: number; name: string; role: Role; active: boolean }

export function StaffView() {
  const me = useAppState().session?.staff
  const [list, setList] = useState<StaffRow[]>([])
  const [form, setForm] = useState({ name: '', role: 'kassir' as Role, pin: '' })
  const load = () => api<StaffRow[]>('/api/staff').then(setList).catch((e: Error) => alert(e.message))
  useEffect(() => { void load() }, [])
  const roles = (Object.keys(ROLE_LABEL) as Role[]).filter((r) => r !== 'owner' || me?.role === 'owner')

  const update = async (s: StaffRow, patch: Partial<StaffRow> & { pin?: string }) => {
    try {
      await api(`/api/staff/${s.id}`, { method: 'PUT', body: { name: s.name, role: s.role, active: s.active, ...patch } })
      await load()
    } catch (e) {
      alert((e as Error).message)
    }
  }

  return (
    <Section title={t('Xodimlar')}>
      <div className="divide-y divide-stone-100">
        {list.map((s) => (
          <div key={s.id} className="flex flex-wrap items-center gap-3 py-2.5">
            <span className={`min-w-28 flex-1 font-medium ${s.active ? '' : 'text-stone-400 line-through'}`}>{s.name}{s.id === me?.id && <span className="ml-1 text-xs text-stone-400">({t('siz')})</span>}</span>
            <select value={s.role} disabled={s.id === me?.id || (s.role === 'owner' && me?.role !== 'owner')} onChange={(e) => update(s, { role: e.target.value as Role })} className={input}>
              {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r} disabled={!roles.includes(r)}>{t(ROLE_LABEL[r])}</option>)}
            </select>
            <button onClick={() => { const pin = prompt(t('{name} uchun yangi PIN (4–6 raqam)', { name: s.name })); if (pin) void update(s, { pin }) }} className="rounded-lg border border-stone-200 px-3 py-2 text-sm">PIN</button>
            {s.id !== me?.id && (
              <button onClick={() => update(s, { active: !s.active })} className="rounded-lg border border-stone-200 px-3 py-2 text-sm">{s.active ? t("staff:O'chirish") : t('Faollashtirish')}</button>
            )}
          </div>
        ))}
      </div>
      <form className="mt-4 flex flex-wrap gap-2 border-t border-stone-100 pt-4" onSubmit={async (e) => {
        e.preventDefault()
        try {
          await api('/api/staff', { body: form })
          setForm({ name: '', role: 'kassir', pin: '' })
          await load()
        } catch (err) {
          alert((err as Error).message)
        }
      }}>
        <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={t('Ism')} className={`${input} min-w-32 flex-1`} />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })} className={input}>
          {roles.map((r) => <option key={r} value={r}>{t(ROLE_LABEL[r])}</option>)}
        </select>
        <input required minLength={4} value={form.pin} onChange={(e) => setForm({ ...form, pin: e.target.value.replace(/\D/g, '').slice(0, 6) })} placeholder="PIN" inputMode="numeric" className={`${input} w-24`} />
        <button className={btn}>{t("Qo'shish")}</button>
      </form>
    </Section>
  )
}

export function ShiftsView() {
  const [list, setList] = useState<ShiftInfo[]>([])
  useEffect(() => { api<ShiftInfo[]>('/api/shifts').then(setList).catch((e: Error) => alert(e.message)) }, [])
  return (
    <Section title={t('Smenalar tarixi')}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="text-left text-stone-500">
            <tr><th className="pb-2 font-medium">{t('Sana')}</th><th className="pb-2 font-medium">{t('Kassir')}</th><th className="pb-2 text-right font-medium">{t('Buyurtma')}</th><th className="pb-2 text-right font-medium">{t('Tushum')}</th><th className="pb-2 pl-4 font-medium">{t("To'lov turlari")}</th><th className="pb-2 text-right font-medium">{t('Naqd farqi')}</th></tr>
          </thead>
          <tbody>
            {list.map((s) => {
              const diff = s.shift.closedAt ? (s.shift.closingCash ?? 0) - (s.shift.expectedCash ?? 0) : null
              return (
                <tr key={s.shift.id} className="border-t border-stone-100">
                  <td className="py-2">{new Date(s.shift.openedAt).toLocaleDateString('ru-RU')} {time(s.shift.openedAt)}–{s.shift.closedAt ? time(s.shift.closedAt) : <span className="text-emerald-600">{t('ochiq')}</span>}</td>
                  <td className="py-2">{s.shift.staff}</td>
                  <td className="py-2 text-right">{s.orders}</td>
                  <td className="py-2 text-right font-semibold tabular-nums">{fmt(s.revenue)}</td>
                  <td className="py-2 pl-4 text-stone-500">{(Object.keys(s.byPayment) as Payment[]).map((p) => `${t(PAYMENT_LABEL[p])} ${fmt(s.byPayment[p] ?? 0)}`).join(' · ') || '—'}</td>
                  <td className={`py-2 text-right font-medium ${diff === null ? 'text-stone-400' : diff === 0 ? 'text-emerald-700' : 'text-red-600'}`}>{diff === null ? '—' : som(diff)}</td>
                </tr>
              )
            })}
            {list.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-stone-500">{t("Hali smena yo'q.")}</td></tr>}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

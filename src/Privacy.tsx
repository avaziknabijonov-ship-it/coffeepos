import { useState } from 'react'
import { api } from './api'
import { logout, useAppState } from './store'
import { getLang } from './i18n'

export default function Privacy({ onClose }: { onClose?: () => void }) {
  const support = import.meta.env.VITE_SUPPORT_EMAIL as string | undefined
  const backupDays = import.meta.env.VITE_PRIVACY_BACKUP_DAYS as string | undefined
  const ru = getLang() === 'ru'
  const { session } = useAppState()
  const [company, setCompany] = useState(session?.company.slug || '')
  const [pin, setPin] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [deleted, setDeleted] = useState(false)
  const erase = async (e: React.FormEvent) => {
    e.preventDefault()
    if (busy || !confirmed) return
    setBusy(true); setMessage('')
    try {
      const auth = await api<{ token: string; staff: { role: string } }>('/api/auth/login', { body: { company: company.trim().toLowerCase(), pin }, authToken: null })
      if (auth.staff.role !== 'owner') throw new Error(ru ? 'Нужен PIN владельца.' : 'Rahbarning PIN-kodi kerak.')
      await api('/api/account', { method: 'DELETE', body: { company: company.trim().toLowerCase(), pin }, authToken: auth.token })
      // Delete only the cafe that was explicitly authenticated, never another session.
      for (const key of Object.keys(localStorage)) {
        if (key.startsWith(`coffeepos-floor:${company.trim().toLowerCase()}:`)) localStorage.removeItem(key)
      }
      if (session?.company.slug === company.trim().toLowerCase()) logout()
      setPin(''); setDeleted(true)
      setMessage(ru ? 'Аккаунт и данные кофейни удалены.' : 'Hisob va qahvaxona ma’lumotlari o‘chirildi.')
    } catch (err) { setMessage((err as Error).message) }
    finally { setBusy(false) }
  }
  return <main className="mx-auto max-w-3xl space-y-5 p-5 text-sm leading-relaxed">
    {onClose && <button onClick={onClose} className="rounded-xl border px-4 py-3">{ru ? 'Назад' : 'Orqaga'}</button>}
    <h1 className="text-2xl font-bold">CoffeePOS — {ru ? 'Конфиденциальность' : 'Maxfiylik'}</h1>
    <p>{ru ? 'Обновлено: 17 октября 2026 г. CoffeePOS предназначен для управления продажами и складом кофейни.' : 'Yangilangan: 2026-yil 17-oktabr. CoffeePOS qahvaxona savdosi va omborini boshqarish uchun mo‘ljallangan.'}</p>
    <h2 className="text-lg font-semibold">{ru ? 'Какие данные обрабатываются' : 'Qanday ma’lumotlar ishlatiladi'}</h2>
    <p>{ru ? 'Название и логин кофейни, имена и роли сотрудников, хеши PIN-кодов, заказы, имена клиентов (если введены), телефоны участников бонусной программы, баланс и история бонусов, долги, зарплаты, смены и складские операции. Приложение не запрашивает реквизиты банковских карт: способ оплаты только записывается в отчёт.' : 'Qahvaxona nomi va logini, xodim ismlari va rollari, PIN-kod xeshlari, buyurtmalar, kiritilgan mijoz ismlari, bonus dasturi qatnashchilarining telefon raqamlari, bonus balansi va tarixi, qarzlar, ish haqi, smena va ombor amallari. Ilova bank kartasi rekvizitlarini so‘ramaydi: to‘lov usuli faqat hisobotga yoziladi.'}</p>
    <h2 className="text-lg font-semibold">{ru ? 'Использование и хранение' : 'Foydalanish va saqlash'}</h2>
    <p>{ru ? 'Данные отправляются на настроенный сервер CoffeePOS и доступны сотрудникам согласно их ролям, а также уполномоченным администраторам сервиса и поставщику хостинга для работы сервиса. На устройстве сохраняются сессия, язык, адрес сервера, схема зала и неоплаченные корзины. Текущая сборка не содержит рекламных и аналитических SDK и не продаёт персональные данные.' : 'Ma’lumotlar sozlangan CoffeePOS serveriga yuboriladi. Ulardan xodimlar o‘z roli doirasida, xizmatning vakolatli administratorlari va hosting provayderi xizmatni yuritish uchun foydalanadi. Qurilmada sessiya, til, server manzili, zal rejasi va to‘lanmagan savatlar saqlanadi. Hozirgi versiyada reklama va analitika SDK’lari yo‘q; shaxsiy ma’lumotlar sotilmaydi.'}</p>
    <p>{ru ? 'По вопросам персональных данных сотрудники могут обратиться к владельцу своей кофейни.' : 'Xodimlar shaxsiy ma’lumotlar bo‘yicha o‘z qahvaxonasi rahbariga murojaat qilishi mumkin.'}</p>
    {support && <p>{ru ? 'Оператор CoffeePOS: ' : 'CoffeePOS operatori: '}<a className="underline" href={`mailto:${support}`}>{support}</a></p>}
    <p>{backupDays ? (ru ? `Удалённые данные исключаются из резервных копий не позднее чем через ${backupDays} дней. Восстановление копий должно учитывать удалённые аккаунты.` : `O‘chirilgan ma’lumotlar zaxira nusxalaridan ko‘pi bilan ${backupDays} kun ichida chiqariladi. Nusxadan tiklashda o‘chirilgan hisoblar qayta tiklanmasligi kerak.`) : (ru ? 'Срок хранения резервных копий уточняйте у оператора вашего сервера.' : 'Zaxira nusxalar saqlash muddatini o‘z serveringiz operatoridan aniqlang.')}</p>
    <h2 className="text-lg font-semibold">{ru ? 'Удаление аккаунта владельца' : 'Rahbar hisobini o‘chirish'}</h2>
    <p>{ru ? 'Владелец может удалить аккаунт вместе со всей кофейней здесь. Это безвозвратно удаляет сотрудников, заказы, склад, долги, зарплаты и лицензионные записи из рабочей базы. Сначала сохраните необходимые отчёты. Копии на других устройствах и резервные копии требуют отдельного удаления оператором; автоматическое восстановление удалённого аккаунта недопустимо.' : 'Rahbar shu yerda hisobni butun qahvaxona bilan birga o‘chirishi mumkin. Xodimlar, buyurtmalar, ombor, qarzlar, ish haqi va litsenziya yozuvlari ishchi bazadan qaytarib bo‘lmaydigan tarzda o‘chadi. Avval kerakli hisobotlarni saqlang. Boshqa qurilmalardagi va zaxira nusxalardagi ma’lumotlar operator tomonidan alohida o‘chiriladi; o‘chirilgan hisobni avtomatik tiklash mumkin emas.'}</p>
    {!deleted && <form onSubmit={erase} className="space-y-3 rounded-2xl border border-red-200 bg-white p-4">
      <label className="block">{ru ? 'Логин удаляемой кофейни' : 'O‘chiriladigan qahvaxona logini'}<input required autoCapitalize="none" value={company} onChange={e => { setCompany(e.target.value); setConfirmed(false) }} className="mt-1 block w-full rounded-xl border p-3" /></label>
      <label className="block">{ru ? 'PIN владельца' : 'Rahbar PIN-kodi'}<input required type="password" inputMode="numeric" pattern="[0-9]{4,6}" value={pin} onChange={e => setPin(e.target.value)} className="mt-1 block w-full rounded-xl border p-3" /></label>
      <label className="flex items-start gap-3"><input required type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} className="mt-1" />{ru ? 'Подтверждаю удаление аккаунта и ВСЕХ данных этой кофейни.' : 'Hisob va shu qahvaxonaning BARCHA ma’lumotlarini o‘chirishni tasdiqlayman.'}</label>
      <button disabled={busy || !confirmed} className="rounded-xl bg-red-700 px-4 py-3 font-semibold text-white disabled:opacity-50">{busy ? (ru ? 'Удаляется…' : 'O‘chirilmoqda…') : (ru ? 'Удалить аккаунт и кофейню' : 'Hisob va qahvaxonani o‘chirish')}</button>
    </form>}
    {message && <p role="status" className="rounded-xl border p-3">{message}</p>}
  </main>
}

export type Lang = 'uz' | 'ru'

const KEY = 'coffeepos-lang'
let lang: Lang = localStorage.getItem(KEY) === 'ru' ? 'ru' : 'uz'
document.documentElement.lang = lang

export const getLang = () => lang
export function setLangValue(l: Lang) {
  lang = l
  localStorage.setItem(KEY, l)
  document.documentElement.lang = l
}

// Uzbek text is the key; "context:" keys disambiguate words that translate differently.
const UZ: Record<string, string> = { "staff:O'chirish": "O'chirish", 'cash:Berildi': 'Berildi' }

const RU: Record<string, string> = {
  'Kun': 'День',
  'Oy': 'Месяц',
  'Buyurtmalar': 'Заказы',
  'Tushum': 'Выручка',
  'Tannarx': 'Себестоимость',
  'Xarajatlar': 'Расходы',
  'Hisoblangan sof foyda': 'Чистая прибыль (расчётная)',
  'Qarzga sotuvlar (tushumga kiritilgan)': 'Продажи в долг (включены в выручку)',
  'Xarajatlar kategoriyalar bo‘yicha': 'Расходы по категориям',
  'Hisoblangan foydaga qarzga sotuvlar ham kiradi. Eski qarz qaytarilishi foydaga qayta qo‘shilmaydi.': 'Расчётная прибыль учитывает продажи в долг как выручку. Погашения старых долгов повторно в прибыль не включаются.',
  'Foyda hisoboti': 'Отчёт о прибыли',
  'Xodim': 'Сотрудник',
  'Xodimni tanlang': 'Выберите сотрудника',

  'expense:Tozalash': 'Уборка',
  'g': 'г',
  'ml': 'мл',
  'kg': 'кг',
  'l': 'л',
  'Jami': 'Итого',
  'Qaytarildi': 'Погашено',
  'Bekor': 'Отмена',
  'Transport': 'Транспорт',
  'Kommunal': 'Коммунальные услуги',
  'Ta’mirlash': 'Ремонт',
  'naqd': 'Наличные',
  'karta': 'Карта',
  'To‘lovlar yo‘q': 'Платежей нет',
  'Naqd chiqim ochiq smenadan ayriladi. Bu xarajat ombor qoldig‘ini avtomatik oshirmaydi.': 'Наличные расходы вычитаются из открытой смены. Расход не увеличивает остатки склада автоматически.',
  'Necha kun ishladi?': 'Сколько дней отработано?',
  'Summani kiriting': 'Введите сумму',
  'Izoh (ixtiyoriy)': 'Примечание (необязательно)',

  'Qarzdan qaytarilgan': 'Погашение долгов',
  'Naqd chiqimlar': 'Расходы наличными',
  'Izoh': 'Примечание',
  'Izohsiz': 'Без примечания',
  'Nimaga sarflandi?': 'На что потрачено?',
  'Ish kunlari': 'Рабочие дни',
  'Qarz': 'Долг',

  'Kategoriya nomi': 'Название категории', 'Nomini o‘zgartirish': 'Переименовать', Yuqoriga: 'Выше', Pastga: 'Ниже',
  Oylik: 'Зарплата', Qarzlar: 'Долги', 'Kunlik chiqimlar': 'Ежедневные расходы',
  'Xodimlar oyligi': 'Зарплата сотрудников', Kunlik: 'Посуточно', Stavka: 'Ставка',
  'Ish kunlari:': 'Рабочие дни:', 'Hisoblandi:': 'Начислено:', 'To‘landi:': 'Выплачено:', 'Qoldiq:': 'Остаток:',
  '+ Ish kuni': '+ Рабочий день', '+ Bonus': '+ Бонус', Ushlanma: 'Удержание', Avans: 'Аванс', 'Oylik to‘landi': 'Выплата зарплаты',
  'Qarzlar ro‘yxati': 'Список долгов', 'Qarz to‘lash': 'Погасить долг', 'To‘lovlar tarixi': 'История платежей',
  'Rasm yuklash': 'Загрузить фото', 'Rasmni olib tashlash': 'Удалить фото',
  'Summa (so‘m)': 'Сумма (сум)', 'To‘lov turi': 'Способ оплаты', 'Chiqimni saqlash': 'Сохранить расход',
  'Bu kunda chiqim yo‘q.': 'За этот день расходов нет.',
  Kassa: 'Касса', Barista: 'Бариста', 'Mijoz ekrani': 'Экран клиента', Admin: 'Админ', 'Yuklanmoqda…': 'Загрузка…',
  "Server bilan aloqa yo'q": 'Нет связи с сервером', "Aloqa yo'q": 'Нет связи', 'Smena ochiq': 'Смена открыта', 'Smena yopiq': 'Смена закрыта',
  'Tizimdan chiqilsinmi?': 'Выйти из системы?', Chiqish: 'Выход',
  Rahbar: 'Руководитель', Administrator: 'Администратор', Kassir: 'Кассир',
  Naqd: 'Наличные', Karta: 'Карта',
  Yangi: 'Новый', Tayyorlanmoqda: 'Готовится', Tayyor: 'Готово', Berildi: 'Выдан', Boshlash: 'Начать',
  dona: 'шт', "so'm": 'сум',
  'Kofe bar logini': 'Логин кофейни', 'PIN-kod': 'PIN-код', Tozalash: 'Очистить', "O'chirish": 'Удалить',
  'Kirilmoqda…': 'Вход…', Kirish: 'Войти', 'Demo PIN: 1111 rahbar · 2222 kassir · 3333 barista': 'Демо PIN: 1111 руководитель · 2222 кассир · 3333 бариста',
  "Yangi kofe barni ro'yxatdan o'tkazish": 'Зарегистрировать новую кофейню', 'Yangi kofe bar': 'Новая кофейня', 'Kofe bar nomi': 'Название кофейни',
  'Login (masalan: bek-coffee)': 'Логин (например: bek-coffee)', 'Kirishda ishlatiladi: lotin harflari, raqam va "-"': 'Используется для входа: латинские буквы, цифры и «-»',
  'Rahbar ismi': 'Имя руководителя', 'Rahbar PIN-kodi (4–6 raqam)': 'PIN руководителя (4–6 цифр)', 'Yaratilmoqda…': 'Создание…', Yaratish: 'Создать',
  "Standart kofe menyusi, texkartalar va ombor avtomatik qo'shiladi, keyin Admin bo'limida o'zgartirasiz.": 'Стандартное кофейное меню, техкарты и склад добавятся автоматически, потом их можно изменить в разделе «Админ».',
  Orqaga: 'Назад',
  "Kassadagi boshlang'ich naqd pul": 'Начальная наличность в кассе', 'Smenani ochish': 'Открыть смену', 'Smenani kassir yoki administrator ochadi.': 'Смену открывает кассир или администратор.',
  Ochilgan: 'Открыта', Buyurtmalar: 'Заказы', Tushum: 'Выручка', "Boshlang'ich naqd": 'Начальная наличность', "Kassada bo'lishi kerak": 'Должно быть в кассе',
  '{n} ta': '{n} шт', 'Smena yopilsinmi?': 'Закрыть смену?', 'Smena yopildi': 'Смена закрыта', 'Smena (X-hisobot)': 'Смена (X-отчёт)', Yopish: 'Закрыть',
  "Ochiq smena yo'q.": 'Нет открытой смены.', Sanalgan: 'Пересчитано', Farq: 'Разница', 'Kassada sanalgan naqd pul': 'Пересчитанная наличность в кассе',
  'Smenani yopish (Z-hisobot)': 'Закрыть смену (Z-отчёт)',
  "Buyurtma yo'q": 'Заказов нет', 'Tayyor — olib keting': 'Готово — заберите',
  'Mahsulot qidirish': 'Поиск товара', Smena: 'Смена', Stop: 'Стоп', '{p} dan': 'от {p}', 'Hech narsa topilmadi.': 'Ничего не найдено.', Savat: 'Корзина',
  'Yangi buyurtma': 'Новый заказ', 'Mijoz ismi (stakan uchun)': 'Имя клиента (для стакана)', "Savat bo'sh. Mahsulotni tanlang.": 'Корзина пуста. Выберите товар.',
  Kamaytirish: 'Уменьшить', "Ko'paytirish": 'Увеличить', Chegirma: 'Скидка', "Yo'q": 'Нет', 'Oraliq summa': 'Промежуточная сумма', "To'lov": 'Оплата',
  Hajm: 'Объём', 'Sut turi': 'Молоко', Sirop: 'Сироп', 'bir nechtasini tanlash mumkin': 'можно выбрать несколько', "Qo'shimcha espresso": 'Дополнительный эспрессо',
  "Qo'shish": 'Добавить', "To'lanadigan summa": 'К оплате', 'Mijoz bergan summa': 'Сумма от клиента', Qaytim: 'Сдача', Yetmaydi: 'Не хватает',
  "To'lovni ilovada tekshirib, qo'lda tasdiqlang. QR va avtomatik tasdiqlash keyingi versiyada.": 'Проверьте оплату в приложении и подтвердите вручную. QR и автоподтверждение — в следующей версии.',
  Tasdiqlash: 'Подтвердить', 'Buyurtma #{n} qabul qilindi': 'Заказ #{n} принят', 'Barista ekraniga yuborildi': 'Отправлен на экран бариста', Mijoz: 'Клиент',
  JAMI: 'ИТОГО', 'cash:Berildi': 'Получено', 'Rahmat! Yana keling.': 'Спасибо! Ждём вас снова.', Chek: 'Чек',
  Dashboard: 'Дашборд', Ombor: 'Склад', Inventarizatsiya: 'Инвентаризация', Menyu: 'Меню', Texkarta: 'Техкарта', Xodimlar: 'Сотрудники', Smenalar: 'Смены',
  '{n} ta mahsulot tugayapti:': 'Заканчивается позиций: {n}.', "Omborga o'tish": 'Перейти на склад', 'Bugungi tushum': 'Выручка за сегодня', "O'rtacha chek": 'Средний чек',
  'Yalpi foyda': 'Валовая прибыль', marja: 'маржа', "Soatlar bo'yicha tushum (bugun)": 'Выручка по часам (сегодня)', 'Haftalik tushum': 'Выручка за неделю', Bugun: 'Сегодня',
  Ya: 'Вс', Du: 'Пн', Se: 'Вт', Ch: 'Ср', Pa: 'Чт', Ju: 'Пт', Sh: 'Сб',
  "O'tgan kunlar — namuna ma'lumot.": 'Прошлые дни — демо-данные.', 'Top mahsulotlar (bugun)': 'Топ товаров (сегодня)', Mahsulot: 'Товар', Soni: 'Кол-во', Foyda: 'Прибыль',
  "To'lov turlari (bugun)": 'Способы оплаты (сегодня)', 'Ombor qoldiqlari': 'Остатки на складе',
  "Har bir sotuvda texkarta bo'yicha avtomatik ayiriladi. Kirim qilish uchun miqdorni yozing.": 'Списывается автоматически по техкарте при каждой продаже. Для прихода введите количество.',
  Xomashyo: 'Сырьё', Qoldiq: 'Остаток', 'Bugun sarf': 'Расход сегодня', Tannarx: 'Себестоимость', Holat: 'Статус', Kirim: 'Приход', 'Kam (min {n})': 'Мало (мин {n})',
  Yetarli: 'Достаточно', "Menyu bo'sh.": 'Меню пусто.', 'Sotuv narxi': 'Цена продажи', Marja: 'Маржа',
  "Qo'shimchalar texkartani avtomatik o'zgartiradi:": 'Добавки автоматически меняют техкарту:',
  "Masalan, bodom suti oddiy sut o'rniga ayiriladi, sirop +15 ml, +1 shot +9 g kofe.": 'Например, миндальное молоко списывается вместо обычного, сироп +15 мл, +1 шот +9 г кофе.',
  'Bugungi buyurtmalar ({n})': 'Заказы за сегодня ({n})', Vaqt: 'Время', Tarkib: 'Состав', Summa: 'Сумма',
  Mahsulotlar: 'Товары', 'Yangi mahsulot': 'Новый товар', "Kategoriyani o'chirish": 'Удалить категорию', Tahrirlash: 'Редактировать', 'Yangi kategoriya nomi': 'Название новой категории',
  "Qo'shimchalar narxi": 'Цены добавок', 'Yangi xomashyo': 'Новое сырьё', Nomi: 'Название', '1 birlik narxi': 'Цена за 1 ед.', 'Min qoldiq': 'Мин. остаток',
  "Narx 1 g, 1 ml yoki 1 dona uchun yoziladi. Masalan: 1 kg kofe 260 000 so'm bo'lsa, 1 g = 260.": 'Цена указывается за 1 г, 1 мл или 1 шт. Например: если 1 кг кофе стоит 260 000 сум, то 1 г = 260.',
  "Qo'shimcha shot": 'Доп. шот', "{name} o'chirilsinmi?": 'Удалить «{name}»?', 'Mahsulotni tahrirlash': 'Редактирование товара', "O'lcham (S/M/L)": 'Размер (S/M/L)',
  'Hajm (350 ml)': 'Объём (350 мл)', Narx: 'Цена', "O'lchamni o'chirish": 'Удалить размер', "Qatorni o'chirish": 'Удалить строку', "+ Xomashyo qo'shish": '+ Добавить сырьё',
  "+ O'lcham qo'shish": '+ Добавить размер', Saqlash: 'Сохранить', siz: 'вы', '{name} uchun yangi PIN (4–6 raqam)': 'Новый PIN для {name} (4–6 цифр)',
  "staff:O'chirish": 'Отключить', Faollashtirish: 'Включить', Ism: 'Имя', 'Smenalar tarixi': 'История смен', Sana: 'Дата', Buyurtma: 'Заказы',
  "To'lov turlari": 'Способы оплаты', 'Naqd farqi': 'Разница наличных', ochiq: 'открыта', "Hali smena yo'q.": 'Смен пока нет.',
  Sanash: 'Пересчёт', 'Hisobdan chiqarish': 'Списание', Tarix: 'История', 'Kamomad hisoboti': 'Отчёт о недостаче',
  "To'kildi / isrof": 'Пролито / потери', "Muddati o'tdi": 'Истёк срок', 'Xodim ichdi': 'Выпил сотрудник', 'Buzildi / sindi': 'Испорчено / разбито', Boshqa: 'Другое',
  "{n} ta xomashyo qoldig'i sanalgan miqdorga to'g'rilanadi. Davom etamizmi?": 'Остатки {n} позиций будут исправлены на пересчитанные. Продолжить?',
  'Inventarizatsiya: sanash': 'Инвентаризация: пересчёт',
  "Har bir xomashyoning haqiqiy qoldig'ini sanab yozing. Bo'sh qolgan qatorlar o'zgarmaydi.": 'Пересчитайте и введите фактический остаток. Пустые строки не изменятся.',
  Dasturda: 'В системе', Sanaldi: 'Факт', 'Sanalgan xomashyo': 'Пересчитано позиций', Kamomad: 'Недостача', Ortiqcha: 'Излишек',
  'Izoh (masalan: oy oxiri)': 'Комментарий (например: конец месяца)', "Qolganini dasturdagidek to'ldirish": 'Заполнить остальные как в системе',
  "To'kilgan, buzilgan yoki muddati o'tgan xomashyoni sababi bilan yozing.": 'Укажите пролитое, испорченное или просроченное сырьё с причиной.',
  Miqdor: 'Кол-во', Sabab: 'Причина', Chiqarish: 'Списать', Zarar: 'Ущерб', 'Oxirgi 30 kun': 'Последние 30 дней', Kim: 'Кто', "Hisobdan chiqarish yo'q.": 'Списаний нет.',
  'Inventarizatsiyalar tarixi': 'История инвентаризаций', "Hali inventarizatsiya o'tkazilmagan.": 'Инвентаризаций пока не было.',
  '{n} ta sanaldi, {m} tasida farq': 'пересчитано {n}, расхождений {m}', '{n} kun': '{n} дн.', 'Hisobdan chiqarildi': 'Списано',
  'Kamomad ({n} ta inventarizatsiya)': 'Недостача (инвентаризаций: {n})', "Jami yo'qotish": 'Итого потери', 'Hisobdan chiqarish sabablari': 'Причины списания',
  "Bu davrda hisobdan chiqarish yo'q.": 'За этот период списаний нет.', "Xomashyo bo'yicha": 'По сырью',
  "Sanashdagi farq: manfiy bo'lsa kamomad, musbat bo'lsa ortiqcha.": 'Разница при пересчёте: минус — недостача, плюс — излишек.',
  Chiqarildi: 'Списано', 'Sanashdagi farq': 'Разница пересчёта', "Ma'lumot yo'q.": 'Нет данных.',
  "Server bilan aloqa yo'q. Internetni tekshiring": 'Нет связи с сервером. Проверьте интернет', 'Xato ({n})': 'Ошибка ({n})',
  "Ma'lumotlar noto'g'ri to'ldirilgan": 'Данные заполнены неверно',
  'Avval smenani oching': 'Сначала откройте смену', 'Berilgan pul yetarli emas': 'Полученной суммы недостаточно', 'Bu PIN band': 'Этот PIN занят',
  "Bu amal uchun ruxsat yo'q": 'Нет прав на это действие', 'Bu login band, boshqasini tanlang': 'Этот логин занят, выберите другой',
  "Bunday chegirma uchun ruxsat yo'q": 'Нет прав на такую скидку', "Faqat rahbar rahbar qo'sha oladi": 'Только руководитель может добавить руководителя',
  'Kategoriyada mahsulotlar bor': 'В категории есть товары', "Ko'p urinish. 5 daqiqadan keyin qayta urining": 'Слишком много попыток. Повторите через 5 минут',
  "Kofe bar yoki PIN noto'g'ri": 'Неверная кофейня или PIN', 'Mahsulot topilmadi': 'Товар не найден', "Miqdor musbat bo'lsin": 'Количество должно быть больше нуля',
  "Miqdor noto'g'ri": 'Неверное количество', 'O\'lchamlar takrorlanmasin': 'Размеры не должны повторяться',
  "O'zingizning rolingizni o'zgartira olmaysiz": 'Нельзя изменить свою роль', "Ochiq smena yo'q": 'Нет открытой смены', 'PIN kerak': 'Нужен PIN',
  'Qaytadan kiring': 'Войдите заново', "Qoldiq manfiy bo'lmaydi": 'Остаток не может быть отрицательным', 'Smena allaqachon ochiq': 'Смена уже открыта',
  "Texkartada noma'lum xomashyo": 'В техкарте неизвестное сырьё', Topilmadi: 'Не найдено', 'Xomashyo takrorlangan': 'Сырьё повторяется',
}

const RU_PATTERNS: [RegExp, string][] = [
  [/^Xomashyo topilmadi: (.*)$/, 'Сырьё не найдено: $1'],
  [/^(.*) stop-listda$/, '$1 в стоп-листе'],
  [/^(.*): bitta guruhdan bitta tanlanadi$/, '$1: из группы выбирается только один вариант'],
  [/^(.*): o'lcham topilmadi$/, '$1: размер не найден'],
  [/^(.*): qo'shimcha mos emas$/, '$1: добавка не подходит'],
]

export function t(key: string, vars?: Record<string, string | number>): string {
  let s = (lang === 'ru' ? RU[key] : UZ[key]) ?? key
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v))
  return s
}

/** Translate a server error message (Uzbek) into the current language. */
export function tServer(msg: string): string {
  if (lang !== 'ru') return msg
  if (RU[msg]) return RU[msg]
  for (const [re, out] of RU_PATTERNS) if (re.test(msg)) return msg.replace(re, out)
  return msg
}

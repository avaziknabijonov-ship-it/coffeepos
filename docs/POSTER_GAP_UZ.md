# Poster → CoffeePOS: yetishmayotgan imkoniyatlar (2026-11-27)

Manba: `coffee40.joinposter.com` admin paneli (menyu bo‘limlari + «Все приложения» katalogi).
Faqat **funksiya ro‘yxati** olinadi; Poster kodi, dizayni, matnlari va brendi ko‘chirilmaydi (qarang: `COMPETITOR_MODULE_PLAN_UZ.md`).

Belgilar: ✅ CoffeePOS’da bor · 🟡 qisman · ❌ yo‘q

## 1. Admin panel bo‘limlari

| Poster bo‘limi | Nima qiladi | CoffeePOS | Ustuvorlik |
|---|---|---|---|
| Статистика → Продажи | Davr bo‘yicha savdo | ✅ `/reports/daily`, Dashboard | — |
| Статистика → Товары / Категории | Mahsulot va kategoriya kesimida savdo | ✅ Savdo tahlili | — |
| Статистика → ABC-анализ | Mahsulotlarni daromad ulushi bo‘yicha A/B/C guruhlash | ✅ Admin → Savdo tahlili | — |
| Статистика → Сотрудники | Kassir/barista bo‘yicha savdo | ✅ Savdo tahlili | — |
| Статистика → Чеки | Chek tarixi, filtr | ✅ `/orders/history` | — |
| Статистика → Оплаты | Naqd/karta/QR bo‘yicha taqsimot | ✅ Savdo tahlili | — |
| Статистика → Клиенты | Mijozlar bo‘yicha savdo | 🟡 bonus mijozlari bor | P1 |
| Статистика → Цехи / Столы / Налоги / Отзывы | Sex, stol, soliq, sharhlar | ❌ | P2 |
| Финансы → Транзакции, Счета | Pul hisoblari (kassa, bank, karta) va ular orasidagi o‘tkazmalar | 🟡 faqat xarajat | P1 |
| Финансы → Cash flow | Kirim/chiqim oqimi | 🟡 `/reports/finance` | P1 |
| Финансы → Кассовые смены | Smena tarixi | ✅ | — |
| Финансы → Зарплата | Oylik hisoblash | ✅ Payroll | — |
| Финансы → Категории | Xarajat kategoriyalari | 🟡 | P1 |
| Финансы → P&L | Foyda/zarar hisoboti | 🟡 «taxminiy foyda» | P1 |
| Меню → Товары, Тех. карты, Ингредиенты | Mahsulot, texkarta, xomashyo | ✅ | — |
| Меню → Полуфабрикаты | Yarim tayyor mahsulot (sirop, krem) o‘z texkartasi bilan | ✅ Admin → Polufabrikatlar | — |
| Меню → Контроль фудкоста | Tannarx % ni kuzatish, oshib ketsa ogohlantirish | ❌ | P1 |
| Меню → Цехи | Buyurtmani bar/oshxonaga bo‘lish | ❌ (Barista bitta navbat) | P2 |
| Склад → Остатки | Joriy qoldiq | ✅ | — |
| Склад → Поставки, Поставщики | Nakladnoy, yetkazib beruvchi | ✅ / 🟡 | P1 (qarz, narx tarixi) |
| Склад → Списания | Sababli hisobdan chiqarish | 🟡 `writeoff` | P1 (sabablar ro‘yxati) |
| Склад → Перемещения, Склады | Bir nechta ombor va ular orasida transfer | ❌ | P1 (multi-filial) |
| Склад → Переработки, Фасовки | Xomashyoni qayta ishlash / qadoqlash | ❌ | P2 |
| Склад → Инвентаризации | Inventarizatsiya | ✅ | — |
| Склад → Отчёт по движению | Davr bo‘yicha ombor harakati | 🟡 `/stock/moves` | P1 |
| Маркетинг → Клиенты, Группы | Mijoz bazasi va guruhlar (VIP, xodim) | 🟡 | P1 |
| Маркетинг → Программы лояльности | Bonus/chegirma dasturi | ✅ bonus | — |
| Маркетинг → Акции, Исключения | Vaqt/kun/mahsulot bo‘yicha aksiyalar (happy hour, 2+1) | ✅ foizli aksiyalar (2+1 hali yo‘q) | P2 |
| Доступ → Сотрудники, Должности | Xodimlar va rollar | ✅ | — |
| Доступ → Сессии пользователей | Faol sessiyalarni ko‘rish/chiqarish | ❌ | P1 (xavfsizlik) |
| Доступ → Кассы, Заведения | Qurilmalar va filiallar | 🟡 | P1 |
| Настройки → Чек | Chek shabloni (logo, matn, QR) | 🟡 printer sozlamasi | P1 |
| Настройки → Безопасность | Bekor qilish/chegirma uchun PIN talab | 🟡 | P1 |

## 2. Ilovalar katalogidan CoffeePOS’ga foydali modullar

| Poster ilovasi | G‘oya | Ustuvorlik |
|---|---|---|
| Стоп-лист на кассе | Tugagan mahsulot kassada avtomatik bloklanadi (qoldiq 0 bo‘lsa) | ✅ Ombor → Avtomatik stop-list |
| Уведомления об остатках | Minimal qoldiqdan tushganda ogohlantirish (Telegram) | ✅ Ombor → Telegram ogohlantirish |
| Списания на кассе | Kassir smenada to‘kilgan/buzilgan mahsulotni hisobdan chiqaradi | P1 |
| Производство на кассе | Polufabrikatni kassada tayyorlash (sirop qaynatish) | ✅ Kassa → Polufabrikat |
| Удаление чеков на кассе | Rahbar PIN bilan chekni bekor qilish | ✅ cancel/refund bor |
| Отчет по рисковым чекам | Shubhali cheklar: ko‘p bekor qilish, katta chegirma, to‘lovsiz yopish | ✅ Savdo tahlili → Shubhali cheklar |
| Отчет по себестоимости | Yetkazib beruvchi bo‘yicha tannarx dinamikasi | P1 |
| Расширенный отчёт по движению | Soatbay ombor harakati | P2 |
| Poster Boss | Rahbar uchun mobil read-only dashboard | P1 |
| Уведомления об онлайн-заказах / Telegram Mini App | Telegram orqali buyurtma va bildirishnoma | P2 |
| Табло заказов | Mijozga «tayyor» buyurtmalar ekrani | P1 (`Display.tsx` bor — tekshirish) |
| Kitchen Kit | Qog‘oz o‘rniga barista ekrani | ✅ Barista |
| QR-код на чек | Chekka QR (Instagram, sharh, Wi‑Fi) | P1 — oson |
| Poster QR / Hey Waiter! | QR-menyu, sharh, ofitsiantni chaqirish | P2 |
| Чек-листы | Xodim uchun kunlik ochish/yopish checklist | ✅ Kassa → Checklist |
| Регулярные платежи | Ijara, kommunal to‘lov eslatmasi + avtomatik xarajat | ✅ Admin → Doimiy to‘lovlar |
| Кастомный % за обслуживание | Xizmat haqi % | P2 |
| Печать тех. карт | Texkartani chop etish (barista uchun) | P2 |
| Печать ценников | Narx yorlig‘i PDF | P2 |
| Весы CAS / Toledo | Tarozi integratsiyasi | P2 (`test_scale.py` bor) |
| Multikassa | O‘zbekiston fiskalizatsiyasi | **P0** (litsenziyali provayder orqali) |
| Rahmat / QR✓OK | UzQR to‘lov + choy puli | P1 (Click/Payme/Uzum adapter) |
| Nonbor, Kwaaka, GetOrder | Yetkazib berish agregatorlari | P2 |

## 3. Tavsiya etilgan navbat

1. ~~Polufabrikatlar + avtomatik stop-list + minimal qoldiq ogohlantirishi~~ — bajarildi (2026-11-27).
2. **Fiskalizatsiya** adapteri (Multikassa yoki boshqa sertifikatlangan provayder).
3. ~~Aksiyalar~~ — bajarildi; kombo (2+1) va mijoz guruhlari qoldi.
4. **Hisoblar (kassa/bank/karta) + P&L + cash flow** ni bitta moliya modulida.
5. ~~ABC-analiz, xodim/to‘lov turi kesimidagi hisobotlar, riskli cheklar~~ — bajarildi.
6. ~~Xodim checklistlari, doimiy to‘lov eslatmalari~~ — bajarildi; chekdagi QR qoldi.
7. Ko‘p ombor + transfer (multi-filial bilan birga).

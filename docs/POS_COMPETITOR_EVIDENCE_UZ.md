# CoffeePOS: 5 POS bilan dalilli taqqoslash (23 modul)

Tekshirilgan sana: 2026-10-27. Manba — faqat rasmiy yordam markazlari / API hujjatlari (iiko uchun rasmiy hujjat va hamkor qo‘llanmasi alohida belgilangan). Real akkauntlarda sinov qilinmagan. «—» = shu tekshiruvda rasmiy dalil topilmadi (funksiya yo‘q degani emas). Tarif, region va versiyaga qarab farq bor. CoffeePOS ustuni — shu branch'dagi kod va avtomatik test holati (`docs/POS_23_PROGRESS_UZ.md`), real staging qabul emas.

Qoida: boshqa POS dizayni yoki kodi ko‘chirilmaydi; benchmark faqat qabul mezonini aniqlash uchun.

## Modul bo‘yicha jadval

| № | Modul | Toast | Lightspeed | Square | Loyverse | iiko | CoffeePOS qarori / holati |
|---|---|---|---|---|---|---|---|
| 1 | Split payment | Item/seat/payment bo‘yicha split [T1] | — | Split tender to‘liq summa qoplanmaguncha yopilmaydi [S1] | — | — | Square kabi: `partial` holat, qoldiq qoplanmaguncha `paid` emas; clientKey bilan takror to‘lov yo‘q |
| 2 | Refund | Void (capture'gacha) va refund (capture'dan keyin, asl to‘lov usuliga) ajratilgan; ruxsat 3.8/3.32 [T2][T3] | — | — | Item/miqdor bo‘yicha refund [L1] | — | Asl to‘lovga bog‘langan qisman/to‘liq refund, ortiqcha refund taqiq, manager RBAC, stock/bonus/fiscal reversal |
| 3 | Tannarx | — | — | — | Inventory valuation (paid) [L2] | Sotuvda «акт реализации» orqali ombordan yechish [I1] | Ingredient/retsept snapshot; eski order tannarxi o‘zgarmaydi |
| 4 | Low stock | — | — | Joylashuv bo‘yicha threshold, har joylashuvga alohida alert [S2] | Kunlik low-stock xabari [L3] | — | Filial+ingredient threshold, dedupe notification |
| 5 | P&L | — | Ko‘p nuqta hisobotlari [LS1] | — | — | Moliya/hisobot ekotizimi (umumiy) [I2] | Sotuv − refund − COGS − xarajat − ish haqi, filial/sana filtri; soliq hisobi emas |
| 6 | Audit | Voids by server/approver, void user/approver hisobotlari [T4] | — | Team member Activity Log: refund, chegirma, void [S3] | — | — | Append-only audit: actor/action/before-after; sirlar allowlist orqali chiqarilmaydi |
| 7 | Fiscal | — (UZ talabi) | — | — | — | Fiskal registrator plagin API, OFD holati, offline rejim maydonlari [I3]; birinchi ulanishda nofiskal rejim [I4] | iiko kabi provider-neutral adapter + nofiskal/sandbox holat; majburiy rejimda fail-closed. **Real OFD — bloklangan** |
| 8 | Backup | — | — | — | — | — | Shifrlangan pg_dump, retention, restore drill (CI). **Offsite — bloklangan** |
| 9 | Draft orders | Open check'lar [T5] | Order hold qilinadi [LS2] | — | — | — | Serverda draft, versiya konflikti, checkoutgacha tushum yo‘q |
| 10 | Tables | Service area/table setup, move order, combine (faqat Open check) [T5][T6] | Table profillari [LS3] | — | — | — | Zal/stol, occupancy, move/merge (manager), takeaway; to‘langan draft merge qilinmaydi |
| 11 | Stock transfer | — | L-Series'da nuqtalararo stock management yo‘q deb yozilgan [LS4] | Transfer stock, unique transfer raqami, history [S4] | Transfer order: draft yoki create — yaratishda manbadan darhol yechiladi [L4] | Ichki ko‘chirish hujjati [I1] | Dispatch → in_transit → receive; ikki filial ledger atomik; ikki marta receive rad |
| 12 | Inventory variance | — | — | — | Inventory count: kutilgan vs haqiqiy, kamomad/ortiqcha [L2] | Inventarizatsiya hujjati, сличительная ведомость (hamkor qo‘llanmasi) [I5] | Kutilgan/sanalgan, signed adjustment, approval/reject |
| 13 | Cash variance | — | — | Expected cash = opening + cash payments − cash refunds + paid in − paid out [S5] | Z-report: expected vs actual, farq; kassirdan expected yashirish mumkin [L5] | — | Opening + naqd sotuv − naqd refund − naqd xarajat; farq va actor |
| 14 | Staff analytics | — | — | Team sales report, xodim bo‘yicha chegirma/refund [S3] | — | — | staff_id bo‘yicha (ism kolliziyasiz) order/sotuv/chegirma/refund/smena |
| 15 | Telegram director | — | — | — | Shift report email avtomatizatsiyasi (blog) [L6] | — | Lokal talab: opt-in tenant chat, outbox+retry. **Real bot — bloklangan** |
| 16 | E-receipt | Text/email/show on device [T4] | — | Email/SMS digital receipt; kontakt sotuvchiga ko‘rsatilmaydi [S6] | Email receipt [L7] | — | Imzolangan qisqa muddatli link; fiskal/nofiskal/sandbox aniq; PII minimal |
| 17 | Happy Hour | Time-specific price (schedule) [T7] | Happy hour order profile + price list jadvali [LS3][LS5] | — | — | — | Lokal TZ, tungi jadval, ustuvorlik, chegirma limiti, filial |
| 18 | Customer analytics | — | — | — | Mijoz xarid tarixi [L8] | — | Consent, takroriy tashrif, kogorta, PII o‘chirish (buxgalteriya saqlanadi) |
| 19 | Combo | — | Combo o‘z SKU'si + guruhlar [LS5][LS6] | — | — | — | Combo komponent SKU, ingredient bir marta yechiladi, refundda reversal |
| 20 | Offline | Offline rejim cheklovlari [T8] | Lokal tarmoqda order davom etadi; internetsiz terminal ishlamaydi [LS7] | Offline to‘lovlar qayta ulanishda yuboriladi, qurilma limiti [S7] | — | Offline kassa lokal saqlaydi, keyin navbat bilan sinx (hamkor manbasi) [I6] | Faqat naqd, durable navbat, idempotency, konflikt → manager; soxta fiskal chek yo‘q |
| 21 | Device management | Toast Guardian MDM: minimal versiya, Device Hub [T9] | Menyuni qurilmaga biriktirish [LS5] | Device code: qurilmani joylashuvga bog‘lash, Forget device [S8] | — | — | Hashed device token, filial binding, revoke, last seen |
| 22 | Updates | Touchless tungi update, majburiy minimal versiya [T9][T10] | — | — | — | — | Semver, staged rollout, rollback, min versiya (426). **APK imzo — bloklangan** |
| 23 | Loyalty | Offline'da loyalty cheklangan [T8] | — | Refundda ballar proporsional olib tashlanadi; idempotency key [S9][S10] | 1 ball = 1 valyuta, barcha do‘konlarda [L9] | Bonus dasturi: % hisoblash, to‘lov limiti [I7] | Ledger, accrual/redeem, refundda proporsional reversal, lock bilan parallel himoya |

## Takrorlamaslik bo‘yicha qarorlar
- Square/Loyverse'dagi kabi transferni yaratishda darhol yechish o‘rniga, CoffeePOS `in_transit` holatini saqlaydi — qabul qiluvchi filial tasdiqlamaguncha qoldiq qabul qilinmaydi.
- Toast kabi void va refund ajratiladi: draft (to‘lanmagan) o‘chiriladi, to‘langan order faqat refund orqali qaytariladi.
- Square kabi refundda bonus proporsional qaytariladi; Loyverse'dagi qo‘lda ball tahriri o‘rniga ledger yozuvi.
- iiko kabi fiskal provayder adapter orqali ulanadi; O‘zbekiston OFD talablari provayder hujjatisiz implementatsiya qilinmaydi.

## Manbalar
- [T1] https://support.toasttab.com/en/article/Splitting-Checks-by-Item-1492811097734
- [T2] https://support.toasttab.com/en/article/Understand-when-to-void-vs-refund
- [T3] https://support.toasttab.com/en/article/Issuing-a-Refund
- [T4] https://support.toasttab.com/en/article/Using-the-Sales-Exception-Report-to-Identify-Voided-Payments-and-Items-for-Re-Opened-Checks
- [T5] https://support.toasttab.com/en/article/Creating-Service-Areas-and-Table-Setup-1493049150430
- [T6] https://support.toasttab.com/en/article/Transferring-Items-Checks-and-Payments
- [T7] https://doc.toasttab.com/openapi/menus/tag/Data-definitions/schema/TimeSpecificPrice/
- [T8] https://support.toasttab.com/en/article/Using-Toast-in-Offline-Mode
- [T9] https://support.toasttab.com/en/article/Toast-Guardian-Device-Security-and-App-Management-Overview
- [T10] https://support.toasttab.com/en/article/Installing-a-Required-Toast-Update-1493052766385
- [LS1] https://www.lightspeedhq.com/pos/restaurant/multilocation-restaurant-pos/
- [LS2] https://k-series-support.lightspeedhq.com/hc/en-us/articles/53028167251867-Offline-POS-functionality
- [LS3] https://k-series-support.lightspeedhq.com/hc/en-us/articles/4407098296091-Managing-Order-Anywhere-service-profiles
- [LS4] https://resto-support.lightspeedhq.com/hc/en-us/articles/360011424154-Using-multi-location-establishments
- [LS5] https://k-series-support.lightspeedhq.com/hc/en-us/articles/1260804647349-About-menus-and-items
- [LS6] https://k-series-support.lightspeedhq.com/hc/en-us/articles/1260804656529-About-combos
- [LS7] https://k-series-support.lightspeedhq.com/hc/en-us/articles/53028167251867-Offline-POS-functionality
- [S1] https://squareup.com/help/us/en/article/5097-process-split-tender-payments-with-square
- [S2] https://squareup.com/help/us/en/article/8333-create-inventory-alerts
- [S3] https://squareup.com/ie/en/point-of-sale/features/team-management
- [S4] https://squareup.com/help/us/en/article/8254-transfer-stock-between-locations-with-square-for-retail
- [S5] https://developer.squareup.com/reference/square/objects/CashDrawerShift
- [S6] https://squareup.com/help/us/en/article/6139-print-receipts
- [S7] https://squareup.com/help/us/en/article/7777-process-card-payments-with-offline-mode
- [S8] https://squareup.com/help/us/en/article/8339-set-up-device-codes
- [S9] https://squareup.com/help/us/en/article/6130-manage-your-square-loyalty-program
- [S10] https://developer.squareup.com/docs/loyalty-api/loyalty-points
- [L1] https://help.loyverse.com/help/how-issue-refund-loyverse-pos
- [L2] https://help.loyverse.com/help/advanced-inventory-management
- [L3] https://help.loyverse.com/help/low-stocks
- [L4] https://help.loyverse.com/help/how-work-transfer-orders
- [L5] https://help.loyverse.com/help/shift-management-loyverse-pos
- [L6] https://loyverse.com/blog/get-email-notification-about-new-shift-report
- [L7] https://loyverse.com/en-us/features
- [L8] https://help.loyverse.com/help/purchase-history-registered
- [L9] https://help.loyverse.com/help/how-customer-loyalty-program
- [I1] https://ru.iiko.help/resources/Storage/archive/PDF/UG_iikoOffice_5.0.pdf
- [I2] https://iiko.ru/corner/coffee-shop/
- [I3] https://iiko.github.io/front.api.doc/v6/ru/CashRegisters.html
- [I4] https://mini.iiko.help/ru/start/fr
- [I5] https://iikoservice.ru/blog/inventarizacziya-v-iiko-polnoe-rukovodstvo-po-provedeniyu-nastrojke-i-rabote-s-rashozhdeniyami/ (rasmiy hamkor, iiko'ning o‘zi emas)
- [I6] https://posbazar.ru/blog/pos-server-iiko-nedostupen-prichiny-i-poryadok-diagnostiki/ (uchinchi tomon, past ishonch)
- [I7] https://rapid.iiko.ru/userguide/iikoCard5/UG_iikoCard.pdf

## Cheklovlar
- «—» kataklar uchun rasmiy dalil topilmadi; ular keyingi research'da yoki test akkaunt orqali to‘ldiriladi.
- [I5], [I6] rasmiy iiko manbasi emas — faqat yo‘naltiruvchi.
- Bu hujjat CoffeePOS raqobatchilardan ustun degani emas; faqat qabul mezonlarini asoslash uchun.

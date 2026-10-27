# CoffeePOS: 5 POS bilan dalilli taqqoslash

Tekshirilgan sana: 2026-10-27. Bu real akkauntlarda sinov emas, ochiq rasmiy hujjatlar benchmarki. «—» = shu tekshiruvda yetarli dalil olinmagan; funksiya yo‘q degani emas. Tarif, region, qurilma va mahsulot versiyasiga qarab farq bor. CoffeePOS ustuni kod holati, staging qabul holati emas.

| Tizim | Rasmiy dalil | CoffeePOS uchun qaror |
|---|---|---|
| Toast | Chekni mahsulot/o‘rindiq yoki to‘lov bo‘yicha bo‘lish; offline’da loyalty va shift review cheklovlari | Split tender va item splitni aralashtirmaslik; offline’ni shaffof cheklash |
| Lightspeed Restaurant L-Series | Ko‘p nuqta hisobotlari va menyu tarqatish; shu versiyada nuqtalararo stock management mavjud emas deb yozilgan | «Multi-location»ni avtomatik stock transfer deb hisoblamaslik |
| Square | Split tender to‘liq summa qoplanmaguncha tugamaydi; offline to‘lovlar qayta ulanishgacha pending | Pending/settled holatlari va qayta jo‘natish kaliti majburiy |
| Loyverse | Item/quantity refund; low-stock ogohlantirish; mijoz xarid tarixi va receipt yuborish | Moliyaviy refundni fizik qaytarishdan ajratish; threshold va privacy testlari |
| iiko | Coffee-shop sahifasi sklad, moliya, hisobot va loyalty ekotizimini ta’riflaydi | Moliya va omborni bir xil order orqali ulash; marketingni texnik qabul testi deb hisoblamaslik |

## 23 modul bo‘yicha qiyoslash chegarasi

| № | Modul | Shu tekshiruvdagi rasmiy benchmark | CoffeePOS ochiq farqi |
|---|---|---|---|
| 1 | Split payment | Toast/Square split | Qisman settled payment lifecycle hali ochiq |
| 2 | Refund | Loyverse item/quantity refund | Hozir manual amount ledger; stock/bonus/fiscal reversal yo‘q |
| 3 | Tannarx | — | Snapshot regression bor; to‘liq costing auditi ochiq |
| 4 | Low stock | Loyverse threshold notifications | Filial/dedupe notification ochiq |
| 5 | P&L | iiko moliya/hisobot (umumiy tavsif) | Formal P&L va filial kesimi to‘liq emas |
| 6 | Audit | — | 3 turdagi operational audit; global emas |
| 7 | Fiscal | — (UZ provider mustaqil talab) | Certified sandbox yo‘q |
| 8 | Backup | — | Encrypted offsite/restore drill yo‘q |
| 9 | Draft orders | — | Server drafts bor; checkout/konflikt qabul sinovi ochiq |
| 10 | Tables | — | Joriy tarmoqda server table occupancy yo‘q |
| 11 | Stock transfer | Lightspeed L-Series multi-location stock cheklovi | Branch ledger/transfer lifecycle yo‘q |
| 12 | Inventory variance | — | Count bor; approval workflow yo‘q |
| 13 | Cash variance | Toast offline shift review cheklovi | Online reconciliation bor; multi-device staging yo‘q |
| 14 | Staff analytics | iiko time tracking (umumiy tavsif) | Server analytics bor; bir xil ism kolliziyasi ochiq |
| 15 | Telegram director | — (lokal talab) | Digest/retry yo‘q |
| 16 | Electronic receipt | Loyverse send/print receipt | Signed nonfiscal link; QR/revoke ochiq |
| 17 | Happy Hour | — | Overnight schedule/priority/checkout bor; filial/staging ochiq |
| 18 | Customer analytics | Loyverse purchase history | Cohort/consent workflow yo‘q |
| 19 | Combo | — | Faqat calculation helper; stock/refund integratsiyasi yo‘q |
| 20 | Offline | Toast/Square explicit restrictions | Cash queue; price conflict va multi-device qabul ochiq |
| 21 | Device management | Square offline setting modes (umumiy) | Device binding/revoke hali yo‘q |
| 22 | Updates | — | Version notice bor; staged rollout/rollback yo‘q |
| 23 | Loyalty | iiko loyalty (umumiy tavsif), Toast offline loyalty cheklovi | Ledger bor; refund reversal/concurrency qabul ochiq |

## Rasmiy manbalar

- Toast split: https://support.toasttab.com/en/article/Splitting-Checks-by-Item-1492811097734
- Toast offline: https://support.toasttab.com/en/article/Using-Toast-in-Offline-Mode
- Lightspeed L-Series multi-location: https://resto-support.lightspeedhq.com/hc/en-us/articles/360011424154-Using-multi-location-establishments
- Square split: https://api.squareup.com/help/us/en/article/5097-process-split-tender-payments-with-square
- Square offline: https://squareup.com/help/us/en/article/7777-process-card-payments-with-offline-mode
- Loyverse refund: https://help.loyverse.com/help/how-issue-refund-loyverse-pos
- Loyverse low stock: https://help.loyverse.com/help/low-stocks
- Loyverse purchase history: https://help.loyverse.com/help/purchase-history-registered
- iiko coffee: https://iiko.ru/corner/coffee-shop/
- iiko solutions: https://iiko.ru/solutions/

Boshqa POS dizayni yoki kodi ko‘chirilmaydi. Bir tizimdagi funksiyani barcha versiya/regionlarga umumlashtirmang. Keyingi research vazifasi: «—» joylar uchun rasmiy texnik qo‘llanma va ishlaydigan test akkaunti orqali dalil yig‘ish. Bu hujjat «barcha raqobatchilar to‘liq tahlil bo‘ldi» degani emas.

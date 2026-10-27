# 23 modul: dalillarga asoslangan dastlabki baho

Sana: 2026-10-27. Ishchi PR: https://github.com/avaziknabijonov-ship-it/coffeepos/pull/8

**Umumiy dastlabki baho: 27%. To‘liq qabul qilingan: 0/23.**
Bu sarflangan vaqt yoki yakunlash muddatining foizi emas. Modullar teng og‘irlikda. Baho dastlabki kod auditi, chuqur tekshiruvda pasayishi ham mumkin.

Mezon: 0 — ishlaydigan modul dalili yo‘q; 20 — qisman kod/scaffold; 40 — API/UI/testlarning asosiy qismi bor, mezonlar hali ochiq; 60 — barcha ichki integratsiya mezonlari dalil bilan; 80 — staging/hardware tekshirilgan; 100 — foydalanuvchi qabul qilgan. Yordamchi funksiya to‘liq modul hisoblanmaydi.

Oxirgi tasdiqlangan CI: https://github.com/avaziknabijonov-ship-it/coffeepos/actions/runs/40467127704 — backend SQLite, PostgreSQL va frontend muvaffaqiyatli. Bu barcha 23 modul uchun staging dalili emas.

| № | Modul | Baho | Dalil / ochiq ish |
|---|---|---:|---|
| 1 | Split payment | 40% | API/UI va tender testlari; qisman to‘lov va filial kesimi yetishmaydi |
| 2 | Refund | 40% | Manual ledger/UI va parallel test; provider, stock/bonus/fiscal reversal yo‘q |
| 3 | Tannarx | 40% | Order snapshot bor; yangi regression testi tekshirilmoqda |
| 4 | Low stock | 40% | Threshold API/UI va test; filial/dedupe notification yetishmaydi |
| 5 | P&L | 40% | Finance API/UI; filial va to‘liq reconciliation yetishmaydi |
| 6 | Audit | 40% | Refund/cancel/inventory DB jurnal, API/UI va SQL himoya testlari; global qamrov/filial/staging ochiq |
| 7 | Fiscal | 20% | Adapter scaffold; provider sandbox yo‘q |
| 8 | Backup | 20% | Qo‘lda script; encrypted offsite va restore dalili yo‘q |
| 9 | Draft orders | 40% | Server/API testlari; to‘liq checkout integratsiyasi tekshirilsin |
| 10 | Tables | 0% | Joriy tarmoqda server occupancy/move/merge yo‘q |
| 11 | Stock transfer | 0% | Faqat hisoblash yordamchisi; modul emas |
| 12 | Inventory variance | 40% | API/UI/test; approval workflow yo‘q |
| 13 | Cash variance | 40% | Smena balansi/API/UI/test; staging yo‘q |
| 14 | Staff analytics | 40% | Server API/UI, discount/refund/net, RBAC va tenant test; ism kolliziyasi va staging ochiq |
| 15 | Telegram director | 0% | Opt-in digest/retry integratsiyasi yo‘q |
| 16 | Electronic receipt | 40% | Signed 15-min nonfiscal link/API/UI, privacy va token testlari; QR/revoke/log redaction/staging ochiq |
| 17 | Happy Hour | 20% | Hisoblash yordamchisi; server/UI workflow yo‘q |
| 18 | Customer analytics | 20% | Mijoz bazasi; cohort/consent hali yo‘q |
| 19 | Combo | 20% | Hisoblash yordamchisi; stock/refund integratsiyasi yo‘q |
| 20 | Offline | 20% | Boshlang‘ich queue; ko‘p qurilma/qayta ochish testi yo‘q |
| 21 | Device management | 0% | Device binding/revoke yo‘q |
| 22 | Updates | 20% | Version/update UI bor; staged rollout/rollback yo‘q |
| 23 | Loyalty | 40% | Ledger/API/UI bor; refund reversal va concurrency to‘liq emas |

Productionga tegilmadi. Foiz faqat yangi dalil yoki bajarilgan qabul mezoni bilan o‘zgartiriladi.

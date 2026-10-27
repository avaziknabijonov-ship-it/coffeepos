# 23 modul: dalillarga asoslangan holat

Sana: 2026-10-27. Ishchi branch: `devin/1793089384-pos-23-modules` (PR #8 / `codex/ci-lint-20261027` ning `79948a6` commiti to‘liq ichida).

**Acceptance shkalasi bo‘yicha o‘rtacha: ~56%. Foydalanuvchi tomonidan to‘liq qabul qilingan: 0/23.**

Mezon (o‘zgarmagan): 0 — dalil yo‘q; 20 — scaffold; 40 — API/UI/testlarning asosiy qismi, mezonlar ochiq; 60 — barcha ichki integratsiya mezonlari dalil bilan; 80 — real staging/hardware tekshirilgan; 100 — foydalanuvchi qabul qilgan.
"Lokal staging" — VM'dagi alohida `coffeepos-staging` Docker stack (alohida `coffeepos_staging` bazasi). Bu real staging serveri emas, shuning uchun 80% berilmaydi.

## Tekshirilgan dalillar (2026-10-27, mahalliy)

| Tekshiruv | Natija |
|---|---|
| Backend SQLite `pytest backend/tests` | 90 passed, 3 skipped (PostgreSQL-only) |
| Backend PostgreSQL 16 (disposable konteyner, toza sxema) | 93 passed |
| Frontend `check-i18n.mjs` | o‘tdi, 706 RU kalit |
| Frontend `npm test` / `lint` / `build` | 5/5 o‘tdi; lint 0 xato (faqat ogohlantirishlar); build o‘tdi |
| Lokal staging `scripts/staging_smoke.py` (HTTP, nginx+API+PostgreSQL) | 23/23 o‘tdi |
| Shifrlangan backup + restore drill (throwaway PostgreSQL) | o‘tdi |
| GitHub Actions (backend SQLite, backend PostgreSQL, frontend, staging-smoke + backup/restore drill), commit `dc0efb8` | 4/4 o‘tdi: https://github.com/avaziknabijonov-ship-it/coffeepos/actions/runs/40477480648 |

Production VPS va production bazasiga tegilmadi. Deploy qilinmadi.

## Modullar

| № | Modul | Baho | Bajarilgan mezonlar va dalil | Ochiq / bloklangan |
|---|---|---:|---|---|
| 1 | Split payment | 60% | `OrderPayment` yozuvlari, partial status, keyingi to‘lov, clientKey idempotency; `test_split_api`, `test_payment_rules`, smoke 06–07 | Real terminal/Payme/Click provider |
| 2 | Refund | 60% | Original to‘lovga bog‘lash, qisman/to‘liq, ortiqcha refund taqiq, stock/bonus/fiscal reversal, audit; `test_refunds_api`, `test_refund_concurrency`, smoke 09–10 | Provider orqali pul qaytarish |
| 3 | Tannarx | 60% | Ingredient/retsept snapshot, tarixiy o‘zgarmaslik; `test_cost_snapshot` | — |
| 4 | Low stock | 60% | Filial bo‘yicha threshold, dedupe notification; `test_stock_alerts`, smoke 22 | — |
| 5 | P&L | 60% | Revenue − refund, COGS, xarajat, filial/sana filtri; `test_finance_ops`, smoke 18 | — |
| 6 | Audit | 60% | Actor/action/before-after/company, append-only, sirlar maskalangan; `test_audit`, smoke 20–21 | — |
| 7 | Fiscal | 40% | STIR/operator/terminal config, Fernet shifrlangan credential, sandbox provider, QR payload, refund chek, mandatory fail-closed (503); `test_fiscal`, `test_integrations`, smoke 13–15 | **Bloklangan:** sertifikatlangan OFD/fiskal provayder, kalitlar va uskuna |
| 8 | Backup | 40% | AES-256 (PBKDF2) shifrlangan dump, retention, `last-status.json`, restore drill o‘tdi; CI job qo‘shildi | **Bloklangan:** offsite (rclone) kirish ma’lumoti, monitoring/alert kanali |
| 9 | Draft orders | 60% | Server draft, version conflict, checkoutgacha tushum yo‘q; `test_drafts` | — |
| 10 | Tables | 60% | Zal/stol, occupancy, move/merge RBAC, takeaway; `test_experience`, admin "Zal" UI | — |
| 11 | Stock transfer | 60% | Dispatch/in-transit/receive, atomik ikki filial ledger, ikki marta qabul taqiq; `test_inventory_ops`, smoke 11–12 | — |
| 12 | Inventory variance | 60% | Kutilgan/sanalgan, signed adjustment, approval/reject; `test_inventory_ops`, UI | — |
| 13 | Cash variance | 60% | opening + naqd sotuv − naqd refund − naqd xarajat, farq va actor; `test_finance_ops`, smoke 19 | — |
| 14 | Staff analytics | 60% | staff_id bo‘yicha order/sotuv/chegirma/refund/smena, rol ko‘rinishi; `test_staff_analytics` | — |
| 15 | Telegram director | 40% | Opt-in tenant chat, shifrlangan token, kunlik digest, dedupe, backoff retry (5), token redaction; fake sender bilan `test_integrations` | **Bloklangan:** real bot token/chat va tarmoq orqali yuborish sinovi |
| 16 | Electronic receipt | 60% | Fiscal/nonfiscal/sandbox holati aniq, signed qisqa muddatli link, privacy; `test_receipts`, `test_access_logs`, smoke 15 | Real fiskal QR (7-modulga bog‘liq) |
| 17 | Happy Hour | 60% | Lokal vaqt zonasi, tungi jadval, ustuvorlik, chegirma limiti, filial; `test_promotions`, `test_experience`, UI | — |
| 18 | Customer analytics | 60% | Consent, takroriy tashrif, kogorta, tarix, PII o‘chirish (buxgalteriya saqlanadi); `test_customer_analytics`, `test_experience`, UI | — |
| 19 | Combo | 60% | Komponent SKU, bir martalik ingredient yechish, qaytarishda reversal; `test_combos`, `test_experience` | — |
| 20 | Offline | 40% | Company-scoped durable queue, idempotency, server conflict jadvali va manager resolve, soxta fiskal chek yo‘q, faqat naqd; `test_reliability`, `tests/offline.test.mjs`, smoke 16 | Ko‘p qurilma/brauzer qayta ochish UI sinovi o‘tkazilmagan |
| 21 | Device management | 60% | Hashed device secret, company/branch binding, revoke, last seen, require-device policy; `test_reliability`, smoke 17 | Real qurilmalar parki |
| 22 | Updates | 40% | Semver, deterministik staged rollout, rollback, min backend/client (426); `test_reliability`, smoke 23 | **Bloklangan:** APK build/imzo va tarqatish infratuzilmasi |
| 23 | Loyalty | 60% | Ledger, accrual/redeem/refund reversal, lock bilan parallel himoya, ledger mosligi; `test_experience`, `test_api` | — |

## Bloklangan qismlar uchun kerakli kirish / qurilmalar

| Modul | Kerak bo‘ladigan narsa |
|---|---|
| 7 Fiscal, 16 E-receipt QR | Sertifikatlangan OFD/fiskal provayder shartnomasi, sandbox va production API hujjati, kalitlar, kompaniya STIR va terminal ID, fiskal modul (uskuna) yoki virtual kassa |
| 8 Backup | Offsite storage (S3/Backblaze/Google Drive, rclone remote) uchun kirish ma’lumoti, shifrlash passphrase saqlash joyi, alert kanali (Telegram yoki email) |
| 15 Telegram director | BotFather orqali bot token, direktor chat ID, server'dan `api.telegram.org` ga chiqish ruxsati |
| 22 Updates | Android APK build pipeline, imzolash keystore, APK tarqatish URL/hosting, test qurilmalari |
| 20 Offline, 21 Devices | Kamida 2 ta real POS qurilma yoki planshet, ko‘p qurilmali offline/qayta ulanish sinovi |
| 1–2 To‘lovlar | Payme/Click/terminal merchant sandbox kalitlari (avtomatik refund uchun) |
| Hammasi (80%) | Production'dan alohida real staging server va domen (masalan, staging.mcoffeepos.uz) |

## Real sinovga tayyorlik

**Hali "real sinovga tayyor" emas.** Sabablar: fiskal provayder, Telegram, offsite backup va APK bloklangan; UI end-to-end sinovi (testing agent) foydalanuvchi ruxsati bilan hali o‘tkazilmagan; real staging serveri yo‘q.

## 2026-10-27: Codex davom ettirish tekshiruvi

Boshlang‘ich commit: `f47e0c4`. Acceptance bahosi **56% o‘zgarmadi**;
quyidagi regression tekshiruvlari real hardware/staging qabuli hisoblanmaydi.

- Offline navbat endi bitta katta JSON massiv o‘rniga har bir clientKey uchun
  alohida localStorage yozuvini saqlaydi. Boshqa tabdagi yangi savdo yoki
  tasdiqlash mavjud savdolarni butun massiv bilan ustidan yozmaydi.
- Eski massiv avtomatik ko‘chiriladi; ko‘chirishda joy tugasa asl massiv saqlanadi.
  Buzilgan navbat yangi savdo bilan jim almashtirilmaydi. Bir xil clientKey
  qayta navbatga kiritilsa, asl yozuv saqlanadi.
- Replay yoki sync davomida logout/token almashsa, eski javob yangi sessiya
  holatini o‘zgartirmaydi va qolgan eski navbat yangi token bilan yuborilmaydi.
- Oxirgi konflikt navbatdan chiqarilganda ham menejer tekshirishi haqidagi
  ogohlantirish ko‘rinib turadi.

Mahalliy dalillar:
- SQLite backend: **90 passed, 3 PostgreSQL-only skipped**.
- Frontend: **11/11** test, shu jumladan eski navbat migratsiyasi, quota xatosi,
  ikki tabdagi enqueue/ack va yuborish paytida logout regression testi.
- `scripts/migration_drill.py`: eski `29bad618` sxemasidan upgrade — **15/15**.
  Tarixiy tushum/xarajat/tannarx/bonus saqlanishi, eski savdoga refund,
  ortiqcha refund taqiqi, qayta migratsiya tekshirildi (SQLite).
- Build, i18n tekshiruvi o‘tdi; lint xatosiz, mavjud ogohlantirishlar bor.

Bu muhitda Docker/PostgreSQL serveri mavjud emas; shu commitning PostgreSQL,
nginx staging va backup/restore natijalari GitHub CI orqali alohida tekshiriladi.
Playwright Chromium yuklashida arxiv xatosi bo‘ldi; brauzer UI qayta sinovi
bajarildi deb hisoblanmaydi. Offline’ning real ikki qurilma sinovi ham ochiq.
Fiskal/Telegram/offsite/APK va tashqi to‘lov kalitlariga bog‘liq bloklar saqlanadi.
Production VPS/bazaga tegilmadi, merge/deploy bajarilmadi.

## 2026-10-27: qoralama va filial RBAC tuzatishlari

Davom ettirishda uchta regression avval xato bilan qayta yaratildi:
boshqa faol filialdan qoralamani o‘chirish 204 qaytargan; shu clientKey bilan
qoralama yaratish boshqa filialdagi mijoz/tarkib ma’lumotini qaytargan;
boshqa filial qoralamasini yangilash uning mavjudligini 409 bilan bildirgan.

- DELETE/PATCH va mavjudlik tekshiruvi company + faol branch bilan cheklangan.
- Boshqa filial clientKey’siga qayta murojaat tafsilotsiz 409 qaytaradi.
- Filialga biriktirilmagan kassir/barista endi X-Branch-Id orqali istalgan filialni
  tanlay olmaydi. Default filial va administrator ro‘yxatdan o‘tkazgan qurilmaga
  biriktirilgan filial ishlaydi; rahbarning filial tanlashi saqlangan.
- Qoralama va filial ruxsati xatolari uchun UZ/RU matnlari qo‘shilgan.

Dalil: `backend/tests/test_branch_drafts.py` da 4 yangi test, mahalliy backend
**94 passed / 3 PostgreSQL-only skipped**. Frontend **11/11**, build va i18n
tekshiruvi o‘tdi. PostgreSQL/staging va migratsiya GitHub CI’da qayta sinaladi.
Acceptance hali **56%**, bu tuzatishlar real pilot yoki foydalanuvchi qabuli emas.

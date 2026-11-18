# CoffeePOS — productionga chiqarishdan oldingi tekshiruv (yangilangan 2026-11-18)

**MUHIM:** GitHub kodini production VPS ga avtomatik o‘tkazmang. Bu branch/commitdagi modullar uchun GitHub build, backend integration test, migrations, gerçek planshet va termoprinter sinovlari hali mustaqil tasdiqlanmagan.

## Modullar qabul holati
| Funksiya | Kod | Majburiy keyingi tekshiruv |
|---|---|---|
| Kassa va Barista, ixtiyoriy 2 rol | bor, avtotest ✅ | — |
| Kassa uchun 0–50% chegirma | bor, avtotest ✅ (0/17/50/51%) | — |
| Kassa xarajati va smena balansi | bor, avtotest ✅ (naqd/karta/xarajat/refund) | Real kassa bilan Z-hisobot solishtirish |
| Payroll — oylik stavka/ishlangan kun/avans | bor | Oy chegarasi, alohida xodim, noto‘g‘ri kunlar |
| Finance — operatsion hisob | bor | Savdo/kirim/chiqim mosligi |
| Bonus va mijozlar bazasi | bor, avtotest ✅ (cancel/refund reversal) | — |
| Platform superadmin | bor | SECRET_KEY, manager ruxsatlari, obunalar |
| Nakladnoy cancel | bor | Omborda sarflangan qoldiq, parallel cancel |
| Order retry/idempotency | bor, avtotest ✅ (8 parallel so‘rov, 2 planshet; poyga xatosi tuzatildi) | — |
| Offline kassa | boshlang‘ich variant | Quvvat o‘chishi, localStorage limit, tarmoq tiklanishi, server 409, multi-terminal |
| Service worker | bor | Android WebView va mobil browser kesimida qayta ochish |
| Chek qog‘ozi 58/80 | bor | Real termoprinter va driver |
| Native Bluetooth/USB/LAN printer | yo‘q | Qurilma modeli va SDK bridge |
| O‘zbekiston fiskal chek provayderi | yo‘q | Sertifikatlangan provayder, qonuniy sandbox |
| Multi-filial transfer | yo‘q | Tenant/branch arxitektura va qoldiq ajratish |
| To‘liq refund (har qanday holat, eski smena) | bor, avtotest ✅ | Qisman (bitta pozitsiya) qaytarish hali yo‘q |
| 100+ tenant izolyatsiyasi | avtotest ✅ (120 kompaniya, 2 tenant cross-access 404) | Real VPS’da yuklama (load) testi |
| Har kuni avtomatik offsite backup | bor: `deploy/backup.sh` + systemd timer + GPG + rclone + `deploy/restore.sh` drill (lokal PostgreSQL’da sinaldi) | VPS’da `install-backup-timer.sh` ishga tushirish, offsite remote sozlash |
| Audit jurnali (chegirma, otmena, refund, smena, ombor, xodim, pul) | bor, avtotest ✅, Admin → «Audit jurnali» | — |

## Staging migratsiya
1. Ishlayotgan VPS dan xavfsiz PostgreSQL snapshot; kamida bitta alohida restore test.
2. Stagingga eng oxirgi GitHub commitini deploy qiling.
3. db.py yangi jadvallar: customers, bonus_configs, bonus_ledger, payroll_plans, audit_log.
4. main.py qo‘shimcha ustunlar: orders.customer_id, orders.bonus_used, orders.bonus_earned, orders.client_key, orders.refunded_at/refunded_by/refund_reason/refund_shift_id, purchase_invoices.status/cancelled_*, staff.can_barista. Eski SQLite bazadan migratsiya sinaldi.
5. Unique order indeks: ix_orders_company_client_key. Eski takroriy ma’lumot va migratsiya sinovdan o‘tsin.
6. Har bir modul /api bilan end-to-end testdan o‘tsin; xatoda rollback.

## Maxfiylik va litsenziya
- SUPERADMIN_KEY server .env ichida kamida 40 belgi; GitHub commitiga qo‘yilmaydi.
- SECRET_KEY va POSTGRES_PASSWORD ham faqat production secretlarda.
- ENFORCE_LICENSES default 0 — eski mijozlarning obunasi oldin to‘ldirilmasdan turib 1 qilish ularni bloklashi mumkin.
- Administrator paneli: https://mcoffeepos.uz/#superadmin (yangi commit productionga joylangandan va key sozlangandan keyin).
- Yuklangan APK hozir remote https://mcoffeepos.uz ni ko‘rsatadi. Sayt deploy qilinmaguncha yangi modullar APK’da yo‘q.

## Offline rejim cheklovlari
- Boshlang‘ich offline navbat faqat naqd va bonus ishlatmaydigan buyurtma uchun.
- 200 ta lokal buyurtmadan ortiq qo‘shilmaydi.
- Offline chekda «SERVER TASDIQLAMAGAN, FISKAL CHEK EMAS» belgisi bo‘ladi.
- Qayta yuborish clientKey bo‘yicha serverda idempotent, lekin bir nechta planshet, eski smena yopilishi, bonus, fiskal va printer holati hali sinovsiz.
- Offline kassa production-ready sifatida reklamaga chiqarilmaydi.

## Keyingi minimal qabul protokoli
- ✅ CI: backend pytest (SQLite + PostgreSQL 16), frontend TypeScript/Vite build, tarjima kalitlari, oxlint, deploy skriptlar sintaksisi.
- ✅ 3 xil xodim: kassir, barista, dual role; to‘g‘ri va noto‘g‘ri API rollar (`backend/tests/test_acceptance.py`).
- ✅ 2 ta alohida coffee tenant; buyurtma, mijoz telefoni, audit bir-biriga aralashmaydi.
- Takroriy buyurtma+ikki planshet, 30 minut offline, internet qaytishi; tushumlar ikki marta hisoblanmaydi.
- 58/80mm printer real Windows va Android qurilmalarida.
- GitHub->VPS ni faqat testlar o‘tgach bir martalik deploy; healthcheck va rollback hujjat bilan.

## Backup
1. `cp deploy/backup.env.example deploy/backup.env` va to‘ldiring (GPG ochiq kalit, rclone remote).
2. `sudo deploy/install-backup-timer.sh` — har kuni 03:30 (Toshkent) backup, darhol bitta sinov backup.
3. Tekshirish: `systemctl list-timers coffeepos-backup.timer`, `cat $BACKUP_DIR/LAST_SUCCESS`.
4. Restore drill (xavfsiz, ishlab turgan bazaga tegmaydi): `deploy/restore.sh /var/backups/coffeepos/coffeepos-….sql.gz.gpg` — oyda kamida 1 marta.
5. Haqiqiy tiklash: `deploy/restore.sh FILE --production` (oldin avtomatik backup oladi, eski baza `coffeepos_old` bo‘lib qoladi).
- GPG maxfiy kaliti serverda saqlanmaydi. Bittagina VPS diskdagi backup yetarli emas — offsite majburiy.

## Modul manbalari
O‘zimizning CoffeePOS dizayn va kod qoidalarini `docs/COMPETITOR_MODULE_PLAN_UZ.md` da ko‘ring.

## Kod bilan hal qilib bo‘lmaydigan qolgan ishlar (qurilma / server / huquqiy)
- Real 58/80mm termoprinter (Windows, Android) va nativ Bluetooth/USB/LAN bridge — qurilma modeli kerak.
- O‘zbekiston fiskal provayderi (OFD) — sertifikatlangan provayder shartnomasi va sandbox kaliti kerak.
- VPS’ga deploy, staging migratsiya, backup timer’ni yoqish — server egasi tomonidan.
- Multi-filial (filiallararo transfer) — alohida arxitektura bosqichi.
- 30 daqiqa offline + real planshetlar bilan sinov.

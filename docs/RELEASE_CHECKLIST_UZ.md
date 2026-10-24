# CoffeePOS — productionga chiqarishdan oldingi tekshiruv (2026-10-25)

**MUHIM:** GitHub kodini production VPS ga avtomatik o‘tkazmang. Bu branch/commitdagi modullar uchun GitHub build, backend integration test, migrations, gerçek planshet va termoprinter sinovlari hali mustaqil tasdiqlanmagan.

## Modullar qabul holati
| Funksiya | Kod | Majburiy keyingi tekshiruv |
|---|---|---|
| Kassa va Barista, ixtiyoriy 2 rol | bor | Role permission integration test |
| Kassa uchun 0–50% chegirma | bor | 0, 17, 50, 51% holatlar |
| Kassa xarajati va smena balansi | bor | Naqd, karta, bank, Z-hisobot |
| Payroll — oylik stavka/ishlangan kun/avans | bor | Oy chegarasi, alohida xodim, noto‘g‘ri kunlar |
| Finance — operatsion hisob | bor | Savdo/kirim/chiqim mosligi |
| Bonus va mijozlar bazasi | bor | Reversal, bir vaqtda 2 POS, saldo |
| Platform superadmin | bor | SECRET_KEY, manager ruxsatlari, obunalar |
| Nakladnoy cancel | bor | Omborda sarflangan qoldiq, parallel cancel |
| Order retry/idempotency | bor | Bir clientKey ikki marta yuborilishi |
| Offline kassa | boshlang‘ich variant | Quvvat o‘chishi, localStorage limit, tarmoq tiklanishi, server 409, multi-terminal |
| Service worker | bor | Android WebView va mobil browser kesimida qayta ochish |
| Chek qog‘ozi 58/80 | bor | Real termoprinter va driver |
| Native Bluetooth/USB/LAN printer | yo‘q | Qurilma modeli va SDK bridge |
| O‘zbekiston fiskal chek provayderi | yo‘q | Sertifikatlangan provayder, qonuniy sandbox |
| Multi-filial transfer | yo‘q | Tenant/branch arxitektura va qoldiq ajratish |
| To‘liq refund/qisman qaytarish | yo‘q | To‘lov reversali, qaytarish hujjati, ombor |
| Haqiqiy 100+ tenant yuklama | sinov yetarli emas | PostgreSQL concurrency/load-test |
| Har kuni avtomatik offsite backup | o‘rnatilmagan | Cron, offsite shifrlash, restore drill |

## Staging migratsiya
1. Ishlayotgan VPS dan xavfsiz PostgreSQL snapshot; kamida bitta alohida restore test.
2. Stagingga eng oxirgi GitHub commitini deploy qiling.
3. db.py yangi jadvallar: customers, bonus_configs, bonus_ledger, payroll_plans.
4. main.py qo‘shimcha ustunlar: orders.customer_id, orders.bonus_used, orders.bonus_earned, orders.client_key, purchase_invoices.status/cancelled_*, staff.can_barista.
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
- GitHub backend pytest, frontend TypeScript/Vite build, tarjima kalitlari, ESLint/oxlint bo‘yicha tekshiruv.
- 3 xil xodim: kassir, barista, dual role; to‘g‘ri va noto‘g‘ri API rollar.
- 2 ta alohida coffee tenant; obuna, mijoz telefoni, ombor harakati bir-biriga aralashmaydi.
- Takroriy buyurtma+ikki planshet, 30 minut offline, internet qaytishi; tushumlar ikki marta hisoblanmaydi.
- 58/80mm printer real Windows va Android qurilmalarida.
- GitHub->VPS ni faqat testlar o‘tgach bir martalik deploy; healthcheck va rollback hujjat bilan.

## Backup
- Joriy qo‘lda ishga tushiriladigan skript: `deploy/backup.sh`.
- Production uchun cron/systemd timer alohida yoqiladi; o‘rnatilganligi va oxirgi saqlanishi tekshiriladi.
- Backupni serverdan tashqarida shifrlangan joyga yuborish va stagingda tiklash majburiy. Bittagina VPS diskdagi backup yetarli emas.

## Modul manbalari
O‘zimizning CoffeePOS dizayn va kod qoidalarini `docs/COMPETITOR_MODULE_PLAN_UZ.md` da ko‘ring.

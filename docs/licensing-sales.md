# CoffeePOS — qahvaxonalar uchun litsenziyalar (sinov versiyasi)

## Hozir ishlaydigan imkoniyatlar
- Barcha qahvaxonalar alohida tenant / slug / PIN / ma'lumotlarga ega.
- Har bir yangi qahvaxona standart **14 kunlik trial** bilan yaratiladi.
- Server vaqti bo'yicha holatlar:
  - `trial`: sinov muddati ichida to'liq operatsiyalar;
  - `active`: amaldagi to'langan muddat (to'lovni hali **qo'lda** tasdiqlash kerak);
  - `grace`: belgilangan imtiyozli muddat tugaguncha ishlaydi;
  - `expired`, `suspended`, `unconfigured`: **GET hisobotlar ochiq**, **POST/PUT/PATCH/DELETE blok**.
- CoffeePOS ichida rahbar uchun qolgan kunlar, muddati tugaganda barcha xodimlar uchun cheklov banneri.
- Super Admin: coffee bar ro'yxati, yangi cafe yaratish, sinov yoki faol muddat berish, **oylik (1 kalendar oy)** va **yillik (1 kalendar yil)** litsenziyani qo'lda uzaytirish, suspension, status tarixi. Qahvaxona egasi o'z tarifini litsenziya sahifasida ko'radi.

## Super Admin'ni yoqish (faqat alohida TEST serverida boshlang)

Production muhitdagi `.env`:

```dotenv
SEED_DEMO=0
ALLOW_PUBLIC_REGISTRATION=0
LICENSE_ENFORCEMENT=0
PLATFORM_ADMIN_KEY=<kamida-32-belgili-random-unique-secret>
PLATFORM_REQUIRE_MFA=1
PLATFORM_ADMIN_TOTP_SECRET=<private-base32-totp-secret>
```

Xavfsizlik: `PLATFORM_ADMIN_KEY` ni chatda yubormang, repo ichiga yozmang, boshqalarga bermang. U oddiy xodim PINidan mustaqil. Docker Compose `PLATFORM_ADMIN_KEY`, `PLATFORM_REQUIRE_MFA`, `PLATFORM_ADMIN_TOTP_SECRET` va `ALLOW_PUBLIC_REGISTRATION` ni API konteynerga beradi.

`/platform-admin` sahifasi orqali xizmatni boshqarish mumkin, lekin uni **internetga HTTPS siz chiqarmang**. Kalit va autentifikator kodini tekshiradigan 15 daqiqalik sessiya qo'shildi, kalit almashtirilsa sessiya bekor bo'ladi. Lekin hozirgi yagona umumiy administrator kaliti **to'liq ko'p-administratorli hisob tizimi emas**: real tijoriy tarqatishdan oldin alohida administrator shaxslari, IP/network cheklovlar, xavfsiz kirish tarixi va ehtiyot choralarini baholash kerak.

Agar local `npm run dev` ishlatilsa, **demo/test** uchun `ALLOW_PUBLIC_REGISTRATION=1` qoldirish mumkin. Hosted `Dockerfile` `VITE_ALLOW_PUBLIC_REGISTRATION=0` bilan signup tugmasini yashiradi; bu serverdagi `ALLOW_PUBLIC_REGISTRATION=0` o'rnini bosmaydi.

## Litsenziyani xavfsiz faollashtirish

`LICENSE_ENFORCEMENT=0` — standart xavfsiz rollout rejimi: litsenziya sanalari ko‘rinadi, lekin oldingi mavjud qahvaxonalar faqat dastur yangilandi degani uchun to‘satdan bloklanmaydi. **Yangi savdoni bloklash faqat `LICENSE_ENFORCEMENT=1` qilganda ishga tushadi.** Bu sozlama barcha tenantlar uchun server darajasida.

Server egasi ishga tushirishdan oldin:
1. TEST bazani backup qilish va yangilash/migratsiya sinovini tugatadi.
2. Super Admin'da eski qahvaxonalarning hammasiga tegishli `trial` yoki `active` obuna holatini belgilaydi.
3. TEST serverda `LICENSE_ENFORCEMENT=1` bilan muddat tugashi va tiklanishini tekshiradi.
4. Production'da xodimlar savdosini to'xtatmaydigan reja bilan ehtiyotkorlik bilan yoqadi.

`LICENSE_ENFORCEMENT=0` holatda **litsenziya tijoriy nazorat uchun faol emas**, shuning uchun haqiqiy mijozlarga pullik obuna sotishda bu sozlamani albatta yoqish kerak. Bu sozlamaning yoqilganini faqat foydalanuvchi tasdiqlashi mumkin.

## Litsenziya berish tartibi

1. Super Admin orqali yangi qahvaxona yarating (nom, noyob login/slug, rahbar va 4–6 xonali PIN). 14 kunlik sinov darhol boshlanadi.
2. Qahvaxona uchun `trial`, `active`, `grace`, `expired`, `suspended` holatini o'zgartiring.
3. To'lovni **o'zingiz tashqi tizimda** tekshirgandan keyin Admin panelda **Oylik** yoki **Yillik** tarifni tanlang va uzaytirishni tasdiqlang.
4. Oylik tarif: 1 kalendar oy (masalan, 31-yanvar → 28-fevral). Yillik: 1 kalendar yil (29-fevral → keyingi yil 28-fevral). `active` muddat hali tugamagan bo'lsa, uzaytirishda qolgan muddat saqlanadi. Tugagan bo'lsa yangi muddat serverdagi hozirgi vaqtdan boshlanadi.
5. `expired` va `suspended` holatda mijoz eski savdo/ombor hisobotlarini ko'rishi mumkin, lekin yangi operatsiyalar server tomonidan rad etiladi. Admin uzaytirsa yozish huquqi avtomatik qaytadi.
6. Litsenziya o'zgarishlari oxirgi 100 yozuv sifatida ko'rinadi.

## API (Super Admin kaliti kerak)

- `GET /api/platform/companies`
- `POST /api/platform/companies`
- `PUT /api/platform/companies/{id}/subscription`
- `POST /api/platform/companies/{id}/subscription/extend` — JSON `{"period":"monthly","operationId":"new-unique-operation-id"}` yoki `{"period":"yearly","operationId":"another-unique-operation-id"}`. Eski integratsiyalar uchun `{"days":30}` vaqtincha qo'llanadi; yangi panel faqat ikki tarifni ko'rsatadi.
- `GET /api/platform/companies/{id}/license-history`
- Oddiy kafe loginiga tegishli: `GET /api/license/status` (status, canWrite, expiresAt, serverTime).

## Hali tijoriy release tayyor emas

- Avtomatik Click/Payme/to'lov provayderi yoki fiskal chek bilan bog'lash **yo'q**. To'lov avtomatik tasdiqlanmaydi.
- **Tariflar**: Oylik va Yillik. **Narxlar hozircha belgilanmagan**; foydalanuvchi oylik/yillik so'm summalarini keyin belgilaydi. Avtomatik debet, chek yoki billing mavjud emas. Chegirmalar, sotuv hujjatlari va mijozga ko'rsatiladigan qo'llab-quvvatlash siyosati hali belgilanmagan.
- **Alohida shaxsiy Super Admin/Menejer/Auditor hisoblari** (MFA, sessiya, RBAC, litsenziya va narx o‘zgarishi bo‘yicha audit) ishlab chiqildi — [to‘liq yo‘riqnoma](platform-admin-accounts.md). Rasmiy to‘lov provayderi/billing auditi hali yo‘q. Vaqtinchalik PostgreSQL CI backup/restore sinovi mavjud; real production tiklash mashqi hali o'tkazilmagan.
- Migratsiya va ishga tushirishni avval TEST COFFEE da tekshiring, ayniqsa eski tenantlarda `subscriptions` row mavjudligini. **Production MasterCoffee bazasiga hech qanday TEST ma'lumotni nusxalamang**.
- Android APK build va backend avtomatik testlaridan tashqari real qurilmadagi login, sync, smena va expiry banneri sinovi talab etiladi.

## Avtomatik testlar

```bash
cd backend
python -m pytest tests/test_license.py tests/test_platform.py -q
```

Testlar faqat alohida vaqtinchalik bazalarda ishlashi kerak. Import manzili ishlab turgan `C:\CoffeePoss\yangi-versiya` emas, **shu repository checkoutdagi** `backend/app` bo'lishini tekshiring.


## Tarifni saqlash va migratsiya

`subscriptions.plan` nomli nullable ustun qo'shiladi: `monthly` yoki `yearly`. Eski obunalar o'zgarmaydi; avvalgi qo'lda berilgan sanalar va eski `days` uzaytirish yozuvlarida tarif `null` bo'lishi mumkin. `backend/app/main.py` dagi ishga tushish migratsiyasi bu ustunni bazani tozalamasdan qo'shadi. Avval **TEST** ma'lumotlari nusxasida tekshiring.

Yangi oylik/yillik uzaytirishda `operationId` qayta ishlatilsa muddat takror qo'shilmaydi. Eski `days` API bilan `operationId` yubormaydigan integratsiyalar bu himoyaga kirmaydi. To'lov avtomatlashtirilishidan oldin payment idempotency, to'lov kvitansiyasi va to'lov provayderi bilan real tasdiqlash talab qilinadi.


## Super Admin — MFA va xavfsiz kirish

Tijoriy Docker serverda default `PLATFORM_REQUIRE_MFA=1`; TOTP sozlanmagan bo'lsa admin kirishi **bloklanadi** (qahvaxona savdosi emas).

Test/server operatori o'z kompyuterida **maxfiy** TOTP Base32 qiymati ishlab chiqishi mumkin:

```bash
python -c "import base64,secrets; print(base64.b32encode(secrets.token_bytes(20)).decode().rstrip('='))"
```

Bu kodni autentifikator ilovasiga qo'lda qo'shing va .env dagi `PLATFORM_ADMIN_TOTP_SECRET` ga yozing. Maxfiy qiymatni GitHub, xabar, ekran rasmi yoki mijozga yubormang. `PLATFORM_ADMIN_KEY` bilan **bir xil bo'lmasin**.

`https://SERVER-DOMAIN/platform-admin` sahifasida maxfiy kalit va autentifikator ilovasining 6 xonali kodini kiritasiz. Kalit faqat kirishda yuboriladi; boshqa API chaqiruvlar 15 daqiqalik vaqtinchalik token orqali o'tadi. Istalgan vaqtda `PLATFORM_ADMIN_KEY`ni almashtirish eski sessiyalarni bekor qiladi. Login urinishlariga vaqtinchalik cheklov qo'yilgan. HTTP orqali internetga maxfiy admin kalitini yubormang.

## Narxlar va takroriy so'rovdan himoya

Super Admin'dagi Oylik/Yillik narx maydonlari **narx belgilanmaganida bo'sh** turadi. Tasdiqlangan narxlarni istalgan vaqt o'sha panelda kiritish yoki bo'shatish mumkin. Narx `UZS`da musbat butun son sifatida serverda saqlanadi. Mijozning `Litsenziya` bo'limida ko'rinadi; **dastur to'lovni avtomatik olmaydi**. Narxni kiritish yoki o'zgartirish mavjud litsenziyalar muddatiga ta'sir qilmaydi.

`POST /api/platform/companies/{id}/subscription/extend` (oylik/yillik) uchun **takrorlanmas `operationId`** talab qilinadi:

```json
{"period": "monthly", "operationId": "unique-grant-request-20261013"}
```

Server bir `operationId`ni o'sha qahvaxonada takror qabul qilsa muddatni yana uzaytirmaydi, avvalgi natijani qaytaradi. Bu foydalanuvchi tasodifan qayta yuborganda himoya qiladi; avtomatik to'lovning idempotent webhook tizimi o'rnini bosmaydi. Hozircha bitta Super Admin kaliti ishlatiladi, to'lov kim tomonidan va qaysi provayderda qabul qilingani bog'lanmagan.

## Backup va migratsiya

PostgreSQL va SQLite uchun alohida read-only zaxira olish vositalari hamda CI sinovlari: [backup-restore.md](backup-restore.md). Production DB uchun rejalashtirilgan recovery hamda deployment oldi backup talablari saqlanib qolgan.

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
- Super Admin: coffee bar ro'yxati, yangi cafe yaratish, sinov yoki faol muddat berish, 30/90/365 kun qo'lda uzaytirish, suspension, status tarixi.

## Super Admin'ni yoqish (faqat alohida TEST serverida boshlang)

Production muhitdagi `.env`:

```dotenv
SEED_DEMO=0
ALLOW_PUBLIC_REGISTRATION=0
PLATFORM_ADMIN_KEY=<kamida-32-belgili-random-unique-secret>
```

Xavfsizlik: `PLATFORM_ADMIN_KEY` ni chatda yubormang, repo ichiga yozmang, boshqalarga bermang. U oddiy xodim PINidan mustaqil. Docker Compose `PLATFORM_ADMIN_KEY` va `ALLOW_PUBLIC_REGISTRATION` ni API konteynerga beradi.

`/platform-admin` sahifasi orqali xizmatni boshqarish mumkin, lekin uni **internetga HTTPS siz chiqarmang**. Hozirgi 32+ belgili yagona maxfiy kalit — vaqtinchalik yechim: ko'p mijozli real tijoriy tarqatishdan oldin alohida administrator hisobi, MFA, xavfsiz kirish jurnali, IP cheklov va ehtiyot choralarini qo'shish kerak.

Agar local `npm run dev` ishlatilsa, **demo/test** uchun `ALLOW_PUBLIC_REGISTRATION=1` qoldirish mumkin. Hosted `Dockerfile` `VITE_ALLOW_PUBLIC_REGISTRATION=0` bilan signup tugmasini yashiradi; bu serverdagi `ALLOW_PUBLIC_REGISTRATION=0` o'rnini bosmaydi.

## Litsenziya berish tartibi

1. Super Admin orqali yangi qahvaxona yarating (nom, noyob login/slug, rahbar va 4–6 xonali PIN). 14 kunlik sinov darhol boshlanadi.
2. Qahvaxona uchun `trial`, `active`, `grace`, `expired`, `suspended` holatini o'zgartiring.
3. To'lovni **o'zingiz tashqi tizimda** tekshirgandan keyin Admin paneldagi 30/90/365 kun uzaytirish tugmasini bosing; tasdiqlang.
4. `active` muddat hali tugamagan bo'lsa, uzaytirishda qolgan kunlar saqlanadi. Tugagan bo'lsa yangi muddat serverdagi hozirgi vaqtdan boshlanadi.
5. `expired` va `suspended` holatda mijoz eski savdo/ombor hisobotlarini ko'rishi mumkin, lekin yangi operatsiyalar server tomonidan rad etiladi. Admin uzaytirsa yozish huquqi avtomatik qaytadi.
6. Litsenziya o'zgarishlari oxirgi 100 yozuv sifatida ko'rinadi.

## API (Super Admin kaliti kerak)

- `GET /api/platform/companies`
- `POST /api/platform/companies`
- `PUT /api/platform/companies/{id}/subscription`
- `POST /api/platform/companies/{id}/subscription/extend` — JSON `{"days": 30}`
- `GET /api/platform/companies/{id}/license-history`
- Oddiy kafe loginiga tegishli: `GET /api/license/status` (status, canWrite, expiresAt, serverTime).

## Hali tijoriy release tayyor emas

- Avtomatik Click/Payme/to'lov provayderi yoki fiskal chek bilan bog'lash **yo'q**. To'lov avtomatik tasdiqlanmaydi.
- Tarif narxlari, chegirmalar, sotuv hujjatlari va mijozga ko'rsatiladigan qo'llab-quvvatlash siyosati hali belgilanmagan.
- Platform administratorning kuchli MFA tizimi, advanced billing audit va real PostgreSQL backup/restore testlari talab etiladi.
- Migratsiya va ishga tushirishni avval TEST COFFEE da tekshiring, ayniqsa eski tenantlarda `subscriptions` row mavjudligini. **Production MasterCoffee bazasiga hech qanday TEST ma'lumotni nusxalamang**.
- Android APK build va backend avtomatik testlaridan tashqari real qurilmadagi login, sync, smena va expiry banneri sinovi talab etiladi.

## Avtomatik testlar

```bash
cd backend
python -m pytest tests/test_license.py tests/test_platform.py -q
```

Testlar faqat alohida vaqtinchalik bazalarda ishlashi kerak. Import manzili ishlab turgan `C:\CoffeePoss\yangi-versiya` emas, **shu repository checkoutdagi** `backend/app` bo'lishini tekshiring.

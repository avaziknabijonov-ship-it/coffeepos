# CoffeePOS Super Admin: shaxsiy hisoblar, MFA, huquqlar va audit

Bu o'zgarish **4-band — Super Admin uchun alohida administrator akkauntlari va to'liq audit**ni TEST tarmog'ida joriy etadi. Dastlabki ishga tushirishga tegishli ko'rsatmalar. Hech qachon haqiqiy MasterCoffee SQLite faylini almashtirmang yoki dastlabki TEST admin ma'lumotlarini production'ga nusxalamang.

## Shaxsiy administrator hisoblari

| Rol | Kafelarni ko'rish | Litsenziya va yangi kafe | Narxlarni o'zgartirish | Adminlarni boshqarish | Platforma to'liq auditini ko'rish |
|---|---|---|---|---|---|
| **superadmin** | Ha | Ha | Ha | Ha | Ha |
| **manager** | Ha | Ha | Yo'q | Yo'q | Yo'q |
| **auditor** | Ha | Yo'q | Yo'q | Yo'q | Yo'q |

- Har bir administrator uchun **noyob login**, o'zi belgilagan **12+ belgili parol** (salt bilan PBKDF2-SHA256) va **shaxsiy TOTP 6 xonali kod**.
- TOTP seed PostgreSQL/SQLite bazasiga **Fernet shifrlangan** holda yoziladi. `PLATFORM_MFA_ENCRYPTION_KEY` kerak; bu kalit yo'qolsa administrator autentifikatorlari ishlamaydi — kalitni xavfsiz alohida backup qiling.
- Sessiya **15 daqiqa**; chiqish, bloklash, huquqni o'zgartirish, parol/MFA reset va asosiy `PLATFORM_ADMIN_KEY` almashishi eski sessiyalarni bekor qiladi.
- Birinchi administrator o'rnatilgach eski umumiy `X-Platform-Key` bilan API ga kirish **avtomatik taqiqlanadi**.
- Yagona faol bosh administratorni o'chirish yoki pasaytirish taqiqlangan.
- Inviteni olgan administrator o'zi MFA va parol tanlaydi. Taklif **24 soat** amal qiladi; server xotirasida faqat token SHA256 hashi turadi. Taklif tokenini yoki TOTP seedni chatga yubormang.

## 1. TEST server tayyorlash

`backend` API ishlaydigan serverning himoyalangan `.env` faylida quyidagilar bo'lsin:

```dotenv
PLATFORM_ADMIN_KEY=long-random-unique-platform-bootstrap-secret
PLATFORM_REQUIRE_MFA=1
PLATFORM_ADMIN_TOTP_SECRET=BASE32_BOOTSTRAP_SECRET
PLATFORM_REQUIRE_ADMIN_ACCOUNTS=1
PLATFORM_MFA_ENCRYPTION_KEY=FERNET_KEY
ALLOW_PUBLIC_REGISTRATION=0
LICENSE_ENFORCEMENT=0
SEED_DEMO=0
```

Kalitlarni haqiqiy yangi random qiymatlarga almashtiring. **Hech birini GitHub, chat yoki ekran rasmiga qo'ymang.** `PLATFORM_ADMIN_KEY` kamida 32 ta belgidan iborat. Quyidagi ikki buyruqni faqat **o'z serveringiz terminalida** ishlatib, natijalarni maxfiy saqlang:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import base64,secrets;print(base64.b32encode(secrets.token_bytes(20)).decode().rstrip('='))"
```

Birinchi buyruq `PLATFORM_MFA_ENCRYPTION_KEY`, ikkinchisi `PLATFORM_ADMIN_TOTP_SECRET` uchun. Bootstrap TOTP seedni shaxsiy autentifikator ilovangizga bir marta qo'lda kiriting. Server va telefon vaqti to'g'ri sinxron bo'lishi kerak.

**Production domen orqali admin login faqat HTTPS bilan ishlatilishi mumkin**. Nginx `/platform-admin` ni FastAPI'ga yo'naltiradi. Internetga HTTP bilan maxfiy kalit yubormang.

## 2. Birinchi Super Admin

1. TEST domenida `/platform-admin` sahifasini oching.
2. **Birinchi Super Admin hisobini yaratish** bo'limida shaxsiy login, serverdagi bootstrap maxfiy kaliti va bootstrap autentifikator kodini kiriting.
3. Bir martalik taklif tokeni quyidagi **Administrator hisobini faollashtirish** bo'limiga joylanadi.
4. **MFA kalitini olish** ni bosing. Yangi (bootstrap'dan **alohida**) TOTP seedni shaxsiy authenticator ilovangizga kiriting.
5. Kuchli shaxsiy parol va yangi MFA kodni tasdiqlang. Hisob faollashadi.
6. Endi yuqoridagi login formasiga o'z login/parolingiz/MFA kodini kiriting. Birinchi administrator yaratilib ketgandan keyin bootstrap maxfiy kalitini bevosita API kirishi sifatida ishlatish mumkin emas.

Agar birinchi taklif tokenining 24 soatlik muddati o'tib ketsa va hali hech bir faol Super Admin bo'lmasa, **faqat server terminalidagi offline recovery** yo'lidan foydalanish mumkin.

## 3. Menejer va auditor yaratish

Super Admin ichida **Administratorlar va huquqlar** bo'limi mavjud. Yangi login va rolni tanlang. Taklif tokeni faqat bir marta ko'rinadi; uni xodimga **shifrlangan, ishonchli aloqa orqali** yuboring. Yangi xodim o'z parolini va TOTP autentifikatorini o'zi faollashtiradi.

Administrator kerak bo'lmaganda **Bloklash** tugmasi uning avvalgi sessiyalarini darhol bekor qiladi. MFA telefoni yo'qolganda boshqa faol Super Admin **MFA/parolni yangilash**ni bosib yangi taklif beradi. Bu amalda eski parol, TOTP va sessiyalar bekor bo'ladi. Yagona faol Super Admin o'z MFA sini shu usulda tiklay olmaydi.

## 4. Audit va litsenziya tarixi

- `GET /api/platform/audit?limit=100&beforeId=...` — platforma bo'yicha sahifalangan barcha admin amallari: **actor**, **vaqt**, amal, kompaniya ID, oldingi/yangi qiymatlar. Faqat Super Admin ko'radi.
- `GET /api/platform/companies/{id}/license-history` — aynan o'sha qahvaxona litsenziyasining tarixi (administrator logini, muddati, oldingi/yangi holat).
- Kafe yaratish, litsenziyani aktivlashtirish/suspend qilish, tarif narxlari, admin hisobini yaratish, bloklash, reset va login/logout yangi audit yozuvlarini hosil qiladi.
- Dastur yangilanishidan **oldingi** voqealarda `actor=legacy-unknown` bo'lishi mumkin; o'tmishdagi kim bajarganini taxmin qilib to'ldirmaymiz.
- Auditning o'zi shu DB'da saqlanadi. **DB administratorlari o'zgartira olmaydigan alohida markaziy/SIEM log saqlash** va retention siyosati katta tijoriy xizmat uchun keyingi infratuzilma bosqichidir.

Admin API tokenlari, parollar va TOTP seedlari audit ichiga yozilmaydi. Adminlar shaxsiy akkauntini hech kim bilan bo'lishmasligi kerak.

## 5. Favqulodda tiklash (faqat server operatori)

Agar barcha Super Admin kirish yo'llari yo'qolsa, server konsolida maxsus offline script mavjud: `python -m app.recover_platform_admin --username USER --confirm RECOVER-PLATFORM-ADMIN`. U **faqat** `DATABASE_URL` aniq sozlanganda va `PLATFORM_RECOVERY_MODE=1` bo'lganda ishlaydi. Avval test muhitda bajaring.

Script nomlangan Super Admin hisobining eski parol/MFA/sessiyalarini bekor qiladi, yangi taklif tokenini stdout'ga **faqat bir marta** chiqaradi; tokenni xavfsiz joyda saqlang. Agar boshqa faol Super Admin bo'lsa, offline tiklash bloklanadi — o'sha admin o'z panelidan reset qilsin.

Ushbu jarayonni haqiqiy MasterCoffee production bazasida avvaldan backup va egasining aniq ruxsatisiz ishga tushirmang.

## Holat

Yuqoridagi funksiyalar `feature/platform-admin-accounts-20261013` sinov tarmog'ida. Ishlab turgan serverda shaxsiy admin login, MFA reset, audit, backup va barcha rollarni **TEST COFFEE** bilan tekshirmasdan productionga qo'shmang. Click/Payme kabi avtomatik to'lov ulanishi bu qismga kirmaydi.

# CoffeePOS — do‘konlarga nashr qilish tekshiruvi

Tekshirilgan sana: 2026-10-17. Holat: koddagi asosiy to‘siqlar tuzatildi;
Google Play/App Store’ga topshirish hali yakunlanmagan.

## Tuzatildi

- Google Play uchun target/compile SDK 36, mos AGP 8.10.1 va Gradle 8.11.1.
  Native loyiha qayta yaratilganda ham sozlamalar scripts/configure_android.py orqali qaytadi.
- Alohida store rejimi: HTTPS, ochiq ro‘yxatdan o‘tishsiz, ilovada tashqi obuna
  xaridiga chaqiriqsiz. Web/sinov APK’da mahalliy Wi-Fi rejimi saqlanadi.
- Maxfiylik va hisob sahifasi: login ekranida ham, Funksiyalar menyusida ham;
  web manzillar /privacy va /delete-account. UZ/RU matnlar.
- Rahbar qayta PIN kiritib, qahvaxona loginini va butun baza o‘chishini tasdiqlab
  hisobini o‘chiradi. Xodim/admin bu amalni bajara olmaydi. Muddati tugagan
  obuna o‘chirish huquqini to‘smaydi. Boshqa qahvaxona va platforma hisoblari qoladi.
- Eski tokenlar PIN o‘zgarganda yoki hisob o‘chirilganda bekor bo‘ladi.
  Yangilanishdan keyin eski sessiyalar bir marta qayta login qiladi.
- API so‘rovlariga 20 soniya, server tekshiruviga 15 soniya cheklov: aloqa
  uzilganda cheksiz aylanish o‘rniga xato ko‘rsatiladi.
- Sinovdan nashrni ajratadigan kirish tekshiruvi va qo‘lda ishga tushiriladigan
  `.github/workflows/store-package.yml`: imzosiz Android AAB va iOS arxiv.
  Bu workflow do‘konlarga hech narsa yubormaydi.
- Xcode 26 orqali iOS yig‘ish, versiya/build raqami, CoffeePOS ikonkalari,
  iPhone xavfsiz ekran chetlari. Android’da ilova ma’lumotlarini tizim backupiga
  avtomatik kiritish o‘chirilgan; server backupini alohida boshqarish zarur.

## Hali talab qilinadi

1. Doimiy public HTTPS server va CoffeePOS domeni. Bu tekshiruv mijozning
   kompyuteridagi amaldagi serverni yangilamadi; haqiqiy ma’lumotlarga tegmadi.
2. Xizmat operatorining tasdiqlangan support emaili va backupni saqlash/o‘chirish
   muddati. `VITE_SUPPORT_EMAIL` va `VITE_PRIVACY_BACKUP_DAYS` haqiqiy amaliyotga
   mos bo‘lishi shart. Barcha backup joylarida muddatli tozalash va o‘chirilgan
   hisoblarni restore paytida qaytarmaslik tartibini joriy etish kerak.
3. Platforma ma’lumotlari (license audit, mijoz sluglari) yoki boshqa qurilmalardagi
   to‘lanmagan savatlar avvalgi backuplarda qolishi mumkin. Ushbu versiya server
   ishchi bazasini o‘chiradi; offsite nusxalar va boshqa qurilmalarga masofadan
   o‘chirishni va’da qilmaydi. Xodimlarning alohida privacy so‘rovlarini kafe
   rahbari bajaradi; majburiy hisobotlarni saqlash tartibi operator bilan belgilanadi.
4. Google Play Console / Apple Developer hisoblari, shaxs/tashkilot tasdig‘i;
   Android upload key, Apple signing va provisioning. Sirlarni repoga joylamang.
5. Alohida, haqiqiy mijozdan ajratilgan, ishlaydigan demo server/hisoblar. Ularni
   do‘konning App access / Review information maydoniga bering. Public repo ichida
   production PIN yoki kalit bo‘lmasin. Demo hisobi sinov vaqtida bloklanmasin.
6. Play Data safety / App Store App Privacy: xodim va mijoz ismlari, kafe ID,
   buyurtma/qarz/ish haqi ma’lumotlari, operator/serverga uzatish holatini haqiqiy
   deployment bo‘yicha ko‘rsating. Reklama/tracking SDK hozir yo‘q. Host loglari va
   kelajakdagi SDK o‘zgarishlari deklaratsiyani qayta tekshirishni talab qiladi.
7. Haqiqiy iPhone, iPad va Android planshetda sotuv, chegirma, ombor, smena,
   rus/o‘zbek til, klaviatura, burilish, tarmoq uzilishi/502 va qayta kirish sinovi.
   Simulator yoki kompilyatsiya haqiqiy qurilmadagi sinov o‘rnini bosmaydi.
8. Printer sinovi: hozirgi chek tugmasi `window.print()`ga tayangan. Native
   Bluetooth/USB/AirPrint qo‘llab-quvvatlashi isbotlanmagan; do‘kon tavsifida
   buni tayyor funksiya deb ko‘rsatmang. Zarur printer uchun alohida integratsiya kerak.
9. Hozirgi zal rejasi va to‘lanmagan stol savatlari qurilmada saqlanadi, boshqa
   planshetlar bilan sinxronlashmaydi. To‘lovni yuborishdan oldin aloqa yo‘qolsa
   server natijasini tekshiring; offline savdo kafolatlanmagan.
10. Store tavsifi, real skrinshotlar, support/privacy URL, yosh reytingi va kontent
    deklaratsiyalari. Narxlar/digital subscriptions modelini do‘kon talablari bilan
    solishtiring: CoffeePOS tashkilotlarga xodimlari uchun xizmat sifatida ko‘zlangan.
    Iste’molchi uchun raqamli obuna sotish qo‘shilsa billing qayta loyihalanadi.
11. Yangi shaxsiy Google hisoblari uchun tegishli yopiq test: kamida 12 tester,
    uzluksiz 14 kun. Bu muddatni kod bilan almashtirib bo‘lmaydi.

## Nashr paketini tayyorlash

GitHub Actions → Store package (unsigned, no publication). Haqiqiy HTTPS origin,
support email, amalda bajariladigan backup muddati, oldingi uploaddan yuqori build
raqamini kiriting. API origin odatda nginx orqali frontend va /api’ni birga beradi;
privacy va deletion sahifalari ham shu domenda ochilishi kerak. Workflow imzolashsiz
kompilyatsiya qiladi. AAB’ni o‘z upload key’ingiz bilan imzolang; iOS arxivni Apple
hisobida imzolab TestFlight’ga topshiring. Imzosiz arxiv install qilinadigan IPA emas.

Mahalliy tekshiruvlar:

```sh
npm ci
npm run build
npm run lint
node scripts/test-mobile-api.mjs
python -m pip install -e './backend[dev]'
PYTHONPATH=backend python -m pytest backend/tests -q
```

## Rasmiy talablar

- https://developer.android.com/google/play/requirements/target-sdk
- https://developer.android.com/build/releases/agp-8-10-0-release-notes
- https://support.google.com/googleplay/android-developer/answer/14151465
- https://support.google.com/googleplay/android-developer/answer/13327111
- https://developer.apple.com/app-store/review/guidelines/
- https://developer.apple.com/news/upcoming-requirements/?id=04282026a
- https://developer.apple.com/support/offering-account-deletion-in-your-app/

Do‘kon tomonidan qabul qilinish yakuniy tekshiruv natijasiga bog‘liq.

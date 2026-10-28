# Zal xaritasi — 2026-10-27

Kassa → Zal xaritasi stollarni zal bo‘yicha chizadi. Band stol ko‘k, bo‘sh stol kulrang; band stolni bosish saqlangan buyurtmani davom ettiradi. Bir stolda bir nechta draft bo‘lsa buyurtmalar tanlash oynasi ochiladi. Xarita ochiq paytda holat 10 soniyada yangilanadi.

Admin → Zal va stollar: xaritada stolni tanlang, shakl (dumaloq/to‘rtburchak/Bar/VIP), chapdan/yuqoridan joy va kenglik/balandlikni sozlab Saqlash tugmasini bosing. O‘zgarish avval ko‘rib chiqiladi, keyin saqlanadi. Joylashuv DiningTable.layout JSON ustunida, layout_version eski tabdan yangi sozlamani bosib yuborishdan himoyalaydi. Migratsiya 8 qo‘shimcha ustunlar kiritadi. Owner/admin tahrirlaydi, kassir o‘qiydi. Tenant/filial chegaralari tekshiriladi, audit yoziladi.

Dastlabki tartib: 1–4 yuqorida, 10–14 o‘rtada, 9–5 pastda; Bar chapda, VIP o‘ngda. Bunday nomlar mavjud bo‘lsagina chiziladi; foydalanuvchi bazasida yangi stollar avtomatik yaratilmaydi. Boshqa nomlar avtomatik katak tartibida joylanadi va admin tahrirlay oladi. Suratdagi xona faqat disposable brauzer testida fixture sifatida yaratildi. Kichik ekranlarda xarita surib ko‘riladi. Sichqoncha bilan sudrash bu versiyada yo‘q; joylashuv raqamli maydonlardan sozlanadi. Bir-biriga ustma-ust qo‘yishni admin nazorat qiladi.

Tekshiruv: backend SQLite 96 passed / 3 PostgreSQL-only skipped; frontend 11/11; brauzer 16/16 (joylashuvni tahrirlash, reload, kassada o‘sha joylashuv, band stol draftini ochish); build, i18n, eski baza migratsiya drill 15/15. Lint xatosiz, ogohlantirishlar bor. Production, merge va deploy bajarilmadi.

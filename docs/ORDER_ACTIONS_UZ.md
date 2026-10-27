# Chek amallari — 2026-10-27

Kassadagi ⋯ Chek amallari menyusi:
- Chekka izoh: 500 belgigacha. Tayyor oynani yopadi; izoh buyurtmani saqlash, ko‘chirish, ajratish, mas’ul tayinlash yoki to‘lovda serverga yoziladi. Yakuniy kassir chekida ko‘rsatiladi.
- Stolni almashtirish: mavjud savat avval serverga saqlanadi, so‘ng version bilan bo‘sh stolga yoki olib ketishga o‘tkaziladi. Band stolga ko‘chirish rad etiladi.
- Chekni ajratish: hozir tanlangan mehmon mahsulotlari alohida draftga ko‘chadi. Asl draftda boshqa mehmonlar qolishi shart. Ikki chek shu stolda qoladi va alohida to‘lanadi. Bu amal pul qabul qilmaydi, stock yechmaydi. Mehmon raqamlari, izoh va mas’ul nusxalanadi. Saqlangan buyurtmalar ro‘yxatida chek ID va mehmon raqamlari ko‘rinadi.
- Buyurtmani tozalash: tasdiq so‘raladi; mavjud draft version tekshiruvi bilan o‘chiriladi. Xato bo‘lsa savat yo‘qolmaydi.
- Mas’ul xodimni almashtirish: faqat manager; tenant/filial va active holati serverda tekshiriladi. Savdoni amalga oshirgan kassirning staff_id va audit actor'i o‘zgartirilmaydi. Mas’ulning nomi alohida snapshotda qoladi.
- Mehmonlar soni: 1–50. Mahsuloti bor mehmon raqamidan pastga kamaytirish mumkin emas. Bo‘sh mehmonlar soni ham endi draftda saqlanadi.

Migratsiya 9: orders/draft_orders note, guest_count va waiter_name qo‘shimcha ustunlari. Chek ajratish va mas’ul tayinlash version guard bilan himoyalangan; amallar auditga yoziladi (izoh matni auditga yozilmaydi).

Mahalliy tekshiruvlar: SQLite backend 98 passed / 3 PostgreSQL-only skipped; frontend 11/11; Playwright 18/18. Browser izoh, mehmonlar soni, mas’ul tayinlash va split saqlanishini tekshiradi. API testi split, eski version, move, izoh/mas’ulning checkoutgacha yetishi, stol bo‘shashi va delete'ni tekshiradi. Build va i18n o‘tdi; lint xatosiz, ogohlantirishlar bor. Legacy SQLite migratsiya drill 15/15. Production, merge/deploy qilinmadi. Yangi kod foydalanuvchining eski Windows zip nusxasiga hali o‘rnatilmagan.

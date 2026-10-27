# Mahsulot va kategoriya rasmlari — 2026-10-27

Admin → Menyu → kategoriya yonidagi Rasm orqali kategoriya rasmini tanlash, almashtirish yoki olib tashlash mumkin. Mahsulotni tahrirlash oynasida ham fayl tanlash va URL mavjud. JPG/PNG/WebP, ko‘pi bilan 3 MB; server faylni haqiqiy rasm sifatida ochadi, 16 megapiksel chegarasini tekshiradi, 1024 pikselgacha kichraytiradi va metadatasiz WebP qilib saqlaydi. SVG qabul qilinmaydi.

Rasmlar catalog_images jadvalida saqlanadi va DB backup tarkibiga kiradi. Yuklash faqat owner/admin uchun; boshqa kompaniya rasmiga havola biriktirish rad etiladi. Rasmni ko‘rish uchun taxmin qilib bo‘lmaydigan ochiq URL ishlatiladi: katalog rasmlariga shaxsiy hujjat yuklamang. Har tenant uchun jami saqlangan rasmlar chegarasi 30 MB. Rasmdan voz kechish uning havolasini mahsulot/kategoriyadan olib tashlaydi; eski fayllarni avtomatik tozalash hozir mavjud emas.

Kategoriya image_url ustuni uchun qo‘shimcha migratsiya 7 qo‘shildi. Eski kategoriyani faqat nomini o‘zgartirish rasmni o‘chirmaydi. Google share havolalari uchun faylni yuklash tavsiyasi chiqariladi; rasm ochilmasa kassada o‘rinbosar belgi chiqadi. Rasm URL'lari server tomonidan tashqi manzildan yuklab olinmaydi.

Tekshiruvlar: SQLite backend 95 passed / 3 PostgreSQL-only skipped; frontend 11/11; build o‘tdi; i18n 734 kalit tekshiruvi o‘tdi; lint mavjud ogohlantirishlar bilan, xatosiz; eski SQLite bazasidan migratsiya drill 15/15. Lokal Playwright 15/15, shu jumladan kategoriya rasmini yuklash, kassada ko‘rsatish, reload va mahsulot rasm picker'i.

Windows'dagi eski zip nusxa avtomatik yangilanmaydi. Yangi versiyada backend dependency (Pillow) ham o‘rnatilishi kerak. Production, merge va deploy bajarilmadi. Bu ish barcha 23 modul yoki avval so‘ralgan barcha zal/guest funksiyalari qabul qilinganini anglatmaydi.

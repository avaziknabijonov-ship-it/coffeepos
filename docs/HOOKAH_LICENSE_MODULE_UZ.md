# Litsenziyalanadigan Kalyanxona moduli — 2026-10-28

CoffeePOS asosida alohida biznes ko‘rinishi. Superadmin yangi kompaniya yaratishda yoki litsenziya Berish/Uzaytirish paytida Kalyanxona moduli checkbox'ini tanlaydi. Tanlov aynan o‘sha litsenziya amali bajarilganda saqlanadi; checkbox'ni o‘zgartirishning o‘zi serverni o‘zgartirmaydi.

Yangi kalyanxona akkaunti: Kalyan, Choy, Sovuq ichimliklar, Sneklar kategoriyalari; mahsulot va xomashyo ro‘yxati bo‘sh — egasi o‘z brend/narx/gramm sarfini kiritadi. Standart kofe mahsulotlari, sut/sirop modifierlari bu profilga yuklanmaydi. Oddiy yangi CoffeePOS akkaunti avvalgidek yaratiladi.

Mavjud kompaniyaga modul ulansa, mahsulotlar, ombor va savdo tarixi o‘zgartirilmaydi/o‘chirilmaydi. Agar kalyan kategoriyasi yo‘q bo‘lsa bitta bo‘sh kategoriya qo‘shiladi; bor kategoriya takrorlanmaydi. Modul o‘chirilganda barcha tarix qoladi. `majlis1` va boshqa production akkauntlarga avtomatik litsenziya berilmadi.

Modulli akkaunt o‘zining lounge uslubidagi admin va kassasini ko‘radi: Kalyanxona hisoboti; Zal, Bar va VIP; Tamaki va sarf materiallari; Tamaki va bar kirimi; Kalyan va bar menyusi; Aralashmalar va sarf retseptlari; Kalyanchilar va kassirlar. Barista roli ko‘rinishda Kalyanchi deb ataladi, uning amaldagi xavfsizlik ruxsatlari o‘zgarmaydi. Admin paneldagi mavjud moliya, audit, payroll, bonus, transfer va xavfsizlik komponentlari qayta ishlatiladi. Bu alohida baza yoki yangi dastur nusxasi emas.

Litsenziya: subscriptions.modules JSON, qo‘shimcha migratsiya 10. Eski litsenziyalar bo‘sh modullar bilan qoladi. ENFORCE_LICENSES=0 bo‘lsa ham ixtiyoriy hookah moduli uchun active va tugamagan litsenziya shart. `/api/me` va login faqat amaldagi modullarni qaytaradi; `/api/modules/hookah` serverda company va rolni tekshiradi. Muddati tugashi/suspend/modul olib tashlanishi access'ni rad etadi; UI 15 soniyada tekshiradi va mavjud savatni o‘chirmasdan ko‘rinishni to‘sadi. Litsenziya o‘zgargach navigatsiya login/reload bilan yangilanadi.

Modul alohida xona vaqtiga tariflash, ko‘mir almashtirish eslatmalari yoki native printer integratsiyasini hali qo‘shmaydi. Tamaki gramm sarfi mavjud texkarta va ombor dvigatelida yuritiladi. Umumiy katalog/savdo endpointlari oddiy CoffeePOS uchun saqlanadi; litsenziya qo‘shimcha hookah ish maydonini boshqaradi.

Tekshiruvlar: backend SQLite 99 passed / 3 PostgreSQL-only skipped; frontend 11/11; browser 19/19; migratsiya drill 15/15. Yoqish, renew'da saqlanish, modulni olib tashlash, suspend/expiry, tenant chegarasi, noqonuniy nom va superadmin ruxsati sinovdan o‘tdi. Brauzerda checkbox → litsenziya → alohida admin/kassa → revoke oqimi o‘tdi. Build/i18n o‘tdi; lint xatosiz, mavjud ogohlantirishlar qolgan. Production/VDS o‘zgartirilmadi, merge/deploy qilinmadi.

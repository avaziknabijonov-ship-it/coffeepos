# CI ogohlantirishlari — 2026-10-28

Yuborilgan GitHub Actions rasmlaridagi 15 warning va 5 notice tekshirildi.

- Finance, Payroll, Operations va chek tarixi effektlari ma’lumotni bevosita asinxron so‘rov orqali oladi, dependency ro‘yxatlari to‘liq. So‘rov revision'i eskirgan javobning yangisini almashtirishini va yopilgan komponentga natija qo‘llanishini to‘sadi.
- Superadmin kalitini o‘zgartirish panel holatini o‘sha input event'ida tozalaydi; oldingi kalit uchun kelgan kech javob panelni qayta ochmaydi.
- Dashboard sana komponent ishga tushganda olinadi va taymerda yangilanadi; render ichidagi impure Date chaqirig‘i olib tashlandi.
- FloorMap yordamchi funksiya/tiplari floorLayout.ts'ga ajratildi; komponent Fast Refresh talabiga mos.
- Admin, Superadmin, HookahPOS va Barista React.lazy orqali yuklanadi. Eng katta dastlabki JS fayl ~287 kB; 500 kB chunk ogohlantirishi yo‘q.
- Uchta workflow'da runner ubuntu-24.04 bilan belgilandi; ubuntu-latest ko‘chishi haqidagi notice olib tashlanadi.
- Rasmiy action.yml fayllarida Node 24 tasdiqlangan aniq versiyalar: checkout v7.0.1, setup-node v7.1.0, setup-python v7.1.0, upload-artifact v7.0.2, setup-java v6.1.0. CI ichidagi ilova Node versiyasi bilan action runtime'i alohida tushunchalar.
- Lint endi `oxlint --deny-warnings`: ogohlantirish qaytsa job muvaffaqiyatsiz tugaydi. Qoidalar o‘chirilmagan/yashirilmagan.

Lokal natijalar: lint 0 warning / 0 error; TypeScript/Vite build; frontend 11/11; i18n 780 kalit; SQLite backend 99 passed / 3 PostgreSQL-only skipped; Playwright 21/21. Qo‘shilgan browser regressiyalar: kechikkan eski finance davri javobi va eski superadmin kaliti javobi. Backend test kutubxonasining Starlette/httpx deprecation xabari hali mavjud; u bu rasmlardagi React va Actions ogohlantirishlaridan alohida.

CI natijasi commit/run orqali alohida tekshiriladi; eski run annotations tarixdan o‘chmaydi. Android workflow'larining action/runtime sozlamalari yangilandi, lekin imzolangan production APK bu ishda yig‘ilmagan. Production/VDS, deploy va merge bajarilmadi. Ushbu tuzatishlar 23 modulning real uskuna va provayder qabul sinovlarini almashtirmaydi.

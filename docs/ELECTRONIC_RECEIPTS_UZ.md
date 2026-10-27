# Muddati cheklangan elektron chek

Productionga chiqarilmagan. Yangi DB jadvali yoki ustun talab qilmaydi.

Owner/admin chek tarixida havola yaratadi. API faqat o‘z company_id buyurtmasini imzolaydi. Havola 15 daqiqa amal qiladi, shu vaqt ichida havolasi bor har kim ko‘rishi mumkin. Avtomatik SMS/Telegram/email yuborilmaydi.

HS256 token audience va purpose bilan cheklangan. Login tokeni chekni ochmaydi, chek tokeni auth API uchun yaramaydi. Har yangi havolada jti boshqa; eskisi amal muddati tugaguncha ishlaydi. Alohida revocation yo‘q. SECRET_KEY o‘zgarsa barcha havola va sessiyalar bekor bo‘ladi.

Ommaviy sahifa: kompaniya nomi, chek raqami, sana, mahsulot nomi/o‘lcham/son/narx, chegirma, jami, qaytarilgan summa va cancel holati. Mijoz nomi/telefon, kassir ismi, texkarta/tannarx va erkin izohlar chiqarilmaydi. HTML escaped, CSP scripts va framesni bloklaydi, cache no-store, referrer no-referrer, robots noindex.

Bu FISKAL CHEK EMAS. Fiskal provider, fiskal QR va haqiqiy printer testi mavjud emas. Muddati o‘tgan havola 404 qaytaradi. Sahifa qaytarish/cancelning joriy holatini ko‘rsatadi.

Staging/production oldidan HTTPS va URL loglarini redaction qilish majburiy: token URL ichida bo‘lgani uchun reverse proxy va API access loglari uni yozishi mumkin. Ularni qo‘llab-quvvatlash chatiga yoki analyticsga yubormang. Ushbu commit production logging sozlamalarini o‘zgartirmaydi. Native APK alohida API domeniga ulanganida havola shu domen orqali ochilishini tekshiring.

Avtomatik testlar: RBAC, tenant isolation, expiry, audience/purpose separation, buzilgan token, XSS escape, maxfiy maydonlar yo‘qligi, UZ/RU va security headers. Haqiqiy brauzer va staging sinovi hali yo‘q.

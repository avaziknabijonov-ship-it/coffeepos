# Muddati cheklangan elektron chek

Productionga chiqarilmagan. Additiv migratsiya: startup create_all orqali receipt_links jadvali yaratiladi (company/order foreign key, SHA-256 jti ID, expiry va revoked_at). Buyurtmalar o‘zgarmaydi. Oldingi stateless havolalar grant yozuvi bo‘lmagani uchun yaroqsiz bo‘ladi; rahbar yangisini yaratadi. Migratsiya productionda bajarilmadi.

Owner/admin chek tarixida havola yaratadi. API faqat o‘z company_id buyurtmasini imzolaydi. Havola 15 daqiqa amal qiladi, shu vaqt ichida havolasi bor har kim ko‘rishi mumkin. Avtomatik SMS/Telegram/email yuborilmaydi.

HS256 token audience va purpose bilan cheklangan. Login tokeni chekni ochmaydi, chek tokeni auth API uchun yaramaydi. Har yangi havolada jti boshqa; bazada token emas, jti SHA-256 xeshi saqlanadi. Owner/admin DELETE /api/orders/{oid}/receipt-links orqali chekdagi barcha faol havolalarni bekor qiladi; bu amal qayta bajarilganda yangi audit yozuvi chiqmaydi. Yangi havolani yana yaratish mumkin. Issue/revoke PostgreSQLda order qatori orqali ketma-ketlashtiriladi. Havola yaratish/bekor qilish auditga bir tranzaksiyada yoziladi. SECRET_KEY o‘zgarsa barcha havola va sessiyalar bekor bo‘ladi.

Ommaviy sahifa: kompaniya nomi, chek raqami, sana, mahsulot nomi/o‘lcham/son/narx, chegirma, jami, qaytarilgan summa va cancel holati. Mijoz nomi/telefon, kassir ismi, texkarta/tannarx va erkin izohlar chiqarilmaydi. HTML escaped, CSP scripts va framesni bloklaydi, cache no-store, referrer no-referrer, robots noindex.

Bu FISKAL CHEK EMAS. Fiskal provider, fiskal QR va haqiqiy printer testi mavjud emas. Muddati o‘tgan havola 404 qaytaradi. Sahifa qaytarish/cancelning joriy holatini ko‘rsatadi.

Standart uvicorn.access logger token va query stringni [REDACTED] bilan almashtiradi; startup filteri va real logger testi bor. Staging/production oldidan HTTPS, reverse proxy/CDN/APM loglarini redaction qilish alohida tekshiriladi; ilova filteri tashqi loglarni himoyalamaydi. Ularni qo‘llab-quvvatlash chatiga yoki analyticsga yubormang. Production logging sozlamalari o‘zgartirilmagan. Native APK alohida API domeniga ulanganida havola shu domen orqali ochilishini tekshiring.

Avtomatik testlar: revoke/expiry, bekor qilingandan keyin qayta yaratish, takroriy audit yo‘qligi, grant/token maxfiyligi, access log redaction, RBAC, tenant isolation, expiry, audience/purpose separation, buzilgan token, XSS escape, maxfiy maydonlar yo‘qligi, UZ/RU va security headers. Haqiqiy brauzer va staging sinovi hali yo‘q.

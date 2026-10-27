# Mijozlar tahlili va rozilik

Yangi mijozlar ham, eski mijozlar ham default tahlilga roziliksiz. Startup additive migratsiya customers.analytics_consent (false), consent_updated_at va consent_actor_id ustunlarini qo‘shadi. Bonus saldo va telefon o‘zgarmaydi. Migratsiya qayta bajarilishi sinovdan o‘tadi; staging backupdan restore hali bajarilmagan.

Owner/admin mijozdan rozilik olinganini alohida tasdiqlab yozadi; bu mijozning o‘zi imzolagan raqamli hujjat emas. Rozilikni bekor qilish qayta so‘ralgan analytics va purchase-historydan mijozni chiqaradi. Bonus va moliyaviy orderlar o‘chirilmaydi. Consent o‘zgarishi actor ID/timestamp bilan bir tranzaksiyada operational auditga tushadi. Bir xil holatni retry qilish yangi audit yozmaydi.

Mijozlar ro‘yxati owner/admin uchun cursor pagination (max 100): id, ism, telefonning oxirgi 4 belgisi, consent holati. Tahlil va Excel faqat agregatlar: rozilar, davrdagi xaridorlar, 2+ faol cheki bor xaridorlar, orderlar va gross tushum. Ro‘yxatdan o‘tish oyi va xarid oyi kesimidagi faoliyat matritsasi bor. Bu retention foizi emas. Bir nechta chek bir kunda ham «takroriy xarid» hisoblanadi.

Davr 1–92 kun. Cancelled orderlar agregatga kirmaydi; refund gross tushumdan ayrilmaydi (UI’da belgilangan). Xaridlar tarixi status bilan, 50 tadan sahifalanadi, mijoz/telefon/tannarx kiritilmaydi. Eski tarix rozilik yoqilganda tahlilga kiradi; consent faqat kelajak savdolariga cheklangan rejim yo‘q.

Faqat order.customer_id bilan bog‘langan savdolar tahlil qilinadi; hozir bu asosan bonus yoqilgandagi ro‘yxatli savdolar. Anonim savdo, barcha mijozlar ulushi va refund-net cohort hisoboti yo‘q. Cohort guruhlari kichik bo‘lishi mumkin; hisobot ommaviy emas. Bekor qilingan rozilik avval eksport qilingan Excelni qurilmadan o‘chira olmaydi. Retention/deletion siyosati va filiallar kesimi hali ochiq.

Test: default opt-out, operator tasdig‘i, immediate revoke, masked phone, manager RBAC, tenant isolation, customer history, cohort/gross/repeat arifmetika, idempotent audit, davr/pagination chegaralari va eski schema migratsiyasi. Browser/staging qabul sinovi hali yo‘q. Productionga tegilmagan.

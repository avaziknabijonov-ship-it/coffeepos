# Qurilmalar: ro‘yxatga olish va sessiyani bekor qilish

Productionga chiqarilmagan. Filial modeli hali yo‘q; kompaniya chegarasi serverda tekshiriladi. Bu brauzer/APK ichidagi mantiqiy ro‘yxatga olish, hardware fingerprint yoki MDM emas.

## Migratsiya va moslik

Startup Base.metadata.create_all additiv ravishda devices va device_policies jadvallarini yaratadi. Mavjud company/staff/order o‘zgarmaydi. Qurilma majburiyligi avvalgi kompaniyalarda o‘chiq; eski JWTlar default rejimda ishlaydi. Legacy bazaga init_db ikki marta bajarilishi va staff ma’lumotlari saqlanishi test qilindi. Production bazasiga migratsiya bajarilmagan.

## Ishlash tartibi

1. Rahbar yoki administrator ishlatiladigan brauzerda PIN bilan kiradi va Qurilmalar bo‘limida nom berib ro‘yxatga oladi.
2. Server 256 bitli tasodifiy credential yaratadi, faqat SHA-256 xeshini saqlaydi. Secret bir marta authenticated enrollment javobida keladi; frontend uni localStorage’da kompaniya bo‘yicha saqlaydi. List, audit va hisobotga secret chiqmaydi. Enrollment tokeni darhol yangi qurilmaga bog‘lanadi.
3. Rahbar chiqadi. Kassir/barista shu brauzerda o‘z PIN kodi bilan kiradi. Login kompaniya/PIN bilan birga saqlangan credentialni yuboradi. JWT did orqali serverdagi device IDga bog‘lanadi. Boshqa kompaniya credentiali/token bog‘lanishi rad etiladi.
4. Owner/admin qurilmani bekor qilsa, undan oldin berilgan barcha bog‘langan JWTlar keyingi API so‘rovida 401 oladi. Login ham eski credential bilan rad etiladi. Qayta revoke yangi audit yaratmaydi. Reactivate yo‘q: yangi ro‘yxatdan o‘tkazish yangi credential/ID beradi.
5. Owner majburiy tartibni yoqsa kassir/barista qurilmasiz kira olmaydi; oldingi unbound JWTlar ham API’da rad etiladi. Qurilma ma’lumotlarini brauzerdan o‘chirish bu tartibni chetlab o‘tmaydi.

Owner/admin PIN orqali qurilmasiz kirib tiklashi mumkin — bu ochiq ko‘rsatilgan boshqaruv istisnosi. Faqat owner majburiy tartibni o‘zgartiradi. Administrator ro‘yxatga olishi va bekor qilishi mumkin. Login oynasidagi bog‘lanishni unutish faqat lokal credentialni o‘chiradi; server qurilmasi avtomatik o‘chmaydi.

Last-seen authenticated API faolligi bo‘yicha minutiga ko‘pi bilan bir marta yoziladi, login va enrollmentda ham yangilanadi. Enrollment/revoke/policy audit biznes amali bilan bir tranzaksiyada. PostgreSQLda takroriy revoke order-independent device row lock bilan ketma-ketlashtiriladi; policy uchun company row lock ishlatiladi.

## Cheklovlar va sinovlar

Credential brauzer profiliga bog‘langan; uni ko‘chirgan shaxs va PIN egasi ro‘yxatdan o‘tgan qurilma sifatida kira oladi. Hardware attestation, branch binding, secure Android keystore, masofadan local cache o‘chirish va qurilma soni/litsenziya limiti hali yo‘q. Qurilma o‘chirilganda allaqachon bajarilayotgan so‘rov avtomatik ortga qaytarilmaydi. Offline brauzer revoke haqida qayta ulanganda biladi; server bekor qilingan token orqali navbatdagi savdoni qabul qilmaydi. Majburiy tartib o‘chiq bo‘lsa yangi PIN login qurilmasiz mumkin; UI va API buni yashirmaydi.

API: GET/POST /api/devices; POST /api/devices/{id}/revoke; PUT /api/devices/policy. Token/credential yuborish faqat HTTPS orqali stagingda tasdiqlanadi. Proxy/APM request-body loggingi secretni yozmasligi alohida tekshiriladi.

Avtomatik testlar: RBAC, tenant isolation, secret hashing/privacy, invalid JWT did types, stale JWT revoke, last-seen, majburiy tartib bilan legacy sessiya, manager recovery, takroriy revoke audit dedupe, additiv migration. Ikki PostgreSQL-only test double revoke va login/revoke race holatlarini tekshiradi. UI build va literal UZ/RU kalitlari tekshirildi; brauzer/APK/staging qabul sinovi hali bajarilmagan.

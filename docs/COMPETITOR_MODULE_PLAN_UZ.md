# CoffeePOS — original mahsulot modullari (2026-10-25)

Maqsad: O‘zbekistonda 1 ta coffee point'dan 100+ qahvaxonagacha mos POS yaratish.
Bu hujjat raqobatchilardagi umumiy biznes imkoniyatlarini o‘rganadi; ularning kodini, ekrani, brendi yoki axborot arxitekturasini ko‘chirishga ruxsat bermaydi.

**UX qat'iy tamoyili:** Kassa buyurtma va to‘lovni qabul qiladi; Barista alohida tayyorlash navbatini boshqaradi. Rahbar kassirga ixtiyoriy «barista vazifasi ham» ruxsatini berishi mumkin. Admin’da yangi buyurtma olish yo‘q; faqat nazorat, chek tarixi, sozlama, moliya. Planshetda tez, sodda.

## Manbalar (ommaviy funksiya ro‘yxatlari; marketing emas, real ishga tushish testlari ustun)
- Clopos: https://www.clopos.com/uz/features ; https://www.clopos.com/uz/compare ; https://www.clopos.com/uz/multilocation-restaurant-pos
- Poster: https://joinposter.com/en ; https://knowledge-base.joinposter.com/ru/ ; https://knowledge-base.joinposter.com/ru/how-to-work-with-inventory
- iiko: https://iiko.ru/solutions/coffee-shop/ 
- r_keeper: https://docs.rkeeper.ru/ ; https://rkeeper.ru/select-module/
- JOWI: https://jowi.app/ (JS-ga bog‘liq, to‘liq ochiq katalog cheklangan); https://biznestizim.uz/uz/tizimlar/jowiapp (uchinchi tomon tavsifi, tasdiqlash talab etiladi)

## 1. Clopos: amaliy savdo va boshqaruv
| Yo‘nalish | Raqobatchi g‘oyasi | CoffeePOS qarori |
|---|---|---|
| Ochiq chek | Saqlash/tahrirlash | P0 — serverda «draft/order» va to‘lovdan keyin yakunlash; takroriy to‘lovdan himoya |
| Chekni qaytarish | Qisman/to‘liq | P0 — qaytarish tarixini saqlash, to‘lov va ombor reversali, rahbar ruxsati |
| Ombor | Past zaxira, transfer, kirim, qayta sanash | P0/P1 — kamomad mavjud, filiallararo transfer va minimal qoldiq bildirishnomalari qo‘shiladi |
| Mijoz bazasi | Bonus, xaridlar tarixi | P1 — maxfiy telefon bilan mijoz profili, bonus ledger va tranzaksiya tarixi |
| Xodim | Ruxsat va ish vaqtini hisoblash | P0/P1 — dual-role ixtiyoriy, smena soatlari, stavka va avans hisobi |
| Boshqaruvchi mobil | Barcha nuqtalar hisobi | P1 — mobilga mos read-only direktor dashboard |
| QR menyu | Menyu ko‘rish va buyurtma | P2 — kerak bo‘lgan filial uchun ixtiyoriy modul |
| Multi-branch | Bitta boshqaruv paneli | P1 — markaziy kompaniya/filial arxitekturasi, omborlar ajratilgan |

## 2. JOWI: oddiy ishlash, oshxona-kassa bog‘lanishi
- P0: Kassa → Barista holat ketma-ketligi, real vaqtda yangi buyurtma va holat ko‘rsatish.
- P0: Texkarta asosida ichimlik bo‘yicha aniq gramm/ml minus qilish.
- P1: Savdo bilan moliyaviy ko‘rsatkichni bir xil order ID orqali bog‘lash; harakatlar audit logi.
- P2: Zalda stol boshqaruvi va bron; faqat stolda xizmat ko‘rsatadigan qahvaxonalar uchun.
- JOWI sayti texnik JS talab qiladi; barcha imkoniyatlari mavjud deb taxmin qilinmaydi. Mustaqil funksiya testlari talab.

## 3. iiko: murakkab hisobni soddalashtirib olish
- P0: Texkarta, tannarx, nakladnoy, chiqim, kamomad bo‘yicha aniq hujjat va stock movement ledger.
- P1: Yetkazib beruvchi rekvizitlari, narxlar tarixi, yetkazib beruvchiga qarz va qisman to‘lovlar.
- P1: Kunlar kesimidagi revenue, COGS, xarajat, berilgan oylik/avans va naqd oqimi; «taxminiy operatsion foyda» yorlig‘i.
- P1: Kunlik/smena asosida ish vaqtini belgilash, stavka, avansdan minus, audit.
- P2: 7/30 kunlik mahsulot sarfi prognozi, minimal qoldiq asosida bozorlik ro‘yxati.
- P2: Filiallar uchun menyu narxini markaziy boshqarish, lekin lokal narxga ruxsat.
- Soliq/fiskal integratsiya faqat huquqiy tasdiqlangan provayder API orqali.

## 4. Poster: oddiy tablet UX va ishonchlilik
- P0: Android/Windows online, internet uzilsa locally persisted transaction queue. Idempotency key server va qurilma tomonida, qayta ulanib ikki marta sotmaslik.
- P0: Termoprinterlar: ESC/POS test matritsasi (USB/LAN/Bluetooth); Androidda nativ bridge, Windowsda mos bridge. Web window.print — to‘liq yechim emas.
- P0: Smena ochish/yopish, kassa pulini naqd xarajat bilan solishtirish.
- P1: Mahsulotni 2-3 bosishda topish, tezkor qidirish, masofa, joylashuv planshetda.
- P1: Ombor harakati davr bo‘yicha, inventarizatsiyani draft sifatida saqlash.
- P1: Tarif/mahsulot soni cheklovlari CoffeePOS’da shaffof bo‘lishi kerak, yashirin to‘lov yo‘q.
- P2: yetkazib berish, mijoz telefoni, integratsiyalar faqat talab bo‘lsa.

## 5. r_keeper: modullilik va barqaror integratsiyalar
- P0: POS/Kassa alohida xizmat, Barista/KDS alohida rol, Admin/CFO boshqaruv alohida.
- P0: API/hardware integratsiya interfeyslari, to‘lov provider adapterlari va fiskal adapter; test environment talab.
- P1: Har bir mijoz kompaniya/filial uchun feature flag va rolga mos menyu.
- P1: Loglar va operatsion kuzatuv: xatolar, printer ulanishi, buyurtma muvaffaqiyati.
- P1: Qarzni boshqarish, qaytarilgan pul audit izi.
- P2: Self-service kiosk, navbat ekranlari, menuboard; qahvaxonalar talabiga ko‘ra alohida kengaytma.

## CoffeePOS yakuniy mustaqil modul sxemasi
### P0 — qahvaxonaga sotishdan oldin
1. Kassa va Barista (alohida, rahbar boshqaradigan ixtiyoriy dual rol).
2. Smena, naqd/karta va pul xarajatlari bilan balans.
3. Ochiq chek, order cancel, chekni qayta chiqarish va qaytarish/refund audit.
4. Texkarta, nakladnoy, ombor, inventarizatsiya; manfiy/qoldiq holatlari.
5. Real offline sotuv + konflikt/sinxronlash/duplicate-payment himoyasi.
6. Termoprinterlar: Android/Windows real qurilmada test.
7. O‘zbekiston fiskal talablarini sertifikatlangan provayder bilan tekshirish.
8. Platform superadmin, xavfsiz litsenziya, cheklangan sinov va obuna.
9. Avtomatik backup + tiklash sinovi, TLS, parol/PIN, RBAC, audit log.
10. PostgreSQL yuklamasi va 100+ ko‘p-tenant xavfsizlik testi.

### P1 — sotuvga chiqish bilan / yaqin reliz
11. Bonus/loyalty (foiz, telefon, history, reversal).
12. Har bir xodim uchun kunlar/soatlar, oylik/avans qarz hisoboti.
13. Moliyaviy pul oqimi, COGS, operatsion foyda, to‘lanmagan qarzlar.
14. Ombor bozorlik ro‘yxati, yetkazib beruvchi narxlari, kirim/chiqim.
15. Multi-filial, filiallararo mahsulot transferi va filial tahlili.
16. Mobil direktor analitikasi va narx/mahsulot eksporti.

### P2 — talab asosida
17. QR menyu, o‘z-o‘ziga buyurtma, pickup.
18. Delivery, kuryer va agregatorlar.
19. Stol bron/zal sxemasi, ofitsiant.
20. Prognozlash va taklif etiladigan tovar buyurtmasi.
21. Self-service kiosk, reklama/menuboard.

## Hozirgi kod holati (GitHub implementatsiyasi != VPS tasdig‘i)
- Bor: Kassa/order, Barista, rol asoslari, bazaviy texkarta/ombor/smena, nakladnoy, smena tarixi, Dashboard, Android online WebView APK.
- GitHub’da yangi: superadmin CRUD/subscription API va UI, qisman refund/cancel, bonus ledger va admin sozlamalari, kassirga tezkor xarajat, pul chiqimini smenadan ayirish, moliyaviy boshqaruv hisoboti, kassirga ixtiyoriy barista ruxsati.
- Yo‘q yoki qurilma bilan tekshirilmagan: offline queue, nativ printer bridge, fiskal provayder, to‘liq transfer, ish haqi formula, real yuklama, backup avtomatik jadval, Apple/iOS nativ release.
- Hech qachon «100% tayyor» demaslik: CI, migratsiya, real Android printer, ishlab turgan VPS va ikki qahvaxona (data-isolation) testlari o‘tmaguncha.

## Qabul sinovlari
- Kassir xodimi Kassa’da; oddiy barista faqat Barista; dual-role faqat manager belgilaganida ikki modul.
- Smena: ochilgan naqd + naqd savdolar − naqd xarajatlar = kutilgan kassadagi naqd.
- Cancel/refund idempotent; ombor harakati ikki marta qaytmaydi.
- Har bir order global va filial doirasida unik idempotency key bilan faqat 1 marta yoziladi.
- Offline 30+ minut va keyin tarmoq qaytganda buyurtma/printer/kassa yo‘qotilmaydi.
- 100+ kompaniya bir vaqtda sotib, boshqalarning yozuvini o‘qiy olmaydi.
- Staging serverda eski va yangi DB migratsiyasi backupdan qayta tiklanib sinaladi.
- iOS/Android/Windows printerlar uchun test bayonnomasi alohida.

## Deploy tartibi
1. GitHub branch/commits yig‘iladi; CI (frontend build + backend tests + lint) yashil.
2. VPS PostgreSQL snapshot + restore sinovi.
3. Stagingda migration, buyurtma, ombor, bonus, rol, printer, offline test.
4. Bir martalik production deploy, health-check va tez rollback.
5. User bilmasdan productiondagi ma’lumotni o‘chirmaslik / o‘zgartirmaslik.

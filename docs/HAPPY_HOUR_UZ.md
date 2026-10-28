# Happy Hour: joriy scope va test

Productionda bajarilmagan. Startup yangi `promotions` jadvalini yaratadi va `orders.promotion_snapshot` nullable JSON ustunini idempotent qo‘shadi. Eski orderlar o‘zgarmaydi. Staging backupdan migratsiya hali tekshirilmagan.

Owner/admin aksiya yaratadi va faolligini almashtiradi. Butun savat uchun 1–50%, HH:MM, hafta kunlari (0=dushanba), 0–100 ustuvorlik. Server TZ_NAME (default Asia/Tashkent). Boshlanish kiradi, tugash kirmaydi. Tun oralig‘ida hafta kuni boshlanish kuniga tegishli. Teng start/end rad etiladi. Ustuvorlik kattasi, teng bo‘lsa ID kichigi tanlanadi.

Qo‘lda chegirma va aksiya qo‘shilmaydi: kattarog‘i olinadi. Bonus alohida keyin hisoblanadi. Tushirilgan summa butun UZS, mavjud 100 UZS yumaloqlashga yaqin, lekin so‘ralgan foizdan ortmaydi. Juda kichik summalarda foizning butun UZS limiti ustun. Python/JS hisoblash bir xil.

Kassa faol aksiyani har 15 soniya tekshiradi. Checkout serverda qayta hisoblanadi; `expectedTotal` mos kelmasa 409 va hech qanday savdo/bonus/ombor yozuvi commit bo‘lmaydi. Eski client faol aksiyada expectedTotal yubormasa ham 409 bilan yangilanish talab etiladi. Mijoz ekrandagi summani tekshirib qayta urinadi. Shu sabab barcha qurilma frontend/backend versiyasi birga stagingda tekshirilishi kerak.

Aksiya ko‘rinayotgan paytda offline fallback o‘chiq. Oddiy offline buyurtma expectedTotalni saqlaydi; keyin aksiya/narx o‘zgarsa server navbatni boshqa narxda jim qabul qilmaydi, 409 konflikt qoladi. Legacy queued order faol aksiyada ham qo‘lda tekshirilishi kerak. Bu to‘liq offline pricing yechimi emas.

Qo‘llangan aksiyaning id/nom/foiz/timezone nusxasi orderda saqlanadi. Aksiya o‘chirilsa tarix o‘zgarmaydi. Mahsulotga alohida aksiya, sana oralig‘i, filial timezone, qo‘lda tahrir UI va promotion audit hali yo‘q; boshqaruvda faol/nofaol tugmasi bor, PUT API barcha maydonlarni yangilaydi. Staging va browser/hardware qabul sinovi ochiq.

Test: overnight va weekday chegaralari, priority tie, foiz limitlari, JS integer arifmetika, tenant/RBAC, stale price rejection, qo‘lda yuqoriroq chegirma va tarixiy snapshot. CI SQLite va PostgreSQLda bajaradi.

# Operatsion audit: migratsiya va cheklovlar

Productionda bajarilmadi. Stagingda backup/restore va operator tekshiruvidan keyin chiqariladi.

Yangi `audit_events` jadvali mavjud startup `Base.metadata.create_all` orqali qo‘shiladi. Eski biznes jadvallari o‘zgarmaydi. `install_guards` har startupda idempotent ravishda SQLite va PostgreSQL uchun UPDATE/DELETE triggerlarini o‘rnatadi. DDL uchun ruxsat bo‘lmasa startup xato bilan to‘xtaydi; himoyasiz davom etmaydi.

Yozuvlar refund, order cancel va inventory count bilan bir tranzaksiyada yaratiladi. Rad etilgan amal rollback qilinadi; refund retry yana event yaratmaydi. Eski amallar qayta to‘ldirilmaydi. Davomiylik boshlangan commitdan hisoblanadi.

API faqat owner/admin uchun; company_id server sessiyasidan olinadi. ID cursor paginatsiya, max 100. DELETE/PUT API yo‘q. Mijoz telefoni, PIN, token va erkin sabab matni snapshotga olinmaydi. Actor nomi va IDsi xizmat auditi uchun saqlanadi.

Bu to‘liq global audit emas: staff, menyu, litsenziya, shift va boshqa o‘zgarishlar hali qamralmagan. Filial ajratish ham ochiq. DB egasi triggerni olib tashlashi yoki jadvalni truncate/drop qilishi mumkin; tashqi buzib bo‘lmaydigan arxiv deb hisoblanmaydi. Production runtime uchun alohida eng kam ruxsatli DB user kerak.

Rollback: oldingi dastur versiyasi yangi jadvalni ishlatmaydi. Jadval/yozuvlarni rollback paytida o‘chirmang. Qo‘lda destructive downgrade script berilmagan.

Sinov: pytest audit API ruxsatlari, tenant isolation, pagination, redaction, idempotency, biznes rollback va to‘g‘ridan-to‘g‘ri SQL UPDATE/DELETE bloklanishini SQLite/PostgreSQL CI matritsasida tekshiradi. Haqiqiy staging backupdan migration/restore sinovi hali bajarilmagan.

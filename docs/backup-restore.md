# PostgreSQL zaxira va tiklash — CoffeePOS

**Production MasterCoffee bazasiga sinov ma'lumotlarini hech qachon yozmang.**\n\nAdministrator MFA seedlari bazada shifrlangan. Ma'lumotlarni tiklash uchun `PLATFORM_MFA_ENCRYPTION_KEY` ham **alohida maxfiy joyda** saqlangan bo'lishi kerak; faqat bazaning backup nusxasini tiklash MFA ni ochish uchun yetarli emas.
Har qanday yangilashdan oldin alohida backup yarating; backup'ning o'zi o'chirilmaydigan, shifrlangan, alohida saqlanadigan joyga nusxalansin.

## Zaxira nusxasi (mavjud bazani faqat o'qiydi)

Serverda Docker Compose mavjud bo'lsa, repository ildizida:

```bash
bash scripts/backup-postgres.sh /safe-location/coffee-backups
```

Script `db` servisiga `pg_dump -Fc` yuboradi, yangi .dump faylini `pg_restore --list` orqali tasdiqlaydi va faqat shundan so'ng yakuniy nom beradi. Eski backup ustiga yozmaydi. Natijani imkon qadar boshqa disk/joyga ko'chiring. Nusxa olinayotgan baza foydalanuvchilari va kompaniya ma'lumotlarini o'z ichiga oladi: **maxfiy ma'lumot sifatida saqlang**.

## SQLite (Windowsdagi lokal CoffeePOS)

SQLite uchun alohida skript source bazani **faqat o'qish rejimida** ochadi va `sqlite3.Connection.backup()` yordamida yangi snapshot yaratadi; uning yaxlitligi tekshiriladi. Masalan TEST loyihangizdagi baza bilan:

```cmd
py -3.12 scripts\backup-sqlite.py "C:\\path\\to\\TEST-coffeepos.db" "D:\\test-coffee-backups"
```

**Bu faqat misol:** yo'llarni tekshirib, aynan qaysi bazaga tegishli ekanini aniqlang. Script ishlab turgan bazani o'chirmaydi, yangilamaydi yoki ustiga yozmaydi. Kompyuterdagi `C:\\CoffeePoss\\yangi-versiya\\coffeepos.db` haqiqiy MasterCoffee bazasi; undan faqat ruxsat va alohida saqlash reja bo'lganda zaxira oling, hech qachon sinov bazasi bilan almashtirmang.

`backend/tests/test_sqlite_backup.py` faqat vaqtinchalik sinov bazasida bu skriptni test qiladi.

## Test bazasida tiklash (production emas)

To'liq tiklashni **bo'sh, alohida test PostgreSQL bazasiga**, aynan mos server/DB versiyasida qiling. Masalan CI sinovida `coffeepos` manba test bazasidan `coffeepos_restored` nomli bo'sh test bazaga tiklanadi va kompaniya, xodim, mahsulot, obuna satrlari tekshiriladi.

TEST muhitda PostgreSQL containeriga backup'ni kiriting va alohida DB oching:

```bash
# Quyidagi misollar faqat maxsus TEST konteynerda!
docker cp coffeepos-test.dump TEST_PG_CONTAINER:/tmp/coffeepos-test.dump
docker exec TEST_PG_CONTAINER createdb -U coffeepos coffeepos_restored
docker exec TEST_PG_CONTAINER pg_restore -U coffeepos -d coffeepos_restored /tmp/coffeepos-test.dump
```

**TEST_PG_CONTAINER** ishlab turgan production container nomi bo'lmasligi kerak. O'zingiz tanlamagan DBga nusxa tiklamang. Ishlayotgan qahvaxona ma'lumotlarini qayta tiklash maxsus muolaja va ishni to'xtatish rejasisiz bajarilmasligi kerak.

## Avtomatik CI tekshiruvi

GitHub Actions `postgres_backup_restore` job har safar vaqtinchalik **PostgreSQL 16** servisni yaratadi, unda alohida test qahvaxona qo'shadi, `pg_dump/pg_restore` bilan yangi test DBga tiklaydi va muhim ma'lumotlar saqlanganini tekshiradi. GitHub CI **hech qachon mahalliy `C:\CoffeePoss\yangi-versiya\coffeepos.db`** fayliga ulanmaydi.

### Hali majburiy tekshiruvlar

- Rejalashtirilgan kunlik avtomatik backup va xavfsiz tashqi saqlash
- Agar PostgreSQL bo'lmasa, SQLite `coffeepos.db` nusxasi uchun `sqlite3.Connection.backup()` orqali jonli bazani shikastlamasdan backup; TEST nusxadan recovery sinovi
- Restore va migratsiya mashqi, serverga yangilashdan oldingi / keyingi nazorat
- RTO/RPO maqsadlari, disk to'lib qolsa ogohlantirish, rollback va tiklash bo'yicha mas'ul shaxs

Dastur hali ishlab turgan production xizmat uchun to'liq disaster recovery kafolatiga ega emas.

# CoffeePOS bepul sinov serveri (Render)

GitHub branch: `coffeepos-development`. Repo ildizida `render.yaml` mavjud.

1. Render dashboard -> New -> Blueprint. GitHub'ni ulang va `avaziknabijonov-ship-it/coffeepos` repozitoriysini tanlang.
2. Blueprint uchun `coffeepos-development` branch'ni tanlang. `render.yaml`ni tekshiring: bitta bepul API va bitta bepul PostgreSQL.
3. Deployni tasdiqlang. Render yaratgan `https://...onrender.com` manzilini yozib oling.
4. Brauzerda `https://...onrender.com/healthz`ni oching; `{"ok":true}` javobini tekshiring.
5. Hozir `SEED_DEMO=0`: ommaga ma'lum demo PIN'lar internetga chiqarilmaydi. Mijoz va xodimlarni qo'shish uchun platform admin orqali xavfsiz sozlash kerak. Admin kalitini chatga yubormang.
6. Android build uchun HTTPS API manzilini `Android debug APK` GitHub Actions workflow'iga `api_url` sifatida kiriting. Ishga tushirishdan oldin API'ning Android WebView originiga CORS ruxsatlarini tekshiring.
7. Render bepul web xizmati 15 daqiqa trafik bo'lmasa uyquga ketadi, uyg'onishi taxminan bir daqiqa olishi mumkin. Bepul PostgreSQL 30 kundan so'ng tugaydi va zaxira nusxalari yo'q. Bu faqat test uchun. Haqiqiy savdo va mijoz ma'lumotlarini kiritmang.

**Hali bajarilmagan:** Render akkauntida Blueprint'ni yaratish, deploy va API test, Android APK build, xavfsizlik sinovi. Platforma foydalanuvchi tasdig'isiz yaratilmaydi.

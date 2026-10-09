# CoffeePOS Android — markaziy server

Android planshet va Windows kassa bir xil HTTPS API serveriga ulanadi.
Bu fayl Android build uchun tayyorgarlik yo'riqnomasi; APK hali yaratilmagan.

## 1. HTTPS server
Production domen va HTTPS sertifikatini sozlang. API'da kompaniya ma'lumotlari ajratilganini, rollar va obunani tekshirishni, PostgreSQL backup va monitoringni test qiling.
Hech qachon PLATFORM_ADMIN_KEY yoki SECRET_KEY ni frontendga, APKga yoki GitHubga yozmang.

## 2. Frontend API manzili
Vite build vaqtida API URL belgilanadi. Masalan, PowerShell:
```powershell
$env:VITE_API_URL="https://api.example.com"
npm run build
```
example.com faqat namuna: haqiqiy HTTPS domen bilan almashtiriladi. Android WebView orqali boshqa domendagi API'ga murojaat qilish uchun backend CORS sozlamalari xavfsiz tarzda tekshirilishi kerak. Buning o'rniga bir xil originli HTTPS hosting ham tanlanishi mumkin.

## 3. Android ilova yaratish
Node.js, Android Studio va Android SDK o'rnatilgan kompyuterda:
```powershell
npm install
npm install
npm run build
npx cap add android
npm run android:sync
npm run android:open
```
Android Studio'da debug APK build qiling va planshetda sinang.
Capacitor uchun `server.url` ishlatmang: production resurslari APK ichida bo'ladi, API esa HTTPS orqali ishlaydi.

## 4. Sinov shartlari
- Kassadan buyurtma yaratish va Buyurtmalar ekranida ko'rish
- Statusni o'zgartirish va ikkinchi qurilmada yangilanishi
- Kassir va rahbar huquqlarini tekshirish
- Internet uzilganda aniq xabar; hozirgi versiyada offline savdo kafolatlanmagan
- Android ilova to'liq yopilib qayta ochilganda login va ulanish
- Planshetda ekran o'lchamlari va chek printeri

## Muhim
APK ishlab chiqarishga tayyor emas. Markaziy server, autentifikatsiya, CORS va sinovlar tugamaguncha haqiqiy mijoz ma'lumotlari bilan ishlatmang.

## 5. Joriy kod holati
Capacitor kutubxonalari package.json'ga qo'shildi, lekin package-lock.json hali yangilanmagan. Lokal kompyuterda `npm install` bajarib lockfile yangilang. Android platforma papkasi `npx cap add android` orqali lokal yaratiladi. GitHub'da APK yoki tayyor Android Studio loyihasi hozircha yo'q.

## 6. Cloud API xavfsizligi
- `VITE_API_URL` faqat HTTPS URL bo'lsin; uni APK ichiga build vaqtida joylashadi.
- CORS_ORIGINS'ni real Android WebView originlari va web domenlari bo'yicha cheklang; wildcard production uchun tavsiya etilmaydi.
- Administratorning platform kaliti mobil ilovada saqlanmasin.
- Internet yo'q bo'lsa, hozirgi versiyada yangi buyurtma serverga yuborilmaydi.
- Android release APK imzolash kalitini xavfsiz saqlang va GitHub'ga yuklamang.

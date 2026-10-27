# Combo mahsulotlar: hisoblash va cheklovlar

Productionga chiqarilmagan. Additive startup migratsiya products.combo_components nullable JSON ustunini qo‘shadi. Oddiy mahsulotlar o‘zgarmaydi. Operator backupdan staging migratsiyasini hali tekshirmagan.

Owner/admin 2–10 turli productId+size tarkibidan, har birida 1–10 dona, belgilangan narxli combo yaratadi/tahrirlaydi. Combo kassa katalogida bitta mahsulot bo‘ladi. Nested combo va component modifiers qo‘llanmaydi. Combo oddiy menu editor orqali recipe bilan almashtirilmaydi. Manba mahsulotni combo ishlatayotgan paytda o‘chirish bloklanadi.

Katalog va checkoutda tarkib manba mahsulotning amaldagi texkartasidan hisoblanadi: ingredient miqdori component soniga ko‘payadi va bir ingredient birlashtiriladi. Checkout umumiy order qty bilan ko‘paytirib bitta sale ledgerga yozadi. Manba stop-listga tushsa yoki topilmasa combo kassada sotilmaydi. Admin listidagi active — sozlama; kassadagi active — tarkib mavjudligini ham hisobga oladi.

Har orderda combo nomi, narxi, tannarxi va consumption snapshot saqlanadi; qo‘shimcha components maydoni source mahsulot nomi/o‘lcham/son/narx nusxasini saqlaydi. Keyingi recipe yoki combo narx o‘zgarishi eski orderni o‘zgartirmaydi. Order cancel eski stock_movesni qaytaradi — yangi combo recipe bo‘yicha qayta hisoblamaydi. Moliyaviy manual refund avtomatik fizik stock qaytarish emas; item-level return hali alohida ochiq ish.

API: GET/POST /api/combos va PUT /api/combos/{key}; tenant manager RBAC. Combo key tasodifiy va tenant doirasida. Faol/nofaol existing product endpointidan boshqariladi. Rasm tahriri combo formida hali yo‘q. Branch stock, concurrent ingredient locking va offline conflict resolution oldingi umumiy cheklovlar bo‘lib qolmoqda.

Test: aggregate recipe, qty=2 stock deduction, return after combo reconfiguration, duplicate cancellation, nested/duplicate components rejection, source deletion guard, source stop-list va company/RBAC separation. UI build/i18n tekshiriladi; brauzer, printer va staging acceptance hali yo‘q.

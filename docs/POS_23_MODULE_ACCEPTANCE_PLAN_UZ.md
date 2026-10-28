# CoffeePOS: 23 modul uchun raqobatchi benchmark va qabul mezonlari

Holat: REJA, hali ishlab chiqilgan yoki testdan o'tgan degani emas.
Branch: feature/fiscal-integration-scaffold. Production VPSga tegilmaydi.

## Benchmark
- Toast: split checks, stol/buyurtma, KDS, offline cheklovlari, xodim ruxsatlari.
  https://pos.toasttab.com/restaurant-pos/full-service-pos-system
  https://support.toasttab.com/en/article/Using-Toast-in-Offline-Mode
- Lightspeed Restaurant: stol xaritasi, combo, filial boshqaruvi, analitika.
  https://www.lightspeedhq.com/pos/restaurant/multilocation-restaurant-pos/
- Lightspeed Retail: split payments, filiallararo ombor o'tkazmalari.
  https://www.lightspeedhq.com/pos/retail/features/
- Bular funksional benchmark, dizayn/kod ko'chirilmaydi.

## Barcha modullarga umumiy talab
company_id/branch_id ajratish, server RBAC, idempotency, audit, Uzbek/Rus,
migratsiya, backend unit/integration, frontend UI, real staging qabul testi.
Moliyaviy hisob-kitoblar butun birliklarda; tarixiy order snapshot saqlansin.

## 23 modul: qabul mezonlari
1. Split payment: payments jadvali, yig'indi totalga teng, qisman to'lov statusi; 2 qurilma takroriy to'lov yaratmaydi.
2. Refund: asl paymentga bog'langan partial/full reversal, audit, stock/bonus/fiscal reversal; ortiqcha qaytarish bloklanadi.
3. Tannarx: ingredient va texkarta asosida snapshot; eski order tannarxi narx yangilanganda o'zgarmaydi.
4. Low stock: filial+ingredient threshold, dedupe notification, minimal qoldiq testlari.
5. P&L: revenue-refunds-COGS-expenses, filial/sana kesimi; reconciliation.
6. Audit: actor/action/before-after/timestamp/company, append-only, maxfiy ma'lumotlar maskalanadi.
7. Fiscal: har kompaniya STIR/operator/terminal, provider sandbox, encrypted credentials, fiskal QR va refund; majburiy fiskalizatsiyani chetlab o'tish yo'q.
8. Backup: encrypted offsite scheduled PostgreSQL dump, retention, restore drill va monitoring.
9. Draft orders: serverda draft, versiya konflikti, checkoutdan oldin revenuega kirmaydi.
10. Tables: table/area occupancy, move/merge permissions, takeaway.
11. Stock transfer: dispatch/in-transit/receive, ikki filial qoldig'i atomar ledger, double receive yo'q.
12. Inventory variance: expected vs counted, signed adjustment, approval, report.
13. Cash variance: opening+cash sales-cash refunds-cash expenses, actual difference, actor.
14. Staff analytics: orders, sales, discounts, refunds, shifts, role visibility.
15. Telegram director: opt-in tenant chat, daily digest, retries, no credentials in repo.
16. Electronic receipt: nonfiscal/fiscal status clearly marked, signed link/QR, private customer data protection.
17. Happy Hour: local timezone, overnight schedule, conflict priority, discount caps.
18. Customer analytics: consent/privacy, repeat visits, cohorts, purchase history.
19. Combo: component SKUs and ingredient deduction once, returns reversal.
20. Offline: durable queue, idempotency, conflict state, no false fiscal receipt, restricted unsupported payment.
21. Device management: registered device identity, company/branch binding, revoke and last seen.
22. Updates: semantic version, staged rollout, rollback, APK/backend compatibility.
23. Loyalty: customer ledger, accrual/redeem/refund reversal, concurrent balance protection.

## Release gates
G0 baseline: CI green, migrations tested, tenant isolation.
G1 financial engine: payments/refunds/drafts/audit tests green.
G2 inventory/branch: transfers/variance/cost tests green.
G3 experience: tables/combos/promotions/loyalty/analytics green.
G4 external: fiscal provider sandbox, Telegram, receipt, printer/APK.
G5 reliability: offline multi-device, encrypted backup restore, rollback drill.
G6 real pilot: customer-approved staging test, no production changes until explicit approval.

Status labels: planned -> implemented -> unit-tested -> integrated -> staging-tested -> hardware-tested -> accepted.
No status may be upgraded without evidence (CI run, test logs, screenshots or acceptance record).

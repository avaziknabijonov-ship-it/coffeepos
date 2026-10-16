# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.

## 1-bosqich: backend

```
cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --port 8000   # API
.venv/bin/python -m pytest                   # testlar
npm run dev                                  # frontend, /api -> :8000 proxy
```

- Baza: `DATABASE_URL` (standart: SQLite `./coffeepos.db`, `/data` papkasi bo'lsa `/data/coffeepos.db`). PostgreSQL URL ham ishlaydi.
- `SECRET_KEY` berilmasa, bazada avtomatik yaratiladi. `SEED_DEMO=0` demo kofe barni o'chiradi.
- Frontend production build: `VITE_API_URL=https://api-manzil npm run build`.
- Demo: login `demo`, PIN 1111 rahbar, 2222 kassir, 3333 barista.

## Serverga joylash (VPS, Docker)

Talab: Docker va Docker Compose o'rnatilgan Linux server.

```
git clone https://github.com/avaziknabijonov-ship-it/coffeepos.git && cd coffeepos
cp .env.example .env    # POSTGRES_PASSWORD va SECRET_KEY ni almashtiring (openssl rand -hex 32)
docker compose up -d --build
curl localhost/healthz  # {"ok":true}
```

- Konteynerlar: `db` (PostgreSQL 16, ma'lumot `pgdata` volume'da), `api` (FastAPI), `web` (nginx: frontend + `/api` proxy).
- HTTPS uchun domenni server IP'ga yo'naltiring va oldiga Caddy yoki certbot+nginx qo'ying.
- Tekshiriladigan zaxira nusxa: `bash scripts/backup-postgres.sh ./backups`. SQLite uchun `scripts/backup-sqlite.py`. [Yo‘riqnoma](docs/backup-restore.md).


## Litsenziya va qahvaxonalarni sotuvga tayyorlash

- **Super Admin paneli:** `/platform-admin` — mijoz qahvaxonalarni yaratish, 14 kunlik sinov, oylik (kalendar oy) va yillik (kalendar yil) obunani qo‘lda uzaytirish, suspend qilish va o‘zgarishlar tarixini ko‘rish.
- **Qahvaxona egasining Litsenziya bo‘limi:** obunaning holati, tugash sanasi, qolgan kunlar.
- **Muddati tugagan obuna:** yangi server operatsiyalari bloklanadi, oldingi hisobotlarni ko‘rish mumkin. Uzaytirilgach yangi amallar qayta ishlaydi.
- **Tijoriy server:** barcha eski kafelarga obuna tayinlangach `LICENSE_ENFORCEMENT=1` ni yoqing (standart `0` — eski MasterCoffee'ni bloklamaslik uchun). `ALLOW_PUBLIC_REGISTRATION=0`, `PLATFORM_ADMIN_KEY` = tasodifiy 32+ belgili maxfiy kalit, `PLATFORM_REQUIRE_MFA=1`, `PLATFORM_ADMIN_TOTP_SECRET` = maxfiy autentifikator kaliti, `SEED_DEMO=0`. Platform Admin sahifasini internetda faqat HTTPS orqali oching.

**Ish tartibi va cheklovlar:** [docs/licensing-sales.md](docs/licensing-sales.md). **Android sinovi:** [docs/android-local-testing.md](docs/android-local-testing.md).

To‘lovlarni avtomatik qabul qilish hali yo‘q; oylik va yillik tarif narxlari avval bo‘sh bo‘ladi, keyinchalik Super Admin orqali o‘zgartiriladi. Har bir Super Admin/Menejer/Auditor uchun alohida login/parol/TOTP hisoblar, hisobni bloklash, MFA tiklash va kim nimani o'zgartirganini qayd etish joriy etilgan. Real production muhitidagi operator sinovi va restore mashqi hali qolgan. [Admin hisoblari yo'riqnomasi](docs/platform-admin-accounts.md). PostgreSQL backup/restore va eski licenziya schema migratsiyasi avtomatik CI testlarda sinovdan o‘tadi; real xizmatni avval sinov muhitida tekshiring. Haqiqiy MasterCoffee ma’lumotlarini TEST COFFEE bilan aralashtirmang.

## Google Play va App Store tayyorligi

Tekshiruv, tuzatishlar va qolgan nashr talablari: [docs/store-readiness.md](docs/store-readiness.md). Imzolangan nashr va do‘kon tasdig‘i hali yo‘q.

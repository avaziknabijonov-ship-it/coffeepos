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
- Zaxira nusxa: `docker compose exec db pg_dump -U coffeepos coffeepos > backup.sql`.

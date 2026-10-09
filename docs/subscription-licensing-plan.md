# CoffeePOS Hybrid — subscription licensing plan

Status: design specification; NOT yet implemented.

## Roles
- Platform super-admin (separate from tenant owner/admin).
- Coffee bar tenant owner, admin, cashier.
- No Barista or customer-display navigation.

## Proposed subscription lifecycle
- trial: 14 days from activation
- active: paid through subscription end date
- grace: short configurable renewal grace period
- expired: renewal required; preserve all records and allow exports
- suspended: manually suspended for fraud/security; do not erase tenant data

## Data model
- tenants: existing companies, stable IDs
- plans: code, name, price, billing currency, interval, active
- subscriptions: company_id, plan_id, status, trial_ends_at, current_period_ends_at, grace_ends_at, version
- payments: company_id, subscription_id, amount, currency, payment_reference, status, paid_at; unique provider transaction ID
- devices: company_id, device_id, public_key, last_seen_at, revoked_at
- audit_log: actor, company, action, timestamp, metadata

## API outline
- /api/platform/*: isolated super-admin auth and management; never reuse tenant PIN login
- /api/license/status: tenant-scoped status, server timestamp, signed offline entitlement
- /api/license/activate: register a device securely
- /api/billing/webhook: verify payment provider signature; idempotent processing
- /api/billing/history: tenant owner payment history

## Offline requirements
- Signed entitlements, verified locally with public key; private signing key remains server-side.
- Grace policy must be explicit, bounded, and resistant to local clock changes.
- Offline POS orders queue with stable IDs; idempotent server ingest and conflict handling.
- Never delete or rewrite existing sales on license expiry.
- Ensure existing backend DB and auth paths keep working throughout migration.

## Implementation order
1. DB migrations and license status API with automated tests.
2. Super-admin authentication, authorization, and tenant management.
3. Payment integration, audit trails, renewal jobs, webhook tests.
4. Signed offline entitlements and robust POS sync protocol.
5. Installer/update process, backups, monitoring, pilot coffee bars.
6. Verify Uzbekistan fiscal receipts and data protection requirements before commercial launch.

Do not deploy commercially until tested for security, data isolation, offline resilience, and fiscal compliance.

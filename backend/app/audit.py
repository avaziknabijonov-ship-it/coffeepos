"""Operational audit writes participate in the business transaction."""
from sqlalchemy import text
from .db import AuditEvent

_ALLOWED = {'status', 'amount', 'method', 'orderId', 'shortage', 'surplus', 'lines',
            'ingredient', 'expected', 'counted', 'difference'}


def safe_snapshot(value):
    if isinstance(value, dict):
        return {key: safe_snapshot(item) for key, item in value.items() if key in _ALLOWED}
    if isinstance(value, list):
        return [safe_snapshot(item) for item in value]
    return value


def record(ctx, action, entity_id, before, after):
    ctx.db.add(AuditEvent(company_id=ctx.cid, actor_id=ctx.staff.id,
                          actor_name=ctx.staff.name, action=action, entity_id=entity_id,
                          before=safe_snapshot(before), after=safe_snapshot(after)))


def install_guards(engine):
    """DB-level UPDATE/DELETE guards, including bulk SQL (not just ORM hooks).

    Database owners can remove triggers; this is not an external tamper-proof archive.
    """
    with engine.begin() as conn:
        if engine.dialect.name == 'sqlite':
            for operation in ('UPDATE', 'DELETE'):
                conn.execute(text(f"""CREATE TRIGGER IF NOT EXISTS audit_no_{operation.lower()}
                    BEFORE {operation} ON audit_events BEGIN
                    SELECT RAISE(ABORT, 'audit_events is append-only'); END"""))
        elif engine.dialect.name == 'postgresql':
            conn.execute(text("""CREATE OR REPLACE FUNCTION reject_audit_mutation() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit_events is append-only'; END; $$"""))
            conn.execute(text('DROP TRIGGER IF EXISTS audit_append_only ON audit_events'))
            conn.execute(text('CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()'))

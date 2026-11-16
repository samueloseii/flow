"""Additive schema fixes for databases created before a column existed.

The app relies on ``create_all``, which never alters existing tables, so new
columns are added here at startup. Every statement must be idempotent.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Runs BEFORE create_all on databases built around Household / Community.
# Tables and columns are renamed in place so meters, readings, bills and payments
# keep their history.  Each statement is skipped when already applied.
RENAME_STATEMENTS = (
    "ALTER TABLE households RENAME TO connections",
    "ALTER TABLE connections RENAME COLUMN head_of_household TO contact_name",
    "ALTER TYPE householdstatus RENAME TO connectionstatus",
    "ALTER TABLE meters RENAME COLUMN household_id TO connection_id",
    "ALTER TABLE invoices RENAME COLUMN household_id TO connection_id",
    "ALTER TABLE payments RENAME COLUMN household_id TO connection_id",
    "ALTER TABLE users RENAME COLUMN household_id TO connection_id",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'ADMIN'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'EDITOR'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'VIEWER'",
)

# Runs AFTER create_all: new columns, then the data moves.
DATA_STATEMENTS = (
    "CREATE TYPE connectiontype AS ENUM "
    "('HOUSEHOLD','SCHOOL','CLINIC','COMMERCIAL','PUBLIC_TAP','INSTITUTION','OTHER')",
    "ALTER TABLE connections ADD COLUMN IF NOT EXISTS connection_type connectiontype DEFAULT 'HOUSEHOLD'",
    "ALTER TABLE connections ADD COLUMN IF NOT EXISTS water_committee_id UUID REFERENCES water_committees(id)",
    "ALTER TABLE connections ALTER COLUMN community_id DROP NOT NULL",
    # Communities created before committees were required: when there is exactly
    # one committee it is the only possible owner.
    "UPDATE communities SET water_committee_id = (SELECT id FROM water_committees) "
    "WHERE water_committee_id IS NULL AND (SELECT count(*) FROM water_committees) = 1",
    "UPDATE connections SET water_committee_id = c.water_committee_id FROM communities c "
    "WHERE connections.community_id = c.id AND connections.water_committee_id IS NULL",
    "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS water_committee_id UUID REFERENCES water_committees(id)",
    "ALTER TABLE expenses ALTER COLUMN community_id DROP NOT NULL",
    "UPDATE expenses SET water_committee_id = c.water_committee_id FROM communities c "
    "WHERE expenses.community_id = c.id AND expenses.water_committee_id IS NULL",
    "ALTER TABLE maintenance_records ADD COLUMN IF NOT EXISTS water_committee_id UUID REFERENCES water_committees(id)",
    "ALTER TABLE maintenance_records ALTER COLUMN community_id DROP NOT NULL",
    "UPDATE maintenance_records SET water_committee_id = c.water_committee_id FROM communities c "
    "WHERE maintenance_records.community_id = c.id AND maintenance_records.water_committee_id IS NULL",
    "ALTER TABLE communities ALTER COLUMN partner_id DROP NOT NULL",
    # Accounts: one PARENT relation each, from the old scope columns.
    "INSERT INTO user_relations (id, relation_type, access_all_children, user_id, water_committee_id) "
    "SELECT gen_random_uuid(), 'PARENT', TRUE, u.id, u.water_committee_id FROM users u "
    "WHERE u.role::text IN ('COMMUNITY_ADMIN','TREASURER','OPERATOR','READER') "
    "AND u.water_committee_id IS NOT NULL AND u.connection_id IS NULL "
    "AND NOT EXISTS (SELECT 1 FROM user_relations r WHERE r.user_id = u.id AND r.relation_type = 'PARENT')",
    "INSERT INTO user_relations (id, relation_type, access_all_children, user_id, water_committee_id) "
    "SELECT gen_random_uuid(), 'PARENT', TRUE, u.id, c.water_committee_id FROM users u "
    "JOIN communities c ON c.id = u.community_id "
    "WHERE u.role::text IN ('COMMUNITY_ADMIN','TREASURER','OPERATOR','READER') AND u.connection_id IS NULL "
    "AND c.water_committee_id IS NOT NULL "
    "AND NOT EXISTS (SELECT 1 FROM user_relations r WHERE r.user_id = u.id AND r.relation_type = 'PARENT')",
    "INSERT INTO user_relations (id, relation_type, access_all_children, user_id, connection_id) "
    "SELECT gen_random_uuid(), 'PARENT', TRUE, u.id, u.connection_id FROM users u "
    "WHERE u.connection_id IS NOT NULL "
    "AND NOT EXISTS (SELECT 1 FROM user_relations r WHERE r.user_id = u.id AND r.relation_type = 'PARENT')",
    "INSERT INTO user_relations (id, relation_type, access_all_children, user_id, partner_id) "
    "SELECT gen_random_uuid(), 'PARENT', TRUE, u.id, u.partner_id FROM users u "
    "WHERE u.partner_id IS NOT NULL AND u.role::text <> 'SUPER_ADMIN' "
    "AND NOT EXISTS (SELECT 1 FROM user_relations r WHERE r.user_id = u.id AND r.relation_type = 'PARENT')",
    # Operators limited to certain communities keep them as CHILD relations.
    "INSERT INTO user_relations (id, relation_type, access_all_children, user_id, community_id) "
    "SELECT gen_random_uuid(), 'CHILD', FALSE, oc.user_id, oc.community_id FROM operator_communities oc "
    "WHERE NOT EXISTS (SELECT 1 FROM user_relations r WHERE r.user_id = oc.user_id AND r.community_id = oc.community_id)",
    "UPDATE user_relations SET access_all_children = FALSE WHERE relation_type = 'PARENT' "
    "AND user_id IN (SELECT user_id FROM user_relations WHERE relation_type = 'CHILD')",
    # Roles: partner/committee admin -> admin, treasurer -> editor, reader -> viewer.
    "UPDATE users SET role = 'ADMIN' WHERE role::text IN ('PARTNER_ADMIN','COMMUNITY_ADMIN')",
    "UPDATE users SET role = 'EDITOR' WHERE role::text = 'TREASURER'",
    "UPDATE users SET role = 'VIEWER' WHERE role::text = 'READER'",
    "UPDATE users SET role = 'VIEWER' WHERE role::text = 'OPERATOR' "
    "AND id IN (SELECT user_id FROM user_relations WHERE relation_type = 'PARENT' AND water_committee_id IS NULL)",
    # Accounts whose old scope gave no committee: with exactly one committee, use it.
    "INSERT INTO user_relations (id, relation_type, access_all_children, user_id, water_committee_id) "
    "SELECT gen_random_uuid(), 'PARENT', "
    "NOT EXISTS (SELECT 1 FROM user_relations r2 WHERE r2.user_id = u.id AND r2.relation_type = 'CHILD'), "
    "u.id, (SELECT id FROM water_committees) FROM users u "
    "WHERE u.role::text <> 'SUPER_ADMIN' AND (SELECT count(*) FROM water_committees) = 1 "
    "AND NOT EXISTS (SELECT 1 FROM user_relations r WHERE r.user_id = u.id AND r.relation_type = 'PARENT')",
    # The old scope columns are no longer read; drop them so they cannot drift.
    "ALTER TABLE users DROP COLUMN IF EXISTS partner_id",
    "ALTER TABLE users DROP COLUMN IF EXISTS water_committee_id",
    "ALTER TABLE users DROP COLUMN IF EXISTS community_id",
    "ALTER TABLE users DROP COLUMN IF EXISTS connection_id",
    "DROP TABLE IF EXISTS operator_communities",
    "ALTER TABLE communities DROP COLUMN IF EXISTS currency",
    "ALTER TABLE communities DROP COLUMN IF EXISTS tariff_fixed",
    "ALTER TABLE communities DROP COLUMN IF EXISTS tariff_per_m3",
    "ALTER TABLE communities DROP COLUMN IF EXISTS water_system_type",
    "ALTER TABLE communities DROP COLUMN IF EXISTS community_size",
    "ALTER TABLE communities DROP COLUMN IF EXISTS total_connections",
    "ALTER TABLE communities DROP COLUMN IF EXISTS partner_id",
)

STATEMENTS = (
    "ALTER TABLE meters ADD COLUMN IF NOT EXISTS avg_consumption_m3 DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE meter_readings ADD COLUMN IF NOT EXISTS flag_reason VARCHAR(255)",
    "ALTER TABLE maintenance_records "
    "ADD COLUMN IF NOT EXISTS reported_via_whatsapp BOOLEAN DEFAULT FALSE",
    "ALTER TABLE meter_readings ADD COLUMN IF NOT EXISTS client_id VARCHAR(64)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_meter_readings_client_id "
    "ON meter_readings (client_id)",
    "ALTER TABLE communities ADD COLUMN IF NOT EXISTS water_committee_id UUID "
    "REFERENCES water_committees(id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS water_committee_id UUID "
    "REFERENCES water_committees(id)",
    "ALTER TABLE connections ADD COLUMN IF NOT EXISTS tariff_id UUID REFERENCES tariffs(id)",
    "ALTER TABLE meter_readings ADD COLUMN IF NOT EXISTS invoice_id UUID REFERENCES invoices(id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS connection_id UUID REFERENCES connections(id)",
    "ALTER TABLE partners ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id)",
)


SQLITE_STATEMENTS = (
    "ALTER TABLE meters ADD COLUMN avg_consumption_m3 FLOAT DEFAULT 0",
    "ALTER TABLE meter_readings ADD COLUMN flag_reason VARCHAR(255)",
    "ALTER TABLE maintenance_records ADD COLUMN reported_via_whatsapp BOOLEAN DEFAULT 0",
    "ALTER TABLE meter_readings ADD COLUMN client_id VARCHAR(64)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_meter_readings_client_id "
    "ON meter_readings (client_id)",
    "ALTER TABLE communities ADD COLUMN water_committee_id CHAR(36) REFERENCES water_committees(id)",
    "ALTER TABLE users ADD COLUMN water_committee_id CHAR(36) REFERENCES water_committees(id)",
    "ALTER TABLE connections ADD COLUMN tariff_id CHAR(36) REFERENCES tariffs(id)",
    "ALTER TABLE meter_readings ADD COLUMN invoice_id CHAR(36) REFERENCES invoices(id)",
    "ALTER TABLE users ADD COLUMN connection_id CHAR(36) REFERENCES connections(id)",
    "ALTER TABLE partners ADD COLUMN organization_id CHAR(36) REFERENCES organizations(id)",
)


def _run(engine: Engine, statements) -> None:
    for statement in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
        except Exception as exc:  # pragma: no cover - already applied or table absent
            logger.info("Skipped migration (%s): %s", exc.__class__.__name__, statement)


def run_pre_migrations(engine: Engine) -> None:
    """Renames that must happen before create_all (which would otherwise create empty new tables)."""
    if engine.dialect.name == "sqlite":
        return
    _run(engine, RENAME_STATEMENTS)


def run_migrations(engine: Engine) -> None:
    if engine.dialect.name == "sqlite":
        _run(engine, SQLITE_STATEMENTS)
        return
    _run(engine, STATEMENTS + DATA_STATEMENTS)

"""Additive schema fixes for databases created before a column existed.

The app relies on ``create_all``, which never alters existing tables, so new
columns are added here at startup. Every statement must be idempotent.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

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
    "ALTER TABLE households ADD COLUMN IF NOT EXISTS tariff_id UUID REFERENCES tariffs(id)",
    "ALTER TABLE meter_readings ADD COLUMN IF NOT EXISTS invoice_id UUID REFERENCES invoices(id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS household_id UUID REFERENCES households(id)",
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
    "ALTER TABLE households ADD COLUMN tariff_id CHAR(36) REFERENCES tariffs(id)",
    "ALTER TABLE meter_readings ADD COLUMN invoice_id CHAR(36) REFERENCES invoices(id)",
    "ALTER TABLE users ADD COLUMN household_id CHAR(36) REFERENCES households(id)",
    "ALTER TABLE partners ADD COLUMN organization_id CHAR(36) REFERENCES organizations(id)",
)


def run_migrations(engine: Engine) -> None:
    statements = SQLITE_STATEMENTS if engine.dialect.name == "sqlite" else STATEMENTS
    for statement in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
        except Exception as exc:  # pragma: no cover - already applied or table absent
            logger.info("Skipped migration (%s): %s", exc.__class__.__name__, statement)

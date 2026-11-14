"""Sample data for local development only.

Production databases are prepared by ``app.db.bootstrap``, which creates no
records beyond the first administrator. Run this with ``--demo`` to opt in.
"""

import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.models.community import Community, CommunitySize, WaterSystemType
from app.models.expense import Expense, ExpenseCategory
from app.models.connection import Connection, ConnectionStatus
from app.models.maintenance import (
    MaintenanceCategory,
    MaintenancePriority,
    MaintenanceRecord,
    MaintenanceStatus,
)
from app.models.meter import Meter, MeterReading
from app.models.partner import Partner
from app.models.user import User, UserRole


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Partner).count() > 0:
            print("Database already seeded. Skipping.")
            return
        _seed_data(db)
        print("Database seeded successfully!")
    finally:
        db.close()


def _seed_data(db: Session):
    # Partners
    partners = [
        Partner(name="FEDICAMP", country="Nicaragua", contact_name="Maria Lopez", contact_email="maria@fedicamp.org"),
        Partner(name="ALTROPICO", country="Ecuador", contact_name="Carlos Vega", contact_email="carlos@altropico.org"),
        Partner(name="AVODEC", country="Honduras", contact_name="Ana Martinez", contact_email="ana@avodec.org"),
        Partner(name="ASOMAINCUPACO", country="Nicaragua", contact_name="Jose Hernandez", contact_email="jose@asomaincupaco.org"),
    ]
    for p in partners:
        db.add(p)
    db.flush()

    # Communities (12 total across partners)
    community_data = [
        ("San Juan del Sur", "Nicaragua", "Rivas", partners[0], WaterSystemType.GRAVITY_FED, CommunitySize.SMALL, "NIO", 5.0, 0.15, 45),
        ("El Jicaral", "Nicaragua", "León", partners[0], WaterSystemType.PUMPED, CommunitySize.MEDIUM, "NIO", 8.0, 0.20, 120),
        ("Santa Teresa", "Nicaragua", "Carazo", partners[0], WaterSystemType.GRAVITY_FED, CommunitySize.SMALL, "NIO", 4.0, 0.12, 35),
        ("Otavalo Rural", "Ecuador", "Imbabura", partners[1], WaterSystemType.GRAVITY_FED, CommunitySize.MEDIUM, "USD", 2.0, 0.35, 180),
        ("Cotacachi Sur", "Ecuador", "Imbabura", partners[1], WaterSystemType.GRAVITY_FED, CommunitySize.SMALL, "USD", 1.5, 0.30, 40),
        ("Esmeraldas Norte", "Ecuador", "Esmeraldas", partners[1], WaterSystemType.PUMPED, CommunitySize.LARGE, "USD", 3.0, 0.40, 250),
        ("La Ceiba Rural", "Honduras", "Atlántida", partners[2], WaterSystemType.GRAVITY_FED, CommunitySize.SMALL, "HNL", 50.0, 2.0, 55),
        ("Tela Comunidad", "Honduras", "Atlántida", partners[2], WaterSystemType.MIXED, CommunitySize.MEDIUM, "HNL", 75.0, 3.5, 150),
        ("El Progreso Sur", "Honduras", "Yoro", partners[2], WaterSystemType.PUMPED, CommunitySize.MEDIUM, "HNL", 60.0, 2.5, 90),
        ("Jinotega Norte", "Nicaragua", "Jinotega", partners[3], WaterSystemType.GRAVITY_FED, CommunitySize.SMALL, "NIO", 6.0, 0.18, 48),
        ("Matagalpa Este", "Nicaragua", "Matagalpa", partners[3], WaterSystemType.GRAVITY_FED, CommunitySize.MEDIUM, "NIO", 7.0, 0.22, 110),
        ("Muy Muy Central", "Nicaragua", "Matagalpa", partners[3], WaterSystemType.MIXED, CommunitySize.SMALL, "NIO", 5.5, 0.16, 38),
    ]

    communities = []
    for name, country, region, partner, ws_type, size, currency, tariff_fixed, tariff_m3, conns in community_data:
        c = Community(
            name=name, country=country, region=region, partner_id=partner.id,
            water_system_type=ws_type, community_size=size, currency=currency,
            tariff_fixed=tariff_fixed, tariff_per_m3=tariff_m3,
            total_connections=conns, population=conns * 4,
        )
        db.add(c)
        communities.append(c)
    db.flush()

    # Admin user
    admin = User(
        email="admin@flow.app", hashed_password=get_password_hash("admin123"),
        full_name="Flow Administrator", role=UserRole.SUPER_ADMIN,
    )
    db.add(admin)

    # Partner admin users
    for partner in partners:
        u = User(
            email=f"admin@{partner.name.lower()}.org",
            hashed_password=get_password_hash("partner123"),
            full_name=f"{partner.name} Admin", role=UserRole.PARTNER_ADMIN,
            partner_id=partner.id,
        )
        db.add(u)
    db.flush()

    # Community-level users: the administrator runs accounts and billing,
    # the operator reads meters, the treasurer handles money.
    for ci, community in enumerate(communities[:6]):
        db.add(User(
            email=f"sysadmin{ci+1}@flow.app",
            hashed_password=get_password_hash("sysadmin123"),
            full_name=f"System Administrator - {community.name}",
            role=UserRole.COMMUNITY_ADMIN,
            partner_id=community.partner_id,
            community_id=community.id,
        ))
        op = User(
            email=f"operator{ci+1}@flow.app",
            hashed_password=get_password_hash("operator123"),
            full_name=f"Operator - {community.name}",
            role=UserRole.OPERATOR,
            partner_id=community.partner_id,
            community_id=community.id,
        )
        db.add(op)
        tr = User(
            email=f"treasurer{ci+1}@flow.app",
            hashed_password=get_password_hash("treasurer123"),
            full_name=f"Treasurer - {community.name}",
            role=UserRole.TREASURER,
            partner_id=community.partner_id,
            community_id=community.id,
        )
        db.add(tr)
    db.flush()

    # Connections, meters, readings, invoices, payments for first 3 communities (demo)
    now = datetime.now(timezone.utc)
    names_pool = [
        "García", "Rodríguez", "López", "Hernández", "Martínez", "Pérez",
        "Sánchez", "Ramírez", "Torres", "Flores", "Rivera", "Gómez",
        "Díaz", "Reyes", "Morales", "Cruz", "Ortiz", "Gutiérrez",
        "Chávez", "Ramos", "Vargas", "Castillo", "Jiménez", "Medina",
    ]
    first_names = ["Juan", "María", "Pedro", "Ana", "José", "Rosa", "Carlos", "Elena", "Luis", "Carmen"]

    for ci, community in enumerate(communities[:6]):
        num_connections = min(community.total_connections, 20)
        for hi in range(num_connections):
            fname = random.choice(first_names)
            lname = random.choice(names_pool)
            hh = Connection(
                account_number=f"C{ci+1:02d}-{hi+1:04d}",
                contact_name=f"{fname} {lname}",
                members_count=random.randint(2, 8),
                status=random.choices(
                    [ConnectionStatus.ACTIVE, ConnectionStatus.ACTIVE, ConnectionStatus.ACTIVE, ConnectionStatus.SUSPENDED],
                    weights=[7, 7, 7, 1],
                )[0],
                has_meter=True,
                community_id=community.id,
            )
            db.add(hh)
            db.flush()

            # Meter
            meter = Meter(
                serial_number=f"M-C{ci+1:02d}-{hi+1:04d}",
                brand="Zenner" if hi % 2 == 0 else "Itron",
                install_date=now - timedelta(days=random.randint(60, 365)),
                connection_id=hh.id,
            )
            db.add(meter)
            db.flush()

            # Meter readings — 12 months of history so trends are meaningful
            cumulative = random.uniform(50, 500)
            baseline = random.uniform(8, 22)
            monthly_consumption: dict[int, float] = {}
            recent: list[float] = []
            for month_offset in range(12, 0, -1):
                consumption = max(0.0, random.gauss(baseline, baseline * 0.18))
                flag_reason = None
                # A few connections show a leak-like spike the admin should notice.
                if month_offset <= 2 and hi % 7 == 0:
                    consumption = baseline * random.uniform(1.8, 3.0)
                    average = sum(recent[-6:]) / len(recent[-6:]) if recent else 0.0
                    pct = round((consumption / average - 1) * 100) if average else 0
                    flag_reason = (
                        f"Consumption {consumption:.1f} m³ is {pct}% above this "
                        f"connection's average of {average:.1f} m³ — possible leak or misread."
                    )
                prev = cumulative
                cumulative += consumption
                monthly_consumption[month_offset] = round(consumption, 1)
                recent.append(consumption)
                reading = MeterReading(
                    reading_value=round(cumulative, 1),
                    previous_value=round(prev, 1),
                    consumption_m3=round(consumption, 1),
                    reading_date=now - timedelta(days=month_offset * 30),
                    meter_id=meter.id,
                    recorded_by=f"Operator - {community.name}",
                    flag_reason=flag_reason,
                )
                db.add(reading)

            meter.last_reading_value = round(cumulative, 1)
            meter.last_reading_date = now - timedelta(days=30)
            meter.avg_consumption_m3 = round(sum(recent[-6:]) / len(recent[-6:]), 1)

            # Invoices for the last 6 months, priced off the actual readings
            for month_offset in range(6, 0, -1):
                period_start = now - timedelta(days=month_offset * 30 + 30)
                period_end = now - timedelta(days=month_offset * 30)
                consumption = monthly_consumption.get(month_offset, baseline)
                variable = consumption * community.tariff_per_m3
                total = community.tariff_fixed + variable

                inv = Invoice(
                    invoice_number=f"INV-C{ci+1:02d}-{hi+1:03d}-{month_offset}",
                    billing_period_start=period_start,
                    billing_period_end=period_end,
                    consumption_m3=round(consumption, 1),
                    fixed_charge=community.tariff_fixed,
                    variable_charge=round(variable, 2),
                    total_amount=round(total, 2),
                    currency=community.currency,
                    due_date=period_end + timedelta(days=15),
                    connection_id=hh.id,
                )

                # Simulate payment status
                pay_chance = random.random()
                if pay_chance > 0.3:
                    inv.amount_paid = inv.total_amount
                    inv.balance_due = 0
                    inv.status = InvoiceStatus.PAID
                elif pay_chance > 0.15:
                    partial = round(inv.total_amount * random.uniform(0.3, 0.7), 2)
                    inv.amount_paid = partial
                    inv.balance_due = round(inv.total_amount - partial, 2)
                    inv.status = InvoiceStatus.PARTIAL
                else:
                    inv.balance_due = inv.total_amount
                    inv.status = InvoiceStatus.OVERDUE if month_offset > 1 else InvoiceStatus.PENDING

                db.add(inv)
                db.flush()

                if inv.amount_paid > 0:
                    pmt = Payment(
                        amount=inv.amount_paid,
                        currency=community.currency,
                        payment_method=random.choice([PaymentMethod.CASH, PaymentMethod.CASH, PaymentMethod.BANK_TRANSFER]),
                        payment_date=period_end + timedelta(days=random.randint(1, 14)),
                        connection_id=hh.id,
                        invoice_id=inv.id,
                    )
                    db.add(pmt)

            # Update outstanding balance
            outstanding = (
                db.query(Invoice)
                .filter(Invoice.connection_id == hh.id, Invoice.balance_due > 0)
                .all()
            )
            hh.outstanding_balance = round(sum(i.balance_due for i in outstanding), 2)

    # Maintenance records
    categories = list(MaintenanceCategory)
    for community in communities[:6]:
        for _ in range(random.randint(2, 6)):
            record = MaintenanceRecord(
                title=random.choice([
                    "Pipe leak near distribution tank",
                    "Valve replacement needed",
                    "Pump motor overheating",
                    "Tank cleaning scheduled",
                    "Meter not registering",
                    "Chlorination system check",
                    "Electrical panel inspection",
                    "Spring box maintenance",
                ]),
                category=random.choice(categories),
                priority=random.choice(list(MaintenancePriority)),
                status=random.choice([MaintenanceStatus.REPORTED, MaintenanceStatus.REPORTED, MaintenanceStatus.IN_PROGRESS, MaintenanceStatus.COMPLETED]),
                reported_date=now - timedelta(days=random.randint(1, 90)),
                reported_by=f"Operator - {community.name}",
                reported_via_whatsapp=random.random() > 0.4,
                community_id=community.id,
            )
            if record.status == MaintenanceStatus.COMPLETED:
                record.resolved_date = record.reported_date + timedelta(days=random.randint(1, 14))
                record.resolved_by = f"System Administrator - {community.name}"
            db.add(record)

    # Expenses — money spent, tracked separately from maintenance reports
    expense_templates = [
        ("Chlorine and water treatment supplies", ExpenseCategory.MAINTENANCE),
        ("PVC pipe and fittings", ExpenseCategory.MAINTENANCE),
        ("Pump repair labour", ExpenseCategory.MAINTENANCE),
        ("Replacement water meter", ExpenseCategory.MAINTENANCE),
        ("Electricity for pumping station", ExpenseCategory.ADMINISTRATIVE),
        ("Operator monthly stipend", ExpenseCategory.ADMINISTRATIVE),
        ("Printing of bills and receipts", ExpenseCategory.ADMINISTRATIVE),
        ("Transport to municipal office", ExpenseCategory.OTHER),
    ]
    for community in communities[:6]:
        scale = 1.0 if community.currency == "USD" else 25.0
        for month_offset in range(9):
            description, category = random.choice(expense_templates)
            db.add(Expense(
                expense_date=now - timedelta(days=month_offset * 30 + random.randint(0, 20)),
                amount=round(random.uniform(10, 220) * scale, 2),
                currency=community.currency,
                description=description,
                category=category,
                receipt_number=f"R-{community.name[:3].upper()}-{random.randint(1000, 9999)}",
                recorded_by=f"Treasurer - {community.name}",
                community_id=community.id,
            ))

    db.commit()
    print(f"Seeded: {len(partners)} partners, {len(communities)} communities, demo connections/billing/maintenance/expenses")


if __name__ == "__main__":
    if "--demo" not in sys.argv:
        raise SystemExit(
            "Refusing to insert sample data. Re-run with --demo for local development, "
            "or use `python -m app.db.bootstrap` for a real deployment."
        )
    seed()

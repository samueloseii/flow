"""AI Analytics Module for Flow.

Provides payment risk prediction, anomaly detection, maintenance prioritization,
financial sustainability alerts, and automated reporting using LLM integration.
"""

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing import Invoice, InvoiceStatus, Payment
from app.models.connection import Connection, ConnectionStatus
from app.models.maintenance import MaintenanceRecord, MaintenanceStatus
from app.models.meter import Meter, MeterReading


def get_payment_risk_scores(db: Session, community_id: str) -> list[dict]:
    """Identify connections at risk of non-payment based on payment history."""
    connections = (
        db.query(Connection)
        .filter(Connection.community_id == community_id, Connection.status == ConnectionStatus.ACTIVE)
        .all()
    )

    risk_scores = []
    for connection in connections:
        overdue_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.connection_id == connection.id,
                Invoice.status.in_([InvoiceStatus.OVERDUE, InvoiceStatus.PENDING]),
            )
            .count()
        )
        total_arrears = (
            db.query(func.coalesce(func.sum(Invoice.balance_due), 0))
            .filter(Invoice.connection_id == connection.id)
            .scalar()
        )

        risk_level = "low"
        if overdue_invoices >= 3 or float(total_arrears) > 100:
            risk_level = "high"
        elif overdue_invoices >= 1 or float(total_arrears) > 30:
            risk_level = "medium"

        risk_scores.append({
            "connection_id": str(connection.id),
            "account_number": connection.account_number,
            "contact_name": connection.contact_name,
            "overdue_invoices": overdue_invoices,
            "total_arrears": float(total_arrears),
            "risk_level": risk_level,
        })

    risk_scores.sort(key=lambda x: x["total_arrears"], reverse=True)
    return risk_scores


def detect_consumption_anomalies(db: Session, community_id: str) -> list[dict]:
    """Detect unusual consumption patterns in meter readings."""
    connection_ids = (
        db.query(Connection.id)
        .filter(Connection.community_id == community_id)
        .subquery()
    )
    meters = (
        db.query(Meter)
        .filter(Meter.connection_id.in_(connection_ids))
        .all()
    )

    anomalies = []
    for meter in meters:
        readings = (
            db.query(MeterReading)
            .filter(MeterReading.meter_id == meter.id)
            .order_by(MeterReading.reading_date.desc())
            .limit(6)
            .all()
        )

        if len(readings) < 3:
            continue

        consumptions = [r.consumption_m3 for r in readings if r.consumption_m3 > 0]
        if not consumptions:
            continue

        avg_consumption = sum(consumptions) / len(consumptions)
        latest = readings[0].consumption_m3

        if avg_consumption > 0 and latest > avg_consumption * 2:
            anomalies.append({
                "meter_id": str(meter.id),
                "serial_number": meter.serial_number,
                "connection_id": str(meter.connection_id),
                "latest_consumption": latest,
                "avg_consumption": round(avg_consumption, 2),
                "deviation_pct": round((latest - avg_consumption) / avg_consumption * 100, 1),
                "type": "high_consumption",
                "message": f"Consumption {latest:.1f} m³ is {(latest/avg_consumption):.1f}x the average",
            })
        elif avg_consumption > 0 and latest < avg_consumption * 0.2:
            anomalies.append({
                "meter_id": str(meter.id),
                "serial_number": meter.serial_number,
                "connection_id": str(meter.connection_id),
                "latest_consumption": latest,
                "avg_consumption": round(avg_consumption, 2),
                "deviation_pct": round((avg_consumption - latest) / avg_consumption * 100, 1),
                "type": "low_consumption",
                "message": f"Consumption {latest:.1f} m³ is unusually low (avg: {avg_consumption:.1f} m³)",
            })

    return anomalies


def prioritize_maintenance(db: Session, community_id: str) -> list[dict]:
    """Prioritize pending maintenance tasks based on age and priority."""
    records = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.community_id == community_id,
            MaintenanceRecord.status.in_([MaintenanceStatus.REPORTED, MaintenanceStatus.IN_PROGRESS]),
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    scored_records = []
    for record in records:
        age_days = (now - record.reported_date.replace(tzinfo=timezone.utc)).days
        priority_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        score = age_days * priority_weight.get(record.priority.value, 1)

        scored_records.append({
            "record_id": str(record.id),
            "title": record.title,
            "category": record.category.value,
            "priority": record.priority.value,
            "status": record.status.value,
            "age_days": age_days,
            "urgency_score": score,
            "recommendation": _maintenance_recommendation(record.priority.value, age_days),
        })

    scored_records.sort(key=lambda x: x["urgency_score"], reverse=True)
    return scored_records


def _maintenance_recommendation(priority: str, age_days: int) -> str:
    if priority == "critical":
        return "Immediate action required"
    if priority == "high" and age_days > 7:
        return "Overdue - schedule immediately"
    if priority == "medium" and age_days > 30:
        return "Aging issue - plan resolution this week"
    if age_days > 60:
        return "Long-standing issue - review and resolve or close"
    return "Monitor and schedule as resources allow"


def get_financial_sustainability_alerts(db: Session, community_id: str) -> list[dict]:
    """Generate financial sustainability alerts for a community."""
    connection_ids = (
        db.query(Connection.id)
        .filter(Connection.community_id == community_id)
        .subquery()
    )

    total_invoiced = float(
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0))
        .filter(Invoice.connection_id.in_(connection_ids))
        .scalar()
    )
    total_paid = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.connection_id.in_(connection_ids))
        .scalar()
    )

    collection_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0

    maintenance_costs = float(
        db.query(func.coalesce(func.sum(MaintenanceRecord.cost), 0))
        .filter(MaintenanceRecord.community_id == community_id)
        .scalar()
    )

    alerts = []
    if collection_rate < 70:
        alerts.append({
            "type": "low_collection_rate",
            "severity": "high",
            "message": f"Collection rate is {collection_rate:.1f}% — below the 70% sustainability threshold",
            "recommendation": "Review arrears, engage with delinquent connections, consider payment plans",
        })

    if total_paid > 0 and maintenance_costs > total_paid * 0.5:
        alerts.append({
            "type": "high_maintenance_cost",
            "severity": "medium",
            "message": f"Maintenance costs ({maintenance_costs:.0f}) exceed 50% of revenue ({total_paid:.0f})",
            "recommendation": "Review maintenance spending, consider preventive maintenance program",
        })

    overdue_count = (
        db.query(Invoice)
        .filter(
            Invoice.connection_id.in_(connection_ids),
            Invoice.status == InvoiceStatus.OVERDUE,
        )
        .count()
    )
    total_invoices = (
        db.query(Invoice)
        .filter(Invoice.connection_id.in_(connection_ids))
        .count()
    )
    if total_invoices > 0 and overdue_count / total_invoices > 0.3:
        alerts.append({
            "type": "high_arrears",
            "severity": "high",
            "message": f"{overdue_count} of {total_invoices} invoices are overdue ({overdue_count/total_invoices*100:.0f}%)",
            "recommendation": "Implement structured collection follow-up and consider disconnection policy",
        })

    if not alerts:
        alerts.append({
            "type": "healthy",
            "severity": "info",
            "message": "No financial sustainability concerns detected",
            "recommendation": "Continue monitoring key metrics",
        })

    return alerts

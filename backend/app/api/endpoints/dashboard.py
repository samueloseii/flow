import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.billing import Invoice, InvoiceStatus, Payment
from app.models.community import Community
from app.models.connection import Connection, ConnectionStatus
from app.models.maintenance import MaintenanceRecord, MaintenanceStatus
from app.models.meter import Meter, MeterReading
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.schemas.dashboard import CommunityDashboard, PartnerDashboard, SystemDashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/community/{community_id}", response_model=CommunityDashboard)
def community_dashboard(
    community_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")

    total_connections = db.query(Connection).filter(
        Connection.community_id == community_id
    ).count()
    active_connections = db.query(Connection).filter(
        Connection.community_id == community_id,
        Connection.status == ConnectionStatus.ACTIVE,
    ).count()

    connection_ids = db.query(Connection.id).filter(
        Connection.community_id == community_id
    ).subquery()

    total_meters = db.query(Meter).filter(Meter.connection_id.in_(connection_ids)).count()

    total_invoiced = db.query(func.coalesce(func.sum(Invoice.total_amount), 0)).filter(
        Invoice.connection_id.in_(connection_ids)
    ).scalar()
    total_paid = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.connection_id.in_(connection_ids)
    ).scalar()

    collection_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0.0

    total_arrears = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
        Invoice.connection_id.in_(connection_ids),
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE]),
    ).scalar()

    pending_maintenance = db.query(MaintenanceRecord).filter(
        MaintenanceRecord.community_id == community_id,
        MaintenanceRecord.status.in_([MaintenanceStatus.REPORTED, MaintenanceStatus.IN_PROGRESS]),
    ).count()

    avg_consumption = db.query(func.coalesce(func.avg(MeterReading.consumption_m3), 0)).filter(
        MeterReading.meter_id.in_(
            db.query(Meter.id).filter(Meter.connection_id.in_(connection_ids))
        )
    ).scalar()

    return CommunityDashboard(
        total_connections=total_connections,
        active_connections=active_connections,
        total_meters=total_meters,
        collection_rate=round(collection_rate, 1),
        total_revenue=float(total_paid),
        total_arrears=float(total_arrears),
        pending_maintenance=pending_maintenance,
        avg_consumption_m3=round(float(avg_consumption), 2),
    )


@router.get("/partner/{partner_id}", response_model=PartnerDashboard)
def partner_dashboard(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.PARTNER_ADMIN)),
):
    community_ids = db.query(Community.id).filter(Community.partner_id == partner_id).subquery()
    total_communities = db.query(Community).filter(Community.partner_id == partner_id).count()

    connection_ids = db.query(Connection.id).filter(
        Connection.community_id.in_(community_ids)
    ).subquery()
    total_connections = db.query(Connection).filter(
        Connection.community_id.in_(community_ids)
    ).count()

    total_invoiced = db.query(func.coalesce(func.sum(Invoice.total_amount), 0)).filter(
        Invoice.connection_id.in_(connection_ids)
    ).scalar()
    total_paid = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.connection_id.in_(connection_ids)
    ).scalar()
    collection_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0.0

    total_arrears = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
        Invoice.connection_id.in_(connection_ids),
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE]),
    ).scalar()

    pending_maintenance = db.query(MaintenanceRecord).filter(
        MaintenanceRecord.community_id.in_(community_ids),
        MaintenanceRecord.status.in_([MaintenanceStatus.REPORTED, MaintenanceStatus.IN_PROGRESS]),
    ).count()

    return PartnerDashboard(
        total_communities=total_communities,
        total_connections=total_connections,
        overall_collection_rate=round(collection_rate, 1),
        total_revenue=float(total_paid),
        total_arrears=float(total_arrears),
        pending_maintenance=pending_maintenance,
        communities_at_risk=0,
    )


@router.get("/system", response_model=SystemDashboard)
def system_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    total_partners = db.query(Partner).count()
    total_communities = db.query(Community).count()
    total_connections = db.query(Connection).count()
    total_users = db.query(User).count()

    total_invoiced = db.query(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar()
    total_paid = db.query(func.coalesce(func.sum(Payment.amount), 0)).scalar()
    collection_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0.0

    total_arrears = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE]),
    ).scalar()

    return SystemDashboard(
        total_partners=total_partners,
        total_communities=total_communities,
        total_connections=total_connections,
        total_users=total_users,
        overall_collection_rate=round(collection_rate, 1),
        total_revenue=float(total_paid),
        total_arrears=float(total_arrears),
    )

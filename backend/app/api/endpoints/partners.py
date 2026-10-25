import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.community import Community
from app.models.organization import Organization
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.schemas.partner import PartnerCreate, PartnerResponse, PartnerUpdate

router = APIRouter(prefix="/partners", tags=["partners"])


def _response(db: Session, partner: Partner) -> PartnerResponse:
    count = db.query(Community).filter(Community.partner_id == partner.id).count()
    return PartnerResponse(
        id=partner.id,
        name=partner.name,
        country=partner.country,
        contact_name=partner.contact_name,
        contact_email=partner.contact_email,
        contact_phone=partner.contact_phone,
        description=partner.description,
        created_at=partner.created_at,
        communities_count=count,
        organization_id=partner.organization_id,
        organization_name=partner.organization.name if partner.organization else None,
    )


@router.get("/", response_model=list[PartnerResponse])
def list_partners(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Partner)
    if current_user.role is not UserRole.SUPER_ADMIN and current_user.partner_id:
        query = query.filter(Partner.id == current_user.partner_id)
    return [_response(db, p) for p in query.order_by(Partner.name).all()]


@router.post("/", response_model=PartnerResponse, status_code=status.HTTP_201_CREATED)
def create_partner(
    payload: PartnerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    if db.query(Partner).filter(Partner.name == payload.name).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A partner with that name already exists",
        )
    data = payload.model_dump(exclude={"new_organization_name"})
    if data.get("organization_id"):
        if not db.query(Organization).filter(Organization.id == data["organization_id"]).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    elif payload.new_organization_name:
        org = db.query(Organization).filter(Organization.name == payload.new_organization_name).first()
        if not org:
            org = Organization(name=payload.new_organization_name, country=payload.country)
            db.add(org)
            db.flush()
        data["organization_id"] = org.id
    else:
        raise HTTPException(status_code=400, detail="Choose the organization this partner belongs to")
    partner = Partner(**data)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return _response(db, partner)


@router.patch("/{partner_id}", response_model=PartnerResponse)
def update_partner(
    partner_id: uuid.UUID,
    payload: PartnerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.PARTNER_ADMIN)),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    data = payload.model_dump(exclude_unset=True)
    if "organization_id" in data and current_user.role is not UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the system administrator moves partners between organizations")
    for field, value in data.items():
        setattr(partner, field, value)
    db.commit()
    db.refresh(partner)
    return _response(db, partner)


@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    if db.query(Community).filter(Community.partner_id == partner_id).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete the communities in this organization first",
        )
    db.query(User).filter(User.partner_id == partner_id).update(
        {User.partner_id: None}, synchronize_session=False
    )
    db.delete(partner)
    db.commit()

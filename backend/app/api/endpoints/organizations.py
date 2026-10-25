import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.organization import Organization
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.schemas.partner import OrganizationCreate, OrganizationResponse, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _response(db: Session, org: Organization) -> OrganizationResponse:
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        country=org.country,
        description=org.description,
        created_at=org.created_at,
        partners_count=db.query(Partner).filter(Partner.organization_id == org.id).count(),
    )


@router.get("/", response_model=list[OrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Organization)
    if current_user.role is not UserRole.SUPER_ADMIN:
        if not current_user.partner_id:
            return []
        query = query.join(Partner, Partner.organization_id == Organization.id).filter(
            Partner.id == current_user.partner_id
        )
    return [_response(db, o) for o in query.order_by(Organization.name).all()]


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    if db.query(Organization).filter(Organization.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An organization with that name already exists")
    org = Organization(**payload.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return _response(db, org)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: uuid.UUID,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return _response(db, org)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if db.query(Partner).filter(Partner.organization_id == organization_id).count():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Move or delete this organization's partners first")
    db.delete(org)
    db.commit()

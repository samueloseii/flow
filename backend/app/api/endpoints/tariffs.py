import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.household import Household
from app.models.tariff import Tariff
from app.models.user import User, UserRole
from app.schemas.tariff import TariffCreate, TariffPreview, TariffResponse, TariffUpdate
from app.services.scope import can_see_committee, forbid, require_committee, visible_committee_ids

router = APIRouter(prefix="/tariffs", tags=["tariffs"])

TARIFF_EDITORS = (UserRole.SUPER_ADMIN, UserRole.PARTNER_ADMIN, UserRole.COMMUNITY_ADMIN, UserRole.TREASURER)


def _response(db: Session, tariff: Tariff) -> TariffResponse:
    response = TariffResponse.model_validate(tariff)
    response.household_count = db.query(Household).filter(Household.tariff_id == tariff.id).count()
    return response


def _require_tariff(db: Session, user: User, tariff_id: uuid.UUID) -> Tariff:
    tariff = db.query(Tariff).filter(Tariff.id == tariff_id).first()
    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")
    if not can_see_committee(db, user, tariff.water_committee_id):
        raise forbid()
    return tariff


@router.get("/", response_model=list[TariffResponse])
def list_tariffs(
    water_committee_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Tariff)
    ids = visible_committee_ids(db, current_user)
    if ids is not None:
        query = query.filter(Tariff.water_committee_id.in_(ids)) if ids else query.filter(False)
    if water_committee_id:
        query = query.filter(Tariff.water_committee_id == water_committee_id)
    return [_response(db, t) for t in query.order_by(Tariff.name).all()]


@router.post("/", response_model=TariffResponse, status_code=status.HTTP_201_CREATED)
def create_tariff(
    payload: TariffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*TARIFF_EDITORS)),
):
    require_committee(db, current_user, payload.water_committee_id)
    tariff = Tariff(**payload.model_dump())
    if tariff.is_default:
        db.query(Tariff).filter(Tariff.water_committee_id == tariff.water_committee_id).update(
            {Tariff.is_default: False}, synchronize_session=False
        )
    db.add(tariff)
    db.commit()
    db.refresh(tariff)
    return _response(db, tariff)


@router.post("/preview", response_model=TariffPreview)
def preview_tariff(
    payload: TariffCreate,
    consumption_m3: float = Query(..., ge=0),
    current_user: User = Depends(get_current_user),
):
    """Work out a bill for a consumption figure before saving the tariff."""
    tariff = Tariff(**payload.model_dump())
    fixed, variable, blocks = tariff.charge_for(consumption_m3)
    return TariffPreview(
        consumption_m3=consumption_m3,
        fixed_charge=fixed,
        variable_charge=variable,
        total=round(fixed + variable, 2),
        blocks=blocks,
    )


@router.get("/{tariff_id}", response_model=TariffResponse)
def get_tariff(
    tariff_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _response(db, _require_tariff(db, current_user, tariff_id))


@router.patch("/{tariff_id}", response_model=TariffResponse)
def update_tariff(
    tariff_id: uuid.UUID,
    payload: TariffUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*TARIFF_EDITORS)),
):
    tariff = _require_tariff(db, current_user, tariff_id)
    data = payload.model_dump(exclude_unset=True)
    thresholds = data.get("thresholds", tariff.thresholds or [])
    rates = data.get("rates", tariff.rates or [])
    if len(rates) != len(thresholds) + 1:
        raise HTTPException(status_code=400, detail="Give one rate per block: one more rate than thresholds")
    if any(b <= a for a, b in zip(thresholds, thresholds[1:])):
        raise HTTPException(status_code=400, detail="Thresholds must increase")
    if data.get("is_default"):
        db.query(Tariff).filter(Tariff.water_committee_id == tariff.water_committee_id).update(
            {Tariff.is_default: False}, synchronize_session=False
        )
    for field, value in data.items():
        setattr(tariff, field, value)
    db.commit()
    db.refresh(tariff)
    return _response(db, tariff)


@router.delete("/{tariff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tariff(
    tariff_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*TARIFF_EDITORS)),
):
    tariff = _require_tariff(db, current_user, tariff_id)
    if db.query(Household).filter(Household.tariff_id == tariff_id).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Households still use this tariff. Move them to another tariff first.",
        )
    db.delete(tariff)
    db.commit()

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.expense import ExpenseCategory


class ExpenseCreate(BaseModel):
    expense_date: datetime
    amount: float
    currency: str = "USD"
    description: str
    category: ExpenseCategory = ExpenseCategory.OTHER
    receipt_number: str | None = None
    notes: str | None = None
    water_committee_id: uuid.UUID | None = None
    community_id: uuid.UUID | None = None


class ExpenseUpdate(BaseModel):
    expense_date: datetime | None = None
    amount: float | None = None
    description: str | None = None
    category: ExpenseCategory | None = None
    receipt_number: str | None = None
    notes: str | None = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    expense_date: datetime
    amount: float
    currency: str
    description: str
    category: ExpenseCategory
    receipt_number: str | None
    recorded_by: str | None
    notes: str | None
    water_committee_id: uuid.UUID
    community_id: uuid.UUID | None = None
    created_at: datetime
    community_name: str | None = None

    class Config:
        from_attributes = True


class ExpenseSummary(BaseModel):
    total: float
    currency: str
    by_category: dict[str, float]
    by_currency: dict[str, float] = {}
    count: int

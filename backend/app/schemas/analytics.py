import uuid

from pydantic import BaseModel


class MonthlyPoint(BaseModel):
    month: str
    label: str
    consumption_m3: float
    billed: float
    collected: float
    expenses: float
    net: float
    cash_position: float
    connections_read: int
    reading_coverage: float
    issues_reported: int
    issues_resolved: int


class AnalyticsTotals(BaseModel):
    billed: float
    collected: float
    expenses: float
    arrears: float
    net_balance: float
    collection_rate: float
    consumption_m3: float
    connections: int
    metered_connections: int
    open_maintenance: int


class AgingBucket(BaseModel):
    bucket: str
    amount: float
    invoices: int


class TopConsumer(BaseModel):
    connection_id: uuid.UUID
    account_number: str
    contact_name: str
    consumption_m3: float


class CategorySlice(BaseModel):
    category: str
    amount: float
    count: int


class StatusSlice(BaseModel):
    status: str
    count: int
    amount: float


class AnalyticsOverview(BaseModel):
    currency: str
    months: list[MonthlyPoint]
    totals: AnalyticsTotals
    aging: list[AgingBucket]
    top_consumers: list[TopConsumer]
    invoice_status: list[StatusSlice]
    expense_categories: list[CategorySlice]

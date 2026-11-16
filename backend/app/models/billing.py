import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_PAYMENT = "mobile_payment"
    OTHER = "other"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    billing_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    billing_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumption_m3: Mapped[float] = mapped_column(Float, default=0.0)
    fixed_charge: Mapped[float] = mapped_column(Float, default=0.0)
    variable_charge: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    balance_due: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), default=InvoiceStatus.PENDING
    )
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    months_overdue: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("connections.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    connection: Mapped["Connection"] = relationship(back_populates="invoices")  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), default=PaymentMethod.CASH
    )
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("connections.id")
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("invoices.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    connection: Mapped["Connection"] = relationship(back_populates="payments")  # noqa: F821
    invoice: Mapped["Invoice | None"] = relationship(back_populates="payments")

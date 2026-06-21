from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID

from app.services.billing import PAYMENT_METHODS, ALL_STATUSES


class LineItemCreate(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v

    @field_validator("unit_price")
    @classmethod
    def unit_price_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("unit_price cannot be negative")
        return v


class LineItemResponse(BaseModel):
    id: UUID
    description: str
    quantity: int
    unit_price: float

    model_config = ConfigDict(from_attributes=True)


class BillingCreate(BaseModel):
    patient_id: UUID
    # An invoice must have at least one charge -- a bill with no line items
    # has nothing to total and shouldn't be creatable.
    line_items: list[LineItemCreate]
    tax_amount: float = 0.0
    discount_amount: float = 0.0
    method: str | None = None

    @field_validator("line_items")
    @classmethod
    def must_have_at_least_one_item(cls, v: list[LineItemCreate]) -> list[LineItemCreate]:
        if not v:
            raise ValueError("a bill must have at least one line item")
        return v

    @field_validator("tax_amount", "discount_amount")
    @classmethod
    def amounts_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("amount cannot be negative")
        return v

    @field_validator("method")
    @classmethod
    def method_must_be_known(cls, v: str | None) -> str | None:
        if v is not None and v not in PAYMENT_METHODS:
            raise ValueError(f"method must be one of {sorted(PAYMENT_METHODS)}")
        return v


class BillingUpdate(BaseModel):
    # `amount`/`subtotal` are intentionally absent -- they're always derived
    # from line items + tax - discount (see services/billing.py). Clients
    # update the inputs (line items, tax, discount, status, method) and the
    # server recomputes the total.
    status: str | None = None
    method: str | None = None
    tax_amount: float | None = None
    discount_amount: float | None = None

    @field_validator("status")
    @classmethod
    def status_must_be_known(cls, v: str | None) -> str | None:
        if v is not None and v not in ALL_STATUSES:
            raise ValueError(f"status must be one of {sorted(ALL_STATUSES)}")
        return v

    @field_validator("method")
    @classmethod
    def method_must_be_known(cls, v: str | None) -> str | None:
        if v is not None and v not in PAYMENT_METHODS:
            raise ValueError(f"method must be one of {sorted(PAYMENT_METHODS)}")
        return v

    @field_validator("tax_amount", "discount_amount")
    @classmethod
    def amounts_must_be_non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("amount cannot be negative")
        return v


class BillingResponse(BaseModel):
    id: UUID
    patient_id: UUID
    subtotal: float
    tax_amount: float
    discount_amount: float
    amount: float
    status: str
    method: str | None
    created_at: datetime
    line_items: list[LineItemResponse] = []

    model_config = ConfigDict(from_attributes=True)

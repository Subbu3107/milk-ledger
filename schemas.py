from pydantic import BaseModel
from typing import Optional
from datetime import date
from enum import Enum

class BillingType(str, Enum):
    daily = "daily"
    monthly = "monthly"
    hybrid = "hybrid"

# ── Customer ──────────────────────────────────────────────────────────────────
class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    cow_price_per_liter: float = 0.0
    buffalo_price_per_liter: float = 0.0
    billing_type: BillingType = BillingType.monthly

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    cow_price_per_liter: Optional[float] = None
    buffalo_price_per_liter: Optional[float] = None
    billing_type: Optional[BillingType] = None

class CustomerOut(CustomerBase):
    id: int

    class Config:
        orm_mode = True

# ── Milk Entry ────────────────────────────────────────────────────────────────
class MilkEntryCreate(BaseModel):
    customer_id: int
    date: date
    cow_qty: float = 0.0
    buffalo_qty: float = 0.0

class MilkEntryOut(BaseModel):
    id: int
    customer_id: int
    date: date
    cow_qty: float
    buffalo_qty: float
    cow_total: float
    buffalo_total: float
    grand_total: float

    class Config:
        orm_mode = True

# ── Monthly Summary ───────────────────────────────────────────────────────────
class CustomerMonthlySummary(BaseModel):
    customer_id: int
    customer_name: str
    phone: Optional[str]
    cow_price_per_liter: float
    buffalo_price_per_liter: float
    total_cow_qty: float
    total_buffalo_qty: float
    total_cow_amount: float
    total_buffalo_amount: float
    grand_total: float
    entry_count: int

# ── New Payment Schemas ──────────────────────────────────────────────────────
class PaymentBase(BaseModel):
    customer_id: int
    year: int
    month: int
    amount: float
    status: str = "pending"
    paid_date: Optional[date] = None
    notes: Optional[str] = None

class PaymentCreate(PaymentBase):
    pass

class PaymentOut(PaymentBase):
    id: int

    class Config:
        orm_mode = True

# ── Daily Default ─────────────────────────────────────────────────────────────
class DailyDefaultBase(BaseModel):
    customer_id: int
    cow_qty: float = 0.0
    buffalo_qty: float = 0.0
    skip_sunday: bool = True

class DailyDefaultCreate(DailyDefaultBase):
    pass

class DailyDefaultOut(DailyDefaultBase):
    id: int
    created_at: date

    class Config:
        orm_mode = True

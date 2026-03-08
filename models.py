from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Enum as SQLEnum, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import date

class BillingType(str, enum.Enum):
    daily = "daily"
    monthly = "monthly"
    hybrid = "hybrid"

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    cow_price_per_liter = Column(Float, default=0.0)
    buffalo_price_per_liter = Column(Float, default=0.0)
    billing_type = Column(SQLEnum(BillingType), default=BillingType.monthly)

    entries = relationship("MilkEntry", back_populates="customer", cascade="all, delete-orphan")

class MilkEntry(Base):
    __tablename__ = "milk_entries"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    date = Column(Date, nullable=False)
    cow_qty = Column(Float, default=0.0)
    buffalo_qty = Column(Float, default=0.0)
    cow_total = Column(Float, default=0.0)
    buffalo_total = Column(Float, default=0.0)
    grand_total = Column(Float, default=0.0)

    customer = relationship("Customer", back_populates="entries")

    __table_args__ = (
        UniqueConstraint('customer_id', 'date', name='unique_customer_date'),
    )

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    entry_id = Column(Integer, ForeignKey("milk_entries.id"), nullable=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending")
    paid_date = Column(Date, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(Date, default=date.today)

    customer = relationship("Customer", backref="payments")
    entry = relationship("MilkEntry")

class DailyDefault(Base):
    __tablename__ = "daily_defaults"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), unique=True, nullable=False)
    cow_qty = Column(Float, default=0.0)
    buffalo_qty = Column(Float, default=0.0)
    skip_sunday = Column(Boolean, default=True)
    created_at = Column(Date, default=date.today)

    customer = relationship("Customer", backref="daily_default")


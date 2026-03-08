from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from models import Customer, MilkEntry, Payment, DailyDefault,BillingType
from schemas import CustomerCreate, CustomerUpdate, MilkEntryCreate, PaymentCreate, DailyDefaultCreate
from datetime import date
from typing import Optional

# ── Customers ─────────────────────────────────────────────────────────────────
def get_customers(db: Session):
    return db.query(Customer).order_by(Customer.name).all()

def get_customer(db: Session, customer_id: int):
    return db.query(Customer).filter(Customer.id == customer_id).first()

def create_customer(db: Session, data: CustomerCreate):
    c = Customer(**data.dict())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def update_customer(db: Session, customer_id: int, data: CustomerUpdate):
    c = get_customer(db, customer_id)
    if not c:
        return None
    for k, v in data.dict(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c

def delete_customer(db: Session, customer_id: int):
    c = get_customer(db, customer_id)
    if c:
        # Delete daily default if exists
        db.query(DailyDefault).filter(DailyDefault.customer_id == customer_id).delete()
        db.delete(c)
        db.commit()
    return c

# ── Milk Entries ──────────────────────────────────────────────────────────────
def get_entries(db: Session, customer_id: int = None, year: int = None, month: int = None):
    q = db.query(MilkEntry)
    if customer_id:
        q = q.filter(MilkEntry.customer_id == customer_id)
    if year:
        q = q.filter(extract("year", MilkEntry.date) == year)
    if month:
        q = q.filter(extract("month", MilkEntry.date) == month)
    return q.order_by(MilkEntry.date.desc()).all()

def get_entries_by_date(db: Session, customer_id: int, target_date: date):
    return db.query(MilkEntry).filter(
        MilkEntry.customer_id == customer_id,
        MilkEntry.date == target_date
    ).all()

def create_entry(db: Session, data: MilkEntryCreate):
    customer = get_customer(db, data.customer_id)
    if not customer:
        return None

    # Check for duplicate entry on same date
    existing = db.query(MilkEntry).filter(
        MilkEntry.customer_id == data.customer_id,
        MilkEntry.date == data.date
    ).first()
    if existing:
        raise ValueError("Entry already exists for this date")

    cow_total = data.cow_qty * customer.cow_price_per_liter
    buffalo_total = data.buffalo_qty * customer.buffalo_price_per_liter
    grand_total = cow_total + buffalo_total

    entry = MilkEntry(
        customer_id=data.customer_id,
        date=data.date,
        cow_qty=data.cow_qty,
        buffalo_qty=data.buffalo_qty,
        cow_total=cow_total,
        buffalo_total=buffalo_total,
        grand_total=grand_total,
    )
    db.add(entry)
    db.flush()

    # Auto‑create paid payment for daily customers
    if customer.billing_type == BillingType.daily:
        payment = Payment(
            customer_id=customer.id,
            entry_id=entry.id,
            year=data.date.year,
            month=data.date.month,
            amount=grand_total,
            status="paid",
            paid_date=data.date,
            notes=f"Auto payment for entry #{entry.id}"
        )
        db.add(payment)

    db.commit()
    db.refresh(entry)
    return entry

def delete_entry(db: Session, entry_id: int):
    e = db.query(MilkEntry).filter(MilkEntry.id == entry_id).first()
    if e:
        db.delete(e)
        db.commit()
    return e

# ── Monthly Summary ───────────────────────────────────────────────────────────
def get_monthly_summary(db: Session, year: int, month: int):
    customers = db.query(Customer).all()
    summaries = []
    for c in customers:
        entries = (
            db.query(MilkEntry)
            .filter(
                MilkEntry.customer_id == c.id,
                extract("year", MilkEntry.date) == year,
                extract("month", MilkEntry.date) == month,
            )
            .all()
        )
        total_cow_qty = sum(e.cow_qty for e in entries)
        total_buffalo_qty = sum(e.buffalo_qty for e in entries)
        total_cow_amount = sum(e.cow_total for e in entries)
        total_buffalo_amount = sum(e.buffalo_total for e in entries)
        grand = sum(e.grand_total for e in entries)

        summaries.append({
            "customer_id": c.id,
            "customer_name": c.name,
            "phone": c.phone,
            "cow_price_per_liter": c.cow_price_per_liter,
            "buffalo_price_per_liter": c.buffalo_price_per_liter,
            "total_cow_qty": total_cow_qty,
            "total_buffalo_qty": total_buffalo_qty,
            "total_cow_amount": total_cow_amount,
            "total_buffalo_amount": total_buffalo_amount,
            "grand_total": grand,
            "entry_count": len(entries),
        })
    return summaries

# ── Payments ─────────────────────────────────────────────────────────────────
def get_payments(db: Session, customer_id: Optional[int] = None, year: Optional[int] = None, month: Optional[int] = None):
    q = db.query(Payment)
    if customer_id:
        q = q.filter(Payment.customer_id == customer_id)
    if year:
        q = q.filter(Payment.year == year)
    if month:
        q = q.filter(Payment.month == month)
    return q.order_by(Payment.paid_date.desc()).all()

def get_customer_payment(db: Session, customer_id: int, year: int, month: int):
    return db.query(Payment).filter(
        Payment.customer_id == customer_id,
        Payment.year == year,
        Payment.month == month
    ).first()

def create_or_update_payment(db: Session, data: PaymentCreate):
    payment = get_customer_payment(db, data.customer_id, data.year, data.month)
    if payment:
        for k, v in data.dict().items():
            setattr(payment, k, v)
    else:
        payment = Payment(**data.dict())
        db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment

# ── Daily Defaults ────────────────────────────────────────────────────────────
def get_daily_default(db: Session, customer_id: int):
    return db.query(DailyDefault).filter(DailyDefault.customer_id == customer_id).first()

def set_daily_default(db: Session, data: DailyDefaultCreate):
    default = get_daily_default(db, data.customer_id)
    if default:
        for k, v in data.dict().items():
            setattr(default, k, v)
    else:
        default = DailyDefault(**data.dict())
        db.add(default)
    db.commit()
    db.refresh(default)
    return default

def get_last_entry(db: Session, customer_id: int):
    today = date.today()
    return db.query(MilkEntry)\
        .filter(
            MilkEntry.customer_id == customer_id,
            MilkEntry.date < today
        )\
        .order_by(MilkEntry.date.desc())\
        .first()

def generate_monthly_entries(db: Session, customer_id: int, year: int, month: int):
    customer = get_customer(db, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    default = get_daily_default(db, customer_id)
    if not default or (default.cow_qty == 0 and default.buffalo_qty == 0):
        raise ValueError("No default quantities set for this customer")

    import calendar
    last_day = calendar.monthrange(year, month)[1]
    created = []
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        if default.skip_sunday and d.weekday() == 6:
            continue
        existing = get_entries_by_date(db, customer_id, d)
        if existing:
            continue
        entry = create_entry(db, MilkEntryCreate(
            customer_id=customer_id,
            date=d,
            cow_qty=default.cow_qty,
            buffalo_qty=default.buffalo_qty
        ))
        created.append(entry)
    return created

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import calendar
from datetime import date
from sqlalchemy import func
from models import MilkEntry

import models, schemas, crud
from database import engine, get_db
from pdf_generator import generate_bill, BILLS_DIR

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Milk Vendor Ledger API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Vendor settings ─────────────────────────────────────────────────────────
VENDOR_NAME = "Murugan Dairy"
UPI_ID = "murugan@upi"
PAYMENT_DEADLINE = "before 10th"

# ── Helper: Build bill header ───────────────────────────────────────────────
def build_bill_header(billing_type: models.BillingType, year: int, month: int) -> str:
    today = date.today()
    month_name = calendar.month_name[month]

    if billing_type == models.BillingType.daily:
        return today.strftime("%d/%m/%Y")
    if billing_type == models.BillingType.monthly:
        return f"{month_name} {year}"
    if billing_type == models.BillingType.hybrid:
        last_day = calendar.monthrange(year, month)[1]
        return f"01/{month:02d}/{year} to {last_day:02d}/{month:02d}/{year}"
    return f"{month_name} {year}"  # fallback

# ── Helper: Format bill message ─────────────────────────────────────────────
def format_bill_message(customer, header, cow_qty, buf_qty, cow_amount, buf_amount, total):
    cow_line = f"{cow_qty:.1f} L × ₹{customer.cow_price_per_liter:.0f} = ₹{cow_amount:.2f}"
    buf_line = f"{buf_qty:.1f} L × ₹{customer.buffalo_price_per_liter:.0f} = ₹{buf_amount:.2f}"
    return f"""🧾 Milk Bill – {header}

Vendor: {VENDOR_NAME}
Customer: {customer.name}

🐄 Cow Milk
{cow_line}

🐃 Buffalo Milk
{buf_line}

💰 Total Bill: ₹{total:.2f}

UPI: {UPI_ID}
Please pay {PAYMENT_DEADLINE} 🙏

Thank you"""

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "message": "Milk Vendor Ledger API v2"}

# ── Customers ─────────────────────────────────────────────────────────────────
@app.get("/customers", response_model=List[schemas.CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return crud.get_customers(db)

@app.post("/customers", response_model=schemas.CustomerOut, status_code=201)
def create_customer(data: schemas.CustomerCreate, db: Session = Depends(get_db)):
    return crud.create_customer(db, data)

@app.get("/customers/{customer_id}", response_model=schemas.CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = crud.get_customer(db, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c

@app.put("/customers/{customer_id}", response_model=schemas.CustomerOut)
def update_customer(
    customer_id: int, data: schemas.CustomerUpdate, db: Session = Depends(get_db)
):
    c = crud.update_customer(db, customer_id, data)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c

@app.delete("/customers/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    c = crud.delete_customer(db, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"message": f"Customer '{c.name}' deleted"}

# ── Milk Entries ──────────────────────────────────────────────────────────────
@app.get("/entries", response_model=List[schemas.MilkEntryOut])
def list_entries(
    customer_id: Optional[int] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return crud.get_entries(db, customer_id=customer_id, year=year, month=month)

# ... (other imports and code) ...

@app.post("/entries", response_model=schemas.MilkEntryOut, status_code=201)
def create_entry(data: schemas.MilkEntryCreate, db: Session = Depends(get_db)):
    try:
        entry = crud.create_entry(db, data)
        if not entry:
            raise HTTPException(status_code=404, detail="Customer not found")
        return entry
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ... (rest of endpoints) ...

@app.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    e = crud.delete_entry(db, entry_id)
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Entry deleted"}

# ── Today Total Per Customer ──────────────────────────────────────────────────
@app.get("/customers/{customer_id}/today-total")
def get_today_total(customer_id: int, db: Session = Depends(get_db)):
    today_str = date.today().isoformat()
    customer = crud.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    entries = crud.get_entries(db, customer_id=customer_id)
    total = 0
    for e in entries:
        if str(e.date) == today_str:
            total += (
                e.cow_qty * customer.cow_price_per_liter +
                e.buffalo_qty * customer.buffalo_price_per_liter
            )
    return {"total": total}

@app.get("/customers/{customer_id}/last-entry", response_model=Optional[schemas.MilkEntryOut])
def get_last_entry(customer_id: int, db: Session = Depends(get_db)):
    entry = crud.get_last_entry(db, customer_id)
    if not entry:
        raise HTTPException(status_code=404, detail="No previous entry found")
    return entry

# ── Monthly Summary ───────────────────────────────────────────────────────────
@app.get("/summary/monthly", response_model=List[schemas.CustomerMonthlySummary])
def monthly_summary(year: int, month: int, db: Session = Depends(get_db)):
    return crud.get_monthly_summary(db, year=year, month=month)

# ── Monthly Bill PDF ──────────────────────────────────────────────────────────
@app.get(
    "/generate-monthly-bill/{customer_id}/{year}/{month}",
    summary="Generate & download a monthly PDF bill for a customer",
    response_class=FileResponse,
    tags=["Bills"],
)
def generate_monthly_bill(
    customer_id: int,
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="month must be between 1 and 12")
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=400, detail="year out of valid range")

    customer = crud.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    entries = crud.get_entries(db, customer_id=customer_id, year=year, month=month)
    entries = sorted(entries, key=lambda e: e.date)

    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No entries found for '{customer.name}' in {year}-{month:02d}",
        )

    try:
        pdf_path = generate_bill(
            customer_name=customer.name,
            customer_phone=customer.phone,
            cow_price=customer.cow_price_per_liter,
            buffalo_price=customer.buffalo_price_per_liter,
            entries=entries,
            year=year,
            month=month,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    month_label = calendar.month_name[month]
    download_name = (
        f"MilkBill_{customer.name.replace(' ', '_')}_{month_label}_{year}.pdf"
    )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )

# ── Monthly Bill Text Message (WhatsApp) ─────────────────────────────────────
@app.get("/bill-text/{customer_id}/{year}/{month}")
def generate_bill_text(customer_id: int, year: int, month: int, db: Session = Depends(get_db)):
    customer = crud.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.billing_type == models.BillingType.daily:
        entries = crud.get_entries_by_date(db, customer_id, date.today())
    else:
        entries = crud.get_entries(db, customer_id=customer_id, year=year, month=month)

    cow_qty = sum(e.cow_qty for e in entries)
    buf_qty = sum(e.buffalo_qty for e in entries)
    cow_amount = cow_qty * customer.cow_price_per_liter
    buf_amount = buf_qty * customer.buffalo_price_per_liter
    total = cow_amount + buf_amount

    header = build_bill_header(customer.billing_type, year, month)
    message = format_bill_message(customer, header, cow_qty, buf_qty, cow_amount, buf_amount, total)

    return {
        "phone": customer.phone,
        "message": message
    }

# ── Bulk Bill Text for all customers with entries ────────────────────────────
@app.get("/bulk-bill-text/{year}/{month}")
def generate_bulk_bill_text(year: int, month: int, db: Session = Depends(get_db)):
    customers = crud.get_customers(db)
    result = []

    for customer in customers:
        entries = crud.get_entries(db, customer_id=customer.id, year=year, month=month)
        if not entries:
            continue

        cow_qty = sum(e.cow_qty for e in entries)
        buf_qty = sum(e.buffalo_qty for e in entries)
        cow_amount = cow_qty * customer.cow_price_per_liter
        buf_amount = buf_qty * customer.buffalo_price_per_liter
        total = cow_amount + buf_amount

        header = build_bill_header(customer.billing_type, year, month)
        message = format_bill_message(customer, header, cow_qty, buf_qty, cow_amount, buf_amount, total)

        result.append({
            "phone": customer.phone,
            "message": message,
            "customer_name": customer.name
        })

    return result

# ── New Payment Endpoints ─────────────────────────────────────────────────────
@app.get("/payments", response_model=List[schemas.PaymentOut])
def list_payments(
    customer_id: Optional[int] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db)
):
    return crud.get_payments(db, customer_id=customer_id, year=year, month=month)

@app.post("/payments", response_model=schemas.PaymentOut)
def update_payment(data: schemas.PaymentCreate, db: Session = Depends(get_db)):
    return crud.create_or_update_payment(db, data)

# ── Daily Defaults ────────────────────────────────────────────────────────────
@app.post("/daily-defaults", response_model=schemas.DailyDefaultOut)
def set_daily_default(data: schemas.DailyDefaultCreate, db: Session = Depends(get_db)):
    return crud.set_daily_default(db, data)

@app.post("/generate-monthly-entries/{customer_id}/{year}/{month}")
def generate_monthly_entries(customer_id: int, year: int, month: int, db: Session = Depends(get_db)):
    try:
        entries = crud.generate_monthly_entries(db, customer_id, year, month)
        return {"message": f"Generated {len(entries)} entries", "count": len(entries)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/reminder-text/{customer_id}/{year}/{month}")
def generate_reminder_text(customer_id: int, year: int, month: int, db: Session = Depends(get_db)):
    customer = crud.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Get monthly total and payments
    entries = crud.get_entries(db, customer_id=customer_id, year=year, month=month)
    payments = crud.get_payments(db, customer_id=customer_id, year=year, month=month)

    total = sum(e.grand_total for e in entries)
    paid = sum(p.amount for p in payments)
    pending = total - paid

    month_name = calendar.month_name[month]
    message = f"""🔔 Payment Reminder

Hello {customer.name},

Your milk bill for {month_name} {year} is ₹{total:.2f}.
Paid: ₹{paid:.2f}
Pending: ₹{pending:.2f}

Please pay at your earliest convenience.

– {VENDOR_NAME}
UPI: {UPI_ID}"""

    return {"phone": customer.phone, "message": message}


@app.get("/dashboard/today")
def today_dashboard(db: Session = Depends(get_db)):
    today = date.today()
    total = db.query(func.sum(MilkEntry.grand_total))\
        .filter(MilkEntry.date == today)\
        .scalar() or 0
    return {"date": today.isoformat(), "total": total}


"""
pdf_generator.py
────────────────
Generates a professional monthly milk bill PDF using ReportLab.
Called by the /generate-monthly-bill endpoint in main.py.
"""

import os
import calendar
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)

# ── Output directory ──────────────────────────────────────────────────────────
BILLS_DIR = Path(__file__).parent / "bills"
BILLS_DIR.mkdir(exist_ok=True)

# ── Brand colours ─────────────────────────────────────────────────────────────
SAFFRON      = colors.HexColor("#D97706")
SAFFRON_DARK = colors.HexColor("#B45309")
SAFFRON_LITE = colors.HexColor("#FEF3C7")
COW_AMBER    = colors.HexColor("#92400E")
BUF_NAVY     = colors.HexColor("#1E3A5F")
CREAM        = colors.HexColor("#FFFDF5")
DARK         = colors.HexColor("#2C1A0E")
MID          = colors.HexColor("#6B4C3B")
LIGHT_RULE   = colors.HexColor("#E8D9B8")
GREEN        = colors.HexColor("#16A34A")
TABLE_ALT    = colors.HexColor("#FDF6E3")


def _month_label(year: int, month: int) -> str:
    return f"{calendar.month_name[month]} {year}"


def generate_bill(
    customer_name: str,
    customer_phone: Optional[str],
    cow_price: float,
    buffalo_price: float,
    entries: list,          # list of MilkEntry ORM objects, sorted by date ASC
    year: int,
    month: int,
) -> Path:
    """
    Build the PDF, save to bills/<filename>, return the Path.
    """

    # ── Derived totals ─────────────────────────────────────────────────────────
    total_cow_qty      = sum(e.cow_qty      for e in entries)
    total_buffalo_qty  = sum(e.buffalo_qty  for e in entries)
    total_cow_amount   = sum(e.cow_total    for e in entries)
    total_buffalo_amt  = sum(e.buffalo_total for e in entries)
    grand_total        = sum(e.grand_total  for e in entries)
    generated_on       = datetime.now().strftime("%d %b %Y, %I:%M %p")

    # ── File path ──────────────────────────────────────────────────────────────
    safe_name = "".join(c if c.isalnum() else "_" for c in customer_name)
    filename  = f"bill_{safe_name}_{year}_{month:02d}.pdf"
    filepath  = BILLS_DIR / filename

    # ── Document setup ─────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Milk Bill – {customer_name} – {_month_label(year, month)}",
        author="Milk Vendor Smart Ledger",
    )

    styles = getSampleStyleSheet()
    W = A4[0] - 4 * cm   # usable width

    # ── Custom paragraph styles ────────────────────────────────────────────────
    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    style_appname = ps("AppName",
        fontName="Helvetica-Bold", fontSize=11,
        textColor=MID, alignment=TA_CENTER, spaceAfter=2)
    style_title = ps("Title",
        fontName="Helvetica-Bold", fontSize=26,
        textColor=SAFFRON_DARK, alignment=TA_CENTER, spaceAfter=4, leading=30)
    style_subtitle = ps("Subtitle",
        fontName="Helvetica", fontSize=11,
        textColor=MID, alignment=TA_CENTER, spaceAfter=2)
    style_label = ps("Label",
        fontName="Helvetica-Bold", fontSize=9,
        textColor=MID, spaceAfter=1)
    style_value = ps("Value",
        fontName="Helvetica", fontSize=12,
        textColor=DARK)
    style_section = ps("Section",
        fontName="Helvetica-Bold", fontSize=10,
        textColor=SAFFRON_DARK, spaceBefore=12, spaceAfter=4)
    style_footer = ps("Footer",
        fontName="Helvetica", fontSize=8,
        textColor=MID, alignment=TA_CENTER)
    style_tbl_hdr = ps("TblHdr",
        fontName="Helvetica-Bold", fontSize=9,
        textColor=colors.white, alignment=TA_CENTER)
    style_tbl_cell = ps("TblCell",
        fontName="Helvetica", fontSize=9,
        textColor=DARK, alignment=TA_CENTER)
    style_tbl_cell_L = ps("TblCellL",
        fontName="Helvetica", fontSize=9,
        textColor=DARK, alignment=TA_LEFT)
    style_tbl_total = ps("TblTotal",
        fontName="Helvetica-Bold", fontSize=9,
        textColor=DARK, alignment=TA_CENTER)
    style_amt = ps("Amt",
        fontName="Helvetica-Bold", fontSize=14,
        textColor=GREEN, alignment=TA_RIGHT)

    story = []

    # ══════════════════════════════════════════════════════
    # HEADER BLOCK
    # ══════════════════════════════════════════════════════
    story.append(Paragraph("🥛  Milk Vendor Smart Ledger", style_appname))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Monthly Milk Bill", style_title))
    story.append(Paragraph(_month_label(year, month), style_subtitle))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=2, color=SAFFRON, spaceAfter=6))

    # ══════════════════════════════════════════════════════
    # CUSTOMER INFO TABLE
    # ══════════════════════════════════════════════════════
    story.append(Paragraph("Customer Details", style_section))

    phone_display = customer_phone or "—"
    info_data = [
        [
            Paragraph("Customer Name", style_label),
            Paragraph(customer_name, style_value),
            Paragraph("Phone", style_label),
            Paragraph(phone_display, style_value),
        ],
        [
            Paragraph("Billing Period", style_label),
            Paragraph(_month_label(year, month), style_value),
            Paragraph("Generated On", style_label),
            Paragraph(generated_on, style_value),
        ],
        [
            Paragraph("Cow Rate", style_label),
            Paragraph(f"₹{cow_price:.2f} / Litre", style_value),
            Paragraph("Buffalo Rate", style_label),
            Paragraph(f"₹{buffalo_price:.2f} / Litre", style_value),
        ],
    ]

    info_table = Table(info_data, colWidths=[3.0 * cm, 6.5 * cm, 3.0 * cm, 5.5 * cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), CREAM),
        ("BOX",         (0, 0), (-1, -1), 1, LIGHT_RULE),
        ("INNERGRID",   (0, 0), (-1, -1), 0.5, LIGHT_RULE),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CREAM, SAFFRON_LITE]),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",(0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # ══════════════════════════════════════════════════════
    # DAILY ENTRIES TABLE
    # ══════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_RULE, spaceAfter=4))
    story.append(Paragraph("Daily Delivery Log", style_section))

    # Column widths: Date | Cow Qty | Buffalo Qty | Cow Amt | Buffalo Amt | Daily Total
    col_w = [3.2*cm, 2.5*cm, 2.8*cm, 2.8*cm, 2.8*cm, 3.9*cm]

    tbl_hdr = [
        Paragraph("Date",         style_tbl_hdr),
        Paragraph("Cow\n(Litres)",style_tbl_hdr),
        Paragraph("Buffalo\n(Litres)", style_tbl_hdr),
        Paragraph("Cow\nAmount",  style_tbl_hdr),
        Paragraph("Buffalo\nAmount", style_tbl_hdr),
        Paragraph("Daily\nTotal", style_tbl_hdr),
    ]

    tbl_data = [tbl_hdr]
    for i, e in enumerate(entries):
        date_str = e.date.strftime("%d %b") if hasattr(e.date, "strftime") else str(e.date)
        row = [
            Paragraph(date_str,           style_tbl_cell_L),
            Paragraph(f"{e.cow_qty:.1f}",     style_tbl_cell),
            Paragraph(f"{e.buffalo_qty:.1f}", style_tbl_cell),
            Paragraph(f"₹{e.cow_total:.2f}",     style_tbl_cell),
            Paragraph(f"₹{e.buffalo_total:.2f}", style_tbl_cell),
            Paragraph(f"₹{e.grand_total:.2f}",   style_tbl_cell),
        ]
        tbl_data.append(row)

    # Totals footer row
    tbl_data.append([
        Paragraph("TOTAL", style_tbl_total),
        Paragraph(f"{total_cow_qty:.1f}",     style_tbl_total),
        Paragraph(f"{total_buffalo_qty:.1f}", style_tbl_total),
        Paragraph(f"₹{total_cow_amount:.2f}",    style_tbl_total),
        Paragraph(f"₹{total_buffalo_amt:.2f}",   style_tbl_total),
        Paragraph(f"₹{grand_total:.2f}",         style_tbl_total),
    ])

    n = len(entries)
    entry_table = Table(tbl_data, colWidths=col_w, repeatRows=1)

    # Build alternating row colours
    row_styles = [
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), SAFFRON_DARK),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BOX",           (0, 0), (-1, -1), 1, LIGHT_RULE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, LIGHT_RULE),
        # Totals footer
        ("BACKGROUND",    (0, n+1), (-1, n+1), SAFFRON_LITE),
        ("FONTNAME",      (0, n+1), (-1, n+1), "Helvetica-Bold"),
        ("LINEABOVE",     (0, n+1), (-1, n+1), 1.5, SAFFRON),
    ]

    # Alternate data rows
    for r in range(1, n + 1):
        bg = CREAM if r % 2 == 0 else colors.white
        row_styles.append(("BACKGROUND", (0, r), (-1, r), bg))

    entry_table.setStyle(TableStyle(row_styles))
    story.append(entry_table)
    story.append(Spacer(1, 8 * mm))

    # ══════════════════════════════════════════════════════
    # SUMMARY BOX
    # ══════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_RULE, spaceAfter=4))
    story.append(Paragraph("Bill Summary", style_section))

    summary_data = [
        ["", "Description",                   "Qty (Litres)", "Rate (₹/L)",       "Amount (₹)"],
        ["🐄", "Cow Milk",    f"{total_cow_qty:.2f}",     f"{cow_price:.2f}",     f"₹{total_cow_amount:.2f}"],
        ["🐃", "Buffalo Milk",f"{total_buffalo_qty:.2f}", f"{buffalo_price:.2f}", f"₹{total_buffalo_amt:.2f}"],
        ["", "GRAND TOTAL", f"{(total_cow_qty+total_buffalo_qty):.2f}", "—", f"₹{grand_total:.2f}"],
    ]

    sum_style = ps("SumCell", fontName="Helvetica", fontSize=10, textColor=DARK, alignment=TA_CENTER)
    sum_bold  = ps("SumBold", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, alignment=TA_CENTER)
    sum_grand = ps("SumGrand",fontName="Helvetica-Bold", fontSize=13, textColor=GREEN, alignment=TA_CENTER)

    formatted = []
    for ri, row in enumerate(summary_data):
        if ri == 0:
            formatted.append([Paragraph(c, ps("H", fontName="Helvetica-Bold", fontSize=9,
                textColor=colors.white, alignment=TA_CENTER)) for c in row])
        elif ri == 3:
            formatted.append([
                Paragraph(row[0], sum_bold),
                Paragraph(row[1], sum_bold),
                Paragraph(row[2], sum_bold),
                Paragraph(row[3], sum_bold),
                Paragraph(row[4], sum_grand),
            ])
        else:
            formatted.append([Paragraph(c, sum_style) for c in row])

    sum_table = Table(formatted, colWidths=[0.8*cm, 4.5*cm, 3.5*cm, 3.5*cm, 5.7*cm])
    sum_table.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), SAFFRON_DARK),
        ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, 2), [colors.white, SAFFRON_LITE]),
        ("BACKGROUND",     (0, 3), (-1, 3), SAFFRON_LITE),
        ("BOX",            (0, 0), (-1, -1), 1.5, SAFFRON),
        ("INNERGRID",      (0, 0), (-1, -1), 0.4, LIGHT_RULE),
        ("LINEABOVE",      (0, 3), (-1, 3), 1.5, SAFFRON),
        ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",     (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 7),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 10 * mm))

    # ══════════════════════════════════════════════════════
    # AMOUNT DUE HIGHLIGHT
    # ══════════════════════════════════════════════════════
    due_data = [[
        Paragraph("TOTAL AMOUNT DUE", ps("DueL", fontName="Helvetica-Bold", fontSize=13,
            textColor=colors.white, alignment=TA_LEFT)),
        Paragraph(f"₹ {grand_total:,.2f}", ps("DueR", fontName="Helvetica-Bold", fontSize=20,
            textColor=colors.white, alignment=TA_RIGHT)),
    ]]
    due_table = Table(due_data, colWidths=[10*cm, 8*cm])
    due_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), SAFFRON_DARK),
        ("ROUNDEDCORNERS",[6]),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(due_table)
    story.append(Spacer(1, 10 * mm))

    # ══════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_RULE, spaceAfter=6))
    story.append(Paragraph(
        f"Generated by Milk Vendor Smart Ledger  ·  {generated_on}  ·  Thank you for your business!",
        style_footer,
    ))

    # ── Build ──────────────────────────────────────────────────────────────────
    doc.build(story)
    return filepath

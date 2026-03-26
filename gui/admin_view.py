"""
myBay — Admin View (Sole Prop Business Backend)

Manages:
- Business entity info (DBA, EIN, permits)
- Expense tracking with receipt uploads
- Income logging with eBay listing import
- Mileage tracking (IRS standard rate)
- Business document storage
- Tax summary (Schedule C / quarterly estimates)
"""

import csv
import io
import os
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import date, datetime
from typing import Optional

try:
    import customtkinter as ctk
    from PIL import Image
except ImportError:
    raise

from core.paths import get_admin_files_dir, get_receipts_dir, get_documents_dir
from data.database import (
    Database, Expense, Income, MileageTrip, Document, TaxPayment
)

# Reuse app theme
COLORS = {
    "primary": "#2E8BFF",
    "primary_hover": "#1A6FD4",
    "secondary": "#FF4D6D",
    "success": "#34C77B",
    "success_hover": "#28A965",
    "warning": "#F4B740",
    "error": "#FF4D6D",
    "bg_dark": "#0D0D12",
    "bg_card": "#16161D",
    "bg_light": "#1E1E28",
    "border": "#2A2A35",
    "text": "#EEEEF0",
    "text_muted": "#8888A0",
}

import sys as _sys
_FONT_DISPLAY = "SF Pro Display" if _sys.platform == "darwin" else "Segoe UI"
_FONT_TEXT = "SF Pro Text" if _sys.platform == "darwin" else "Segoe UI"
FONT_HEADING = (_FONT_DISPLAY, 16, "bold")
FONT_BODY = (_FONT_TEXT, 14)
FONT_SMALL = (_FONT_TEXT, 12)
FONT_LABEL = (_FONT_TEXT, 13, "bold")

EXPENSE_CATEGORIES = [
    "inventory", "shipping", "ebay_fees", "supplies",
    "mileage", "storage", "phone_internet", "office", "other",
]

EXPENSE_LABELS = {
    "inventory": "Inventory / COGS",
    "shipping": "Shipping & Postage",
    "ebay_fees": "eBay / PayPal Fees",
    "supplies": "Packing Supplies",
    "mileage": "Mileage (manual $)",
    "storage": "Storage",
    "phone_internet": "Phone / Internet",
    "office": "Office Supplies",
    "other": "Other",
}

MILEAGE_PURPOSES = ["Sourcing", "Post Office", "Supplies Run", "Bank", "Other"]

DOC_TYPES = [
    ("sellers_permit", "CA Seller's Permit (CDTFA)"),
    ("ein_letter", "EIN Letter (IRS)"),
    ("dba_filing", "DBA / Fictitious Business Name"),
    ("business_tax_cert", "SD Business Tax Certificate"),
    ("bank_docs", "Bank Account Documents"),
    ("other", "Other Document"),
]

DOCS_DIR = get_admin_files_dir()
RECEIPTS_DIR = get_receipts_dir()
DOCUMENTS_DIR = get_documents_dir()


def _ensure_dirs():
    DOCS_DIR.mkdir(exist_ok=True)
    RECEIPTS_DIR.mkdir(exist_ok=True)
    DOCUMENTS_DIR.mkdir(exist_ok=True)


class AdminView:
    """Builds and manages the Admin tab UI within a parent frame."""

    def __init__(self, parent: ctk.CTkFrame, db: Database):
        self.parent = parent
        self.db = db
        _ensure_dirs()

        # Main admin frame
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")

        # Sub-navigation state
        self._current_section = None
        self._section_frames = {}

        self._build_ui()
        self._show_section("assistant")

    # ================================================================
    # Layout
    # ================================================================

    def _build_ui(self):
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)

        # Sub-nav bar
        nav = ctk.CTkFrame(self.frame, fg_color=COLORS["bg_card"], height=50, corner_radius=0)
        nav.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 2))

        sections = [
            ("assistant", "AI Assistant"),
            ("business_info", "Business"),
            ("expenses", "Expenses"),
            ("income", "Income"),
            ("mileage", "Mileage"),
            ("documents", "Docs"),
            ("tax", "Taxes"),
            ("export", "Export"),
        ]

        self._nav_buttons = {}
        for key, label in sections:
            btn = ctk.CTkButton(
                nav, text=label, width=110, height=34,
                fg_color=COLORS["bg_light"], hover_color=COLORS["border"],
                corner_radius=6,
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(side="left", padx=4, pady=8)
            self._nav_buttons[key] = btn

        # Content area
        self._content = ctk.CTkFrame(self.frame, fg_color="transparent")
        self._content.grid(row=1, column=0, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # Build each section
        self._build_assistant()
        self._build_business_info()
        self._build_expenses()
        self._build_income()
        self._build_mileage()
        self._build_documents()
        self._build_tax()
        self._build_export()

    def _show_section(self, key: str):
        if self._current_section == key:
            return
        # Hide current
        for k, f in self._section_frames.items():
            f.grid_forget()
        # Highlight nav button
        for k, btn in self._nav_buttons.items():
            btn.configure(fg_color=COLORS["primary"] if k == key else COLORS["bg_light"])
        # Show target
        self._section_frames[key].grid(row=0, column=0, sticky="nsew")
        self._current_section = key
        # Refresh data
        refresh = {
            "assistant": lambda: None,
            "business_info": self._refresh_business_info,
            "expenses": self._refresh_expenses,
            "income": self._refresh_income,
            "mileage": self._refresh_mileage,
            "documents": self._refresh_documents,
            "tax": self._refresh_tax,
            "export": lambda: None,
        }
        refresh.get(key, lambda: None)()

    # ================================================================
    # Helper: card frame
    # ================================================================

    def _card(self, parent, title: str = "", pad=15) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=10)
        card.pack(fill="x", padx=pad, pady=(0, 12))
        if title:
            ctk.CTkLabel(card, text=title, font=FONT_HEADING).pack(
                anchor="w", padx=15, pady=(12, 6))
        return card

    def _label_entry(self, parent, label: str, row: int, default: str = "",
                     show: str = None) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).grid(
            row=row, column=0, sticky="w", padx=(15, 5), pady=4)
        entry = ctk.CTkEntry(parent, width=300, fg_color=COLORS["bg_light"],
                             border_color=COLORS["border"])
        if show:
            entry.configure(show=show)
        entry.grid(row=row, column=1, sticky="w", padx=(0, 15), pady=4)
        if default:
            entry.insert(0, default)
        return entry

    # ================================================================
    # Section: AI Assistant
    # ================================================================

    def _build_assistant(self):
        frame = ctk.CTkFrame(self._content, fg_color="transparent")
        self._section_frames["assistant"] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        ctk.CTkLabel(
            hdr, text="AI Business Assistant",
            font=FONT_HEADING,
        ).pack(side="left")
        ctk.CTkLabel(
            hdr,
            text="Tell me what you bought, sold, or drove — I'll log it for you.",
            font=FONT_SMALL, text_color=COLORS["text_muted"],
        ).pack(side="left", padx=(15, 0))

        # Chat history area
        self._chat_display = ctk.CTkTextbox(
            frame, fg_color=COLORS["bg_card"], corner_radius=10,
            font=FONT_BODY, wrap="word", state="disabled",
            text_color=COLORS["text"],
        )
        self._chat_display.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)

        # Input row
        input_row = ctk.CTkFrame(frame, fg_color="transparent")
        input_row.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 12))
        input_row.grid_columnconfigure(0, weight=1)

        self._chat_entry = ctk.CTkEntry(
            input_row, placeholder_text='e.g. "drove 40 miles to post office, mailed a bike part for $40"',
            fg_color=COLORS["bg_light"], border_color=COLORS["border"],
            font=FONT_BODY, height=40,
        )
        self._chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._chat_entry.bind("<Return>", lambda e: self._send_chat())

        self._chat_send_btn = ctk.CTkButton(
            input_row, text="Send", width=80, height=40,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            command=self._send_chat,
        )
        self._chat_send_btn.grid(row=0, column=1)

        # Examples
        examples_frame = ctk.CTkFrame(frame, fg_color="transparent")
        examples_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 8))
        ctk.CTkLabel(
            examples_frame, text="Try:", font=FONT_SMALL,
            text_color=COLORS["text_muted"],
        ).pack(side="left")
        for example in [
            "spent $25 at goodwill on inventory",
            "drove 12 miles to the swap meet",
            "sold a vintage camera for $85 on ebay, $11 in fees",
        ]:
            ctk.CTkButton(
                examples_frame, text=example, height=26,
                fg_color=COLORS["bg_light"], hover_color=COLORS["border"],
                font=(_FONT_TEXT, 11),
                command=lambda t=example: self._fill_chat(t),
            ).pack(side="left", padx=3)

        # Seed welcome message
        self._chat_append("Assistant", "Hey! Tell me about any purchases, sales, or trips and I'll log them for you.")

    def _fill_chat(self, text: str):
        self._chat_entry.delete(0, "end")
        self._chat_entry.insert(0, text)

    def _chat_append(self, sender: str, message: str):
        self._chat_display.configure(state="normal")
        if self._chat_display.get("1.0", "end").strip():
            self._chat_display.insert("end", "\n\n")
        prefix = "You" if sender == "user" else "Assistant"
        self._chat_display.insert("end", f"{prefix}: {message}")
        self._chat_display.see("end")
        self._chat_display.configure(state="disabled")

    def _send_chat(self):
        message = self._chat_entry.get().strip()
        if not message:
            return

        self._chat_entry.delete(0, "end")
        self._chat_append("user", message)
        self._chat_append("assistant", "Thinking...")
        self._chat_send_btn.configure(state="disabled", text="...")

        # Run AI call in background thread
        def _run():
            try:
                from core.assistant import BusinessAssistant
                assistant = BusinessAssistant()
                result = assistant.parse_message(message)
            except Exception as exc:
                result = {
                    "reply": f"Error: {exc}",
                    "expenses": [], "income": [], "mileage": [],
                }
            # Process results on main thread
            self.frame.after(0, lambda: self._handle_ai_result(result))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _handle_ai_result(self, result: dict):
        self._chat_send_btn.configure(state="normal", text="Send")

        # Remove the "Thinking..." placeholder
        self._chat_display.configure(state="normal")
        content = self._chat_display.get("1.0", "end")
        placeholder = "\n\nAssistant: Thinking..."
        if content.rstrip().endswith("Assistant: Thinking..."):
            idx = content.rfind(placeholder)
            if idx >= 0:
                start_pos = f"1.0+{idx}c"
                self._chat_display.delete(start_pos, "end")
        self._chat_display.configure(state="disabled")

        entries_logged = []

        # Save expenses
        for exp_data in result.get("expenses", []):
            try:
                exp = Expense(
                    date=date.fromisoformat(exp_data["date"]),
                    category=exp_data["category"],
                    amount=float(exp_data["amount"]),
                    description=exp_data.get("description", ""),
                    vendor=exp_data.get("vendor", ""),
                )
                self.db.add_expense(exp)
                entries_logged.append(
                    f"Expense: ${exp.amount:.2f} ({exp.category})"
                )
            except (KeyError, ValueError) as e:
                entries_logged.append(f"Expense error: {e}")

        # Save income
        for inc_data in result.get("income", []):
            try:
                from data.database import Income as IncomeModel
                inc = IncomeModel(
                    date=date.fromisoformat(inc_data["date"]),
                    amount=float(inc_data["amount"]),
                    source=inc_data.get("source", "ebay"),
                    description=inc_data.get("description", ""),
                    platform_fees=float(inc_data.get("platform_fees", 0)),
                    shipping_cost=float(inc_data.get("shipping_cost", 0)),
                )
                self.db.add_income(inc)
                entries_logged.append(
                    f"Income: ${inc.amount:.2f} ({inc.source})"
                )
            except (KeyError, ValueError) as e:
                entries_logged.append(f"Income error: {e}")

        # Save mileage
        for mil_data in result.get("mileage", []):
            try:
                trip = MileageTrip(
                    date=date.fromisoformat(mil_data["date"]),
                    purpose=mil_data["purpose"],
                    miles=float(mil_data["miles"]),
                    destination=mil_data.get("destination", ""),
                )
                self.db.add_mileage(trip)
                ded = trip.miles * trip.rate_per_mile
                entries_logged.append(
                    f"Mileage: {trip.miles:.1f} mi (${ded:.2f} deduction)"
                )
            except (KeyError, ValueError) as e:
                entries_logged.append(f"Mileage error: {e}")

        # Build response
        reply = result.get("reply", "")
        if entries_logged:
            reply += "\n\nLogged:\n" + "\n".join(f"  - {e}" for e in entries_logged)

        self._chat_append("assistant", reply)

    # ================================================================
    # Section: Business Info
    # ================================================================

    def _build_business_info(self):
        scroll = ctk.CTkScrollableFrame(self._content, fg_color="transparent")
        self._section_frames["business_info"] = scroll

        # Entity card
        card = self._card(scroll, "Business Entity")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=5, pady=(0, 10))

        self._biz_fields = {}
        fields = [
            ("business_name", "Business Name"),
            ("dba_name", "DBA Name"),
            ("owner_name", "Owner Name"),
            ("business_address", "Address"),
            ("business_phone", "Phone"),
            ("business_email", "Email"),
        ]
        for i, (key, label) in enumerate(fields):
            self._biz_fields[key] = self._label_entry(inner, label, i)

        # Tax IDs
        card2 = self._card(scroll, "Tax IDs & Permits")
        inner2 = ctk.CTkFrame(card2, fg_color="transparent")
        inner2.pack(fill="x", padx=5, pady=(0, 10))

        tax_fields = [
            ("ein", "EIN"),
            ("cdtfa_permit", "CA Seller's Permit #"),
            ("cdtfa_expiry", "Permit Expiry (YYYY-MM-DD)"),
            ("sd_cert", "SD Business Tax Cert #"),
            ("sd_cert_expiry", "Cert Expiry (YYYY-MM-DD)"),
        ]
        for i, (key, label) in enumerate(tax_fields):
            self._biz_fields[key] = self._label_entry(inner2, label, i)

        # Banking
        card3 = self._card(scroll, "Business Banking")
        inner3 = ctk.CTkFrame(card3, fg_color="transparent")
        inner3.pack(fill="x", padx=5, pady=(0, 10))

        bank_fields = [
            ("bank_name", "Bank Name"),
            ("bank_account_last4", "Account (last 4)"),
            ("bank_routing_last4", "Routing (last 4)"),
        ]
        for i, (key, label) in enumerate(bank_fields):
            show = "*" if "account" in key or "routing" in key else None
            self._biz_fields[key] = self._label_entry(inner3, label, i, show=show)

        # Save button
        ctk.CTkButton(
            scroll, text="Save Business Info", width=200,
            fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
            command=self._save_business_info,
        ).pack(pady=(5, 20))

    def _refresh_business_info(self):
        info = self.db.get_all_business_info()
        for key, entry in self._biz_fields.items():
            entry.delete(0, "end")
            if key in info and info[key]:
                entry.insert(0, info[key])

    def _save_business_info(self):
        for key, entry in self._biz_fields.items():
            self.db.set_business_info(key, entry.get().strip())
        messagebox.showinfo("Saved", "Business info saved.")

    # ================================================================
    # Section: Expenses
    # ================================================================

    def _build_expenses(self):
        scroll = ctk.CTkScrollableFrame(self._content, fg_color="transparent")
        self._section_frames["expenses"] = scroll

        # Add expense form
        card = self._card(scroll, "Add Expense")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=15, pady=(0, 12))

        # Row 1: date, category, amount
        r1 = ctk.CTkFrame(form, fg_color="transparent")
        r1.pack(fill="x", pady=4)

        ctk.CTkLabel(r1, text="Date:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._exp_date = ctk.CTkEntry(r1, width=120, fg_color=COLORS["bg_light"],
                                       border_color=COLORS["border"])
        self._exp_date.pack(side="left", padx=(4, 12))
        self._exp_date.insert(0, date.today().isoformat())

        ctk.CTkLabel(r1, text="Category:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._exp_cat = ctk.CTkOptionMenu(
            r1, width=180, values=[EXPENSE_LABELS[c] for c in EXPENSE_CATEGORIES],
            fg_color=COLORS["bg_light"], button_color=COLORS["border"],
        )
        self._exp_cat.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(r1, text="Amount $:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._exp_amount = ctk.CTkEntry(r1, width=100, fg_color=COLORS["bg_light"],
                                         border_color=COLORS["border"])
        self._exp_amount.pack(side="left", padx=4)

        # Row 2: vendor, description
        r2 = ctk.CTkFrame(form, fg_color="transparent")
        r2.pack(fill="x", pady=4)

        ctk.CTkLabel(r2, text="Vendor:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._exp_vendor = ctk.CTkEntry(r2, width=180, fg_color=COLORS["bg_light"],
                                         border_color=COLORS["border"],
                                         placeholder_text="e.g. Goodwill, USPS")
        self._exp_vendor.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(r2, text="Description:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._exp_desc = ctk.CTkEntry(r2, width=280, fg_color=COLORS["bg_light"],
                                       border_color=COLORS["border"])
        self._exp_desc.pack(side="left", padx=4)

        # Row 3: receipt upload + save
        r3 = ctk.CTkFrame(form, fg_color="transparent")
        r3.pack(fill="x", pady=4)

        self._exp_receipt_path = ""
        self._exp_receipt_label = ctk.CTkLabel(r3, text="No receipt",
                                                font=FONT_SMALL,
                                                text_color=COLORS["text_muted"])
        self._exp_receipt_label.pack(side="left")

        ctk.CTkButton(
            r3, text="Attach Receipt", width=120,
            fg_color=COLORS["bg_light"], hover_color=COLORS["border"],
            command=self._attach_receipt,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            r3, text="Save Expense", width=120,
            fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
            command=self._save_expense,
        ).pack(side="right", padx=4)

        # Summary card
        self._exp_summary_card = self._card(scroll, "Expense Summary")
        self._exp_summary_content = ctk.CTkFrame(
            self._exp_summary_card, fg_color="transparent")
        self._exp_summary_content.pack(fill="x", padx=15, pady=(0, 12))

        # Expense list
        self._exp_list_card = self._card(scroll, "Recent Expenses")
        self._exp_list_content = ctk.CTkFrame(
            self._exp_list_card, fg_color="transparent")
        self._exp_list_content.pack(fill="x", padx=10, pady=(0, 10))

    def _attach_receipt(self):
        path = filedialog.askopenfilename(
            title="Select Receipt Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.heic *.pdf"),
                       ("All files", "*.*")]
        )
        if path:
            # Copy to receipts dir
            src = Path(path)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = RECEIPTS_DIR / f"{ts}_{src.name}"
            shutil.copy2(src, dest)
            self._exp_receipt_path = str(dest)
            self._exp_receipt_label.configure(text=f"Attached: {src.name}")

    def _save_expense(self):
        try:
            amount = float(self._exp_amount.get())
        except ValueError:
            messagebox.showerror("Error", "Enter a valid amount.")
            return

        if amount <= 0:
            messagebox.showerror("Error", "Amount must be greater than $0.")
            return
        if amount > 100_000:
            messagebox.showerror("Error", "Amount seems too high. Please double-check.")
            return

        try:
            exp_date = date.fromisoformat(self._exp_date.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Enter date as YYYY-MM-DD.")
            return

        # Map label back to category key
        selected_label = self._exp_cat.get()
        category = "other"
        for k, v in EXPENSE_LABELS.items():
            if v == selected_label:
                category = k
                break

        expense = Expense(
            date=exp_date,
            category=category,
            amount=amount,
            description=self._exp_desc.get().strip(),
            vendor=self._exp_vendor.get().strip(),
            receipt_path=self._exp_receipt_path,
        )
        self.db.add_expense(expense)

        # Reset form
        self._exp_amount.delete(0, "end")
        self._exp_desc.delete(0, "end")
        self._exp_vendor.delete(0, "end")
        self._exp_receipt_path = ""
        self._exp_receipt_label.configure(text="No receipt")

        self._refresh_expenses()

    def _refresh_expenses(self):
        year_start = date(date.today().year, 1, 1)

        # Summary
        for w in self._exp_summary_content.winfo_children():
            w.destroy()
        totals = self.db.get_expense_totals(year_start)
        grand = 0.0
        for cat, total in totals.items():
            label = EXPENSE_LABELS.get(cat, cat.title())
            ctk.CTkLabel(
                self._exp_summary_content,
                text=f"{label}: ${total:,.2f}",
                font=FONT_SMALL,
            ).pack(anchor="w", padx=5, pady=1)
            grand += total
        ctk.CTkLabel(
            self._exp_summary_content,
            text=f"Total YTD: ${grand:,.2f}",
            font=FONT_LABEL, text_color=COLORS["warning"],
        ).pack(anchor="w", padx=5, pady=(6, 2))

        # List
        for w in self._exp_list_content.winfo_children():
            w.destroy()
        expenses = self.db.get_expenses(limit=50)
        for exp in expenses:
            row = ctk.CTkFrame(self._exp_list_content, fg_color=COLORS["bg_light"],
                               corner_radius=6, height=36)
            row.pack(fill="x", pady=2, padx=2)
            label_text = EXPENSE_LABELS.get(exp.category, exp.category)
            info = f"{exp.date}  |  {label_text}  |  {exp.vendor or '—'}  |  ${exp.amount:,.2f}"
            if exp.description:
                info += f"  |  {exp.description}"
            ctk.CTkLabel(row, text=info, font=FONT_SMALL).pack(
                side="left", padx=10, pady=6)
            if exp.receipt_path:
                ctk.CTkLabel(row, text="[receipt]", font=FONT_SMALL,
                             text_color=COLORS["success"]).pack(side="left", padx=4)
            ctk.CTkButton(
                row, text="X", width=28, height=24,
                fg_color=COLORS["error"], hover_color="#CC3355",
                command=lambda eid=exp.id: self._delete_expense(eid),
            ).pack(side="right", padx=6, pady=4)

    def _delete_expense(self, expense_id: int):
        if messagebox.askyesno("Delete", "Delete this expense?"):
            self.db.delete_expense(expense_id)
            self._refresh_expenses()

    # ================================================================
    # Section: Income
    # ================================================================

    def _build_income(self):
        scroll = ctk.CTkScrollableFrame(self._content, fg_color="transparent")
        self._section_frames["income"] = scroll

        # Add income form
        card = self._card(scroll, "Add Income")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=15, pady=(0, 12))

        r1 = ctk.CTkFrame(form, fg_color="transparent")
        r1.pack(fill="x", pady=4)

        ctk.CTkLabel(r1, text="Date:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._inc_date = ctk.CTkEntry(r1, width=120, fg_color=COLORS["bg_light"],
                                       border_color=COLORS["border"])
        self._inc_date.pack(side="left", padx=(4, 12))
        self._inc_date.insert(0, date.today().isoformat())

        ctk.CTkLabel(r1, text="Source:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._inc_source = ctk.CTkOptionMenu(
            r1, width=120, values=["eBay", "Cash", "Other"],
            fg_color=COLORS["bg_light"], button_color=COLORS["border"],
        )
        self._inc_source.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(r1, text="Gross $:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._inc_amount = ctk.CTkEntry(r1, width=100, fg_color=COLORS["bg_light"],
                                         border_color=COLORS["border"])
        self._inc_amount.pack(side="left", padx=4)

        r2 = ctk.CTkFrame(form, fg_color="transparent")
        r2.pack(fill="x", pady=4)

        ctk.CTkLabel(r2, text="Fees $:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._inc_fees = ctk.CTkEntry(r2, width=90, fg_color=COLORS["bg_light"],
                                       border_color=COLORS["border"])
        self._inc_fees.pack(side="left", padx=(4, 12))
        self._inc_fees.insert(0, "0")

        ctk.CTkLabel(r2, text="Shipping $:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._inc_shipping = ctk.CTkEntry(r2, width=90, fg_color=COLORS["bg_light"],
                                           border_color=COLORS["border"])
        self._inc_shipping.pack(side="left", padx=(4, 12))
        self._inc_shipping.insert(0, "0")

        ctk.CTkLabel(r2, text="Sales Tax $:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._inc_sales_tax = ctk.CTkEntry(r2, width=90, fg_color=COLORS["bg_light"],
                                            border_color=COLORS["border"])
        self._inc_sales_tax.pack(side="left", padx=(4, 12))
        self._inc_sales_tax.insert(0, "0")

        ctk.CTkLabel(r2, text="Description:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._inc_desc = ctk.CTkEntry(r2, width=200, fg_color=COLORS["bg_light"],
                                       border_color=COLORS["border"])
        self._inc_desc.pack(side="left", padx=4)

        r3 = ctk.CTkFrame(form, fg_color="transparent")
        r3.pack(fill="x", pady=4)

        ctk.CTkButton(
            r3, text="Save Income", width=120,
            fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
            command=self._save_income,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            r3, text="Import Sold Listings", width=160,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            command=self._import_sold_listings,
        ).pack(side="left", padx=12)

        ctk.CTkButton(
            r3, text="Log Return/Refund", width=140,
            fg_color=COLORS["warning"], hover_color="#D9A030",
            command=self._log_return_refund,
        ).pack(side="left", padx=4)

        # Summary
        self._inc_summary_card = self._card(scroll, "Income Summary (YTD)")
        self._inc_summary_content = ctk.CTkFrame(
            self._inc_summary_card, fg_color="transparent")
        self._inc_summary_content.pack(fill="x", padx=15, pady=(0, 12))

        # List
        self._inc_list_card = self._card(scroll, "Recent Income")
        self._inc_list_content = ctk.CTkFrame(
            self._inc_list_card, fg_color="transparent")
        self._inc_list_content.pack(fill="x", padx=10, pady=(0, 10))

    def _save_income(self):
        try:
            amount = float(self._inc_amount.get())
        except ValueError:
            messagebox.showerror("Error", "Enter a valid amount.")
            return
        try:
            inc_date = date.fromisoformat(self._inc_date.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Enter date as YYYY-MM-DD.")
            return

        fees = float(self._inc_fees.get() or 0)
        shipping = float(self._inc_shipping.get() or 0)
        sales_tax = float(self._inc_sales_tax.get() or 0)

        income = Income(
            date=inc_date,
            amount=amount,
            source=self._inc_source.get().lower(),
            description=self._inc_desc.get().strip(),
            platform_fees=fees,
            shipping_cost=shipping,
            sales_tax_collected=sales_tax,
        )
        self.db.add_income(income)

        self._inc_amount.delete(0, "end")
        self._inc_desc.delete(0, "end")
        self._inc_fees.delete(0, "end")
        self._inc_fees.insert(0, "0")
        self._inc_shipping.delete(0, "end")
        self._inc_shipping.insert(0, "0")
        self._inc_sales_tax.delete(0, "end")
        self._inc_sales_tax.insert(0, "0")

        self._refresh_income()

    def _import_sold_listings(self):
        """Import SOLD listings that aren't already in the income table."""
        imported_skus = self.db.get_imported_skus()

        # Also build a set of (title, date) from existing income to catch
        # listings with empty/missing SKUs that were already imported.
        existing_income = self.db.get_income(limit=5000)
        imported_keys = {
            (inc.description, inc.date.isoformat()) for inc in existing_income
        }

        sold = []
        for l in self.db.get_recent_listings(limit=500):
            if l.status != "SOLD":
                continue
            # Skip if already imported by SKU
            if l.sku and l.sku in imported_skus:
                continue
            # Skip if already imported by title + date (catches empty-SKU dupes)
            sale_date = l.sold_at.date() if l.sold_at else date.today()
            if (l.title, sale_date.isoformat()) in imported_keys:
                continue
            sold.append(l)

        if not sold:
            messagebox.showinfo("Import", "No new sold listings to import.")
            return

        count = 0
        for listing in sold:
            income = Income(
                date=listing.sold_at.date() if listing.sold_at else date.today(),
                amount=listing.sold_price or listing.price or 0.0,
                source="ebay",
                description=listing.title,
                listing_sku=listing.sku,
            )
            self.db.add_income(income)
            count += 1

        messagebox.showinfo("Imported", f"Imported {count} sold listings as income.")
        self._refresh_income()

    def _log_return_refund(self):
        """Show a dialog to log a return/refund as negative income."""
        dialog = ctk.CTkToplevel(self.parent)
        dialog.title("Log Return / Refund")
        dialog.geometry("400x280")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self.parent)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Log Return / Refund", font=FONT_HEADING).pack(
            anchor="w", padx=20, pady=(15, 10))

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="x", padx=20)

        ctk.CTkLabel(form, text="Date:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).grid(row=0, column=0, sticky="w", pady=4)
        refund_date = ctk.CTkEntry(form, width=140, fg_color=COLORS["bg_light"],
                                    border_color=COLORS["border"])
        refund_date.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=4)
        refund_date.insert(0, date.today().isoformat())

        ctk.CTkLabel(form, text="Amount $:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).grid(row=1, column=0, sticky="w", pady=4)
        refund_amount = ctk.CTkEntry(form, width=140, fg_color=COLORS["bg_light"],
                                      border_color=COLORS["border"],
                                      placeholder_text="Enter as positive number")
        refund_amount.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=4)

        ctk.CTkLabel(form, text="Description:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).grid(row=2, column=0, sticky="w", pady=4)
        refund_desc = ctk.CTkEntry(form, width=220, fg_color=COLORS["bg_light"],
                                    border_color=COLORS["border"],
                                    placeholder_text="e.g. Buyer return - item #123")
        refund_desc.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        ctk.CTkLabel(
            dialog, text="Amount will be saved as negative income.",
            font=FONT_SMALL, text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=20, pady=(8, 0))

        def _save_refund():
            try:
                amt = float(refund_amount.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Enter a valid amount.", parent=dialog)
                return
            if amt <= 0:
                messagebox.showerror("Error", "Enter a positive amount (it will be stored as negative).",
                                     parent=dialog)
                return
            try:
                rdate = date.fromisoformat(refund_date.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Enter date as YYYY-MM-DD.", parent=dialog)
                return

            income = Income(
                date=rdate,
                amount=-amt,
                source="refund",
                description=refund_desc.get().strip() or "Return/Refund",
            )
            self.db.add_income(income)
            dialog.destroy()
            self._refresh_income()

        ctk.CTkButton(
            dialog, text="Save Refund", width=140,
            fg_color=COLORS["warning"], hover_color="#D9A030",
            command=_save_refund,
        ).pack(pady=15)

    def _refresh_income(self):
        year_start = date(date.today().year, 1, 1)

        # Summary
        for w in self._inc_summary_content.winfo_children():
            w.destroy()
        totals = self.db.get_income_total(year_start)
        for label, key in [("Gross Income", "gross"), ("Platform Fees", "fees"),
                           ("Shipping Costs", "shipping"),
                           ("Sales Tax Collected", "sales_tax"),
                           ("Net Income", "net")]:
            color = COLORS["warning"] if key == "net" else COLORS["text"]
            ctk.CTkLabel(
                self._inc_summary_content,
                text=f"{label}: ${totals[key]:,.2f}",
                font=FONT_SMALL if key != "net" else FONT_LABEL,
                text_color=color,
            ).pack(anchor="w", padx=5, pady=1)

        # List
        for w in self._inc_list_content.winfo_children():
            w.destroy()
        entries = self.db.get_income(limit=50)
        for inc in entries:
            row = ctk.CTkFrame(self._inc_list_content, fg_color=COLORS["bg_light"],
                               corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)
            info = f"{inc.date}  |  {inc.source}  |  ${inc.amount:,.2f}"
            if inc.description:
                info += f"  |  {inc.description[:40]}"
            if inc.net_amount and inc.net_amount != inc.amount:
                info += f"  (net ${inc.net_amount:,.2f})"
            ctk.CTkLabel(row, text=info, font=FONT_SMALL).pack(
                side="left", padx=10, pady=6)
            ctk.CTkButton(
                row, text="X", width=28, height=24,
                fg_color=COLORS["error"], hover_color="#CC3355",
                command=lambda iid=inc.id: self._delete_income(iid),
            ).pack(side="right", padx=6, pady=4)

    def _delete_income(self, income_id: int):
        if messagebox.askyesno("Delete", "Delete this income entry?"):
            self.db.delete_income(income_id)
            self._refresh_income()

    # ================================================================
    # Section: Mileage
    # ================================================================

    def _build_mileage(self):
        scroll = ctk.CTkScrollableFrame(self._content, fg_color="transparent")
        self._section_frames["mileage"] = scroll

        card = self._card(scroll, "Log Trip")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=15, pady=(0, 12))

        r1 = ctk.CTkFrame(form, fg_color="transparent")
        r1.pack(fill="x", pady=4)

        ctk.CTkLabel(r1, text="Date:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._mil_date = ctk.CTkEntry(r1, width=120, fg_color=COLORS["bg_light"],
                                       border_color=COLORS["border"])
        self._mil_date.pack(side="left", padx=(4, 12))
        self._mil_date.insert(0, date.today().isoformat())

        ctk.CTkLabel(r1, text="Purpose:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._mil_purpose = ctk.CTkOptionMenu(
            r1, width=140, values=MILEAGE_PURPOSES,
            fg_color=COLORS["bg_light"], button_color=COLORS["border"],
        )
        self._mil_purpose.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(r1, text="Miles:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._mil_miles = ctk.CTkEntry(r1, width=80, fg_color=COLORS["bg_light"],
                                        border_color=COLORS["border"])
        self._mil_miles.pack(side="left", padx=4)

        r2 = ctk.CTkFrame(form, fg_color="transparent")
        r2.pack(fill="x", pady=4)

        ctk.CTkLabel(r2, text="Destination:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._mil_dest = ctk.CTkEntry(r2, width=300, fg_color=COLORS["bg_light"],
                                       border_color=COLORS["border"],
                                       placeholder_text="e.g. Goodwill on El Cajon Blvd")
        self._mil_dest.pack(side="left", padx=(4, 12))

        ctk.CTkButton(
            r2, text="Log Trip", width=100,
            fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
            command=self._save_mileage,
        ).pack(side="right", padx=4)

        # IRS rate display with edit
        rate_frame = ctk.CTkFrame(form, fg_color="transparent")
        rate_frame.pack(fill="x", pady=(4, 0))

        current_year = date.today().year
        current_rate = self.db.get_mileage_rate(current_year)
        self._mil_rate_label = ctk.CTkLabel(
            rate_frame,
            text=f"IRS Rate ({current_year}): ${current_rate:.3f}/mile",
            font=FONT_SMALL, text_color=COLORS["text_muted"],
        )
        self._mil_rate_label.pack(side="left")

        self._mil_rate_entry = ctk.CTkEntry(
            rate_frame, width=70, fg_color=COLORS["bg_light"],
            border_color=COLORS["border"], font=FONT_SMALL,
        )
        self._mil_rate_entry.pack(side="left", padx=(12, 4))
        self._mil_rate_entry.insert(0, f"{current_rate:.3f}")

        ctk.CTkButton(
            rate_frame, text="Update Rate", width=90, height=26,
            fg_color=COLORS["bg_light"], hover_color=COLORS["border"],
            font=FONT_SMALL,
            command=self._update_mileage_rate,
        ).pack(side="left", padx=4)

        # Summary
        self._mil_summary_card = self._card(scroll, "Mileage Summary (YTD)")
        self._mil_summary_content = ctk.CTkFrame(
            self._mil_summary_card, fg_color="transparent")
        self._mil_summary_content.pack(fill="x", padx=15, pady=(0, 12))

        # List
        self._mil_list_card = self._card(scroll, "Trip Log")
        self._mil_list_content = ctk.CTkFrame(
            self._mil_list_card, fg_color="transparent")
        self._mil_list_content.pack(fill="x", padx=10, pady=(0, 10))

    def _update_mileage_rate(self):
        try:
            rate = float(self._mil_rate_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Enter a valid rate (e.g. 0.70).")
            return
        if rate <= 0 or rate > 5.0:
            messagebox.showerror("Error", "Rate must be between $0.001 and $5.00.")
            return
        current_year = date.today().year
        self.db.set_mileage_rate(current_year, rate)
        self._mil_rate_label.configure(
            text=f"IRS Rate ({current_year}): ${rate:.3f}/mile")
        messagebox.showinfo("Saved", f"Mileage rate for {current_year} set to ${rate:.3f}/mile.")

    def _save_mileage(self):
        try:
            miles = float(self._mil_miles.get())
        except ValueError:
            messagebox.showerror("Error", "Enter valid miles.")
            return

        if miles <= 0:
            messagebox.showerror("Error", "Miles must be greater than 0.")
            return
        if miles > 500:
            if not messagebox.askyesno(
                "Confirm", f"{miles:.0f} miles seems high for a single trip. Save anyway?"
            ):
                return

        try:
            trip_date = date.fromisoformat(self._mil_date.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Enter date as YYYY-MM-DD.")
            return

        trip = MileageTrip(
            date=trip_date,
            purpose=self._mil_purpose.get(),
            miles=miles,
            destination=self._mil_dest.get().strip(),
            rate_per_mile=self.db.get_mileage_rate(trip_date.year),
        )
        self.db.add_mileage(trip)

        self._mil_miles.delete(0, "end")
        self._mil_dest.delete(0, "end")
        self._refresh_mileage()

    def _refresh_mileage(self):
        year_start = date(date.today().year, 1, 1)

        for w in self._mil_summary_content.winfo_children():
            w.destroy()
        totals = self.db.get_mileage_totals(year_start)
        ctk.CTkLabel(
            self._mil_summary_content,
            text=f"Total Miles: {totals['total_miles']:,.1f}",
            font=FONT_SMALL,
        ).pack(anchor="w", padx=5, pady=1)
        ctk.CTkLabel(
            self._mil_summary_content,
            text=f"Total Deduction: ${totals['total_deduction']:,.2f}",
            font=FONT_LABEL, text_color=COLORS["success"],
        ).pack(anchor="w", padx=5, pady=1)

        for w in self._mil_list_content.winfo_children():
            w.destroy()
        trips = self.db.get_mileage(limit=50)
        for trip in trips:
            row = ctk.CTkFrame(self._mil_list_content, fg_color=COLORS["bg_light"],
                               corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)
            ded = trip.miles * trip.rate_per_mile
            info = f"{trip.date}  |  {trip.purpose}  |  {trip.destination or '—'}  |  {trip.miles:.1f} mi  |  ${ded:.2f}"
            ctk.CTkLabel(row, text=info, font=FONT_SMALL).pack(
                side="left", padx=10, pady=6)
            ctk.CTkButton(
                row, text="X", width=28, height=24,
                fg_color=COLORS["error"], hover_color="#CC3355",
                command=lambda tid=trip.id: self._delete_mileage(tid),
            ).pack(side="right", padx=6, pady=4)

    def _delete_mileage(self, trip_id: int):
        if messagebox.askyesno("Delete", "Delete this trip?"):
            self.db.delete_mileage(trip_id)
            self._refresh_mileage()

    # ================================================================
    # Section: Documents
    # ================================================================

    def _build_documents(self):
        scroll = ctk.CTkScrollableFrame(self._content, fg_color="transparent")
        self._section_frames["documents"] = scroll

        # Upload card
        card = self._card(scroll, "Upload Document")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=15, pady=(0, 12))

        r1 = ctk.CTkFrame(form, fg_color="transparent")
        r1.pack(fill="x", pady=4)

        ctk.CTkLabel(r1, text="Type:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._doc_type = ctk.CTkOptionMenu(
            r1, width=240, values=[label for _, label in DOC_TYPES],
            fg_color=COLORS["bg_light"], button_color=COLORS["border"],
        )
        self._doc_type.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(r1, text="Name:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._doc_name = ctk.CTkEntry(r1, width=200, fg_color=COLORS["bg_light"],
                                       border_color=COLORS["border"],
                                       placeholder_text="Document name")
        self._doc_name.pack(side="left", padx=4)

        r2 = ctk.CTkFrame(form, fg_color="transparent")
        r2.pack(fill="x", pady=4)

        ctk.CTkLabel(r2, text="Expiry:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._doc_expiry = ctk.CTkEntry(r2, width=130, fg_color=COLORS["bg_light"],
                                         border_color=COLORS["border"],
                                         placeholder_text="YYYY-MM-DD (optional)")
        self._doc_expiry.pack(side="left", padx=(4, 12))

        self._doc_file_path = ""
        self._doc_file_label = ctk.CTkLabel(r2, text="No file selected",
                                             font=FONT_SMALL,
                                             text_color=COLORS["text_muted"])
        self._doc_file_label.pack(side="left", padx=4)

        ctk.CTkButton(
            r2, text="Choose File", width=100,
            fg_color=COLORS["bg_light"], hover_color=COLORS["border"],
            command=self._choose_doc_file,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            r2, text="Upload", width=80,
            fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
            command=self._save_document,
        ).pack(side="right", padx=4)

        # Document grid
        self._doc_grid_card = self._card(scroll, "Stored Documents")
        self._doc_grid_content = ctk.CTkFrame(
            self._doc_grid_card, fg_color="transparent")
        self._doc_grid_content.pack(fill="x", padx=10, pady=(0, 10))

    def _choose_doc_file(self):
        path = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[("Images & PDFs", "*.png *.jpg *.jpeg *.pdf *.heic"),
                       ("All files", "*.*")]
        )
        if path:
            src = Path(path)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = DOCUMENTS_DIR / f"{ts}_{src.name}"
            shutil.copy2(src, dest)
            self._doc_file_path = str(dest)
            self._doc_file_label.configure(text=f"Selected: {src.name}")

    def _save_document(self):
        name = self._doc_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Enter a document name.")
            return
        if not self._doc_file_path:
            messagebox.showerror("Error", "Choose a file to upload.")
            return

        # Map label back to key
        selected_label = self._doc_type.get()
        doc_type = "other"
        for k, v in DOC_TYPES:
            if v == selected_label:
                doc_type = k
                break

        expiry = None
        exp_str = self._doc_expiry.get().strip()
        if exp_str:
            try:
                expiry = date.fromisoformat(exp_str)
            except ValueError:
                messagebox.showerror("Error", "Expiry must be YYYY-MM-DD.")
                return

        doc = Document(
            doc_type=doc_type,
            name=name,
            file_path=self._doc_file_path,
            expiry_date=expiry,
        )
        self.db.add_document(doc)

        self._doc_name.delete(0, "end")
        self._doc_expiry.delete(0, "end")
        self._doc_file_path = ""
        self._doc_file_label.configure(text="No file selected")
        self._refresh_documents()

    def _refresh_documents(self):
        for w in self._doc_grid_content.winfo_children():
            w.destroy()

        docs = self.db.get_documents()
        if not docs:
            ctk.CTkLabel(
                self._doc_grid_content,
                text="No documents uploaded yet.",
                font=FONT_SMALL, text_color=COLORS["text_muted"],
            ).pack(anchor="w", padx=10, pady=10)
            return

        for doc in docs:
            row = ctk.CTkFrame(self._doc_grid_content, fg_color=COLORS["bg_light"],
                               corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)

            type_label = doc.doc_type
            for k, v in DOC_TYPES:
                if k == doc.doc_type:
                    type_label = v
                    break

            info = f"{type_label}  |  {doc.name}"
            if doc.expiry_date:
                days_left = (doc.expiry_date - date.today()).days
                if days_left < 0:
                    info += f"  |  EXPIRED"
                elif days_left < 30:
                    info += f"  |  Expires in {days_left}d"
                else:
                    info += f"  |  Exp: {doc.expiry_date}"

            ctk.CTkLabel(row, text=info, font=FONT_SMALL).pack(
                side="left", padx=10, pady=6)

            if doc.file_path and Path(doc.file_path).exists():
                ctk.CTkButton(
                    row, text="Open", width=50, height=24,
                    fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                    command=lambda p=doc.file_path: self._open_file(p),
                ).pack(side="right", padx=4, pady=4)

            ctk.CTkButton(
                row, text="X", width=28, height=24,
                fg_color=COLORS["error"], hover_color="#CC3355",
                command=lambda did=doc.id: self._delete_document(did),
            ).pack(side="right", padx=4, pady=4)

    def _open_file(self, path: str):
        import subprocess
        subprocess.Popen(["open", path])

    def _delete_document(self, doc_id: int):
        if messagebox.askyesno("Delete", "Delete this document?"):
            # Find the file path before removing the DB row
            docs = self.db.get_documents()
            file_path = None
            for doc in docs:
                if doc.id == doc_id and doc.file_path:
                    file_path = doc.file_path
                    break

            self.db.delete_document(doc_id)

            # Clean up the actual file from disk
            if file_path:
                try:
                    p = Path(file_path)
                    if p.exists():
                        p.unlink()
                except Exception as e:
                    print(f"Warning: could not delete file {file_path}: {e}")

            self._refresh_documents()

    # ================================================================
    # Section: Tax Summary
    # ================================================================

    def _build_tax(self):
        scroll = ctk.CTkScrollableFrame(self._content, fg_color="transparent")
        self._section_frames["tax"] = scroll

        # Year selector
        yr_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        yr_frame.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(yr_frame, text="Tax Year:", font=FONT_LABEL).pack(side="left")
        current_year = date.today().year
        self._tax_year = ctk.CTkOptionMenu(
            yr_frame, width=100,
            values=[str(y) for y in range(current_year, current_year - 3, -1)],
            fg_color=COLORS["bg_light"], button_color=COLORS["border"],
            command=lambda _: self._refresh_tax(),
        )
        self._tax_year.pack(side="left", padx=8)

        # Home Office setting
        ho_card = self._card(scroll, "Home Office Deduction")
        ho_inner = ctk.CTkFrame(ho_card, fg_color="transparent")
        ho_inner.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(ho_inner, text="Home Office (sq ft):", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._ho_sqft_entry = ctk.CTkEntry(
            ho_inner, width=80, fg_color=COLORS["bg_light"],
            border_color=COLORS["border"], font=FONT_SMALL,
        )
        self._ho_sqft_entry.pack(side="left", padx=(8, 4))
        saved_sqft = self.db.get_setting("home_office_sqft", "0") or "0"
        self._ho_sqft_entry.insert(0, saved_sqft)

        ctk.CTkButton(
            ho_inner, text="Save", width=60, height=26,
            fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
            font=FONT_SMALL,
            command=self._save_home_office,
        ).pack(side="left", padx=4)

        self._ho_info_label = ctk.CTkLabel(
            ho_inner, text="", font=FONT_SMALL, text_color=COLORS["text_muted"],
        )
        self._ho_info_label.pack(side="left", padx=(12, 0))
        sqft = float(saved_sqft) if saved_sqft else 0
        if sqft > 0:
            ded = min(sqft * 5.0, 1500.0)
            self._ho_info_label.configure(
                text=f"Simplified method: {sqft:.0f} sq ft x $5 = ${ded:,.2f}/yr (max $1,500)")

        # Schedule C card
        self._tax_schedule_c = self._card(scroll, "Schedule C Summary (P&L)")
        self._tax_sc_content = ctk.CTkFrame(
            self._tax_schedule_c, fg_color="transparent")
        self._tax_sc_content.pack(fill="x", padx=15, pady=(0, 12))

        # Quarterly payments card
        self._tax_quarterly = self._card(scroll, "Quarterly Estimated Taxes")
        self._tax_q_content = ctk.CTkFrame(
            self._tax_quarterly, fg_color="transparent")
        self._tax_q_content.pack(fill="x", padx=15, pady=(0, 12))

        # Init quarters button
        ctk.CTkButton(
            scroll, text="Initialize Quarterly Reminders", width=220,
            fg_color=COLORS["bg_light"], hover_color=COLORS["border"],
            command=self._init_quarterly_payments,
        ).pack(pady=(0, 15))

        # 1099-K Reconciliation card
        recon_card = self._card(scroll, "1099-K Reconciliation")
        recon_inner = ctk.CTkFrame(recon_card, fg_color="transparent")
        recon_inner.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(recon_inner, text="1099-K Gross Amount $:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._1099k_entry = ctk.CTkEntry(
            recon_inner, width=120, fg_color=COLORS["bg_light"],
            border_color=COLORS["border"], font=FONT_SMALL,
            placeholder_text="e.g. 12500.00",
        )
        self._1099k_entry.pack(side="left", padx=(8, 4))

        ctk.CTkButton(
            recon_inner, text="Compare", width=80, height=26,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=FONT_SMALL,
            command=self._compare_1099k,
        ).pack(side="left", padx=4)

        self._1099k_result = ctk.CTkFrame(recon_card, fg_color="transparent")
        self._1099k_result.pack(fill="x", padx=15, pady=(0, 10))

    def _save_home_office(self):
        val = self._ho_sqft_entry.get().strip()
        try:
            sqft = float(val) if val else 0
        except ValueError:
            messagebox.showerror("Error", "Enter a valid number for square footage.")
            return
        if sqft < 0 or sqft > 1000:
            messagebox.showerror("Error", "Square footage must be between 0 and 1000.")
            return
        self.db.set_setting("home_office_sqft", str(sqft))
        if sqft > 0:
            ded = min(sqft * 5.0, 1500.0)
            self._ho_info_label.configure(
                text=f"Simplified method: {sqft:.0f} sq ft x $5 = ${ded:,.2f}/yr (max $1,500)")
        else:
            self._ho_info_label.configure(text="")
        messagebox.showinfo("Saved", f"Home office set to {sqft:.0f} sq ft.")
        self._refresh_tax()

    def _compare_1099k(self):
        val = self._1099k_entry.get().strip()
        if not val:
            messagebox.showerror("Error", "Enter the 1099-K gross amount.")
            return
        try:
            k_amount = float(val)
        except ValueError:
            messagebox.showerror("Error", "Enter a valid dollar amount.")
            return

        year = int(self._tax_year.get())
        summary = self.db.get_schedule_c_summary(year)
        logged_gross = summary["gross_income"] + summary.get("sales_tax_collected", 0)

        # Clear previous results
        for w in self._1099k_result.winfo_children():
            w.destroy()

        diff = logged_gross - k_amount

        ctk.CTkLabel(
            self._1099k_result,
            text=f"Your Logged Gross (incl. sales tax): ${logged_gross:,.2f}",
            font=FONT_SMALL,
        ).pack(anchor="w", padx=5, pady=1)
        ctk.CTkLabel(
            self._1099k_result,
            text=f"1099-K Gross Amount: ${k_amount:,.2f}",
            font=FONT_SMALL,
        ).pack(anchor="w", padx=5, pady=1)

        diff_color = COLORS["success"] if abs(diff) < 1.0 else COLORS["warning"]
        ctk.CTkLabel(
            self._1099k_result,
            text=f"Difference: ${diff:+,.2f}",
            font=FONT_LABEL, text_color=diff_color,
        ).pack(anchor="w", padx=5, pady=(2, 4))

        if abs(diff) < 1.0:
            guidance = "Your records match the 1099-K. No action needed."
        elif diff > 0:
            guidance = (
                "Your logged income is HIGHER than the 1099-K. This can happen if you "
                "have cash sales or non-platform income. You still report all income."
            )
        else:
            guidance = (
                "Your logged income is LOWER than the 1099-K. This may indicate "
                "missing income entries. Review your sales log for completeness. "
                "The IRS receives a copy of the 1099-K."
            )
        ctk.CTkLabel(
            self._1099k_result, text=guidance, font=FONT_SMALL,
            text_color=COLORS["text_muted"], wraplength=500, justify="left",
        ).pack(anchor="w", padx=5, pady=(0, 4))

    def _refresh_tax(self):
        year = int(self._tax_year.get())

        # Schedule C
        for w in self._tax_sc_content.winfo_children():
            w.destroy()

        summary = self.db.get_schedule_c_summary(year)

        lines = [
            ("Gross Income", summary["gross_income"], COLORS["text"]),
            ("Less: Cost of Goods (Inventory)", -summary["cogs"], COLORS["text_muted"]),
            ("Gross Profit", summary["gross_profit"], COLORS["text"]),
            ("", 0, ""),  # spacer
        ]

        # Expense breakdown
        for cat, total in summary["expense_breakdown"].items():
            if cat == "inventory":
                continue
            label = EXPENSE_LABELS.get(cat, cat.title())
            lines.append((f"  {label}", -total, COLORS["text_muted"]))

        if summary["mileage_deduction"] > 0:
            lines.append(("  Mileage Deduction", -summary["mileage_deduction"],
                          COLORS["text_muted"]))

        if summary.get("home_office_deduction", 0) > 0:
            lines.append(("  Home Office Deduction", -summary["home_office_deduction"],
                          COLORS["text_muted"]))

        lines.append(("Total Expenses", -summary["total_expenses"], COLORS["text"]))
        lines.append(("", 0, ""))
        lines.append(("Net Profit (Schedule C Line 31)", summary["net_profit"],
                       COLORS["success"] if summary["net_profit"] >= 0 else COLORS["error"]))
        lines.append(("", 0, ""))
        lines.append(("Self-Employment Tax (est.)", summary["se_tax_estimate"],
                       COLORS["warning"]))

        for label, amount, color in lines:
            if not label:
                ctk.CTkFrame(self._tax_sc_content, fg_color=COLORS["border"],
                             height=1).pack(fill="x", pady=4)
                continue
            row = ctk.CTkFrame(self._tax_sc_content, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                         text_color=color).pack(side="left", padx=5)
            sign = "" if amount >= 0 else "-"
            ctk.CTkLabel(row, text=f"{sign}${abs(amount):,.2f}", font=FONT_SMALL,
                         text_color=color).pack(side="right", padx=5)

        # Quarterly payments
        for w in self._tax_q_content.winfo_children():
            w.destroy()

        payments = self.db.get_tax_payments(year)
        if not payments:
            ctk.CTkLabel(
                self._tax_q_content,
                text="No quarterly payments set up. Click 'Initialize' below.",
                font=FONT_SMALL, text_color=COLORS["text_muted"],
            ).pack(anchor="w", padx=5, pady=5)
            return

        # Header row
        hdr = ctk.CTkFrame(self._tax_q_content, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 4))
        for col, w in [("Quarter", 60), ("Due Date", 100), ("Federal", 80),
                       ("CA State", 80), ("Status", 120)]:
            ctk.CTkLabel(hdr, text=col, font=FONT_LABEL, width=w).pack(
                side="left", padx=4)

        for p in payments:
            row = ctk.CTkFrame(self._tax_q_content, fg_color=COLORS["bg_light"],
                               corner_radius=6)
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(row, text=f"Q{p.quarter}", font=FONT_SMALL,
                         width=60).pack(side="left", padx=4, pady=6)
            ctk.CTkLabel(row, text=str(p.due_date), font=FONT_SMALL,
                         width=100).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"${p.federal_amount:,.0f}", font=FONT_SMALL,
                         width=80).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"${p.state_amount:,.0f}", font=FONT_SMALL,
                         width=80).pack(side="left", padx=4)

            if p.paid_date:
                status = f"Paid {p.paid_date}"
                color = COLORS["success"]
            elif p.due_date < date.today():
                status = "OVERDUE"
                color = COLORS["error"]
            elif (p.due_date - date.today()).days < 30:
                status = f"Due in {(p.due_date - date.today()).days}d"
                color = COLORS["warning"]
            else:
                status = "Upcoming"
                color = COLORS["text_muted"]

            ctk.CTkLabel(row, text=status, font=FONT_SMALL,
                         text_color=color, width=120).pack(side="left", padx=4)

            if p.confirmation:
                ctk.CTkLabel(row, text=f"#{p.confirmation}", font=FONT_SMALL,
                             text_color=COLORS["text_muted"]).pack(side="left", padx=4)

            if not p.paid_date:
                ctk.CTkButton(
                    row, text="Mark Paid", width=80, height=24,
                    fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                    font=FONT_SMALL,
                    command=lambda pid=p.id, pf=p.federal_amount, ps=p.state_amount: (
                        self._mark_payment_paid(pid, pf, ps)),
                ).pack(side="right", padx=6, pady=4)

        # Also refresh 1099-K comparison if entry has a value
        if hasattr(self, '_1099k_entry') and self._1099k_entry.get().strip():
            self._compare_1099k()

    def _mark_payment_paid(self, payment_id: int, federal: float, state: float):
        """Show a dialog to confirm marking a quarterly payment as paid."""
        dialog = ctk.CTkToplevel(self.parent)
        dialog.title("Mark Payment Paid")
        dialog.geometry("350x180")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self.parent)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Mark as Paid", font=FONT_HEADING).pack(
            anchor="w", padx=20, pady=(15, 10))

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="x", padx=20)

        ctk.CTkLabel(form, text="Confirmation # (optional):", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        conf_entry = ctk.CTkEntry(form, width=200, fg_color=COLORS["bg_light"],
                                   border_color=COLORS["border"],
                                   placeholder_text="e.g. IRS confirmation number")
        conf_entry.pack(anchor="w", pady=(4, 0))

        def _confirm():
            conf_num = conf_entry.get().strip()
            self.db.update_tax_payment(
                payment_id, paid_date=date.today(),
                federal=federal, state=state, confirmation=conf_num,
            )
            dialog.destroy()
            self._refresh_tax()

        ctk.CTkButton(
            dialog, text="Confirm Paid", width=140,
            fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
            command=_confirm,
        ).pack(pady=15)

    def _init_quarterly_payments(self):
        year = int(self._tax_year.get())
        existing = self.db.get_tax_payments(year)
        if existing:
            # Offer to recalculate estimates from current data
            if not messagebox.askyesno(
                "Recalculate?",
                f"Quarterly payments for {year} already exist.\n\n"
                "Recalculate estimated amounts from your current income & expenses?"
            ):
                return
            recalc = True
        else:
            recalc = False

        # Calculate estimated quarterly amounts from Schedule C
        summary = self.db.get_schedule_c_summary(year)
        net_profit = summary["net_profit"]

        if net_profit > 0:
            # Federal: SE tax (15.3% on 92.35% of net) + income tax estimate (~12% effective)
            annual_se_tax = net_profit * 0.9235 * 0.153
            annual_income_tax = net_profit * 0.12  # rough effective rate for small biz
            quarterly_federal = (annual_se_tax + annual_income_tax) / 4

            # California: ~5% effective state rate for small sole prop income
            quarterly_state = (net_profit * 0.05) / 4
        else:
            quarterly_federal = 0.0
            quarterly_state = 0.0

        # Federal + CA quarterly due dates
        quarters = [
            (1, date(year, 4, 15)),
            (2, date(year, 6, 15)),
            (3, date(year, 9, 15)),
            (4, date(year + 1, 1, 15)),
        ]

        for q, due in quarters:
            if recalc:
                # Update existing amounts (preserves paid_date/confirmation)
                for ep in existing:
                    if ep.quarter == q:
                        self.db.update_tax_payment(
                            ep.id,
                            paid_date=ep.paid_date or date.min,
                            federal=quarterly_federal,
                            state=quarterly_state,
                            confirmation=ep.confirmation,
                        )
                        # Clear paid_date=date.min hack if it wasn't paid
                        if not ep.paid_date:
                            with self.db._get_connection() as conn:
                                conn.execute(
                                    "UPDATE tax_payments SET paid_date = NULL WHERE id = ?",
                                    (ep.id,))
                        break
            else:
                payment = TaxPayment(
                    tax_year=year,
                    quarter=q,
                    due_date=due,
                    federal_amount=quarterly_federal,
                    state_amount=quarterly_state,
                )
                self.db.add_tax_payment(payment)

        action = "Recalculated" if recalc else "Created"
        if net_profit > 0:
            messagebox.showinfo(
                "Done",
                f"{action} quarterly tax estimates for {year}.\n\n"
                f"Based on ${net_profit:,.2f} net profit:\n"
                f"  Federal: ~${quarterly_federal:,.0f}/quarter\n"
                f"  CA State: ~${quarterly_state:,.0f}/quarter\n\n"
                "These are estimates. Consult a tax professional for exact amounts."
            )
        else:
            messagebox.showinfo(
                "Done",
                f"{action} quarterly reminders for {year}.\n"
                "No estimated tax yet (net profit is $0 or negative)."
            )
        self._refresh_tax()

    # ================================================================
    # Section: Export CSV
    # ================================================================

    def _build_export(self):
        scroll = ctk.CTkScrollableFrame(self._content, fg_color="transparent")
        self._section_frames["export"] = scroll

        # Date range filter
        dr_card = self._card(scroll, "Date Range")
        dr_inner = ctk.CTkFrame(dr_card, fg_color="transparent")
        dr_inner.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(dr_inner, text="Start:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._export_start = ctk.CTkEntry(
            dr_inner, width=120, fg_color=COLORS["bg_light"],
            border_color=COLORS["border"], font=FONT_SMALL,
        )
        self._export_start.pack(side="left", padx=(4, 12))
        self._export_start.insert(0, f"{date.today().year}-01-01")

        ctk.CTkLabel(dr_inner, text="End:", font=FONT_SMALL,
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._export_end = ctk.CTkEntry(
            dr_inner, width=120, fg_color=COLORS["bg_light"],
            border_color=COLORS["border"], font=FONT_SMALL,
        )
        self._export_end.pack(side="left", padx=(4, 12))
        self._export_end.insert(0, date.today().isoformat())

        card = self._card(scroll, "Export Data to CSV")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkLabel(
            inner,
            text="Export your business data as CSV files for your accountant, tax prep, or personal records.",
            font=FONT_SMALL, text_color=COLORS["text_muted"],
        ).pack(anchor="w", pady=(0, 12))

        exports = [
            ("Export Expenses", "expenses", self._export_expenses),
            ("Export Income", "income", self._export_income),
            ("Export Mileage", "mileage", self._export_mileage),
            ("Export Documents List", "documents", self._export_documents),
            ("Export Tax Summary", "tax_summary", self._export_tax_summary),
            ("Export All (ZIP)", "all", self._export_all),
        ]

        for label, key, cmd in exports:
            row = ctk.CTkFrame(inner, fg_color=COLORS["bg_light"], corner_radius=6)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, font=FONT_BODY).pack(
                side="left", padx=15, pady=10)
            ctk.CTkButton(
                row, text="Export", width=90,
                fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                command=cmd,
            ).pack(side="right", padx=10, pady=6)

    def _get_export_date_range(self):
        """Parse the start/end date entries for export filtering."""
        try:
            start = date.fromisoformat(self._export_start.get().strip())
        except (ValueError, AttributeError):
            start = date(date.today().year, 1, 1)
        try:
            end = date.fromisoformat(self._export_end.get().strip())
        except (ValueError, AttributeError):
            end = date.today()
        return start, end

    def _export_expenses(self):
        start, end = self._get_export_date_range()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"expenses_{date.today().isoformat()}.csv",
        )
        if not path:
            return
        all_expenses = self.db.get_expenses(limit=10000)
        expenses = [e for e in all_expenses if start <= e.date <= end]
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Date", "Category", "Amount", "Vendor", "Description",
                        "Receipt", "Tax Deductible", "Notes"])
            for e in expenses:
                w.writerow([e.date, EXPENSE_LABELS.get(e.category, e.category),
                            f"{e.amount:.2f}", e.vendor, e.description,
                            "Yes" if e.receipt_path else "No",
                            "Yes" if e.tax_deductible else "No", e.notes])
        messagebox.showinfo("Exported", f"Expenses exported to:\n{path}")

    def _export_income(self):
        start, end = self._get_export_date_range()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"income_{date.today().isoformat()}.csv",
        )
        if not path:
            return
        all_entries = self.db.get_income(limit=10000)
        entries = [i for i in all_entries if start <= i.date <= end]
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Date", "Source", "Description", "Gross Amount",
                        "Platform Fees", "Shipping Cost", "Net Amount", "Notes"])
            for i in entries:
                w.writerow([i.date, i.source, i.description,
                            f"{i.amount:.2f}", f"{i.platform_fees:.2f}",
                            f"{i.shipping_cost:.2f}", f"{i.net_amount:.2f}",
                            i.notes])
        messagebox.showinfo("Exported", f"Income exported to:\n{path}")

    def _export_mileage(self):
        start, end = self._get_export_date_range()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"mileage_{date.today().isoformat()}.csv",
        )
        if not path:
            return
        all_trips = self.db.get_mileage(limit=10000)
        trips = [t for t in all_trips if start <= t.date <= end]
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Date", "Purpose", "Destination", "Miles",
                        "Rate/Mile", "Deduction", "Notes"])
            for t in trips:
                ded = t.miles * t.rate_per_mile
                w.writerow([t.date, t.purpose, t.destination,
                            f"{t.miles:.1f}", f"{t.rate_per_mile:.2f}",
                            f"{ded:.2f}", t.notes])
        messagebox.showinfo("Exported", f"Mileage exported to:\n{path}")

    def _export_documents(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"documents_{date.today().isoformat()}.csv",
        )
        if not path:
            return
        docs = self.db.get_documents()
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Type", "Name", "File Path", "Expiry Date", "Notes"])
            for d in docs:
                type_label = d.doc_type
                for k, v in DOC_TYPES:
                    if k == d.doc_type:
                        type_label = v
                        break
                w.writerow([type_label, d.name, d.file_path,
                            d.expiry_date or "", d.notes])
        messagebox.showinfo("Exported", f"Documents list exported to:\n{path}")

    def _export_tax_summary(self):
        start, end = self._get_export_date_range()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"tax_summary_{start.year}.csv",
        )
        if not path:
            return
        year = start.year
        summary = self.db.get_schedule_c_summary(year)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Category", "Amount"])
            w.writerow(["Gross Income", f"{summary['gross_income']:.2f}"])
            w.writerow(["Cost of Goods (Inventory)", f"{summary['cogs']:.2f}"])
            w.writerow(["Gross Profit", f"{summary['gross_profit']:.2f}"])
            for cat, total in summary["expense_breakdown"].items():
                if cat == "inventory":
                    continue
                label = EXPENSE_LABELS.get(cat, cat.title())
                w.writerow([label, f"{total:.2f}"])
            w.writerow(["Mileage Deduction", f"{summary['mileage_deduction']:.2f}"])
            w.writerow(["Total Expenses", f"{summary['total_expenses']:.2f}"])
            w.writerow(["Net Profit", f"{summary['net_profit']:.2f}"])
            w.writerow(["Self-Employment Tax (est.)", f"{summary['se_tax_estimate']:.2f}"])
        messagebox.showinfo("Exported", f"Tax summary exported to:\n{path}")

    def _export_all(self):
        """Export all data as individual CSVs in a ZIP file, including receipts."""
        start, end = self._get_export_date_range()
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")],
            initialfile=f"mybay_business_export_{date.today().isoformat()}.zip",
        )
        if not path:
            return

        import zipfile

        def _csv_string(header, rows):
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(header)
            for row in rows:
                w.writerow(row)
            return buf.getvalue()

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Expenses (date filtered)
            all_expenses = self.db.get_expenses(limit=10000)
            expenses = [e for e in all_expenses if start <= e.date <= end]
            zf.writestr("expenses.csv", _csv_string(
                ["Date", "Category", "Amount", "Vendor", "Description", "Receipt", "Tax Deductible", "Notes"],
                [[e.date, EXPENSE_LABELS.get(e.category, e.category), f"{e.amount:.2f}",
                  e.vendor, e.description, "Yes" if e.receipt_path else "No",
                  "Yes" if e.tax_deductible else "No", e.notes] for e in expenses]
            ))

            # Income (date filtered)
            all_entries = self.db.get_income(limit=10000)
            entries = [i for i in all_entries if start <= i.date <= end]
            zf.writestr("income.csv", _csv_string(
                ["Date", "Source", "Description", "Gross", "Fees", "Shipping", "Net", "Notes"],
                [[i.date, i.source, i.description, f"{i.amount:.2f}",
                  f"{i.platform_fees:.2f}", f"{i.shipping_cost:.2f}",
                  f"{i.net_amount:.2f}", i.notes] for i in entries]
            ))

            # Mileage (date filtered)
            all_trips = self.db.get_mileage(limit=10000)
            trips = [t for t in all_trips if start <= t.date <= end]
            zf.writestr("mileage.csv", _csv_string(
                ["Date", "Purpose", "Destination", "Miles", "Rate", "Deduction", "Notes"],
                [[t.date, t.purpose, t.destination, f"{t.miles:.1f}",
                  f"{t.rate_per_mile:.2f}", f"{t.miles * t.rate_per_mile:.2f}",
                  t.notes] for t in trips]
            ))

            # Tax summary
            year = start.year
            summary = self.db.get_schedule_c_summary(year)
            tax_rows = [
                ["Gross Income", f"{summary['gross_income']:.2f}"],
                ["COGS", f"{summary['cogs']:.2f}"],
                ["Gross Profit", f"{summary['gross_profit']:.2f}"],
            ]
            for cat, total in summary["expense_breakdown"].items():
                if cat == "inventory":
                    continue
                tax_rows.append([EXPENSE_LABELS.get(cat, cat.title()), f"{total:.2f}"])
            tax_rows.extend([
                ["Mileage Deduction", f"{summary['mileage_deduction']:.2f}"],
                ["Home Office Deduction", f"{summary.get('home_office_deduction', 0):.2f}"],
                ["Total Expenses", f"{summary['total_expenses']:.2f}"],
                ["Net Profit", f"{summary['net_profit']:.2f}"],
                ["SE Tax (est.)", f"{summary['se_tax_estimate']:.2f}"],
            ])
            zf.writestr("tax_summary.csv", _csv_string(["Category", "Amount"], tax_rows))

            # Receipt images
            receipt_count = 0
            for e in expenses:
                if e.receipt_path:
                    rp = Path(e.receipt_path)
                    if rp.exists():
                        zf.write(str(rp), f"receipts/{rp.name}")
                        receipt_count += 1

        msg = f"All data exported to:\n{path}"
        if receipt_count > 0:
            msg += f"\n\nIncluded {receipt_count} receipt file(s) in receipts/ folder."
        messagebox.showinfo("Exported", msg)

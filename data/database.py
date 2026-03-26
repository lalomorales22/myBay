"""
SQLite Database for myBay

Manages:
- Drafts: AI-analyzed items awaiting review
- Listings: Published items on eBay
- Stats: Daily performance metrics
"""

import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from contextlib import contextmanager

from core.paths import get_db_path

DB_PATH = get_db_path()


@dataclass
class Draft:
    """A draft listing awaiting review."""
    sku: str
    title: str
    description: str
    category_id: str = ""
    category_name: str = ""
    condition: str = "NEW"
    price: float = 0.0
    quantity: int = 1
    listing_format: str = "FIXED_PRICE"  # FIXED_PRICE or AUCTION
    image_paths: list = field(default_factory=list)
    ai_confidence: float = 0.0
    aspects: dict = field(default_factory=dict)
    brand: Optional[str] = None
    model: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    cost_basis: float = 0.0
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "sku": self.sku,
            "title": self.title,
            "description": self.description,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "condition": self.condition,
            "price": self.price,
            "quantity": self.quantity,
            "listing_format": self.listing_format,
            "image_paths": self.image_paths,
            "ai_confidence": self.ai_confidence,
            "aspects": self.aspects,
            "brand": self.brand,
            "model": self.model,
            "size": self.size,
            "color": self.color,
            "cost_basis": self.cost_basis,
        }
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Draft":
        return cls(
            id=row["id"],
            sku=row["sku"],
            title=row["title"],
            description=row["description"],
            category_id=row["category_id"] or "",
            category_name=row["category_name"] or "",
            condition=row["condition"],
            price=row["price"],
            quantity=row["quantity"] if "quantity" in row.keys() else 1,
            listing_format=row["listing_format"] if "listing_format" in row.keys() else "FIXED_PRICE",
            image_paths=json.loads(row["image_paths"]) if row["image_paths"] else [],
            ai_confidence=row["ai_confidence"],
            aspects=json.loads(row["aspects"]) if row["aspects"] else {},
            brand=row["brand"],
            model=row["model"] if "model" in row.keys() else None,
            size=row["size"] if "size" in row.keys() else None,
            color=row["color"],
            cost_basis=row["cost_basis"] if "cost_basis" in row.keys() else 0.0,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


@dataclass
class Listing:
    """A published eBay listing."""
    sku: str
    ebay_listing_id: str
    title: str
    price: float
    status: str = "ACTIVE"  # ACTIVE, SOLD, ENDED
    environment: Optional[str] = None  # sandbox or production
    id: Optional[int] = None
    published_at: Optional[datetime] = None
    sold_at: Optional[datetime] = None
    sold_price: Optional[float] = None
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Listing":
        return cls(
            id=row["id"],
            sku=row["sku"],
            ebay_listing_id=row["ebay_listing_id"],
            title=row["title"],
            price=row["price"],
            status=row["status"],
            environment=row["environment"] if "environment" in row.keys() else None,
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
            sold_at=datetime.fromisoformat(row["sold_at"]) if row["sold_at"] else None,
            sold_price=row["sold_price"],
        )


@dataclass
class DailyStat:
    """Daily performance statistics."""
    date: date
    listings_created: int = 0
    items_sold: int = 0
    revenue: float = 0.0
    time_saved_seconds: int = 0  # Estimated time saved vs manual listing
    id: Optional[int] = None
    
    @property
    def time_saved_minutes(self) -> float:
        return self.time_saved_seconds / 60
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "DailyStat":
        return cls(
            id=row["id"],
            date=date.fromisoformat(row["date"]),
            listings_created=row["listings_created"],
            items_sold=row["items_sold"],
            revenue=row["revenue"],
            time_saved_seconds=row["time_saved_seconds"],
        )


@dataclass
class Expense:
    """A business expense entry."""
    date: date
    category: str
    amount: float
    description: str = ""
    vendor: str = ""
    receipt_path: str = ""
    tax_deductible: bool = True
    notes: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Expense":
        return cls(
            id=row["id"],
            date=date.fromisoformat(row["date"]),
            category=row["category"],
            amount=row["amount"],
            description=row["description"] or "",
            vendor=row["vendor"] or "",
            receipt_path=row["receipt_path"] or "",
            tax_deductible=bool(row["tax_deductible"]),
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


@dataclass
class Income:
    """A business income entry."""
    date: date
    amount: float
    source: str = "ebay"
    description: str = ""
    listing_sku: str = ""
    platform_fees: float = 0.0
    shipping_cost: float = 0.0
    net_amount: float = 0.0
    sales_tax_collected: float = 0.0
    notes: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Income":
        keys = row.keys()
        return cls(
            id=row["id"],
            date=date.fromisoformat(row["date"]),
            amount=row["amount"],
            source=row["source"] or "ebay",
            description=row["description"] or "",
            listing_sku=row["listing_sku"] or "",
            platform_fees=row["platform_fees"] or 0.0,
            shipping_cost=row["shipping_cost"] or 0.0,
            net_amount=row["net_amount"] or 0.0,
            sales_tax_collected=row["sales_tax_collected"] or 0.0 if "sales_tax_collected" in keys else 0.0,
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


@dataclass
class MileageTrip:
    """A mileage log entry for IRS deduction."""
    date: date
    purpose: str
    miles: float
    destination: str = ""
    rate_per_mile: float = 0.70  # 2025 IRS standard rate
    notes: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @property
    def deduction(self) -> float:
        return self.miles * self.rate_per_mile

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "MileageTrip":
        return cls(
            id=row["id"],
            date=date.fromisoformat(row["date"]),
            purpose=row["purpose"],
            miles=row["miles"],
            destination=row["destination"] or "",
            rate_per_mile=row["rate_per_mile"] or 0.70,
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


@dataclass
class Document:
    """A stored business document."""
    doc_type: str
    name: str
    file_path: str = ""
    expiry_date: Optional[date] = None
    notes: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Document":
        return cls(
            id=row["id"],
            doc_type=row["doc_type"],
            name=row["name"],
            file_path=row["file_path"] or "",
            expiry_date=date.fromisoformat(row["expiry_date"]) if row["expiry_date"] else None,
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


@dataclass
class TaxPayment:
    """A quarterly estimated tax payment."""
    tax_year: int
    quarter: int
    due_date: date
    federal_amount: float = 0.0
    state_amount: float = 0.0
    paid_date: Optional[date] = None
    confirmation: str = ""
    notes: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TaxPayment":
        return cls(
            id=row["id"],
            tax_year=row["tax_year"],
            quarter=row["quarter"],
            due_date=date.fromisoformat(row["due_date"]),
            federal_amount=row["federal_amount"] or 0.0,
            state_amount=row["state_amount"] or 0.0,
            paid_date=date.fromisoformat(row["paid_date"]) if row["paid_date"] else None,
            confirmation=row["confirmation"] or "",
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


class Database:
    """
    SQLite database manager for myBay.

    Usage:
        db = Database()
        db.add_draft(draft)
        drafts = db.get_all_drafts()
    """

    # Estimated time to manually list an item (in seconds)
    MANUAL_LISTING_TIME = 300  # 5 minutes

    def __init__(self, db_path: Path = None):
        """Initialize database connection."""
        self.db_path = db_path or DB_PATH
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Drafts awaiting review
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category_id TEXT,
                    category_name TEXT,
                    condition TEXT DEFAULT 'NEW',
                    price REAL DEFAULT 0,
                    image_paths TEXT,
                    ai_confidence REAL DEFAULT 0,
                    aspects TEXT,
                    brand TEXT,
                    color TEXT,
                    quantity INTEGER DEFAULT 1,
                    listing_format TEXT DEFAULT 'FIXED_PRICE',
                    model TEXT,
                    size TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Published listings
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT UNIQUE NOT NULL,
                    ebay_listing_id TEXT,
                    title TEXT NOT NULL,
                    price REAL,
                    status TEXT DEFAULT 'ACTIVE',
                    environment TEXT,
                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sold_at TIMESTAMP,
                    sold_price REAL
                );

                -- Daily performance stats
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    listings_created INTEGER DEFAULT 0,
                    items_sold INTEGER DEFAULT 0,
                    revenue REAL DEFAULT 0,
                    time_saved_seconds INTEGER DEFAULT 0
                );
                
                -- App settings/config
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_drafts_created ON drafts(created_at);
                CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
                CREATE INDEX IF NOT EXISTS idx_listings_published ON listings(published_at);
                CREATE INDEX IF NOT EXISTS idx_stats_date ON stats(date);

                -- Business info (key-value for sole prop details)
                CREATE TABLE IF NOT EXISTS business_info (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Expenses
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    vendor TEXT,
                    receipt_path TEXT,
                    tax_deductible INTEGER DEFAULT 1,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Income
                CREATE TABLE IF NOT EXISTS income (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    source TEXT DEFAULT 'ebay',
                    description TEXT,
                    amount REAL NOT NULL,
                    listing_sku TEXT,
                    platform_fees REAL DEFAULT 0,
                    shipping_cost REAL DEFAULT 0,
                    net_amount REAL DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Mileage trips
                CREATE TABLE IF NOT EXISTS mileage_trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    purpose TEXT NOT NULL,
                    destination TEXT,
                    miles REAL NOT NULL,
                    rate_per_mile REAL DEFAULT 0.70,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Business documents
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    file_path TEXT,
                    expiry_date DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Tax payments
                CREATE TABLE IF NOT EXISTS tax_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tax_year INTEGER NOT NULL,
                    quarter INTEGER NOT NULL,
                    due_date DATE NOT NULL,
                    federal_amount REAL DEFAULT 0,
                    state_amount REAL DEFAULT 0,
                    paid_date DATE,
                    confirmation TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
                CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
                CREATE INDEX IF NOT EXISTS idx_income_date ON income(date);
                CREATE INDEX IF NOT EXISTS idx_mileage_date ON mileage_trips(date);
                CREATE INDEX IF NOT EXISTS idx_tax_year ON tax_payments(tax_year);
            """)

            # Migration: Add new columns to existing databases
            self._migrate_drafts_table(conn)
            self._migrate_listings_table(conn)
            self._migrate_income_table(conn)
    
    def _migrate_drafts_table(self, conn):
        """Add new columns if they don't exist (for existing databases)."""
        # Check which columns exist
        cursor = conn.execute("PRAGMA table_info(drafts)")
        existing = {row[1] for row in cursor.fetchall()}
        
        # Add missing columns
        migrations = [
            ("quantity", "INTEGER DEFAULT 1"),
            ("listing_format", "TEXT DEFAULT 'FIXED_PRICE'"),
            ("model", "TEXT"),
            ("size", "TEXT"),
            ("cost_basis", "REAL DEFAULT 0"),
        ]
        
        for col_name, col_def in migrations:
            if col_name not in existing:
                try:
                    conn.execute(f"ALTER TABLE drafts ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass  # Column might already exist

    def _migrate_listings_table(self, conn):
        """Add new listing columns if they don't exist (for existing databases)."""
        cursor = conn.execute("PRAGMA table_info(listings)")
        existing = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("environment", "TEXT"),
        ]

        for col_name, col_def in migrations:
            if col_name not in existing:
                try:
                    conn.execute(f"ALTER TABLE listings ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass

    def _migrate_income_table(self, conn):
        """Add new income columns if they don't exist."""
        cursor = conn.execute("PRAGMA table_info(income)")
        existing = {row[1] for row in cursor.fetchall()}
        migrations = [
            ("sales_tax_collected", "REAL DEFAULT 0"),
        ]
        for col_name, col_def in migrations:
            if col_name not in existing:
                try:
                    conn.execute(f"ALTER TABLE income ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass

    @contextmanager
    def _get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    # ==================== Drafts ====================
    
    def add_draft(self, draft: Draft) -> int:
        """Add a new draft. Returns the draft ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO drafts
                (sku, title, description, category_id, category_name, condition,
                 price, image_paths, ai_confidence, aspects, brand, color,
                 quantity, listing_format, model, size, cost_basis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                draft.sku,
                draft.title,
                draft.description,
                draft.category_id,
                draft.category_name,
                draft.condition,
                draft.price,
                json.dumps(draft.image_paths),
                draft.ai_confidence,
                json.dumps(draft.aspects),
                draft.brand,
                draft.color,
                draft.quantity,
                draft.listing_format,
                draft.model,
                draft.size,
                draft.cost_basis,
            ))
            return cursor.lastrowid
    
    def get_draft(self, sku: str) -> Optional[Draft]:
        """Get a draft by SKU."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM drafts WHERE sku = ?", (sku,)
            ).fetchone()
            return Draft.from_row(row) if row else None
    
    def get_draft_by_id(self, draft_id: int) -> Optional[Draft]:
        """Get a draft by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
            return Draft.from_row(row) if row else None
    
    def get_all_drafts(self, limit: int = 100) -> list[Draft]:
        """Get all drafts, newest first."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [Draft.from_row(row) for row in rows]
    
    def get_high_confidence_drafts(self, min_confidence: float = 0.85) -> list[Draft]:
        """Get drafts with high AI confidence (for Turbo Mode)."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM drafts WHERE ai_confidence >= ? ORDER BY ai_confidence DESC",
                (min_confidence,)
            ).fetchall()
            return [Draft.from_row(row) for row in rows]
    
    def update_draft(self, draft: Draft) -> bool:
        """Update an existing draft."""
        if not draft.sku:
            return False
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE drafts SET
                    title = ?, description = ?, category_id = ?, category_name = ?,
                    condition = ?, price = ?, image_paths = ?, ai_confidence = ?,
                    aspects = ?, brand = ?, color = ?, quantity = ?, listing_format = ?,
                    model = ?, size = ?, cost_basis = ?
                WHERE sku = ?
            """, (
                draft.title, draft.description, draft.category_id, draft.category_name,
                draft.condition, draft.price, json.dumps(draft.image_paths),
                draft.ai_confidence, json.dumps(draft.aspects), draft.brand, draft.color,
                draft.quantity, draft.listing_format, draft.model, draft.size,
                draft.cost_basis,
                draft.sku,
            ))
            return True
    
    def delete_draft(self, sku: str) -> bool:
        """Delete a draft by SKU."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM drafts WHERE sku = ?", (sku,))
            return cursor.rowcount > 0
    
    def draft_count(self) -> int:
        """Get total number of drafts."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM drafts").fetchone()
            return row["count"]
    
    # ==================== Listings ====================
    
    def add_listing(self, listing: Listing) -> int:
        """Add a published listing. Returns the listing ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO listings 
                (sku, ebay_listing_id, title, price, status, environment, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                listing.sku,
                listing.ebay_listing_id,
                listing.title,
                listing.price,
                listing.status,
                listing.environment,
                listing.published_at or datetime.now(),
            ))
            
            # Update daily stats (passing connection to avoid lock)
            self._increment_stat_with_conn(conn, "listings_created")
            self._add_time_saved_with_conn(conn, self.MANUAL_LISTING_TIME)
            
            return cursor.lastrowid
    
    def get_listing(self, sku: str) -> Optional[Listing]:
        """Get a listing by SKU."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM listings WHERE sku = ?", (sku,)
            ).fetchone()
            return Listing.from_row(row) if row else None
    
    def get_active_listings(self, limit: int = 100) -> list[Listing]:
        """Get active listings."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM listings WHERE status = 'ACTIVE' ORDER BY published_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [Listing.from_row(row) for row in rows]
    
    def get_recent_listings(self, limit: int = 10) -> list[Listing]:
        """Get recently published listings."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM listings ORDER BY published_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [Listing.from_row(row) for row in rows]

    def delete_listing(self, sku: str) -> bool:
        """Delete a listing record by SKU (local database only)."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM listings WHERE sku = ?", (sku,))
            return cursor.rowcount > 0
    
    def mark_listing_sold(self, sku: str, sold_price: float = None) -> bool:
        """Mark a listing as sold."""
        with self._get_connection() as conn:
            # Get listing within this connection
            row = conn.execute(
                "SELECT * FROM listings WHERE sku = ?", (sku,)
            ).fetchone()
            if not row:
                return False
            
            listing = Listing.from_row(row)
            final_price = sold_price or listing.price
            conn.execute("""
                UPDATE listings SET status = 'SOLD', sold_at = ?, sold_price = ?
                WHERE sku = ?
            """, (datetime.now(), final_price, sku))
            
            # Update stats (using connection-aware methods)
            self._increment_stat_with_conn(conn, "items_sold")
            self._add_revenue_with_conn(conn, final_price)
            
            return True
    
    def listing_count(self, status: str = None) -> int:
        """Get count of listings, optionally filtered by status."""
        with self._get_connection() as conn:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) as count FROM listings WHERE status = ?", (status,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as count FROM listings").fetchone()
            return row["count"]
    
    # ==================== Stats ====================
    
    def _get_today_stat(self, conn) -> sqlite3.Row:
        """Get or create today's stat record."""
        today = date.today().isoformat()
        row = conn.execute("SELECT * FROM stats WHERE date = ?", (today,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO stats (date) VALUES (?)", (today,)
            )
            row = conn.execute("SELECT * FROM stats WHERE date = ?", (today,)).fetchone()
        return row
    
    def _increment_stat(self, field: str, amount: int = 1):
        """Increment a stat field for today."""
        with self._get_connection() as conn:
            self._increment_stat_with_conn(conn, field, amount)
    
    def _increment_stat_with_conn(self, conn, field: str, amount: int = 1):
        """Increment a stat field for today (using existing connection)."""
        self._get_today_stat(conn)
        conn.execute(f"""
            UPDATE stats SET {field} = {field} + ? WHERE date = ?
        """, (amount, date.today().isoformat()))
    
    def _add_revenue(self, amount: float):
        """Add to today's revenue."""
        with self._get_connection() as conn:
            self._add_revenue_with_conn(conn, amount)
    
    def _add_revenue_with_conn(self, conn, amount: float):
        """Add to today's revenue (using existing connection)."""
        self._get_today_stat(conn)
        conn.execute("""
            UPDATE stats SET revenue = revenue + ? WHERE date = ?
        """, (amount, date.today().isoformat()))
    
    def _add_time_saved(self, seconds: int):
        """Add to today's time saved."""
        with self._get_connection() as conn:
            self._add_time_saved_with_conn(conn, seconds)
    
    def _add_time_saved_with_conn(self, conn, seconds: int):
        """Add to today's time saved (using existing connection)."""
        self._get_today_stat(conn)
        conn.execute("""
            UPDATE stats SET time_saved_seconds = time_saved_seconds + ? WHERE date = ?
        """, (seconds, date.today().isoformat()))
    
    def get_today_stats(self) -> DailyStat:
        """Get today's statistics."""
        with self._get_connection() as conn:
            row = self._get_today_stat(conn)
            return DailyStat.from_row(row)
    
    def get_stats_range(self, days: int = 7) -> list[DailyStat]:
        """Get stats for the last N days."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM stats 
                ORDER BY date DESC 
                LIMIT ?
            """, (days,)).fetchall()
            return [DailyStat.from_row(row) for row in rows]
    
    def get_total_stats(self) -> dict:
        """Get all-time totals."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT 
                    COALESCE(SUM(listings_created), 0) as total_listings,
                    COALESCE(SUM(items_sold), 0) as total_sold,
                    COALESCE(SUM(revenue), 0) as total_revenue,
                    COALESCE(SUM(time_saved_seconds), 0) as total_time_saved
                FROM stats
            """).fetchone()
            return {
                "total_listings": row["total_listings"],
                "total_sold": row["total_sold"],
                "total_revenue": row["total_revenue"],
                "total_time_saved_minutes": row["total_time_saved"] / 60,
            }
    
    # ==================== Settings ====================
    
    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a setting value."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default
    
    def set_setting(self, key: str, value: str):
        """Set a setting value."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            """, (key, value))
    
    def get_all_settings(self) -> dict:
        """Get all settings as a dictionary."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {row["key"]: row["value"] for row in rows}

    # ==================== Business Info ====================

    def get_business_info(self, key: str, default: str = "") -> str:
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM business_info WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_business_info(self, key: str, value: str):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO business_info (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.now()))

    def get_all_business_info(self) -> dict:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM business_info").fetchall()
            return {row["key"]: row["value"] for row in rows}

    # ==================== Expenses ====================

    def add_expense(self, expense: Expense) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO expenses (date, category, description, amount, vendor,
                    receipt_path, tax_deductible, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                expense.date.isoformat(), expense.category, expense.description,
                expense.amount, expense.vendor, expense.receipt_path,
                1 if expense.tax_deductible else 0, expense.notes,
            ))
            return cursor.lastrowid

    def get_expenses(self, start_date: date = None, end_date: date = None,
                     category: str = None, limit: int = 500) -> list[Expense]:
        with self._get_connection() as conn:
            query = "SELECT * FROM expenses WHERE 1=1"
            params = []
            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())
            if category:
                query += " AND category = ?"
                params.append(category)
            query += " ORDER BY date DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [Expense.from_row(row) for row in rows]

    def delete_expense(self, expense_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            return cursor.rowcount > 0

    def get_expense_totals(self, start_date: date = None, end_date: date = None) -> dict:
        with self._get_connection() as conn:
            query = "SELECT category, SUM(amount) as total FROM expenses WHERE 1=1"
            params = []
            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())
            query += " GROUP BY category ORDER BY total DESC"
            rows = conn.execute(query, params).fetchall()
            return {row["category"]: row["total"] for row in rows}

    # ==================== Income ====================

    def add_income(self, income: Income) -> int:
        with self._get_connection() as conn:
            net = income.amount - income.platform_fees - income.shipping_cost
            cursor = conn.execute("""
                INSERT INTO income (date, source, description, amount, listing_sku,
                    platform_fees, shipping_cost, net_amount, sales_tax_collected, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                income.date.isoformat(), income.source, income.description,
                income.amount, income.listing_sku, income.platform_fees,
                income.shipping_cost, net, income.sales_tax_collected, income.notes,
            ))
            return cursor.lastrowid

    def get_income(self, start_date: date = None, end_date: date = None,
                   limit: int = 500) -> list[Income]:
        with self._get_connection() as conn:
            query = "SELECT * FROM income WHERE 1=1"
            params = []
            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())
            query += " ORDER BY date DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [Income.from_row(row) for row in rows]

    def delete_income(self, income_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM income WHERE id = ?", (income_id,))
            return cursor.rowcount > 0

    def get_income_total(self, start_date: date = None, end_date: date = None) -> dict:
        with self._get_connection() as conn:
            query = """SELECT COALESCE(SUM(amount), 0) as gross,
                       COALESCE(SUM(platform_fees), 0) as fees,
                       COALESCE(SUM(shipping_cost), 0) as shipping,
                       COALESCE(SUM(net_amount), 0) as net,
                       COALESCE(SUM(sales_tax_collected), 0) as sales_tax
                       FROM income WHERE 1=1"""
            params = []
            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())
            row = conn.execute(query, params).fetchone()
            return {"gross": row["gross"], "fees": row["fees"],
                    "shipping": row["shipping"], "net": row["net"],
                    "sales_tax": row["sales_tax"]}

    def get_imported_skus(self) -> set:
        """Get set of listing SKUs already imported as income."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT listing_sku FROM income WHERE listing_sku IS NOT NULL AND listing_sku != ''"
            ).fetchall()
            return {row["listing_sku"] for row in rows}

    # ==================== Mileage ====================

    def add_mileage(self, trip: MileageTrip) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO mileage_trips (date, purpose, destination, miles,
                    rate_per_mile, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                trip.date.isoformat(), trip.purpose, trip.destination,
                trip.miles, trip.rate_per_mile, trip.notes,
            ))
            return cursor.lastrowid

    def get_mileage(self, start_date: date = None, end_date: date = None,
                    limit: int = 500) -> list[MileageTrip]:
        with self._get_connection() as conn:
            query = "SELECT * FROM mileage_trips WHERE 1=1"
            params = []
            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())
            query += " ORDER BY date DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [MileageTrip.from_row(row) for row in rows]

    def delete_mileage(self, trip_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM mileage_trips WHERE id = ?", (trip_id,))
            return cursor.rowcount > 0

    def get_mileage_totals(self, start_date: date = None, end_date: date = None) -> dict:
        with self._get_connection() as conn:
            query = """SELECT COALESCE(SUM(miles), 0) as total_miles,
                       COALESCE(SUM(miles * rate_per_mile), 0) as total_deduction
                       FROM mileage_trips WHERE 1=1"""
            params = []
            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())
            row = conn.execute(query, params).fetchone()
            return {"total_miles": row["total_miles"],
                    "total_deduction": row["total_deduction"]}

    # ==================== Mileage Rate Helpers ====================

    # IRS standard mileage rates by year
    IRS_MILEAGE_RATES = {2023: 0.655, 2024: 0.67, 2025: 0.70, 2026: 0.70}

    def get_mileage_rate(self, year: int) -> float:
        """Get the IRS mileage rate for a given year. Checks settings first, then defaults."""
        custom = self.get_setting(f"mileage_rate_{year}")
        if custom:
            try:
                return float(custom)
            except ValueError:
                pass
        return self.IRS_MILEAGE_RATES.get(year, 0.70)

    def set_mileage_rate(self, year: int, rate: float):
        """Override the IRS mileage rate for a given year."""
        self.set_setting(f"mileage_rate_{year}", str(rate))

    # ==================== Documents ====================

    def add_document(self, doc: Document) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO documents (doc_type, name, file_path, expiry_date, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (
                doc.doc_type, doc.name, doc.file_path,
                doc.expiry_date.isoformat() if doc.expiry_date else None,
                doc.notes,
            ))
            return cursor.lastrowid

    def get_documents(self, doc_type: str = None) -> list[Document]:
        with self._get_connection() as conn:
            if doc_type:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE doc_type = ? ORDER BY created_at DESC",
                    (doc_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY doc_type, created_at DESC"
                ).fetchall()
            return [Document.from_row(row) for row in rows]

    def delete_document(self, doc_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return cursor.rowcount > 0

    # ==================== Tax Payments ====================

    def add_tax_payment(self, payment: TaxPayment) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO tax_payments
                    (tax_year, quarter, due_date, federal_amount, state_amount,
                     paid_date, confirmation, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payment.tax_year, payment.quarter,
                payment.due_date.isoformat(),
                payment.federal_amount, payment.state_amount,
                payment.paid_date.isoformat() if payment.paid_date else None,
                payment.confirmation, payment.notes,
            ))
            return cursor.lastrowid

    def get_tax_payments(self, tax_year: int = None) -> list[TaxPayment]:
        with self._get_connection() as conn:
            if tax_year:
                rows = conn.execute(
                    "SELECT * FROM tax_payments WHERE tax_year = ? ORDER BY quarter",
                    (tax_year,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tax_payments ORDER BY tax_year DESC, quarter"
                ).fetchall()
            return [TaxPayment.from_row(row) for row in rows]

    def update_tax_payment(self, payment_id: int, paid_date: date,
                           federal: float, state: float, confirmation: str = ""):
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE tax_payments SET paid_date = ?, federal_amount = ?,
                    state_amount = ?, confirmation = ?
                WHERE id = ?
            """, (paid_date.isoformat(), federal, state, confirmation, payment_id))

    # ==================== Tax Summary Helpers ====================

    def get_schedule_c_summary(self, tax_year: int) -> dict:
        """Generate a Schedule C style P&L for a tax year."""
        start = date(tax_year, 1, 1)
        end = date(tax_year, 12, 31)

        income_totals = self.get_income_total(start, end)
        expense_totals = self.get_expense_totals(start, end)
        mileage_totals = self.get_mileage_totals(start, end)

        # Gross income excludes collected sales tax (pass-through, not income)
        sales_tax_collected = income_totals.get("sales_tax", 0.0)
        gross_income = income_totals["gross"] - sales_tax_collected

        cogs = expense_totals.get("inventory", 0.0)
        gross_profit = gross_income - cogs

        operating_expenses = sum(
            v for k, v in expense_totals.items() if k != "inventory"
        )
        mileage_deduction = mileage_totals["total_deduction"]

        # Home office deduction (simplified method: $5/sq ft, max 300 sq ft)
        home_office_sqft = float(self.get_setting("home_office_sqft", "0") or 0)
        home_office_deduction = min(home_office_sqft * 5.0, 1500.0) if home_office_sqft > 0 else 0.0

        total_expenses = operating_expenses + mileage_deduction + home_office_deduction

        net_profit = gross_profit - total_expenses
        se_tax = net_profit * 0.9235 * 0.153 if net_profit > 0 else 0.0

        return {
            "gross_income": gross_income,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "expense_breakdown": expense_totals,
            "mileage_deduction": mileage_deduction,
            "home_office_deduction": home_office_deduction,
            "home_office_sqft": home_office_sqft,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "se_tax_estimate": se_tax,
            "platform_fees": income_totals["fees"],
            "shipping_costs": income_totals["shipping"],
            "sales_tax_collected": sales_tax_collected,
        }


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


# CLI interface
if __name__ == "__main__":
    db = get_db()
    
    print("=" * 50)
    print("  myBay — Database Status")
    print("=" * 50)
    print(f"\n  📂 Database: {db.db_path}")
    print(f"  📝 Drafts: {db.draft_count()}")
    print(f"  📦 Listings: {db.listing_count()}")
    print(f"  ✅ Sold: {db.listing_count('SOLD')}")
    
    stats = db.get_today_stats()
    print(f"\n  📊 Today's Stats:")
    print(f"     Listed: {stats.listings_created}")
    print(f"     Sold: {stats.items_sold}")
    print(f"     Revenue: ${stats.revenue:.2f}")
    print(f"     Time Saved: {stats.time_saved_minutes:.0f} min")
    
    totals = db.get_total_stats()
    print(f"\n  🏆 All-Time Totals:")
    print(f"     Listed: {totals['total_listings']}")
    print(f"     Sold: {totals['total_sold']}")
    print(f"     Revenue: ${totals['total_revenue']:.2f}")
    print(f"     Time Saved: {totals['total_time_saved_minutes']:.0f} min")

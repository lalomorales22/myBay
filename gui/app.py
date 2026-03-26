"""
myBay — Desktop GUI

A modern CustomTkinter interface for:
- Reviewing AI-analyzed product drafts
- Editing listing details
- One-click publishing to eBay
- Tracking sales and stats

Run with: python -m gui.app
"""

import sys
import threading
import io
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import customtkinter as ctk
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    print("Required packages not installed. Run:")
    print("  pip install customtkinter pillow")
    sys.exit(1)

from data.database import get_db, Draft, Listing


# ============================================================================
# Theme and Constants
# ============================================================================

# Colors (refined dark theme)
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
    "active_tab": "#2E8BFF",
}

# CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Fonts (SF Pro for macOS, Segoe UI for Windows, fallback to Helvetica)
_FONT_DISPLAY = "SF Pro Display" if sys.platform == "darwin" else "Segoe UI"
_FONT_TEXT = "SF Pro Text" if sys.platform == "darwin" else "Segoe UI"
FONT_TITLE = (_FONT_DISPLAY, 24, "bold")
FONT_HEADING = (_FONT_DISPLAY, 16, "bold")
FONT_BODY = (_FONT_TEXT, 14)
FONT_SMALL = (_FONT_TEXT, 12)


# ============================================================================
# Main Application Window
# ============================================================================

class MyBayApp(ctk.CTk):
    """
    Main application window for myBay.
    
    Layout:
    ┌─────────────────────────────────────────────────────────────┐
    │  Header: Logo + Title + Settings                            │
    ├──────────────┬──────────────────────────────────────────────┤
    │              │                                              │
    │   Draft      │        Main Editor / Dashboard               │
    │   Queue      │                                              │
    │   Sidebar    │                                              │
    │              │                                              │
    ├──────────────┴──────────────────────────────────────────────┤
    │  Status Bar: Stats + QR Code Link                           │
    └─────────────────────────────────────────────────────────────┘
    """
    
    def __init__(self):
        super().__init__()
        
        self.title("myBay")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        default_w = min(1420, max(1080, int(screen_w * 0.94)))
        default_h = min(940, max(700, int(screen_h * 0.90)))
        self.geometry(f"{default_w}x{default_h}")
        self.minsize(980, 640)
        self.configure(fg_color=COLORS["bg_dark"])
        
        # Initialize database
        self.db = get_db()
        
        # Current state
        self.current_draft: Optional[Draft] = None
        self.draft_widgets = {}  # SKU -> widget mapping
        self.sidebar_visible = True
        self.draft_scroll_threshold = 8
        self.activity_scroll_threshold = 5
        self.current_image_paths: list[str] = []
        self.current_image_path: Optional[str] = None
        self.last_listing_url: Optional[str] = None
        self._qr_image = None
        self._camera_url = "http://localhost:8000/camera"
        self._qr_request_id = 0
        self._mousewheel_bound = False
        self.sidebar_restore_btn = None
        self._current_view = "editor"
        self._editor_snapshot: dict = {}
        self._autosave_counter = 0
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Build UI
        self._create_header()
        self._create_split_layout()
        self._create_sidebar()
        self._create_main_content()
        self._create_status_bar()
        self._bind_global_mousewheel()
        
        # Load initial data
        self._refresh_drafts()
        self._update_stats()
        self._load_last_listing_from_db()
        
        # Start background refresh
        self._schedule_refresh()
    
    # ========== Header ==========
    
    def _create_header(self):
        """Create the header with logo and controls."""
        header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=COLORS["bg_card"])
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)
        
        # Logo/Title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        ctk.CTkLabel(
            title_frame, 
            text="📦",
            font=("", 28)
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkLabel(
            title_frame,
            text="myBay",
            font=FONT_TITLE
        ).pack(side="left")
        
        # Right-side buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=20, pady=10, sticky="e")
        
        self._nav_buttons = {}

        nav_items = [
            ("editor", "Listings", self._show_editor),
            ("dashboard", "Dashboard", self._show_dashboard),
            ("admin", "Admin", self._show_admin),
            ("settings", "Settings", self._show_settings),
        ]
        for key, label, cmd in nav_items:
            btn = ctk.CTkButton(
                btn_frame,
                text=label,
                width=100,
                fg_color=COLORS["bg_light"],
                hover_color=COLORS["border"],
                command=cmd,
            )
            btn.pack(side="left", padx=4)
            self._nav_buttons[key] = btn

        self.btn_dashboard = self._nav_buttons["dashboard"]
        self.btn_admin = self._nav_buttons["admin"]
        self.btn_settings = self._nav_buttons["settings"]

    def _create_split_layout(self):
        """Create a draggable split layout for sidebar + main content."""
        self.split = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=COLORS["bg_dark"],
            sashwidth=8,
            showhandle=False,
            bd=0,
        )
        self.split.grid(row=1, column=0, sticky="nsew")

        self.sidebar_host = ctk.CTkFrame(self.split, fg_color=COLORS["bg_card"], corner_radius=0)
        self.main_host = ctk.CTkFrame(self.split, fg_color=COLORS["bg_dark"], corner_radius=0)

        self.split.add(self.sidebar_host, minsize=230, width=290)
        self.split.add(self.main_host, minsize=700)

    def _toggle_sidebar(self):
        """Show/hide the queue sidebar."""
        if self.sidebar_visible:
            self.split.forget(self.sidebar_host)
            self.sidebar_visible = False
            if self.sidebar_restore_btn is not None:
                self.sidebar_restore_btn.place(x=10, y=10)
                self.sidebar_restore_btn.lift()
            self._show_status("Queue hidden")
        else:
            self.split.add(self.sidebar_host, before=self.main_host, minsize=230, width=290)
            self.sidebar_visible = True
            if self.sidebar_restore_btn is not None:
                self.sidebar_restore_btn.place_forget()
            self._show_status("Queue shown")
    
    # ========== Sidebar (Draft Queue) ==========
    
    def _create_sidebar(self):
        """Create the draft queue sidebar."""
        self.sidebar = ctk.CTkFrame(self.sidebar_host, width=280, corner_radius=0, fg_color=COLORS["bg_card"])
        self.sidebar.pack(fill="both", expand=True)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(1, weight=1)
        self.sidebar.grid_propagate(False)
        
        # Sidebar header
        header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            header,
            text="📝 Draft Queue",
            font=FONT_HEADING
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Drag divider to resize",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        header_controls = ctk.CTkFrame(header, fg_color="transparent")
        header_controls.grid(row=0, column=1, sticky="e")

        self.draft_count_label = ctk.CTkLabel(
            header_controls,
            text="0 items",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        )
        self.draft_count_label.pack(side="left", padx=(0, 6))

        self.sidebar_toggle_btn = ctk.CTkButton(
            header_controls,
            text="☰",
            width=28,
            height=24,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            command=self._toggle_sidebar,
        )
        self.sidebar_toggle_btn.pack(side="left")
        
        # Draft list host (switches between compact and scrollable modes)
        self.draft_list_host = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.draft_list_host.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.draft_list_host.grid_columnconfigure(0, weight=1)

        self.draft_list_compact = ctk.CTkFrame(self.draft_list_host, fg_color="transparent")
        self.draft_list_scroll = ctk.CTkScrollableFrame(
            self.draft_list_host,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self.draft_list_active = self.draft_list_compact
        self.draft_list_active.pack(fill="both", expand=True)

        # Keep cards synchronized with pane resizing.
        self.sidebar.bind("<Configure>", self._on_sidebar_resized)
        
        # Refresh button
        ctk.CTkButton(
            self.sidebar,
            text="🔄 Refresh",
            command=self._refresh_drafts,
            height=35,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
        ).grid(row=2, column=0, sticky="ew", padx=15, pady=10)
    
    def _refresh_drafts(self):
        """Refresh the draft queue from database."""
        # Load drafts
        drafts = self.db.get_all_drafts(limit=50)
        self.draft_count_label.configure(text=f"{len(drafts)} items")

        # Use scroll only when queue exceeds current visible capacity.
        self.update_idletasks()
        available_height = max(self.sidebar.winfo_height() - 170, 0)
        dynamic_threshold = max(self.draft_scroll_threshold, available_height // 84) if available_height else self.draft_scroll_threshold
        use_scroll = len(drafts) > dynamic_threshold
        self._set_draft_container(use_scroll)

        # Clear existing items
        for widget in self.draft_list_active.winfo_children():
            widget.destroy()
        self.draft_widgets.clear()
        
        if not drafts:
            ctk.CTkLabel(
                self.draft_list_active,
                text="No drafts yet!\n\nSnap photos from your\nphone to get started.",
                font=FONT_BODY,
                text_color=COLORS["text_muted"],
                justify="center"
            ).pack(pady=40)
            return
        
        # Add draft cards
        for draft in drafts:
            card = self._create_draft_card(draft, self.draft_list_active)
            card.pack(fill="x", padx=5, pady=3)
            self.draft_widgets[draft.sku] = card

        self._resize_draft_cards()
    
    def _set_draft_container(self, use_scroll: bool):
        """Switch between compact and scrollable draft containers."""
        target = self.draft_list_scroll if use_scroll else self.draft_list_compact
        if target == self.draft_list_active:
            return
        self.draft_list_active.pack_forget()
        self.draft_list_active = target
        self.draft_list_active.pack(fill="both", expand=True)

    def _on_sidebar_resized(self, _event=None):
        """Resize draft containers/cards as the pane width changes."""
        self._resize_draft_cards()

    def _resize_draft_cards(self):
        """Resize draft list cards to match current sidebar width."""
        width = max(self.sidebar.winfo_width() - 32, 180)
        self.draft_list_compact.configure(width=width)
        self.draft_list_scroll.configure(width=width)
        for card in self.draft_widgets.values():
            try:
                card.configure(width=max(width - 10, 170))
            except Exception:
                pass

    def _create_draft_card(self, draft: Draft, parent) -> ctk.CTkFrame:
        """Create a clickable card for a draft item."""
        card = ctk.CTkFrame(
            parent,
            corner_radius=10,
            height=78,
            fg_color=COLORS["bg_light"],
            border_width=1,
            border_color=COLORS["border"],
        )
        card.pack_propagate(False)
        
        # Make entire card clickable
        card.bind("<Button-1>", lambda e: self._select_draft(draft))
        
        # Content
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=10, pady=8)
        content.bind("<Button-1>", lambda e: self._select_draft(draft))
        
        # Title (truncated)
        title_text = draft.title[:30] + "..." if len(draft.title) > 30 else draft.title
        title_label = ctk.CTkLabel(
            content,
            text=title_text,
            font=(_FONT_TEXT, 13, "bold"),
            anchor="w"
        )
        title_label.pack(anchor="w")
        title_label.bind("<Button-1>", lambda e: self._select_draft(draft))
        
        # Price and confidence
        info_frame = ctk.CTkFrame(content, fg_color="transparent")
        info_frame.pack(fill="x", pady=(5, 0))
        info_frame.bind("<Button-1>", lambda e: self._select_draft(draft))
        
        price_label = ctk.CTkLabel(
            info_frame,
            text=f"${draft.price:.2f}",
            font=FONT_SMALL,
            text_color=COLORS["success"]
        )
        price_label.pack(side="left")
        price_label.bind("<Button-1>", lambda e: self._select_draft(draft))
        
        # Confidence indicator
        conf_color = COLORS["success"] if draft.ai_confidence >= 0.85 else (
            COLORS["warning"] if draft.ai_confidence >= 0.7 else COLORS["secondary"]
        )
        conf_label = ctk.CTkLabel(
            info_frame,
            text=f"🎯 {draft.ai_confidence*100:.0f}%",
            font=FONT_SMALL,
            text_color=conf_color
        )
        conf_label.pack(side="right")
        conf_label.bind("<Button-1>", lambda e: self._select_draft(draft))
        
        return card
    
    def _select_draft(self, draft: Draft):
        """Select a draft for editing."""
        self.current_draft = draft
        self._show_editor()
        self._load_draft_into_editor(draft)
        
        # Highlight selected card
        for sku, card in self.draft_widgets.items():
            if sku == draft.sku:
                card.configure(fg_color="#0B2A3B", border_color=COLORS["primary"])
            else:
                card.configure(fg_color=COLORS["bg_light"], border_color=COLORS["border"])
    
    # ========== Main Content Area ==========
    
    def _create_main_content(self):
        """Create the main content area (editor/dashboard)."""
        self.main_frame = ctk.CTkFrame(self.main_host, corner_radius=0, fg_color=COLORS["bg_dark"])
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # Left-edge restore toggle shown only when the sidebar is hidden.
        self.sidebar_restore_btn = ctk.CTkButton(
            self.main_frame,
            text="☰",
            width=34,
            height=30,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            command=self._toggle_sidebar,
        )
        self.sidebar_restore_btn.place_forget()
        
        # Create frames for different views
        self._create_editor_view()
        self._create_dashboard_view()
        self._create_settings_view()
        self._create_admin_view()

        # Show editor by default and highlight its nav button
        self._show_editor()
    
    def _create_editor_view(self):
        """Create the listing editor view."""
        self.editor_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        # Two-column layout
        self.editor_frame.grid_columnconfigure(0, weight=3, minsize=320)
        self.editor_frame.grid_columnconfigure(1, weight=4, minsize=430)
        self.editor_frame.grid_rowconfigure(0, weight=1)
        
        # Left column: Image preview
        left_col = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        # Image preview area
        self.image_frame = ctk.CTkFrame(
            left_col,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        self.image_frame.pack(fill="both", expand=True)
        
        self.image_label = ctk.CTkLabel(
            self.image_frame,
            text="📷\n\nSelect a draft\nto preview images",
            font=FONT_BODY,
            text_color=COLORS["text_muted"]
        )
        self.image_label.pack(expand=True)

        # Image tools
        img_tools = ctk.CTkFrame(left_col, fg_color="transparent")
        img_tools.pack(fill="x", pady=(10, 0))

        self.rotate_left_btn = ctk.CTkButton(
            img_tools,
            text="↺ Rotate Left",
            width=140,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            state="disabled",
            command=self._rotate_image_left,
        )
        self.rotate_left_btn.pack(side="left", padx=(0, 8))

        self.rotate_right_btn = ctk.CTkButton(
            img_tools,
            text="↻ Rotate Right",
            width=140,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            state="disabled",
            command=self._rotate_image_right,
        )
        self.rotate_right_btn.pack(side="left")
        
        # Thumbnail strip
        self.thumb_frame = ctk.CTkFrame(left_col, fg_color="transparent", height=80)
        self.thumb_frame.pack(fill="x", pady=(10, 0))
        
        # Right column: Form fields
        right_col_wrap = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        right_col_wrap.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        right_col_wrap.grid_columnconfigure(0, weight=1)
        right_col_wrap.grid_rowconfigure(0, weight=1)

        right_col = ctk.CTkScrollableFrame(
            right_col_wrap,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        right_col.grid(row=0, column=0, sticky="nsew")
        
        # Title
        ctk.CTkLabel(right_col, text="Title", font=FONT_HEADING).pack(anchor="w", pady=(0, 5))
        self.title_entry = ctk.CTkEntry(right_col, height=40, font=FONT_BODY)
        self.title_entry.pack(fill="x", pady=(0, 15))
        
        # Category
        ctk.CTkLabel(right_col, text="Category", font=FONT_HEADING).pack(anchor="w", pady=(0, 5))
        self.category_entry = ctk.CTkEntry(right_col, height=40, font=FONT_BODY)
        self.category_entry.pack(fill="x", pady=(0, 15))
        
        # Condition, Price, and Cost row
        row_frame = ctk.CTkFrame(right_col, fg_color="transparent")
        row_frame.pack(fill="x", pady=(0, 15))
        row_frame.grid_columnconfigure(0, weight=2)
        row_frame.grid_columnconfigure(1, weight=1)
        row_frame.grid_columnconfigure(2, weight=1)

        # Condition
        cond_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        cond_frame.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkLabel(cond_frame, text="Condition", font=FONT_HEADING).pack(anchor="w", pady=(0, 5))
        self.condition_combo = ctk.CTkComboBox(
            cond_frame,
            values=["NEW", "LIKE_NEW", "VERY_GOOD", "GOOD", "ACCEPTABLE"],
            height=40,
            font=FONT_BODY
        )
        self.condition_combo.pack(fill="x")

        # Price
        price_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        price_frame.grid(row=0, column=1, sticky="ew", padx=(10, 5))
        ctk.CTkLabel(price_frame, text="Price ($)", font=FONT_HEADING).pack(anchor="w", pady=(0, 5))
        self.price_entry = ctk.CTkEntry(price_frame, height=40, font=FONT_BODY)
        self.price_entry.pack(fill="x")

        # Cost (cost basis for COGS tracking)
        cost_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        cost_frame.grid(row=0, column=2, sticky="ew", padx=(5, 0))
        ctk.CTkLabel(cost_frame, text="Cost ($)", font=FONT_HEADING).pack(anchor="w", pady=(0, 5))
        self.cost_entry = ctk.CTkEntry(cost_frame, height=40, font=FONT_BODY, placeholder_text="0.00")
        self.cost_entry.pack(fill="x")
        
        # Quantity row
        qty_row = ctk.CTkFrame(right_col, fg_color="transparent")
        qty_row.pack(fill="x", pady=(10, 0))
        qty_row.grid_columnconfigure(0, weight=1)
        qty_row.grid_columnconfigure(1, weight=1)
        
        # Quantity
        qty_frame = ctk.CTkFrame(qty_row, fg_color="transparent")
        qty_frame.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkLabel(qty_frame, text="Quantity", font=FONT_HEADING).pack(anchor="w", pady=(0, 5))
        self.quantity_entry = ctk.CTkEntry(qty_frame, height=40, font=FONT_BODY, placeholder_text="1")
        self.quantity_entry.pack(fill="x")
        self.quantity_entry.insert(0, "1")
        
        # Format (Buy It Now vs Auction)
        format_frame = ctk.CTkFrame(qty_row, fg_color="transparent")
        format_frame.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        ctk.CTkLabel(format_frame, text="Format", font=FONT_HEADING).pack(anchor="w", pady=(0, 5))
        self.format_combo = ctk.CTkComboBox(
            format_frame,
            values=["Buy It Now", "Auction"],
            height=40,
            font=FONT_BODY
        )
        self.format_combo.pack(fill="x")
        self.format_combo.set("Buy It Now")
        
        # Description
        ctk.CTkLabel(right_col, text="Description", font=FONT_HEADING).pack(anchor="w", pady=(0, 5))
        self.desc_text = ctk.CTkTextbox(right_col, height=120, font=FONT_BODY)
        self.desc_text.pack(fill="x", pady=(0, 15))
        
        # AI Confidence indicator
        conf_frame = ctk.CTkFrame(right_col, fg_color="transparent")
        conf_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(conf_frame, text="AI Confidence:", font=FONT_BODY).pack(side="left")
        self.confidence_bar = ctk.CTkProgressBar(conf_frame, width=150)
        self.confidence_bar.pack(side="left", padx=10)
        self.confidence_bar.set(0)
        self.confidence_label = ctk.CTkLabel(conf_frame, text="0%", font=FONT_BODY)
        self.confidence_label.pack(side="left")
        
        # Action buttons
        btn_frame = ctk.CTkFrame(right_col_wrap, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        
        self.save_btn = ctk.CTkButton(
            btn_frame,
            text="💾 Save Draft",
            width=1,
            height=45,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            command=self._save_draft
        )
        self.save_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))
        
        self.publish_btn = ctk.CTkButton(
            btn_frame,
            text="🚀 Publish to eBay",
            width=1,
            height=45,
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            command=self._publish_listing
        )
        self.publish_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 8))

        self.open_listing_btn = ctk.CTkButton(
            btn_frame,
            text="🔗 Open Listing",
            width=1,
            height=45,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            state="disabled",
            command=self._open_last_listing,
        )
        self.open_listing_btn.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        
        self.delete_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️",
            width=1,
            height=45,
            fg_color=COLORS["secondary"],
            hover_color="#CC3355",
            command=self._delete_draft
        )
        self.delete_btn.grid(row=1, column=1, sticky="ew", padx=(6, 0))
    
    def _create_dashboard_view(self):
        """Create the dashboard/stats view."""
        self.dashboard_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.dashboard_frame.grid_columnconfigure(0, weight=1)
        self.dashboard_frame.grid_columnconfigure(1, weight=1)
        
        # Title
        ctk.CTkLabel(
            self.dashboard_frame,
            text="📊 Dashboard",
            font=FONT_TITLE
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=30, pady=20)
        
        # Stats cards
        self._create_stat_cards()
        
        # Recent activity
        self._create_recent_activity()
        
        # QR Code section
        self._create_qr_section()
    
    def _create_stat_cards(self):
        """Create stat cards for dashboard."""
        cards_frame = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        cards_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        
        for i in range(4):
            cards_frame.grid_columnconfigure(i, weight=1)
        
        # Today's stats
        self.stat_cards = {}
        stats = [
            ("today_listed", "📦 Listed Today", "0", COLORS["primary"]),
            ("today_sold", "💰 Sold Today", "0", COLORS["success"]),
            ("today_revenue", "💵 Revenue Today", "$0", COLORS["warning"]),
            ("time_saved", "⏱️ Time Saved", "0 min", COLORS["secondary"]),
        ]
        
        for i, (key, label, value, color) in enumerate(stats):
            card = ctk.CTkFrame(
                cards_frame,
                corner_radius=12,
                fg_color=COLORS["bg_card"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.grid(row=0, column=i, sticky="ew", padx=10, pady=10)
            
            ctk.CTkLabel(card, text=label, font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(pady=(15, 5))
            value_label = ctk.CTkLabel(card, text=value, font=(_FONT_DISPLAY, 28, "bold"), text_color=color)
            value_label.pack(pady=(0, 15))
            
            self.stat_cards[key] = value_label

        # All-time summary row
        alltime_frame = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        alltime_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=30, pady=(0, 5))
        # Re-grid today's cards to row 1, alltime to a sub-row via a wrapper
        cards_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(10, 0))
        alltime_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=30, pady=(0, 5))

        self._alltime_label = ctk.CTkLabel(
            alltime_frame,
            text="All-time: 0 listed | 0 sold | $0 revenue | 0 min saved",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
        )
        self._alltime_label.pack(anchor="w")

    def _create_recent_activity(self):
        """Create recent activity section."""
        self.activity_frame = ctk.CTkFrame(
            self.dashboard_frame,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        self.activity_frame.grid(row=3, column=0, sticky="nsew", padx=30, pady=10)
        
        ctk.CTkLabel(
            self.activity_frame,
            text="📜 Recent Listings",
            font=FONT_HEADING
        ).pack(anchor="w", padx=20, pady=15)

        self.activity_list_host = ctk.CTkFrame(self.activity_frame, fg_color="transparent")
        self.activity_list_host.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.activity_list_compact = ctk.CTkFrame(self.activity_list_host, fg_color="transparent")
        self.activity_list_scroll = ctk.CTkScrollableFrame(
            self.activity_list_host,
            fg_color="transparent",
            height=200,
            scrollbar_button_color=COLORS["bg_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self.activity_list_active = self.activity_list_compact
        self.activity_list = self.activity_list_active
        self.activity_list_active.pack(fill="both", expand=True)

    def _set_activity_container(self, use_scroll: bool):
        """Switch between compact and scrollable recent-list containers."""
        target = self.activity_list_scroll if use_scroll else self.activity_list_compact
        if target == self.activity_list_active:
            return
        self.activity_list_active.pack_forget()
        self.activity_list_active = target
        self.activity_list = target
        self.activity_list_active.pack(fill="both", expand=True)
    
    def _create_qr_section(self):
        """Create QR code section for phone access."""
        self.qr_frame = ctk.CTkFrame(
            self.dashboard_frame,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        self.qr_frame.grid(row=3, column=1, sticky="nsew", padx=30, pady=10)
        
        ctk.CTkLabel(
            self.qr_frame,
            text="📱 Phone Camera",
            font=FONT_HEADING
        ).pack(anchor="w", padx=20, pady=15)
        
        self.qr_url_label = ctk.CTkLabel(
            self.qr_frame,
            text=self._camera_url,
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.qr_url_label.pack(fill="x", padx=20, pady=(0, 8))

        self.qr_display_frame = ctk.CTkFrame(self.qr_frame, fg_color="transparent")
        self.qr_display_frame.pack(expand=True, fill="both", pady=20)

        # QR placeholder / image slot
        self.qr_label = ctk.CTkLabel(
            self.qr_display_frame,
            text="Loading QR code...",
            font=FONT_BODY,
            text_color=COLORS["text_muted"]
        )
        self.qr_label.pack(expand=True)
        
        self.qr_btn_row = ctk.CTkFrame(self.qr_frame, fg_color="transparent")
        btn_row = self.qr_btn_row
        btn_row.pack(pady=(0, 14))

        ctk.CTkButton(
            btn_row,
            text="🔄 Refresh QR",
            width=120,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            command=self._refresh_qr_code,
        ).pack(side="left")

        self._refresh_qr_code()

    def _refresh_qr_code(self):
        """Fetch and render the QR code inside the app."""
        self._qr_request_id += 1
        request_id = self._qr_request_id
        self._set_qr_label(text="Loading QR code...", image=None)
        threading.Thread(target=self._fetch_qr_code, args=(request_id,), daemon=True).start()

    def _set_qr_label(self, text: Optional[str] = None, image=None):
        """Safely update QR label content and recover from stale image handles."""
        if not hasattr(self, "qr_label"):
            return

        try:
            kwargs = {"image": image}
            if text is not None:
                kwargs["text"] = text
            self.qr_label.configure(**kwargs)
            return
        except tk.TclError:
            pass

        # Recreate label if Tk image handle became invalid.
        try:
            self.qr_label.destroy()
        except Exception:
            pass

        self.qr_label = ctk.CTkLabel(
            self.qr_display_frame,
            text=text or "",
            font=FONT_BODY,
            text_color=COLORS["text_muted"],
        )
        self.qr_label.pack(expand=True)
        if image is not None:
            self.qr_label.configure(image=image)

    def _queue_on_ui(self, callback):
        """Schedule a callback on the UI loop if the window still exists."""
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except (RuntimeError, tk.TclError):
            # App is closing or UI loop is no longer available.
            pass

    def _apply_qr_success(self, request_id: int, image_bytes: bytes, camera_url: str):
        """Apply QR content on the Tk main thread."""
        if request_id != self._qr_request_id:
            return

        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.thumbnail((250, 250))
            self._qr_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self._camera_url = camera_url
            self._set_qr_label(image=self._qr_image, text="")
            if hasattr(self, "qr_url_label"):
                self.qr_url_label.configure(text=camera_url)
            self._show_status("✅ QR ready. Scan from your phone camera.")
        except Exception as e:
            self._apply_qr_error(request_id, str(e))

    def _apply_qr_error(self, request_id: int, error_text: str):
        """Show QR loading errors on the Tk main thread."""
        if request_id != self._qr_request_id:
            return
        self._set_qr_label(text="⚠️ Camera server offline\n\nStart with: python run.py", image=None)
        if hasattr(self, "qr_url_label"):
            self.qr_url_label.configure(text="http://localhost:8000/camera")
        self._show_status(f"⚠️ QR unavailable: {error_text}")

    def _fetch_qr_code(self, request_id: int):
        """Background QR loader to keep UI responsive."""
        try:
            import httpx

            qr_data = httpx.get("http://localhost:8000/qr/data", timeout=4.0)
            qr_data.raise_for_status()
            camera_url = qr_data.json().get("camera_url", "http://localhost:8000/camera")

            qr_image_response = httpx.get("http://localhost:8000/qr", timeout=6.0)
            qr_image_response.raise_for_status()
            image_bytes = qr_image_response.content
            self._queue_on_ui(lambda rid=request_id, b=image_bytes, u=camera_url: self._apply_qr_success(rid, b, u))
        except Exception as e:
            error_text = str(e)
            self._queue_on_ui(lambda rid=request_id, err=error_text: self._apply_qr_error(rid, err))

    def _opt_in_selling_policies(self):
        """Opt in to SELLING_POLICY_MANAGEMENT for sandbox accounts."""
        if self.env_var.get() != "sandbox":
            self._show_status("⚠️ Opt-in is only needed for Sandbox.")
            return

        self._show_status("⏳ Opting into sandbox business policies...")

        def run_opt_in():
            try:
                from ebay import get_inventory
                inv = get_inventory()
                inv.opt_in_to_program("SELLING_POLICY_MANAGEMENT")
                self.after(0, lambda: self._show_status("✅ Sandbox policy program enabled"))
            except Exception as e:
                self.after(0, lambda err=str(e): self._show_status(f"❌ Opt-in failed: {err}"))

        threading.Thread(target=run_opt_in, daemon=True).start()
    
    def _create_settings_view(self):
        """Create the settings view."""
        self.settings_frame = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        
        # Title
        ctk.CTkLabel(
            self.settings_frame,
            text="⚙️ Settings",
            font=FONT_TITLE
        ).pack(anchor="w", padx=30, pady=20)
        
        # eBay API Credentials Card
        creds_card = ctk.CTkFrame(
            self.settings_frame,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        creds_card.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(creds_card, text="🔑 eBay API Credentials", font=FONT_HEADING).pack(anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(
            creds_card,
            text="Get these from developer.ebay.com → Your Account → Application Keys",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        ).pack(anchor="w", padx=20, pady=(0, 10))
        
        # Client ID
        ctk.CTkLabel(creds_card, text="Client ID (App ID):", font=FONT_BODY).pack(anchor="w", padx=20, pady=(5, 0))
        self.client_id_entry = ctk.CTkEntry(creds_card, width=400, placeholder_text="Enter your Client ID")
        self.client_id_entry.pack(anchor="w", padx=20, pady=(2, 5))
        
        # Client Secret
        ctk.CTkLabel(creds_card, text="Client Secret (Cert ID):", font=FONT_BODY).pack(anchor="w", padx=20, pady=(5, 0))
        self.client_secret_entry = ctk.CTkEntry(creds_card, width=400, placeholder_text="Enter your Client Secret", show="•")
        self.client_secret_entry.pack(anchor="w", padx=20, pady=(2, 5))
        
        # RuName
        ctk.CTkLabel(creds_card, text="RuName (Redirect URL Name):", font=FONT_BODY).pack(anchor="w", padx=20, pady=(5, 0))
        self.runame_entry = ctk.CTkEntry(creds_card, width=400, placeholder_text="Enter your RuName")
        self.runame_entry.pack(anchor="w", padx=20, pady=(2, 5))
        
        # Environment selector
        env_frame = ctk.CTkFrame(creds_card, fg_color="transparent")
        env_frame.pack(anchor="w", padx=20, pady=10)
        ctk.CTkLabel(env_frame, text="Environment:", font=FONT_BODY).pack(side="left", padx=(0, 10))
        self.env_var = ctk.StringVar(value="sandbox")
        ctk.CTkRadioButton(env_frame, text="Sandbox (Testing)", variable=self.env_var, value="sandbox").pack(side="left", padx=5)
        ctk.CTkRadioButton(env_frame, text="Production (Live)", variable=self.env_var, value="production").pack(side="left", padx=5)
        
        # Reload credentials when environment changes
        self.env_var.trace_add("write", lambda *args: self._on_env_change())
        
        # Save credentials button
        ctk.CTkButton(
            creds_card,
            text="💾 Save Credentials",
            command=self._save_ebay_credentials
        ).pack(anchor="w", padx=20, pady=(5, 15))
        
        # eBay Connection Card
        ebay_card = ctk.CTkFrame(
            self.settings_frame,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        ebay_card.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(ebay_card, text="🔗 eBay Account Connection", font=FONT_HEADING).pack(anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(
            ebay_card,
            text="After saving credentials above, connect your eBay seller account",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        ).pack(anchor="w", padx=20, pady=(0, 10))
        
        self.ebay_status_label = ctk.CTkLabel(
            ebay_card,
            text="❌ Not connected",
            font=FONT_BODY,
            text_color=COLORS["text_muted"]
        )
        self.ebay_status_label.pack(anchor="w", padx=20, pady=(0, 10))
        
        # Button row for Connect and Refresh
        btn_row = ctk.CTkFrame(ebay_card, fg_color="transparent")
        btn_row.pack(anchor="w", padx=20, pady=(0, 15))
        
        ctk.CTkButton(
            btn_row,
            text="🔐 Connect eBay Account",
            command=self._connect_ebay
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            btn_row,
            text="🔄 Refresh",
            width=80,
            fg_color="gray40",
            command=self._refresh_ebay_status
        ).pack(side="left")
        
        ctk.CTkButton(
            btn_row,
            text="📋 Paste Code",
            width=100,
            fg_color="gray40",
            command=self._paste_oauth_code
        ).pack(side="left", padx=(10, 0))

        self.opt_in_btn = ctk.CTkButton(
            btn_row,
            text="🧩 Opt-in Policies",
            width=140,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            command=self._opt_in_selling_policies,
        )
        self.opt_in_btn.pack(side="left", padx=(10, 0))
        
        # Load existing credentials (set environment from saved config on initial load)
        self._load_ebay_credentials(set_env_from_config=True)
        
        # Turbo Mode
        turbo_card = ctk.CTkFrame(
            self.settings_frame,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        turbo_card.pack(fill="x", padx=30, pady=10)
        
        turbo_row = ctk.CTkFrame(turbo_card, fg_color="transparent")
        turbo_row.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(turbo_row, text="⚡ Turbo Mode", font=FONT_HEADING).pack(side="left")
        self.turbo_switch = ctk.CTkSwitch(turbo_row, text="", command=self._toggle_turbo)
        self.turbo_switch.pack(side="right")
        
        ctk.CTkLabel(
            turbo_card,
            text="Auto-publish listings with AI confidence ≥ 90%",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        ).pack(anchor="w", padx=20, pady=(0, 15))
        
        # Default Pricing
        pricing_card = ctk.CTkFrame(
            self.settings_frame,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        pricing_card.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(pricing_card, text="💵 Default Markup", font=FONT_HEADING).pack(anchor="w", padx=20, pady=(15, 5))
        
        markup_frame = ctk.CTkFrame(pricing_card, fg_color="transparent")
        markup_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        self.markup_slider = ctk.CTkSlider(markup_frame, from_=0, to=50, number_of_steps=50)
        self.markup_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.markup_slider.set(10)
        
        self.markup_label = ctk.CTkLabel(markup_frame, text="10%", font=FONT_BODY)
        self.markup_label.pack(side="right")
        
        self.markup_slider.configure(command=lambda v: self.markup_label.configure(text=f"{int(v)}%"))
        
        # Server Status
        server_card = ctk.CTkFrame(
            self.settings_frame,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        server_card.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(server_card, text="🌐 Camera Server", font=FONT_HEADING).pack(anchor="w", padx=20, pady=(15, 5))
        
        self.server_status_label = ctk.CTkLabel(
            server_card,
            text="Run 'python run.py' to start",
            font=FONT_BODY,
            text_color=COLORS["text_muted"]
        )
        self.server_status_label.pack(anchor="w", padx=20, pady=(0, 15))

        # AI Backend Card
        ai_card = ctk.CTkFrame(
            self.settings_frame,
            corner_radius=12,
            fg_color=COLORS["bg_card"],
            border_width=1,
            border_color=COLORS["border"],
        )
        ai_card.pack(fill="x", padx=30, pady=10)

        ctk.CTkLabel(ai_card, text="🤖 AI Backend", font=FONT_HEADING).pack(anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(
            ai_card,
            text="Choose between OpenAI (cloud) and Ollama (local, free)",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Radio buttons
        from core.presets import get_presets as _get_presets
        _p = _get_presets()
        self._ai_backend_var = ctk.StringVar(value=_p.ai_backend)

        ai_radio_frame = ctk.CTkFrame(ai_card, fg_color="transparent")
        ai_radio_frame.pack(anchor="w", padx=20, pady=(0, 5))
        ctk.CTkRadioButton(ai_radio_frame, text="OpenAI (cloud)", variable=self._ai_backend_var, value="openai").pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(ai_radio_frame, text="Ollama (local)", variable=self._ai_backend_var, value="ollama").pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(ai_radio_frame, text="Auto-detect", variable=self._ai_backend_var, value="auto").pack(side="left")

        # Ollama-specific fields
        ollama_frame = ctk.CTkFrame(ai_card, fg_color="transparent")
        ollama_frame.pack(fill="x", padx=20, pady=(5, 5))

        ctk.CTkLabel(ollama_frame, text="Ollama Model:", font=FONT_SMALL).pack(anchor="w")
        self._ollama_model_entry = ctk.CTkEntry(ollama_frame, width=300, placeholder_text="qwen3.5:2b")
        self._ollama_model_entry.insert(0, _p.ollama_model)
        self._ollama_model_entry.pack(anchor="w", pady=(2, 5))

        ctk.CTkLabel(ollama_frame, text="Ollama URL:", font=FONT_SMALL).pack(anchor="w")
        self._ollama_url_entry = ctk.CTkEntry(ollama_frame, width=300, placeholder_text="http://localhost:11434")
        self._ollama_url_entry.insert(0, _p.ollama_url)
        self._ollama_url_entry.pack(anchor="w", pady=(2, 5))

        # Action row: Test + Save
        ai_btn_row = ctk.CTkFrame(ai_card, fg_color="transparent")
        ai_btn_row.pack(anchor="w", padx=20, pady=(5, 10))

        ctk.CTkButton(
            ai_btn_row, text="Test Connection", width=130, fg_color="gray40",
            command=self._test_ai_connection,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            ai_btn_row, text="💾 Save AI Settings",
            command=self._save_ai_settings,
        ).pack(side="left")

        self._ai_test_label = ctk.CTkLabel(
            ai_card, text="", font=FONT_SMALL, text_color=COLORS["text_muted"]
        )
        self._ai_test_label.pack(anchor="w", padx=20, pady=(0, 15))

    def _test_ai_connection(self):
        """Test whichever AI backend is selected."""
        backend = self._ai_backend_var.get()
        try:
            if backend == "ollama":
                from core.ollama import check_ollama_status, get_ollama_models
                url = self._ollama_url_entry.get().strip() or "http://localhost:11434"
                if check_ollama_status(url):
                    models = get_ollama_models(url)
                    self._ai_test_label.configure(
                        text=f"Ollama OK — models: {', '.join(models[:4])}",
                        text_color=COLORS["success"],
                    )
                else:
                    self._ai_test_label.configure(
                        text="Ollama not reachable. Is it running? (ollama serve)",
                        text_color=COLORS["error"],
                    )
            elif backend == "openai":
                from core.vision import ProductAnalyzer
                analyzer = ProductAnalyzer()
                if analyzer.check_openai_status():
                    self._ai_test_label.configure(
                        text=f"OpenAI OK — model: {analyzer.model}",
                        text_color=COLORS["success"],
                    )
                else:
                    self._ai_test_label.configure(
                        text="OpenAI check failed. Verify key and billing.",
                        text_color=COLORS["error"],
                    )
            else:
                from core.analyzer_factory import detect_available_backend
                result = detect_available_backend()
                if result:
                    self._ai_test_label.configure(
                        text=f"Auto-detected: {result}",
                        text_color=COLORS["success"],
                    )
                else:
                    self._ai_test_label.configure(
                        text="No AI backend detected.",
                        text_color=COLORS["error"],
                    )
        except Exception as e:
            self._ai_test_label.configure(
                text=f"Error: {e}", text_color=COLORS["error"],
            )

    def _save_ai_settings(self):
        """Save AI backend settings to presets."""
        from core.presets import get_presets, save_presets
        presets = get_presets()
        presets.ai_backend = self._ai_backend_var.get()
        presets.ollama_model = self._ollama_model_entry.get().strip() or "qwen3.5:2b"
        presets.ollama_url = self._ollama_url_entry.get().strip() or "http://localhost:11434"
        save_presets(presets)
        self._ai_test_label.configure(text="Settings saved!", text_color=COLORS["success"])

    # ========== Status Bar ==========
    
    def _create_status_bar(self):
        """Create the bottom status bar."""
        status_bar = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color=COLORS["bg_card"])
        status_bar.grid(row=2, column=0, sticky="ew")
        status_bar.grid_columnconfigure(1, weight=1)
        
        # Stats summary
        self.status_label = ctk.CTkLabel(
            status_bar,
            text="📊 Ready",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        )
        self.status_label.grid(row=0, column=0, padx=20, pady=8, sticky="w")
        
        # Quick actions
        quick_frame = ctk.CTkFrame(status_bar, fg_color="transparent")
        quick_frame.grid(row=0, column=2, padx=20, pady=5, sticky="e")
        
        self.open_last_btn = ctk.CTkButton(
            quick_frame,
            text="🔗 Open Last",
            width=105,
            height=28,
            font=FONT_SMALL,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["border"],
            state="disabled",
            command=self._open_last_listing,
        )
        self.open_last_btn.pack(side="left", padx=5)
    
    # ========== View Navigation ==========
    
    def _create_admin_view(self):
        """Create the admin/business backend view."""
        from gui.admin_view import AdminView
        self._admin_view = AdminView(self.main_frame, self.db)
        self.admin_frame = self._admin_view.frame

    def _highlight_nav(self, active_key: str):
        """Highlight the active nav button."""
        for key, btn in self._nav_buttons.items():
            if key == active_key:
                btn.configure(fg_color=COLORS["active_tab"], hover_color=COLORS["primary_hover"])
            else:
                btn.configure(fg_color=COLORS["bg_light"], hover_color=COLORS["border"])

    def _get_editor_state(self) -> dict:
        """Capture current editor field values for dirty-checking."""
        if not self.current_draft:
            return {}
        try:
            return {
                "title": self.title_entry.get(),
                "category": self.category_entry.get(),
                "condition": self.condition_combo.get(),
                "price": self.price_entry.get(),
                "cost": self.cost_entry.get(),
                "quantity": self.quantity_entry.get(),
                "format": self.format_combo.get(),
                "description": self.desc_text.get("1.0", "end").strip(),
            }
        except Exception:
            return {}

    def _has_unsaved_changes(self) -> bool:
        """Check if editor fields differ from last save/load."""
        if not self.current_draft or not self._editor_snapshot:
            return False
        return self._get_editor_state() != self._editor_snapshot

    def _leaving_editor_ok(self) -> bool:
        """Prompt to save if leaving editor with unsaved changes. Returns True if ok to proceed."""
        if self._current_view != "editor" or not self._has_unsaved_changes():
            return True
        result = messagebox.askyesnocancel(
            "Unsaved Changes",
            "You have unsaved changes. Save before leaving?"
        )
        if result is None:  # Cancel
            return False
        if result:  # Yes - save first
            self._save_draft()
        return True

    def _show_editor(self):
        """Show the editor view."""
        self._current_view = "editor"
        self.dashboard_frame.grid_forget()
        self.settings_frame.grid_forget()
        self.admin_frame.grid_forget()
        self.editor_frame.grid(row=0, column=0, sticky="nsew")
        self._highlight_nav("editor")

    def _show_dashboard(self):
        """Show the dashboard view."""
        if not self._leaving_editor_ok():
            return
        self._current_view = "dashboard"
        self.editor_frame.grid_forget()
        self.settings_frame.grid_forget()
        self.admin_frame.grid_forget()
        self.dashboard_frame.grid(row=0, column=0, sticky="nsew")
        self._highlight_nav("dashboard")
        self._update_stats()
        self._update_recent_activity()
        self._refresh_qr_code()

    def _show_settings(self):
        """Show the settings view."""
        if not self._leaving_editor_ok():
            return
        self._current_view = "settings"
        self.editor_frame.grid_forget()
        self.dashboard_frame.grid_forget()
        self.admin_frame.grid_forget()
        self.settings_frame.grid(row=0, column=0, sticky="nsew")
        self._highlight_nav("settings")
        self._update_ebay_status()

    def _show_admin(self):
        """Show the admin/business backend view."""
        if not self._leaving_editor_ok():
            return
        self._current_view = "admin"
        self.editor_frame.grid_forget()
        self.dashboard_frame.grid_forget()
        self.settings_frame.grid_forget()
        self.admin_frame.grid(row=0, column=0, sticky="nsew")
        self._highlight_nav("admin")
    
    # ========== Editor Actions ==========
    
    def _load_draft_into_editor(self, draft: Draft):
        """Load a draft into the editor form."""
        # Clear fields
        self.title_entry.delete(0, "end")
        self.category_entry.delete(0, "end")
        self.price_entry.delete(0, "end")
        self.cost_entry.delete(0, "end")
        self.quantity_entry.delete(0, "end")
        self.desc_text.delete("1.0", "end")

        # Fill fields
        self.title_entry.insert(0, draft.title)
        self.category_entry.insert(0, draft.category_name or draft.category_id)
        self.condition_combo.set(draft.condition)
        self.price_entry.insert(0, f"{draft.price:.2f}")
        if draft.cost_basis:
            self.cost_entry.insert(0, f"{draft.cost_basis:.2f}")
        self.quantity_entry.insert(0, str(draft.quantity))
        self.format_combo.set(draft.listing_format.replace("_", " ").title() if draft.listing_format else "Buy It Now")
        self.desc_text.insert("1.0", draft.description)
        
        # Update confidence
        self.confidence_bar.set(draft.ai_confidence)
        self.confidence_label.configure(text=f"{draft.ai_confidence*100:.0f}%")
        
        # Load images
        self._load_images(draft.image_paths)

        # Snapshot for unsaved-changes detection
        self._editor_snapshot = self._get_editor_state()
    
    def _load_images(self, image_paths: list):
        """Load and display images."""
        self.current_image_paths = list(image_paths or [])
        self.current_image_path = None

        # Clear thumbnails
        for widget in self.thumb_frame.winfo_children():
            widget.destroy()
        
        if not image_paths:
            self.image_label.configure(image=None, text="📷\n\nNo images")
            self._set_rotate_buttons_enabled(False)
            return
        
        # Try to load first image as main preview
        main_path = Path(image_paths[0])
        if main_path.exists():
            self._show_image(str(main_path))
        else:
            self.image_label.configure(image=None, text=f"📷\n\nImage not found\n{main_path.name}")
            self._set_rotate_buttons_enabled(False)
        
        # Load thumbnails
        for i, path in enumerate(image_paths[:5]):
            thumb_path = Path(path)
            if thumb_path.exists():
                try:
                    img = Image.open(thumb_path)
                    img.thumbnail((60, 60))
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=(60, 60))
                    thumb_btn = ctk.CTkButton(
                        self.thumb_frame,
                        image=photo,
                        text="",
                        width=65,
                        height=65,
                        fg_color="gray30",
                        command=lambda p=path: self._show_image(p)
                    )
                    thumb_btn.pack(side="left", padx=3)
                except Exception:
                    pass
    
    def _show_image(self, path: str):
        """Show a specific image in the main preview."""
        img_path = Path(path)
        if img_path.exists():
            try:
                img = Image.open(img_path)
                img = ImageOps.exif_transpose(img)
                img.thumbnail((350, 350))
                photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.image_label.configure(image=photo, text="")
                self.image_label.image = photo
                self.current_image_path = str(img_path)
                self._set_rotate_buttons_enabled(True)
            except Exception:
                self.image_label.configure(image=None, text=f"📷\n\nCouldn't load image\n{img_path.name}")
                self.current_image_path = None
                self._set_rotate_buttons_enabled(False)
        else:
            self.image_label.configure(image=None, text=f"📷\n\nImage not found\n{img_path.name}")
            self.current_image_path = None
            self._set_rotate_buttons_enabled(False)

    def _set_rotate_buttons_enabled(self, enabled: bool):
        """Enable/disable rotate controls based on image availability."""
        state = "normal" if enabled else "disabled"
        self.rotate_left_btn.configure(state=state)
        self.rotate_right_btn.configure(state=state)

    def _rotate_image_left(self):
        """Rotate currently previewed image 90° counter-clockwise."""
        self._rotate_current_image(90)

    def _rotate_image_right(self):
        """Rotate currently previewed image 90° clockwise."""
        self._rotate_current_image(-90)

    def _rotate_current_image(self, angle: int):
        """Rotate current image file and refresh preview + thumbnails."""
        if not self.current_image_path:
            self._show_status("⚠️ Select an image first")
            return

        img_path = Path(self.current_image_path)
        if not img_path.exists():
            self._show_status("⚠️ Image file not found")
            return

        try:
            # Load fully into memory before closing file handle, then save
            img = Image.open(img_path)
            img.load()  # force full read into memory
            original_format = img.format
            img = ImageOps.exif_transpose(img)
            rotated = img.rotate(angle, expand=True)
            img.close()

            suffix = img_path.suffix.lower()
            save_kwargs = {}
            fmt = None
            if suffix in (".jpg", ".jpeg"):
                if rotated.mode not in ("RGB", "L"):
                    rotated = rotated.convert("RGB")
                fmt = "JPEG"
                save_kwargs["quality"] = 95
            elif suffix == ".png":
                fmt = "PNG"
            elif original_format:
                fmt = original_format

            if fmt:
                rotated.save(img_path, format=fmt, **save_kwargs)
            else:
                rotated.save(img_path, **save_kwargs)

            # Refresh thumbnails and preview while preserving current image selection
            self._load_images(self.current_image_paths)
            self._show_image(str(img_path))
            self._show_status("✅ Image rotated")
        except Exception as e:
            self._show_status(f"❌ Rotate failed: {e}")

    def _open_last_listing(self):
        """Open the last successfully published eBay listing."""
        if not self.last_listing_url:
            self._show_status("⚠️ No listing URL available yet")
            return
        try:
            import webbrowser
            webbrowser.open(self.last_listing_url)
            self._show_status("🌐 Opened listing in browser")
        except Exception as e:
            self._show_status(f"❌ Could not open listing: {e}")

    def _open_listing_by_id(self, listing_id: Optional[str], environment: Optional[str] = None):
        """Open a specific listing by eBay listing ID."""
        normalized_listing_id = self._normalize_listing_id(listing_id)
        if not normalized_listing_id:
            self._show_status("⚠️ Listing ID is missing")
            return
        url = self._resolve_listing_url(normalized_listing_id, environment)
        self._set_last_listing_url(url)
        self._open_last_listing()

    @staticmethod
    def _normalize_listing_id(listing_id: Optional[str]) -> Optional[str]:
        """
        Normalize eBay listing IDs for browser links.

        Handles both legacy numeric IDs and REST-style IDs like `v1|<id>|0`.
        """
        if listing_id is None:
            return None

        raw = str(listing_id).strip()
        if not raw:
            return None

        if "|" in raw:
            for token in raw.split("|"):
                token = token.strip()
                if token.isdigit():
                    return token

        return raw

    def _is_listing_url_reachable(self, url: str) -> bool:
        """Check whether a listing URL resolves (HTTP 200)."""
        try:
            import httpx
            response = httpx.get(url, timeout=3.0, follow_redirects=True)
            return response.status_code == 200
        except Exception:
            return False

    def _get_canonical_listing_url(self, listing_id: str, environment: str) -> Optional[str]:
        """
        Ask eBay Browse API for canonical itemWebUrl in the target environment.

        This is more reliable than guessing /itm/<id> patterns, especially in
        sandbox where hostname/path behavior can vary.
        """
        normalized_listing_id = self._normalize_listing_id(listing_id) or listing_id
        if environment not in {"sandbox", "production"}:
            return None

        try:
            from ebay.config import get_config
            from ebay.inventory import get_inventory

            config = get_config()
            original_env = config._active_environment
            try:
                config._active_environment = environment
                inv = get_inventory()
                return inv.get_item_web_url(normalized_listing_id)
            finally:
                config._active_environment = original_env
        except Exception:
            return None

    def _verify_listing_on_ebay(
        self,
        inv,
        listing_id: str,
        environment: str,
        max_attempts: int = 5,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Verify a freshly published listing via eBay Browse API.

        Returns:
            (verified, canonical_url, error_message)
        """
        normalized_listing_id = self._normalize_listing_id(listing_id) or listing_id
        if not normalized_listing_id:
            return False, None, "Missing listing ID"

        last_error: Optional[str] = None

        for attempt in range(1, max_attempts + 1):
            try:
                item_url = inv.get_item_web_url(normalized_listing_id)
                if item_url:
                    return True, item_url, None
                last_error = "Browse API did not return itemWebUrl yet"
            except Exception as e:
                last_error = str(e)

            if attempt < max_attempts:
                # Give eBay indexing a moment before retrying.
                import time
                time.sleep(0.8 * attempt)

        env_label = environment if environment in {"sandbox", "production"} else "unknown"
        return False, None, f"{env_label}: {last_error or 'verification not available'}"

    def _resolve_listing_url(self, listing_id: str, environment: Optional[str] = None) -> str:
        """
        Resolve listing URL using preferred environment first, then fallback.

        This prevents dead links when older local rows were missing the
        environment or when a listing ID is opened under the wrong domain.
        """
        normalized_listing_id = self._normalize_listing_id(listing_id) or listing_id

        preferred_env = environment if environment in {"sandbox", "production"} else None
        if preferred_env:
            env_candidates = [preferred_env, "production" if preferred_env == "sandbox" else "sandbox"]
        else:
            try:
                from ebay.config import get_config
                current_env = get_config().environment.value
            except Exception:
                current_env = "sandbox"
            env_candidates = [current_env, "production" if current_env == "sandbox" else "sandbox"]

        for env_name in env_candidates:
            canonical_url = self._get_canonical_listing_url(normalized_listing_id, env_name)
            if canonical_url:
                if preferred_env and env_name != preferred_env:
                    print(f"⚠️ Listing URL fallback: requested {preferred_env}, opened {env_name} for {normalized_listing_id}")
                return canonical_url

        for env_name in env_candidates:
            candidate_url = f"{self._get_listing_base_url(env_name)}{normalized_listing_id}"
            if self._is_listing_url_reachable(candidate_url):
                if preferred_env and env_name != preferred_env:
                    print(f"⚠️ Listing URL fallback: requested {preferred_env}, opened {env_name} for {normalized_listing_id}")
                return candidate_url

        return f"{self._get_listing_base_url(env_candidates[0])}{normalized_listing_id}"

    def _get_listing_base_url(self, environment: Optional[str] = None) -> str:
        """Return listing URL base for a specific eBay environment."""
        env = environment
        try:
            if env not in {"sandbox", "production"}:
                from ebay.config import get_config
                env = get_config().environment.value
        except Exception:
            env = "sandbox"

        return "https://cgi.sandbox.ebay.com/itm/" if env == "sandbox" else "https://www.ebay.com/itm/"

    def _set_last_listing_url(self, url: Optional[str]):
        """Set last listing URL and synchronize related buttons."""
        self.last_listing_url = url
        state = "normal" if url else "disabled"
        if hasattr(self, "open_listing_btn"):
            self.open_listing_btn.configure(state=state)
        if hasattr(self, "open_last_btn"):
            self.open_last_btn.configure(state=state)

    def _load_last_listing_from_db(self):
        """Load the most recent listing URL from local database on startup."""
        try:
            listings = self.db.get_recent_listings(limit=1)
            if listings:
                listing_id = self._normalize_listing_id(listings[0].ebay_listing_id)
                if listing_id:
                    listing_url = f"{self._get_listing_base_url(listings[0].environment)}{listing_id}"
                    self._set_last_listing_url(listing_url)
                    return
        except Exception:
            pass

        self._set_last_listing_url(None)
    
    def _save_draft(self):
        """Save the current draft."""
        if not self.current_draft:
            return

        # Validate price
        price_str = self.price_entry.get().strip()
        try:
            price = float(price_str)
            if price < 0:
                self._show_status("⚠️ Price cannot be negative")
                return
        except ValueError:
            if price_str:
                self._show_status("⚠️ Price must be a number (e.g. 29.99)")
                return
            price = 0

        # Validate quantity
        qty_str = self.quantity_entry.get().strip()
        try:
            quantity = int(qty_str)
            if quantity < 1:
                self._show_status("⚠️ Quantity must be at least 1")
                return
        except ValueError:
            if qty_str:
                self._show_status("⚠️ Quantity must be a whole number")
                return
            quantity = 1

        # Validate cost
        cost_str = self.cost_entry.get().strip()
        try:
            cost = float(cost_str) if cost_str else 0.0
            if cost < 0:
                self._show_status("Cost cannot be negative")
                return
        except ValueError:
            if cost_str:
                self._show_status("Cost must be a number (e.g. 5.00)")
                return
            cost = 0.0

        # Update draft from form
        self.current_draft.title = self.title_entry.get()
        self.current_draft.category_name = self.category_entry.get()
        self.current_draft.condition = self.condition_combo.get()
        self.current_draft.price = price
        self.current_draft.cost_basis = cost
        self.current_draft.quantity = quantity
        
        # Convert format combo to enum value
        format_map = {"Buy It Now": "FIXED_PRICE", "Auction": "AUCTION"}
        self.current_draft.listing_format = format_map.get(self.format_combo.get(), "FIXED_PRICE")
        
        self.current_draft.description = self.desc_text.get("1.0", "end").strip()
        
        # Save to database
        self.db.update_draft(self.current_draft)
        
        self._editor_snapshot = self._get_editor_state()
        self._show_status("✅ Draft saved!")
        self._refresh_drafts()
    
    def _publish_listing(self):
        """Publish the current draft to eBay."""
        if not self.current_draft:
            return
        
        # Save first
        self._save_draft()
        
        # Check for eBay connection
        try:
            from ebay.config import get_config
            config = get_config()
            if not config.has_valid_token:
                self._show_status("❌ Please connect your eBay account first")
                return
        except ImportError:
            self._show_status("❌ eBay module not available")
            return
        
        self._show_status("🚀 Publishing to eBay...")
        
        # Run in background thread
        def do_publish():
            try:
                from ebay import get_inventory
                
                inv = get_inventory()
                draft = self.current_draft
                
                # Get category ID if we don't have one
                category_id = draft.category_id
                if not category_id and draft.category_name:
                    try:
                        from ebay import suggest_category
                        suggestions = suggest_category(draft.title)
                        if suggestions:
                            category_id = suggestions[0].category_id
                    except Exception as cat_err:
                        print(f"⚠️ Category suggestion failed (continuing anyway): {cat_err}")
                
                # Use a default leaf category if still none (Everything Else > Every Other Thing)
                if not category_id:
                    category_id = "88433"  # Leaf category that works well for sandbox fallback
                    print(f"⚠️ Using default category ID: {category_id}")
                
                # Upload images to eBay Picture Services
                image_urls = []
                if draft.image_paths:
                    from ebay.images import upload_images as ebay_upload_images
                    self._show_status("Uploading images to eBay...")

                    def _on_progress(current, total, result):
                        status = "ok" if result.success else "failed"
                        self.after(0, lambda c=current, t=total, s=status:
                            self._show_status(f"Uploading image {c}/{t}... {s}"))

                    batch = ebay_upload_images(draft.image_paths, on_progress=_on_progress)
                    image_urls = batch.successful_urls

                    if not batch.any_successful:
                        errors = "; ".join(r.error for r in batch.failed if r.error)
                        self._show_status(f"❌ All image uploads failed: {errors}")
                        from tkinter import messagebox
                        messagebox.showerror(
                            "Image Upload Failed",
                            f"Could not upload any images to eBay:\n\n{errors}"
                        )
                        return

                    if batch.failed:
                        print(f"⚠️ {len(batch.failed)}/{len(draft.image_paths)} images failed, continuing with {len(image_urls)}")
                
                # Quick list
                result = inv.quick_list(
                    sku=draft.sku,
                    title=draft.title,
                    description=draft.description,
                    price=draft.price,
                    category_id=category_id,
                    image_urls=image_urls,
                    condition=draft.condition,
                    quantity=draft.quantity,
                    listing_format=draft.listing_format,
                    aspects=draft.aspects,
                )
                
                if result.success:
                    publish_env = inv.config.environment.value if getattr(inv, "config", None) else "sandbox"
                    listing_id = self._normalize_listing_id(result.listing_id)

                    if not listing_id:
                        offer_hint = f" (offer {result.offer_id})" if result.offer_id else ""
                        warn_msg = (
                            "⚠️ Publish completed but eBay did not return a usable listing ID."
                            f"{offer_hint} Check Seller Hub and refresh."
                        )
                        print(warn_msg)
                        self.after(0, lambda msg=warn_msg: self._show_status(msg))
                        return

                    verified, verified_url, verify_error = self._verify_listing_on_ebay(
                        inv=inv,
                        listing_id=listing_id,
                        environment=publish_env,
                    )
                    if verified:
                        print(f"✅ API verification passed for {listing_id} ({publish_env})")
                    else:
                        print(f"⚠️ API verification pending for {listing_id}: {verify_error}")

                    # Add to listings DB
                    listing = Listing(
                        sku=draft.sku,
                        ebay_listing_id=listing_id,
                        title=draft.title,
                        price=draft.price,
                        status="ACTIVE",
                        environment=publish_env,
                    )
                    self.db.add_listing(listing)
                    
                    # Remove draft
                    self.db.delete_draft(draft.sku)
                    
                    try:
                        listing_url = verified_url or self._resolve_listing_url(listing_id, publish_env)
                        print(f"✅ Published listing URL: {listing_url}")
                        self._set_last_listing_url(listing_url)
                    except Exception:
                        pass

                    if verified:
                        status_msg = f"✅ Published + API verified on {publish_env}! Listing ID: {listing_id}"
                    else:
                        status_msg = f"✅ Published to {publish_env} (API verify pending). Listing ID: {listing_id}"

                    self.after(0, lambda msg=status_msg: self._show_status(msg))
                    self.after(0, self._refresh_drafts)
                    self.after(0, lambda: setattr(self, 'current_draft', None))
                else:
                    error_msg = result.errors[0].get('message', 'Unknown error') if result.errors else 'Unknown error'
                    print(f"❌ eBay Publish Failed: {error_msg}")
                    print(f"   Full errors: {result.errors}")
                    self.after(0, lambda msg=error_msg: self._show_status(f"❌ Failed: {msg}"))
                    
            except Exception as e:
                import traceback
                err_str = str(e)
                print(f"❌ Exception during publish: {err_str}")
                traceback.print_exc()

                # Map common errors to user-friendly messages
                friendly = err_str
                err_lower = err_str.lower()
                if "connect" in err_lower and ("refused" in err_lower or "error" in err_lower):
                    friendly = "Could not connect to eBay. Check your internet connection."
                elif "401" in err_str or "unauthorized" in err_lower:
                    friendly = "eBay session expired. Go to Settings and reconnect your account."
                elif "403" in err_str or "forbidden" in err_lower:
                    friendly = "eBay denied this request. Your account may need additional permissions."
                elif "timeout" in err_lower or "timed out" in err_lower:
                    friendly = "eBay took too long to respond. Try again in a moment."
                elif "rate" in err_lower and "limit" in err_lower:
                    friendly = "Too many requests to eBay. Wait a minute and try again."
                elif "token" in err_lower and ("expired" in err_lower or "invalid" in err_lower):
                    friendly = "eBay login expired. Go to Settings and reconnect."

                self.after(0, lambda msg=friendly: self._show_status(f"❌ {msg}"))
                if friendly != err_str:
                    self.after(0, lambda: messagebox.showerror(
                        "Publish Failed", f"{friendly}\n\nTechnical detail: {err_str[:200]}"))
        
        threading.Thread(target=do_publish, daemon=True).start()
    
    def _delete_draft(self):
        """Delete the current draft."""
        if not self.current_draft:
            return
        
        title = self.current_draft.title or self.current_draft.sku
        if not messagebox.askyesno("Delete Draft", f"Delete this draft?\n\n{title}"):
            return

        self.db.delete_draft(self.current_draft.sku)
        self.current_draft = None
        
        self._show_status("🗑️ Draft deleted")
        self._refresh_drafts()
        
        # Clear editor
        self.title_entry.delete(0, "end")
        self.category_entry.delete(0, "end")
        self.price_entry.delete(0, "end")
        self.cost_entry.delete(0, "end")
        self.desc_text.delete("1.0", "end")
        self.current_image_paths = []
        self.current_image_path = None
        self._set_rotate_buttons_enabled(False)
        self.image_label.configure(image=None, text="📷\n\nSelect a draft")
    
    # ========== Stats & Dashboard ==========
    
    def _update_stats(self):
        """Update dashboard statistics."""
        stats = self.db.get_today_stats()
        
        if hasattr(self, 'stat_cards'):
            self.stat_cards["today_listed"].configure(text=str(stats.listings_created))
            self.stat_cards["today_sold"].configure(text=str(stats.items_sold))
            self.stat_cards["today_revenue"].configure(text=f"${stats.revenue:.2f}")
            self.stat_cards["time_saved"].configure(text=f"{stats.time_saved_minutes:.0f} min")

        if hasattr(self, '_alltime_label'):
            totals = self.db.get_total_stats()
            self._alltime_label.configure(
                text=(
                    f"All-time: {totals['total_listings']} listed"
                    f" | {totals['total_sold']} sold"
                    f" | ${totals['total_revenue']:,.2f} revenue"
                    f" | {totals['total_time_saved_minutes']:.0f} min saved"
                )
            )
    
    def _update_recent_activity(self):
        """Update recent activity list."""
        if not hasattr(self, 'activity_list_host'):
            return

        # Get recent listings
        listings = self.db.get_recent_listings(limit=10)

        # Only use scroll when there are enough listings to overflow visible space.
        self.update_idletasks()
        available_height = max(self.activity_list_host.winfo_height() - 8, 0)
        dynamic_threshold = (
            max(self.activity_scroll_threshold, available_height // 34)
            if available_height else self.activity_scroll_threshold
        )
        use_scroll = len(listings) > dynamic_threshold
        self._set_activity_container(use_scroll)

        # Clear existing
        for widget in self.activity_list_active.winfo_children():
            widget.destroy()
        
        if not listings:
            ctk.CTkLabel(
                self.activity_list_active,
                text="No listings yet",
                font=FONT_BODY,
                text_color=COLORS["text_muted"]
            ).pack(pady=20)
            return
        
        for listing in listings:
            row = ctk.CTkFrame(self.activity_list_active, fg_color="transparent")
            row.pack(fill="x", pady=3)
            
            status_emoji = "✅" if listing.status == "ACTIVE" else "💰" if listing.status == "SOLD" else "⏹️"
            env_badge = "SBX" if listing.environment == "sandbox" else "LIVE" if listing.environment == "production" else "?"
            
            ctk.CTkLabel(
                row,
                text=f"{status_emoji} [{env_badge}] {listing.title[:34]}...",
                font=FONT_SMALL,
                anchor="w"
            ).pack(side="left", fill="x", expand=True)
            
            ctk.CTkLabel(
                row,
                text=f"${listing.price:.2f}",
                font=FONT_SMALL,
                text_color=COLORS["success"]
            ).pack(side="right", padx=(8, 0))

            ctk.CTkButton(
                row,
                text="Delete",
                width=68,
                height=24,
                font=FONT_SMALL,
                fg_color=COLORS["secondary"],
                hover_color="#CC3355",
                command=lambda item=listing: self._delete_recent_listing(item),
            ).pack(side="right", padx=(6, 0))

            if listing.ebay_listing_id:
                ctk.CTkButton(
                    row,
                    text="Open",
                    width=62,
                    height=24,
                    font=FONT_SMALL,
                    fg_color=COLORS["bg_light"],
                    hover_color=COLORS["border"],
                    command=lambda lid=listing.ebay_listing_id, env=listing.environment: self._open_listing_by_id(lid, env),
                ).pack(side="right")

    def _delete_recent_listing(self, listing: Listing):
        """Delete a listing row from dashboard history (local DB only)."""
        title = listing.title or listing.sku
        confirm = messagebox.askyesno(
            "Delete Listing History",
            (
                f"Remove this listing from the dashboard?\n\n"
                f"{title}\n\n"
                "This only deletes the local history row. "
                "It does NOT end/remove the live eBay listing."
            ),
        )
        if not confirm:
            return

        deleted = self.db.delete_listing(listing.sku)
        if not deleted:
            self._show_status("⚠️ Listing not found in local history")
            return

        self._update_recent_activity()
        self._load_last_listing_from_db()
        self._show_status("🗑️ Removed listing from dashboard history")
    
    # ========== Settings Actions ==========
    
    def _update_ebay_status(self):
        """Update eBay connection status for the selected environment."""
        try:
            from ebay.config import get_config
            config = get_config()
            config.reload()  # Reload to pick up any changes from OAuth callback
            
            environment = self.env_var.get()
            creds = config.get_credentials_for_env(environment)
            env_label = "Sandbox" if environment == "sandbox" else "Production"
            if hasattr(self, "opt_in_btn"):
                if environment == "sandbox":
                    self.opt_in_btn.pack(side="left", padx=(10, 0))
                    self.opt_in_btn.configure(state="normal", text="Opt-in Policies")
                else:
                    self.opt_in_btn.pack_forget()
            
            # Check if this environment has saved credentials
            if creds and creds.client_id:
                # Check if we have tokens for this environment
                # Temporarily switch to check token status
                original_env = config._active_environment
                config._active_environment = environment
                has_token = config.has_valid_token
                tokens = config.tokens
                config._active_environment = original_env
                
                if has_token:
                    # Show username if available
                    username = tokens.username if tokens and tokens.username else None
                    if username:
                        status_text = f"✅ {env_label}: {username}"
                    else:
                        status_text = f"✅ Connected ({env_label})"
                    self.ebay_status_label.configure(
                        text=status_text,
                        text_color=COLORS["success"]
                    )
                else:
                    self.ebay_status_label.configure(
                        text=f"⚠️ {env_label}: Credentials saved - click Connect",
                        text_color=COLORS["warning"]
                    )
            else:
                self.ebay_status_label.configure(
                    text=f"❌ {env_label}: Not configured",
                    text_color=COLORS["secondary"]
                )
        except ImportError:
            self.ebay_status_label.configure(
                text="❌ eBay module not available",
                text_color=COLORS["text_muted"]
            )
    
    def _load_ebay_credentials(self, set_env_from_config: bool = False):
        """Load existing eBay credentials into the form for the selected environment.
        
        Args:
            set_env_from_config: If True, sets the environment selector from saved config
        """
        try:
            from ebay.config import get_config
            config = get_config()
            
            # On initial load, set the environment from saved config
            if set_env_from_config:
                self.env_var.set(config._active_environment)
            
            # Get credentials for the currently selected environment
            env = self.env_var.get()
            creds = config.get_credentials_for_env(env)
            
            # Clear current entries
            self.client_id_entry.delete(0, "end")
            self.client_secret_entry.delete(0, "end")
            self.runame_entry.delete(0, "end")
            
            if creds:
                if creds.client_id:
                    self.client_id_entry.insert(0, creds.client_id)
                if creds.client_secret:
                    self.client_secret_entry.insert(0, creds.client_secret)
                if creds.ru_name:
                    self.runame_entry.insert(0, creds.ru_name)
        except Exception:
            pass  # No credentials saved yet
    
    def _on_env_change(self):
        """Called when environment radio button changes."""
        self._load_ebay_credentials()
        self._update_ebay_status()
    
    def _save_ebay_credentials(self):
        """Save eBay API credentials."""
        client_id = self.client_id_entry.get().strip()
        client_secret = self.client_secret_entry.get().strip()
        ru_name = self.runame_entry.get().strip()
        environment = self.env_var.get()
        
        if not client_id or not client_secret or not ru_name:
            self._show_status("❌ Please fill in all credential fields")
            return
        
        try:
            from ebay import setup_credentials
            setup_credentials(
                client_id=client_id,
                client_secret=client_secret,
                ru_name=ru_name,
                environment=environment
            )
            env_label = "Sandbox" if environment == "sandbox" else "Production"
            self._show_status(f"✅ {env_label} credentials saved! Now click 'Connect eBay Account'")
        except Exception as e:
            self._show_status(f"❌ Error saving: {str(e)}")
    
    def _paste_oauth_code(self):
        """Manually paste OAuth code (workaround when callback URL doesn't work)."""
        from urllib.parse import unquote
        import tkinter as tk
        
        # Create dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Paste OAuth Code")
        dialog.geometry("500x300")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 500) // 2
        y = self.winfo_y() + (self.winfo_height() - 300) // 2
        dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(
            dialog,
            text="📋 Paste OAuth Code",
            font=FONT_HEADING
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            dialog,
            text="After logging into eBay, copy the 'code' parameter from the URL\nor paste the entire URL:",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
            wraplength=450
        ).pack(pady=(0, 10))
        
        code_entry = ctk.CTkTextbox(dialog, height=100, width=450)
        code_entry.pack(pady=10)
        
        status_label = ctk.CTkLabel(dialog, text="", font=FONT_SMALL)
        status_label.pack(pady=5)
        
        def submit_code():
            raw_input = code_entry.get("1.0", "end").strip()
            
            # Extract code from URL if full URL was pasted
            code = raw_input
            if "code=" in raw_input:
                # Parse code from URL
                import re
                match = re.search(r'code=([^&]+)', raw_input)
                if match:
                    code = unquote(match.group(1))
            else:
                # Might be URL-encoded code directly
                code = unquote(raw_input)
            
            if not code:
                status_label.configure(text="❌ Please paste a code or URL", text_color=COLORS["error"])
                return
            
            try:
                from ebay.config import get_config
                from ebay.auth import get_auth
                
                config = get_config()
                environment = self.env_var.get()
                config.set_active_environment(environment)
                
                auth = get_auth()
                status_label.configure(text="⏳ Exchanging code for tokens...", text_color=COLORS["warning"])
                dialog.update()
                
                tokens = auth.exchange_code_for_token(code)
                
                # Try to fetch user info
                try:
                    user_info = auth.get_user_info()
                    if user_info:
                        tokens.username = user_info.get("username")
                        tokens.user_id = user_info.get("userId")
                        config.tokens = tokens
                except:
                    pass
                
                env_label = "Sandbox" if environment == "sandbox" else "Production"
                status_label.configure(text=f"✅ Connected to {env_label}!", text_color=COLORS["success"])
                self._update_ebay_status()
                self._show_status(f"✅ eBay {env_label} connected!")
                
                # Close after short delay
                dialog.after(1500, dialog.destroy)
                
            except Exception as e:
                error_msg = str(e)
                if "invalid_grant" in error_msg.lower():
                    error_msg = "Code expired - try logging in again"
                status_label.configure(text=f"❌ {error_msg}", text_color=COLORS["error"])
        
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=15)
        
        ctk.CTkButton(btn_row, text="✅ Submit", command=submit_code).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Cancel", fg_color="gray40", command=dialog.destroy).pack(side="left", padx=5)
    
    def _connect_ebay(self):
        """Start eBay OAuth flow."""
        try:
            # Check if credentials are configured for selected environment
            from ebay.config import get_config
            config = get_config()
            
            environment = self.env_var.get()
            creds = config.get_credentials_for_env(environment)
            
            if not creds or not creds.client_id or not creds.client_secret or not creds.ru_name:
                env_label = "Sandbox" if environment == "sandbox" else "Production"
                self._show_status(f"❌ Please save {env_label} API credentials first")
                return
            
            # Set the active environment
            config.set_active_environment(environment)
            
            env_label = "Sandbox" if environment == "sandbox" else "Production"
            from ebay.auth import start_auth_flow
            start_auth_flow()
            self._show_status(f"🔐 Opening eBay {env_label} login in browser...")
        except Exception as e:
            self._show_status(f"❌ {str(e)}")
    
    def _refresh_ebay_status(self):
        """Refresh eBay connection status and fetch user info if needed."""
        try:
            from ebay.config import get_config
            from ebay.auth import get_auth
            
            config = get_config()
            config.reload()  # Reload from file to pick up tokens saved by OAuth callback
            environment = self.env_var.get()
            
            # Temporarily switch environment to check/update
            original_env = config._active_environment
            config._active_environment = environment
            
            # If connected but no username, try to fetch it
            if config.has_valid_token:
                tokens = config.tokens
                if tokens and not tokens.username:
                    auth = get_auth()
                    user_info = auth.get_user_info()
                    if user_info:
                        tokens.username = user_info.get("username")
                        tokens.user_id = user_info.get("userId")
                        config.tokens = tokens  # Save updated tokens
            
            config._active_environment = original_env
            
            # Update display
            self._update_ebay_status()
            self._show_status("🔄 Status refreshed")
        except Exception as e:
            self._show_status(f"❌ Refresh failed: {str(e)}")
    
    def _toggle_turbo(self):
        """Toggle turbo mode."""
        enabled = self.turbo_switch.get()
        self.db.set_setting("turbo_mode", "1" if enabled else "0")
        self._show_status("⚡ Turbo Mode: " + ("ON" if enabled else "OFF"))
    
    def _open_qr_page(self):
        """Jump to dashboard and refresh in-app QR display."""
        self._show_dashboard()
        self._refresh_qr_code()

    def _bind_global_mousewheel(self):
        """Bind mousewheel once and route it to the visible scrollable views."""
        if self._mousewheel_bound:
            return
        self.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_global_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_global_mousewheel, add="+")
        self._mousewheel_bound = True

    def _is_widget_descendant(self, widget, ancestor) -> bool:
        """Return True when widget is ancestor itself or a child/grandchild."""
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            try:
                parent_name = current.winfo_parent()
                if not parent_name:
                    break
                current = current.nametowidget(parent_name)
            except Exception:
                break
        return False

    def _on_global_mousewheel(self, event):
        """Ensure mouse wheel scroll works reliably for settings on desktop."""
        if not hasattr(self, "settings_frame"):
            return
        try:
            if not self.settings_frame.winfo_ismapped():
                return
            hovered = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        except Exception:
            return

        if hovered is None or not self._is_widget_descendant(hovered, self.settings_frame):
            return

        canvas = getattr(self.settings_frame, "_parent_canvas", None)
        if canvas is None:
            return

        if getattr(event, "num", None) == 4:
            steps = -1
        elif getattr(event, "num", None) == 5:
            steps = 1
        else:
            delta = int(getattr(event, "delta", 0))
            if delta == 0:
                return
            # macOS typically emits small deltas; Windows emits ±120 multiples.
            steps = int(-delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)

        try:
            canvas.yview_scroll(steps, "units")
            return "break"
        except Exception:
            return
    
    # ========== Utilities ==========
    
    def _show_status(self, message: str):
        """Show a status message."""
        if hasattr(self, "status_label"):
            self.status_label.configure(text=message)
    
    def _schedule_refresh(self):
        """Schedule periodic data refresh."""
        # Refresh drafts every 5 seconds
        self.after(5000, self._auto_refresh)
    
    def _auto_refresh(self):
        """Auto-refresh data and autosave drafts."""
        self._refresh_drafts()
        self._update_stats()
        # Autosave every ~30 seconds (6 cycles * 5s each)
        self._autosave_counter += 1
        if self._autosave_counter >= 6:
            self._autosave_counter = 0
            if (self._current_view == "editor"
                    and self.current_draft
                    and self._has_unsaved_changes()):
                # Sync form -> draft object -> DB (quiet, no status refresh)
                try:
                    d = self.current_draft
                    d.title = self.title_entry.get()
                    d.category_name = self.category_entry.get()
                    d.condition = self.condition_combo.get()
                    d.price = float(self.price_entry.get() or 0)
                    d.cost_basis = float(self.cost_entry.get() or 0)
                    d.quantity = int(self.quantity_entry.get() or 1)
                    fmt_map = {"Buy It Now": "FIXED_PRICE", "Auction": "AUCTION"}
                    d.listing_format = fmt_map.get(self.format_combo.get(), "FIXED_PRICE")
                    d.description = self.desc_text.get("1.0", "end").strip()
                    self.db.update_draft(d)
                    self._editor_snapshot = self._get_editor_state()
                    self._show_status("Auto-saved draft")
                except (ValueError, Exception):
                    pass  # skip autosave if form has invalid data
        self._schedule_refresh()


# ============================================================================
# Entry Point
# ============================================================================

def run_app():
    """Run the myBay GUI."""
    app = MyBayApp()
    app.mainloop()


if __name__ == "__main__":
    run_app()

# myBay V2 — Implementation Plan

## Handoff Notes

This document is a complete implementation plan for myBay V2. It was created by a prior Claude session that did a full codebase audit, security review, and landing page redesign. Use this as your roadmap — it contains everything you need to implement each phase without re-exploring the codebase from scratch.

### What was done in the prior session
- Full codebase audit: no leaked API keys, no hardcoded secrets, `.gitignore` is solid
- Removed all "joey" references from application code (only remnants are in `venv/` shebangs from old path — gitignored, harmless, fix with `rm -rf venv && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`)
- Updated OpenAI model from `gpt-4o` to `gpt-5.4-nano-2026-03-17` in `core/vision.py:28`, `README.md` (4 places), `.env.example`
- Created `HOW_TO_USE.md` — full setup guide for new users
- Completely redesigned `landing-page/index.php` — premium dark-mode product page with CSS app mockups, feature grid, FAQ, setup guide, download CTAs. Admin backend preserved untouched.
- Deleted old `landing-page/landing.sqlite` so it regenerates with fresh seed data

### Key architecture you need to know

**AI pipeline pattern (the thing you'll extend most):**
- `core/vision.py` — `ProductAnalyzer` class uses `httpx.Client` (sync) to call OpenAI's Responses API at `{base_url}/responses`
- Model is set via: `DEFAULT_OPENAI_MODEL` constant (line 28) overridden by `OPENAI_VISION_MODEL` env var (line 235)
- Auth: Bearer token in header, key from `OPENAI_API_KEY` env var
- Output: `ProductData` dataclass (line 109) with fields: title, brand, model, size, category_keywords, condition, color, material, description, suggested_price_usd, confidence_score
- Web search: Uses OpenAI's `web_search_preview` tool for live market pricing — this is the thing Ollama can't do
- `core/assistant.py` — `BusinessAssistant` class reuses the same pattern (imports `_load_runtime_env`, `OPENAI_BASE_URL`, `DEFAULT_OPENAI_MODEL` from vision.py)

**Publish flow** (`gui/app.py` `_publish_listing()` around line 1696):
1. Pre-flight: validate draft exists, save it, check eBay token
2. Background thread: category resolution → image upload to eBay Picture Services → `inv.quick_list()` → verification via Browse API → create Listing record in DB → delete Draft → refresh UI

**Presets system** (`core/presets.py`):
- `MybayPresets` dataclass holds: shipping, returns, location, pricing, policy IDs, turbo settings
- Persisted to SQLite, singleton pattern via `get_presets()`/`save_presets()`
- `is_ready_to_list` property checks all required fields are set

**Setup wizard** (`gui/wizard.py`):
- 5 steps: OpenAI check → eBay OAuth → Location → Policies/Preferences → Done
- `CTkToplevel` modal, 600x500px
- Each step validates before allowing "Next"

**Startup** (`run.py`):
- `run_gui()` starts: camera server thread → file watcher thread → GUI (blocking)
- Server: FastAPI on port 8000, endpoints: `/camera`, `/upload`, `/qr`, `/ws`, `/health`
- Watcher: monitors `./queue/` for new images, triggers AI analysis, creates Draft in DB

**Dependencies** (`requirements.txt`):
- HTTP: `httpx==0.28.1` (sync + async)
- Server: `fastapi==0.128.7`, `uvicorn==0.40.0`
- GUI: `customtkinter==5.2.2`
- Images: `Pillow==12.1.0`, optional `rembg==2.0.72`
- eBay pricing uses `httpx.AsyncClient`

**Test suite**: 80 tests across `tests/test_phase{1-5}.py`. Run with `pytest tests/ -v`.

---

## Phase 1: Ollama Integration (Local AI)

**Goal:** Users can analyze products with zero API keys and zero cost using a local Ollama model. OpenAI remains available as the premium option.

**Why this is Phase 1:** It removes the #1 adoption barrier. Right now every user needs an OpenAI account, a credit card, and an API key before they can even try the app. With Ollama, they download the app, install Ollama, pull a model, and they're listing. Zero accounts, zero cost.

### 1.1 — Create `core/ollama.py`

New module that provides an `OllamaAnalyzer` class with the same interface as `ProductAnalyzer`.

```
File: core/ollama.py
Class: OllamaAnalyzer
Constructor: (model: str = None, base_url: str = "http://localhost:11434", timeout: float = 120.0)
Key method: analyze_images(image_paths: list[str | Path], additional_context: str = "") -> ProductData
```

**Implementation details:**
- Use `httpx.Client` (same pattern as vision.py) to call Ollama's API at `POST {base_url}/api/chat`
- Ollama's vision API accepts base64 images in the `images` field of a message
- Send the same system prompt used in vision.py (extract it into a shared constant or function)
- Parse the response into the same `ProductData` dataclass
- The JSON schema enforcement trick: include a strict JSON template in the prompt since Ollama doesn't support OpenAI's `response_format` parameter natively. Use the same `_parse_json()` repair logic from assistant.py as fallback.
- Default model: `llava:7b` (best balance of quality and resource usage)
- Model override via `OLLAMA_VISION_MODEL` env var
- Add `check_ollama_status() -> bool` method that hits `GET {base_url}/api/tags` to verify Ollama is running and the model is pulled

**What Ollama CAN'T do that OpenAI can:**
- Web search for live market pricing. Solution: after Ollama generates the product analysis, call `ebay/pricing.py`'s `PricingIntelligence.analyze()` with the product title to get market pricing. This already exists and uses eBay's Browse API (free, no OpenAI needed). Wire it up as a post-analysis step.

**Recommended Ollama models (document these for users):**

| Model | Size | RAM | Speed | Notes |
|-------|------|-----|-------|-------|
| `moondream` | 1.7B | ~2GB | Fast | Lightest option, good for basic product ID |
| `llava:7b` | 7B | ~5GB | Medium | **Recommended default** — solid quality |
| `llama3.2-vision:11b` | 11B | ~8GB | Slower | Best local quality |
| `minicpm-v` | 3B | ~3GB | Fast | Good middle ground |

### 1.2 — Create `core/analyzer_factory.py`

Thin factory that returns the right analyzer based on user preference.

```python
def get_analyzer(backend: str = None) -> ProductAnalyzer | OllamaAnalyzer:
    """
    backend: "openai", "ollama", or None (auto-detect from env/presets)
    Auto-detect priority:
      1. If OLLAMA_VISION_MODEL is set and Ollama is running → OllamaAnalyzer
      2. If OPENAI_API_KEY is set → ProductAnalyzer
      3. If Ollama is running (any model available) → OllamaAnalyzer
      4. Raise clear error with setup instructions
    """
```

This replaces direct `ProductAnalyzer()` construction throughout the codebase. Search for `ProductAnalyzer(` to find all call sites — they're in:
- `core/watcher.py` (line ~80, the `QueueWatcher` class)
- `gui/wizard.py` (line ~140, OpenAI check step)
- `gui/app.py` (if any direct construction)
- `tests/test_phase1.py`

### 1.3 — Update `core/watcher.py`

The file watcher creates a `ProductAnalyzer` to process queued images. Change it to use `get_analyzer()` instead. The watcher callback flow stays the same — it just gets its analyzer from the factory.

### 1.4 — Add eBay pricing fallback for Ollama

When using Ollama (which can't do web search), add a post-analysis step:

```python
# In the watcher or integration layer, after analyze_images():
if isinstance(analyzer, OllamaAnalyzer) and product_data.suggested_price_usd <= 0:
    pricing = PricingIntelligence()
    analysis = await pricing.analyze(product_data.title, condition=product_data.condition)
    if analysis and analysis.suggested_price > 0:
        product_data.suggested_price_usd = analysis.suggested_price
```

`PricingIntelligence` uses `httpx.AsyncClient` so you'll need to handle the sync/async bridge. Options:
- Use `asyncio.run()` in the watcher thread (it has its own thread, no event loop conflict)
- Or add a `get_market_price_sync()` wrapper (pricing.py may already have one — check)

### 1.5 — Update `MybayPresets` in `core/presets.py`

Add new fields to the `MybayPresets` dataclass:

```python
ai_backend: str = "auto"  # "openai", "ollama", "auto"
ollama_model: str = "llava:7b"
ollama_url: str = "http://localhost:11434"
```

Update `save()` and `load()` to handle these new fields (they serialize to JSON in SQLite, so just adding fields should be backward-compatible — test with an existing DB).

### 1.6 — Update Setup Wizard (`gui/wizard.py`)

**Modify Step 0** (currently "OpenAI Check") to become "AI Setup":
- Add a toggle/selector: "OpenAI (cloud)" vs "Ollama (local, free)"
- If Ollama selected:
  - Check if Ollama is running (`check_ollama_status()`)
  - If not running, show install instructions: `brew install ollama && ollama serve`
  - Check if vision model is pulled (`GET /api/tags`)
  - If no model, show: `ollama pull llava:7b` with a "Check Again" button
  - If model ready, show green checkmark and continue
- If OpenAI selected: existing flow (validate API key)
- Save choice to presets

### 1.7 — Update Settings UI in `gui/app.py`

Add an "AI Backend" section in Settings view:
- Radio buttons: OpenAI / Ollama / Auto-detect
- If Ollama: model selector dropdown, custom URL field, "Test Connection" button
- If OpenAI: existing API key field + model override field
- Show which backend is currently active

### 1.8 — Update `.env.example`

Add:
```env
# ============================================
# AI Backend (choose one)
# ============================================
# Option 1: OpenAI (cloud, paid, best quality + web search)
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
# OPENAI_VISION_MODEL=gpt-5.4-nano-2026-03-17

# Option 2: Ollama (local, free, private)
# OLLAMA_VISION_MODEL=llava:7b
# OLLAMA_URL=http://localhost:11434
```

### 1.9 — Update `requirements.txt`

No new dependencies needed. Ollama's API is plain HTTP — `httpx` handles it.

### 1.10 — Tests

Add `tests/test_phase6.py` — Ollama integration tests:
- `test_ollama_connection()` — skip if Ollama not running
- `test_ollama_analyze_images()` — with test product image from `tests/samples/`
- `test_analyzer_factory_auto_detect()` — mock both backends
- `test_analyzer_factory_fallback()` — when neither is available
- `test_ollama_with_ebay_pricing_fallback()`

### 1.11 — Update landing page + docs

- Update `landing-page/index.php`: add "Free local AI" to hero badge, mention Ollama in features
- Update `README.md`: add Ollama section under Configuration
- Update `HOW_TO_USE.md`: add "Option B: Free local AI with Ollama" path

---

## Phase 2: Setup Concierge + UX Improvements

**Goal:** Reduce setup friction and improve the daily listing workflow. The current setup requires reading docs and visiting multiple websites. The concierge holds the user's hand through every click.

### 2.1 — Setup Concierge (`gui/wizard.py` rewrite)

Replace the current 5-step wizard with a richer guided experience. Keep the `CTkToplevel` pattern but make it 7 steps with inline guidance.

**New Step Flow:**

**Step 0: Welcome + AI Backend Choice**
- "Choose your AI engine" — big cards for OpenAI vs Ollama
- OpenAI card: "Best quality, web search pricing, ~$0.02/listing"
- Ollama card: "Free, private, runs on your machine, no account needed"
- Selecting one determines which setup path follows

**Step 1: AI Setup (conditional)**
- If OpenAI: Show exact URL to open (platform.openai.com/api-keys), paste field with live validation (calls `check_openai_status()` as they paste), green checkmark on success
- If Ollama: Check if running, show install command if not, check if model pulled, show pull command if not, "Check Again" button, green checkmark when ready

**Step 2: eBay Developer Account**
- Show: "You need API credentials from eBay's Developer Portal"
- Button: "Open eBay Developer Portal" → opens `https://developer.ebay.com/my/keys` in browser
- Inline numbered instructions with what to look for on the page
- Three paste fields: App ID, Cert ID, Dev ID — each validates format on paste
- RuName field with note: "Set redirect URL to `http://localhost:8000/ebay/callback`"
- Environment toggle: Sandbox (for testing) / Production (for real listings)
- "Test Connection" button that does a client_credentials grant to verify

**Step 3: eBay OAuth Login**
- "Now let's connect your eBay seller account"
- Button: "Connect eBay Account" → opens OAuth consent URL
- Status indicator: Waiting → Connected
- Shows eBay username on success

**Step 4: Business Policies (Production only)**
- If sandbox: skip this step automatically
- If production: explain that eBay requires business policies
- Button: "Open eBay Seller Hub" → opens business policies page
- Fields for Policy IDs (or auto-detect via eBay Account API if possible)
- "Check Again" / "Skip for now" options

**Step 5: Location + Preferences**
- Same as current steps 2-3 combined into one screen
- City, State, ZIP, shipping defaults, return policy, pricing markup, turbo mode

**Step 6: Complete**
- Summary of what's configured
- "Start Listing" button
- Quick tips

### 2.2 — Batch Mode

Add batch processing for power sellers who source many items at once.

**New file: `core/batch.py`**

```python
class BatchProcessor:
    """Process multiple product image sets in sequence."""

    def __init__(self, analyzer, on_progress=None, on_item_complete=None):
        ...

    def process_folder(self, folder_path: Path) -> list[ProductData]:
        """
        Scan folder for images. Group by subfolder or by filename prefix.
        Process each group as a separate product.
        """
        ...

    def process_image_sets(self, image_sets: list[list[Path]]) -> list[ProductData]:
        """Process explicit image groupings."""
        ...
```

**Grouping logic:**
- If folder contains subfolders, each subfolder = one product
- If flat folder, group by filename prefix (e.g., `camera_1.jpg`, `camera_2.jpg`)
- If no clear grouping, each image = one product

**GUI integration** (`gui/app.py`):
- Add "Batch Import" button in the header or sidebar
- Opens folder picker dialog
- Shows progress: "Processing item 3/12..."
- Each completed item appears as a Draft in the queue
- Optional: "Auto-publish all high-confidence items" checkbox (uses Turbo Mode logic)

### 2.3 — Barcode/UPC Scanning

Add barcode detection to the mobile camera UI for instant product lookup.

**Server-side** (`server/main.py`):
- Add new endpoint: `POST /scan` — accepts image, returns barcode data
- Use `pyzbar` library (add to requirements.txt: `pyzbar==0.1.9`)
- Decode barcode → UPC/EAN number

**Product lookup:**
- Use eBay Browse API to search by UPC: `GET /buy/browse/v1/item_summary/search?q={upc}&fieldgroups=MATCHING_ITEMS`
- Returns matching products with titles, prices, images
- Pre-fill `ProductData` from the best match
- Confidence score = 1.0 for exact UPC matches (no AI guessing needed)

**Mobile UI** (`server/templates/camera.html`):
- Add "Scan Barcode" mode toggle
- When active, camera focuses on center frame
- On successful scan, show product info overlay
- "Use this product" button sends pre-filled data to desktop

**Fallback:** If barcode not found in eBay database, fall back to normal AI vision analysis.

### 2.4 — Listing Templates

**New file: `core/templates.py`**

```python
@dataclass
class ListingTemplate:
    name: str           # "Electronics", "Clothing", "Books"
    category_id: str    # Default eBay category
    condition: str      # Default condition
    description_prefix: str  # Boilerplate text prepended to AI description
    description_suffix: str  # Boilerplate appended (e.g., return policy note)
    aspects: dict       # Default item specifics (brand, size, etc.)
    shipping_preset: str  # Override shipping for this template
```

**Database:** Add `listing_templates` table to `data/database.py`.

**GUI:** Add "Templates" section in Settings. Users create/edit/delete templates. When editing a draft, dropdown to "Apply Template" which fills in defaults.

### 2.5 — Keyboard Shortcuts

Add to `gui/app.py`:

| Shortcut | Action |
|----------|--------|
| `Cmd+Enter` | Publish current draft |
| `Cmd+S` | Save current draft |
| `Cmd+Delete` | Delete current draft |
| `Cmd+N` | Select next draft in queue |
| `Cmd+P` | Select previous draft in queue |
| `Cmd+1/2/3` | Switch to Dashboard/Editor/Settings |
| `Cmd+,` | Open Settings |

CustomTkinter supports `bind()` for keyboard events. Add bindings in the `__init__` method of `MyBayApp`.

### 2.6 — Tests

Add to `tests/test_phase6.py`:
- Batch processor tests (folder grouping, progress callbacks)
- Template CRUD tests
- Barcode scanning tests (mock pyzbar)
- Analyzer factory with Ollama tests

---

## Phase 3: Business Intelligence + Growth Features

**Goal:** Make myBay the tool sellers can't live without. Move from "listing tool" to "business platform."

### 3.1 — Profit Calculator

Extend the Dashboard in `gui/app.py` to show true profit per listing.

**Data already available:**
- Sale price (from `Listing` model)
- COGS/cost basis (from `Draft.cost` field — already exists)
- eBay fees (~13.25% final value fee — calculate or pull from eBay Finances API)
- Shipping cost (from `Income` model's `shipping_cost` field)

**New calculation:**
```
Net Profit = Sale Price - COGS - eBay Fees - Shipping Cost
Margin % = Net Profit / Sale Price * 100
```

**GUI:** Add profit column to Recent Listings in Dashboard. Add "Profit Summary" card showing total profit, average margin, best/worst items.

### 3.2 — Sales Analytics Dashboard

New tab or view in the Dashboard area.

**Visualizations** (use CustomTkinter canvas drawing or matplotlib embedded):
- Revenue over time (last 30 days line chart)
- Listings by category (bar chart)
- Average days to sale by category
- Best performing price points
- Sell-through rate (listed vs sold)

**Data source:** All from existing `Listing`, `DailyStat`, `Income` tables in `data/database.py`.

### 3.3 — Auto-Relist

Items that don't sell after N days get automatically relisted.

**New fields in presets:**
```python
auto_relist: bool = False
auto_relist_days: int = 30
auto_relist_price_drop: float = 0.0  # percentage to drop price, 0 = same price
auto_relist_max_times: int = 3
```

**Implementation:**
- Add `relist_count` and `original_listing_date` to `Listing` model
- Background check (in `run.py` startup or periodic timer): find listings where `status == ENDED` and `days_since_end > auto_relist_days` and `relist_count < max_times`
- Re-publish using existing `quick_list()` with optionally reduced price
- Log as new listing linked to original

### 3.4 — eBay Message Integration

Pull buyer messages into the app so sellers don't have to check eBay separately.

**eBay API:** `POST /sell/messaging/v1/message` (requires `sell.messaging` OAuth scope)

**Implementation:**
- Add `sell.messaging` to `DEFAULT_SCOPES` in `ebay/config.py` (line 39)
- New module: `ebay/messaging.py` — fetch messages, mark as read
- New tab in GUI: "Messages" with inbox view
- Notification badge on the Messages tab when unread messages exist

**Note:** This requires the eBay user to re-authorize with the new scope. Handle gracefully — detect missing scope and prompt re-auth.

### 3.5 — Multi-Marketplace (Mercari)

Start with Mercari as the second marketplace. It's the most natural fit (same category of sellers).

**New directory:** `mercari/`
- `mercari/auth.py` — Mercari OAuth
- `mercari/inventory.py` — Create/publish listings
- `mercari/images.py` — Image upload

**Cross-posting flow:**
- After publishing to eBay, offer "Also list on Mercari?" button
- Reuse the same `ProductData` — map fields to Mercari's schema
- Track which marketplaces each item is listed on
- When item sells on one platform, prompt to end listing on others

**This is the biggest engineering effort in V2.** Mercari's API is less documented than eBay's. Consider this a stretch goal — only pursue if Phases 1-2 are solid and tested.

### 3.6 — Shipping Label Integration

Generate USPS shipping labels directly from sold items.

**Options:**
- eBay's own shipping label API (part of Fulfillment API)
- EasyPost API (multi-carrier, well-documented)
- Pirate Ship API (popular with eBay sellers, competitive rates)

**Implementation:**
- New module: `shipping/labels.py`
- In Dashboard sold items list, add "Print Label" button
- Pre-fill: buyer address (from eBay order), item weight (manual or from template), package dimensions
- Generate label PDF, open in system PDF viewer

### 3.7 — Photo Studio Mode

Enhance the mobile camera UI with guides for consistent photography.

**Changes to `server/templates/camera.html`:**
- Add overlay grid lines (rule of thirds)
- Add "center placement" guide (dashed rectangle showing where to place item)
- Add consistent lighting indicator (analyze image brightness, warn if too dark/bright)
- "Flat lay" mode: top-down framing guide
- "Front view" mode: centered horizontal guide
- Save mode preference per session

### 3.8 — Tests

Extend test suite:
- `tests/test_phase7.py` — profit calculator, analytics queries
- `tests/test_phase8.py` — auto-relist logic, messaging
- Integration tests for Ollama + eBay pricing fallback end-to-end

---

## Implementation Priority

```
Phase 1 (Ollama)          ████████████████████ — Do this first, biggest impact
  1.1-1.4  Core Ollama      ██████████         — 2-3 sessions
  1.5-1.7  Presets + UI     ██████             — 1-2 sessions
  1.8-1.11 Docs + Tests     ████               — 1 session

Phase 2 (UX)              ████████████████████
  2.1  Setup Concierge      ████████           — 2 sessions
  2.2  Batch Mode           ██████             — 1-2 sessions
  2.3  Barcode Scanning     ██████             — 1-2 sessions
  2.4  Templates            ████               — 1 session
  2.5  Keyboard Shortcuts   ██                 — Quick win

Phase 3 (Growth)          ████████████████████
  3.1  Profit Calculator    ████               — 1 session
  3.2  Analytics Dashboard  ██████             — 1-2 sessions
  3.3  Auto-Relist          ████               — 1 session
  3.4  eBay Messages        ██████             — 1-2 sessions
  3.5  Multi-Marketplace    ██████████████     — Major effort, stretch goal
  3.6  Shipping Labels      ████████           — 1-2 sessions
  3.7  Photo Studio         ████               — 1 session
```

## Files You'll Create

| File | Phase | Purpose |
|------|-------|---------|
| `core/ollama.py` | 1 | Ollama vision analyzer |
| `core/analyzer_factory.py` | 1 | Backend auto-detection + routing |
| `core/batch.py` | 2 | Batch image processing |
| `core/templates.py` | 2 | Listing templates |
| `ebay/messaging.py` | 3 | eBay buyer messages |
| `shipping/labels.py` | 3 | Shipping label generation |
| `tests/test_phase6.py` | 1-2 | Ollama + batch + template tests |
| `tests/test_phase7.py` | 3 | Analytics + profit tests |
| `tests/test_phase8.py` | 3 | Auto-relist + messaging tests |

## Files You'll Modify

| File | Phase | What Changes |
|------|-------|-------------|
| `core/vision.py` | 1 | Extract shared prompt to reusable constant |
| `core/watcher.py` | 1 | Use `get_analyzer()` instead of direct `ProductAnalyzer()` |
| `core/presets.py` | 1 | Add `ai_backend`, `ollama_model`, `ollama_url` fields |
| `gui/wizard.py` | 1-2 | Rewrite as Setup Concierge (7 steps) |
| `gui/app.py` | 1-3 | Settings UI for AI backend, batch import button, keyboard shortcuts, profit display, analytics view |
| `gui/admin_view.py` | 3 | Messages tab (if adding eBay messaging) |
| `server/main.py` | 2 | Add `/scan` barcode endpoint |
| `server/templates/camera.html` | 2-3 | Barcode mode, photo studio guides |
| `data/database.py` | 2-3 | Templates table, relist tracking fields |
| `ebay/config.py` | 3 | Add `sell.messaging` to DEFAULT_SCOPES |
| `.env.example` | 1 | Add Ollama config vars |
| `requirements.txt` | 2 | Add `pyzbar` for barcode scanning |
| `README.md` | 1-2 | Document Ollama, batch mode, barcodes |
| `HOW_TO_USE.md` | 1 | Add Ollama setup path |
| `landing-page/index.php` | 1 | Mention free local AI in hero/features |

## Testing Strategy

Run the full test suite after each sub-task: `pytest tests/ -v`

Before starting any phase, verify current tests pass. The last known state was 80 passing tests. If any fail, investigate before adding new code — they may reveal environment drift.

For Ollama tests, use `@pytest.mark.skipif` when Ollama isn't running so CI doesn't break:
```python
import pytest, httpx

def ollama_available():
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

@pytest.mark.skipif(not ollama_available(), reason="Ollama not running")
def test_ollama_analyze():
    ...
```

# 📦 myBay

### Snap. List. Sell. Run the business. — All in one app.

myBay is a desktop application that turns photos into eBay listings instantly **and** manages the entire sole proprietorship behind it. Snap photos on your iPhone, and the app uses OpenAI vision + web search to create complete listings — title, description, price, category — all with one click to publish. The built-in Admin dashboard tracks expenses, income, mileage, business documents, and taxes — with an AI assistant that lets you log transactions just by typing plain English.

---

## 🧪 Current QA Status

- **Last update**: March 25, 2026
- **Current phase**: Production-ready (Phases 1-3 complete)
- **Automated tests**: 80 passed
- **Latest packaged build**: `dist/MyBay-1.0.0.dmg`
- **AI Model**: OpenAI GPT-5.4 Nano (vision + web search)
- **Key capabilities**:
  - One-click eBay publishing with API verification
  - AI vision analysis with web search for pricing
  - Mobile phone camera integration (QR code)
  - Full admin dashboard: expenses, income, mileage, taxes, documents
  - Schedule C P&L with home office deduction, 1099-K reconciliation
  - Quarterly estimated tax calculation (Federal SE + CA state)
  - Sales tax tracking, return/refund logging, inventory cost tracking
  - CSV/ZIP export with receipt images for accountant
  - Auto-save, unsaved changes protection, input validation
  - Port conflict detection, human-readable error messages

---

## ✨ Features

### eBay Listing Features

| Feature | Description |
|---------|-------------|
| **📱 Phone Camera Integration** | Scan a QR code to open the camera on your phone. Photos go straight to your Mac. |
| **🤖 AI Vision + Web Search** | OpenAI analyzes your photos and does a quick web lookup to improve identification and pricing. |
| **🧾 Structured AI Output** | Uses strict JSON schema validation so listing fields stay consistent and parseable. |
| **💰 Smart Pricing** | Compares to similar eBay listings to suggest competitive prices. |
| **🚀 Turbo Mode** | High-confidence items auto-publish without review. Includes 30-second undo! |
| **📊 Performance Dashboard** | Track daily listings, revenue, and time saved. |
| **🎨 Background Removal** | Automatic white background for professional photos. |
| **💾 Offline Support** | Queue listings when offline, auto-sync when connected. |
| **☁️ Cloud AI Accuracy** | Uses OpenAI API for stronger product recognition and fewer hallucinations. |
| **✅ Publish API Verification** | After publish, app verifies listing via eBay Browse API and shows verified/pending status. |
| **🛡️ Publish Recovery Logic** | Handles invalid condition/category combos, duplicate existing offers, and missing required item specifics with retries/fallbacks. |
| **🧩 Landing Page + Backend** | Includes a PHP + SQLite landing page with admin-managed content, downloads, and lead inbox. |
| **🔏 Trusted Release Pipeline** | Supports macOS signing/notarization and Windows Authenticode signing hooks (local + GitHub Actions). |

### Admin Dashboard (Sole Prop Business Backend)

| Feature | Description |
|---------|-------------|
| **💬 AI Business Assistant** | Type plain English like "spent $25 at goodwill on inventory" and the AI logs expenses, income, and mileage automatically. |
| **💼 Business Info** | Store business entity details — DBA name, EIN, CA seller's permit, SD business tax cert, bank info. |
| **💸 Expense Tracking** | Log expenses by category (inventory/COGS, shipping, eBay fees, supplies, storage, etc.) with receipt image uploads. |
| **💵 Income Tracking** | Manual income entry + one-click import of sold eBay listings as income. Sales tax tracked separately. |
| **🔄 Return/Refund Logging** | Log returns as negative income entries so Schedule C stays accurate. |
| **🚗 Mileage Tracker** | Log trips with IRS standard rate deduction (configurable per year: 2024 $0.67, 2025 $0.70). |
| **💰 Inventory Cost Tracking** | Track what you paid for items (cost basis) for accurate COGS on Schedule C. |
| **📄 Document Storage** | Upload and manage business documents (permits, EIN letter, DBA filing, tax certs) with expiry warnings. |
| **📋 Tax Summary** | Schedule C P&L with home office deduction, quarterly estimated tax amounts (Federal + CA), 1099-K reconciliation. |
| **📤 CSV Export** | Export by date range. Individual CSVs or bundled ZIP with receipt images included. |

---

## 🖥️ Screenshots

### Listing Editor

```
┌──────────────────────────────────────────────────────────────────────┐
│  📦 myBay                      [📊 Dashboard] [Admin] [⚙️ Settings] │
├───────────────┬──────────────────────────────────────────────────────┤
│               │                                                      │
│  DRAFT QUEUE  │  📷 Product Images         Edit Listing             │
│               │  ┌─────────────────┐                                │
│ ┌───────────┐ │  │                 │  Title: [Vintage Camera      ] │
│ │ Camera    │ │  │   [IMAGE 1]     │                                │
│ │ $45       │ │  │                 │  Category: [Electronics      ] │
│ │ ████ 92%  │ │  └─────────────────┘                                │
│ └───────────┘ │                         Condition: [Like New       ] │
│               │  AI Confidence: ████████░░ 92%                       │
│ ┌───────────┐ │                         Price: $[45.00             ] │
│ │ Nike Shoe │ │  ┌──────────────────────────────────────────┐       │
│ │ $89       │ │  │ Great condition vintage Polaroid camera  │       │
│ │ ████ 88%  │ │  │ with original case. Tested and working.  │       │
│ └───────────┘ │  └──────────────────────────────────────────┘       │
│               │                                                      │
│               │    [💾 Save]  [🗑️ Delete]  [🚀 Publish]             │
├───────────────┴──────────────────────────────────────────────────────┤
│  📊 Today: 12 listed | 3 sold | $247 revenue | 48 min saved         │
└──────────────────────────────────────────────────────────────────────┘
```

### Admin Dashboard — AI Assistant

```
┌──────────────────────────────────────────────────────────────────────┐
│  📦 myBay                      [📊 Dashboard] [Admin] [⚙️ Settings] │
├──────────────────────────────────────────────────────────────────────┤
│ [AI Assistant] [Business Info] [Expenses] [Income] [Mileage]         │
│ [Documents] [Tax Summary] [Export CSV]                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  AI Business Assistant                                               │
│  Tell me what you bought, sold, or drove — I'll log it for you.     │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ You: spent $25 at goodwill on inventory, drove 12 miles       │  │
│  │                                                                │  │
│  │ Assistant: Got it!                                             │  │
│  │                                                                │  │
│  │ Logged:                                                        │  │
│  │   - Expense: $25.00 (inventory)                                │  │
│  │   - Mileage: 12.0 mi ($8.40 deduction)                        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  [Type a message...                                        ] [Send]  │
│                                                                      │
│  Try: [spent $25 at goodwill] [drove 12 miles to swap meet]         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Option 1: Download the App (Recommended)

1. **Download** `MyBay.dmg` from the Releases page
2. **Drag** the app to your Applications folder
3. **Open** myBay
4. **Follow** the setup wizard (connects eBay, sets preferences)
5. **Scan** the QR code with your phone and start snapping!

### Option 2: Run from Source (One-Command Install)

```bash
# Clone or copy the project, then:
cd mybay

# Run the installer (sets up Python, venv, dependencies, .env)
chmod +x install.sh
./install.sh

# Edit .env with your API keys
nano .env

# Launch! (or double-click start.command)
source venv/bin/activate
python3 run.py --gui
```

### Option 3: Manual Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python3 run.py --gui
```

---

## 📱 How It Works

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   PHONE     │      │    MAC      │      │   OPENAI    │      │    EBAY     │
│             │      │             │      │     AI      │      │             │
│  📷 Snap    │ ───▶ │  📥 Receive │ ───▶ │  🤖 Analyze │ ───▶ │  🚀 Publish │
│   Photos    │ WiFi │   Images    │      │   & Price   │      │   Listing   │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                ▼
                                          ┌─────────────┐
                                          │   REVIEW    │
                                          │  (optional) │
                                          │  Edit title │
                                          │  Adjust $   │
                                          └─────────────┘
```

### Step by Step

1. **Launch the App** — Opens the main window with QR code displayed
2. **Scan QR Code** — Use your iPhone camera to scan and open the photo portal
3. **Snap Photos** — Take 1-3 photos of your item (supports multiple angles)
4. **AI Analysis** — Within seconds, the AI generates:
   - Product title (eBay-optimized, max 80 chars)
   - Description (2-3 detailed sentences)
   - Category suggestion
   - Condition assessment
   - Price recommendation (based on market data)
5. **Review & Edit** — Fine-tune anything if needed
6. **Publish** — One click and you're live on eBay!

---

## ⚙️ Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| **macOS** | 12.0+ | Apple Silicon (M1/M2/M3) recommended |
| **Python** | 3.10+ | Only needed if running from source |
| **AI Backend** | See below | OpenAI *or* Ollama (at least one required) |
| **ngrok** | Latest (optional) | Only needed for phone camera QR code access over the internet |
| **eBay Account** | — | Seller account required |

### AI Backend Options

| Backend | Cost | Quality | Privacy | Setup |
|---------|------|---------|---------|-------|
| **OpenAI** | ~$0.01-0.05/listing | Best (vision + web search pricing) | Cloud | API key required |
| **Ollama** | Free | Good (local vision model) | Fully local | `brew install ollama && ollama pull qwen3.5:2b` |

You only need **one**. Ollama lets you try the app with zero accounts and zero cost. OpenAI gives the best results and includes live web-search pricing.

**Recommended Ollama models:**

| Model | Size | RAM | Speed | Notes |
|-------|------|-----|-------|-------|
| `qwen3.5:2b` | 2B | ~2GB | Fast | **Recommended default** — small, fast, vision-capable |
| `moondream` | 1.7B | ~2GB | Fast | Lightest option, good for basic product ID |
| `minicpm-v` | 3B | ~3GB | Fast | Good middle ground |
| `llava:7b` | 7B | ~5GB | Medium | Solid quality, needs more RAM |
| `llama3.2-vision:11b` | 11B | ~8GB | Slower | Best local quality |

### eBay Developer Setup

To connect to eBay, you'll need API credentials:

1. Go to [eBay Developer Portal](https://developer.ebay.com)
2. Create an application (Sandbox first, then Production)
3. Set the redirect URL to: `http://localhost:8000/ebay/callback`
4. Note your Client ID, Client Secret, and RuName
5. Enter these in the app's Settings

---

## 🛠️ Configuration

### First-Run Setup Wizard

The app guides you through setup on first launch:

1. **AI Setup** — Choose OpenAI or Ollama, verify connection
2. **eBay Connection** — OAuth login to your eBay seller account
3. **Location** — Set your item location (city, state, ZIP)
4. **Policies** — Configure shipping, returns, and payment defaults
5. **Done!** — Start listing immediately

### AI Configuration

**Option A — OpenAI (cloud, best quality):**

```bash
export OPENAI_API_KEY="sk-..."
# Optional model override:
export OPENAI_VISION_MODEL="gpt-5.4-nano-2026-03-17"
```

**Option B — Ollama (local, free, no account):**

```bash
brew install ollama
ollama serve          # start the server (runs in background)
ollama pull qwen3.5:2b  # download a vision model
```

Optional overrides:

```bash
export OLLAMA_VISION_MODEL="qwen3.5:2b"
export OLLAMA_URL="http://localhost:11434"
```

Or use `.env` in the project root:

```env
# OpenAI (comment out if using Ollama)
OPENAI_API_KEY=sk-...

# Ollama (comment out if using OpenAI)
# OLLAMA_VISION_MODEL=qwen3.5:2b
# OLLAMA_URL=http://localhost:11434

NGROK_AUTHTOKEN=your_ngrok_token
```

The app automatically loads this `.env` file at runtime. If both backends are configured, the app auto-detects which to use (Ollama preferred when `OLLAMA_VISION_MODEL` is set).

### Sharing the App (Important)

If another person runs the app with **your** OpenAI key, it will work and all usage is billed to **your** OpenAI account.

- **Yes, it works**: as long as the machine has a valid `OPENAI_API_KEY`.
- **If no key is set**: AI analysis fails at startup/check time.
- **Build note (secure default)**: release builds do **not** bundle `.env`, `.ebay_config.json`, `mybay.db`, or `ngrok`.
- **Optional override**: set `BUNDLE_LOCAL_STATE=1` and/or `BUNDLE_NGROK=1` only for private/internal builds you control.
- **Result**: production installers stay safer by default and each user brings their own credentials.
- **Recommended for production sharing**: each person should use their own OpenAI key.
- **If you still share your key**: assume it can be exposed, set usage limits, and be ready to rotate/revoke it.

### Smart Presets

Save time with smart defaults:

- **Shipping**: USPS Ground Advantage, 1-day handling
- **Returns**: 30-day returns accepted
- **Pricing**: 10% markup, round to .99
- **Turbo Mode**: Auto-publish if AI confidence ≥ 90%

### Image Hosting

When you publish a listing, the app uploads your product images directly to **eBay Picture Services** using the Trading API (`UploadSiteHostedPictures`). eBay returns permanent `https://i.ebayimg.com/...` URLs that are used in the listing — no ngrok or public URL required for publishing.

During publish you'll see progress in the terminal:

```text
  Uploaded image 1/3: photo1.jpg — ok
  Uploaded image 2/3: photo2.jpg — ok
  Uploaded image 3/3: photo3.jpg — ok
```

### ngrok (Optional — Phone Camera Only)

ngrok is **only** needed if you want to access the phone camera portal from outside your local network. For local WiFi usage between your phone and Mac, ngrok is not required.

```bash
# Install ngrok (one-time)
brew install ngrok/ngrok/ngrok

# Add your ngrok auth token (one-time)
ngrok config add-authtoken <YOUR_NGROK_TOKEN>

# Start app (auto-starts ngrok in GUI mode if available)
python3 run.py --gui
```

---

## 🎛️ Advanced Features

### Turbo Mode

Enable in Settings to auto-publish items when AI confidence is high:

```
Turbo Mode: [ON]  Threshold: [90%]

When AI confidence ≥ 90%:
  ✅ Auto-publishes without review
  ⏱️ 30-second undo window
  🔔 Desktop notification
```

### Pricing Intelligence

The app uses eBay's Browse API to find comparable listings:

- Shows **average**, **median**, **min**, **max** prices
- Suggests optimal price based on market analysis
- Warns if your price is too low or too high

### Offline Mode

Lost internet? No problem:

- Listings queue locally
- Auto-sync when connection restored
- Visual indicator shows offline status

### Recent Desktop UI/UX Updates

- Sidebar collapse/expand now uses a persistent hamburger toggle (including collapsed state).
- Top-right header actions are streamlined to `Dashboard`, `Admin`, and `Settings`.
- Recent Listings scrollbar behavior is cleaner and less intrusive.
- Settings view mouse-wheel scrolling was fixed for smoother navigation.

---

## 💼 Admin Dashboard (Sole Prop Business Backend)

The **Admin** tab turns myBay into a full business management tool for your sole proprietorship. Click the `Admin` button in the header to access it.

### AI Business Assistant

The fastest way to log transactions. Just type what happened in plain English:

```
"spent $25 at goodwill on inventory, drove 12 miles"
"sold a vintage camera for $85 on ebay, $11 in fees"
"drove 50 miles round trip to the swap meet"
"bought $8 of shipping tape at walmart"
```

The AI parses each message and automatically creates the correct entries across expenses, income, and mileage — a single message can generate multiple entries. Uses the same OpenAI API key already configured in the app.

### Expense Tracking

- Log expenses by category: Inventory/COGS, Shipping, eBay Fees, Supplies, Storage, Phone/Internet, Office, Other
- Attach receipt images (copied to `admin_files/receipts/`)
- YTD category totals and expense list with delete

### Income Tracking

- Manual income entry with source (eBay, Cash, Other)
- Track platform fees and shipping costs, auto-calculates net
- **Import Sold Listings** button — one-click import of sold eBay listings into the income log

### Mileage Tracker

- Log trips with purpose (Sourcing, Post Office, Supplies Run, Bank)
- IRS standard mileage rate: $0.70/mile (2025)
- Auto-calculates deduction per trip and YTD totals
- Destination field for record-keeping

### Business Info

- Store DBA name, owner name, business address, phone, email
- Tax IDs: EIN, CA Seller's Permit (CDTFA) number + expiry, SD Business Tax Certificate number + expiry
- Business banking info (masked display)

### Document Storage

- Upload business documents: CA Seller's Permit, EIN Letter, DBA Filing, SD Business Tax Cert, Bank Docs
- Expiry date tracking with warnings (expired, expiring soon)
- Open documents directly from the app
- Files stored in `admin_files/documents/`

### Tax Summary

- **Schedule C (P&L)**: Gross income (excludes collected sales tax), COGS, gross profit, operating expenses by category, mileage deduction, home office deduction, net profit
- **Home office deduction**: Simplified method ($5/sq ft, max 300 sq ft = $1,500)
- **Self-employment tax estimate**: 15.3% of 92.35% of net profit
- **Quarterly estimated taxes**: Calculates Federal (SE + income tax) and CA state amounts per quarter, with mark-as-paid and confirmation number tracking
- **1099-K reconciliation**: Compare your logged gross income against the 1099-K from eBay to find discrepancies
- Year selector for viewing prior years

### CSV Export

Export any or all business data for your accountant or tax prep:

- **Date range filter**: Export a specific period (Q1, full year, custom range)
- Individual exports: Expenses, Income, Mileage, Documents, Tax Summary
- **Export All (ZIP)**: Bundles everything into a single `.zip` file with receipt images included

---

## 🌐 Landing Page + Admin Backend

New landing site module in `landing-page/`:

- `landing-page/index.php`: single-file frontend + admin backend
- Auto-creates SQLite DB (`landing-page/landing.sqlite`) on first run
- Admin can manage site settings, categories, content blocks, and download links
- Contact form submissions are stored and reviewable in backend inbox

Quick run:

```bash
cd landing-page
php -S 127.0.0.1:8080
```

Then open `http://127.0.0.1:8080` (admin: `http://127.0.0.1:8080/?admin=1`).

Security hardening included:

- CSRF protection on forms
- Session cookie hardening (`HttpOnly`, `SameSite=Strict`, strict mode)
- Security headers (`CSP`, `X-Frame-Options`, `nosniff`, `Referrer-Policy`)
- Login and contact rate limiting by IP
- URL sanitization for CTA/download links
- Default-password remote-login block

---

## 📂 Project Structure

```
mybay/
├── core/                 # Core functionality
│   ├── vision.py         # AI product analysis (OpenAI vision + web search)
│   ├── assistant.py      # AI business assistant (natural language → entries)
│   ├── turbo.py          # Auto-publish logic
│   ├── retry.py          # Error handling & offline queue
│   └── presets.py        # Smart defaults
├── ebay/                 # eBay API integration
│   ├── auth.py           # OAuth 2.0 flow
│   ├── images.py         # eBay Picture Services upload
│   ├── inventory.py      # Listings management
│   └── pricing.py        # Market price analysis
├── gui/                  # Desktop interface
│   ├── app.py            # Main CustomTkinter app
│   ├── admin_view.py     # Admin dashboard (business backend)
│   └── wizard.py         # Setup wizard
├── server/               # Mobile camera server
│   ├── main.py           # FastAPI server
│   └── templates/        # Mobile UI
├── data/                 # Database
│   └── database.py       # SQLite storage (listings + admin tables)
├── admin_files/          # Uploaded business files (auto-created)
│   ├── receipts/         # Expense receipt images
│   └── documents/        # Business document uploads
├── landing-page/         # PHP landing page + SQLite admin backend
│   └── index.php
├── .github/workflows/
│   └── build-cross-platform.yml
├── run.py                # Main entry point
├── install.sh            # One-command setup for new Mac
├── .env.example          # Template for API keys
├── build.py              # macOS packaging + optional sign/notarize
├── build_windows.py      # Windows .exe build + optional signing
├── build_linux.py        # Linux .AppImage build
├── SECURITY_CHECKLIST.md # Pre-release security checklist
├── SIGNING.md            # Signing/notarization setup
└── requirements.txt      # Python dependencies
```

---

## 🔧 Troubleshooting

### App won't launch

```bash
# Kill any process using port 8000
lsof -ti :8000 | xargs kill -9

# Try launching again
open /Applications/MyBay.app
```

### OpenAI not detected

```bash
# Set API key in your shell
export OPENAI_API_KEY="sk-..."

# Or add to .env in project root
echo 'OPENAI_API_KEY=sk-...' >> .env
```

### OpenAI errors during analysis

- `401/403`: bad key, revoked key, or missing project permissions
- `429`: rate limit or spend limit hit
- `5xx`: temporary provider issue; retry

### eBay connection issues

1. Check your API credentials in Settings
2. Ensure redirect URL matches: `http://localhost:8000/ebay/callback`
3. Try disconnecting and reconnecting your eBay account

### Photos not appearing

- Ensure phone and Mac are on the same WiFi network
- Check that the server is running (green status in Settings)
- Try refreshing the QR code

### Publish works but eBay listing has missing images (or publish image errors)

- Images are uploaded directly to eBay Picture Services — no ngrok needed
- Check terminal for upload errors (e.g. `FAILED: ...`)
- Verify you have a valid eBay OAuth token (reconnect in Settings if expired)
- Ensure images are under 12 MB and in a supported format (JPG, PNG, etc.)

### Publish says success, but the listing link says "nothing found"

- Most common cause: environment mismatch (`sandbox` vs `production`).
- Sandbox listings are best opened via eBay's canonical sandbox URL (`itemWebUrl`), commonly `https://cgi.sandbox.ebay.com/itm/...`.
- Production listings only open on `https://www.ebay.com/itm/<listingId>`.
- The app now stores listing environment per publish and resolves listing links using eBay Browse API first, then domain fallback.
- In Dashboard recent activity, each listing now shows an environment badge:
  - `[SBX]` = sandbox listing
  - `[LIVE]` = production listing
- Status bar now reports either:
  - `Published + API verified ...`
  - `Published ... (API verify pending)`

### Sandbox listing opens, but Seller Hub/seller page looks empty

- This can happen in sandbox even when the listing is live.
- Sandbox UI is less reliable than production Seller Hub.
- Prefer verification using:
  - App publish status (`Published + API verified ...`)
  - Dashboard `Open` button (uses canonical `itemWebUrl`)
  - eBay Browse API lookup by legacy item ID

### Production publish: "Missing business policies" error

- This means your eBay production seller account is not fully set up for Business Policies.
- In eBay Seller Hub, create:
  - Payment policy
  - Return policy
  - Fulfillment/Shipping policy
- Re-authenticate production OAuth after policy/account changes.

### Production publish: invalid condition for category

- Some eBay categories only allow specific condition IDs.
- The app now attempts condition fallback automatically when a requested condition is invalid for the selected category.
- If needed, adjust category/condition in the listing editor and retry.

### Production publish: `Offer entity already exists`

- eBay already has an offer for that inventory item SKU.
- The app now handles this by reusing/updating existing offers instead of hard failing.
- If this persists, delete stale offer/inventory in Seller Hub or use a fresh SKU.

### Production publish: missing required item specific (for example `Ring Size`)

- Category-specific required aspects must be present before publish.
- The app attempts to infer/fill required aspects and retry publish.
- If still blocked, include the required specific directly in title/description or edit aspects manually.

---

## 🏗️ Building from Source

```bash
# Activate virtual environment
source venv/bin/activate

# Build macOS .app bundle (run on macOS)
python build.py

# Build macOS with .dmg installer
python build.py --dmg

# Build + sign macOS app/dmg (requires MACOS_SIGN_IDENTITY)
python build.py --dmg --sign

# Build + sign + notarize macOS dmg
python build.py --dmg --sign --notarize

# Build Windows .exe (run on Windows)
python build_windows.py --clean

# Build + sign Windows .exe (run on Windows)
python build_windows.py --clean --sign

# Build Linux .AppImage (run on Linux)
python build_linux.py --clean

# Optional: private/internal build that bundles local state (NOT for public release)
ALLOW_BUNDLED_SECRETS=1 BUNDLE_LOCAL_STATE=1 python build.py --dmg

# Clean macOS build artifacts
python build.py --clean
```

Output examples:

- macOS: `dist/MyBay.app`, `dist/MyBay-1.0.0.dmg`
- Windows: `dist/windows/MyBay/MyBay.exe`
- Linux: `dist/MyBay-1.0.0-x86_64.AppImage`

Automated cross-platform builds are also configured in `.github/workflows/build-cross-platform.yml` (manual `workflow_dispatch`).

For signing/notarization environment variables and required GitHub secrets, see `SIGNING.md`.

Important:

- Windows and Linux builds are designed to run on native OS runners.
- Public release builds should keep `BUNDLE_LOCAL_STATE=0` (default).

---

## 🔐 Release Security

- Review `SECURITY_CHECKLIST.md` before every public release.
- Keep API credentials, OAuth tokens, and local DB files out of packaged public installers.
- Use signed artifacts for production distribution:
  - macOS: signed + notarized DMG
  - Windows: Authenticode-signed EXE

---

## 🧪 Running Tests

```bash
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific phase
pytest tests/test_phase1.py -v  # AI Vision
pytest tests/test_phase2.py -v  # Camera Server
pytest tests/test_phase3.py -v  # eBay API
pytest tests/test_phase4.py -v  # GUI & Database
pytest tests/test_phase5.py -v  # Pro Features
```

---

## 📈 Stats & Metrics

The **Dashboard** tracks eBay listing performance:

| Metric | Description |
|--------|-------------|
| **Listed Today** | Items published today |
| **Sold Today** | Items that sold |
| **Revenue** | Total sales amount |
| **Time Saved** | Estimated minutes saved (5 min/listing) |
| **Success Rate** | Listings that sold vs. total |

The **Admin > Tax Summary** tracks business financials:

| Metric | Description |
|--------|-------------|
| **Gross Income** | Total income from all sources (eBay + cash) |
| **COGS** | Cost of goods / inventory purchases |
| **Operating Expenses** | Shipping, fees, supplies, storage, etc. |
| **Mileage Deduction** | IRS standard rate deduction for business miles |
| **Net Profit** | Schedule C Line 31 equivalent |
| **SE Tax Estimate** | Self-employment tax (15.3% of 92.35% of net) |

---

## 🙏 Credits

- **AI Model**: OpenAI (`OPENAI_VISION_MODEL`, default `gpt-5.4-nano-2026-03-17`)
- **GUI**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- **Background Removal**: [rembg](https://github.com/danielgatis/rembg)

---

## 📄 License

MIT License — Do whatever you want with it!

---

<p align="center">
  <i>"List faster. Sell more. Live better."</i>
</p>

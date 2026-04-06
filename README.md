# myBay

### Snap. List. Sell. Run the business.

myBay turns photos into eBay listings in under 60 seconds. Snap photos on your phone, and AI creates the listing — title, description, price, category — with one click to publish. Choose between **Ollama** (free, local, private) or **OpenAI** (cloud, best quality + web search pricing). The built-in Admin dashboard tracks expenses, income, mileage, and taxes with an AI assistant that logs transactions from plain English.

**Open source. MIT License. Free forever.**

---

## Quick Start

```bash
git clone https://github.com/lalomorales22/myBay.git
cd myBay
./install.sh
```

The installer sets up Python, a virtual environment, and all dependencies. Then:

```bash
# Edit .env with your API keys (or skip for Ollama-only)
nano .env

# Launch the app
source venv/bin/activate
python3 run.py --gui
```

Or double-click `start.command` after install.

---

## AI Backend — Pick One

| Backend | Cost | Quality | Setup |
|---------|------|---------|-------|
| **Ollama** (local) | Free | Good — local vision model, fully private | `brew install ollama && ollama serve && ollama pull qwen3.5:2b` |
| **OpenAI** (cloud) | ~$0.01-0.05/listing | Best — vision + web search pricing | Set `OPENAI_API_KEY` in `.env` |

You only need **one**. Ollama lets you try the app with zero accounts and zero cost.

### Recommended Ollama Models

| Model | Size | Notes |
|-------|------|-------|
| **`qwen3.5:2b`** | 2B | Default — fast, vision-capable, low RAM |
| **`gemma4`** | 12B | Higher quality if you have the RAM/VRAM (`ollama run gemma4`) |

The app auto-detects your backend. If both are configured, set your preference in Settings.

---

## How It Works

```
  PHONE              DESKTOP            AI                 EBAY
  -----              -------            --                 ----
  Snap photos  --->  Receive via  --->  Analyze with  ---> Publish
  (QR code)    WiFi  WiFi server        Ollama/OpenAI      listing
```

1. **Scan QR code** — Opens the camera on your phone
2. **Snap 1-3 photos** — They transfer to your desktop instantly over WiFi
3. **AI analyzes** — Generates title, description, category, condition, and market price
4. **Review & publish** — Edit anything, then one click to go live on eBay

---

## Features

### Listing

- **Phone Camera Integration** — QR code opens camera, photos transfer over WiFi
- **AI Vision Analysis** — Product identification with structured JSON output
- **Smart Pricing** — Compares against eBay market data (average, median, range)
- **Turbo Mode** — Auto-publish high-confidence items with 30-second undo
- **Background Removal** — AI-powered white backgrounds (local, optional)
- **Offline Support** — Queue listings when offline, auto-sync when connected
- **Publish Recovery** — Handles condition/category mismatches, duplicates, and missing item specifics automatically

### Admin Dashboard (Business Backend)

- **AI Business Assistant** — Type "spent $25 at goodwill on inventory, drove 12 miles" and it logs everything
- **Expense Tracking** — By category with receipt uploads and YTD totals
- **Income Tracking** — Manual entry or one-click import of sold eBay listings
- **Mileage Tracker** — IRS standard rate ($0.70/mile for 2025), auto-calculates deductions
- **Tax Summary** — Schedule C P&L, SE tax estimate, quarterly payments, 1099-K reconciliation
- **CSV Export** — By date range, individual or bundled ZIP with receipts

---

## eBay Developer Setup

To publish listings, you need eBay API credentials:

1. Go to [developer.ebay.com](https://developer.ebay.com) and create an account
2. Create an application (start with Sandbox, switch to Production when ready)
3. Set the redirect URL to: `http://localhost:8000/ebay/callback`
4. Note your **Client ID**, **Client Secret**, and **RuName**
5. Enter these in the app's Settings, or the Setup Wizard will guide you on first launch

---

## ngrok (Optional)

ngrok is **only** needed if your phone and computer are on different networks (e.g., phone on cellular, computer on home WiFi). If they're on the same WiFi, you don't need ngrok at all.

```bash
# 1. Sign up for a free account at https://ngrok.com
# 2. Install
brew install ngrok/ngrok/ngrok

# 3. Add your auth token (one-time, from your ngrok dashboard)
ngrok config add-authtoken YOUR_TOKEN

# 4. Add to .env (optional — app auto-detects ngrok if installed)
echo 'NGROK_AUTHTOKEN=YOUR_TOKEN' >> .env
```

The app auto-starts an ngrok tunnel in GUI mode when available. You can also set `NGROK_DOMAIN` for a static free-tier domain.

---

## Configuration

### .env File

```env
# AI Backend (choose one or both)
OPENAI_API_KEY=sk-proj-...
# OLLAMA_VISION_MODEL=qwen3.5:2b

# eBay Sandbox
EBAY_SANDBOX_APP_ID=your-sandbox-app-id
EBAY_SANDBOX_CERT_ID=your-sandbox-cert-id
EBAY_SANDBOX_DEV_ID=your-sandbox-dev-id

# eBay Production
EBAY_PRODUCTION_APP_ID=your-production-app-id
EBAY_PRODUCTION_CERT_ID=your-production-cert-id
EBAY_PRODUCTION_DEV_ID=your-production-dev-id

# Optional
# NGROK_AUTHTOKEN=your-ngrok-token
```

### Smart Presets

Configurable defaults applied to every listing:

- **Shipping**: USPS Ground Advantage, 1-day handling
- **Returns**: 30-day returns accepted
- **Pricing**: Markup %, round to .99, minimum price
- **Turbo Mode**: Auto-publish threshold (default 90% confidence)

---

## Project Structure

```
myBay/
├── core/                 # Core functionality
│   ├── vision.py         # OpenAI vision analysis
│   ├── ollama.py         # Ollama vision analysis
│   ├── parsing.py        # Shared JSON parsing & validation
│   ├── assistant.py      # AI business assistant (OpenAI + Ollama)
│   ├── analyzer_factory.py # Auto-detects and returns correct backend
│   ├── watcher.py        # File watcher for photo queue
│   ├── turbo.py          # Auto-publish logic
│   ├── retry.py          # Error handling & offline queue
│   └── presets.py        # Smart defaults
├── ebay/                 # eBay API integration
│   ├── auth.py           # OAuth 2.0 flow
│   ├── inventory.py      # Listings management
│   ├── images.py         # eBay Picture Services upload
│   ├── taxonomy.py       # Category suggestions
│   └── pricing.py        # Market price analysis
├── gui/                  # Desktop interface
│   ├── app.py            # Main CustomTkinter app
│   ├── admin_view.py     # Admin dashboard
│   └── wizard.py         # First-run setup wizard
├── server/               # Mobile camera server
│   ├── main.py           # FastAPI server
│   └── templates/        # Mobile camera UI
├── data/
│   └── database.py       # SQLite storage
├── docs/
│   └── index.html        # GitHub Pages landing page
├── run.py                # Main entry point
├── install.sh            # One-command setup
├── build.py              # macOS .app/.dmg packaging
├── build_windows.py      # Windows .exe packaging
├── build_linux.py        # Linux .AppImage packaging
├── requirements.txt      # Runtime dependencies
└── requirements-dev.txt  # Build & test dependencies
```

---

## Building Executables (Advanced)

The build scripts create standalone executables using PyInstaller. These are optional — most users should run from source.

```bash
pip install -r requirements-dev.txt

# macOS — creates dist/myBay.app (and optional .dmg)
python build.py              # .app only
python build.py --dmg        # .app + .dmg installer
python build.py --dmg --sign --notarize  # signed + notarized (requires Apple Developer ID)

# Windows — creates dist/windows/myBay/myBay.exe
python build_windows.py --clean

# Linux — creates dist/myBay-x86_64.AppImage
python build_linux.py --clean
```

Note: macOS signing/notarization requires an Apple Developer account. Without it, the .app works locally but will show Gatekeeper warnings on other machines.

---

## Running Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

93 tests covering AI vision, camera server, eBay API, GUI, database, presets, turbo mode, and Ollama integration.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App won't launch | `lsof -ti :8000 \| xargs kill -9` then retry |
| OpenAI not detected | Set `OPENAI_API_KEY` in `.env` |
| Ollama not detected | Run `ollama serve` and `ollama pull qwen3.5:2b` |
| Photos not appearing | Ensure phone and computer are on the same WiFi |
| eBay connection issues | Check credentials in Settings, ensure redirect URL is `http://localhost:8000/ebay/callback` |
| Publish fails: missing policies | Create payment, return, and shipping policies in eBay Seller Hub |
| Publish fails: invalid condition | App retries with fallback condition automatically |
| Images fail to upload | Ensure images are under 12 MB, valid format (JPG/PNG), and eBay token is fresh |

---

## Credits

- **AI**: [OpenAI](https://openai.com) + [Ollama](https://ollama.com)
- **GUI**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- **Background Removal**: [rembg](https://github.com/danielgatis/rembg)

## License

MIT License — Do whatever you want with it.

---

<p align="center"><i>List faster. Sell more. Live better.</i></p>

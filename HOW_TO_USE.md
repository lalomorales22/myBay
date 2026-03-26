# How to Use myBay

This guide walks you through setting up myBay from scratch — from creating developer accounts to publishing your first eBay listing.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Get an OpenAI API Key](#2-get-an-openai-api-key)
3. [Set Up an eBay Developer Account](#3-set-up-an-ebay-developer-account)
4. [Create an eBay Application (API Keys)](#4-create-an-ebay-application-api-keys)
5. [Install myBay](#5-install-mybay)
6. [Enter Your Credentials](#6-enter-your-credentials)
7. [Connect Your eBay Seller Account](#7-connect-your-ebay-seller-account)
8. [Your First Listing](#8-your-first-listing)
9. [Admin Dashboard (Business Backend)](#9-admin-dashboard-business-backend)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Requirement | Details |
|-------------|---------|
| **macOS** 12.0+ / Windows 10+ / Linux | Apple Silicon recommended for macOS |
| **Python** 3.10+ | Only if running from source (not needed for .dmg/.exe) |
| **eBay Seller Account** | A regular eBay account with selling enabled |
| **AI Backend** | OpenAI (paid, best quality) **or** Ollama (free, local) — at least one |
| **Same WiFi Network** | Your phone and computer must be on the same network for camera features |

---

## 2. Get an OpenAI API Key

myBay uses OpenAI's API for AI-powered product analysis (vision + web search) and the business assistant. The default model is `gpt-5.4-nano-2026-03-17`.

### Step-by-step:

1. Go to [https://platform.openai.com/signup](https://platform.openai.com/signup) and create an account (or sign in)
2. Navigate to **API Keys**: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
3. Click **"Create new secret key"**
4. Give it a name (e.g., "myBay") and click **Create**
5. **Copy the key immediately** — it starts with `sk-proj-...` and you won't be able to see it again
6. Save it somewhere safe for now (you'll enter it into myBay shortly)

### Important notes:

- OpenAI API usage is **pay-per-use**. Each product analysis costs roughly $0.01-0.05 depending on image count and model
- Set a **monthly spending limit** in your OpenAI account under Settings > Limits to avoid surprises
- You'll need to add a payment method (credit card) before the API key will work
- The model used by default is `gpt-5.4-nano-2026-03-17` — this can be overridden with the `OPENAI_VISION_MODEL` environment variable if needed

---

## 2b. Alternative: Use Ollama (Free Local AI)

If you don't want to create an OpenAI account or pay for API usage, you can use **Ollama** instead. Ollama runs AI models locally on your machine — completely free and private.

### Step-by-step:

1. Install Ollama:
   ```bash
   brew install ollama
   ```
2. Start the Ollama server:
   ```bash
   ollama serve
   ```
3. Pull a vision model (recommended: `qwen3.5:2b`):
   ```bash
   ollama pull qwen3.5:2b
   ```
4. That's it! myBay will auto-detect Ollama when you launch it.

### Optional: set a specific model

Add to your `.env` file:

```env
OLLAMA_VISION_MODEL=qwen3.5:2b
OLLAMA_URL=http://localhost:11434
```

### Recommended models:

| Model | RAM Needed | Quality | Speed |
|-------|-----------|---------|-------|
| `qwen3.5:2b` | ~2GB | **Good (recommended)** | Fast |
| `moondream` | ~2GB | Basic | Fast |
| `minicpm-v` | ~3GB | Good | Fast |
| `llava:7b` | ~5GB | Good | Medium |
| `llama3.2-vision:11b` | ~8GB | Best local | Slower |

### Trade-offs vs OpenAI:

- Ollama **cannot** do web search for live market pricing. myBay compensates by using eBay's Browse API for pricing data when Ollama is the backend.
- OpenAI generally produces more accurate product identification and richer descriptions.
- Ollama is free, private, and works offline.

---

## 3. Set Up an eBay Developer Account

The eBay Developer Program gives you API access to create listings programmatically.

### Step-by-step:

1. Go to [https://developer.ebay.com](https://developer.ebay.com)
2. Click **"Join"** or **"Sign In"** (use your regular eBay account or create a new one)
3. Complete the registration form
4. Verify your email address
5. You'll land on the **Developer Dashboard** at [https://developer.ebay.com/my/keys](https://developer.ebay.com/my/keys)

### Choose your program tier:

- **Individual** (free): 5,000 API calls/day — plenty for personal use
- **Enterprise**: Higher limits, apply if needed later

---

## 4. Create an eBay Application (API Keys)

You need to create an "application" in the eBay Developer Portal to get your API credentials. You'll want **two** sets — Sandbox (for testing) and Production (for real listings).

### Step-by-step:

1. Go to [https://developer.ebay.com/my/keys](https://developer.ebay.com/my/keys)
2. Click **"Create a keyset"** (or **"Application Keys"**)
3. Enter an **Application Title** (e.g., "myBay Desktop App")
4. You'll see two environments listed:

#### Sandbox Keys (for testing):

5. Under **Sandbox**, you'll see:
   - **App ID (Client ID)** — e.g., `YourName-myBay-SBX-abc123def-456789`
   - **Cert ID (Client Secret)** — click "Show" to reveal
   - **Dev ID** — shared across both environments
6. Click **"Configure Settings"** next to Sandbox
7. Under **RuName (eBay Redirect URL Name)**:
   - If no RuName exists, click **"Create"** or **"Generate"**
   - Set the **Auth Accepted URL** to: `http://localhost:8000/ebay/callback`
   - Set the **Auth Declined URL** to: `http://localhost:8000/ebay/callback`
   - Set the **Privacy Policy URL** to any URL (e.g., your website or `http://localhost:8000`)
   - Save it
8. **Copy your RuName** — it looks like `YourName-YourNam-myBay-SBX-xyzabc`

#### Production Keys (for real listings):

9. Under **Production**, click **"Create a keyset"** (or it may already exist)
10. You'll see the same three values: **App ID**, **Cert ID**, **Dev ID**
11. Click **"Configure Settings"** next to Production
12. Create/configure a **RuName** with the same redirect URLs:
    - Auth Accepted URL: `http://localhost:8000/ebay/callback`
    - Auth Declined URL: `http://localhost:8000/ebay/callback`
13. **Copy your Production RuName**

### Summary of what you need:

| Credential | Sandbox | Production |
|------------|---------|------------|
| **App ID (Client ID)** | From Sandbox keyset | From Production keyset |
| **Cert ID (Client Secret)** | From Sandbox keyset | From Production keyset |
| **Dev ID** | Shared (same for both) | Shared (same for both) |
| **RuName** | From Sandbox settings | From Production settings |

> **Tip:** Start with Sandbox to test everything. Switch to Production when you're ready to list real items.

---

## 5. Install myBay

### Option A: Download the App (Recommended)

1. Download `MyBay.dmg` (macOS), `MyBay.exe` (Windows), or `MyBay.AppImage` (Linux) from the Releases page
2. Install as usual for your platform
3. Launch the app — the Setup Wizard will guide you

### Option B: One-Command Install (macOS, from source)

```bash
cd mybay
chmod +x install.sh
./install.sh
```

This creates a virtual environment, installs dependencies, and generates a `.env` template.

### Option C: Manual Setup (any platform, from source)

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate          # Windows

pip install -r requirements.txt
cp .env.example .env
```

---

## 6. Enter Your Credentials

There are two ways to provide your API keys:

### Method 1: `.env` file (recommended for running from source)

Open the `.env` file in the project root and fill in your values:

```env
# Required — your OpenAI API key
OPENAI_API_KEY=sk-proj-YOUR_ACTUAL_KEY_HERE

# Optional — override the default AI model
# OPENAI_VISION_MODEL=gpt-5.4-nano-2026-03-17

# eBay Sandbox (for testing)
EBAY_SANDBOX_APP_ID=YourName-myBay-SBX-abc123def-456789
EBAY_SANDBOX_CERT_ID=SBX-your-cert-id-here
EBAY_SANDBOX_DEV_ID=your-dev-id-here

# eBay Production (for real listings)
EBAY_PRODUCTION_APP_ID=YourName-myBay-PRD-abc123def-456789
EBAY_PRODUCTION_CERT_ID=PRD-your-cert-id-here
EBAY_PRODUCTION_DEV_ID=your-dev-id-here

# Optional — only needed for phone camera access outside your local network
# NGROK_AUTHTOKEN=your-ngrok-token
```

### Method 2: Settings Panel (recommended for .dmg/.exe installs)

1. Launch myBay
2. The **Setup Wizard** will appear on first launch
3. It walks you through entering:
   - Your OpenAI API key (tested live during setup)
   - Your eBay credentials (OAuth login flow)
   - Business location
   - Shipping/return/pricing preferences
4. You can also access Settings anytime via the **Settings** button in the top-right

### Where credentials are stored:

| File | Contents | Location |
|------|----------|----------|
| `.env` | OpenAI key, eBay App/Cert/Dev IDs | Project root (source) or app data dir |
| `.ebay_config.json` | OAuth tokens, RuName, environment | `~/Library/Application Support/myBay/` (macOS) |

Both files are excluded from git via `.gitignore`.

---

## 7. Connect Your eBay Seller Account

After entering your eBay API credentials, you need to authorize myBay to access your seller account via OAuth:

1. In the app, go to **Settings** (or the Setup Wizard handles this)
2. Select your environment: **Sandbox** or **Production**
3. Enter your **App ID**, **Cert ID**, and **RuName** for that environment
4. Click **"Connect eBay Account"**
5. A browser window opens with the eBay login page
6. Sign in with your **eBay seller account** (not your developer account)
7. Grant permission to the app
8. You'll be redirected to `http://localhost:8000/ebay/callback` — the app captures the authorization automatically
9. You should see a success message in the app

### Production: Set Up Business Policies First

Before publishing to Production, eBay requires **Business Policies** on your seller account:

1. Go to [eBay Seller Hub](https://www.ebay.com/sh/landing)
2. Navigate to **Account > Business Policies**
3. Create at least one of each:
   - **Payment Policy** (e.g., "Immediate Payment Required")
   - **Return Policy** (e.g., "30-Day Returns")
   - **Shipping/Fulfillment Policy** (e.g., "USPS Ground Advantage")
4. Note the **Policy IDs** — enter them in myBay's Settings or the Setup Wizard will detect them

---

## 8. Your First Listing

### The Snap-List-Sell Workflow

1. **Launch the app**: `python3 run.py --gui` (from source) or open the installed app
2. **Scan the QR code**: The app displays a QR code — scan it with your iPhone camera
3. **Take photos**: The mobile camera UI opens. Take 1-3 photos of your item
4. **AI analyzes the photos**: Within seconds, OpenAI identifies the product and generates:
   - Title (optimized for eBay search, max 80 characters)
   - Description (2-3 detailed sentences)
   - Category suggestion
   - Condition assessment
   - Price recommendation (based on web search of current market prices)
5. **Review the draft**: The item appears in your Draft Queue on the left sidebar
6. **Edit if needed**: Click the draft to review/edit title, price, description, etc.
7. **Publish**: Click the **Publish** button — the app uploads images to eBay and creates the listing
8. **Verify**: The app confirms the listing with an eBay listing ID and verification status

### Tips:

- **Turbo Mode**: Enable in Settings to auto-publish high-confidence items (90%+ confidence) without manual review. Includes a 30-second undo window.
- **Background Removal**: The app can automatically remove backgrounds for professional-looking product photos (requires the optional `rembg` dependency).
- **Offline Support**: If you lose internet, listings queue locally and auto-publish when reconnected.

---

## 9. Admin Dashboard (Business Backend)

Click the **Admin** button in the header to access the full business management suite.

### AI Business Assistant

The fastest way to log transactions. Just type in plain English:

```
"spent $25 at goodwill on inventory, drove 12 miles"
"sold a vintage camera for $85 on ebay, $11 in fees"
"bought $8 of shipping tape at walmart"
```

The AI parses your message and automatically creates expense, income, and/or mileage entries.

### Available Tabs:

| Tab | What It Does |
|-----|--------------|
| **AI Assistant** | Natural language transaction entry |
| **Business Info** | Store DBA name, EIN, permits, bank info |
| **Expenses** | Track by category with receipt image uploads |
| **Income** | Manual entry + import sold eBay listings |
| **Mileage** | IRS standard rate trip logging |
| **Documents** | Upload permits, EIN letters, tax certs (with expiry warnings) |
| **Tax Summary** | Schedule C P&L, quarterly tax estimates, 1099-K reconciliation |
| **Export CSV** | Date-range exports, individual or bundled ZIP with receipts |

---

## 10. Troubleshooting

### "OPENAI_API_KEY is not set"

- Make sure your `.env` file has a valid key: `OPENAI_API_KEY=sk-proj-...`
- Or set it in your shell: `export OPENAI_API_KEY="sk-proj-..."`
- Restart the app after changing environment variables

### "eBay OAuth failed" or "Token expired"

- Go to Settings and click **"Connect eBay Account"** to re-authorize
- Make sure your redirect URL is set to `http://localhost:8000/ebay/callback` in the eBay Developer Portal
- Check that port 8000 is not blocked by another process: `lsof -ti :8000`

### "Missing business policies" on Production publish

- Create Payment, Return, and Shipping policies in eBay Seller Hub
- Re-authenticate your Production eBay connection after creating policies

### Photos not appearing from phone

- Ensure phone and computer are on the same WiFi network
- Check that the camera server is running (status shown in the app)
- Try refreshing the QR code in the app

### OpenAI rate limit (429 error)

- You've hit your API usage limit
- Check your limits at [https://platform.openai.com/settings](https://platform.openai.com/settings)
- Wait a minute and try again, or increase your spending limit

### Need more help?

- Check the full `README.md` for detailed troubleshooting
- Report issues at the project's GitHub Issues page

---

## Quick Reference: All API Keys You Need

| Service | What to Get | Where to Get It |
|---------|-------------|-----------------|
| **OpenAI** | API Key (`sk-proj-...`) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **eBay** | App ID (Client ID) | [developer.ebay.com/my/keys](https://developer.ebay.com/my/keys) |
| **eBay** | Cert ID (Client Secret) | Same page as above |
| **eBay** | Dev ID | Same page as above |
| **eBay** | RuName (Redirect URL Name) | Configure Settings for your app on eBay Dev Portal |
| **ngrok** (optional) | Auth Token | [dashboard.ngrok.com](https://dashboard.ngrok.com) |

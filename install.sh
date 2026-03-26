#!/bin/bash
# ============================================================================
# myBay - Install Script for macOS
#
# This script sets up everything you need to run the app from source.
# Run it once on a fresh Mac:
#
#   chmod +x install.sh
#   ./install.sh
#
# ============================================================================

set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/venv"
ENV_FILE="$APP_DIR/.env"
ENV_EXAMPLE="$APP_DIR/.env.example"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║       📦 myBay — Installer                                ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# ------------------------------------------------------------------
# 1. Check for Python 3.10+
# ------------------------------------------------------------------
echo "🔍 Checking Python..."

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            echo "   ✅ Found $cmd ($version)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "   ❌ Python 3.10+ is required but not found."
    echo ""
    echo "   Install Python with Homebrew:"
    echo "     /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "     brew install python@3.11"
    echo ""
    echo "   Then re-run this script."
    exit 1
fi

# ------------------------------------------------------------------
# 2. Create virtual environment
# ------------------------------------------------------------------
echo ""
echo "📦 Setting up virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON" -m venv "$VENV_DIR"
    echo "   ✅ Created venv at $VENV_DIR"
else
    echo "   ✅ Venv already exists"
fi

source "$VENV_DIR/bin/activate"

# ------------------------------------------------------------------
# 3. Install dependencies
# ------------------------------------------------------------------
echo ""
echo "📥 Installing dependencies (this may take a minute)..."

pip install --upgrade pip -q
pip install -r "$APP_DIR/requirements.txt" -q

echo "   ✅ All dependencies installed"

# ------------------------------------------------------------------
# 4. Set up .env file
# ------------------------------------------------------------------
echo ""
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo "⚙️  Created .env from template."
    else
        cat > "$ENV_FILE" << 'ENVEOF'
# myBay - Environment Variables
OPENAI_API_KEY=
EBAY_SANDBOX_APP_ID=
EBAY_SANDBOX_CERT_ID=
EBAY_SANDBOX_DEV_ID=
EBAY_PRODUCTION_APP_ID=
EBAY_PRODUCTION_CERT_ID=
EBAY_PRODUCTION_DEV_ID=
ENVEOF
        echo "⚙️  Created blank .env file."
    fi
    echo ""
    echo "   ⚠️  You MUST edit .env with your API keys before running!"
    echo "   Open it with:  nano $ENV_FILE"
    NEEDS_KEYS=true
else
    echo "⚙️  .env already exists"
    # Check if keys are filled in
    if grep -q "OPENAI_API_KEY=sk-" "$ENV_FILE" 2>/dev/null; then
        echo "   ✅ OpenAI key found"
    else
        echo "   ⚠️  OpenAI key appears empty — edit .env before running"
        NEEDS_KEYS=true
    fi
fi

# ------------------------------------------------------------------
# 5. Verify key modules load
# ------------------------------------------------------------------
echo ""
echo "🧪 Verifying installation..."

# Use the venv python (already activated), not the system python
python -c "import _tkinter" 2>/dev/null || {
    echo "   ❌ Tkinter is not available for your Python."
    echo "      Fix with:  brew install python-tk@$($PYTHON -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')"
    echo "      Then re-run:  rm -rf venv && ./install.sh"
    exit 1
}
echo "   ✅ Tkinter"

python -c "
import customtkinter; print('   ✅ CustomTkinter')
import httpx; print('   ✅ httpx')
import fastapi; print('   ✅ FastAPI')
from PIL import Image; print('   ✅ Pillow')
" 2>/dev/null || {
    echo "   ❌ Some packages failed to import. Try re-running:"
    echo "      source venv/bin/activate && pip install -r requirements.txt"
    exit 1
}

# ------------------------------------------------------------------
# 6. Create launch shortcut
# ------------------------------------------------------------------
LAUNCH_SCRIPT="$APP_DIR/start.command"
cat > "$LAUNCH_SCRIPT" << 'STARTEOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python run.py --gui
STARTEOF
chmod +x "$LAUNCH_SCRIPT"
echo ""
echo "🚀 Created start.command (double-click to launch!)"

# ------------------------------------------------------------------
# Done!
# ------------------------------------------------------------------
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                 ✅ Installation Complete!                  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

if [ "$NEEDS_KEYS" = true ]; then
    echo "👉 NEXT STEPS:"
    echo "   1. Edit your API keys:  nano .env"
    echo "   2. Launch the app:      double-click start.command"
    echo "                    or:    source venv/bin/activate && python run.py --gui"
else
    echo "👉 TO LAUNCH:"
    echo "   Double-click start.command"
    echo "   or: source venv/bin/activate && python run.py --gui"
fi

echo ""
echo "📱 On first launch, the Setup Wizard will guide you through"
echo "   connecting your eBay account."
echo ""

#!/usr/bin/env bash
# VigIA - Setup Script
# Run this script once to set up the environment

set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         VigIA - Setup Script              ║"
echo "║   Sistema de Vigilancia Residencial       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 1. Check Python ───────────────────────────────────────────────────────────
echo "▶ Verificando Python..."
if ! command -v python3 &>/dev/null; then
    echo "  ✗ Python 3 no encontrado. Instálalo desde https://python.org"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1)
echo "  ✓ $PYTHON_VERSION"

# ── 2. System dependencies ────────────────────────────────────────────────────
echo ""
echo "▶ Instalando dependencias del sistema..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y \
        cmake \
        build-essential \
        libopenblas-dev \
        liblapack-dev \
        libx11-dev \
        libgl1-mesa-glx \
        libglib2.0-0 \
        python3-dev \
        python3-venv \
        libv4l-dev \
        v4l-utils \
        2>/dev/null || echo "  ⚠ Algunos paquetes no se pudieron instalar (continúa de todas formas)"
    echo "  ✓ Dependencias del sistema instaladas"
elif command -v brew &>/dev/null; then
    brew install cmake openblas lapack 2>/dev/null || true
    echo "  ✓ Dependencias macOS instaladas"
else
    echo "  ⚠ No se pudo detectar el gestor de paquetes. Instala cmake y dlib manualmente si hay errores."
fi

# ── 3. Virtual environment ────────────────────────────────────────────────────
echo ""
echo "▶ Creando entorno virtual..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Entorno virtual creado en ./venv"
else
    echo "  ✓ Entorno virtual ya existe"
fi

# Activate
source venv/bin/activate
echo "  ✓ Entorno virtual activado"

# Upgrade pip
pip install --upgrade pip --quiet

# ── 4. Python dependencies ────────────────────────────────────────────────────
echo ""
echo "▶ Instalando dependencias Python..."
echo "  (Esto puede tomar varios minutos - dlib requiere compilación)"
echo ""
pip install -r backend/requirements.txt
echo "  ✓ Dependencias instaladas"

# ── 5. .env file ──────────────────────────────────────────────────────────────
echo ""
echo "▶ Configurando variables de entorno..."
if [ ! -f ".env" ]; then
    cp backend/.env.example .env
    # Generate random secret key
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change-this-secret-key-vigia-2024/$SECRET/" .env
    echo "  ✓ .env creado con clave secreta generada automáticamente"
    echo "  ⚠ Edita .env para configurar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID"
else
    echo "  ✓ .env ya existe"
fi

# ── 6. Data directories ───────────────────────────────────────────────────────
echo ""
echo "▶ Creando directorios de datos..."
mkdir -p data/faces data/events
echo "  ✓ data/faces  y  data/events  listos"

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           Setup completado               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Para iniciar VigIA:"
echo ""
echo "    source venv/bin/activate"
echo "    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "  Luego abre en tu navegador:"
echo "    http://localhost:8000/app"
echo ""
echo "  Credenciales por defecto:"
echo "    Usuario:    admin"
echo "    Contraseña: vigia123"
echo ""
echo "  Configura Telegram en:"
echo "    http://localhost:8000/app#settings"
echo ""

# Optionally start immediately
read -p "  ¿Iniciar VigIA ahora? [s/N]: " SHOULD_START
if [[ "$SHOULD_START" =~ ^[Ss]$ ]]; then
    echo ""
    echo "  Iniciando VigIA en http://localhost:8000 ..."
    echo "  (Ctrl+C para detener)"
    echo ""
    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
fi

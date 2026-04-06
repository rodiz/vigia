# VigIA - Sistema de Vigilancia para Conjuntos Residenciales

Sistema SaaS local de vigilancia inteligente con reconocimiento facial, detección de objetos y notificaciones en tiempo real via Telegram.

## Características principales

- **Reconocimiento facial** - Identifica residentes y visitantes registrados usando face_recognition (dlib)
- **Detección de objetos** - YOLOv8n detecta personas, vehículos y objetos de interés
- **Streaming de cámaras** - Soporte RTSP (cámaras IP) y webcams USB/integradas
- **Notificaciones Telegram** - Alertas instantáneas con foto al detectar personas
- **Bitácora de accesos** - Registro completo con filtros y exportación CSV
- **Interfaz web** - SPA Bootstrap 5 con tema oscuro, sin build step

## Inicio rápido

### Opción 1: Script de instalación (recomendado)

```bash
cd /home/admi/Escritorio/VigIA
chmod +x setup.sh
./setup.sh
```

### Opción 2: Manual

```bash
# 1. Instalar dependencias del sistema (Ubuntu/Debian)
sudo apt-get install cmake build-essential libopenblas-dev liblapack-dev libx11-dev libgl1-mesa-glx python3-venv

# 2. Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias Python
pip install -r backend/requirements.txt

# 4. Configurar entorno
cp backend/.env.example .env
# Editar .env con tus valores

# 5. Crear directorios
mkdir -p data/faces data/events

# 6. Iniciar
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Opción 3: Docker

```bash
docker-compose up --build
```

## Acceso

- **Frontend:** http://localhost:8000/app
- **API Docs:** http://localhost:8000/docs
- **Usuario:** admin / **Contraseña:** vigia123

## Configuración

Edita el archivo `.env`:

```env
SECRET_KEY=tu-clave-secreta-aleatoria
TELEGRAM_BOT_TOKEN=token-de-tu-bot
TELEGRAM_CHAT_ID=-100tu-chat-id
FACE_CONFIDENCE_THRESHOLD=0.6
DATABASE_URL=sqlite:///./data/vigia.db
DATA_DIR=./data
```

### Configurar bot de Telegram

1. Habla con [@BotFather](https://t.me/botfather) en Telegram
2. Crea un nuevo bot con `/newbot`
3. Copia el token al `.env` o la interfaz web
4. Agrega el bot a tu grupo/canal
5. Obtén el chat ID (usa [@userinfobot](https://t.me/userinfobot))
6. Prueba la conexión en Configuración → Telegram

### Agregar cámaras

En la interfaz: **Configuración → Cámaras → Agregar cámara**

- **Webcam local:** URL = `0`, `1`, `2`...
- **RTSP IP Cam:** URL = `rtsp://usuario:contraseña@192.168.1.10:554/stream`

## Estructura del proyecto

```
VigIA/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, WebSockets, startup
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Pydantic schemas
│   │   ├── auth.py          # JWT authentication
│   │   ├── camera.py        # Camera stream management
│   │   ├── recognition.py   # Face recognition + YOLO
│   │   ├── notifications.py # Telegram notifications
│   │   └── routers/         # API route handlers
│   └── requirements.txt
├── frontend/
│   ├── index.html           # SPA shell
│   ├── js/                  # Page controllers + API client
│   └── css/style.css
├── data/
│   ├── faces/               # Face photos (residents + visitors)
│   └── events/              # Snapshot images by date
├── setup.sh                 # One-click setup
└── docker-compose.yml
```

## API endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, retorna JWT |
| GET | `/api/residents/` | Listar residentes |
| POST | `/api/residents/{id}/face` | Subir foto facial |
| GET | `/api/visitors/` | Listar visitantes |
| POST | `/api/visitors/recognize` | Reconocer persona en foto |
| GET | `/api/events/` | Bitácora de accesos |
| GET | `/api/events/stats` | Estadísticas del día |
| GET | `/api/cameras/{id}/stream` | Stream MJPEG |
| WS | `/ws/camera/{id}` | WebSocket con detecciones |
| WS | `/ws/events` | Stream de eventos en tiempo real |

## Notas de rendimiento

- El reconocimiento facial se ejecuta cada **500ms** (no cada frame) para reducir CPU
- YOLO usa el modelo `yolov8n.pt` (nano) para mayor velocidad
- Las imágenes de rostros se redimensionan a 50% antes del reconocimiento
- Se guarda snapshot JPEG de cada detección en `data/events/YYYY-MM-DD/`
- Cooldown de 30 segundos por persona detectada para evitar spam de logs

## Requisitos del sistema

- Python 3.10+
- Ubuntu 20.04+ / macOS 12+ / Windows 10+ (WSL2 recomendado)
- RAM: mínimo 2GB (4GB recomendado con YOLO activo)
- CPU: i5 o equivalente (webcam 720p @ 15fps)
- Disco: 500MB para dependencias + datos de operación

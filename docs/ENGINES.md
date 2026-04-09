# Motores biométricos de VigIA

## Arquitectura

```
recognition.py (shim de compatibilidad)
    └── services/recognition_service.py  (orquestación)
            ├── biometrics/factory.py    (selección por env var)
            │       ├── dlib_engine.py   (motor legacy)
            │       └── insightface_engine.py  (motor nuevo)
            └── services/face_registry_service.py  (embeddings en memoria)
```

Los routers existentes (`residents.py`, `visitors.py`, `main.py`) no cambiaron
su import: `from .recognition import recognition_service`. El shim redirige
transparentemente al nuevo servicio.

---

## Motor activo por defecto: `dlib`

El sistema arranca con `FACE_ENGINE=dlib` si no se configura nada.
Esto garantiza que el MVP actual siga funcionando sin ningún cambio.

---

## Activar InsightFace

### 1. Instalar dependencias

```bash
source venv/bin/activate
pip install insightface onnxruntime
```

Para GPU (si disponible):
```bash
pip install insightface onnxruntime-gpu
```

### 2. Configurar variable de entorno

En `.env`:
```env
FACE_ENGINE=insightface
INSIGHTFACE_MODEL=buffalo_s        # liviano (recomendado para la mayoría)
# INSIGHTFACE_MODEL=buffalo_l      # más preciso, más lento
FACE_CONFIDENCE_THRESHOLD=0.45     # InsightFace usa escala diferente a dlib
```

### 3. Reindexar embeddings

Los embeddings de dlib (128 dims) no son compatibles con InsightFace (512 dims).
Antes de reiniciar el servidor, regenera los embeddings:

```bash
# Dry run primero (sin escribir en BD)
python backend/scripts/reindex_embeddings.py --engine insightface --dry-run

# Si el dry run se ve bien, ejecutar real
python backend/scripts/reindex_embeddings.py --engine insightface
```

### 4. Reiniciar el servidor

```bash
./start.sh
```

Al arrancar, el log mostrará:
```
Motor biométrico activo: InsightFaceEngine (buffalo_s)
```

---

## Volver a dlib (rollback)

### Opción 1 — Solo env var (instantáneo)

En `.env`:
```env
FACE_ENGINE=dlib
FACE_CONFIDENCE_THRESHOLD=0.6
```

Reiniciar el servidor. Si hay embeddings dlib en la BD, funcionan de inmediato.
Si se reindexó con InsightFace, re-ejecutar reindex con dlib:

```bash
python backend/scripts/reindex_embeddings.py --engine dlib
```

### Opción 2 — Git rollback de la rama

```bash
git checkout master
./start.sh
```

---

## Comparar motores antes de migrar

```bash
# Comparar detección en una foto de residente
python backend/scripts/compare_engines.py --image data/faces/resident_1.jpg

# Comparar score entre dos fotos del mismo residente
python backend/scripts/compare_engines.py \
  --image data/faces/resident_1.jpg \
  --against data/faces/resident_1_alt.jpg
```

Salida esperada:
```
┌─────────────────────┬───────────────┬──────────────────────────────┐
│                     │ dlib          │ insightface                  │
├─────────────────────┼───────────────┼──────────────────────────────┤
│ Rostro detectado    │ ✓             │ ✓                            │
│ Embedding dim       │ 128           │ 512                          │
│ Tiempo encoding     │ 342ms         │ 78ms                         │
│ Score vs --against  │ 0.821         │ 0.923                        │
│ Error               │ —             │ —                            │
└─────────────────────┴───────────────┴──────────────────────────────┘
```

---

## Variables de entorno del motor biométrico

| Variable | Default | Descripción |
|---|---|---|
| `FACE_ENGINE` | `dlib` | Motor activo: `dlib` o `insightface` |
| `INSIGHTFACE_MODEL` | `buffalo_s` | Modelo: `buffalo_s` (liviano) o `buffalo_l` (preciso) |
| `FACE_CONFIDENCE_THRESHOLD` | `0.6` | Score mínimo para declarar match (dlib: ~0.6, InsightFace: ~0.45) |
| `RECOGNITION_INTERVAL` | `1.0` | Segundos entre inferencias en el loop de cámara |
| `RECOGNITION_DOWNSCALE` | `0.5` | Factor de resize antes de inferencia (dlib aplica, InsightFace no) |
| `RECOGNITION_MAX_FPS` | `5` | Máx frames/seg con IA (futuro rate limiter) |
| `DETECTION_COOLDOWN_SECONDS` | `30` | Cooldown entre alertas Telegram por cámara |

---

## Recomendaciones por plataforma

### Laptop / mini PC x86
```env
FACE_ENGINE=insightface
INSIGHTFACE_MODEL=buffalo_l
FACE_CONFIDENCE_THRESHOLD=0.45
RECOGNITION_INTERVAL=0.5
```

### Raspberry Pi 5
```env
FACE_ENGINE=insightface
INSIGHTFACE_MODEL=buffalo_s
FACE_CONFIDENCE_THRESHOLD=0.45
RECOGNITION_INTERVAL=2.0
RECOGNITION_DOWNSCALE=0.25
```
> En Pi, la primera inferencia puede tardar 5-10s mientras carga el modelo ONNX.
> Las siguientes serán ~100-200ms.

### Tablet como cliente UI (backend remoto)
La tablet solo muestra el stream de video y la UI web.
La inferencia corre en el servidor backend (laptop, mini PC o VPS).
No se necesita instalar insightface ni face-recognition en la tablet.

```env
# En el SERVIDOR (no en la tablet)
FACE_ENGINE=insightface
INSIGHTFACE_MODEL=buffalo_s
```

La tablet accede a `http://IP_SERVIDOR:8000/app` desde su navegador.

---

## Compatibilidad de embeddings

| Motor | Dimensión | Método de similitud | Umbral recomendado |
|---|---|---|---|
| `dlib_hog_128` | 128 | Distancia euclídea | 0.60 |
| `insightface_buffalo_s_512` | 512 | Similitud coseno | 0.45 |
| `insightface_buffalo_l_512` | 512 | Similitud coseno | 0.45 |

**Los embeddings de distintos motores NO son compatibles entre sí.**
Al cambiar de motor, ejecutar `reindex_embeddings.py` antes de reiniciar.

Si se cambia de motor sin reindexar, `FaceRegistryService` omite los embeddings
incompatibles y los registra como advertencia en el log. El sistema no crashea
pero nadie será reconocido hasta reindexar.

---

## Por qué biometría como apoyo, no como decisión final

Este sistema es para portería residencial. La biometría es una **sugerencia**,
no una autorización automática:

1. **Tasas de error**: Incluso InsightFace tiene falsos positivos y negativos.
   En una portería, un falso positivo deja entrar a quien no debe.

2. **Variaciones reales**: Luz, ángulo, lentes, mascarilla, cámara económica.
   El sistema ve casos que no estaban en el entrenamiento del modelo.

3. **Responsabilidad**: La decisión de acceso tiene consecuencias legales y
   de seguridad. Debe recaer en un humano, no en un umbral numérico.

4. **YOLO no identifica personas**: YOLOv8 detecta la clase "person" (presencia)
   pero no puede distinguir entre individuos. No se usa para identidad.

El flujo correcto es siempre:
```
Cámara detecta → Sistema sugiere → Portero confirma/rechaza → Se registra evento
```

---

## Archivos creados en esta rama

| Archivo | Descripción |
|---|---|
| `backend/app/core/settings.py` | Configuración centralizada |
| `backend/app/biometrics/base.py` | Interfaz abstracta FaceEngine |
| `backend/app/biometrics/dlib_engine.py` | Motor legacy (dlib) |
| `backend/app/biometrics/insightface_engine.py` | Motor nuevo (InsightFace) |
| `backend/app/biometrics/factory.py` | Selector con fallback |
| `backend/app/services/recognition_service.py` | Orquestación principal |
| `backend/app/services/face_registry_service.py` | Gestión de embeddings en memoria |
| `backend/scripts/compare_engines.py` | Comparación side-by-side |
| `backend/scripts/reindex_embeddings.py` | Migración de embeddings |
| `docs/ENGINES.md` | Esta documentación |

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `backend/app/recognition.py` | Shim al final: re-exporta desde services/ |
| `backend/app/models.py` | 3 columnas nullable de metadatos en Resident y Visitor |
| `backend/app/routers/residents.py` | Guarda embedding_model al registrar foto |
| `backend/app/routers/visitors.py` | Guarda embedding_model al registrar foto |
| `backend/requirements.txt` | Agrega insightface + onnxruntime |

## Archivos NO modificados

`main.py`, `auth.py`, `camera.py`, `database.py`, `notifications.py`,
`schemas.py`, `routers/auth.py`, `routers/events.py`, `routers/settings.py`,
todo el frontend.

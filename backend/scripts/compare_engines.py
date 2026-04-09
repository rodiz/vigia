"""
compare_engines.py — Compara DlibFaceEngine vs InsightFaceEngine sobre la misma imagen.

Uso:
    python backend/scripts/compare_engines.py --image data/faces/resident_1.jpg
    python backend/scripts/compare_engines.py --image data/faces/resident_1.jpg --against data/faces/resident_2.jpg

Qué evalúa:
    - ¿Se detectó rostro?
    - Dimensión del embedding generado
    - Tiempo de procesamiento
    - Score de similitud contra una segunda imagen (si se provee --against)
    - Errores si algún motor falla

Propósito:
    Validar que InsightFace detecta y genera embeddings correctamente
    antes de activarlo en producción. No modifica ningún dato.

Ejemplo de salida:
    ┌─────────────────────┬───────────────┬──────────────────────────────┐
    │                     │ dlib          │ insightface                  │
    ├─────────────────────┼───────────────┼──────────────────────────────┤
    │ Rostro detectado    │ ✓             │ ✓                            │
    │ Embedding dim       │ 128           │ 512                          │
    │ Tiempo encoding     │ 342ms         │ 78ms                         │
    │ Score vs --against  │ 0.821         │ 0.923                        │
    │ Error               │ —             │ —                            │
    └─────────────────────┴───────────────┴──────────────────────────────┘
"""

import argparse
import sys
import time
from pathlib import Path

# Asegurar que el root del proyecto esté en el path
_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))


def _load_image(path: str) -> bytes:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: No se encontró la imagen: {path}")
        sys.exit(1)
    return p.read_bytes()


def _run_engine(engine_name: str, image_bytes: bytes, against_bytes: bytes | None) -> dict:
    result = {
        "engine": engine_name,
        "detected": False,
        "embedding_dim": 0,
        "encoding_ms": 0,
        "score": None,
        "error": None,
    }

    try:
        if engine_name == "dlib":
            from backend.app.biometrics.dlib_engine import DlibFaceEngine
            engine = DlibFaceEngine()
        elif engine_name == "insightface":
            from backend.app.biometrics.insightface_engine import InsightFaceEngine
            from backend.app.core.settings import settings
            engine = InsightFaceEngine(model_name=settings.insightface_model)
            engine.warmup()
        else:
            result["error"] = f"Motor desconocido: {engine_name}"
            return result

        if not engine.is_available():
            result["error"] = f"{engine_name} no está instalado"
            return result

        # ── Encode imagen principal ──
        t0 = time.perf_counter()
        enc_result = engine.encode_face(image_bytes)
        result["encoding_ms"] = round((time.perf_counter() - t0) * 1000)
        result["detected"] = enc_result.detected
        result["embedding_dim"] = enc_result.embedding_dim
        result["error"] = enc_result.error

        if enc_result.embedding is None:
            return result

        # ── Score contra segunda imagen si se provee ──
        if against_bytes is not None:
            enc_against = engine.encode_face(against_bytes)
            if enc_against.embedding is not None:
                import numpy as np
                e1 = np.array(enc_result.embedding)
                e2 = np.array(enc_against.embedding)

                if engine_name == "dlib":
                    # dlib: distancia euclídea → score = 1 - dist
                    dist = float(np.linalg.norm(e1 - e2))
                    result["score"] = round(max(0.0, 1.0 - dist), 3)
                else:
                    # InsightFace: coseno (producto punto, ya normalizados)
                    result["score"] = round(float(np.dot(e1 / np.linalg.norm(e1),
                                                          e2 / np.linalg.norm(e2))), 3)
            else:
                result["score"] = "N/A (sin rostro en --against)"

    except Exception as exc:
        result["error"] = str(exc)

    return result


def _print_table(r_dlib: dict, r_if: dict, has_against: bool):
    CHECK = "✓"
    CROSS = "✗"
    DASH  = "—"

    def fmt_bool(v):  return CHECK if v else CROSS
    def fmt_ms(v):    return f"{v}ms"
    def fmt_score(v): return str(v) if v is not None else DASH
    def fmt_err(v):   return v if v else DASH
    def fmt_dim(v):   return str(v) if v else DASH

    rows = [
        ("Rostro detectado",   fmt_bool(r_dlib["detected"]),         fmt_bool(r_if["detected"])),
        ("Embedding dim",      fmt_dim(r_dlib["embedding_dim"]),      fmt_dim(r_if["embedding_dim"])),
        ("Tiempo encoding",    fmt_ms(r_dlib["encoding_ms"]),         fmt_ms(r_if["encoding_ms"])),
    ]
    if has_against:
        rows.append(("Score vs --against", fmt_score(r_dlib["score"]), fmt_score(r_if["score"])))
    rows.append(("Error", fmt_err(r_dlib["error"]), fmt_err(r_if["error"])))

    col0 = max(len(r[0]) for r in rows) + 2
    col1 = max(len(r[1]) for r in rows) + 2
    col2 = max(len(r[2]) for r in rows) + 2

    sep = f"├{'─' * col0}┼{'─' * col1}┼{'─' * col2}┤"
    top = f"┌{'─' * col0}┬{'─' * col1}┬{'─' * col2}┐"
    bot = f"└{'─' * col0}┴{'─' * col1}┴{'─' * col2}┘"
    hdr = f"│{'':^{col0}}│{'dlib':^{col1}}│{'insightface':^{col2}}│"

    print()
    print(top)
    print(hdr)
    for row in rows:
        print(sep)
        print(f"│{row[0]:<{col0}}│{row[1]:^{col1}}│{row[2]:^{col2}}│")
    print(bot)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Compara DlibFaceEngine vs InsightFaceEngine sobre la misma imagen"
    )
    parser.add_argument("--image", required=True, help="Ruta a la imagen principal")
    parser.add_argument(
        "--against",
        help="Segunda imagen para calcular score de similitud (opcional)",
    )
    parser.add_argument(
        "--engine",
        choices=["dlib", "insightface", "both"],
        default="both",
        help="Motor a probar (default: both)",
    )
    args = parser.parse_args()

    image_bytes = _load_image(args.image)
    against_bytes = _load_image(args.against) if args.against else None

    print(f"\nImagen principal : {args.image}")
    if args.against:
        print(f"Comparar contra  : {args.against}")

    r_dlib = _run_engine("dlib", image_bytes, against_bytes)
    r_if   = _run_engine("insightface", image_bytes, against_bytes)

    _print_table(r_dlib, r_if, has_against=against_bytes is not None)

    # Resumen de recomendación
    if r_dlib["detected"] and r_if["detected"]:
        print("Ambos motores detectaron el rostro correctamente.")
        if r_if["encoding_ms"] < r_dlib["encoding_ms"]:
            print(f"InsightFace fue {r_dlib['encoding_ms'] - r_if['encoding_ms']}ms más rápido.")
        if args.against and isinstance(r_if["score"], float) and isinstance(r_dlib["score"], float):
            if r_if["score"] > r_dlib["score"]:
                print(f"InsightFace obtuvo score más alto ({r_if['score']} vs {r_dlib['score']}).")
    elif not r_dlib["detected"] and not r_if["detected"]:
        print("ADVERTENCIA: Ningún motor detectó un rostro. Verifica la imagen.")
    else:
        detected = "dlib" if r_dlib["detected"] else "insightface"
        missed   = "insightface" if r_dlib["detected"] else "dlib"
        print(f"NOTA: {detected} detectó el rostro pero {missed} no.")


if __name__ == "__main__":
    main()

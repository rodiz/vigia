"""
reindex_embeddings.py — Regenera todos los embeddings con el motor especificado.

CUÁNDO SE NECESITA
-------------------
Al cambiar FACE_ENGINE de "dlib" a "insightface" (o viceversa), los embeddings
almacenados en la BD son incompatibles: dlib genera vectores de 128 dims y
InsightFace de 512 dims. FaceRegistryService omite automáticamente los embeddings
incompatibles, lo que significa que nadie sería reconocido hasta reindexar.

Este script:
  1. Lee todos los residentes/visitantes con foto registrada.
  2. Regenera el embedding de cada foto con el motor indicado.
  3. Actualiza face_encoding, embedding_model, embedding_created_at en la BD.
  4. Reporta éxitos, fallos y advertencias.

CÓMO USARLO
------------
# Reindexar con dlib (motor legacy):
python backend/scripts/reindex_embeddings.py --engine dlib

# Reindexar con insightface:
python backend/scripts/reindex_embeddings.py --engine insightface

# Dry run (simula sin escribir en BD):
python backend/scripts/reindex_embeddings.py --engine insightface --dry-run

# Solo residentes:
python backend/scripts/reindex_embeddings.py --engine insightface --only residents

# Solo visitantes:
python backend/scripts/reindex_embeddings.py --engine insightface --only visitors

SEGURIDAD
---------
- No elimina ningún registro ni foto.
- Solo actualiza los campos de embedding en BD.
- Hace un commit por registro (no one shot) para evitar perder todo si falla.
- En caso de error en un registro, lo reporta y continúa con el siguiente.

NOTA: Este script lee las fotos desde foto_path.
Si las fotos fueron movidas o eliminadas, esos registros serán omitidos.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))


def _build_engine(engine_name: str):
    if engine_name == "dlib":
        from backend.app.biometrics.dlib_engine import DlibFaceEngine
        engine = DlibFaceEngine()
    elif engine_name == "insightface":
        from backend.app.biometrics.insightface_engine import InsightFaceEngine
        from backend.app.core.settings import settings
        engine = InsightFaceEngine(model_name=settings.insightface_model)
        print(f"Calentando modelo InsightFace ({settings.insightface_model})...")
        engine.warmup()
    else:
        print(f"Motor desconocido: {engine_name}")
        sys.exit(1)

    if not engine.is_available():
        print(f"ERROR: El motor '{engine_name}' no está disponible.")
        print("  dlib:       pip install face-recognition")
        print("  insightface: pip install insightface onnxruntime")
        sys.exit(1)

    return engine


def _process_record(record, engine, dry_run: bool, db, label: str) -> str:
    """
    Procesa un registro (Resident o Visitor).
    Retorna "ok", "no_photo", "no_face", "error:<msg>"
    """
    if not record.foto_path:
        return "no_photo"

    photo = Path(record.foto_path)
    if not photo.exists():
        return f"no_file:{record.foto_path}"

    try:
        image_bytes = photo.read_bytes()
        result = engine.encode_face(image_bytes)

        if not result.detected or result.embedding is None:
            return "no_face"

        if not dry_run:
            record.face_encoding = json.dumps(result.embedding)
            record.embedding_model = result.model_name
            record.embedding_version = None
            record.embedding_created_at = datetime.datetime.utcnow()
            db.commit()

        return "ok"

    except Exception as exc:
        return f"error:{exc}"


def main():
    parser = argparse.ArgumentParser(
        description="Regenera embeddings faciales con el motor especificado"
    )
    parser.add_argument(
        "--engine", required=True, choices=["dlib", "insightface"],
        help="Motor a usar para regenerar embeddings",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simula sin escribir en la BD",
    )
    parser.add_argument(
        "--only", choices=["residents", "visitors"],
        help="Procesar solo residentes o solo visitantes (default: ambos)",
    )
    args = parser.parse_args()

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Reindexando con motor: {args.engine}")
    print("=" * 60)

    engine = _build_engine(args.engine)

    from backend.app.database import SessionLocal
    from backend.app.models import Resident, Visitor
    db = SessionLocal()

    stats = {"ok": 0, "no_photo": 0, "no_face": 0, "error": 0, "no_file": 0}

    try:
        # ── Residentes ──────────────────────────────────────────────────────
        if args.only in (None, "residents"):
            residents = db.query(Resident).filter(Resident.activo == True).all()
            print(f"\nResidentes activos: {len(residents)}")
            for r in residents:
                status = _process_record(r, engine, args.dry_run, db, "R")
                cat = status.split(":")[0]
                stats[cat] = stats.get(cat, 0) + 1
                icon = "✓" if status == "ok" else "⚠" if status in ("no_photo", "no_face") else "✗"
                print(f"  {icon} [{r.id:4d}] {r.nombre:<30} {r.apartamento:<10} → {status}")

        # ── Visitantes ──────────────────────────────────────────────────────
        if args.only in (None, "visitors"):
            visitors = db.query(Visitor).all()
            print(f"\nVisitantes: {len(visitors)}")
            for v in visitors:
                status = _process_record(v, engine, args.dry_run, db, "V")
                cat = status.split(":")[0]
                stats[cat] = stats.get(cat, 0) + 1
                icon = "✓" if status == "ok" else "⚠" if status in ("no_photo", "no_face") else "✗"
                print(f"  {icon} [{v.id:4d}] {v.nombre:<30} {'':10} → {status}")

    finally:
        db.close()

    # ── Resumen ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESUMEN")
    print(f"  ✓ Reindexados:         {stats.get('ok', 0)}")
    print(f"  ⚠ Sin foto registrada: {stats.get('no_photo', 0)}")
    print(f"  ⚠ Sin rostro en foto:  {stats.get('no_face', 0)}")
    print(f"  ✗ Archivo no encontrado: {stats.get('no_file', 0)}")
    print(f"  ✗ Errores:             {stats.get('error', 0)}")

    if args.dry_run:
        print("\n[DRY RUN] No se escribió ningún dato en la BD.")
    elif stats.get("ok", 0) > 0:
        print(f"\nEmbeddings actualizados con motor '{args.engine}'.")
        print("Reinicia el servidor para que los cambios tomen efecto.")


if __name__ == "__main__":
    main()

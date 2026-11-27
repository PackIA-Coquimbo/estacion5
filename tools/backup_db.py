"""Crea un respaldo consistente de la base SQLite usando la API de backup."""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.db import DATABASE_PATH, engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destino",
        type=Path,
        default=Path("backups"),
        help="directorio de respaldo (por defecto ./backups)",
    )
    args = parser.parse_args(argv)

    if engine.dialect.name != "sqlite":
        parser.error("los respaldos de este comando requieren SQLite")
    if not DATABASE_PATH.is_file():
        parser.error(f"no existe la base SQLite: {DATABASE_PATH}")

    args.destino.mkdir(parents=True, exist_ok=True)
    sufijo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destino = args.destino / f"e5-{sufijo}.sqlite3"
    origen_db = sqlite3.connect(str(DATABASE_PATH), timeout=5)
    destino_db = sqlite3.connect(str(destino), timeout=5)
    completado = False
    try:
        origen_db.backup(destino_db)
        resultado = destino_db.execute("PRAGMA integrity_check").fetchone()
        if resultado is None or resultado[0] != "ok":
            raise RuntimeError(f"El respaldo no pasó integrity_check: {resultado}")
        completado = True
    finally:
        destino_db.close()
        origen_db.close()
        if not completado:
            destino.unlink(missing_ok=True)
    print(f"Respaldo verificado: {destino}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, sqlite3.Error, RuntimeError) as error:
        print(f"No se pudo respaldar la base E5: {error}", file=sys.stderr)
        raise

"""Entrena el pronóstico horario de E5 usando su historial SQLite real."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.db import DATABASE_PATH, SessionLocal, engine
from app.models import Fruta
from app.prediccion import entrenar_pronostico


def cargar_horas():
    if engine.dialect.name != "sqlite":
        raise RuntimeError("El entrenamiento requiere la base SQLite de E5")
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"No existe la base SQLite de E5: {DATABASE_PATH}")

    with SessionLocal() as session:
        lecturas = session.execute(
            select(Fruta.salida, Fruta.e4_categoria_final)
            .where(
                Fruta.salida.is_not(None),
                Fruta.e4_categoria_final.is_not(None),
            )
            .order_by(Fruta.salida)
        ).all()

    if not lecturas:
        raise ValueError("La base no contiene mandarinas clasificadas por E4")

    agregados = {}
    for salida, categoria in lecturas:
        hora = salida.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        fila = agregados.setdefault(
            hora, {"frutas_clasificadas": 0, "rechazadas": 0}
        )
        fila["frutas_clasificadas"] += 1
        fila["rechazadas"] += int(categoria == "rechazo")

    inicio = min(agregados)
    fin = max(agregados)
    horas = []
    while inicio <= fin:
        horas.append(
            agregados.get(
                inicio, {"frutas_clasificadas": 0, "rechazadas": 0}
            )
        )
        inicio += timedelta(hours=1)
    return horas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modelo",
        type=Path,
        default=DATABASE_PATH.parent / "modelo_metricas.json",
        help="archivo JSON de salida (por defecto junto a la base SQLite)",
    )
    args = parser.parse_args(argv)

    try:
        modelo = entrenar_pronostico(cargar_horas())
    except (FileNotFoundError, RuntimeError, ValueError, KeyError) as error:
        print(f"No se pudo entrenar el modelo de E5: {error}", file=sys.stderr)
        return 1

    args.modelo.parent.mkdir(parents=True, exist_ok=True)
    temporal = args.modelo.with_suffix(args.modelo.suffix + ".tmp")
    temporal.write_text(
        json.dumps(modelo, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporal.replace(args.modelo)
    print(
        json.dumps(
            {
                "modelo": str(args.modelo),
                "horas_entrenamiento": modelo["horas_entrenamiento"],
                "horas_evaluacion": modelo["horas_evaluacion"],
                "metricas": modelo["metricas"],
                "pronostico_siguiente_hora": modelo["pronostico_siguiente_hora"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

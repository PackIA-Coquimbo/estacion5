"""Configuración común de pytest para la API de la Estación 5.

Los tests usan una base SQLite en memoria, nueva y vacía en cada test; nunca
tocan el archivo real ./e5.db:

- `get_db` se reemplaza con `app.dependency_overrides`.
- El lifespan de app/main.py usa `crear_tablas` y `SessionLocal` del engine
  real, que `dependency_overrides` no alcanza; se reemplazan con monkeypatch.
- El monitor de señales (`_monitor_senales`) se desactiva: correría en otro
  hilo sobre la misma conexión en memoria. Su lógica se prueba como función
  pura en tests/test_reglas.py (`evaluar_sin_senal`).
"""

import json
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CONTRATOS = RAIZ / "docs" / "formato_datos"
ESTACIONES = ["E1", "E2", "E3", "E4", "E6"]

# Red de seguridad: aunque algo escape a los reemplazos de abajo, el engine
# de app/db.py apunta a memoria y no a ./e5.db. Debe ir antes de importar app.
os.environ["DATABASE_URL"] = "sqlite://"

# Permite importar app/ y tools/ desde los tests sin instalar el proyecto
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def leer_contrato(estacion: str) -> dict:
    """Carga el JSON de ejemplo de una estación desde docs/formato_datos."""
    with open(CONTRATOS / f"{estacion}.json", encoding="utf-8") as archivo:
        return json.load(archivo)


@pytest.fixture
def contratos() -> dict[str, dict]:
    """Todos los contratos de ejemplo, por estación: {"E1": {...}, ...}."""
    return {estacion: leer_contrato(estacion) for estacion in ESTACIONES}


@pytest.fixture
def engine_prueba():
    """Engine SQLite en memoria, con las tablas de app/models.py creadas.

    StaticPool hace que todas las sesiones compartan la misma conexión; sin
    eso cada conexión vería una base en memoria distinta y vacía.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import StaticPool

    from app import models  # noqa: F401  registra los modelos en Base
    from app.db import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _activar_claves_foraneas(connection, _record):
        # Igual que en app/db.py; WAL no aplica a una base en memoria
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db(engine_prueba):
    """Fábrica de sesiones sobre la base de prueba: `with db() as sesion: ...`."""
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine_prueba, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(engine_prueba, db, monkeypatch):
    """Cliente HTTP de prueba contra la app FastAPI, con la base en memoria."""
    from fastapi.testclient import TestClient

    import app.main as main
    from app.db import Base, get_db

    def get_db_prueba():
        with db() as sesion:
            yield sesion

    async def monitor_desactivado():
        return None

    monkeypatch.setattr(
        main, "crear_tablas", lambda: Base.metadata.create_all(bind=engine_prueba)
    )
    monkeypatch.setattr(main, "SessionLocal", db)
    monkeypatch.setattr(main, "_monitor_senales", monitor_desactivado)
    main.app.dependency_overrides[get_db] = get_db_prueba

    try:
        with TestClient(main.app) as cliente:
            yield cliente
    finally:
        main.app.dependency_overrides.clear()

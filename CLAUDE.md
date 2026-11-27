# CLAUDE.md — Estación 5 PackIA (Supervisión y Trazabilidad)

## Reglas de trabajo (prioridad máxima)

1. **No hacer cambios sin autorización explícita.** Analizar, proponer y explicar es libre; crear, editar, borrar archivos, instalar dependencias o ejecutar comandos que modifiquen algo requiere que el usuario lo apruebe antes. Si hay duda, preguntar.
2. **Commits sin co-autor de Claude.** Nunca agregar `Co-Authored-By` ni líneas de atribución a Claude en commits ni en descripciones de PR.
3. **No hacer commit, push ni abrir PR sin que se pida.** Proponer el mensaje y esperar la orden.
4. **Nunca trabajar directo en `main`.** Una rama por tarea (`feat/a-...`, `feat/b-...`, `feat/c-...`, `docs/...`, `fix/...`).
5. Idioma: español en documentación, mensajes de commit y respuestas. Commits cortos, en minúsculas, entendibles y sin descripción larga.

## Documentación que hay que conocer antes de actuar

Leer lo que corresponda a la tarea:

| Archivo | Contenido |
|---|---|
| `README.md` | Estado, endpoints y ejecución local (parte puede estar desactualizada) |
| `docs/plan/plan-avance-e5.md` | **Plan general**: decisiones, contratos v2, modelo de BD, API objetivo, reglas de anomalías, plan por semana, despliegue en Raspberry Pi 5 |
| `docs/plan/rol-a-backend.md` | Plan individual de Gabriel (backend y datos) |
| `docs/plan/rol-b-integracion.md` | Plan individual de Maicol (integración y calidad) |
| `docs/plan/rol-c-dashboard.md` | Plan individual de Christian (dashboard) |
| `docs/plan/plan-conexiones.md` | Plan de la red de la línea: router, IP fijas, Pi con la API y conexión de cada estación |
| `docs/plan/conexion-estaciones.md` | Cómo se comunican las estaciones con E5 y por qué medio (maqueta en `conexion-estaciones.html`) |
| `docs/trelo/semana2.md` | Bitácora de la semana 2 |
| `docs/formato_datos/*.json` | Contratos de datos v3 por estación (una mandarina por mensaje) |
| `docs/formato_datos/README.md` | Guía de los contratos v3, preguntas abiertas con otras estaciones y respuestas por defecto |
| `docs/integracion/feat-b-integracion.md` | Rama de integración: tests, simulador y Docker para desarrollo y Pi |
| `docs/avance/registro-dashboard.md` | Registro de avance del dashboard (rol C) y decisiones abiertas del frontend |
| `docs/avance/registro-conexiones.md` | Registro de la jornada de conexiones: qué se hizo en cada fase de la red y configuración real |
| `docs/avance/pendientes.md` | **Lo que queda por hacer**, por rol, con evidencia; se marca al resolver |

Si el código y la documentación se contradicen, avisar al usuario antes de decidir cuál manda.

## Equipo

| Rol | Persona | Área |
|---|---|---|
| A — Backend y datos | Gabriel | `app/` |
| B — Integración y calidad | Maicol | contratos, `tests/`, `tools/`, Docker |
| C — Dashboard | Christian | `frontend/` |

El usuario de esta sesión es normalmente **Christian (rol C)**; confirmar si no queda claro. No tocar el área de otro rol sin avisar.

## Decisiones confirmadas

- Transporte con **cinta transportadora** (no carrito); E6 informa `estado_cinta`.
- La cinta lleva **una mandarina a la vez** (desde el 25 de noviembre; antes eran grupos de frutas). Cada estación informa por mandarina con `id_fruta`; ya no existe `id_grupo`.
- **E3** informa `diametro_mm` y `tamano` (`pequeno | mediano | grande`), con rangos de mandarina propuestos (bajo 60 mm pequeño, 60–70 mediano, sobre 70 grande; por confirmar con E3). E5 guarda lo que llega y no recalcula el tamaño.
- Equipo de E5: **Raspberry Pi 5** (ARM64, OS de 64 bits) con monitor en modo kiosko.
- Base de datos: **SQLite en modo WAL** (PostgreSQL solo como opción vía `DATABASE_URL`).
- Frontend sin framework (HTML/CSS/JS), servido por la misma API; *polling* y luego SSE si hay tiempo.

**Contratos:** los JSON de `docs/formato_datos/` son la fuente de verdad. Un cambio de campos se actualiza primero en el contrato y se avisa al equipo; después `schemas.py`, la BD y el frontend.

## Stack

Python 3.11, FastAPI, Uvicorn, Pydantic v2, Docker/Compose, pytest. Frontend en HTML, CSS y JavaScript.
Planificado (aún no está en `requirements.txt`): SQLAlchemy 2.0 con SQLite.

## Estado del código (verificar antes de asumir)

- `app/main.py`: endpoints `POST /api/v1/ingest/e1|e2|e3|e4|e6` que validan pero **no guardan**.
- `docs/formato_datos/`: en **v3** (una mandarina por mensaje, sin `id_grupo`).
- `app/schemas.py`, la BD, `tools/simulador.py` y `tests/`: todavía en **v2** (por grupo); falta migrarlos a v3 (ver `docs/avance/pendientes.md`). Mientras tanto la API responde 422 a los mensajes v3.
- `app/script.sql`: esquema v1, no coincide con los schemas.
- `tests/`: `test_contratos.py` valida los JSON v2 y el simulador; `test_ingesta.py` se salta solo mientras `schemas.py` siga en v1 (hoy: 27 pasan, 46 se saltan).
- `tools/simulador.py`: imita a E1–E4 y E6 enviando mensajes v2 a la API.
- Docker: `docker-compose.yml` es la configuración base (Pi, sin `--reload`, volumen para la BD) y `docker-compose.override.yml` agrega el modo desarrollo.
- `frontend/`: el dashboard es `index.html` (horizontal y vertical), con `app.js` (pantalla y animación de la cinta), `sim.js` (datos simulados y reglas) y la tipografía en `fonts/`. Usa datos simulados. `api.js` es la capa de datos (modos `?api=`, `?mock=1`, `?sim=1`) con ejemplos en `mock/`, pero la pantalla aún no la usa. Los prototipos anteriores se eliminaron; están en el historial de git.

## Cómo ejecutar

```bash
docker compose up --build        # desarrollo: API en http://localhost:8000 (docs en /docs)
docker compose -f docker-compose.yml up -d --build   # Raspberry Pi: solo la configuración base
# o, sin Docker:
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Tests y simulador (Python 3.11):

```bash
pip install -r requirements-dev.txt
pytest -q
python tools/simulador.py --dry-run --frutas 2      # ver los JSON sin enviarlos
python tools/simulador.py --frutas 20 --velocidad 2 # enviar a http://localhost:8000
python tools/simulador.py --rangos 92,112           # cortes de tamaño que usa el dashboard simulado
```

## Al proponer o hacer cambios

- Explicar qué se va a cambiar y en qué archivos **antes** de hacerlo, y esperar el visto bueno.
- Cambios pequeños y enfocados en la tarea; sin refactors ni mejoras no pedidas.
- Mantener sincronizados contrato, `schemas.py`, BD y frontend.
- Reportar con honestidad lo que se probó y lo que no (por ejemplo, nada se ha probado aún en la Raspberry Pi).

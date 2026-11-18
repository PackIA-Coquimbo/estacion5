# Estación 5 — Backend PackIA

API FastAPI de supervisión y trazabilidad para PackIA. Recibe mensajes v2 de E1, E2, E3, E4 y E6, los conserva en una base de datos y consolida la trazabilidad por lote, grupo y fruta.

## Estado

- Validación de los contratos v2 de [`docs/formato_datos/`](docs/formato_datos/).
- Persistencia de lecturas originales y actualización (*upsert*) de frutas.
- SQLite en modo WAL por defecto; PostgreSQL se configura mediante `DATABASE_URL`.
- Consultas de lotes, grupos, trazabilidad y métricas.
- Reglas de anomalías, alertas y estado de las estaciones.
- Dashboard estático disponible en `/`. Actualmente conserva su simulación propia.

Los contratos JSON son la fuente de verdad. Los mensajes de E1–E4 se asocian a un `id_grupo`; E2–E4 incluyen una lista de frutas. E6 informa el estado de la cinta y no requiere `id_grupo`. Todos los mensajes requieren un `timestamp` ISO 8601 con zona horaria.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Dashboard estático |
| GET | `/docs` | Documentación interactiva de la API |
| POST | `/api/v1/ingest/e1` … `/e4`, `/e6` | Validar y guardar lecturas |
| GET | `/api/v1/lotes` | Lotes y cantidad de grupos |
| GET | `/api/v1/lotes/{id_lote}/grupos?limit=20` | Grupos recientes de un lote; límite de 1 a 100 |
| GET | `/api/v1/grupos/{id_grupo}` | Datos consolidados de frutas y lecturas del grupo |
| GET | `/api/v1/metricas?lote={id_lote}` | Métricas generales o filtradas por lote |
| GET | `/api/v1/alertas?activas=true` | Alertas activas; `activas=false` incluye las resueltas |
| PATCH | `/api/v1/alertas/{id_alerta}` | Marcar una alerta como resuelta |
| GET | `/api/v1/estaciones/estado` | Última lectura y estado online/sin señal por estación |
| GET | `/api/v1/sistema` | Temperatura, CPU y RAM del equipo |

La ingesta responde `201` cuando el mensaje se guardó o era un duplicado exacto, `422` si no cumple el contrato y `409` si un `id_grupo` existente se intenta asociar a otro lote.

`GET /api/v1/metricas` entrega `frutas_por_hora`, `porcentaje_rechazo`, `conteo_por_categoria`, `conteo_por_tamano` y `anomalias_por_estacion`. Las frutas por hora se agrupan según la primera lectura E4 de cada fruta; el porcentaje de rechazo considera las frutas con categoría E4 registrada.

## Persistencia y configuración

La aplicación crea las tablas al iniciar. SQLAlchemy conserva cada lectura recibida y evita duplicar el mismo payload. La tabla de frutas tiene clave única `(id_grupo, id_fruta)` y actualiza los campos de E2, E3 o E4 sin borrar los datos de las otras estaciones.

Sin configuración adicional, la base es `sqlite:///./e5.db` en modo WAL. En Docker Compose, el valor predeterminado es `sqlite:////app/data/e5.db` y se conserva en el volumen `e5_datos`. Para usar PostgreSQL, configura `DATABASE_URL`, por ejemplo:

```text
postgresql+psycopg://usuario:clave@servidor:5432/estacion5
```

Umbrales de alertas:

- Confianza mínima E2: `0.70`.
- Tendencia E2: 3 o más confianzas bajas entre las últimas 12 frutas.
- Diferencia máxima de diámetro por grupo: `15` mm.
- Tiempo sin señal con la cinta en marcha: `30` s.

Los umbrales se definen en `app/config.py`.

La temperatura del sistema se devuelve como `null` cuando el equipo no expone sensores compatibles. CORS permite cualquier origen para facilitar la integración en la red local; no se ha agregado autenticación.

## Ejecución

### Desarrollo con Docker Compose

```bash
docker compose up --build
```

Compose incluye automáticamente `docker-compose.override.yml` para recarga en caliente. La API queda disponible en `http://localhost:8000/` y `http://localhost:8000/docs`.

### Ejecución directa

Requiere Python 3.11:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Raspberry Pi 5

Usa solo el Compose base, sin el modo de recarga de desarrollo:

```bash
docker compose -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml ps
```

El servicio usa el volumen `e5_datos` y `restart: unless-stopped`. El despliegue aún debe validarse en una Raspberry Pi real.

## Pruebas

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
```

`tests/test_contratos.py` valida los contratos y el simulador; `tests/test_ingesta.py` verifica respuestas `201` y `422` para los mensajes válidos e inválidos.

## Simulador

`tools/simulador.py` envía grupos coherentes de 2 a 5 frutas por E1–E4 y el estado de cinta por E6:

```bash
python tools/simulador.py --dry-run --grupos 2
python tools/simulador.py --grupos 20 --velocidad 2
python tools/simulador.py --rangos 92,112
```

`--duplicados` reenvía cada mensaje para verificar idempotencia; `--falla-cinta` y `--baja-confianza` permiten probar las alertas. Consulta `python tools/simulador.py --help` para todas las opciones.

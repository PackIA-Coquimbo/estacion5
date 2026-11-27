# Estación 5 — Supervisión y Trazabilidad

API FastAPI para recibir las lecturas de E1, E2, E3, E4 y E6, consolidar la
trazabilidad **por mandarina** y entregar consultas al dashboard y a las demás
estaciones. Los contratos activos son v3: un JSON por mandarina y estación,
sin `id_grupo` ni arreglos `frutas[]`. Los contratos JSON de
[`docs/formato_datos/`](docs/formato_datos/README.md) son la fuente de verdad.

## Estado del desarrollo

- Schemas y persistencia SQLite actualizados a v3; cada mandarina tiene un
  `id_fruta` único y conserva los datos recibidos por E1–E4.
- Cada POST se guarda como lectura cruda; los reintentos idénticos son
  idempotentes.
- Consultas de lotes, mandarinas, métricas, alertas, cinta y estado de las
  estaciones.
- Guía de envío, consulta y diferencias pendientes en las otras estaciones:
  [`docs/integracion/guia-api-e5.md`](docs/integracion/guia-api-e5.md).
- Pronóstico de frutas/hora y porcentaje de rechazo preparado con evaluación
  temporal. **No se ha entrenado un modelo de producción**: el repositorio no
  tiene historial real de E5. El entrenamiento fallará explícitamente hasta
  tener al menos 24 horas históricas clasificadas.
- SQLite en modo WAL, volumen persistente de Docker, checkpoints y respaldo
  consistente por comando. No hay purga automática de lecturas.

Los repositorios de E1–E6 aún no están completamente alineados con v3. La guía
indica los cambios necesarios; no se modificaron esos repositorios en esta rama.

## API v3

| Método | Ruta | Uso |
|---|---|---|
| GET | `/` | Dashboard estático |
| GET | `/docs` | Especificación interactiva OpenAPI |
| POST | `/api/v1/ingest/e1`, `/e2`, `/e3`, `/e4`, `/e6` | Ingresar una lectura |
| GET | `/api/v1/lotes` | Lotes y cantidad de mandarinas |
| GET | `/api/v1/lotes/{id_lote}/frutas?limit=20` | Mandarinas recientes (1–100) |
| GET | `/api/v1/frutas/{id_fruta}` | Trazabilidad E1–E4, salida y alertas |
| GET | `/api/v1/metricas?lote={id_lote}` | Métricas generales o filtradas por lote |
| GET | `/api/v1/alertas?activas=true` | Alertas activas; `false` incluye resueltas |
| PATCH | `/api/v1/alertas/{id_alerta}` | Resolver una alerta |
| GET | `/api/v1/estaciones/estado` | Señal de estaciones y estado de E6 |
| GET | `/api/v1/sistema` | CPU, RAM, temperatura y espacio del disco |
| GET | `/api/v1/predicciones` | Evaluación y pronóstico entrenado; `503` si no existe modelo |

Una ingesta válida responde `201` e incluye `lectura_id` y `duplicado`. Si se
reenvía exactamente el mismo payload, responde `201` con `duplicado: true`.
Mensajes inválidos reciben `422`; un `id_fruta` asociado a otro lote recibe
`409`. Reintentar el mismo JSON sin cambiar su timestamp permite deduplicarlo.

## Contratos de las estaciones

Todos los mensajes requieren `id_lote`, `timestamp` ISO 8601 con zona horaria y
`estacion` correspondiente a la ruta. E1–E4 incluyen `id_fruta` y un objeto
`datos`; E6 informa `estado_cinta` y opcionalmente `id_fruta_en_cinta`.

Ejemplo E3:

```json
{
  "id_lote": "LOTE-2026-11-A",
  "id_fruta": "M-0001",
  "estacion": "E3",
  "timestamp": "2026-11-25T10:15:41Z",
  "datos": {
    "diametro_mm": 64,
    "tamano": "mediano"
  }
}
```

E5 guarda `tamano` como lo informa E3; no vuelve a clasificar el diámetro. Los
cortes 60/70 mm siguen pendientes de confirmación entre E3 y E5. Ver ejemplos
completos y el mapeo de los repositorios actuales en la
[guía de integración](docs/integracion/guia-api-e5.md).

## Base de datos y Raspberry Pi

La aplicación crea tablas al iniciar. SQLite es el valor por defecto y utiliza
WAL, claves foráneas, `synchronous=NORMAL`, espera de bloqueo de 5 s y
autocheckpoint WAL. Compose persiste `e5.db` en el volumen `e5_datos`; PostgreSQL
sigue disponible configurando `DATABASE_URL`.

Para una Pi de 32 GB:

- El endpoint `/api/v1/sistema` informa uso total del volumen y
  `almacenamiento_alerta` se activa al llegar a 80 %.
- No borrar lecturas automáticamente: `lectura` conserva el payload crudo.
- Respaldar regularmente a un disco/servidor distinto de la tarjeta o volumen
  de la Pi y verificar los respaldos:

```powershell
python tools/backup_db.py --destino D:\respaldos\e5
```

El comando usa la API de respaldo de SQLite y comprueba `integrity_check`; no
copia manualmente el archivo WAL. Configura una tarea programada y una política
de rotación **en el destino externo** según el espacio disponible. En la Pi,
monta el disco externo, configura `BACKUP_DIR=/mnt/e5-respaldo` en `.env` y
ejecuta:

```bash
docker compose -f docker-compose.yml exec backend \
  python tools/backup_db.py --destino /backups
```

> **Base v2 existente:** `create_all` no transforma tablas antiguas. Antes de
> desplegar sobre una base v2, respáldala y planifica una migración/exportación;
> no reutilices una base de producción antigua directamente con los modelos v3.

## Acceso de red

La API no tiene autenticación. No publicar el puerto a Internet ni configurar
port-forwarding en el router. En la Pi, enlazar el puerto Docker solo a la
interfaz LAN y limitarlo con el firewall a la subred de las estaciones. CORS
solo se aplica a navegadores; no autentica clientes HTTP.

En `.env`, `API_BIND_ADDRESS` debe ser `192.168.0.10` para que las otras
estaciones accedan a la Pi; el valor de desarrollo de ejemplo es `127.0.0.1`.
`CORS_ORIGINS` se puede ajustar para los orígenes web autorizados.

## Ejecución

### Desarrollo

```powershell
Copy-Item .env.example .env
# Dejar API_BIND_ADDRESS=127.0.0.1 para desarrollo local
docker compose up --build
```

La API queda en `http://localhost:8000` y `http://localhost:8000/docs`. Compose
aplica `docker-compose.override.yml` para recarga en caliente.

### Raspberry Pi

Editar `.env` y fijar `API_BIND_ADDRESS=192.168.0.10`, luego iniciar solo el
Compose base, sin recarga:

```bash
docker compose -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml ps
```

No se ha validado este despliegue en hardware real.

### Sin Docker

Requiere Python 3.11:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Pruebas y simulador

```powershell
pip install -r requirements-dev.txt
pytest -q
python tools/simulador.py --dry-run --frutas 2
python tools/simulador.py --frutas 20 --velocidad 2
python tools/simulador.py --rangos 60,70 --baja-confianza
```

El simulador genera una mandarina por mensaje. `--duplicados` comprueba
idempotencia; `--falla-cinta` genera eventos E6; `--sin-e3` simula la falta de
señal de E3.

## Entrenar el pronóstico de E5

El modelo es una regresión lineal autorregresiva AR(1) pequeña, sin dependencias
de ML adicionales. Usa conteos horarios reales de frutas clasificadas y
porcentaje de rechazo. Entrena con la primera parte de la serie y reporta MAE,
RMSE y R² sobre el tramo cronológico final; requiere al menos 24 horas con datos
de E4.

```bash
docker compose -f docker-compose.yml exec backend \
  python tools/entrenar_modelo.py
```

El archivo `modelo_metricas.json` se guarda junto a la base SQLite y no debe
subirse al repositorio. Antes de reunir suficientes datos, el comando informa
el motivo y `/api/v1/predicciones` responde `503`. Las métricas se reportan solo
después de entrenar y no deben interpretarse como resultados reales mientras
no haya historial de producción.

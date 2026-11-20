# Pendientes del equipo — Estación 5

**Corte:** miércoles 18 de noviembre de 2026, al cierre de la jornada de conexiones · **Base revisada:** `main` en `76f8083` (después de los PR #12 y #13)

> Lista de lo que queda por hacer, por rol, con la evidencia de cada punto. Al resolver uno, márcalo `[x]` y anota el PR. Los planes completos están en `docs/plan/`.

---

## 1. Estado en 30 segundos

| Área | Estado |
|---|---|
| Backend (A, Gabriel) | Contratos v2, persistencia, consultas, alertas y estado de estaciones **hechos** (PR #13). Los **73 tests pasan**. Quedan 3 errores (sección 2). |
| Integración (B, Maicol) | Simulador, tests y Docker hechos desde el 13 de noviembre. Sin avances nuevos; quedan la coordinación con otras estaciones y la prueba en la Pi. |
| Dashboard (C, Christian) | Pantalla terminada con datos simulados y servida por la API en `/` (PR #11 y #12). **Falta conectarla a la API**: las respuestas no tienen la forma que espera `api.js` (sección 4). |
| Red de la línea | Fase 1 (router) lista. Fase 2 (Pi) **sin empezar**. Ver `docs/avance/registro-conexiones.md`. |

## 2. Gabriel (A) — Backend

Encontrado al levantar la API con Python 3.11 y alimentarla con `tools/simulador.py` (8 grupos, todos los mensajes respondieron `201`).

- [ ] **Los grupos nunca se cierran.** Todo grupo queda con `estado = "en_proceso"` y `salida = null`, aunque haya pasado por E4: el modelo los crea así (`app/models.py`, campos `estado` y `salida`) y ninguna parte de `app/main.py` los cambia. Sin esto no funcionan el historial ni los estados Aprobado / Con anomalía / Con rechazo. **Prioridad alta.**
- [ ] **El estado de la cinta (E6) no se puede consultar.** Se guarda en `EventoCinta`, pero ninguna ruta `GET` lo devuelve. `GET /api/v1/estaciones/estado` solo trae `estacion`, `estado`, `ultima_lectura` y `segundos_desde_lectura`. El aviso de "cinta detenida" del dashboard lo necesita. **Prioridad alta.**
- [ ] **Detalle por fruta en la lista de grupos.** `GET /api/v1/lotes/{id}/grupos` no trae las frutas (categoría, tamaño, diámetro), el diámetro medio ni la uniformidad, que usa la tabla "Últimos grupos". **Prioridad alta.**
- [x] **Los tests escriben en el archivo real `./e5.db`** en vez de una base de datos en memoria, como pedía el plan. Revisar `tests/conftest.py` (también es área de Maicol). → Resuelto por Maicol en `tests/conftest.py` (rama `feat/b-test-persistencia`, PR pendiente).
- [ ] Datos menores que espera el dashboard: grupos del turno y de la última hora en `/metricas`; grupo actual y severidad de la última lectura por estación; alertas de un grupo en `/grupos/{id}`.
- [ ] Descripción del PR #13 (está vacía): qué se hizo y cómo probarlo.
- [ ] Opcional (se recorta primero): `GET /api/v1/stream` con SSE.

## 3. Maicol (B) — Integración

- [ ] Enviar los contratos v2 a E1–E4 y E6 y cerrar las preguntas abiertas (`docs/formato_datos/README.md`): quién asigna `id_grupo` e `id_fruta`, **rangos de diámetro de E3**, lista de defectos de E2 y frecuencia de E6.
- [x] Tests de comportamiento ahora que existe la persistencia: duplicados sin filas nuevas, mensajes en desorden, consultas y reglas. → `tests/test_persistencia.py`, `tests/test_consultas.py`, `tests/test_reglas.py` (rama `feat/b-test-persistencia`, PR pendiente).
- [x] Usar una base de datos en memoria en `tests/conftest.py` (ver sección 2). → SQLite en memoria con `StaticPool`, `get_db` sobrescrito y lifespan sin el engine real (rama `feat/b-test-persistencia`, PR pendiente).
- [ ] Probar `docker compose -f docker-compose.yml up -d --build` **en la Pi** (fase 2 de conexiones).
- [ ] Bitácora `docs/trelo/semana3.md`.
- [ ] Primera prueba real con E4 y E6 → `docs/integracion/semana5.md`.

## 4. Christian (C) — Dashboard

- [ ] **Conectar la pantalla a la API** en una rama `feat/c-conectar-api`: adaptar `api.js` a las respuestas reales y que `app.js` lea de ahí, dejando `sim.js` como plan B (`?sim=1`).

Comparación de las respuestas reales con `frontend/mock/` (lo que espera el dashboard):

| Ruta | Se resuelve en `api.js` | Falta en la API (sección 2) |
|---|---|---|
| `GET /alertas` | Viene como lista en vez de `{alertas:[…]}`; `creado_en` en vez de `creada_en`. | — |
| `GET /metricas` | `conteo_por_categoria` → `por_categoria`; rechazadas y frutas de la última hora se calculan. | Grupos del turno y de la última hora. |
| `GET /estaciones/estado` | Lista en vez de `{estaciones:[…]}`; `online` → `ok`. | Estado de la cinta de E6, grupo actual, severidad. |
| `GET /grupos/{id}` | Estructura distinta (`grupo{}`, frutas planas, `lecturas[]`), pero trae toda la información. | Alertas del grupo. |
| `GET /lotes/{id}/grupos` | Lista en vez de `{grupos:[…]}`. | Frutas, diámetro medio y uniformidad; grupos cerrados. |

- [ ] Mientras falten esos datos, mostrar esa parte con datos simulados o como "sin datos", sin romper la pantalla.
- [ ] Panel de la Pi con `GET /api/v1/sistema` (ya existe; en equipos sin sensor la temperatura viene `null`).
- [ ] Script de kiosko con arranque automático y prueba en el monitor real (fase 7 de conexiones).
- [ ] Opcional: las frutas tapan la etiqueta "E1"…"E4" de la cinta cuando el grupo está detenido en una estación.

## 5. Red de la línea (todos)

Detalle en `docs/avance/registro-conexiones.md` y pasos en `docs/plan/plan-conexiones.md`.

- [x] Fase 1 — Router configurado y respaldado.
- [ ] **Fase 2 — Pi con la API** (sin empezar): grabar Raspberry Pi OS en un pendrive, arrancar, SSH, reservar `192.168.0.10`, Docker, API y prueba de reinicio.
- [ ] Fase 3 — Prueba de red con el simulador.
- [ ] Fase 4 — Conectar las estaciones reales.
- [ ] Fase 5 — Switch · Fase 6 — Tubos PVC · Fase 7 — Ensayo general.

**Material que falta:** cables de red (hoy hay 1; se necesitan al menos 2 más ahora y uno por estación después), teclado USB y switch de 8 puertos.

**Corrección hecha:** `docs/plan/conexion-estaciones.md` ya usa `192.168.0.10` (antes `192.168.10.10`).

## 6. Decisiones abiertas del equipo

| Decisión | Quién |
|---|---|
| Rangos de tamaño de E3 (pequeño, mediano, grande). Hoy hay tres versiones distintas: dashboard 92/112 mm, simulador 35/45 mm, contrato "40 mm = mediano". Además, el backend usa 15 mm como diferencia máxima de diámetro dentro de un grupo. | Maicol con E3 |
| ¿El dashboard se adapta a la API tal como está, o la API cambia a la forma de `frontend/mock/`? Propuesta: el dashboard adapta los nombres en `api.js` y la API agrega solo los datos que faltan (sección 2). | Gabriel y Christian |
| Orientación del monitor en la demo (vertical u horizontal). | Todos |

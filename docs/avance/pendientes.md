# Pendientes del equipo — Estación 5

**Corte:** miércoles 18 de noviembre de 2026, al cierre de la jornada de conexiones · **Base revisada:** `main` en `76f8083` (después de los PR #12 y #13)

> Lista de lo que queda por hacer, por rol, con la evidencia de cada punto. Al resolver uno, márcalo `[x]` y anota el PR. Los planes completos están en `docs/plan/`.

## Actualización — 26 de noviembre de 2026

La rama `feat/e5-api-v3-integracion` migra schemas, modelos SQLite, rutas,
métricas, reglas, simulador y tests a los contratos v3 por mandarina. Las rutas
de grupos de las secciones históricas siguientes ya no son la API vigente. La
guía para adaptar E1–E6 está en
[`docs/integracion/guia-api-e5.md`](../integracion/guia-api-e5.md).

Pendiente después de esta rama: validar los cambios con los equipos de E1–E6,
desplegar y probar en Raspberry Pi; entrenar el pronóstico con al menos 24 horas
de historial real de E5. No se encontró una base SQLite v2 en este checkout y
no se incluye migración automática de bases existentes.

---

## 1. Estado en 30 segundos

| Área | Estado |
|---|---|
| Backend (A, Gabriel) | Migrado a **contratos v3** por mandarina (PR #21): schemas, modelos SQLite, rutas, métricas, reglas, simulador y tests; además pronóstico y respaldo SQLite. Falta validar con E1–E6 y probar en la Pi. |
| Integración (B, Maicol) | Simulador, tests y Docker hechos desde el 13 de noviembre. Sin avances nuevos; quedan la coordinación con otras estaciones y la prueba en la Pi. |
| Dashboard (C, Christian) | Pantalla terminada con datos simulados y servida por la API en `/` (PR #11 y #12). **Falta conectarla a la API**: las respuestas no tienen la forma que espera `api.js` (sección 4). |
| Red de la línea | Fase 1 (router) lista (rehecha el 25/11). Fase 2 (Pi) **en curso**: red y reserva de `192.168.0.10` listas; la microSD quedó dañada el 27/11 y falta una nueva para instalar el sistema, Docker y la API. Ver `docs/avance/registro-conexiones.md`. |

## 1b. Cambio a una mandarina por pasada (contratos v3) — 25 de noviembre

**Nuevo requerimiento:** la cinta lleva **una sola mandarina a la vez**. Se eliminó el grupo de frutas: los contratos pasaron a **v3** (`docs/formato_datos/`), con un mensaje por mandarina y por estación, `id_fruta` en vez de `id_grupo` y los resultados dentro de `datos`. El dashboard ya se adaptó (rama `feat/c-una-mandarina`). **Backend, simulador y tests siguen en v2**, así que la API responde 422 a los mensajes v3 y los tests que leen los JSON de ejemplo fallan hasta migrarlos.

**Gabriel (A):**
- [ ] `app/schemas.py`: `E1Payload`…`E4Payload` con `id_fruta` y `datos` (sin `id_grupo` ni `frutas[]`). E1 sin `frutas_detectadas`. E6 con `id_fruta_en_cinta`.
- [ ] `app/models.py`: unir `Grupo` y `Fruta` en una sola tabla `fruta` (clave `id_fruta`, con `id_lote`, campos de E1, estado, ingreso y salida). `Lectura` y `Alerta` con `id_fruta` en vez de `id_grupo`. Actualizar `app/script.sql`.
- [ ] `app/main.py`: cierre por mandarina al llegar E4; `GET /api/v1/lotes/{id}/frutas` y `GET /api/v1/frutas/{id}` en vez de las rutas de grupos; `/metricas` en mandarinas (del turno y de la última hora); estado de E6 con `id_fruta_en_cinta`.
- [ ] `app/reglas.py`: quitar la regla de "tamaños irregulares en el grupo" (15 mm). El mínimo de tamaño pasa a mandarina (sugerido: alerta bajo 55 mm).

**Maicol (B):**
- [ ] `tools/simulador.py`: una mandarina por pasada (`M-0001`, …), mensajes v3, diámetros de 50 a 80 mm y `--rangos 60,70` por defecto.
- [ ] `tests/`: migrar `test_contratos.py` (formato v3, ejemplo 64 mm → mediano) y los tests que usan grupos (`test_ingesta.py`, `test_persistencia.py`, `test_consultas.py`, `test_cierre_grupo.py`, `test_reglas.py`, `conftest.py`).
- [ ] Enviar el formato v3 a E1–E4 y E6 (mensaje listo en `docs/formato_datos/README.md`) y confirmar con E3 los rangos de 60 y 70 mm.

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
- [ ] **Fase 2 — Pi con la API** (en curso): cable, reserva de `192.168.0.10` y respaldo del router listos el 27/11. La microSD quedó dañada; con una nueva falta grabar el sistema, actualizar, Docker, API y prueba de reinicio.
- [ ] Fase 3 — Prueba de red con el simulador.
- [ ] Fase 4 — Conectar las estaciones reales.
- [ ] Fase 5 — Switch · Fase 6 — Tubos PVC · Fase 7 — Ensayo general.

**Material que falta:** **microSD nueva** (32 GB o más, de marca, A1/A2), cables de red (uno por estación) y switch de 8 puertos.

**Corrección hecha:** `docs/plan/conexion-estaciones.md` ya usa `192.168.0.10` (antes `192.168.10.10`).

## 6. Decisiones abiertas del equipo

| Decisión | Quién |
|---|---|
| Rangos de tamaño de E3 para mandarina. Propuesta v3 (contrato y dashboard): bajo 60 mm pequeño, 60–70 mediano, sobre 70 grande. Falta que E3 los confirme y que el simulador los adopte (hoy 35/45 mm). | Maicol con E3 |
| ¿El dashboard se adapta a la API tal como está, o la API cambia a la forma de `frontend/mock/`? Propuesta: el dashboard adapta los nombres en `api.js` y la API agrega solo los datos que faltan (sección 2). | Gabriel y Christian |
| Orientación del monitor en la demo (vertical u horizontal). | Todos |

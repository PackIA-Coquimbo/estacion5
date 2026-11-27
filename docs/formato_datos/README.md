# Contratos de datos v3 — Estación 5

Estos JSON son la **única fuente de verdad** de lo que cada estación envía a la API de E5. Si un campo cambia, se actualiza primero aquí, se avisa al equipo y recién después se cambian `app/schemas.py`, la base de datos y el frontend.

**Regla general:** la cinta lleva **una mandarina a la vez**. Cada estación envía **un mensaje por mandarina**, con sus resultados en `datos`. E6 informa el estado de la cinta y no depende de una mandarina.

> **Cambio v2 → v3 (25 de noviembre de 2026):** se elimina el grupo de frutas. Ya no existen `id_grupo` ni la lista `frutas[]`; cada mensaje trae un solo `id_fruta`. E1 deja de enviar `frutas_detectadas` y E6 informa `id_fruta_en_cinta`.
>
> **Estado (26 de noviembre de 2026):** la rama `feat/e5-api-v3-integracion` actualiza schemas, persistencia, endpoints y simulador a v3. Los equipos de E1–E6 aún deben adaptar sus emisores/consumidores; consulta [`docs/integracion/guia-api-e5.md`](../integracion/guia-api-e5.md). Los cortes 60/70 mm siguen pendientes de confirmación de E3.

## Endpoints

| Estación | Método y ruta | Ejemplo |
|---|---|---|
| E1 — Recepción y captura | `POST /api/v1/ingest/e1` | [E1.json](E1.json) |
| E2 — Calidad visual | `POST /api/v1/ingest/e2` | [E2.json](E2.json) |
| E3 — Diámetro y tamaño | `POST /api/v1/ingest/e3` | [E3.json](E3.json) |
| E4 — Decisión comercial | `POST /api/v1/ingest/e4` | [E4.json](E4.json) |
| E6 — Estado de la cinta | `POST /api/v1/ingest/e6` | [E6.json](E6.json) |

Respuesta esperada: **201** si el mensaje es válido y **422** si falta un campo, un valor está fuera de rango o `estacion` no coincide con la ruta.

## Campos comunes

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `id_lote` | texto | sí | Ejemplo: `LOTE-2026-11-A` |
| `id_fruta` | texto | sí (excepto E6) | E1 lo asigna y las demás estaciones lo reutilizan. Debe ser único entre lotes. Ejemplo: `M-0001` |
| `estacion` | `E1`, `E2`, `E3`, `E4` o `E6` | sí | Debe coincidir con la ruta |
| `timestamp` | fecha ISO 8601 **con zona horaria** | sí | La pone la estación al medir. Ejemplo: `2026-11-25T10:15:30Z` |
| `datos` | objeto | sí | Campos propios de cada estación (abajo) |

## Campos de `datos` por estación

### E1
| Campo | Tipo | Valores |
|---|---|---|
| `validez_imagen` | booleano | `true` / `false` |
| `estado_captura` | texto | `aceptada`, `repetir`, `revision` |
| `posicion_correcta` | booleano | `true` / `false` |

### E2
| Campo | Tipo | Valores |
|---|---|---|
| `calidad_visual` | texto | `alta`, `media`, `baja`, `defectos_visibles`, `revision` |
| `confianza_visual` | decimal | entre 0 y 1 |
| `defectos_detectados` | lista de texto | puede ir vacía; lista cerrada por confirmar con E2 |

### E3
| Campo | Tipo | Valores |
|---|---|---|
| `diametro_mm` | número | mayor que 0 |
| `tamano` | texto | `pequeno`, `mediano`, `grande` |

E3 calcula el tamaño. E5 guarda el diámetro y el tamaño tal como llegan y **no** recalcula nada.

Rangos propuestos para mandarina (por confirmar con E3): **pequeño** bajo 60 mm, **mediano** de 60 a 70 mm, **grande** sobre 70 mm. Ejemplo: 64 mm → mediano.

### E4
| Campo | Tipo | Valores |
|---|---|---|
| `categoria_final` | texto | `exportacion`, `mercado_nacional`, `proceso`, `rechazo`, `revision_manual` |
| `probabilidad` | decimal | entre 0 y 1 |
| `requiere_revision_manual` | booleano | `true` / `false` |

### E6
| Campo | Tipo | Valores |
|---|---|---|
| `estado_cinta` | texto | `normal`, `detenida`, `falla_mecanica` |
| `falla_mecanica_detectada` | booleano | `true` / `false` |
| `id_fruta_en_cinta` | texto | opcional |

## Preguntas abiertas con las otras estaciones

Si una estación no responde, se avanza con la **respuesta por defecto** y se avisa en el chat.

| Pregunta | Para | Respuesta por defecto |
|---|---|---|
| ¿Quién asigna `id_fruta`? | E1 y todas | E1 asigna `M-0001`, `M-0002`, …; las demás lo reutilizan |
| Rangos de diámetro para pequeño, mediano y grande | E3 | Bajo 60 mm pequeño, 60–70 mm mediano, sobre 70 mm grande |
| Lista cerrada de `defectos_detectados` | E2 | Texto libre en minúsculas con guion bajo (`mancha_leve`) |
| Frecuencia de envío del estado de la cinta | E6 | Cada vez que cambia, más un *heartbeat* cada 10 s |
| URL de la API de E5 | todas | `http://192.168.0.10:8000` (IP reservada en el router, ver `docs/plan/plan-conexiones.md`) |

## Mensaje para enviar a las otras estaciones

> Hola, somos E5 (Supervisión y Trazabilidad). Como la cinta ahora lleva **una mandarina a la vez**, cambiamos el formato de los mensajes a **v3**: un mensaje por mandarina y por estación, con `id_fruta` (sin `id_grupo` ni lista de frutas) y los resultados dentro de `datos`. Los ejemplos están en `docs/formato_datos/` del repo de E5. Necesitamos que nos confirmen: (1) si E1 asigna el `id_fruta` (`M-0001`, …), (2) los rangos de diámetro de E3 para mandarina (proponemos 60 y 70 mm), (3) la lista de defectos de E2 y (4) cada cuánto envía E6 su estado. Si no tenemos respuesta, avanzamos con los valores por defecto del documento.

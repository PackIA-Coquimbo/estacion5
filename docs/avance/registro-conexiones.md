# Registro de avance — Conexiones de la línea

**Jornada:** miércoles 18 de noviembre de 2026, en la universidad · **Plan que se sigue:** [`docs/plan/plan-conexiones.md`](../plan/plan-conexiones.md)
**Última actualización:** 2026-11-18, cierre de la jornada (hora de Chile)

> Registro de lo que se hizo en cada fase del plan de conexiones, lo que salió distinto a lo planeado y lo que falta. **Sin contraseñas.** Las claves se guardan en el grupo del equipo.

---

## 1. Resumen

- ✅ **Fase 1 (router): lista.** Router configurado desde cero, con internet desde la red de la U y respaldo guardado.
- ⏳ **Fase 2 (Pi + API): sin empezar.** Se revisó el material y se decidió cómo hacerla (sección 3), pero todavía no se graba el sistema ni se enciende la Pi.
- Fases 3 a 7: pendientes.

## 2. Fase 1 — Router

| Paso | Resultado |
|---|---|
| 1.2 Conexión física | Router y Pi a la corriente. Cable de red de la U al puerto **WAN**. |
| Estado inicial | El router **venía configurado de antes**: Wi-Fi con otro nombre y clave de administrador desconocida. |
| 1.9 Reset de fábrica | Hecho (botón Reset ~10 s). |
| 1.3 Primer ingreso | Clave de administrador nueva creada (guardada en el grupo del equipo). TP-Link ID omitido. |
| 1.4 Asistente | Zona horaria Santiago. Internet: **Dynamic IP**, sin clonar MAC. Smart Connect **desactivado**, cada banda por separado. Actualización automática de firmware **desactivada**; no se actualizó el firmware. |
| Aviso "otro router en la red" | Se eligió **"This router is independent of my modem"** (modo router, no Access Point). |
| Internet | ✅ Un notebook en `PackIA-Linea-5G` abre páginas web. |
| 1.6 LAN | IP del router `192.168.0.1` (sin cambios). Plan de direcciones de la sección 2 se mantiene. |
| 1.6 DHCP | Venía con rango `192.168.0.2 – 192.168.0.253`, que incluía las IP fijas. **Cambiado a `192.168.0.100 – 192.168.0.249`.** |
| 1.7 Reinicios | Actualización automática y reinicio programado desactivados. |
| 1.8 Respaldo | Hecho. |

## 3. Fase 2 — Pi en la red (sin empezar)

No se ha avanzado en esta fase. Al revisar el material se encontraron dos problemas y se acordó cómo resolverlos cuando se retome.

**Problemas encontrados:**

- La microSD de la Pi tiene un proyecto anterior (se puede borrar), pero **no hay lector de microSD** para regrabarla.
- Hay **un solo cable de red**, y está ocupado en el WAN (internet de la U).

**Solución acordada (por aplicar):** grabar Raspberry Pi OS (64-bit) en un **pendrive** desde un notebook con Raspberry Pi Imager, sacar la microSD de la Pi y arrancar desde el pendrive. Mientras no haya otro cable, la Pi se conecta **por Wi-Fi** a `PackIA-Linea-5G`.

Ajustes que se usarán en el Imager: hostname `e5-pi`, usuario `packia`, Wi-Fi `PackIA-Linea-5G` (país CL), zona `America/Santiago`, SSH activado.

**Diferencias con el plan:**

| Plan | Lo que se hará | Cuándo volver al plan |
|---|---|---|
| Sistema en la microSD | Sistema en un pendrive | Opcional: copiar a la microSD con *SD Card Copier* desde la Pi. |
| Pi por cable en LAN 1, sin Wi-Fi | Pi por Wi-Fi | Cuando haya un segundo cable: conectar a LAN y reservar la `.10` con la MAC **de la tarjeta de red cableada** (es distinta a la del Wi-Fi). |

**Siguientes pasos:** 2.1 grabar el pendrive con Raspberry Pi Imager → 2.2 arrancar la Pi desde el pendrive → 2.3 encontrarla en *Clients* → 2.4 SSH → 2.5 reservar `192.168.0.10` → 2.6 Docker → 2.7 API → 2.8 y 2.9 pruebas.

## 4. Pendientes y material que falta

| Pendiente | Prioridad |
|---|---|
| **Cables de red**: hoy hay 1. Se necesitan al menos 2 más ahora (Pi y notebook o una estación) y uno por estación después. | Alta |
| Teclado USB (para emergencias en la Pi) | Media |
| Switch de 8 puertos | Media |
| Corregir `conexion-estaciones.md`: usa `192.168.10.10`, la red real es `192.168.0.x` | Baja |

## 5. Registro de configuración (sección 13 del plan)

| Dato | Valor |
|---|---|
| Red del router (IP / máscara) | `192.168.0.1` / `255.255.255.0` |
| Rango DHCP automático | `192.168.0.100 – 192.168.0.249` |
| Nombre Wi-Fi 2,4 GHz / 5 GHz | `PackIA-Linea` / `PackIA-Linea-5G` |
| Modo del router | Router (WAN = red de la U, Dynamic IP) |
| Dónde están guardadas las contraseñas | Grupo del equipo |
| Respaldo del router (fecha) | 2026-11-18 |
| Versión del firmware del router | Sin anotar |
| MAC de la Pi (Wi-Fi / cable) | Pendiente |
| IP de la Pi | Pendiente (`192.168.0.10` planificada) |
| Usuario de la Pi | `packia` |

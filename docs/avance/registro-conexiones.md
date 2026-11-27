# Registro de avance — Conexiones de la línea

**Jornadas:** miércoles 18 y miércoles 25 de noviembre de 2026, en la universidad · **Plan que se sigue:** [`docs/plan/plan-conexiones.md`](../plan/plan-conexiones.md)
**Última actualización:** 2026-11-25, cierre de la segunda jornada (hora de Chile)

> Registro de lo que se hizo en cada fase del plan de conexiones, lo que salió distinto a lo planeado y lo que falta. **Sin contraseñas.** Las claves se guardan en el grupo del equipo.

---

## 1. Resumen

- ✅ **Fase 1 (router): lista, rehecha el 25 de noviembre.** Se olvidó la clave de administrador y hubo que volver a fábrica y configurarlo de nuevo (sección 3). Quedan por confirmar algunos ajustes (sección 6).
- ⏳ **Fase 2 (Pi + API): en curso.** La microSD ya tiene Raspberry Pi OS (64-bit), pero **todavía no se pone en la Pi** y el cable de red de la Pi resultó malo. Se retoma otro día: microSD en la Pi y un cable bueno.
- Fases 3 a 7: pendientes.

## 2. Jornada 1 (18 de noviembre) — Router

| Paso | Resultado |
|---|---|
| 1.2 Conexión física | Router y Pi a la corriente. Cable de red de la U al puerto **WAN**. |
| Estado inicial | El router **venía configurado de antes**: Wi-Fi con otro nombre y clave de administrador desconocida. |
| 1.9 Reset de fábrica | Hecho (botón Reset ~10 s). |
| 1.3 Primer ingreso | Clave de administrador nueva creada. TP-Link ID omitido. |
| 1.4 Asistente | Zona horaria Santiago. Internet: **Dynamic IP**, sin clonar MAC. Smart Connect **desactivado**, cada banda por separado. Actualización automática de firmware **desactivada**; no se actualizó el firmware. |
| Aviso "otro router en la red" | Se eligió **"This router is independent of my modem"** (modo router, no Access Point). |
| Internet | ✅ Un notebook en `PackIA-Linea-5G` abre páginas web. |
| 1.6 LAN | IP del router `192.168.0.1` (sin cambios). Plan de direcciones de la sección 2 del plan se mantiene. |
| 1.6 DHCP | Venía con rango `192.168.0.2 – 192.168.0.253`, que incluía las IP fijas. **Cambiado a `192.168.0.100 – 192.168.0.249`.** |
| 1.7 Reinicios | Actualización automática y reinicio programado desactivados. |
| 1.8 Respaldo | Hecho. ⚠️ Ya no sirve: guarda la clave de administrador olvidada (ver sección 3). |

En esa jornada no se avanzó con la Pi: no había lector de microSD y había un solo cable de red (ocupado en el WAN). Se había acordado usar un pendrive y Wi-Fi provisoria, pero el 25 se resolvió de otra forma (sección 4).

## 3. Jornada 2 (25 de noviembre) — Router otra vez

| Paso | Resultado |
|---|---|
| Problema | **Nadie recordaba la clave de administrador** creada el 18. Se probó con la del Wi-Fi, sin éxito. |
| Decisión | Reset de fábrica y configurar de nuevo. **No se usó Restore** con el respaldo del 18, porque traería la misma clave olvidada. |
| 1.9 Reset de fábrica | Hecho. |
| 1.3 Primer ingreso | Clave de administrador nueva creada. ⚠️ Confirmar que quedó anotada en el grupo del equipo. |
| 1.4 Asistente | Internet: **Dynamic IP** con **"Use Default MAC Address"** (sin clonar). Actualización automática **desactivada**. Wi-Fi `PackIA-Linea` / `PackIA-Linea-5G` con la misma clave de antes. |
| Wi-Fi | ✅ Notebooks conectados a `PackIA-Linea-5G` y entrando a `tplinkwifi.net` con la clave nueva. |
| Lista de clientes | En esta versión del firmware no apareció **Network Map**; la lista de equipos se vio en **Advanced → Network → DHCP Server**. |
| 1.6 DHCP | ⚠️ Por confirmar que se volvió a cambiar el rango a `192.168.0.100 – 192.168.0.249` (de fábrica viene `.2 – .253`). |
| 1.7 Reinicios | ⚠️ Por confirmar el reinicio programado desactivado. |
| 1.8 Respaldo | ⏳ Pendiente hacer uno nuevo. |

## 4. Fase 2 — Pi en la red (en curso)

**Cambio respecto de lo acordado el 18:** apareció un **adaptador SD** para la microSD y llegaron **2 cables de red** y el teclado. Por eso se volvió al plan original: sistema **en la microSD** (sin pendrive) y Pi **por cable** en el LAN 1.

| Paso | Resultado |
|---|---|
| 2.1 Grabar la microSD | ✅ Hecho con Raspberry Pi Imager en un notebook Windows del equipo, usando el adaptador SD. Raspberry Pi 5 · Raspberry Pi OS (64-bit) · SSH activado con contraseña. Windows pidió instalar un controlador de **Raspberry Pi Limited** (se aceptó). Se borró el proyecto anterior que tenía la tarjeta. |
| Ajustes del Imager | ⚠️ **Por confirmar** el nombre del equipo y el usuario que quedaron. Durante la grabación se escribieron `Estacion5PackIA` (hostname) y `pack_ia` (usuario); lo recomendado por el plan es `e5-pi` y `packia`. También falta confirmar si se configuró el Wi-Fi `PackIA-Linea-5G`. |
| 2.2 Primer arranque | ❌ **No se hizo:** la microSD grabada **no se alcanzó a poner en la Pi**, así que la Pi todavía no ha arrancado con el sistema nuevo. El cable de la Pi se conectó al **LAN 1** del router. |
| 2.3 Encontrarla en la red | ❌ La Pi no apareció en la lista de DHCP Server (solo dos notebooks). Era esperable sin la microSD. Además, el **cable de red de la Pi resultó malo**. |

**Se detuvo aquí** para seguir el plan en orden y no resolverlo con un atajo. Se retoma otro día con un cable bueno.

**Siguientes pasos:** confirmar los pendientes del router (sección 6) → **poner la microSD en la Pi** (ranura por debajo de la placa) → cable bueno de la Pi al LAN 1 → encender y esperar 3–5 min → 2.3 encontrarla en DHCP Server (MAC de Raspberry Pi empieza con `2C:CF:67`, `D8:3A:DD`, `DC:A6:32`, `E4:5F:01`, `28:CD:C1` o `B8:27:EB`) → 2.4 SSH → 2.5 reservar `192.168.0.10` con la MAC **cableada** → respaldo del router → 2.6 Docker → 2.7 API → 2.8 y 2.9 pruebas.

## 5. Material

| Material | Estado |
|---|---|
| Cables de red | 2: uno en el WAN (funciona) y uno para la Pi (**malo**). Falta al menos 1 bueno ahora y uno por estación después. |
| Adaptador SD para la microSD | ✅ Disponible |
| Teclado USB | ✅ Disponible |
| Switch de 8 puertos | ⏳ Por conseguir |

## 6. Pendientes para la próxima jornada

| Pendiente | Prioridad |
|---|---|
| **Poner la microSD grabada en la Pi** antes de encenderla. | Alta |
| **Conseguir un cable de red bueno** para la Pi (y probarlo antes con un notebook). | Alta |
| Confirmar que la **clave de administrador nueva** está en el grupo del equipo. | Alta |
| Revisar en el router: rango DHCP `192.168.0.100 – 192.168.0.249`, reinicio programado desactivado, Hide SSID desactivado. | Alta |
| Confirmar el **hostname** y el **usuario** que quedaron en la Pi. Si no son `e5-pi` y `packia`, decidir si se regraba la microSD o se actualiza el plan con los nombres reales. | Alta |
| Hacer un **respaldo nuevo** del router y descartar el del 18. | Media |
| Anotar la versión del firmware del router. | Baja |
| Probar un notebook en `PackIA-Linea` (2,4 GHz). | Baja |
| ~~Corregir `conexion-estaciones.md`: usaba `192.168.10.10`, la red real es `192.168.0.x`~~ | ✅ Corregido |

## 7. Registro de configuración (sección 13 del plan)

| Dato | Valor |
|---|---|
| Red del router (IP / máscara) | `192.168.0.1` / `255.255.255.0` |
| Rango DHCP automático | `192.168.0.100 – 192.168.0.249` (⚠️ confirmar después del reset del 25) |
| Nombre Wi-Fi 2,4 GHz / 5 GHz | `PackIA-Linea` / `PackIA-Linea-5G` |
| Modo del router | Router (WAN = red de la U, Dynamic IP, MAC por defecto) |
| Dónde están guardadas las contraseñas | Grupo del equipo (⚠️ confirmar la clave de administrador nueva) |
| Respaldo del router (fecha) | Pendiente (el del 2026-11-18 quedó obsoleto) |
| Versión del firmware del router | Sin anotar |
| Sistema de la Pi | Raspberry Pi OS (64-bit) en la microSD, grabado el 2026-11-25 |
| Hostname de la Pi | Por confirmar (`e5-pi` planificado) |
| Usuario de la Pi | Por confirmar (`packia` planificado) |
| MAC de la Pi (cable / Wi-Fi) | Pendiente |
| IP de la Pi | Pendiente (`192.168.0.10` planificada) |

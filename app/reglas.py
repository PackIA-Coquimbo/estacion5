from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from app.config import (
    CONFIANZA_MINIMA,
    MINIMO_BAJAS_TENDENCIA,
    SEGUNDOS_SIN_SENAL,
    VENTANA_CONFIANZA,
)
from app.schemas import E1Payload, E2Payload, E3Payload, E4Payload, E6Payload


@dataclass(frozen=True)
class AlertaEvaluada:
    codigo: str
    estacion: str
    severidad: str
    mensaje: str
    id_fruta: str | None = None


def evaluar(
    lectura: E1Payload | E2Payload | E3Payload | E4Payload | E6Payload,
    *,
    confianza_reciente: Sequence[float] = (),
) -> list[AlertaEvaluada]:
    alertas = []

    if isinstance(lectura, E1Payload):
        if not lectura.datos.validez_imagen:
            alertas.append(
                AlertaEvaluada(
                    "e1_imagen_invalida", "E1", "falla", "Imagen no válida",
                    lectura.id_fruta,
                )
            )
        if (
            lectura.datos.estado_captura != "aceptada"
            or not lectura.datos.posicion_correcta
        ):
            alertas.append(
                AlertaEvaluada(
                    "e1_captura_requiere_atencion",
                    "E1",
                    "alerta",
                    "Captura no aceptada o posición incorrecta",
                    lectura.id_fruta,
                )
            )

    if isinstance(lectura, E2Payload):
        if lectura.datos.confianza_visual < CONFIANZA_MINIMA:
            alertas.append(
                AlertaEvaluada(
                    "e2_confianza_baja",
                    "E2",
                    "alerta",
                    f"Confianza visual baja: {lectura.datos.confianza_visual:.2f}",
                    lectura.id_fruta,
                )
            )
        recientes = [lectura.datos.confianza_visual, *confianza_reciente]
        if (
            sum(valor < CONFIANZA_MINIMA for valor in recientes[:VENTANA_CONFIANZA])
            >= MINIMO_BAJAS_TENDENCIA
        ):
            alertas.append(
                AlertaEvaluada(
                    "e2_tendencia_confianza_baja",
                    "E2",
                    "alerta",
                    f"{MINIMO_BAJAS_TENDENCIA} o más frutas con confianza baja "
                    f"entre las últimas {VENTANA_CONFIANZA}",
                )
            )

    if isinstance(lectura, E4Payload):
        if lectura.datos.categoria_final == "rechazo":
            alertas.append(
                AlertaEvaluada(
                    "e4_fruta_rechazada",
                    "E4",
                    "falla",
                    "Fruta clasificada como rechazo",
                    lectura.id_fruta,
                )
            )
        if lectura.datos.requiere_revision_manual:
            alertas.append(
                AlertaEvaluada(
                    "e4_revision_manual",
                    "E4",
                    "alerta",
                    "La fruta requiere revisión manual",
                    lectura.id_fruta,
                )
            )

    if isinstance(lectura, E6Payload) and (
        lectura.datos.falla_mecanica_detectada
        or lectura.datos.estado_cinta == "falla_mecanica"
    ):
        alertas.append(
            AlertaEvaluada(
                "e6_falla_cinta",
                "E6",
                "falla_critica",
                "Falla mecánica detectada en la cinta",
            )
        )

    return alertas


def evaluar_sin_senal(
    ultima_lectura_por_estacion: Mapping[str, datetime],
    *,
    cinta_en_marcha: bool,
    inicio_marcha: datetime,
    ahora: datetime,
    segundos_sin_senal: int = SEGUNDOS_SIN_SENAL,
) -> list[AlertaEvaluada]:
    if not cinta_en_marcha:
        return []

    alertas = []
    for estacion in ("E1", "E2", "E3", "E4", "E6"):
        ultima_lectura = ultima_lectura_por_estacion.get(estacion, inicio_marcha)
        if (ahora - ultima_lectura).total_seconds() > segundos_sin_senal:
            alertas.append(
                AlertaEvaluada(
                    f"{estacion.lower()}_sin_senal",
                    estacion,
                    "alerta",
                    f"Estación {estacion} sin señal por más de "
                    f"{segundos_sin_senal} segundos",
                )
            )
    return alertas

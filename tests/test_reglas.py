"""Tests de las reglas de alerta para contratos v3."""

import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.config import (
    CONFIANZA_MINIMA,
    MINIMO_BAJAS_TENDENCIA,
    SEGUNDOS_SIN_SENAL,
    VENTANA_CONFIANZA,
)
from app.reglas import evaluar, evaluar_sin_senal
from app.schemas import E1Payload, E2Payload, E3Payload, E4Payload, E6Payload
from conftest import leer_contrato

MODELOS = {
    "E1": E1Payload,
    "E2": E2Payload,
    "E3": E3Payload,
    "E4": E4Payload,
    "E6": E6Payload,
}


def mensaje(estacion: str, ajustar=None):
    datos = copy.deepcopy(leer_contrato(estacion))
    if ajustar is not None:
        ajustar(datos)
    return MODELOS[estacion].model_validate(datos)


def codigos(alertas) -> list[str]:
    return [alerta.codigo for alerta in alertas]


@pytest.mark.parametrize("estacion", ["E1", "E2", "E3", "E6"])
def test_contrato_normal_sin_alertas(estacion):
    assert evaluar(mensaje(estacion)) == []


def test_e1_imagen_invalida():
    alerta = evaluar(
        mensaje("E1", lambda datos: datos["datos"].update(validez_imagen=False))
    )
    assert codigos(alerta) == ["e1_imagen_invalida"]
    assert alerta[0].id_fruta == "M-0001"
    assert alerta[0].severidad == "falla"


@pytest.mark.parametrize(
    "campo, valor",
    [("estado_captura", "repetir"), ("estado_captura", "revision"),
     ("posicion_correcta", False)],
)
def test_e1_captura_no_aceptada(campo, valor):
    alerta = evaluar(
        mensaje("E1", lambda datos: datos["datos"].update({campo: valor}))
    )
    assert codigos(alerta) == ["e1_captura_requiere_atencion"]
    assert alerta[0].severidad == "alerta"


def test_e2_confianza_baja():
    alerta = evaluar(
        mensaje("E2", lambda datos: datos["datos"].update(confianza_visual=0.5))
    )
    assert codigos(alerta) == ["e2_confianza_baja"]
    assert alerta[0].id_fruta == "M-0001"


def test_e2_confianza_en_el_minimo_no_es_baja():
    assert evaluar(
        mensaje(
            "E2",
            lambda datos: datos["datos"].update(
                confianza_visual=CONFIANZA_MINIMA
            ),
        )
    ) == []


def test_e2_tendencia_conteo_de_ventana():
    baja = mensaje("E2", lambda datos: datos["datos"].update(confianza_visual=0.6))
    anteriores = [0.5] * (MINIMO_BAJAS_TENDENCIA - 1)
    assert codigos(evaluar(baja, confianza_reciente=anteriores)) == [
        "e2_confianza_baja",
        "e2_tendencia_confianza_baja",
    ]


def test_e2_tendencia_respeta_ventana_de_12():
    baja = mensaje("E2", lambda datos: datos["datos"].update(confianza_visual=0.6))
    anteriores = [0.9] * (VENTANA_CONFIANZA - 1) + [0.5] * 3
    assert codigos(evaluar(baja, confianza_reciente=anteriores)) == [
        "e2_confianza_baja"
    ]


def test_e3_no_compara_diametros_entre_mandarinas():
    # La unidad v3 es una mandarina; ya no hay diferencia de diámetros por grupo.
    assert evaluar(mensaje("E3")) == []


def test_e4_fruta_rechazada():
    alerta = evaluar(
        mensaje(
            "E4",
            lambda datos: datos["datos"].update(categoria_final="rechazo"),
        )
    )
    assert codigos(alerta) == ["e4_fruta_rechazada"]
    assert alerta[0].id_fruta == "M-0001"
    assert alerta[0].severidad == "falla"


def test_e4_revision_manual():
    alerta = evaluar(
        mensaje(
            "E4",
            lambda datos: datos["datos"].update(requiere_revision_manual=True),
        )
    )
    assert codigos(alerta) == ["e4_revision_manual"]
    assert alerta[0].id_fruta == "M-0001"


def test_e6_falla_mecanica_detectada():
    alerta = evaluar(
        mensaje(
            "E6",
            lambda datos: datos["datos"].update(
                falla_mecanica_detectada=True
            ),
        )
    )
    assert codigos(alerta) == ["e6_falla_cinta"]
    assert alerta[0].severidad == "falla_critica"


def test_e6_cinta_detenida_no_es_falla():
    assert evaluar(
        mensaje(
            "E6",
            lambda datos: datos["datos"].update(estado_cinta="detenida"),
        )
    ) == []


AHORA = datetime(2026, 11, 25, 10, 20, 0, tzinfo=timezone.utc)
TODAS = ("E1", "E2", "E3", "E4", "E6")


def hace(segundos: float) -> datetime:
    return AHORA - timedelta(seconds=segundos)


def test_sin_senal_con_cinta_detenida_no_alerta():
    assert evaluar_sin_senal(
        {}, cinta_en_marcha=False, inicio_marcha=hace(3600), ahora=AHORA
    ) == []


def test_sin_senal_estacion_vencida():
    lecturas = {estacion: hace(5) for estacion in TODAS}
    lecturas["E2"] = hace(SEGUNDOS_SIN_SENAL + 1)
    alerta = evaluar_sin_senal(
        lecturas,
        cinta_en_marcha=True,
        inicio_marcha=hace(600),
        ahora=AHORA,
    )
    assert codigos(alerta) == ["e2_sin_senal"]
    assert alerta[0].estacion == "E2"


def test_sin_senal_justo_en_el_limite_no_alerta():
    lecturas = {estacion: hace(SEGUNDOS_SIN_SENAL) for estacion in TODAS}
    assert evaluar_sin_senal(
        lecturas,
        cinta_en_marcha=True,
        inicio_marcha=hace(600),
        ahora=AHORA,
    ) == []


def test_sin_senal_ausente_cuenta_desde_inicio_de_cinta():
    recientes = evaluar_sin_senal(
        {},
        cinta_en_marcha=True,
        inicio_marcha=hace(5),
        ahora=AHORA,
    )
    assert recientes == []
    antiguas = evaluar_sin_senal(
        {},
        cinta_en_marcha=True,
        inicio_marcha=hace(SEGUNDOS_SIN_SENAL + 10),
        ahora=AHORA,
    )
    assert codigos(antiguas) == [f"{estacion.lower()}_sin_senal" for estacion in TODAS]

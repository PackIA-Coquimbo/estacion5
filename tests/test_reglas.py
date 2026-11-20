"""Tests de las reglas de anomalías (app/reglas.py) como funciones puras.

Un test por regla de `evaluar` y de `evaluar_sin_senal`, sin API ni base de
datos. Los mensajes parten de los contratos de docs/formato_datos.
"""

import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.config import (
    CONFIANZA_MINIMA,
    DIFERENCIA_DIAMETRO_MAX_MM,
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
    """Contrato de la estación validado con su schema; `ajustar(dict)` lo modifica antes."""
    datos = copy.deepcopy(leer_contrato(estacion))
    if ajustar is not None:
        ajustar(datos)
    return MODELOS[estacion].model_validate(datos)


def codigos(alertas) -> list[str]:
    return [alerta.codigo for alerta in alertas]


def sin_revision_manual(datos):
    for fruta in datos["frutas"]:
        fruta["requiere_revision_manual"] = False


# ------------------------------------------------------------ sin anomalías

@pytest.mark.parametrize("estacion", ["E1", "E2", "E3", "E6"])
def test_contrato_sin_anomalias(estacion):
    assert evaluar(mensaje(estacion)) == []


def test_e4_sin_rechazo_ni_revision_no_alerta():
    assert evaluar(mensaje("E4", sin_revision_manual)) == []


# ------------------------------------------------------------------------ E1

def test_e1_imagen_invalida():
    def ajustar(d):
        d["datos"]["validez_imagen"] = False

    alertas = evaluar(mensaje("E1", ajustar))
    assert codigos(alertas) == ["e1_imagen_invalida"]
    assert alertas[0].estacion == "E1"
    assert alertas[0].severidad == "falla"


@pytest.mark.parametrize(
    "campo, valor",
    [("estado_captura", "repetir"), ("estado_captura", "revision"), ("posicion_correcta", False)],
)
def test_e1_captura_requiere_atencion(campo, valor):
    def ajustar(d):
        d["datos"][campo] = valor

    alertas = evaluar(mensaje("E1", ajustar))
    assert codigos(alertas) == ["e1_captura_requiere_atencion"]
    assert alertas[0].severidad == "alerta"


# ------------------------------------------------------------ conteo frutas

def test_conteo_distinto_al_de_e1_alerta_por_estacion():
    alertas = evaluar(mensaje("E1"), conteos_por_estacion={"E2": 3, "E3": 2})
    assert codigos(alertas) == ["conteo_frutas_e3"]
    assert alertas[0].estacion == "E3"
    assert "3" in alertas[0].mensaje and "2" in alertas[0].mensaje


def test_conteo_usa_frutas_esperadas_si_el_mensaje_no_es_de_e1():
    alertas = evaluar(mensaje("E2"), frutas_esperadas=3, conteos_por_estacion={"E2": 2})
    assert codigos(alertas) == ["conteo_frutas_e2"]


def test_conteo_igual_no_alerta():
    assert evaluar(mensaje("E1"), conteos_por_estacion={"E2": 3, "E3": 3, "E4": 3}) == []


def test_conteo_sin_frutas_esperadas_no_alerta():
    assert evaluar(mensaje("E3"), frutas_esperadas=None, conteos_por_estacion={"E3": 1}) == []


# ------------------------------------------------------------------------ E2

def test_e2_confianza_baja():
    def ajustar(d):
        d["frutas"][1]["confianza_visual"] = 0.5

    alertas = evaluar(mensaje("E2", ajustar))
    assert codigos(alertas) == ["e2_confianza_baja"]
    assert alertas[0].id_fruta == "F2"
    assert alertas[0].estacion == "E2"


def test_e2_confianza_en_el_minimo_no_es_baja():
    def ajustar(d):
        d["frutas"][0]["confianza_visual"] = CONFIANZA_MINIMA

    assert evaluar(mensaje("E2", ajustar)) == []


def test_e2_tendencia_confianza_baja_con_lecturas_recientes():
    def ajustar(d):
        d["frutas"][0]["confianza_visual"] = 0.6

    recientes = [0.5] * (MINIMO_BAJAS_TENDENCIA - 1)
    alertas = evaluar(mensaje("E2", ajustar), confianza_reciente=recientes)
    assert codigos(alertas) == ["e2_confianza_baja", "e2_tendencia_confianza_baja"]


def test_e2_tendencia_ignora_lo_que_queda_fuera_de_la_ventana():
    def ajustar(d):
        d["frutas"][0]["confianza_visual"] = 0.6

    # El mensaje trae 3 frutas: de las recientes solo cuentan las primeras
    # VENTANA_CONFIANZA - 3; las bajas quedan fuera de la ventana
    recientes = [0.9] * (VENTANA_CONFIANZA - 3) + [0.5] * MINIMO_BAJAS_TENDENCIA
    alertas = evaluar(mensaje("E2", ajustar), confianza_reciente=recientes)
    assert codigos(alertas) == ["e2_confianza_baja"]


# ------------------------------------------------------------------------ E3

def test_e3_grupo_irregular():
    def ajustar(d):
        d["frutas"][0]["diametro_mm"] = 30
        d["frutas"][1]["diametro_mm"] = 30 + DIFERENCIA_DIAMETRO_MAX_MM + 1

    alertas = evaluar(mensaje("E3", ajustar))
    assert codigos(alertas) == ["e3_grupo_irregular"]
    assert alertas[0].estacion == "E3"


def test_e3_diferencia_igual_al_maximo_no_alerta():
    def ajustar(d):
        d["frutas"][0]["diametro_mm"] = 30
        d["frutas"][1]["diametro_mm"] = 30 + DIFERENCIA_DIAMETRO_MAX_MM
        d["frutas"][2]["diametro_mm"] = 35

    assert evaluar(mensaje("E3", ajustar)) == []


def test_e3_una_sola_fruta_no_alerta():
    def ajustar(d):
        d["frutas"] = d["frutas"][:1]

    assert evaluar(mensaje("E3", ajustar), diferencia_diametro_max_mm=0) == []


def test_e3_maximo_configurable():
    # El contrato tiene 33 y 47 mm: diferencia de 14
    assert codigos(evaluar(mensaje("E3"), diferencia_diametro_max_mm=10)) == ["e3_grupo_irregular"]


# ------------------------------------------------------------------------ E4

def test_e4_fruta_rechazada():
    def ajustar(d):
        sin_revision_manual(d)
        d["frutas"][0]["categoria_final"] = "rechazo"

    alertas = evaluar(mensaje("E4", ajustar))
    assert codigos(alertas) == ["e4_fruta_rechazada"]
    assert alertas[0].id_fruta == "F1"
    assert alertas[0].severidad == "falla"


def test_e4_revision_manual():
    # El contrato trae F3 con requiere_revision_manual: true
    alertas = evaluar(mensaje("E4"))
    assert codigos(alertas) == ["e4_revision_manual"]
    assert alertas[0].id_fruta == "F3"
    assert alertas[0].severidad == "alerta"


# ------------------------------------------------------------------------ E6

def test_e6_falla_mecanica_detectada():
    def ajustar(d):
        d["datos"]["falla_mecanica_detectada"] = True

    alertas = evaluar(mensaje("E6", ajustar))
    assert codigos(alertas) == ["e6_falla_cinta"]
    assert alertas[0].severidad == "falla_critica"


def test_e6_estado_falla_mecanica():
    def ajustar(d):
        d["datos"]["estado_cinta"] = "falla_mecanica"

    assert codigos(evaluar(mensaje("E6", ajustar))) == ["e6_falla_cinta"]


def test_e6_cinta_detenida_no_es_falla():
    def ajustar(d):
        d["datos"]["estado_cinta"] = "detenida"

    assert evaluar(mensaje("E6", ajustar)) == []


# ---------------------------------------------------------------- sin señal

AHORA = datetime(2026, 11, 18, 10, 20, 0, tzinfo=timezone.utc)
TODAS = ("E1", "E2", "E3", "E4", "E6")


def hace(segundos: float) -> datetime:
    return AHORA - timedelta(seconds=segundos)


def test_sin_senal_con_cinta_detenida_no_alerta():
    alertas = evaluar_sin_senal(
        {}, cinta_en_marcha=False, inicio_marcha=hace(3600), ahora=AHORA
    )
    assert alertas == []


def test_sin_senal_todas_recientes_no_alerta():
    ultimas = {estacion: hace(5) for estacion in TODAS}
    alertas = evaluar_sin_senal(
        ultimas, cinta_en_marcha=True, inicio_marcha=hace(600), ahora=AHORA
    )
    assert alertas == []


def test_sin_senal_estacion_vencida():
    ultimas = {estacion: hace(5) for estacion in TODAS}
    ultimas["E2"] = hace(SEGUNDOS_SIN_SENAL + 1)
    alertas = evaluar_sin_senal(
        ultimas, cinta_en_marcha=True, inicio_marcha=hace(600), ahora=AHORA
    )
    assert codigos(alertas) == ["e2_sin_senal"]
    assert alertas[0].estacion == "E2"
    assert alertas[0].severidad == "alerta"


def test_sin_senal_justo_en_el_limite_no_alerta():
    ultimas = {estacion: hace(SEGUNDOS_SIN_SENAL) for estacion in TODAS}
    alertas = evaluar_sin_senal(
        ultimas, cinta_en_marcha=True, inicio_marcha=hace(600), ahora=AHORA
    )
    assert alertas == []


def test_sin_senal_estacion_sin_lecturas_cuenta_desde_inicio_marcha():
    recien = evaluar_sin_senal(
        {}, cinta_en_marcha=True, inicio_marcha=hace(5), ahora=AHORA
    )
    assert recien == []

    hace_rato = evaluar_sin_senal(
        {}, cinta_en_marcha=True, inicio_marcha=hace(SEGUNDOS_SIN_SENAL + 10), ahora=AHORA
    )
    assert codigos(hace_rato) == [f"{e.lower()}_sin_senal" for e in TODAS]


def test_sin_senal_plazo_configurable():
    ultimas = {estacion: hace(10) for estacion in TODAS}
    alertas = evaluar_sin_senal(
        ultimas, cinta_en_marcha=True, inicio_marcha=hace(600), ahora=AHORA,
        segundos_sin_senal=5,
    )
    assert len(alertas) == 5

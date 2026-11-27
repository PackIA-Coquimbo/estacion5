"""Tests de contratos v3 y del simulador por mandarina."""

import random
from datetime import datetime

import pytest

from conftest import ESTACIONES, leer_contrato
from tools import simulador

ESTADOS_CAPTURA = {"aceptada", "repetir", "revision"}
CALIDADES = {"alta", "media", "baja", "defectos_visibles", "revision"}
TAMANOS = {"pequeno", "mediano", "grande"}
CATEGORIAS = {
    "exportacion",
    "mercado_nacional",
    "proceso",
    "rechazo",
    "revision_manual",
}
ESTADOS_CINTA = {"normal", "detenida", "falla_mecanica"}


def errores_contrato(mensaje: dict) -> list[str]:
    errores = []

    def revisar(condicion: bool, texto: str) -> None:
        if not condicion:
            errores.append(texto)

    estacion = mensaje.get("estacion")
    revisar(estacion in ESTACIONES, f"estacion inválida: {estacion}")
    revisar(
        isinstance(mensaje.get("id_lote"), str) and bool(mensaje["id_lote"]),
        "falta id_lote",
    )
    revisar("id_grupo" not in mensaje and "frutas" not in mensaje, "payload v2")
    try:
        fecha = datetime.fromisoformat(mensaje["timestamp"].replace("Z", "+00:00"))
        revisar(fecha.tzinfo is not None, "timestamp sin zona horaria")
    except (KeyError, AttributeError, ValueError):
        errores.append("timestamp ausente o inválido")

    if estacion == "E6":
        datos = mensaje.get("datos")
        if not isinstance(datos, dict):
            return errores + ["falta datos"]
        revisar(datos.get("estado_cinta") in ESTADOS_CINTA, "estado_cinta inválido")
        revisar(
            isinstance(datos.get("falla_mecanica_detectada"), bool),
            "falla_mecanica_detectada debe ser booleano",
        )
        revisar(
            datos.get("id_fruta_en_cinta") is None
            or isinstance(datos.get("id_fruta_en_cinta"), str),
            "id_fruta_en_cinta debe ser texto u omitirse",
        )
        return errores

    revisar(
        isinstance(mensaje.get("id_fruta"), str) and bool(mensaje["id_fruta"]),
        "falta id_fruta",
    )
    datos = mensaje.get("datos")
    if not isinstance(datos, dict):
        return errores + ["falta datos"]

    if estacion == "E1":
        revisar(isinstance(datos.get("validez_imagen"), bool), "validez_imagen inválida")
        revisar(datos.get("estado_captura") in ESTADOS_CAPTURA, "estado_captura inválido")
        revisar(
            isinstance(datos.get("posicion_correcta"), bool),
            "posicion_correcta inválida",
        )
    elif estacion == "E2":
        revisar(datos.get("calidad_visual") in CALIDADES, "calidad_visual inválida")
        revisar(
            isinstance(datos.get("confianza_visual"), (int, float))
            and 0 <= datos["confianza_visual"] <= 1,
            "confianza_visual inválida",
        )
        revisar(isinstance(datos.get("defectos_detectados"), list), "defectos inválidos")
    elif estacion == "E3":
        revisar(
            isinstance(datos.get("diametro_mm"), (int, float))
            and datos["diametro_mm"] > 0,
            "diametro_mm inválido",
        )
        revisar(datos.get("tamano") in TAMANOS, "tamano inválido")
    elif estacion == "E4":
        revisar(datos.get("categoria_final") in CATEGORIAS, "categoria_final inválida")
        revisar(
            isinstance(datos.get("probabilidad"), (int, float))
            and 0 <= datos["probabilidad"] <= 1,
            "probabilidad inválida",
        )
        revisar(
            isinstance(datos.get("requiere_revision_manual"), bool),
            "requiere_revision_manual inválido",
        )
    return errores


def generar_mensajes(rng, numero, rangos=(60.0, 70.0), baja_confianza=False):
    id_fruta = f"M-{numero:04d}"
    lote = "LOTE-TEST"
    e1 = simulador.generar_e1(rng, lote, id_fruta)
    e2 = simulador.generar_e2(rng, lote, id_fruta, baja_confianza)
    e3 = simulador.generar_e3(rng, lote, id_fruta, *rangos)
    e4 = simulador.generar_e4(rng, lote, e2)
    return e1, e2, e3, e4


@pytest.mark.parametrize("estacion", ESTACIONES)
def test_contrato_cumple_formato_v3(estacion):
    assert errores_contrato(leer_contrato(estacion)) == []


@pytest.mark.parametrize("estacion", ESTACIONES)
def test_estacion_coincide_con_el_archivo(estacion):
    assert leer_contrato(estacion)["estacion"] == estacion


def test_contratos_comparten_lote_y_mandarina(contratos):
    assert {mensaje["id_lote"] for mensaje in contratos.values()} == {
        "LOTE-2026-11-A"
    }
    ids = {
        mensaje["id_fruta"]
        for estacion, mensaje in contratos.items()
        if estacion != "E6"
    }
    assert ids == {"M-0001"}
    assert contratos["E6"]["datos"]["id_fruta_en_cinta"] in ids


def test_e3_64mm_es_mediano(contratos):
    assert contratos["E3"]["datos"]["diametro_mm"] == 64
    assert contratos["E3"]["datos"]["tamano"] == "mediano"


def test_validador_detecta_payload_v2_y_datos_invalidos(contratos):
    v2 = dict(contratos["E1"], id_grupo="G-0001")
    assert "payload v2" in errores_contrato(v2)
    invalido = dict(
        contratos["E3"],
        datos={"diametro_mm": 0, "tamano": "enorme"},
    )
    assert len(errores_contrato(invalido)) == 2
    sin_zona = dict(contratos["E1"], timestamp="2026-11-25T10:15:30")
    assert "timestamp sin zona horaria" in errores_contrato(sin_zona)


@pytest.mark.parametrize("baja_confianza", [False, True])
def test_simulador_genera_mensajes_validos(baja_confianza):
    rng = random.Random(42)
    for numero in range(1, 201):
        for mensaje in generar_mensajes(
            rng, numero, baja_confianza=baja_confianza
        ):
            assert errores_contrato(mensaje) == [], mensaje


@pytest.mark.parametrize("estado", sorted(ESTADOS_CINTA))
def test_simulador_e6_valido(estado):
    mensaje = simulador.generar_e6("LOTE-TEST", estado, "M-0001")
    assert errores_contrato(mensaje) == []
    assert mensaje["datos"]["falla_mecanica_detectada"] == (
        estado == "falla_mecanica"
    )
    assert errores_contrato(simulador.generar_e6("LOTE-TEST", estado, None)) == []


def test_simulador_mantiene_id_fruta_y_categoria_coherentes():
    e1, e2, e3, e4 = generar_mensajes(random.Random(1), 1)
    assert e1["id_fruta"] == e2["id_fruta"] == e3["id_fruta"] == e4["id_fruta"]
    assert e4["datos"]["categoria_final"] == simulador.CATEGORIA_POR_CALIDAD[
        e2["datos"]["calidad_visual"]
    ]


@pytest.mark.parametrize(
    "diametro, esperado",
    [(59, "pequeno"), (60, "mediano"), (64, "mediano"), (70, "mediano"), (71, "grande")],
)
def test_tamano_por_rangos_v3(diametro, esperado):
    assert simulador.tamano_para(diametro, 60, 70) == esperado

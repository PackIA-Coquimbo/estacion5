"""Validación HTTP de los contratos de ingesta v3."""

import copy

import pytest

from conftest import ESTACIONES


def ruta(estacion: str) -> str:
    return f"/api/v1/ingest/{estacion.lower()}"


def cambiar(mensaje: dict, camino: list, valor) -> dict:
    copia = copy.deepcopy(mensaje)
    destino = copia
    for paso in camino[:-1]:
        destino = destino[paso]
    destino[camino[-1]] = valor
    return copia


def borrar(mensaje: dict, camino: list) -> dict:
    copia = copy.deepcopy(mensaje)
    destino = copia
    for paso in camino[:-1]:
        destino = destino[paso]
    del destino[camino[-1]]
    return copia


@pytest.mark.parametrize("estacion", ESTACIONES)
def test_contrato_valido_responde_201(client, contratos, estacion):
    respuesta = client.post(ruta(estacion), json=contratos[estacion])
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["duplicado"] is False


def test_e6_sin_id_fruta_en_cinta_es_valido(client, contratos):
    mensaje = borrar(contratos["E6"], ["datos", "id_fruta_en_cinta"])
    assert client.post(ruta("E6"), json=mensaje).status_code == 201


def test_e2_defectos_vacios_son_validos(client, contratos):
    mensaje = cambiar(
        contratos["E2"], ["datos", "defectos_detectados"], []
    )
    assert client.post(ruta("E2"), json=mensaje).status_code == 201


@pytest.mark.parametrize(
    "estacion, camino",
    [
        ("E1", ["id_lote"]),
        ("E1", ["id_fruta"]),
        ("E1", ["timestamp"]),
        ("E1", ["datos"]),
        ("E1", ["datos", "estado_captura"]),
        ("E2", ["datos", "confianza_visual"]),
        ("E3", ["datos", "diametro_mm"]),
        ("E3", ["datos", "tamano"]),
        ("E4", ["datos", "categoria_final"]),
        ("E4", ["datos", "requiere_revision_manual"]),
        ("E6", ["id_lote"]),
        ("E6", ["datos", "estado_cinta"]),
        ("E6", ["datos", "falla_mecanica_detectada"]),
    ],
)
def test_campo_obligatorio_responde_422(client, contratos, estacion, camino):
    mensaje = borrar(contratos[estacion], camino)
    assert client.post(ruta(estacion), json=mensaje).status_code == 422


@pytest.mark.parametrize(
    "estacion, camino, valor",
    [
        ("E1", ["datos", "estado_captura"], "rechazada"),
        ("E2", ["datos", "calidad_visual"], "excelente"),
        ("E2", ["datos", "confianza_visual"], 1.5),
        ("E2", ["datos", "confianza_visual"], -0.1),
        ("E3", ["datos", "diametro_mm"], 0),
        ("E3", ["datos", "tamano"], "enorme"),
        ("E4", ["datos", "categoria_final"], "basura"),
        ("E4", ["datos", "probabilidad"], 1.01),
        ("E6", ["datos", "estado_cinta"], "rapida"),
        ("E1", ["timestamp"], "2026-11-25T10:15:30"),
        ("E1", ["timestamp"], "ayer"),
    ],
)
def test_valor_invalido_responde_422(client, contratos, estacion, camino, valor):
    mensaje = cambiar(contratos[estacion], camino, valor)
    assert client.post(ruta(estacion), json=mensaje).status_code == 422


@pytest.mark.parametrize("estacion", ESTACIONES)
def test_estacion_distinta_a_la_ruta_responde_422(client, contratos, estacion):
    otra = "E2" if estacion != "E2" else "E1"
    mensaje = cambiar(contratos[estacion], ["estacion"], otra)
    assert client.post(ruta(estacion), json=mensaje).status_code == 422


@pytest.mark.parametrize(
    "origen, destino", [("E1", "E2"), ("E3", "E4"), ("E6", "E1")]
)
def test_mensaje_enviado_a_otra_ruta_responde_422(
    client, contratos, origen, destino
):
    assert client.post(ruta(destino), json=contratos[origen]).status_code == 422


def test_payload_v2_responde_422(client, contratos):
    v2 = dict(contratos["E1"])
    v2.pop("id_fruta")
    v2["id_grupo"] = "G-0001"
    v2["datos"] = {**v2["datos"], "frutas_detectadas": 1}
    assert client.post(ruta("E1"), json=v2).status_code == 422

"""Consultas v3 con una mandarina por mensaje."""

import copy
from datetime import datetime, timezone

import pytest

from app.config import ALMACENAMIENTO_ALERTA_PORCENTAJE

LOTE = "LOTE-2026-11-A"
FRUTA = "M-0001"


def ruta(estacion: str) -> str:
    return f"/api/v1/ingest/{estacion.lower()}"


@pytest.fixture
def cargado(client, contratos):
    ahora = datetime.now(timezone.utc)
    for indice, estacion in enumerate(["E1", "E2", "E3", "E4", "E6"]):
        mensaje = copy.deepcopy(contratos[estacion])
        mensaje["timestamp"] = datetime.fromtimestamp(
            ahora.timestamp() + indice, timezone.utc
        ).isoformat().replace("+00:00", "Z")
        respuesta = client.post(ruta(estacion), json=mensaje)
        assert respuesta.status_code == 201, respuesta.text
    return client


def test_lotes_sin_datos(client):
    assert client.get("/api/v1/lotes").json() == []


def test_lotes_devuelve_cantidad_de_mandarinas(cargado):
    lotes = cargado.get("/api/v1/lotes").json()
    assert len(lotes) == 1
    assert lotes[0]["id_lote"] == LOTE
    assert lotes[0]["total_frutas"] == 1


def test_listado_de_frutas_sigue_el_contrato_del_dashboard(cargado):
    respuesta = cargado.get(f"/api/v1/lotes/{LOTE}/frutas")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id_lote"] == LOTE
    assert cuerpo["total_frutas"] == 1
    assert cuerpo["frutas"][0]["id_fruta"] == FRUTA
    assert cuerpo["frutas"][0]["estado"] == "ok"


def test_lote_inexistente_responde_404(client):
    assert client.get("/api/v1/lotes/NO-EXISTE/frutas").status_code == 404


def test_trazabilidad_de_mandarina(cargado):
    respuesta = cargado.get(f"/api/v1/frutas/{FRUTA}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id_fruta"] == FRUTA
    assert cuerpo["id_lote"] == LOTE
    assert cuerpo["e1"]["estado_captura"] == "aceptada"
    assert cuerpo["e2"]["calidad_visual"] == "alta"
    assert cuerpo["e3"]["diametro_mm"] == 64
    assert cuerpo["e4"]["categoria_final"] == "exportacion"
    assert all(cuerpo[f"e{i}"]["timestamp"] for i in range(1, 5))


def test_mandarina_inexistente_responde_404(client):
    assert client.get("/api/v1/frutas/M-9999").status_code == 404


def test_metricas_v3(cargado):
    metricas = cargado.get("/api/v1/metricas").json()
    assert metricas["id_lote"] is None
    assert metricas["frutas_turno"] == 1
    assert metricas["frutas_ultima_hora"] == 1
    assert metricas["rechazadas"] == 0
    assert metricas["porcentaje_rechazo"] == 0.0
    assert metricas["por_categoria"]["exportacion"] == 1
    assert metricas["por_tamano"]["mediano"] == 1
    assert sum(x["cantidad"] for x in metricas["frutas_por_hora"]) == 1


def test_metricas_filtradas_por_lote(cargado):
    metricas = cargado.get("/api/v1/metricas", params={"lote": LOTE}).json()
    assert metricas["id_lote"] == LOTE
    assert metricas["frutas_turno"] == 1


def test_metricas_lote_inexistente_responde_404(client):
    assert (
        client.get("/api/v1/metricas", params={"lote": "NO-EXISTE"}).status_code
        == 404
    )


def test_porcentaje_rechazo_se_calcula_sobre_clasificadas(
    client, contratos
):
    e4 = copy.deepcopy(contratos["E4"])
    e4["datos"]["categoria_final"] = "rechazo"
    assert client.post(ruta("E4"), json=e4).status_code == 201
    metricas = client.get("/api/v1/metricas").json()
    assert metricas["rechazadas"] == 1
    assert metricas["porcentaje_rechazo"] == 100.0


def test_alertas_se_devuelven_en_el_contenedor_documentado(client, contratos):
    e4 = copy.deepcopy(contratos["E4"])
    e4["datos"]["requiere_revision_manual"] = True
    assert client.post(ruta("E4"), json=e4).status_code == 201
    respuesta = client.get("/api/v1/alertas")
    assert respuesta.status_code == 200
    alertas = respuesta.json()["alertas"]
    assert len(alertas) == 1
    assert alertas[0]["estacion"] == "E4"
    assert alertas[0]["id_fruta"] == FRUTA
    assert alertas[0]["creada_en"] is not None
    assert alertas[0]["resuelta"] is False


def test_alertas_se_filtran_y_pueden_resolverse(client, contratos):
    e4 = copy.deepcopy(contratos["E4"])
    e4["datos"]["requiere_revision_manual"] = True
    client.post(ruta("E4"), json=e4)
    alerta = client.get("/api/v1/alertas").json()["alertas"][0]
    respuesta = client.patch(f"/api/v1/alertas/{alerta['id']}")
    assert respuesta.status_code == 200
    assert respuesta.json()["resuelta"] is True
    assert client.get("/api/v1/alertas").json()["alertas"] == []
    assert len(
        client.get("/api/v1/alertas", params={"activas": "false"}).json()["alertas"]
    ) == 1


def test_estado_estaciones_sin_lecturas(client):
    cuerpo = client.get("/api/v1/estaciones/estado").json()
    assert cuerpo["estaciones"]
    assert [entrada["estacion"] for entrada in cuerpo["estaciones"]] == [
        "E1", "E2", "E3", "E4", "E6"
    ]
    assert all(e["estado"] == "sin_senal" for e in cuerpo["estaciones"])


def test_estado_estaciones_y_cinta_se_ajusta_a_dashboard(cargado):
    respuesta = cargado.get("/api/v1/estaciones/estado")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id_lote"] == LOTE
    assert len(cuerpo["estaciones"]) == 5
    assert all(e["estado"] == "ok" for e in cuerpo["estaciones"])
    e6 = next(e for e in cuerpo["estaciones"] if e["estacion"] == "E6")
    assert e6["estado_cinta"] == "normal"
    assert e6["falla_mecanica_detectada"] is False
    assert e6["id_fruta"] == FRUTA


def test_estado_e6_muestra_falla_mecanica(client, contratos):
    e6 = copy.deepcopy(contratos["E6"])
    e6["datos"]["estado_cinta"] = "falla_mecanica"
    e6["datos"]["falla_mecanica_detectada"] = True
    client.post(ruta("E6"), json=e6)
    resultado = client.get("/api/v1/estaciones/estado").json()
    estado_e6 = next(e for e in resultado["estaciones"] if e["estacion"] == "E6")
    assert estado_e6["estado"] == "falla"
    assert estado_e6["falla_mecanica_detectada"] is True


def test_sistema_reporta_uso_de_almacenamiento(client):
    respuesta = client.get("/api/v1/sistema")
    assert respuesta.status_code == 200
    sistema = respuesta.json()
    assert sistema["almacenamiento_total_bytes"] > 0
    assert 0 <= sistema["almacenamiento_porcentaje"] <= 100
    assert sistema["almacenamiento_alerta"] == (
        sistema["almacenamiento_porcentaje"] >= ALMACENAMIENTO_ALERTA_PORCENTAJE
    )

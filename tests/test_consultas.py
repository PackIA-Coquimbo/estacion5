"""Tests de las consultas GET: responden con los datos que se ingresaron.

Se ingresan los cinco contratos de docs/formato_datos (un grupo de tres
frutas, G-0001) y se revisa lo que devuelve cada endpoint.

No se prueban aquí los errores conocidos del backend (ver
docs/avance/pendientes.md, sección 2): grupos que no se cierran y estado de
la cinta sin GET.
"""

import copy

import pytest

LOTE = "LOTE-2026-11-A"
GRUPO = "G-0001"


def ruta(estacion: str) -> str:
    return f"/api/v1/ingest/{estacion.lower()}"


@pytest.fixture
def cargado(client, contratos):
    """Ingresa E1, E2, E3, E4 y E6 en orden y devuelve el cliente."""
    for estacion in ["E1", "E2", "E3", "E4", "E6"]:
        respuesta = client.post(ruta(estacion), json=contratos[estacion])
        assert respuesta.status_code == 201, respuesta.text
    return client


# --------------------------------------------------------------------- lotes

def test_lotes_vacio_sin_datos(client):
    respuesta = client.get("/api/v1/lotes")
    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_lotes_devuelve_el_lote_ingresado(cargado):
    lotes = cargado.get("/api/v1/lotes").json()
    assert len(lotes) == 1
    assert lotes[0]["id_lote"] == LOTE
    assert lotes[0]["estado"] == "activo"
    assert lotes[0]["grupos"] == 1
    assert lotes[0]["creado_en"] is not None


def test_grupos_del_lote(cargado, contratos):
    respuesta = cargado.get(f"/api/v1/lotes/{LOTE}/grupos")
    assert respuesta.status_code == 200
    grupos = respuesta.json()
    assert len(grupos) == 1
    assert grupos[0]["id_grupo"] == GRUPO
    assert grupos[0]["id_lote"] == LOTE
    assert grupos[0]["frutas_detectadas"] == contratos["E1"]["datos"]["frutas_detectadas"]


def test_grupos_de_lote_inexistente_responde_404(client):
    assert client.get("/api/v1/lotes/NO-EXISTE/grupos").status_code == 404


# -------------------------------------------------------------------- grupos

def test_trazabilidad_del_grupo(cargado, contratos):
    respuesta = cargado.get(f"/api/v1/grupos/{GRUPO}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()

    grupo = cuerpo["grupo"]
    datos_e1 = contratos["E1"]["datos"]
    assert grupo["id_grupo"] == GRUPO
    assert grupo["id_lote"] == LOTE
    assert grupo["frutas_detectadas"] == datos_e1["frutas_detectadas"]
    assert grupo["validez_imagen"] == datos_e1["validez_imagen"]
    assert grupo["estado_captura"] == datos_e1["estado_captura"]
    assert grupo["posicion_correcta"] == datos_e1["posicion_correcta"]

    frutas = {f["id_fruta"]: f for f in cuerpo["frutas"]}
    assert set(frutas) == {"F1", "F2", "F3"}
    for estacion in ["E2", "E3", "E4"]:
        for enviada in contratos[estacion]["frutas"]:
            guardada = frutas[enviada["id_fruta"]]
            for campo, valor in enviada.items():
                assert guardada[campo] == valor, (estacion, enviada["id_fruta"], campo)

    # E6 no informa id_grupo, así que su lectura no queda asociada al grupo
    lecturas = cuerpo["lecturas"]
    assert [l["estacion"] for l in lecturas] == ["E1", "E2", "E3", "E4"]
    for lectura in lecturas:
        assert lectura["payload"]["id_grupo"] == GRUPO
        assert lectura["recibida_en"] is not None


def test_grupo_inexistente_responde_404(client):
    assert client.get("/api/v1/grupos/G-9999").status_code == 404


# ------------------------------------------------------------------ métricas

def test_metricas_con_los_contratos(cargado):
    respuesta = cargado.get("/api/v1/metricas")
    assert respuesta.status_code == 200
    metricas = respuesta.json()

    assert metricas["id_lote"] is None
    assert metricas["conteo_por_categoria"] == {
        "exportacion": 1,
        "mercado_nacional": 1,
        "proceso": 1,
        "rechazo": 0,
        "revision_manual": 0,
    }
    assert metricas["conteo_por_tamano"] == {"pequeno": 1, "mediano": 1, "grande": 1}
    assert metricas["porcentaje_rechazo"] == 0.0
    assert metricas["frutas_por_hora"] == [{"hora": "2026-11-18T10:00:00Z", "cantidad": 3}]
    # El contrato de E4 trae F3 con revisión manual: una alerta de E4
    assert metricas["anomalias_por_estacion"] == {
        "E1": 0, "E2": 0, "E3": 0, "E4": 1, "E6": 0,
    }


def test_metricas_filtradas_por_lote(cargado):
    respuesta = cargado.get("/api/v1/metricas", params={"lote": LOTE})
    assert respuesta.status_code == 200
    assert respuesta.json()["id_lote"] == LOTE
    assert sum(respuesta.json()["conteo_por_categoria"].values()) == 3


def test_metricas_de_lote_inexistente_responde_404(client):
    assert client.get("/api/v1/metricas", params={"lote": "NO-EXISTE"}).status_code == 404


def test_metricas_porcentaje_rechazo(client, contratos):
    e4 = copy.deepcopy(contratos["E4"])
    e4["frutas"][0]["categoria_final"] = "rechazo"
    for estacion, mensaje in [("E1", contratos["E1"]), ("E3", contratos["E3"]), ("E4", e4)]:
        assert client.post(ruta(estacion), json=mensaje).status_code == 201

    metricas = client.get("/api/v1/metricas").json()
    assert metricas["conteo_por_categoria"]["rechazo"] == 1
    assert metricas["porcentaje_rechazo"] == 33.33


# ------------------------------------------------------------------- alertas

def test_alertas_vacio_sin_datos(client):
    assert client.get("/api/v1/alertas").json() == []


def test_alertas_devuelve_la_revision_manual_de_e4(cargado):
    respuesta = cargado.get("/api/v1/alertas")
    assert respuesta.status_code == 200
    alertas = respuesta.json()
    assert len(alertas) == 1
    alerta = alertas[0]
    assert alerta["estacion"] == "E4"
    assert alerta["id_lote"] == LOTE
    assert alerta["id_grupo"] == GRUPO
    assert alerta["id_fruta"] == "F3"
    assert alerta["severidad"] == "alerta"
    assert alerta["resuelta"] is False


def test_alerta_repetida_no_se_duplica(cargado, contratos):
    reenvio = copy.deepcopy(contratos["E4"])
    reenvio["timestamp"] = "2026-11-18T10:17:20Z"
    assert cargado.post(ruta("E4"), json=reenvio).status_code == 201
    assert len(cargado.get("/api/v1/alertas").json()) == 1


# -------------------------------------------------------- estado estaciones

def test_estado_estaciones_sin_datos(client):
    estado = client.get("/api/v1/estaciones/estado").json()
    assert [e["estacion"] for e in estado] == ["E1", "E2", "E3", "E4", "E6"]
    for estacion in estado:
        assert estacion["estado"] == "sin_senal"
        assert estacion["ultima_lectura"] is None
        assert estacion["segundos_desde_lectura"] is None


def test_estado_estaciones_con_datos(cargado):
    respuesta = cargado.get("/api/v1/estaciones/estado")
    assert respuesta.status_code == 200
    for estacion in respuesta.json():
        assert estacion["estado"] == "online", estacion
        assert estacion["ultima_lectura"] is not None
        assert estacion["segundos_desde_lectura"] >= 0

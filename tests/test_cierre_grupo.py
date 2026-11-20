"""Tests del cierre de grupos y del estado de la cinta (E6).

- Un grupo se cierra cuando llegó E1 y E4 clasificó todas sus frutas; queda
  en "rechazo", "anomalia" u "ok" y con la hora de salida.
- GET /api/v1/estaciones/estado incluye estado_cinta y
  falla_mecanica_detectada en la entrada de E6.
"""

import copy

GRUPO = "G-0001"


def ruta(estacion: str) -> str:
    return f"/api/v1/ingest/{estacion.lower()}"


def enviar(client, mensaje: dict) -> dict:
    respuesta = client.post(ruta(mensaje["estacion"]), json=mensaje)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def grupo(client) -> dict:
    return client.get(f"/api/v1/grupos/{GRUPO}").json()["grupo"]


def e4_sin_revision(contratos) -> dict:
    e4 = copy.deepcopy(contratos["E4"])
    for fruta in e4["frutas"]:
        fruta["requiere_revision_manual"] = False
    return e4


def e6_de_estado(client) -> dict:
    estado = client.get("/api/v1/estaciones/estado").json()
    return next(e for e in estado if e["estacion"] == "E6")


# ------------------------------------------------------------ cierre de grupo

def test_grupo_sin_e4_sigue_en_proceso(client, contratos):
    for estacion in ["E1", "E2", "E3"]:
        enviar(client, contratos[estacion])
    assert grupo(client)["estado"] == "en_proceso"
    assert grupo(client)["salida"] is None


def test_grupo_completo_sin_alertas_queda_ok(client, contratos):
    enviar(client, contratos["E1"])
    enviar(client, e4_sin_revision(contratos))
    assert grupo(client)["estado"] == "ok"
    assert grupo(client)["salida"] is not None


def test_grupo_con_alerta_queda_anomalia(client, contratos):
    # El contrato de E4 trae F3 con revisión manual, que genera una alerta
    for estacion in ["E1", "E2", "E3", "E4"]:
        enviar(client, contratos[estacion])
    assert grupo(client)["estado"] == "anomalia"


def test_grupo_con_fruta_rechazada_queda_rechazo(client, contratos):
    e4 = e4_sin_revision(contratos)
    e4["frutas"][0]["categoria_final"] = "rechazo"
    enviar(client, contratos["E1"])
    enviar(client, e4)
    assert grupo(client)["estado"] == "rechazo"


def test_e4_parcial_no_cierra_el_grupo(client, contratos):
    e4 = e4_sin_revision(contratos)
    e4["frutas"] = e4["frutas"][:2]
    enviar(client, contratos["E1"])
    enviar(client, e4)
    assert grupo(client)["estado"] == "en_proceso"
    assert grupo(client)["salida"] is None


def test_e4_antes_que_e1_cierra_cuando_llega_e1(client, contratos):
    enviar(client, e4_sin_revision(contratos))
    assert grupo(client)["estado"] == "en_proceso"

    enviar(client, contratos["E1"])
    assert grupo(client)["estado"] == "ok"
    assert grupo(client)["salida"] is not None


def test_salida_no_cambia_y_alerta_tardia_actualiza_el_estado(client, contratos):
    enviar(client, contratos["E1"])
    enviar(client, e4_sin_revision(contratos))
    salida = grupo(client)["salida"]

    e2 = copy.deepcopy(contratos["E2"])
    e2["frutas"][0]["confianza_visual"] = 0.5
    enviar(client, e2)
    assert grupo(client)["estado"] == "anomalia"
    assert grupo(client)["salida"] == salida


def test_duplicado_no_cambia_el_grupo(client, contratos):
    enviar(client, contratos["E1"])
    enviar(client, e4_sin_revision(contratos))
    antes = grupo(client)

    assert enviar(client, e4_sin_revision(contratos))["duplicado"] is True
    assert grupo(client) == antes


# ------------------------------------------------------------ estado de cinta

def test_estado_cinta_sin_e6_es_nulo(client):
    e6 = e6_de_estado(client)
    assert e6["estado_cinta"] is None
    assert e6["falla_mecanica_detectada"] is None


def test_estado_cinta_con_e6(client, contratos):
    enviar(client, contratos["E6"])
    e6 = e6_de_estado(client)
    assert e6["estado_cinta"] == "normal"
    assert e6["falla_mecanica_detectada"] is False


def test_estado_cinta_toma_el_ultimo_mensaje(client, contratos):
    enviar(client, contratos["E6"])
    falla = copy.deepcopy(contratos["E6"])
    falla["timestamp"] = "2026-11-18T10:17:25Z"
    falla["datos"]["estado_cinta"] = "falla_mecanica"
    falla["datos"]["falla_mecanica_detectada"] = True
    enviar(client, falla)

    e6 = e6_de_estado(client)
    assert e6["estado_cinta"] == "falla_mecanica"
    assert e6["falla_mecanica_detectada"] is True


def test_estado_cinta_solo_en_la_entrada_de_e6(client, contratos):
    enviar(client, contratos["E6"])
    for entrada in client.get("/api/v1/estaciones/estado").json():
        if entrada["estacion"] != "E6":
            assert "estado_cinta" not in entrada
            assert "falla_mecanica_detectada" not in entrada


def test_metricas_solo_cuenta_alertas_activas(client, contratos):
    enviar(client, contratos["E1"])
    enviar(client, contratos["E4"])

    metricas = client.get("/api/v1/metricas").json()
    assert metricas["anomalias_por_estacion"]["E4"] >= 1

    alertas = client.get("/api/v1/alertas?activas=true").json()
    alerta_e4 = next(a for a in alertas if a["estacion"] == "E4")
    respuesta = client.patch(f"/api/v1/alertas/{alerta_e4['id']}")
    assert respuesta.status_code == 200

    metricas = client.get("/api/v1/metricas").json()
    assert metricas["anomalias_por_estacion"]["E4"] == 0



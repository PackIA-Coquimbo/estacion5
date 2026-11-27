"""Cierre de mandarina al recibir E4 y consulta del estado E6."""

import copy


def ruta(estacion: str) -> str:
    return f"/api/v1/ingest/{estacion.lower()}"


def enviar(client, mensaje: dict) -> dict:
    respuesta = client.post(ruta(mensaje["estacion"]), json=mensaje)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def estado_fruta(client) -> dict:
    return client.get("/api/v1/frutas/M-0001").json()


def test_mandarina_sigue_en_proceso_hasta_e4(client, contratos):
    for estacion in ["E1", "E2", "E3"]:
        enviar(client, contratos[estacion])
    assert estado_fruta(client)["estado"] == "en_proceso"
    assert estado_fruta(client)["salida"] is None


def test_e4_cierra_mandarina_sin_alertas(client, contratos):
    for estacion in ["E1", "E2", "E3", "E4"]:
        enviar(client, contratos[estacion])
    assert estado_fruta(client)["estado"] == "ok"
    assert estado_fruta(client)["salida"] is not None


def test_alerta_activa_deja_mandarina_en_anomalia(client, contratos):
    e2 = copy.deepcopy(contratos["E2"])
    e2["datos"]["confianza_visual"] = 0.5
    for mensaje in [contratos["E1"], e2, contratos["E4"]]:
        enviar(client, mensaje)
    assert estado_fruta(client)["estado"] == "anomalia"


def test_categoria_rechazo_cierra_mandarina_como_rechazo(client, contratos):
    e4 = copy.deepcopy(contratos["E4"])
    e4["datos"]["categoria_final"] = "rechazo"
    enviar(client, e4)
    assert estado_fruta(client)["estado"] == "rechazo"
    assert estado_fruta(client)["salida"] is not None


def test_e4_antes_de_e1_cierra_al_llegar_la_primera_lectura(client, contratos):
    enviar(client, contratos["E4"])
    assert estado_fruta(client)["estado"] == "ok"
    enviar(client, contratos["E1"])
    assert estado_fruta(client)["estado"] == "ok"


def test_alerta_tardia_actualiza_estado_sin_cambiar_salida(client, contratos):
    enviar(client, contratos["E1"])
    enviar(client, contratos["E4"])
    salida = estado_fruta(client)["salida"]
    e2 = copy.deepcopy(contratos["E2"])
    e2["datos"]["confianza_visual"] = 0.5
    enviar(client, e2)
    assert estado_fruta(client)["estado"] == "anomalia"
    assert estado_fruta(client)["salida"] == salida


def test_duplicado_no_cambia_estado_ni_salida(client, contratos):
    enviar(client, contratos["E4"])
    antes = estado_fruta(client)
    assert enviar(client, contratos["E4"])["duplicado"] is True
    assert estado_fruta(client) == antes


def test_estado_cinta_nulo_sin_eventos(client):
    e6 = next(
        e
        for e in client.get("/api/v1/estaciones/estado").json()["estaciones"]
        if e["estacion"] == "E6"
    )
    assert e6["estado_cinta"] is None
    assert e6["falla_mecanica_detectada"] is None


def test_estado_cinta_toma_ultimo_evento(client, contratos):
    enviar(client, contratos["E6"])
    falla = copy.deepcopy(contratos["E6"])
    falla["timestamp"] = "2026-11-25T10:16:00Z"
    falla["datos"]["estado_cinta"] = "falla_mecanica"
    falla["datos"]["falla_mecanica_detectada"] = True
    enviar(client, falla)
    e6 = next(
        e
        for e in client.get("/api/v1/estaciones/estado").json()["estaciones"]
        if e["estacion"] == "E6"
    )
    assert e6["estado_cinta"] == "falla_mecanica"
    assert e6["estado"] == "falla"
    assert e6["falla_mecanica_detectada"] is True


def test_metricas_disminuyen_alertas_historicas_al_resolver(client, contratos):
    e4 = copy.deepcopy(contratos["E4"])
    e4["datos"]["requiere_revision_manual"] = True
    enviar(client, e4)
    alerta = client.get("/api/v1/alertas").json()["alertas"][0]
    client.patch(f"/api/v1/alertas/{alerta['id']}")
    assert client.get("/api/v1/alertas").json()["alertas"] == []

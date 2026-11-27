"""Persistencia, deduplicación y orden de llegada de lecturas v3."""

import copy

import pytest
from sqlalchemy import func, select

from app.models import Alerta, Fruta, Lectura, Lote
from conftest import ESTACIONES


def ruta(estacion: str) -> str:
    return f"/api/v1/ingest/{estacion.lower()}"


def contar(db, modelo) -> int:
    with db() as session:
        return session.scalar(select(func.count()).select_from(modelo))


def obtener_fruta(db, id_fruta: str) -> Fruta:
    with db() as session:
        fruta = session.get(Fruta, id_fruta)
        assert fruta is not None
        session.expunge(fruta)
        return fruta


def test_los_tests_no_usan_el_engine_real(client, engine_prueba):
    import app.db
    import app.main

    assert str(app.db.engine.url) == "sqlite://"
    assert app.main.SessionLocal.kw["bind"] is engine_prueba


def test_cada_test_parte_con_la_base_vacia(client, db):
    for modelo in (Lote, Fruta, Lectura, Alerta):
        assert contar(db, modelo) == 0, modelo.__tablename__


@pytest.mark.parametrize("estacion", ESTACIONES)
def test_mensaje_duplicado_no_crea_filas(client, db, contratos, estacion):
    primera = client.post(ruta(estacion), json=contratos[estacion])
    assert primera.status_code == 201, primera.text
    assert primera.json()["duplicado"] is False
    lecturas = contar(db, Lectura)
    frutas = contar(db, Fruta)

    segunda = client.post(ruta(estacion), json=contratos[estacion])
    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["duplicado"] is True
    assert segunda.json()["lectura_id"] == primera.json()["lectura_id"]
    assert contar(db, Lectura) == lecturas
    assert contar(db, Fruta) == frutas


def test_reenvio_con_otro_timestamp_actualiza_la_fruta(client, db, contratos):
    assert client.post(ruta("E3"), json=contratos["E3"]).status_code == 201
    reenvio = copy.deepcopy(contratos["E3"])
    reenvio["timestamp"] = "2026-11-25T10:15:50Z"
    reenvio["datos"]["diametro_mm"] = 65

    respuesta = client.post(ruta("E3"), json=reenvio)
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["duplicado"] is False
    assert contar(db, Lectura) == 2
    assert contar(db, Fruta) == 1
    assert obtener_fruta(db, "M-0001").e3_diametro_mm == 65


def test_e3_antes_que_e1_crea_lote_y_mandarina(client, db, contratos):
    respuesta = client.post(ruta("E3"), json=contratos["E3"])
    assert respuesta.status_code == 201, respuesta.text
    fruta = obtener_fruta(db, "M-0001")
    assert fruta.id_lote == "LOTE-2026-11-A"
    assert fruta.e3_diametro_mm == 64
    assert fruta.e3_tamano == "mediano"
    assert contar(db, Lote) == 1

    assert client.post(ruta("E1"), json=contratos["E1"]).status_code == 201
    fruta = obtener_fruta(db, "M-0001")
    assert fruta.e1_estado_captura == "aceptada"
    assert contar(db, Fruta) == 1


def test_orden_inverso_consolida_una_fila_por_mandarina(client, db, contratos):
    for estacion in ["E6", "E4", "E3", "E2", "E1"]:
        respuesta = client.post(ruta(estacion), json=contratos[estacion])
        assert respuesta.status_code == 201, respuesta.text

    fruta = obtener_fruta(db, "M-0001")
    assert fruta.e1_validez_imagen is True
    assert fruta.e2_calidad_visual == "alta"
    assert fruta.e3_diametro_mm == 64
    assert fruta.e4_categoria_final == "exportacion"
    assert fruta.estado == "ok"
    assert fruta.salida is not None
    assert contar(db, Fruta) == 1
    assert contar(db, Lectura) == 5


def test_mismo_id_fruta_no_se_asocia_a_dos_lotes(client, contratos):
    assert client.post(ruta("E1"), json=contratos["E1"]).status_code == 201
    segundo_lote = copy.deepcopy(contratos["E2"])
    segundo_lote["id_lote"] = "LOTE-OTRO"
    assert client.post(ruta("E2"), json=segundo_lote).status_code == 409


def test_e4_antes_de_e1_cierra_al_llegar_el_mensaje(client, db, contratos):
    assert client.post(ruta("E4"), json=contratos["E4"]).status_code == 201
    fruta = obtener_fruta(db, "M-0001")
    assert fruta.estado == "ok"
    assert fruta.salida is not None

    assert client.post(ruta("E1"), json=contratos["E1"]).status_code == 201
    assert obtener_fruta(db, "M-0001").estado == "ok"

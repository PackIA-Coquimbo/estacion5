"""Tests de persistencia: duplicados, mensajes en desorden y base de prueba.

- Un mensaje repetido (mismo contenido) responde "duplicado": true y no crea
  filas nuevas en Lectura ni en Fruta.
- Un mensaje que llega antes que el de E1 (por ejemplo E3) igual crea el
  lote, el grupo y las frutas.
"""

import copy

import pytest
from sqlalchemy import func, select

from app.models import Alerta, Fruta, Grupo, Lectura, Lote
from conftest import ESTACIONES


def ruta(estacion: str) -> str:
    return f"/api/v1/ingest/{estacion.lower()}"


def contar(db, modelo) -> int:
    with db() as sesion:
        return sesion.scalar(select(func.count()).select_from(modelo))


def frutas_del_grupo(db, id_grupo: str) -> dict[str, Fruta]:
    with db() as sesion:
        filas = sesion.scalars(select(Fruta).where(Fruta.id_grupo == id_grupo)).all()
    return {fruta.id_fruta: fruta for fruta in filas}


# ------------------------------------------------------------ base de prueba

def test_los_tests_no_usan_el_engine_real(client, engine_prueba):
    import app.db
    import app.main

    assert str(app.db.engine.url) == "sqlite://"
    assert app.main.SessionLocal.kw["bind"] is engine_prueba


def test_cada_test_parte_con_la_base_vacia(client, db):
    for modelo in (Lote, Grupo, Fruta, Lectura, Alerta):
        assert contar(db, modelo) == 0, modelo.__tablename__


# ---------------------------------------------------------------- duplicados

@pytest.mark.parametrize("estacion", ESTACIONES)
def test_mensaje_duplicado_no_crea_filas(client, db, contratos, estacion):
    primera = client.post(ruta(estacion), json=contratos[estacion])
    assert primera.status_code == 201, primera.text
    assert primera.json()["duplicado"] is False
    lecturas, frutas = contar(db, Lectura), contar(db, Fruta)

    segunda = client.post(ruta(estacion), json=contratos[estacion])
    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["duplicado"] is True
    assert segunda.json()["lectura_id"] == primera.json()["lectura_id"]
    assert contar(db, Lectura) == lecturas == 1
    assert contar(db, Fruta) == frutas


def test_e3_duplicado_mantiene_las_tres_frutas(client, db, contratos):
    for _ in range(3):
        client.post(ruta("E3"), json=contratos["E3"])
    assert contar(db, Lectura) == 1
    assert contar(db, Fruta) == 3


def test_reenvio_con_otro_timestamp_actualiza_frutas_sin_duplicarlas(client, db, contratos):
    client.post(ruta("E3"), json=contratos["E3"])
    reenvio = copy.deepcopy(contratos["E3"])
    reenvio["timestamp"] = "2026-11-18T10:16:45Z"
    reenvio["frutas"][0]["diametro_mm"] = 41

    respuesta = client.post(ruta("E3"), json=reenvio)
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["duplicado"] is False
    assert contar(db, Lectura) == 2
    assert contar(db, Fruta) == 3
    assert frutas_del_grupo(db, "G-0001")["F1"].e3_diametro_mm == 41


# ------------------------------------------------------------------ desorden

def test_e3_antes_que_e1_crea_el_grupo_y_guarda_las_frutas(client, db, contratos):
    respuesta = client.post(ruta("E3"), json=contratos["E3"])
    assert respuesta.status_code == 201, respuesta.text

    with db() as sesion:
        grupo = sesion.get(Grupo, "G-0001")
        assert sesion.get(Lote, "LOTE-2026-11-A") is not None
    assert grupo is not None
    assert grupo.id_lote == "LOTE-2026-11-A"
    assert grupo.frutas_detectadas is None  # E1 todavía no llega

    frutas = frutas_del_grupo(db, "G-0001")
    esperado = {f["id_fruta"]: f for f in contratos["E3"]["frutas"]}
    assert set(frutas) == set(esperado)
    for id_fruta, fruta in frutas.items():
        assert fruta.e3_diametro_mm == esperado[id_fruta]["diametro_mm"]
        assert fruta.e3_tamano == esperado[id_fruta]["tamano"]

    # Cuando llega E1, completa el grupo sin duplicar nada
    assert client.post(ruta("E1"), json=contratos["E1"]).status_code == 201
    with db() as sesion:
        grupo = sesion.get(Grupo, "G-0001")
    assert grupo.frutas_detectadas == contratos["E1"]["datos"]["frutas_detectadas"]
    assert contar(db, Grupo) == 1
    assert contar(db, Fruta) == 3


def test_orden_inverso_completa_todas_las_columnas(client, db, contratos):
    for estacion in ["E6", "E4", "E3", "E2", "E1"]:
        respuesta = client.post(ruta(estacion), json=contratos[estacion])
        assert respuesta.status_code == 201, respuesta.text

    assert contar(db, Grupo) == 1
    assert contar(db, Lectura) == 5
    frutas = frutas_del_grupo(db, "G-0001")
    assert len(frutas) == 3
    for fruta in frutas.values():
        assert fruta.e2_calidad_visual is not None
        assert fruta.e3_diametro_mm is not None
        assert fruta.e4_categoria_final is not None

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Fruta, Lote
from app.prediccion import entrenar_pronostico
from tools import entrenar_modelo


def historial():
    return [
        {"frutas_clasificadas": 100, "rechazadas": 10 + 2 * indice}
        for indice in range(24)
    ]


def test_entrenamiento_calcula_metricas_sobre_el_tramo_temporal_final():
    modelo = entrenar_pronostico(historial())
    assert modelo["algoritmo"] == "regresion_lineal_autoregresiva_ar1"
    assert modelo["horas_entrenamiento"] == 24
    assert modelo["horas_evaluacion"] == 5
    assert modelo["metricas"]["frutas_por_hora"]["mae"] == 0
    assert modelo["metricas"]["frutas_por_hora"]["rmse"] == 0
    assert modelo["metricas"]["frutas_por_hora"]["r2"] is None
    assert modelo["pronostico_siguiente_hora"]["frutas_por_hora"] == 100
    assert modelo["pronostico_siguiente_hora"]["porcentaje_rechazo"] == 58


def test_entrenamiento_requiere_24_horas():
    with pytest.raises(ValueError, match="al menos 24 horas"):
        entrenar_pronostico(historial()[:23])


def test_entrenamiento_rechaza_conteos_invalidos():
    datos = historial()
    datos[0]["rechazadas"] = datos[0]["frutas_clasificadas"] + 1
    with pytest.raises(ValueError, match="Conteos inválidos"):
        entrenar_pronostico(datos)


def test_entrenamiento_lee_metricas_horarias_de_la_base_e5(
    db, tmp_path, monkeypatch
):
    desde = datetime(2026, 11, 25, 10, tzinfo=timezone.utc)
    with db() as session:
        session.add(Lote(id_lote="LOTE-TEST"))
        session.flush()
        session.add_all(
            [
                Fruta(
                    id_fruta="M-0001",
                    id_lote="LOTE-TEST",
                    e4_categoria_final="rechazo",
                    salida=desde + timedelta(minutes=1),
                ),
                Fruta(
                    id_fruta="M-0002",
                    id_lote="LOTE-TEST",
                    e4_categoria_final="exportacion",
                    salida=desde + timedelta(minutes=2),
                ),
                Fruta(
                    id_fruta="M-0003",
                    id_lote="LOTE-TEST",
                    e4_categoria_final="mercado_nacional",
                    salida=desde + timedelta(hours=2),
                ),
            ]
        )
        session.commit()

    ruta_db = tmp_path / "e5.db"
    ruta_db.touch()
    monkeypatch.setattr(entrenar_modelo, "DATABASE_PATH", ruta_db)
    monkeypatch.setattr(entrenar_modelo, "SessionLocal", db)

    assert entrenar_modelo.cargar_horas() == [
        {"frutas_clasificadas": 2, "rechazadas": 1},
        {"frutas_clasificadas": 0, "rechazadas": 0},
        {"frutas_clasificadas": 1, "rechazadas": 0},
    ]


def test_endpoint_informa_que_no_hay_modelo_entrenado(client, tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(
        main, "MODELO_PREDICCION_PATH", tmp_path / "modelo.json"
    )
    respuesta = client.get("/api/v1/predicciones")
    assert respuesta.status_code == 503
    assert "historial real" in respuesta.json()["detail"]


def test_endpoint_devuelve_el_modelo_entrenado(client, tmp_path, monkeypatch):
    import app.main as main

    ruta = tmp_path / "modelo.json"
    esperado = entrenar_pronostico(historial())
    ruta.write_text(json.dumps(esperado), encoding="utf-8")
    monkeypatch.setattr(main, "MODELO_PREDICCION_PATH", ruta)
    assert client.get("/api/v1/predicciones").json() == esperado

from datetime import datetime, timezone
from math import isfinite, sqrt
from typing import Iterable


def _ajustar(pares: list[tuple[float, float]]) -> dict[str, float]:
    xs = [x for x, _ in pares]
    ys = [y for _, y in pares]
    media_x = sum(xs) / len(xs)
    media_y = sum(ys) / len(ys)
    varianza_x = sum((x - media_x) ** 2 for x in xs)
    pendiente = (
        sum((x - media_x) * (y - media_y) for x, y in pares) / varianza_x
        if varianza_x
        else 0.0
    )
    return {
        "intercepto": media_y - pendiente * media_x,
        "pendiente": pendiente,
    }


def _predecir(modelo: dict[str, float], valor: float) -> float:
    return modelo["intercepto"] + modelo["pendiente"] * valor


def _evaluar(
    pares: list[tuple[float, float]], modelo: dict[str, float]
) -> dict[str, float | None]:
    reales = [real for _, real in pares]
    estimados = [_predecir(modelo, entrada) for entrada, _ in pares]
    errores = [real - estimado for real, estimado in zip(reales, estimados)]
    mae = sum(abs(error) for error in errores) / len(errores)
    rmse = sqrt(sum(error**2 for error in errores) / len(errores))
    media = sum(reales) / len(reales)
    suma_total = sum((real - media) ** 2 for real in reales)
    r2 = (
        1 - sum(error**2 for error in errores) / suma_total
        if suma_total
        else None
    )
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4) if r2 is not None else None,
    }


def entrenar_pronostico(
    filas: Iterable[dict[str, int]],
    *,
    entrenado_en: datetime | None = None,
) -> dict:
    """Entrena un baseline AR(1) y evalúa su último tramo cronológico."""
    datos = list(filas)
    if len(datos) < 24:
        raise ValueError("Se requieren al menos 24 horas históricas para entrenar")

    volumen = []
    rechazo = []
    for indice, fila in enumerate(datos):
        clasificada = fila["frutas_clasificadas"]
        rechazadas = fila["rechazadas"]
        if (
            isinstance(clasificada, bool)
            or isinstance(rechazadas, bool)
            or not isinstance(clasificada, int)
            or not isinstance(rechazadas, int)
            or not isfinite(clasificada)
            or not isfinite(rechazadas)
            or clasificada < 0
            or rechazadas < 0
            or rechazadas > clasificada
        ):
            raise ValueError(f"Conteos inválidos en la hora {indice}")
        volumen.append(float(clasificada))
        rechazo.append(
            float(rechazadas * 100 / clasificada) if clasificada else 0.0
        )

    series = {
        "frutas_por_hora": volumen,
        "porcentaje_rechazo": rechazo,
    }
    modelos = {}
    metricas = {}
    pronostico = {}
    for nombre, valores in series.items():
        pares = list(zip(valores[:-1], valores[1:]))
        corte = max(4, int(len(pares) * 0.8))
        if len(pares) - corte < 2:
            corte = len(pares) - 2
        modelo_validacion = _ajustar(pares[:corte])
        modelo_final = _ajustar(pares)
        metricas[nombre] = _evaluar(pares[corte:], modelo_validacion)
        modelos[nombre] = modelo_final
        valor = max(0.0, _predecir(modelo_final, valores[-1]))
        if nombre == "porcentaje_rechazo":
            valor = min(100.0, valor)
        pronostico[nombre] = round(valor, 2)

    instante = entrenado_en or datetime.now(timezone.utc)
    if instante.tzinfo is None:
        raise ValueError("entrenado_en debe incluir zona horaria")
    return {
        "version": 1,
        "algoritmo": "regresion_lineal_autoregresiva_ar1",
        "entrenado_en": instante.astimezone(timezone.utc).isoformat(),
        "horas_entrenamiento": len(datos),
        "horas_evaluacion": len(datos) - 1 - max(4, int((len(datos) - 1) * 0.8)),
        "metricas": metricas,
        "modelos": modelos,
        "pronostico_siguiente_hora": pronostico,
    }

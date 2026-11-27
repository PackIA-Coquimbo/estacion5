import os


CONFIANZA_MINIMA = 0.70
VENTANA_CONFIANZA = 12
MINIMO_BAJAS_TENDENCIA = 3
SEGUNDOS_SIN_SENAL = 30
INTERVALO_REVISION_SENAL = 5
ALMACENAMIENTO_ALERTA_PORCENTAJE = 80
ESTACIONES = ("E1", "E2", "E3", "E4", "E6")
CORS_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://192.168.0.10:8000",
    ).split(",")
    if origin.strip()
)

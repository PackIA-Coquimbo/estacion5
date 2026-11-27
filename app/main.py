import asyncio
import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import (
    ALMACENAMIENTO_ALERTA_PORCENTAJE,
    CORS_ORIGINS,
    ESTACIONES,
    INTERVALO_REVISION_SENAL,
    SEGUNDOS_SIN_SENAL,
    VENTANA_CONFIANZA,
)
from app.db import DATABASE_PATH, SessionLocal, crear_tablas, get_db
from app.models import Alerta, EventoCinta, Fruta, Lectura, Lote
from app.reglas import AlertaEvaluada, evaluar, evaluar_sin_senal
from app.schemas import E1Payload, E2Payload, E3Payload, E4Payload, E6Payload


logger = logging.getLogger(__name__)
PayloadIngesta = E1Payload | E2Payload | E3Payload | E4Payload | E6Payload
MODELO_PREDICCION_PATH = Path(
    os.getenv(
        "E5_MODELO_PREDICCION",
        str(DATABASE_PATH.parent / "modelo_metricas.json"),
    )
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    crear_tablas()
    monitor = asyncio.create_task(_monitor_senales())
    try:
        yield
    finally:
        monitor.cancel()
        try:
            await monitor
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="API de Supervisión y Trazabilidad - Estación 5",
    description="Ingesta y consulta de datos por mandarina para las estaciones PackIA.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


def _insertar(tabla, valores: dict[str, Any], session: Session):
    dialect = session.get_bind().dialect.name
    tabla = getattr(tabla, "__table__", tabla)
    if dialect == "sqlite":
        return sqlite_insert(tabla).values(**valores)
    if dialect == "postgresql":
        return postgresql_insert(tabla).values(**valores)
    raise RuntimeError(f"Motor de base de datos no soportado: {dialect}")


def _respuesta_duplicada(lectura: Lectura) -> dict:
    return {
        "status": "success",
        "estacion": lectura.estacion,
        "id_lote": lectura.id_lote,
        "id_fruta": lectura.id_fruta,
        "lectura_id": lectura.id,
        "duplicado": True,
    }


def _obtener_o_crear_lote(session: Session, id_lote: str) -> Lote:
    lote = session.get(Lote, id_lote)
    if lote is None:
        lote = Lote(id_lote=id_lote)
        session.add(lote)
        session.flush()
    return lote


def _obtener_o_crear_fruta(
    session: Session, id_fruta: str, id_lote: str, timestamp: datetime
) -> Fruta:
    fruta = session.get(Fruta, id_fruta)
    if fruta is not None and fruta.id_lote != id_lote:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El id_fruta ya está asociado a otro lote",
        )
    if fruta is None:
        fruta = Fruta(id_fruta=id_fruta, id_lote=id_lote, ingreso=timestamp)
        session.add(fruta)
        session.flush()
    elif timestamp < fruta.ingreso:
        fruta.ingreso = timestamp
    return fruta


def _actualizar_fruta(fruta: Fruta, payload: PayloadIngesta) -> None:
    if isinstance(payload, E1Payload):
        fruta.e1_validez_imagen = payload.datos.validez_imagen
        fruta.e1_estado_captura = payload.datos.estado_captura
        fruta.e1_posicion_correcta = payload.datos.posicion_correcta
    elif isinstance(payload, E2Payload):
        fruta.e2_calidad_visual = payload.datos.calidad_visual
        fruta.e2_confianza_visual = payload.datos.confianza_visual
        fruta.e2_defectos = payload.datos.defectos_detectados
    elif isinstance(payload, E3Payload):
        fruta.e3_diametro_mm = payload.datos.diametro_mm
        fruta.e3_tamano = payload.datos.tamano
    elif isinstance(payload, E4Payload):
        fruta.e4_categoria_final = payload.datos.categoria_final
        fruta.e4_probabilidad = payload.datos.probabilidad
        fruta.e4_revision_manual = payload.datos.requiere_revision_manual


def _confianzas_recientes(session: Session, payload_hash: str) -> list[float]:
    lecturas = session.scalars(
        select(Lectura)
        .where(
            Lectura.estacion == "E2",
            Lectura.payload_hash != payload_hash,
        )
        .order_by(Lectura.ts_recepcion.desc(), Lectura.id.desc())
        .limit(VENTANA_CONFIANZA - 1)
    ).all()
    return [
        lectura.payload["datos"]["confianza_visual"]
        for lectura in lecturas
        if "confianza_visual" in lectura.payload.get("datos", {})
    ]


def _registrar_alertas(
    session: Session,
    id_lote: str,
    alertas: list[AlertaEvaluada],
) -> None:
    for alerta in alertas:
        dedupe_source = (
            f"{alerta.codigo}|{id_lote}|{alerta.id_fruta or ''}"
        )
        dedupe_key = hashlib.sha256(dedupe_source.encode("utf-8")).hexdigest()
        activa = session.scalar(
            select(Alerta.id).where(
                Alerta.dedupe_key == dedupe_key,
                Alerta.resuelta.is_(False),
            )
        )
        if activa is None:
            session.add(
                Alerta(
                    id_lote=id_lote,
                    id_fruta=alerta.id_fruta,
                    estacion=alerta.estacion,
                    severidad=alerta.severidad,
                    mensaje=alerta.mensaje,
                    dedupe_key=dedupe_key,
                )
            )


def _registrar_alertas_sin_senal(session: Session) -> None:
    evento_cinta = session.scalar(
        select(EventoCinta)
        .join(Lectura, EventoCinta.lectura_id == Lectura.id)
        .order_by(Lectura.ts_recepcion.desc(), EventoCinta.id.desc())
        .limit(1)
    )
    if evento_cinta is None:
        return

    lectura_cinta = session.get(Lectura, evento_cinta.lectura_id)
    if lectura_cinta is None:
        raise RuntimeError("El evento de cinta no tiene una lectura asociada")

    ultimas_lecturas = {}
    for estacion in ESTACIONES:
        lectura = session.scalar(
            select(Lectura)
            .where(Lectura.estacion == estacion)
            .order_by(Lectura.ts_recepcion.desc(), Lectura.id.desc())
            .limit(1)
        )
        if lectura is not None:
            ultimas_lecturas[estacion] = lectura

    alertas = evaluar_sin_senal(
        {
            estacion: lectura.ts_recepcion
            for estacion, lectura in ultimas_lecturas.items()
        },
        cinta_en_marcha=(
            evento_cinta.estado_cinta == "normal" and not evento_cinta.falla_mecanica
        ),
        inicio_marcha=lectura_cinta.ts_recepcion,
        ahora=datetime.now(timezone.utc),
        segundos_sin_senal=SEGUNDOS_SIN_SENAL,
    )
    for alerta in alertas:
        lectura = ultimas_lecturas.get(alerta.estacion)
        id_lote = lectura.id_lote if lectura is not None else evento_cinta.id_lote
        _registrar_alertas(session, id_lote, [alerta])


def _evaluar_y_registrar_alertas(
    session: Session, payload: PayloadIngesta, payload_hash: str
) -> None:
    confianza_reciente = (
        _confianzas_recientes(session, payload_hash)
        if isinstance(payload, E2Payload)
        else ()
    )
    _registrar_alertas(
        session,
        payload.id_lote,
        evaluar(payload, confianza_reciente=confianza_reciente),
    )
    _registrar_alertas_sin_senal(session)


def _cerrar_fruta_si_clasificada(session: Session, id_fruta: str | None) -> None:
    if id_fruta is None:
        return
    fruta = session.get(Fruta, id_fruta)
    if fruta is None or fruta.e4_categoria_final is None:
        return

    lectura_e4 = session.scalar(
        select(Lectura)
        .where(Lectura.id_fruta == id_fruta, Lectura.estacion == "E4")
        .order_by(Lectura.ts_estacion, Lectura.id)
        .limit(1)
    )
    if lectura_e4 is None:
        raise RuntimeError("La fruta clasificada no tiene lectura E4 asociada")

    fruta.salida = lectura_e4.ts_estacion
    if fruta.e4_categoria_final == "rechazo":
        fruta.estado = "rechazo"
    elif session.scalar(
        select(Alerta.id).where(Alerta.id_fruta == id_fruta).limit(1)
    ) is not None:
        fruta.estado = "anomalia"
    else:
        fruta.estado = "ok"


def _revisar_senales() -> None:
    with SessionLocal() as session:
        try:
            _registrar_alertas_sin_senal(session)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise


async def _monitor_senales() -> None:
    while True:
        try:
            await asyncio.to_thread(_revisar_senales)
        except SQLAlchemyError:
            logger.exception("No se pudo revisar el estado de señal de las estaciones")
        await asyncio.sleep(INTERVALO_REVISION_SENAL)


def _guardar_lectura(session: Session, payload: PayloadIngesta) -> dict:
    datos = payload.model_dump(mode="json")
    json_canonico = json.dumps(
        datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    payload_hash = hashlib.sha256(json_canonico.encode("utf-8")).hexdigest()

    existente = session.scalar(
        select(Lectura).where(Lectura.payload_hash == payload_hash)
    )
    if existente is not None:
        return _respuesta_duplicada(existente)

    _obtener_o_crear_lote(session, payload.id_lote)
    id_fruta = getattr(payload, "id_fruta", None)
    fruta = (
        _obtener_o_crear_fruta(
            session, id_fruta, payload.id_lote, payload.timestamp
        )
        if id_fruta is not None
        else None
    )
    lectura_values = {
        "id_lote": payload.id_lote,
        "id_fruta": id_fruta,
        "estacion": payload.estacion,
        "ts_estacion": payload.timestamp,
        "payload": datos,
        "payload_hash": payload_hash,
    }
    insert = _insertar(Lectura, lectura_values, session)
    inserted = session.execute(
        insert.on_conflict_do_nothing(index_elements=["payload_hash"])
    )
    if inserted.rowcount == 0:
        session.rollback()
        existente = session.scalar(
            select(Lectura).where(Lectura.payload_hash == payload_hash)
        )
        if existente is None:
            raise RuntimeError("No se encontró la lectura duplicada tras el conflicto")
        return _respuesta_duplicada(existente)

    lectura = session.scalar(
        select(Lectura).where(Lectura.payload_hash == payload_hash)
    )
    if lectura is None:
        raise RuntimeError("No se pudo recuperar la lectura recién insertada")

    if fruta is not None:
        _actualizar_fruta(fruta, payload)

    if isinstance(payload, E6Payload):
        session.add(
            EventoCinta(
                id_lote=payload.id_lote,
                lectura_id=lectura.id,
                estado_cinta=payload.datos.estado_cinta,
                falla_mecanica=payload.datos.falla_mecanica_detectada,
                id_fruta_en_cinta=payload.datos.id_fruta_en_cinta,
                ts=payload.timestamp,
            )
        )

    try:
        session.flush()
        _evaluar_y_registrar_alertas(session, payload, payload_hash)
        session.flush()
        _cerrar_fruta_si_clasificada(session, id_fruta)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("No se pudo guardar una lectura de %s", payload.estacion)
        raise

    return {
        "status": "success",
        "estacion": payload.estacion,
        "id_lote": payload.id_lote,
        "id_fruta": id_fruta,
        "lectura_id": lectura.id,
        "duplicado": False,
    }


@app.post("/api/v1/ingest/e1", status_code=status.HTTP_201_CREATED, tags=["Ingesta"])
def ingest_e1(payload: E1Payload, session: Session = Depends(get_db)):
    return _guardar_lectura(session, payload)


@app.post("/api/v1/ingest/e2", status_code=status.HTTP_201_CREATED, tags=["Ingesta"])
def ingest_e2(payload: E2Payload, session: Session = Depends(get_db)):
    return _guardar_lectura(session, payload)


@app.post("/api/v1/ingest/e3", status_code=status.HTTP_201_CREATED, tags=["Ingesta"])
def ingest_e3(payload: E3Payload, session: Session = Depends(get_db)):
    return _guardar_lectura(session, payload)


@app.post("/api/v1/ingest/e4", status_code=status.HTTP_201_CREATED, tags=["Ingesta"])
def ingest_e4(payload: E4Payload, session: Session = Depends(get_db)):
    return _guardar_lectura(session, payload)


@app.post("/api/v1/ingest/e6", status_code=status.HTTP_201_CREATED, tags=["Ingesta"])
def ingest_e6(payload: E6Payload, session: Session = Depends(get_db)):
    return _guardar_lectura(session, payload)


def _alerta_a_dict(alerta: Alerta) -> dict:
    return {
        "id": alerta.id,
        "id_lote": alerta.id_lote,
        "id_fruta": alerta.id_fruta,
        "severidad": alerta.severidad,
        "estacion": alerta.estacion,
        "mensaje": alerta.mensaje,
        "creada_en": alerta.creado_en,
        "resuelta": alerta.resuelta,
    }


def _fruta_a_dict(session: Session, fruta: Fruta) -> dict:
    alertas = session.scalars(
        select(Alerta).where(Alerta.id_fruta == fruta.id_fruta)
    ).all()
    return {
        "id_fruta": fruta.id_fruta,
        "estado": fruta.estado,
        "ingreso": fruta.ingreso,
        "salida": fruta.salida,
        "calidad_visual": fruta.e2_calidad_visual,
        "confianza_visual": fruta.e2_confianza_visual,
        "defectos_detectados": fruta.e2_defectos or [],
        "diametro_mm": fruta.e3_diametro_mm,
        "tamano": fruta.e3_tamano,
        "categoria_final": fruta.e4_categoria_final,
        "probabilidad": fruta.e4_probabilidad,
        "alertas": len(alertas),
    }


@app.get("/api/v1/lotes", tags=["Consultas"])
def listar_lotes(session: Session = Depends(get_db)):
    lotes = session.scalars(select(Lote).order_by(Lote.creado_en.desc())).all()
    return [
        {
            "id_lote": lote.id_lote,
            "creado_en": lote.creado_en,
            "estado": lote.estado,
            "total_frutas": session.scalar(
                select(func.count(Fruta.id_fruta)).where(Fruta.id_lote == lote.id_lote)
            ),
        }
        for lote in lotes
    ]


@app.get("/api/v1/lotes/{id_lote}/frutas", tags=["Consultas"])
def listar_frutas(
    id_lote: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
):
    if session.get(Lote, id_lote) is None:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    frutas = session.scalars(
        select(Fruta)
        .where(Fruta.id_lote == id_lote)
        .order_by(Fruta.ingreso.desc(), Fruta.id_fruta)
        .limit(limit)
    ).all()
    total = session.scalar(
        select(func.count(Fruta.id_fruta)).where(Fruta.id_lote == id_lote)
    )
    return {
        "id_lote": id_lote,
        "total_frutas": total,
        "frutas": [_fruta_a_dict(session, fruta) for fruta in frutas],
    }


@app.get("/api/v1/frutas/{id_fruta}", tags=["Consultas"])
def obtener_trazabilidad_fruta(id_fruta: str, session: Session = Depends(get_db)):
    fruta = session.get(Fruta, id_fruta)
    if fruta is None:
        raise HTTPException(status_code=404, detail="Fruta no encontrada")

    lecturas = {
        lectura.estacion: lectura
        for lectura in session.scalars(
            select(Lectura)
            .where(Lectura.id_fruta == id_fruta)
            .order_by(Lectura.ts_estacion, Lectura.id)
        ).all()
    }
    alertas = session.scalars(
        select(Alerta)
        .where(Alerta.id_fruta == id_fruta)
        .order_by(Alerta.creado_en.desc(), Alerta.id.desc())
    ).all()
    return {
        "id_lote": fruta.id_lote,
        "id_fruta": fruta.id_fruta,
        "estado": fruta.estado,
        "ingreso": fruta.ingreso,
        "salida": fruta.salida,
        "e1": (
            {
                "timestamp": lecturas["E1"].ts_estacion,
                "validez_imagen": fruta.e1_validez_imagen,
                "estado_captura": fruta.e1_estado_captura,
                "posicion_correcta": fruta.e1_posicion_correcta,
            }
            if "E1" in lecturas
            else None
        ),
        "e2": (
            {
                "timestamp": lecturas["E2"].ts_estacion,
                "calidad_visual": fruta.e2_calidad_visual,
                "confianza_visual": fruta.e2_confianza_visual,
                "defectos_detectados": fruta.e2_defectos or [],
            }
            if "E2" in lecturas
            else None
        ),
        "e3": (
            {
                "timestamp": lecturas["E3"].ts_estacion,
                "diametro_mm": fruta.e3_diametro_mm,
                "tamano": fruta.e3_tamano,
            }
            if "E3" in lecturas
            else None
        ),
        "e4": (
            {
                "timestamp": lecturas["E4"].ts_estacion,
                "categoria_final": fruta.e4_categoria_final,
                "probabilidad": fruta.e4_probabilidad,
                "requiere_revision_manual": fruta.e4_revision_manual,
            }
            if "E4" in lecturas
            else None
        ),
        "alertas": [_alerta_a_dict(alerta) for alerta in alertas],
    }


@app.get("/api/v1/metricas", tags=["Consultas"])
def obtener_metricas(
    lote: str | None = None, session: Session = Depends(get_db)
):
    if lote is not None and session.get(Lote, lote) is None:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    ahora = datetime.now(timezone.utc)
    inicio_turno = (
        ahora.astimezone()
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
    )
    consulta_frutas = select(Fruta)
    consulta_alertas = select(func.count(Alerta.id)).where(
        Alerta.creado_en >= ahora - timedelta(hours=1)
    )
    if lote is not None:
        consulta_frutas = consulta_frutas.where(Fruta.id_lote == lote)
        consulta_alertas = consulta_alertas.where(Alerta.id_lote == lote)

    frutas = session.scalars(consulta_frutas).all()
    clasificadas = [
        fruta
        for fruta in frutas
        if fruta.e4_categoria_final is not None and fruta.salida is not None
    ]
    por_categoria = {
        "exportacion": 0,
        "mercado_nacional": 0,
        "proceso": 0,
        "rechazo": 0,
        "revision_manual": 0,
    }
    por_tamano = {"pequeno": 0, "mediano": 0, "grande": 0}
    for fruta in frutas:
        if fruta.e3_tamano is not None:
            por_tamano[fruta.e3_tamano] += 1
    for fruta in clasificadas:
        por_categoria[fruta.e4_categoria_final] += 1

    ultima_hora = ahora - timedelta(hours=1)
    frutas_por_hora = {}
    for fruta in clasificadas:
        hora = fruta.salida.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        clave = hora.isoformat().replace("+00:00", "Z")
        frutas_por_hora[clave] = frutas_por_hora.get(clave, 0) + 1

    alertas_ultima_hora = session.scalar(consulta_alertas) or 0
    turno = [fruta for fruta in clasificadas if fruta.salida >= inicio_turno]
    recientes = [fruta for fruta in clasificadas if fruta.salida >= ultima_hora]
    rechazadas = por_categoria["rechazo"]

    return {
        "id_lote": lote,
        "desde": inicio_turno,
        "hasta": ahora,
        "frutas_turno": len(turno),
        "frutas_ultima_hora": len(recientes),
        "rechazadas": rechazadas,
        "porcentaje_rechazo": (
            round(rechazadas * 100 / len(clasificadas), 2)
            if clasificadas
            else 0.0
        ),
        "alertas_ultima_hora": alertas_ultima_hora,
        "por_categoria": por_categoria,
        "por_tamano": por_tamano,
        "frutas_por_hora": [
            {"hora": hora, "cantidad": cantidad}
            for hora, cantidad in sorted(frutas_por_hora.items())
        ],
    }


@app.get("/api/v1/alertas", tags=["Alertas"])
def listar_alertas(
    activas: bool = True, session: Session = Depends(get_db)
):
    consulta = select(Alerta)
    if activas:
        consulta = consulta.where(Alerta.resuelta.is_(False))
    alertas = session.scalars(
        consulta.order_by(Alerta.creado_en.desc(), Alerta.id.desc())
    ).all()
    return {"alertas": [_alerta_a_dict(alerta) for alerta in alertas]}


@app.patch("/api/v1/alertas/{id_alerta}", tags=["Alertas"])
def resolver_alerta(id_alerta: int, session: Session = Depends(get_db)):
    alerta = session.get(Alerta, id_alerta)
    if alerta is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    if not alerta.resuelta:
        alerta.resuelta = True
        alerta.dedupe_key = f"{alerta.dedupe_key}:resuelta:{alerta.id}"
        try:
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("No se pudo resolver la alerta %s", id_alerta)
            raise
    return _alerta_a_dict(alerta)


@app.get("/api/v1/estaciones/estado", tags=["Estado"])
def obtener_estado_estaciones(session: Session = Depends(get_db)):
    ahora = datetime.now(timezone.utc)
    id_lote = session.scalar(
        select(Lote.id_lote).order_by(Lote.creado_en.desc()).limit(1)
    )
    estado = []
    for estacion in ESTACIONES:
        lectura = session.scalar(
            select(Lectura)
            .where(Lectura.estacion == estacion)
            .order_by(Lectura.ts_recepcion.desc(), Lectura.id.desc())
            .limit(1)
        )
        segundos = (
            round((ahora - lectura.ts_recepcion).total_seconds(), 1)
            if lectura is not None
            else None
        )
        ultima_alerta = None
        if lectura is not None:
            consulta_alerta = select(Alerta).where(Alerta.estacion == estacion)
            if lectura.id_fruta is not None:
                consulta_alerta = consulta_alerta.where(
                    Alerta.id_fruta == lectura.id_fruta
                )
            ultima_alerta = session.scalar(
                consulta_alerta.order_by(Alerta.creado_en.desc(), Alerta.id.desc())
                .limit(1)
            )

        entrada = {
            "estacion": estacion,
            "estado": (
                "ok"
                if segundos is not None and segundos <= SEGUNDOS_SIN_SENAL
                else "sin_senal"
            ),
            "ultima_lectura": (
                lectura.ts_recepcion if lectura is not None else None
            ),
            "id_fruta": lectura.id_fruta if lectura is not None else None,
            "severidad_ultima": (
                ultima_alerta.severidad if ultima_alerta is not None else None
            ),
        }
        if estacion == "E6":
            evento_cinta = session.scalar(
                select(EventoCinta)
                .join(Lectura, EventoCinta.lectura_id == Lectura.id)
                .order_by(Lectura.ts_recepcion.desc(), EventoCinta.id.desc())
                .limit(1)
            )
            entrada["estado_cinta"] = (
                evento_cinta.estado_cinta if evento_cinta is not None else None
            )
            entrada["falla_mecanica_detectada"] = (
                evento_cinta.falla_mecanica if evento_cinta is not None else None
            )
            if evento_cinta is not None and (
                evento_cinta.falla_mecanica
                or evento_cinta.estado_cinta == "falla_mecanica"
            ):
                entrada["estado"] = "falla"
            if evento_cinta is not None:
                entrada["id_fruta"] = evento_cinta.id_fruta_en_cinta
        estado.append(entrada)
    return {"id_lote": id_lote, "ahora": ahora, "estaciones": estado}


@app.get("/api/v1/sistema", tags=["Sistema"])
def obtener_estado_sistema():
    import psutil

    leer_sensores = getattr(psutil, "sensors_temperatures", None)
    try:
        sensores = leer_sensores() if leer_sensores is not None else {}
    except NotImplementedError:
        sensores = {}
    temperatura = next(
        (
            entrada.current
            for nombre in ("cpu_thermal", "coretemp")
            for entrada in sensores.get(nombre, [])
            if entrada.current is not None
        ),
        None,
    )
    memoria = psutil.virtual_memory()
    disco = psutil.disk_usage(str(DATABASE_PATH.parent))
    return {
        "temperatura_c": temperatura,
        "cpu_porcentaje": psutil.cpu_percent(interval=0.1),
        "ram_porcentaje": memoria.percent,
        "ram_usada_bytes": memoria.used,
        "ram_total_bytes": memoria.total,
        "almacenamiento_porcentaje": disco.percent,
        "almacenamiento_usado_bytes": disco.used,
        "almacenamiento_total_bytes": disco.total,
        "almacenamiento_alerta": (
            disco.percent >= ALMACENAMIENTO_ALERTA_PORCENTAJE
        ),
    }


@app.get("/api/v1/predicciones", tags=["Predicción"])
def obtener_predicciones():
    if not MODELO_PREDICCION_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Modelo sin entrenar. Registra historial real de E5 y ejecuta "
                "python tools/entrenar_modelo.py"
            ),
        )
    return json.loads(MODELO_PREDICCION_PATH.read_text(encoding="utf-8"))


app.mount(
    "/",
    StaticFiles(
        directory=Path(__file__).resolve().parent.parent / "frontend",
        html=True,
    ),
    name="frontend",
)

import hashlib
import json
import logging
from contextlib import asynccontextmanager
from datetime import timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import crear_tablas, get_db
from app.models import Alerta, EventoCinta, Fruta, Grupo, Lectura, Lote
from app.schemas import E1Payload, E2Payload, E3Payload, E4Payload, E6Payload


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    crear_tablas()
    yield


app = FastAPI(
    title="API de Ingesta - Estación 5 (Supervisión y Trazabilidad)",
    description="Servicio centralizado para la recepción de lecturas de PackIA.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
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
        "id_grupo": lectura.id_grupo,
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


def _obtener_o_crear_grupo(
    session: Session, id_grupo: str, id_lote: str
) -> Grupo:
    grupo = session.get(Grupo, id_grupo)
    if grupo is not None and grupo.id_lote != id_lote:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El id_grupo ya está asociado a otro lote",
        )
    if grupo is None:
        grupo = Grupo(id_grupo=id_grupo, id_lote=id_lote)
        session.add(grupo)
        session.flush()
    return grupo


def _actualizar_frutas(session: Session, id_grupo: str, payload: Any) -> None:
    if isinstance(payload, E2Payload):
        campo_por_estacion = {
            "e2_calidad_visual": "calidad_visual",
            "e2_confianza_visual": "confianza_visual",
            "e2_defectos": "defectos_detectados",
        }
    elif isinstance(payload, E3Payload):
        campo_por_estacion = {
            "e3_diametro_mm": "diametro_mm",
            "e3_tamano": "tamano",
        }
    elif isinstance(payload, E4Payload):
        campo_por_estacion = {
            "e4_categoria_final": "categoria_final",
            "e4_probabilidad": "probabilidad",
            "e4_revision_manual": "requiere_revision_manual",
        }
    else:
        return

    for fruta in payload.frutas:
        fruta_data = fruta.model_dump()
        valores = {
            "id_grupo": id_grupo,
            "id_fruta": fruta.id_fruta,
            **{
                campo: fruta_data[campo_payload]
                for campo, campo_payload in campo_por_estacion.items()
            },
        }
        insert = _insertar(Fruta, valores, session)
        actualizacion = {
            campo: getattr(insert.excluded, campo)
            for campo in campo_por_estacion
        }
        session.execute(
            insert.on_conflict_do_update(
                index_elements=["id_grupo", "id_fruta"],
                set_=actualizacion,
            )
        )


def _guardar_lectura(session: Session, payload: Any) -> dict:
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

    id_grupo = getattr(payload, "id_grupo", None)
    _obtener_o_crear_lote(session, payload.id_lote)
    if id_grupo is not None:
        _obtener_o_crear_grupo(session, id_grupo, payload.id_lote)

    lectura_values = {
        "id_lote": payload.id_lote,
        "id_grupo": id_grupo,
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

    if isinstance(payload, E1Payload):
        grupo = session.get(Grupo, payload.id_grupo)
        grupo.frutas_detectadas = payload.datos.frutas_detectadas
        grupo.e1_validez_imagen = payload.datos.validez_imagen
        grupo.e1_estado_captura = payload.datos.estado_captura
        grupo.e1_posicion_correcta = payload.datos.posicion_correcta
    else:
        _actualizar_frutas(session, id_grupo, payload)

    if isinstance(payload, E6Payload):
        session.add(
            EventoCinta(
                id_lote=payload.id_lote,
                lectura_id=lectura.id,
                estado_cinta=payload.datos.estado_cinta,
                falla_mecanica=payload.datos.falla_mecanica_detectada,
                id_grupo_en_cinta=payload.datos.id_grupo_en_cinta,
                ts=payload.timestamp,
            )
        )

    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("No se pudo guardar una lectura de %s", payload.estacion)
        raise

    return {
        "status": "success",
        "estacion": payload.estacion,
        "id_lote": payload.id_lote,
        "id_grupo": id_grupo,
        "lectura_id": lectura.id,
        "duplicado": False,
    }


@app.get("/")
def read_root():
    return {"status": "online", "mensaje": "Servidor de Ingesta Estación 5 Operativo"}


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


@app.get("/api/v1/lotes", tags=["Consultas"])
def listar_lotes(session: Session = Depends(get_db)):
    filas = session.execute(
        select(Lote, func.count(Grupo.id_grupo))
        .outerjoin(Grupo, Grupo.id_lote == Lote.id_lote)
        .group_by(Lote.id_lote)
        .order_by(Lote.creado_en.desc())
    ).all()
    return [
        {
            "id_lote": lote.id_lote,
            "creado_en": lote.creado_en,
            "estado": lote.estado,
            "grupos": grupos,
        }
        for lote, grupos in filas
    ]


@app.get("/api/v1/lotes/{id_lote}/grupos", tags=["Consultas"])
def listar_grupos(
    id_lote: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
):
    lote = session.get(Lote, id_lote)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    grupos = session.scalars(
        select(Grupo)
        .where(Grupo.id_lote == id_lote)
        .order_by(Grupo.ingreso.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id_grupo": grupo.id_grupo,
            "id_lote": grupo.id_lote,
            "frutas_detectadas": grupo.frutas_detectadas,
            "estado": grupo.estado,
            "ingreso": grupo.ingreso,
            "salida": grupo.salida,
        }
        for grupo in grupos
    ]


@app.get("/api/v1/grupos/{id_grupo}", tags=["Consultas"])
def obtener_trazabilidad(id_grupo: str, session: Session = Depends(get_db)):
    grupo = session.get(Grupo, id_grupo)
    if grupo is None:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    frutas = session.scalars(
        select(Fruta)
        .where(Fruta.id_grupo == id_grupo)
        .order_by(Fruta.id_fruta)
    ).all()
    lecturas = session.scalars(
        select(Lectura)
        .where(Lectura.id_grupo == id_grupo)
        .order_by(Lectura.ts_estacion, Lectura.id)
    ).all()
    return {
        "grupo": {
            "id_grupo": grupo.id_grupo,
            "id_lote": grupo.id_lote,
            "frutas_detectadas": grupo.frutas_detectadas,
            "validez_imagen": grupo.e1_validez_imagen,
            "estado_captura": grupo.e1_estado_captura,
            "posicion_correcta": grupo.e1_posicion_correcta,
            "estado": grupo.estado,
            "ingreso": grupo.ingreso,
            "salida": grupo.salida,
        },
        "frutas": [
            {
                "id_fruta": fruta.id_fruta,
                "calidad_visual": fruta.e2_calidad_visual,
                "confianza_visual": fruta.e2_confianza_visual,
                "defectos_detectados": fruta.e2_defectos,
                "diametro_mm": fruta.e3_diametro_mm,
                "tamano": fruta.e3_tamano,
                "categoria_final": fruta.e4_categoria_final,
                "probabilidad": fruta.e4_probabilidad,
                "requiere_revision_manual": fruta.e4_revision_manual,
            }
            for fruta in frutas
        ],
        "lecturas": [
            {
                "id": lectura.id,
                "estacion": lectura.estacion,
                "timestamp": lectura.ts_estacion,
                "recibida_en": lectura.ts_recepcion,
                "payload": lectura.payload,
            }
            for lectura in lecturas
        ],
    }


@app.get("/api/v1/metricas", tags=["Consultas"])
def obtener_metricas(
    lote: str | None = None, session: Session = Depends(get_db)
):
    if lote is not None and session.get(Lote, lote) is None:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    frutas_query = select(Fruta, Grupo.id_lote).join(
        Grupo, Fruta.id_grupo == Grupo.id_grupo
    )
    lecturas_query = select(Lectura).where(Lectura.estacion == "E4")
    alertas_query = select(Alerta.estacion, func.count(Alerta.id))
    if lote is not None:
        frutas_query = frutas_query.where(Grupo.id_lote == lote)
        lecturas_query = lecturas_query.where(Lectura.id_lote == lote)
        alertas_query = alertas_query.where(Alerta.id_lote == lote)

    frutas = session.execute(frutas_query).all()
    lecturas_e4 = session.scalars(
        lecturas_query.order_by(Lectura.ts_estacion, Lectura.id)
    ).all()
    alertas_por_estacion = dict(
        session.execute(
            alertas_query.group_by(Alerta.estacion)
        ).all()
    )

    primera_lectura_por_fruta = {}
    for lectura in lecturas_e4:
        for fruta in lectura.payload.get("frutas", []):
            clave = (lectura.id_lote, lectura.id_grupo, fruta["id_fruta"])
            primera_lectura_por_fruta.setdefault(clave, lectura.ts_estacion)

    frutas_por_hora = {}
    conteo_por_categoria = {
        "exportacion": 0,
        "mercado_nacional": 0,
        "proceso": 0,
        "rechazo": 0,
        "revision_manual": 0,
    }
    conteo_por_tamano = {"pequeno": 0, "mediano": 0, "grande": 0}
    frutas_clasificadas = 0
    frutas_rechazadas = 0
    for fruta, id_lote_fruta in frutas:
        if fruta.e3_tamano is not None:
            conteo_por_tamano[fruta.e3_tamano] += 1
        if fruta.e4_categoria_final is None:
            continue
        frutas_clasificadas += 1
        conteo_por_categoria[fruta.e4_categoria_final] += 1
        if fruta.e4_categoria_final == "rechazo":
            frutas_rechazadas += 1

        clave = (id_lote_fruta, fruta.id_grupo, fruta.id_fruta)
        timestamp = primera_lectura_por_fruta.get(clave)
        if timestamp is not None:
            hora = timestamp.astimezone(timezone.utc).replace(
                minute=0, second=0, microsecond=0
            )
            hora_key = hora.isoformat().replace("+00:00", "Z")
            frutas_por_hora[hora_key] = frutas_por_hora.get(hora_key, 0) + 1

    return {
        "id_lote": lote,
        "frutas_por_hora": [
            {"hora": hora, "cantidad": cantidad}
            for hora, cantidad in sorted(frutas_por_hora.items())
        ],
        "porcentaje_rechazo": (
            round(frutas_rechazadas * 100 / frutas_clasificadas, 2)
            if frutas_clasificadas
            else 0.0
        ),
        "conteo_por_categoria": conteo_por_categoria,
        "conteo_por_tamano": conteo_por_tamano,
        "anomalias_por_estacion": {
            estacion: alertas_por_estacion.get(estacion, 0)
            for estacion in ("E1", "E2", "E3", "E4", "E6")
        },
    }

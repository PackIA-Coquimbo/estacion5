from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, _dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Lote(Base):
    __tablename__ = "lote"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('activo', 'finalizado', 'pausado')",
            name="ck_lote_estado",
        ),
    )

    id_lote: Mapped[str] = mapped_column(String(50), primary_key=True)
    creado_en: Mapped[datetime] = mapped_column(
        "fecha_creacion", UTCDateTime(), default=ahora_utc
    )
    estado: Mapped[str] = mapped_column(String(20), default="activo", nullable=False)


class Grupo(Base):
    __tablename__ = "grupo"

    id_grupo: Mapped[str] = mapped_column(String(100), primary_key=True)
    id_lote: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("lote.id_lote", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frutas_detectadas: Mapped[int | None] = mapped_column(Integer)
    e1_validez_imagen: Mapped[bool | None] = mapped_column(Boolean)
    e1_estado_captura: Mapped[str | None] = mapped_column(String(30))
    e1_posicion_correcta: Mapped[bool | None] = mapped_column(Boolean)
    estado: Mapped[str] = mapped_column(String(30), default="en_proceso", nullable=False)
    ingreso: Mapped[datetime] = mapped_column(UTCDateTime(), default=ahora_utc)
    salida: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Fruta(Base):
    __tablename__ = "fruta"
    __table_args__ = (
        UniqueConstraint("id_grupo", "id_fruta", name="uq_fruta_grupo_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_grupo: Mapped[str] = mapped_column(
        ForeignKey("grupo.id_grupo", ondelete="CASCADE"), nullable=False
    )
    id_fruta: Mapped[str] = mapped_column(String(100), nullable=False)
    e2_calidad_visual: Mapped[str | None] = mapped_column(String(40))
    e2_confianza_visual: Mapped[float | None] = mapped_column(Float)
    e2_defectos: Mapped[list[str] | None] = mapped_column(JSON)
    e3_diametro_mm: Mapped[float | None] = mapped_column(Float)
    e3_tamano: Mapped[str | None] = mapped_column(String(20))
    e4_categoria_final: Mapped[str | None] = mapped_column(String(40))
    e4_probabilidad: Mapped[float | None] = mapped_column(Float)
    e4_revision_manual: Mapped[bool | None] = mapped_column(Boolean)


class Lectura(Base):
    __tablename__ = "lectura"
    __table_args__ = (
        UniqueConstraint("payload_hash", name="uq_lectura_payload_hash"),
        Index("ix_lectura_estacion_ts", "estacion", "ts_recepcion"),
        Index("ix_lectura_lote_grupo", "id_lote", "id_grupo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lote: Mapped[str] = mapped_column(
        String(50), ForeignKey("lote.id_lote", ondelete="CASCADE"), nullable=False
    )
    id_grupo: Mapped[str | None] = mapped_column(
        ForeignKey("grupo.id_grupo", ondelete="SET NULL")
    )
    estacion: Mapped[str] = mapped_column(String(2), nullable=False)
    ts_estacion: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    ts_recepcion: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=ahora_utc, nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class Alerta(Base):
    __tablename__ = "alerta"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_alerta_dedupe_key"),
        Index("ix_alerta_activa", "resuelta", "creado_en"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lote: Mapped[str] = mapped_column(
        String(50), ForeignKey("lote.id_lote", ondelete="CASCADE"), nullable=False
    )
    id_grupo: Mapped[str | None] = mapped_column(String(100))
    id_fruta: Mapped[str | None] = mapped_column(String(100))
    estacion: Mapped[str] = mapped_column(String(2), nullable=False)
    severidad: Mapped[str] = mapped_column(String(20), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(300), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(UTCDateTime(), default=ahora_utc)
    resuelta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)


class EventoCinta(Base):
    __tablename__ = "evento_cinta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lote: Mapped[str] = mapped_column(
        String(50), ForeignKey("lote.id_lote", ondelete="CASCADE"), nullable=False
    )
    lectura_id: Mapped[int] = mapped_column(
        ForeignKey("lectura.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    estado_cinta: Mapped[str] = mapped_column(String(30), nullable=False)
    falla_mecanica: Mapped[bool] = mapped_column(Boolean, nullable=False)
    id_grupo_en_cinta: Mapped[str | None] = mapped_column(String(100))
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class PayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestaBase(PayloadModel):
    id_lote: str = Field(..., min_length=1, description="Identificador del lote")
    timestamp: AwareDatetime = Field(
        ..., description="Fecha y hora de la lectura, con zona horaria"
    )


class E1Data(PayloadModel):
    validez_imagen: bool
    estado_captura: Literal["aceptada", "repetir", "revision"]
    posicion_correcta: bool
    frutas_detectadas: int = Field(..., gt=0)


class E1Payload(IngestaBase):
    id_grupo: str = Field(..., min_length=1)
    estacion: Literal["E1"]
    datos: E1Data


class E2Fruta(PayloadModel):
    id_fruta: str = Field(..., min_length=1)
    calidad_visual: Literal[
        "alta", "media", "baja", "defectos_visibles", "revision"
    ]
    confianza_visual: float = Field(
        ..., ge=0.0, le=1.0, json_schema_extra={"example": 0.92}
    )
    defectos_detectados: list[str] = Field(default_factory=list)


class E2Payload(IngestaBase):
    id_grupo: str = Field(..., min_length=1)
    estacion: Literal["E2"]
    frutas: list[E2Fruta]


class E3Fruta(PayloadModel):
    id_fruta: str = Field(..., min_length=1)
    diametro_mm: float = Field(
        ..., gt=0, json_schema_extra={"example": 40}
    )
    tamano: Literal["pequeno", "mediano", "grande"]


class E3Payload(IngestaBase):
    id_grupo: str = Field(..., min_length=1)
    estacion: Literal["E3"]
    frutas: list[E3Fruta]


class E4Fruta(PayloadModel):
    id_fruta: str = Field(..., min_length=1)
    categoria_final: Literal[
        "exportacion", "mercado_nacional", "proceso", "rechazo", "revision_manual"
    ]
    probabilidad: float = Field(
        ..., ge=0.0, le=1.0, json_schema_extra={"example": 0.88}
    )
    requiere_revision_manual: bool


class E4Payload(IngestaBase):
    id_grupo: str = Field(..., min_length=1)
    estacion: Literal["E4"]
    frutas: list[E4Fruta]


class E6Data(PayloadModel):
    estado_cinta: Literal["normal", "detenida", "falla_mecanica"]
    falla_mecanica_detectada: bool
    id_grupo_en_cinta: str | None = None


class E6Payload(IngestaBase):
    estacion: Literal["E6"]
    datos: E6Data

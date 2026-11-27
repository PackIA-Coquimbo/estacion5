from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class PayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestaBase(PayloadModel):
    id_lote: str = Field(..., min_length=1, max_length=50)
    timestamp: AwareDatetime


class E1Data(PayloadModel):
    validez_imagen: bool
    estado_captura: Literal["aceptada", "repetir", "revision"]
    posicion_correcta: bool


class E1Payload(IngestaBase):
    id_fruta: str = Field(..., min_length=1, max_length=100)
    estacion: Literal["E1"]
    datos: E1Data


class E2Data(PayloadModel):
    calidad_visual: Literal[
        "alta", "media", "baja", "defectos_visibles", "revision"
    ]
    confianza_visual: float = Field(..., ge=0.0, le=1.0)
    defectos_detectados: list[str] = Field(default_factory=list)


class E2Payload(IngestaBase):
    id_fruta: str = Field(..., min_length=1, max_length=100)
    estacion: Literal["E2"]
    datos: E2Data


class E3Data(PayloadModel):
    diametro_mm: float = Field(..., gt=0)
    tamano: Literal["pequeno", "mediano", "grande"]


class E3Payload(IngestaBase):
    id_fruta: str = Field(..., min_length=1, max_length=100)
    estacion: Literal["E3"]
    datos: E3Data


class E4Data(PayloadModel):
    categoria_final: Literal[
        "exportacion", "mercado_nacional", "proceso", "rechazo", "revision_manual"
    ]
    probabilidad: float = Field(..., ge=0.0, le=1.0)
    requiere_revision_manual: bool


class E4Payload(IngestaBase):
    id_fruta: str = Field(..., min_length=1, max_length=100)
    estacion: Literal["E4"]
    datos: E4Data


class E6Data(PayloadModel):
    estado_cinta: Literal["normal", "detenida", "falla_mecanica"]
    falla_mecanica_detectada: bool
    id_fruta_en_cinta: str | None = Field(default=None, max_length=100)


class E6Payload(IngestaBase):
    estacion: Literal["E6"]
    datos: E6Data

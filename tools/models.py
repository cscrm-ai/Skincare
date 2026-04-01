"""Schemas Pydantic para o laudo dermatologico da Dra. Sync."""

from typing import Literal

from pydantic import BaseModel, Field


class DermatologicalFinding(BaseModel):
    """Achado clinico individual identificado na imagem."""

    description: str = Field(
        ...,
        description="Descricao clinica do achado (ex: 'melasma malar bilateral')",
    )
    zone: str = Field(
        ...,
        description="Zona facial afetada (ex: 'Macas do rosto', 'Zona T', 'Regiao periorbital')",
    )
    priority: Literal["PRIORITÁRIO", "RECOMENDADO", "OPCIONAL"] = Field(
        ...,
        description="Nivel de prioridade clinica do achado",
    )
    conduta: str = Field(
        ...,
        description="Abordagem terapeutica ou cosmetica sugerida",
    )
    active_or_procedure: str = Field(
        ...,
        description="Ativo cosmetico ou procedimento de referencia",
    )
    clinical_note: str = Field(
        ...,
        description="Observacao clinica especifica (contraindicacoes, fototipo, cuidados)",
    )
    query: str = Field(
        ...,
        description="Query usada para localizar este achado na imagem via FAL AI",
    )
    x_point: float = Field(
        ...,
        description="Coordenada X do achado na imagem (0-1 normalizado)",
    )
    y_point: float = Field(
        ...,
        description="Coordenada Y do achado na imagem (0-1 normalizado)",
    )


class SkinAnalysisReport(BaseModel):
    """Relatorio completo de analise dermatologica."""

    fitzpatrick_type: Literal["I", "II", "III", "IV", "V", "VI"] = Field(
        ...,
        description="Fototipo identificado na escala de Fitzpatrick",
    )
    skin_type: str = Field(
        ...,
        description="Tipo de pele (ex: 'Oleosa, sensivel, fotoenvelhecimento misto')",
    )
    findings: list[DermatologicalFinding] = Field(
        default_factory=list,
        description="Lista de achados clinicos identificados",
    )
    am_routine: str = Field(
        ...,
        description="Rotina de skin care sugerida para manha",
    )
    pm_routine: str = Field(
        ...,
        description="Rotina de skin care sugerida para noite",
    )
    general_observations: str = Field(
        ...,
        description="Observacoes gerais e avisos eticos",
    )

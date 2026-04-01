"""Schemas Pydantic para o laudo dermatológico da Dra. Sync."""

from typing import Literal

from pydantic import BaseModel, Field


class DermatologicalFinding(BaseModel):
    """Achado clínico individual identificado na imagem."""

    description: str = Field(
        ...,
        description="Descrição clínica do achado (ex: 'melasma malar bilateral')",
    )
    zone: str = Field(
        ...,
        description="Zona facial afetada (ex: 'Maçãs do rosto', 'Zona T', 'Região periorbital')",
    )
    priority: Literal["PRIORITÁRIO", "RECOMENDADO", "OPCIONAL"] = Field(
        ...,
        description="Nível de prioridade clínica do achado",
    )
    conduta: str = Field(
        ...,
        description="Abordagem terapêutica ou cosmética sugerida",
    )
    active_or_procedure: str = Field(
        ...,
        description="Ativo cosmético ou procedimento de referência",
    )
    clinical_note: str = Field(
        ...,
        description="Observação clínica específica (contraindicações, fototipo, cuidados)",
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
    """Relatório completo de análise dermatológica."""

    fitzpatrick_type: Literal["I", "II", "III", "IV", "V", "VI"] = Field(
        ...,
        description="Fototipo identificado na escala de Fitzpatrick",
    )
    skin_type: str = Field(
        ...,
        description="Tipo de pele (ex: 'Oleosa, sensível, fotoenvelhecimento misto')",
    )
    findings: list[DermatologicalFinding] = Field(
        default_factory=list,
        description="Lista de achados clínicos identificados",
    )
    am_routine: str = Field(
        ...,
        description="Rotina de skin care sugerida para manhã",
    )
    pm_routine: str = Field(
        ...,
        description="Rotina de skin care sugerida para noite",
    )
    general_observations: str = Field(
        ...,
        description="Observações gerais e avisos éticos",
    )

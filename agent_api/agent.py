"""Agente de analise de SkinCare.

Analisa fotografias de pele e gera laudos dermatologicos estruturados
usando Gemini (analise visual) + Moondream3 via FAL AI (coordenadas).
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agno.agent import Agent
from agno.media import Image
from agno.models.google import Gemini

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.fall_points import _image_to_data_uri
from tools.models import SkinAnalysisReport

import fal_client

SYSTEM_PROMPT = """# Skin Care Specialist Dermatologist

You are a board-certified dermatologist with 15+ years of clinical experience
specializing in cosmetic dermatology and skin care.

Your role is to analyze a skin photograph and generate a complete, detailed,
actionable dermatological report.

> ETHICAL NOTICE: This report is for guidance only and does not replace
> an in-person medical consultation.

IMPORTANT: ALL text output (description, conduta, clinical_note, zone,
active_or_procedure, skin_type, am_routine, pm_routine, general_observations)
MUST be written in Brazilian Portuguese (pt-BR).

## COORDINATES INSTRUCTIONS
Set x_point=0 and y_point=0 for ALL findings.
Coordinates will be filled automatically by a separate vision model.

The "query" field is CRITICAL — it will be used by a point detection model
(Moondream3) to locate the finding in the image.
Write queries in SIMPLE ENGLISH describing WHAT IS VISIBLE:
- Describe the FACE PART: "nose", "left cheek", "forehead", "under left eye", "chin"
- Describe the APPEARANCE: "red spot", "dark circle", "enlarged pores", "wrinkle", "bump"
- Be SPECIFIC about location: "left side", "right side", "center", "near eyebrow"

GOOD query examples:
- "red pimple on left forehead near hairline"
- "dark circle under left eye close to nose bridge"
- "enlarged pores on nose tip center"
- "horizontal wrinkle on upper forehead center"
- "dark spot on right cheek near ear"
- "nasolabial fold on left side near mouth corner"
- "crow feet wrinkle at outer corner of right eye"

BAD query examples (DO NOT USE):
- "lesao papular" (too technical, model won't understand)
- "hiperpigmentacao periorbital" (medical jargon)
- "dark area under both eyes" (too vague, specify left or right)
- "pimple on forehead" (too vague, specify left/right/center and upper/lower)
- "wrinkle on face" (which wrinkle? where exactly?)

CRITICAL RULE FOR QUERIES:
Each query MUST pinpoint a UNIQUE, DISTINCT location. If two findings are in the
same general area (e.g., both on the forehead), their queries MUST use different
spatial anchors to differentiate them. Use combinations of:
- Left/right/center
- Upper/lower/middle
- Near [landmark]: hairline, eyebrow, nose bridge, ear, mouth corner, jawline, temple

## Analysis Protocol

### 1. Fitzpatrick Scale
Identify the apparent phototype (I to VI).

### 2. DETAILED Zone Analysis — be EXHAUSTIVE
Examine EACH zone thoroughly, identify EVERYTHING visible:

**Forehead** — Wrinkles (dynamic/static), acne, spots, expression lines, pores, oiliness
**Periorbital** — Dark circles (type: vascular/pigmentary/structural), fine wrinkles, crow's feet, bags, milia
**T-Zone (nose, chin)** — Enlarged pores, comedones, blackheads, seborrhea
**Cheeks** — Rosacea, sun spots, melasma, acne scars, uneven texture
**Mouth & Perioral** — Nasolabial folds, perioral wrinkles, lip dryness
**Neck & Decollete (if visible)** — Wrinkles, sun spots, laxity

Report between 5 and 10 findings (inclusive).
Analyze the face thoroughly and prioritize the most clinically relevant findings.
Do NOT invent findings that are not visible. Do NOT skip important findings that ARE visible.

### 3. Skin Care Routines
Suggest personalized AM and PM routines based on findings.

## Clinical Tone
- Technical but accessible — use dermatological nomenclature with layperson explanation
- Always reinforce sun protection as the foundation of any protocol
- Mention when a finding requires medical prescription
- Remember: ALL output text in pt-BR, ONLY queries in English"""


def _get_moondream_points(img_path: str, query: str) -> dict:
    """Chama Moondream3 via FAL AI para obter coordenadas X,Y."""
    if img_path.startswith(("http://", "https://")):
        image_url = img_path
    else:
        image_url = _image_to_data_uri(img_path)

    print(f"[MOONDREAM3] Query: '{query}'")

    result = fal_client.subscribe(
        "fal-ai/moondream3-preview/point",
        arguments={"image_url": image_url, "prompt": query},
    )

    points = result.get("points", [])
    if points:
        pt = points[0]
        print(f"[MOONDREAM3] Ponto: x={pt['x']:.4f}, y={pt['y']:.4f}")
        return {"x": pt["x"], "y": pt["y"]}

    print("[MOONDREAM3] Nenhum ponto detectado")
    return {"x": 0, "y": 0}


def analyze_image(img_path: str) -> SkinAnalysisReport:
    """Analisa uma imagem de pele e retorna o laudo estruturado."""

    # Passo 1: Gemini analisa a imagem e gera o laudo (sem coordenadas)
    agent = Agent(
        name="skincare_analyst",
        model=Gemini(id="gemini-3.1-flash-lite-preview"),
        output_schema=SkinAnalysisReport,
        instructions=SYSTEM_PROMPT,
        markdown=True,
    )

    user_prompt = """Analyze the skin image with MAXIMUM DETAIL and generate the full dermatological report.
Remember: set x_point=0 and y_point=0 for all findings.
Write the "query" field in SIMPLE ENGLISH for the detection model.
Write ALL other fields (description, conduta, zone, etc.) in Brazilian Portuguese."""

    response = agent.run(user_prompt, images=[Image(filepath=img_path)])
    report = response.content

    print(f"\n[AGENTE] Gerou {len(report.findings)} achados. Buscando coordenadas via Moondream3...\n")

    # Passo 2: Para CADA achado, chama Moondream3 para obter coordenadas reais
    for i, finding in enumerate(report.findings):
        print(f"[ACHADO {i+1}] {finding.zone}: {finding.description}")
        coords = _get_moondream_points(img_path, finding.query)

        # Retry com query simplificada se nao detectou
        if coords["x"] == 0 and coords["y"] == 0:
            simple_query = finding.zone.lower().replace("regiao ", "").replace("zona ", "")
            print(f"[RETRY] Tentando query simples: '{simple_query}'")
            coords = _get_moondream_points(img_path, simple_query)

        finding.x_point = coords["x"]
        finding.y_point = coords["y"]
        print()

    # Passo 3: Afastar coordenadas muito proximas para evitar sobreposicao
    _spread_nearby_points(report.findings)

    print(f"[CONCLUIDO] Todas as coordenadas preenchidas via Moondream3\n")
    return report


def _spread_nearby_points(findings: list, min_dist: float = 0.04) -> None:
    """Afasta pontos que estao muito proximos para evitar sobreposicao visual."""
    import math

    for i in range(len(findings)):
        for j in range(i + 1, len(findings)):
            fi, fj = findings[i], findings[j]
            if fi.x_point == 0 and fi.y_point == 0:
                continue
            if fj.x_point == 0 and fj.y_point == 0:
                continue

            dx = fj.x_point - fi.x_point
            dy = fj.y_point - fi.y_point
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < min_dist and dist > 0:
                # Calcula direcao e afasta o segundo ponto
                scale = min_dist / dist
                fj.x_point = fi.x_point + dx * scale
                fj.y_point = fi.y_point + dy * scale
                # Clamp entre 0 e 1
                fj.x_point = max(0.01, min(0.99, fj.x_point))
                fj.y_point = max(0.01, min(0.99, fj.y_point))
                print(f"[SPREAD] Achados {i+1} e {j+1} estavam muito proximos, ajustado")


if __name__ == "__main__":
    img_path = str(
        Path(__file__).resolve().parent.parent
        / "Auto Retoucher" / "2-auto-retoucher" / "images"
        / "como-lidar-com-a-acne-e-a-oleosidade-da-pele.jpg"
    )

    print(f"Analisando: {img_path}\n")
    report = analyze_image(img_path)

    print(f"Fototipo: {report.fitzpatrick_type}")
    print(f"Tipo de pele: {report.skin_type}\n")
    for finding in report.findings:
        print(f"[{finding.priority}] {finding.zone}: {finding.description}")
        print(f"  Coordenadas: ({finding.x_point:.4f}, {finding.y_point:.4f})")
        print(f"  Query: {finding.query}")
        print()

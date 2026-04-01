"""Agente de analise de SkinCare.

Analisa fotografias de pele e gera laudos dermatológicos estruturados
usando Gemini (análise visual) + Moondream3 via FAL AI (coordenadas).
Multi-provider: rotaciona entre API keys e modelos para evitar quota.
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
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


# ═══════════════════════════════════════
# MULTI-PROVIDER: rotação de keys e modelos
# ═══════════════════════════════════════

def _load_keys(prefix: str) -> list[str]:
    """Carrega todas as keys de um prefix (ex: GOOGLE_API_KEY, GOOGLE_API_KEY_2, ...)."""
    keys = []
    # Key principal
    main = os.environ.get(prefix)
    if main:
        keys.append(main)
    # Keys adicionais: PREFIX_2, PREFIX_3, ...
    for i in range(2, 20):
        k = os.environ.get(f"{prefix}_{i}")
        if k:
            keys.append(k)
    return keys


GOOGLE_KEYS = _load_keys("GOOGLE_API_KEY")
FAL_KEYS = _load_keys("FAL_KEY")

# Modelos Gemini em ordem de preferencia (mais barato → mais caro)
GEMINI_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

# Indice rotativo para distribuir carga entre keys
_google_key_idx = 0
_fal_key_idx = 0


def _next_google_key() -> str:
    """Retorna a próxima Google API key em round-robin."""
    global _google_key_idx
    if not GOOGLE_KEYS:
        return os.environ.get("GOOGLE_API_KEY", "")
    key = GOOGLE_KEYS[_google_key_idx % len(GOOGLE_KEYS)]
    _google_key_idx += 1
    return key


def _next_fal_key() -> str:
    """Retorna a próxima FAL key em round-robin."""
    global _fal_key_idx
    if not FAL_KEYS:
        return os.environ.get("FAL_KEY", "")
    key = FAL_KEYS[_fal_key_idx % len(FAL_KEYS)]
    _fal_key_idx += 1
    return key

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


def _get_moondream_points(query: str, image_url: str) -> dict:
    """Chama Moondream3 via FAL AI com rotação de keys."""
    print(f"[MOONDREAM3] Query: '{query}'")

    attempts = max(len(FAL_KEYS), 1)
    last_error = None

    for attempt in range(attempts):
        try:
            # Rotaciona FAL key
            key = _next_fal_key()
            os.environ["FAL_KEY"] = key
            print(f"[FAL] Usando key ...{key[-6:]}")

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

        except Exception as e:
            last_error = e
            err_msg = str(e).lower()
            if "quota" in err_msg or "429" in err_msg or "rate" in err_msg:
                print(f"[FAL] Key ...{key[-6:]} atingiu quota, tentando próxima...")
                continue
            raise

    print(f"[FAL] Todas as {attempts} keys falharam")
    raise last_error


def _resolve_finding_coords(finding, index: int, image_url: str) -> None:
    """Resolve coordenadas para um unico achado, com retry simplificado."""
    print(f"[ACHADO {index + 1}] {finding.zone}: {finding.description}")
    coords = _get_moondream_points(finding.query, image_url)

    if coords["x"] == 0 and coords["y"] == 0:
        simple_query = finding.zone.lower().replace("regiao ", "").replace("zona ", "")
        print(f"[RETRY] Tentando query simples: '{simple_query}'")
        coords = _get_moondream_points(simple_query, image_url)

    finding.x_point = coords["x"]
    finding.y_point = coords["y"]


def _call_gemini_with_fallback(prompt: str, img_path: str) -> SkinAnalysisReport:
    """Chama Gemini com rotação de keys e modelos fallback."""
    last_error = None

    for model_id in GEMINI_MODELS:
        for _key_attempt in range(max(len(GOOGLE_KEYS), 1)):
            try:
                key = _next_google_key()
                os.environ["GOOGLE_API_KEY"] = key
                print(f"[GEMINI] Tentando modelo={model_id}, key=...{key[-6:]}")

                agent = Agent(
                    name="skincare_analyst",
                    model=Gemini(id=model_id),
                    output_schema=SkinAnalysisReport,
                    instructions=SYSTEM_PROMPT,
                    markdown=True,
                )
                response = agent.run(prompt, images=[Image(filepath=img_path)])
                print(f"[GEMINI] Sucesso com {model_id}")
                return response.content

            except Exception as e:
                last_error = e
                err_msg = str(e).lower()
                if "quota" in err_msg or "429" in err_msg or "rate" in err_msg:
                    print(f"[GEMINI] Key ...{key[-6:]} quota excedida, tentando próxima...")
                    continue
                # Erro nao relacionado a quota — tenta proximo modelo
                print(f"[GEMINI] Erro com {model_id}: {e}, tentando próximo modelo...")
                break

    raise last_error or Exception("Todos os modelos e keys Gemini falharam")


def analyze_image(img_path: str) -> SkinAnalysisReport:
    """Analisa uma imagem de pele e retorna o laudo estruturado."""

    user_prompt = """Analyze the skin image with MAXIMUM DETAIL and generate the full dermatological report.
Remember: set x_point=0 and y_point=0 for all findings.
Write the "query" field in SIMPLE ENGLISH for the detection model.
Write ALL other fields (description, conduta, zone, etc.) in Brazilian Portuguese."""

    # Passo 1: Gemini analisa com fallback de modelos e keys
    report = _call_gemini_with_fallback(user_prompt, img_path)

    print(f"\n[AGENTE] Gerou {len(report.findings)} achados. Buscando coordenadas via Moondream3...\n")

    # Pre-computa image_url uma unica vez (evita re-ler o arquivo N vezes)
    if img_path.startswith(("http://", "https://")):
        image_url = img_path
    else:
        image_url = _image_to_data_uri(img_path)

    # Passo 2: Chama Moondream3 em PARALELO para todos os achados
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(_resolve_finding_coords, finding, i, image_url)
            for i, finding in enumerate(report.findings)
        ]
        for future in futures:
            future.result()  # Propaga exceções se houver

    # Passo 3: Afastar coordenadas muito proximas para evitar sobreposicao
    _spread_nearby_points(report.findings)

    print(f"[CONCLUIDO] Todas as coordenadas preenchidas via Moondream3\n")
    return report


def _spread_nearby_points(findings: list, min_dist: float = 0.04) -> None:
    """Afasta pontos que estão muito próximos para evitar sobreposição visual."""
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
                # Calcula direção e afasta o segundo ponto
                scale = min_dist / dist
                fj.x_point = fi.x_point + dx * scale
                fj.y_point = fi.y_point + dy * scale
                # Clamp entre 0 e 1
                fj.x_point = max(0.01, min(0.99, fj.x_point))
                fj.y_point = max(0.01, min(0.99, fj.y_point))
                print(f"[SPREAD] Achados {i+1} e {j+1} estavam muito próximos, ajustado")


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

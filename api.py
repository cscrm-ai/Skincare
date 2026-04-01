"""API FastAPI for SkinCare AI agent + frontend serving."""

import asyncio
import hashlib
import json
import os
import shutil
import time
import traceback
import uuid
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from agent_api.agent import analyze_image

BASE_DIR = Path(__file__).resolve().parent
ADMIN_DATA_FILE = Path("/tmp/admin_data.json")

app = FastAPI(title="SkinCare AI API")

DEFAULT_ADMIN_DATA = {
    "products": [],
    "videos": [],
    "tips": [],
    "skincare_guide": {
        "steps": ["Demaquilante", "Sabonete", "Esfoliante", "Tônico", "Sérum", "Antes do Protetor Solar", "Tratamento Noturno", "Hidratante", "Protetor Solar"],
        "skin_types": ["Normal", "Seca", "Oleosa", "Mista", "Sensível", "Acneica", "Madura", "Com Melasma"],
        "data": {}
    },
    "analyses": [],
    "settings": {"app_name": "All Belle", "default_lat": -26.99, "default_lon": -48.63}
}


def _load_admin_data() -> dict:
    if ADMIN_DATA_FILE.exists():
        try:
            return json.loads(ADMIN_DATA_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return DEFAULT_ADMIN_DATA.copy()


def _save_admin_data(data: dict):
    ADMIN_DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("/tmp/skincare_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════
# CACHE (SHA-256 do arquivo → JSON em /tmp)
# ═══════════════════════════════════════
CACHE_DIR = Path("/tmp/skincare_cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL = 86400  # 24 horas


def _get_image_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_cached_result(image_hash: str) -> dict | None:
    cache_file = CACHE_DIR / f"{image_hash}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            if time.time() - data.get("_cached_at", 0) < CACHE_TTL:
                print(f"[CACHE HIT] {image_hash[:12]}...")
                result = data.copy()
                result.pop("_cached_at", None)
                return result
            else:
                cache_file.unlink(missing_ok=True)
        except (json.JSONDecodeError, ValueError):
            cache_file.unlink(missing_ok=True)
    return None


def _set_cached_result(image_hash: str, result: dict):
    cache_file = CACHE_DIR / f"{image_hash}.json"
    data = {**result, "_cached_at": time.time()}
    cache_file.write_text(json.dumps(data, ensure_ascii=False))


# ═══════════════════════════════════════
# RATE LIMITING (in-memory por IP)
# ═══════════════════════════════════════
RATE_LIMIT_MAX = 10  # analises por IP
RATE_LIMIT_WINDOW = 3600  # 1 hora
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    timestamps = _rate_limit_store[ip]
    _rate_limit_store[ip] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit_store[ip].append(now)
    return True

WEATHER_CODES = {
    0: "Céu limpo", 1: "Predominantemente limpo", 2: "Parcialmente nublado",
    3: "Nublado", 45: "Neblina", 48: "Neblina com geada",
    51: "Garoa leve", 53: "Garoa moderada", 55: "Garoa intensa",
    61: "Chuva leve", 63: "Chuva moderada", 65: "Chuva forte",
    80: "Pancadas leves", 81: "Pancadas moderadas", 82: "Pancadas fortes",
    95: "Tempestade", 96: "Tempestade com granizo",
}


def _uv_recommendation(uv: float) -> str:
    if uv <= 2: return "Baixo risco. Protetor opcional."
    if uv <= 5: return "Moderado. Use protetor FPS 30+."
    if uv <= 7: return "Alto. Use protetor FPS 50+ e reaplique a cada 2h."
    if uv <= 10: return "Muito alto. Evite exposição entre 10h-16h. FPS 50+."
    return "Extremo. Evite o sol. FPS 50+ obrigatório."


@app.post("/api/clear-cache")
async def clear_cache():
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink(missing_ok=True)
        count += 1
    return {"cleared": count}


@app.get("/health")
async def health():
    gk = os.environ.get("GOOGLE_API_KEY", "")
    return {
        "status": "ok",
        "fal_key": bool(os.environ.get("FAL_KEY")),
        "google_key": bool(gk),
        "google_key_suffix": gk[-6:] if gk else "MISSING",
    }


@app.get("/api/uv")
async def get_uv(lat: float, lon: float):
    try:
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=uv_index,temperature_2m,weather_code"
        )
        geo_url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?lat={lat}&lon={lon}&format=json&zoom=10"
        )
        async with httpx.AsyncClient() as client:
            weather_resp, geo_resp = await asyncio.gather(
                client.get(weather_url, timeout=10),
                client.get(geo_url, timeout=10, headers={"User-Agent": "SkinCareAI/1.0"}),
            )
            data = weather_resp.json()
            geo = geo_resp.json()

        current = data.get("current", {})
        uv = current.get("uv_index", 0)

        # Extract city name from geocoding
        addr = geo.get("address", {})
        city = addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("county") or "Sua região"

        return {
            "uv_index": uv,
            "temperature": current.get("temperature_2m", 0),
            "weather_description": WEATHER_CODES.get(current.get("weather_code", 0), "Desconhecido"),
            "recommendation": _uv_recommendation(uv),
            "city": city,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/")
async def index():
    html = (BASE_DIR / "templates" / "index.html").read_text()
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.post("/analyze")
async def analyze(request: Request, image: UploadFile = File(...)):
    # Rate limit check
    client_ip = request.headers.get(
        "x-forwarded-for", request.client.host if request.client else "unknown"
    ).split(",")[0].strip()
    if not _check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Você atingiu o limite de análises por hora. Tente novamente mais tarde.",
                "type": "rate_limited",
            },
        )

    try:
        ext = Path(image.filename).suffix or ".jpg"
        unique_name = f"{uuid.uuid4().hex[:12]}{ext}"
        file_path = UPLOAD_DIR / unique_name

        with open(file_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

        # Check cache
        image_hash = _get_image_hash(file_path)
        cached = _get_cached_result(image_hash)
        if cached:
            file_path.unlink(missing_ok=True)
            return cached

        report = analyze_image(str(file_path.resolve()))
        result = report.model_dump()

        # Store in cache
        _set_cached_result(image_hash, result)

        file_path.unlink(missing_ok=True)

        # Save analysis to admin data
        try:
            ad = _load_admin_data()
            ad["analyses"].insert(0, {
                "date": __import__("datetime").datetime.now().isoformat(),
                "fitzpatrick": result.get("fitzpatrick_type", ""),
                "skin_type": result.get("skin_type", ""),
                "score": sum(1 for _ in result.get("findings", [])),
                "findings_count": len(result.get("findings", [])),
            })
            if len(ad["analyses"]) > 100:
                ad["analyses"] = ad["analyses"][:100]
            _save_admin_data(ad)
        except Exception:
            pass

        return result
    except Exception as e:
        traceback.print_exc()
        err_msg = str(e).lower()
        if "quota" in err_msg or "rate" in err_msg or "429" in err_msg:
            return JSONResponse(
                status_code=429,
                content={"error": "Limite de análises atingido. Aguarde alguns minutos.", "type": "quota_exceeded"},
            )
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "type": type(e).__name__},
        )


# ═══════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════

@app.get("/admin")
async def admin():
    html = (BASE_DIR / "templates" / "admin.html").read_text()
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/api/admin/data")
async def get_admin_data():
    return _load_admin_data()


@app.put("/api/admin/data")
async def save_admin_data(request: Request):
    data = await request.json()
    _save_admin_data(data)
    return {"ok": True}


@app.get("/api/admin/stats")
async def admin_stats():
    ad = _load_admin_data()
    return {
        "products": len(ad.get("products", [])),
        "videos": len(ad.get("videos", [])),
        "tips": len(ad.get("tips", [])),
        "analyses": len(ad.get("analyses", [])),
        "guide_types_filled": sum(1 for t in ad.get("skincare_guide", {}).get("data", {}).values() if any(v for v in t.values())),
    }

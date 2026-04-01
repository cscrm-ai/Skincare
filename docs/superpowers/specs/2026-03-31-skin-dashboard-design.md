# SkinCare AI — Skin Dashboard Expansion Design

## Overview

Expand the current single-screen skin analysis app into a multi-screen mobile-first dashboard with daily routines, UV protection, history tracking, and a user profile. Inspired by the HYPERACTIVE Sun Protection App (Behance) adapted for AI-powered dermatological analysis.

**Target user:** End consumer (B2C) wanting to manage their skin care, with a future professional panel (B2B) planned for v2.

**Stack:** FastAPI (Python) backend serving HTML/CSS/JS frontend. No framework migration. localStorage for MVP persistence.

---

## Architecture

### Navigation

5-tab bottom navigation bar (mobile-first):

```
Home | Scan | Rotina | Wishlist* | Perfil
```

*Wishlist is v2 — shows placeholder in MVP.

### Data Flow

```
User opens app
  → Home loads from localStorage (profile, last analysis, routine state)
  → UV card fetches Open-Meteo API via backend proxy (/api/uv?lat=X&lon=Y)

User runs Scan
  → Camera/upload → POST /analyze (Gemini + Moondream3)
  → Result saved to localStorage (analysis history array)
  → Score calculated client-side from findings
  → "Save as my routine" copies am/pm to routine store

Routine screen
  → Reads routine from localStorage
  → Checklist toggles saved per day
  → Reapply timer runs client-side (countdown from configurable interval)

Profile
  → Fitzpatrick + skin type auto-filled from last analysis
  → Name/age entered manually once
  → Stats computed from localStorage history
```

### Backend Changes

Minimal additions to existing FastAPI:

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Serve index.html (exists) |
| `POST /analyze` | Run analysis (exists) |
| `GET /api/uv` | Proxy to Open-Meteo UV API. Params: lat, lon. Returns UV index + weather |
| `GET /health` | Health check (exists) |

No database. No auth. All user state lives in localStorage.

### localStorage Schema

```json
{
  "profile": {
    "name": "string",
    "age": "number",
    "fitzpatrick": "I-VI",
    "skin_type": "string",
    "sensitivity": "string",
    "sunscreen_interval_minutes": 120
  },
  "analyses": [
    {
      "id": "uuid",
      "date": "ISO8601",
      "image_data": "base64 or data URI",
      "score": "number 0-100",
      "report": { "...SkinAnalysisReport schema" }
    }
  ],
  "routine": {
    "am": ["step1", "step2", "..."],
    "pm": ["step1", "step2", "..."],
    "custom_products": [{"name": "string", "when": "am|pm|both"}]
  },
  "today": {
    "date": "YYYY-MM-DD",
    "checked_am": [0, 2],
    "checked_pm": [],
    "reapply_times": ["09:00", "11:00"]
  },
  "daily_tip_index": "number"
}
```

---

## Screens

### 1. Home (Dashboard)

Cards displayed top to bottom:

1. **Greeting** — "Bom dia, {name}" + fitzpatrick + skin type
2. **UV Index** — Current UV from Open-Meteo, city name, temperature, protection recommendation. Color-coded severity (green/yellow/orange/red).
3. **Sunscreen Timer** — Countdown from configured interval (default 2h). "Reaplicei!" button resets timer and logs time. Shows today's reapplication history.
4. **Routine Checklist** — Quick view of today's AM or PM routine (based on time of day). Progress bar. Tap items to check off.
5. **Daily Tip** — Rotating tips based on profile (fitzpatrick, skin type). Array of ~30 tips, cycles daily.
6. **Skin Health Score** — Score from last analysis (0-100). Days since last scan. "Nova Analise" CTA button.

### 2. Scan (Analysis)

Three sub-sections in one scrollable view:

**Upload area** (top):
- Drag/drop zone + Upload button + Camera button (existing, improved visually)
- After upload: preview + "Analisar" button

**Scan History** (middle):
- Horizontal scroll of thumbnail cards: photo + date + score
- Tap to view full result
- Max 20 stored in localStorage

**Recommendations** (bottom):
- Card with top 3 active ingredients from last analysis
- Derived from `active_or_procedure` field of findings

**Result screen** (after analysis completes):
- Same layout as current but enhanced:
  - Score badge at top
  - Photo with numbered point markers (Moondream3 coordinates)
  - Finding cards below (existing design)
  - AM/PM routine cards with "Salvar como minha rotina" button
  - Button saves routine to localStorage and navigates to Rotina tab

### 3. Rotina (Routine)

**AM/PM toggle** at top (tab pills).

**Checklist** — Each routine step as a card:
- Checkbox + step name + brief description
- Tap to toggle checked state
- Progress bar below checklist

**Reapply Timer** — Same as home card but expanded:
- Larger countdown display
- Today's reapplication log with timestamps
- Configurable interval (from profile settings)

**Add Product** — Button opens simple modal:
- Product name (text input)
- When to use: AM / PM / Both (radio)
- Saves to `routine.custom_products`
- Appears in checklist alongside AI-generated steps

**Reset behavior:** Checklist resets daily at midnight (detected on app open by comparing stored date).

### 4. Perfil (Profile)

**Personal info card:**
- Name (text input)
- Age (number input)
- Saved on blur/change

**Skin info card** (auto-filled):
- Fitzpatrick type — from last analysis
- Skin type — from last analysis
- Sensitivity — from last analysis clinical notes
- Read-only badge: "Atualizado pela ultima analise"

**Statistics card:**
- Total analyses count
- Current score
- Best score ever
- Consecutive routine days (streak)

**Settings:**
- Sunscreen interval dropdown (1h, 1.5h, 2h, 2.5h, 3h)
- Theme toggle (dark only for MVP)
- "Limpar todos os dados" — confirmation dialog then clears localStorage

### 5. Wishlist (v2 — Placeholder)

Shows centered message: "Em breve! Aqui voce podera salvar produtos recomendados pela IA."

---

## Score Calculation

```
base_score = 100
for each finding:
  if priority == "PRIORITARIO": base_score -= 12
  if priority == "RECOMENDADO": base_score -= 6
  if priority == "OPCIONAL": base_score -= 2
score = max(0, min(100, base_score))
```

Score is calculated client-side after each analysis and stored with the analysis.

---

## UV API Integration

**Provider:** Open-Meteo (free, no API key required)

**Backend proxy endpoint:** `GET /api/uv?lat={lat}&lon={lon}`

Calls: `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=uv_index,temperature_2m,weathercode`

Returns:
```json
{
  "uv_index": 8.2,
  "temperature": 32,
  "weather_description": "Ensolarado",
  "recommendation": "Use protetor FPS 50+ e reaplique a cada 2h"
}
```

Frontend gets user location via `navigator.geolocation` on first load, caches in localStorage.

---

## Design Language

Maintain current dark glass-morphism style:
- Background: `#020205` with animated gradient blobs
- Cards: glass-panel effect (backdrop-filter blur, semi-transparent borders)
- Accent colors: indigo (`#4f46e5`), pink (`#db2777`), cyan (`#0ea5e9`)
- Priority badges: red (prioritario), yellow (recomendado), green (opcional)
- Typography: Inter (body) + Space Mono (labels, data)
- Bottom nav: glass-panel bar with icon + label, active state with glow

Mobile-first. Responsive but optimized for phone screens (375px-428px width).

---

## Implementation Priority

| Phase | Scope | Effort |
|-------|-------|--------|
| Phase 1 | Multi-screen nav + Home dashboard + UV API | Medium |
| Phase 2 | Scan improvements (history, score, save routine) | Low |
| Phase 3 | Rotina screen (checklist, timer, add product) | Low |
| Phase 4 | Profile screen | Low |
| Phase 5 | Polish, animations, responsive tweaks | Low |

---

## Out of Scope (MVP)

- User authentication / login
- Database persistence (Supabase/Neon)
- Wishlist / product catalog
- Push notifications (browser notifications only via timer)
- PDF report export
- Before/after comparison view
- Multi-device sync
- Professional/clinic panel (B2B)

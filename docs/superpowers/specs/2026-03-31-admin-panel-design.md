# All Belle Admin Panel — Design Spec

## Overview

Admin panel served at `/admin` within the existing FastAPI project. Allows managing all app content (products, videos, tips, skincare guide) and viewing analytics. No authentication for now. Data persisted in local JSON file (works locally, ephemeral on Vercel).

**Visual identity:** All Belle brand (rosé, taupe, cream, Metropolis font).

---

## Architecture

- **Route:** `GET /admin` serves `templates/admin.html`
- **API endpoints:** All under `/api/admin/*` prefix
- **Data storage:** Single JSON file at `/tmp/admin_data.json` with sections for products, videos, tips, skincare guide, and analysis history
- **Design:** Single HTML file with sidebar navigation, same ALL BELLE brand identity

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin` | Serve admin HTML |
| GET | `/api/admin/data` | Get all admin data |
| PUT | `/api/admin/data` | Save all admin data |
| GET | `/api/admin/stats` | Dashboard metrics |

Single data endpoint approach (GET/PUT entire JSON) keeps it simple — admin loads all data on open, saves on each change.

### Data Schema

```json
{
  "products": [
    {
      "id": "string",
      "name": "string",
      "brand": "string",
      "category": "Protetor Solar|Limpeza|Serum|Hidratante|Tratamento",
      "price": 89.90,
      "oldPrice": 99.90,
      "rating": 4.8,
      "reviews": 324,
      "tag": "lancamento|null",
      "sizes": ["50ml", "100ml"],
      "desc": "string",
      "howToUse": "string"
    }
  ],
  "videos": [
    {
      "id": "string",
      "title": "string",
      "desc": "string",
      "url": "https://youtube.com/...",
      "category": "Rotina Básica|Proteção Solar|Ativos e Produtos|Problemas Comuns"
    }
  ],
  "tips": ["string", "string", "..."],
  "skincare_guide": {
    "steps": ["Demaquilante", "Sabonete", "Esfoliante", "Tônico", "Sérum", "Tratamento Noturno", "Hidratante", "Protetor Solar"],
    "skin_types": ["Normal", "Seca", "Oleosa", "Mista", "Sensível", "Acneica", "Madura", "Com Melasma"],
    "data": {
      "Normal": {
        "Demaquilante": "Água micelar, Bioderma sensibio ou cleansing oil...",
        "Sabonete": "Neutrogena Hydroboost gel de limpeza ou Cerave...",
        "...": "..."
      },
      "Seca": { "...": "..." },
      "...": {}
    }
  },
  "analyses": []
}
```

---

## Screens

### 1. Dashboard

Cards with key metrics:
- Total de análises realizadas
- Produtos cadastrados
- Vídeos cadastrados
- Dicas ativas
- Último acesso ao admin

### 2. Produtos

- Table listing all products (name, brand, category, price, tag)
- "Novo Produto" button opens form modal
- Edit/delete buttons per row
- Form fields: nome, marca, preço, preço antigo, categoria (select), tamanhos (comma-separated), descrição (textarea), como usar (textarea), rating, reviews, tag (lançamento checkbox)

### 3. Vídeos

- Table listing all videos (title, category, URL)
- "Novo Vídeo" button opens form modal
- Edit/delete per row
- Form fields: título, descrição, URL YouTube, categoria (select)
- Auto-generate thumbnail from YouTube URL

### 4. Dicas do Dia

- Simple list of text strings
- Add new tip (text input + add button)
- Reorder via up/down arrows
- Delete per item

### 5. Guia de Rotinas

Two views:

**Visão Tabela:** Full matrix view (read-only overview)
- Rows = steps (Demaquilante, Sabonete, etc.)
- Columns = skin types (Normal, Seca, Oleosa, etc.)
- Each cell shows product recommendations
- Horizontal scroll for mobile

**Visão por Tipo:** Editable per skin type
- Select skin type from dropdown
- Shows all 8-10 steps for that type
- Each step is an editable textarea with product recommendations
- Save button per type

### 6. Análises

- Read-only table of analyses stored in the system
- Columns: date, fitzpatrick type, skin type, score, number of findings
- Click to expand and see full report details

### 7. Configurações

- App name (text input)
- Greeting text customization
- Default city for UV fallback (lat/lon)

---

## Integration with User App

The admin data replaces hardcoded data in `index.html`:

1. **Products:** App fetches `/api/admin/data` and uses `products` array instead of hardcoded `PRODUCTS`
2. **Videos:** App uses `videos` array instead of hardcoded `LESSONS`
3. **Tips:** App uses `tips` array instead of hardcoded `TIPS`
4. **Skincare Guide:** After analysis identifies skin type, app shows the matching column from the guide
5. **Analyses:** Each analysis result is also saved to admin data for the dashboard

Fallback: if admin data is empty/unavailable, app uses hardcoded defaults.

---

## File Structure

```
templates/
  index.html      (existing user app)
  admin.html      (new admin panel)
api.py            (add /admin route + /api/admin/* endpoints)
```

---

## Implementation Priority

1. Admin HTML with sidebar + navigation
2. Data API endpoints (GET/PUT)
3. Products CRUD
4. Videos CRUD
5. Tips management
6. Skincare Guide (table + per-type editor)
7. Dashboard metrics
8. Analyses viewer
9. Settings
10. Connect user app to admin data API

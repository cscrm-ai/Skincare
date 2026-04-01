# Skin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the single-screen SkinCare AI app into a 5-tab mobile dashboard with Home, Scan, Routine, Wishlist (placeholder), and Profile screens.

**Architecture:** Single HTML file served by FastAPI with screen-based navigation via JavaScript. All user data persists in localStorage. One new backend endpoint (`/api/uv`) proxies the Open-Meteo UV API.

**Tech Stack:** FastAPI (Python), HTML/CSS/JS (vanilla), localStorage, Open-Meteo API, Iconify icons.

**Spec:** `docs/superpowers/specs/2026-03-31-skin-dashboard-design.md`

---

### Task 1: UV Proxy Endpoint

**Files:**
- Modify: `api.py` (add `/api/uv` endpoint)

- [ ] **Step 1: Add httpx dependency**

Run: `uv add httpx`

- [ ] **Step 2: Add UV endpoint to api.py**

Add after the `/health` endpoint in `api.py`:

```python
import httpx

WEATHER_CODES = {
    0: "Ceu limpo", 1: "Predominantemente limpo", 2: "Parcialmente nublado",
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
    if uv <= 10: return "Muito alto. Evite exposicao entre 10h-16h. FPS 50+."
    return "Extremo. Evite o sol. FPS 50+ obrigatorio."

@app.get("/api/uv")
async def get_uv(lat: float, lon: float):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=uv_index,temperature_2m,weather_code"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            data = resp.json()
        current = data.get("current", {})
        uv = current.get("uv_index", 0)
        return {
            "uv_index": uv,
            "temperature": current.get("temperature_2m", 0),
            "weather_description": WEATHER_CODES.get(current.get("weather_code", 0), "Desconhecido"),
            "recommendation": _uv_recommendation(uv),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
```

- [ ] **Step 3: Test endpoint locally**

Run: `curl "http://localhost:8000/api/uv?lat=-23.55&lon=-46.63"` (Sao Paulo)
Expected: JSON with uv_index, temperature, weather_description, recommendation

- [ ] **Step 4: Remove unused history endpoints from api.py**

Delete the `/history` GET and `/history/{idx}` DELETE endpoints — history is now client-side only.

- [ ] **Step 5: Commit**

```bash
git add api.py pyproject.toml uv.lock
git commit -m "feat: add UV proxy endpoint, remove server-side history"
```

---

### Task 2: localStorage Data Layer (JavaScript)

**Files:**
- Modify: `templates/index.html` (add JS module at bottom of `<script>`)

- [ ] **Step 1: Add storage helper functions**

Add at the TOP of the `<script>` tag in index.html, before any existing code:

```javascript
// ── Storage Layer ──
const Store = {
  _get(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; }
    catch { return fallback; }
  },
  _set(key, val) { localStorage.setItem(key, JSON.stringify(val)); },

  // Profile
  getProfile() { return this._get('profile', { name:'', age:0, fitzpatrick:'', skin_type:'', sensitivity:'', sunscreen_interval_minutes:120 }); },
  setProfile(p) { this._set('profile', p); },

  // Analyses
  getAnalyses() { return this._get('analyses', []); },
  addAnalysis(a) {
    const list = this.getAnalyses();
    list.unshift(a);
    if (list.length > 20) list.length = 20;
    this._set('analyses', list);
  },
  deleteAnalysis(id) {
    this._set('analyses', this.getAnalyses().filter(a => a.id !== id));
  },
  getLastAnalysis() { return this.getAnalyses()[0] || null; },

  // Routine
  getRoutine() { return this._get('routine', { am:[], pm:[], custom_products:[] }); },
  setRoutine(r) { this._set('routine', r); },

  // Today state (resets daily)
  getToday() {
    const today = new Date().toISOString().slice(0,10);
    const stored = this._get('today', { date:'', checked_am:[], checked_pm:[], reapply_times:[] });
    if (stored.date !== today) return { date:today, checked_am:[], checked_pm:[], reapply_times:[] };
    return stored;
  },
  setToday(t) { this._set('today', t); },

  // Geolocation cache
  getLocation() { return this._get('location', null); },
  setLocation(loc) { this._set('location', loc); },

  // Daily tip index
  getTipIndex() { return this._get('daily_tip_index', 0); },
  setTipIndex(i) { this._set('daily_tip_index', i); },

  // Score calculation
  calcScore(findings) {
    let score = 100;
    (findings || []).forEach(f => {
      if (f.priority === 'PRIORITÁRIO') score -= 12;
      else if (f.priority === 'RECOMENDADO') score -= 6;
      else score -= 2;
    });
    return Math.max(0, Math.min(100, score));
  },

  clearAll() { localStorage.clear(); }
};
```

- [ ] **Step 2: Verify Store works in browser console**

Open `http://localhost:8000`, open DevTools console, run:
```
Store.getProfile()
Store.setProfile({name:'Test', age:25})
Store.getProfile().name === 'Test'
```
Expected: returns `true`

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: add localStorage data layer"
```

---

### Task 3: Multi-Screen Navigation + Bottom Nav Bar

**Files:**
- Modify: `templates/index.html` (restructure HTML + CSS + JS)

- [ ] **Step 1: Add bottom nav CSS**

Add to the `<style>` block:

```css
/* Bottom Nav */
.bottom-nav{
  position:fixed;bottom:0;left:0;right:0;z-index:100;
  display:flex;justify-content:space-around;align-items:center;
  padding:.5rem 0 calc(.5rem + env(safe-area-inset-bottom));
  background:rgba(2,2,5,.85);backdrop-filter:blur(30px);-webkit-backdrop-filter:blur(30px);
  border-top:1px solid rgba(255,255,255,.08);
}
.nav-tab{
  display:flex;flex-direction:column;align-items:center;gap:.25rem;
  padding:.5rem .75rem;border-radius:1rem;cursor:pointer;transition:all .3s;
  background:none;border:none;color:rgba(255,255,255,.35);font-size:.6rem;
  font-family:'Space Mono',monospace;text-transform:uppercase;letter-spacing:.05em;
}
.nav-tab.active{color:#fff}
.nav-tab.active iconify-icon{filter:drop-shadow(0 0 8px rgba(79,70,229,.6))}
.nav-tab iconify-icon{font-size:1.4rem;transition:all .3s}

/* Adjust container for bottom nav */
.container{padding-bottom:5rem}
```

- [ ] **Step 2: Replace header nav pills with bottom nav bar**

Remove the existing `<nav class="nav-pills">` from the header. Simplify header to just logo + title.

Add before `</body>`:

```html
<nav class="bottom-nav">
  <button class="nav-tab active" onclick="navigate('home')">
    <iconify-icon icon="solar:home-smile-bold" width="22"></iconify-icon>Home
  </button>
  <button class="nav-tab" onclick="navigate('scan')">
    <iconify-icon icon="solar:camera-bold" width="22"></iconify-icon>Scan
  </button>
  <button class="nav-tab" onclick="navigate('routine')">
    <iconify-icon icon="solar:checklist-bold" width="22"></iconify-icon>Rotina
  </button>
  <button class="nav-tab" onclick="navigate('wishlist')">
    <iconify-icon icon="solar:heart-bold" width="22"></iconify-icon>Wishlist
  </button>
  <button class="nav-tab" onclick="navigate('profile')">
    <iconify-icon icon="solar:user-bold" width="22"></iconify-icon>Perfil
  </button>
</nav>
```

- [ ] **Step 3: Add screen containers for all tabs**

Replace the existing screen divs with 5 new screen sections. Keep the existing upload/loading/results content but nest it inside `screen-scan`. Add empty shells for the others:

```html
<!-- Screen: Home -->
<div id="screen-home" class="screen active">
  <div id="home-content"></div>
</div>

<!-- Screen: Scan (existing upload/loading/results restructured) -->
<div id="screen-scan" class="screen">
  <!-- existing upload, loading, results content moves here -->
</div>

<!-- Screen: Routine -->
<div id="screen-routine" class="screen">
  <div id="routine-content"></div>
</div>

<!-- Screen: Wishlist (placeholder) -->
<div id="screen-wishlist" class="screen">
  <div class="empty-state" style="padding:4rem">
    <iconify-icon icon="solar:heart-linear" width="64" style="display:block;margin:0 auto 1rem;color:rgba(255,255,255,.2)"></iconify-icon>
    <h2 style="font-size:1.2rem;font-weight:400;margin-bottom:.5rem">Em breve!</h2>
    <p style="color:rgba(255,255,255,.35);font-size:.85rem">Aqui voce podera salvar produtos recomendados pela IA.</p>
  </div>
</div>

<!-- Screen: Profile -->
<div id="screen-profile" class="screen">
  <div id="profile-content"></div>
</div>
```

- [ ] **Step 4: Add navigate() function**

Replace the existing `showScreen()` function:

```javascript
function navigate(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-' + name).classList.add('active');
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  const tabs = ['home','scan','routine','wishlist','profile'];
  const idx = tabs.indexOf(name);
  if (idx >= 0) document.querySelectorAll('.nav-tab')[idx].classList.add('active');
  window.scrollTo(0, 0);

  // Render screen content on navigation
  if (name === 'home') renderHome();
  if (name === 'routine') renderRoutine();
  if (name === 'profile') renderProfile();
}
```

- [ ] **Step 5: Verify navigation works**

Reload page. Tap each tab. Each should show its screen. Home is default.

- [ ] **Step 6: Commit**

```bash
git add templates/index.html
git commit -m "feat: add bottom nav bar and multi-screen navigation"
```

---

### Task 4: Home Dashboard Screen

**Files:**
- Modify: `templates/index.html` (add `renderHome()` function + daily tips array)

- [ ] **Step 1: Add daily tips array**

```javascript
const DAILY_TIPS = [
  "Protetor solar e a base de qualquer protocolo de skincare.",
  "Vitamina C pela manha potencializa a protecao solar.",
  "Retinol so deve ser usado a noite — nunca com sol.",
  "Pele oleosa tambem precisa de hidratacao — use texturas leves.",
  "Niacinamida ajuda a controlar oleosidade e reduzir poros.",
  "Agua micelar e otima para limpeza rapida, mas nao substitui o sabonete.",
  "Esfoliacao excessiva danifica a barreira cutanea.",
  "Acido hialuronico funciona melhor em pele umida.",
  "Toque o minimo possivel no rosto durante o dia.",
  "Troque a fronha do travesseiro pelo menos 2x por semana.",
  "SPF do protetor diminui com o tempo — reaplique a cada 2h.",
  "Estresse cronico piora acne e dermatites.",
  "Alimentacao rica em antioxidantes melhora a saude da pele.",
  "O contorno dos olhos tem pele mais fina — use produtos especificos.",
  "Limpar o celular regularmente evita acne na bochecha.",
];
```

- [ ] **Step 2: Add renderHome() function**

```javascript
async function renderHome() {
  const profile = Store.getProfile();
  const last = Store.getLastAnalysis();
  const today = Store.getToday();
  const routine = Store.getRoutine();
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite';
  const tipIdx = Math.floor(Date.now() / 86400000) % DAILY_TIPS.length;

  const score = last ? last.score : '--';
  const daysSince = last ? Math.floor((Date.now() - new Date(last.date).getTime()) / 86400000) : null;

  // Current routine based on time
  const isAM = hour < 14;
  const steps = isAM ? routine.am : routine.pm;
  const checked = isAM ? today.checked_am : today.checked_pm;

  let html = `
    <div style="margin-bottom:1.5rem">
      <h1 class="text-glow" style="font-size:2rem;font-weight:500;letter-spacing:-.03em">${greeting}${profile.name ? ', ' + profile.name : ''}</h1>
      <p style="color:rgba(255,255,255,.4);font-size:.85rem;margin-top:.25rem">
        ${profile.fitzpatrick ? 'Fototipo ' + profile.fitzpatrick + ' · ' : ''}${profile.skin_type || 'Configure seu perfil'}
      </p>
    </div>

    <!-- UV Card -->
    <div id="uv-card" class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem">
      <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem">
        <iconify-icon icon="solar:sun-bold" width="24" style="color:#fbbf24"></iconify-icon>
        <span class="font-mono" style="font-size:.7rem;color:rgba(255,255,255,.4)">INDICE UV</span>
      </div>
      <div id="uv-data" style="color:rgba(255,255,255,.5);font-size:.85rem">Carregando localizacao...</div>
    </div>

    <!-- Sunscreen Timer -->
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem">
      <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.75rem">
        <iconify-icon icon="solar:shield-check-bold" width="24" style="color:#4f46e5"></iconify-icon>
        <span class="font-mono" style="font-size:.7rem;color:rgba(255,255,255,.4)">PROTETOR SOLAR</span>
      </div>
      <div id="home-timer" style="font-size:2rem;font-weight:300;font-family:'Space Mono',monospace;margin-bottom:.5rem">--:--:--</div>
      <button class="btn btn-primary" onclick="reapplySunscreen()" style="width:100%">Reaplicei!</button>
      ${today.reapply_times.length ? '<div style="margin-top:.5rem;font-size:.7rem;color:rgba(255,255,255,.3)">Hoje: ' + today.reapply_times.join(' · ') + '</div>' : ''}
    </div>

    <!-- Routine Quick View -->
    ${steps.length ? `
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem">
        <div style="display:flex;align-items:center;gap:.75rem">
          <iconify-icon icon="solar:checklist-bold" width="24" style="color:#34d399"></iconify-icon>
          <span class="font-mono" style="font-size:.7rem;color:rgba(255,255,255,.4)">ROTINA ${isAM ? 'MANHA' : 'NOITE'}</span>
        </div>
        <span style="font-size:.75rem;color:rgba(255,255,255,.3)">${checked.length}/${steps.length}</span>
      </div>
      ${steps.map((s, i) => `
        <div onclick="toggleHomeCheck(${i}, ${isAM})" style="display:flex;align-items:center;gap:.75rem;padding:.5rem 0;cursor:pointer;border-bottom:1px solid rgba(255,255,255,.05)">
          <span style="width:20px;height:20px;border-radius:6px;border:2px solid ${checked.includes(i) ? '#34d399' : 'rgba(255,255,255,.15)'};background:${checked.includes(i) ? 'rgba(52,211,153,.2)' : 'transparent'};display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0">${checked.includes(i) ? '✓' : ''}</span>
          <span style="font-size:.85rem;color:${checked.includes(i) ? 'rgba(255,255,255,.35)' : 'rgba(255,255,255,.7)'};${checked.includes(i) ? 'text-decoration:line-through' : ''}">${s}</span>
        </div>
      `).join('')}
    </div>` : ''}

    <!-- Daily Tip -->
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem">
      <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem">
        <iconify-icon icon="solar:lightbulb-bolt-bold" width="24" style="color:#fbbf24"></iconify-icon>
        <span class="font-mono" style="font-size:.7rem;color:rgba(255,255,255,.4)">DICA DO DIA</span>
      </div>
      <p style="font-size:.85rem;color:rgba(255,255,255,.6);font-style:italic;line-height:1.5">"${DAILY_TIPS[tipIdx]}"</p>
    </div>

    <!-- Skin Score -->
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem;text-align:center" onclick="navigate('scan')" style="cursor:pointer">
      <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.75rem;justify-content:center">
        <iconify-icon icon="solar:heart-pulse-bold" width="24" style="color:#db2777"></iconify-icon>
        <span class="font-mono" style="font-size:.7rem;color:rgba(255,255,255,.4)">SAUDE DA PELE</span>
      </div>
      <div style="font-size:3rem;font-weight:300;font-family:'Space Mono',monospace;margin-bottom:.25rem">${score}<span style="font-size:1rem;color:rgba(255,255,255,.3)">/100</span></div>
      ${daysSince !== null ? `<div style="font-size:.75rem;color:rgba(255,255,255,.3)">Ultima analise: ha ${daysSince === 0 ? 'hoje' : daysSince + ' dia(s)'}</div>` : '<div style="font-size:.75rem;color:rgba(255,255,255,.3)">Nenhuma analise ainda</div>'}
      <button class="btn btn-primary" style="margin-top:.75rem" onclick="event.stopPropagation();navigate('scan')">
        <iconify-icon icon="solar:camera-bold" width="18"></iconify-icon> Nova Analise
      </button>
    </div>
  `;

  document.getElementById('home-content').innerHTML = html;
  loadUV();
  startSunscreenTimer();
}
```

- [ ] **Step 3: Add UV loading and sunscreen timer functions**

```javascript
async function loadUV() {
  const uvData = document.getElementById('uv-data');
  if (!uvData) return;

  let loc = Store.getLocation();
  if (!loc && navigator.geolocation) {
    try {
      const pos = await new Promise((res, rej) => navigator.geolocation.getCurrentPosition(res, rej, {timeout:5000}));
      loc = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      Store.setLocation(loc);
    } catch { uvData.textContent = 'Localizacao indisponivel'; return; }
  }
  if (!loc) { uvData.textContent = 'Localizacao indisponivel'; return; }

  try {
    const res = await fetch(`/api/uv?lat=${loc.lat}&lon=${loc.lon}`);
    const data = await res.json();
    const colors = ['#34d399','#34d399','#fbbf24','#fbbf24','#f97316','#f97316','#ef4444','#ef4444','#dc2626','#dc2626','#991b1b','#991b1b'];
    const color = colors[Math.min(Math.floor(data.uv_index), 11)];
    uvData.innerHTML = `
      <div style="display:flex;align-items:baseline;gap:.5rem;margin-bottom:.25rem">
        <span style="font-size:2.5rem;font-weight:300;font-family:'Space Mono',monospace;color:${color}">${data.uv_index.toFixed(1)}</span>
        <span style="font-size:.85rem;color:rgba(255,255,255,.5)">${data.temperature}°C · ${data.weather_description}</span>
      </div>
      <div style="font-size:.8rem;color:rgba(255,255,255,.5)">${data.recommendation}</div>
    `;
  } catch { uvData.textContent = 'Erro ao carregar UV'; }
}

let timerInterval = null;
function startSunscreenTimer() {
  if (timerInterval) clearInterval(timerInterval);
  const el = document.getElementById('home-timer');
  if (!el) return;
  const profile = Store.getProfile();
  const intervalMs = (profile.sunscreen_interval_minutes || 120) * 60 * 1000;
  const today = Store.getToday();
  const lastReapply = today.reapply_times.length
    ? new Date(today.date + 'T' + today.reapply_times[today.reapply_times.length - 1] + ':00').getTime()
    : null;

  timerInterval = setInterval(() => {
    if (!lastReapply) { el.textContent = 'Aplicar agora!'; return; }
    const remaining = intervalMs - (Date.now() - lastReapply);
    if (remaining <= 0) { el.textContent = 'Hora de reaplicar!'; el.style.color = '#ef4444'; return; }
    el.style.color = '#fff';
    const h = Math.floor(remaining / 3600000);
    const m = Math.floor((remaining % 3600000) / 60000);
    const s = Math.floor((remaining % 60000) / 1000);
    el.textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  }, 1000);
}

function reapplySunscreen() {
  const today = Store.getToday();
  const now = new Date();
  today.reapply_times.push(String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0'));
  Store.setToday(today);
  renderHome();
}

function toggleHomeCheck(idx, isAM) {
  const today = Store.getToday();
  const arr = isAM ? today.checked_am : today.checked_pm;
  const pos = arr.indexOf(idx);
  if (pos >= 0) arr.splice(pos, 1); else arr.push(idx);
  Store.setToday(today);
  renderHome();
}
```

- [ ] **Step 4: Call renderHome on page load**

At the end of the `<script>`, add: `renderHome();`

- [ ] **Step 5: Verify Home renders with all cards**

Reload page. Should see greeting, UV card (loading), timer, daily tip, score card.

- [ ] **Step 6: Commit**

```bash
git add templates/index.html
git commit -m "feat: implement Home dashboard with UV, timer, routine, tip, score"
```

---

### Task 5: Enhanced Scan Screen (History + Score + Save Routine)

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Update submitAnalysis to save to localStorage**

Replace the existing `submitAnalysis` function. After receiving the response, calculate score, save to Store, and update profile:

```javascript
async function submitAnalysis() {
  if (!selectedFile) return;
  navigate('loading');
  // Show loading screen manually since it's a sub-screen of scan
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-loading').classList.add('active');

  const form = new FormData();
  form.append('image', selectedFile);
  try {
    const res = await fetch('/analyze', { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text();
      throw new Error('Servidor retornou erro ' + res.status + ': ' + text.slice(0, 200));
    }
    const data = await res.json();
    data.image_url = document.getElementById('preview-img').src;

    // Calculate score and save
    const score = Store.calcScore(data.findings);
    const analysis = {
      id: crypto.randomUUID(),
      date: new Date().toISOString(),
      image_data: data.image_url,
      score: score,
      report: data
    };
    Store.addAnalysis(analysis);

    // Update profile from analysis
    const profile = Store.getProfile();
    profile.fitzpatrick = data.fitzpatrick_type || profile.fitzpatrick;
    profile.skin_type = data.skin_type || profile.skin_type;
    Store.setProfile(profile);

    currentReport = { ...data, score };
    renderResults(currentReport);
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-results').classList.add('active');
  } catch (err) {
    alert('Erro na analise: ' + err.message);
    navigate('scan');
  }
}
```

- [ ] **Step 2: Add scan history section to scan screen**

Add a `renderScanHistory()` function that shows horizontal thumbnail cards:

```javascript
function renderScanHistory() {
  const analyses = Store.getAnalyses();
  const container = document.getElementById('scan-history');
  if (!container) return;
  if (!analyses.length) { container.innerHTML = ''; return; }

  container.innerHTML = `
    <div style="margin-top:2rem">
      <h3 style="font-size:.7rem;font-family:'Space Mono',monospace;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem">Ultimos Scans</h3>
      <div style="display:flex;gap:.75rem;overflow-x:auto;padding-bottom:.5rem">
        ${analyses.map(a => `
          <div onclick='viewAnalysis("${a.id}")' style="flex-shrink:0;width:120px;cursor:pointer;border-radius:1rem;overflow:hidden;border:1px solid rgba(255,255,255,.08);transition:all .3s">
            <img src="${a.image_data}" style="width:120px;height:90px;object-fit:cover"/>
            <div style="padding:.5rem;text-align:center">
              <div style="font-size:1.1rem;font-weight:600;font-family:'Space Mono',monospace">${a.score}</div>
              <div style="font-size:.6rem;color:rgba(255,255,255,.3)">${new Date(a.date).toLocaleDateString('pt-BR')}</div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function viewAnalysis(id) {
  const a = Store.getAnalyses().find(x => x.id === id);
  if (!a) return;
  currentReport = { ...a.report, image_url: a.image_data, score: a.score };
  renderResults(currentReport);
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-results').classList.add('active');
}
```

- [ ] **Step 3: Add "Save as my routine" button to results**

Inside `renderResults()`, after the AM/PM routine cards, add:

```javascript
// At the end of renderResults, add save routine button
function saveAsRoutine() {
  if (!currentReport) return;
  const amSteps = (currentReport.am_routine || '').split(/\d+\.\s*/).filter(Boolean).map(s => s.trim());
  const pmSteps = (currentReport.pm_routine || '').split(/\d+\.\s*/).filter(Boolean).map(s => s.trim());
  const routine = Store.getRoutine();
  routine.am = amSteps;
  routine.pm = pmSteps;
  Store.setRoutine(routine);
  alert('Rotina salva com sucesso!');
  navigate('routine');
}
```

Add button HTML inside renderResults after routine cards:
```html
<button class="btn btn-primary" style="width:100%;margin-top:1rem" onclick="saveAsRoutine()">
  <iconify-icon icon="solar:checklist-bold" width="18"></iconify-icon> Salvar como minha rotina
</button>
```

- [ ] **Step 4: Add score badge to results header**

In `renderResults()`, add score display next to fitzpatrick type.

- [ ] **Step 5: Verify scan flow end to end**

Upload image → analyze → see score + save routine button → check history appears.

- [ ] **Step 6: Commit**

```bash
git add templates/index.html
git commit -m "feat: scan history, score, save routine from results"
```

---

### Task 6: Routine Screen

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Add renderRoutine() function**

```javascript
function renderRoutine() {
  const routine = Store.getRoutine();
  const today = Store.getToday();
  const profile = Store.getProfile();
  const isAM = new Date().getHours() < 14;

  const allSteps = (period) => {
    const base = period === 'am' ? routine.am : routine.pm;
    const custom = routine.custom_products.filter(p => p.when === period || p.when === 'both').map(p => p.name);
    return [...base, ...custom];
  };

  const renderChecklist = (period) => {
    const steps = allSteps(period);
    const checked = period === 'am' ? today.checked_am : today.checked_pm;
    if (!steps.length) return '<div style="text-align:center;padding:2rem;color:rgba(255,255,255,.3)">Faca uma analise para gerar sua rotina</div>';

    return steps.map((s, i) => `
      <div onclick="toggleRoutineCheck(${i}, '${period}')" style="display:flex;align-items:center;gap:.75rem;padding:.75rem;cursor:pointer;border-radius:1rem;margin-bottom:.5rem;background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);transition:all .3s">
        <span style="width:24px;height:24px;border-radius:8px;border:2px solid ${checked.includes(i) ? '#34d399' : 'rgba(255,255,255,.15)'};background:${checked.includes(i) ? 'rgba(52,211,153,.2)' : 'transparent'};display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0">${checked.includes(i) ? '✓' : ''}</span>
        <span style="font-size:.9rem;color:${checked.includes(i) ? 'rgba(255,255,255,.35)' : '#fff'};${checked.includes(i) ? 'text-decoration:line-through' : ''}">${s}</span>
      </div>
    `).join('');
  };

  document.getElementById('routine-content').innerHTML = `
    <h2 style="font-size:1.5rem;font-weight:500;letter-spacing:-.02em;margin-bottom:1rem">Minha Rotina</h2>

    <div style="display:flex;gap:.5rem;margin-bottom:1.5rem">
      <button id="tab-am" class="btn ${isAM ? 'btn-primary' : ''}" onclick="switchRoutineTab('am')">Manha</button>
      <button id="tab-pm" class="btn ${!isAM ? 'btn-primary' : ''}" onclick="switchRoutineTab('pm')">Noite</button>
    </div>

    <div id="routine-checklist">${renderChecklist(isAM ? 'am' : 'pm')}</div>

    <div style="margin-top:.5rem;margin-bottom:1.5rem">
      <div style="height:4px;background:rgba(255,255,255,.05);border-radius:2px;overflow:hidden">
        <div id="routine-progress" style="height:100%;background:#34d399;border-radius:2px;transition:width .3s;width:${allSteps(isAM ? 'am' : 'pm').length ? ((isAM ? today.checked_am : today.checked_pm).length / allSteps(isAM ? 'am' : 'pm').length * 100) : 0}%"></div>
      </div>
    </div>

    <!-- Reapply Timer -->
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1.5rem;text-align:center">
      <div style="display:flex;align-items:center;gap:.75rem;justify-content:center;margin-bottom:.75rem">
        <iconify-icon icon="solar:shield-check-bold" width="24" style="color:#4f46e5"></iconify-icon>
        <span class="font-mono" style="font-size:.7rem;color:rgba(255,255,255,.4)">REAPLICACAO DE PROTETOR</span>
      </div>
      <div id="routine-timer" style="font-size:3rem;font-weight:300;font-family:'Space Mono',monospace;margin-bottom:.75rem">--:--:--</div>
      <button class="btn btn-primary" onclick="reapplySunscreen();renderRoutine()" style="width:100%">Reaplicei!</button>
      ${today.reapply_times.length ? '<div style="margin-top:.75rem;font-size:.75rem;color:rgba(255,255,255,.3)">Hoje: ' + today.reapply_times.join(' · ') + '</div>' : ''}
    </div>

    <!-- Add Product -->
    <button class="btn" onclick="showAddProduct()" style="width:100%">
      <iconify-icon icon="solar:add-circle-linear" width="18"></iconify-icon> Adicionar produto
    </button>

    <div id="add-product-modal" style="display:none;margin-top:1rem" class="glass-panel" style="border-radius:1.5rem;padding:1.25rem">
    </div>
  `;

  // Reuse timer from home
  startRoutineTimer();
}

let routineTab = null;
function switchRoutineTab(period) {
  routineTab = period;
  renderRoutine();
}

function toggleRoutineCheck(idx, period) {
  const today = Store.getToday();
  const arr = period === 'am' ? today.checked_am : today.checked_pm;
  const pos = arr.indexOf(idx);
  if (pos >= 0) arr.splice(pos, 1); else arr.push(idx);
  Store.setToday(today);
  renderRoutine();
}

function startRoutineTimer() {
  const el = document.getElementById('routine-timer');
  if (!el) return;
  const profile = Store.getProfile();
  const intervalMs = (profile.sunscreen_interval_minutes || 120) * 60 * 1000;
  const today = Store.getToday();
  const lastReapply = today.reapply_times.length
    ? new Date(today.date + 'T' + today.reapply_times[today.reapply_times.length - 1] + ':00').getTime()
    : null;

  const update = () => {
    if (!lastReapply) { el.textContent = 'Aplicar agora!'; return; }
    const remaining = intervalMs - (Date.now() - lastReapply);
    if (remaining <= 0) { el.textContent = 'Hora de reaplicar!'; el.style.color = '#ef4444'; return; }
    el.style.color = '#fff';
    const h = Math.floor(remaining / 3600000);
    const m = Math.floor((remaining % 3600000) / 60000);
    const s = Math.floor((remaining % 60000) / 1000);
    el.textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  };
  update();
  setInterval(update, 1000);
}

function showAddProduct() {
  const modal = document.getElementById('add-product-modal');
  if (!modal) return;
  modal.style.display = 'block';
  modal.innerHTML = `
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-top:1rem">
      <h3 style="font-size:.85rem;margin-bottom:.75rem">Novo Produto</h3>
      <input id="product-name" placeholder="Nome do produto" style="width:100%;padding:.5rem;border-radius:.5rem;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:#fff;margin-bottom:.5rem;font-family:inherit"/>
      <div style="display:flex;gap:.5rem;margin-bottom:.75rem">
        <label style="font-size:.8rem;color:rgba(255,255,255,.5)"><input type="radio" name="when" value="am" checked/> Manha</label>
        <label style="font-size:.8rem;color:rgba(255,255,255,.5)"><input type="radio" name="when" value="pm"/> Noite</label>
        <label style="font-size:.8rem;color:rgba(255,255,255,.5)"><input type="radio" name="when" value="both"/> Ambos</label>
      </div>
      <div style="display:flex;gap:.5rem">
        <button class="btn btn-primary" onclick="addProduct()">Adicionar</button>
        <button class="btn" onclick="document.getElementById('add-product-modal').style.display='none'">Cancelar</button>
      </div>
    </div>
  `;
}

function addProduct() {
  const name = document.getElementById('product-name').value.trim();
  if (!name) return;
  const when = document.querySelector('input[name=when]:checked').value;
  const routine = Store.getRoutine();
  routine.custom_products.push({ name, when });
  Store.setRoutine(routine);
  renderRoutine();
}
```

- [ ] **Step 2: Verify routine screen**

Navigate to Rotina tab. Should show empty state if no routine saved, or checklist if routine exists.

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: implement Routine screen with checklist, timer, add product"
```

---

### Task 7: Profile Screen

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Add renderProfile() function**

```javascript
function renderProfile() {
  const profile = Store.getProfile();
  const analyses = Store.getAnalyses();
  const today = Store.getToday();

  // Calculate streak
  let streak = 0;
  const todayChecks = today.checked_am.length + today.checked_pm.length;
  if (todayChecks > 0) streak = 1; // simplified for MVP

  const bestScore = analyses.length ? Math.max(...analyses.map(a => a.score)) : 0;

  document.getElementById('profile-content').innerHTML = `
    <h2 style="font-size:1.5rem;font-weight:500;letter-spacing:-.02em;margin-bottom:1.5rem">Meu Perfil</h2>

    <!-- Personal Info -->
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem">
      <h3 style="font-size:.7rem;font-family:'Space Mono',monospace;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem">Informacoes Pessoais</h3>
      <div style="display:flex;flex-direction:column;gap:.75rem">
        <div>
          <label style="font-size:.7rem;color:rgba(255,255,255,.35);display:block;margin-bottom:.25rem">Nome</label>
          <input value="${profile.name}" onchange="updateProfile('name', this.value)" placeholder="Seu nome" style="width:100%;padding:.5rem;border-radius:.5rem;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:#fff;font-family:inherit"/>
        </div>
        <div>
          <label style="font-size:.7rem;color:rgba(255,255,255,.35);display:block;margin-bottom:.25rem">Idade</label>
          <input type="number" value="${profile.age || ''}" onchange="updateProfile('age', parseInt(this.value))" placeholder="Idade" style="width:100%;padding:.5rem;border-radius:.5rem;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:#fff;font-family:inherit"/>
        </div>
      </div>
    </div>

    <!-- Skin Info (auto-filled) -->
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem">
        <h3 style="font-size:.7rem;font-family:'Space Mono',monospace;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.1em">Minha Pele</h3>
        <span style="font-size:.6rem;color:rgba(79,70,229,.6);background:rgba(79,70,229,.1);padding:.2rem .5rem;border-radius:4px">Via analise IA</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem">
        <div><span style="font-size:.7rem;color:rgba(255,255,255,.35)">Fototipo</span><div style="font-size:1rem;margin-top:.25rem">${profile.fitzpatrick || '--'}</div></div>
        <div><span style="font-size:.7rem;color:rgba(255,255,255,.35)">Tipo</span><div style="font-size:.85rem;margin-top:.25rem">${profile.skin_type || '--'}</div></div>
      </div>
    </div>

    <!-- Stats -->
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem">
      <h3 style="font-size:.7rem;font-family:'Space Mono',monospace;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem">Estatisticas</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;text-align:center">
        <div><div style="font-size:1.5rem;font-weight:300;font-family:'Space Mono',monospace">${analyses.length}</div><div style="font-size:.65rem;color:rgba(255,255,255,.35)">Analises</div></div>
        <div><div style="font-size:1.5rem;font-weight:300;font-family:'Space Mono',monospace">${analyses.length ? analyses[0].score : '--'}</div><div style="font-size:.65rem;color:rgba(255,255,255,.35)">Score Atual</div></div>
        <div><div style="font-size:1.5rem;font-weight:300;font-family:'Space Mono',monospace">${bestScore || '--'}</div><div style="font-size:.65rem;color:rgba(255,255,255,.35)">Melhor Score</div></div>
        <div><div style="font-size:1.5rem;font-weight:300;font-family:'Space Mono',monospace">${streak}</div><div style="font-size:.65rem;color:rgba(255,255,255,.35)">Dias Seguidos</div></div>
      </div>
    </div>

    <!-- Settings -->
    <div class="glass-panel" style="border-radius:1.5rem;padding:1.25rem;margin-bottom:1rem">
      <h3 style="font-size:.7rem;font-family:'Space Mono',monospace;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem">Configuracoes</h3>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem">
        <span style="font-size:.85rem">Intervalo protetor</span>
        <select onchange="updateProfile('sunscreen_interval_minutes', parseInt(this.value))" style="padding:.35rem .5rem;border-radius:.5rem;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:#fff;font-family:inherit">
          ${[60,90,120,150,180].map(v => `<option value="${v}" ${profile.sunscreen_interval_minutes === v ? 'selected' : ''}>${v/60}h</option>`).join('')}
        </select>
      </div>
    </div>

    <button class="btn btn-danger" style="width:100%" onclick="if(confirm('Tem certeza? Todos os dados serao apagados.')){Store.clearAll();renderProfile();}">
      <iconify-icon icon="solar:trash-bin-trash-linear" width="18"></iconify-icon> Limpar todos os dados
    </button>
  `;
}

function updateProfile(key, val) {
  const p = Store.getProfile();
  p[key] = val;
  Store.setProfile(p);
}
```

- [ ] **Step 2: Verify profile screen**

Navigate to Perfil. Fill name and age. Check they persist after navigating away and back.

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: implement Profile screen with info, stats, settings"
```

---

### Task 8: Integration Testing & Deploy

**Files:**
- All files

- [ ] **Step 1: Test full flow locally**

1. Start server: `uv run uvicorn api:app --reload --host 0.0.0.0 --port 8000`
2. Open on phone: `http://<local-ip>:8000`
3. Set name in Profile
4. Run a Scan → verify score + history thumbnail
5. Save routine → verify Rotina tab populated
6. Check Home dashboard has all cards populated
7. Test sunscreen timer reset
8. Test UV card loads

- [ ] **Step 2: Deploy to Vercel**

```bash
vercel deploy --prod --yes
```

- [ ] **Step 3: Test on production URL**

Repeat flow from step 1 on the Vercel URL.

- [ ] **Step 4: Final commit with any fixes**

```bash
git add -A
git commit -m "feat: complete Skin Dashboard MVP"
```

# Meta Ads Brief Generation System
## Hair Biolabs España — Plan Técnico Completo

> Versión: 1.0 | Estado: Pre-build | Fecha: Junio 2026

---

## VISIÓN GENERAL

Sistema automatizado que:
1. Conecta con Meta Ads API de Hair Biolabs España
2. Extrae y analiza los ads con mejor performance
3. Clasifica cada ad en uno de 5 formatos creativos propietarios
4. Genera un brief completo (estilo editorial + speech listo para grabar) para los 4 formatos restantes
5. Analiza los ads con peor performance y diagnostica por qué fallan
6. Exporta todo como Google Doc estructurado a una carpeta específica de Drive
7. Corre automáticamente cada día y también tiene trigger manual

---

## PRERREQUISITOS (resolver antes del build)

### Meta API Access
- **Business Manager:** Beryl Fane01 (Portfolio Comercial)
- **Ad Account:** `HAIR_BIO_01`
- **Ad Account ID:** `act_2217973965310655`
- **Page ID:** `345680515293269` (Hair Biolabs)

**Acción requerida antes de buildear:**
Uno de los dos admins con "Control total" (ADMIN Back Up Connie Abalada o BM ADMIN 01 - Ksenia Kocik) debe crear un **System User** en Business Manager con los siguientes permisos sobre `HAIR_BIO_01`:

```
- ads_read
- ads_management  
- business_management
- pages_read_engagement
- video_operations (para acceder a los creatives de video)
```

Pasos para el admin:
1. Business Settings > Usuarios > Usuarios del sistema
2. Crear nuevo System User (tipo: Admin)
3. Asignar a la Ad Account `HAIR_BIO_01` con role "Advertiser"
4. Generar token permanente con los permisos listados
5. Compartir el token con Diego de forma segura (no por Slack, usar 1Password o similar)

### Google API Access
- Reutilizar la misma Google Cloud App ya configurada para los Google Sheets de Shopify
- Necesita scope adicional: `https://www.googleapis.com/auth/drive` y `https://www.googleapis.com/auth/documents`
- Identificar el `folder_id` de la carpeta de Drive donde irán los briefs

### Seadance
- El sistema generará prompts detallados por segmento en texto
- Un miembro del equipo los ejecuta manualmente en Seadance
- Los prompts se incluyen dentro del Google Doc generado

---

## ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────────────┐
│                         SCHEDULER                                │
│              Cron diario (9:00 AM) + Trigger manual             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA 1: DATA INGESTION                        │
│                                                                  │
│  Meta Marketing API                                              │
│  ├── Descarga top 10 video ads por score de performance          │
│  ├── Métricas: CTR, ROAS, Hook Rate, ThruPlay, Spend, Días activo│
│  └── Descarga URL del creative (video) para cada ad             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  CAPA 2: MEDIA PROCESSING                        │
│                                                                  │
│  Por cada video:                                                 │
│  ├── Descarga video con yt-dlp                                   │
│  ├── Extrae 1 frame cada 5 segundos con ffmpeg                   │
│  └── Transcribe audio con Whisper API (OpenAI)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                CAPA 3: AI CLASSIFICATION ENGINE                  │
│                                                                  │
│  Input: frames + transcripción + métricas                        │
│  Modelo: Claude claude-sonnet-4-20250514 Vision                            │
│                                                                  │
│  Output por ad:                                                  │
│  ├── Formato creativo (1 de 5)                                   │
│  ├── Score de performance (algoritmo interno)                    │
│  ├── Deseo del avatar                                            │
│  ├── Situación del avatar                                        │
│  ├── Mecanismo revelado                                          │
│  ├── Nivel de awareness                                          │
│  ├── Villain del ad                                              │
│  ├── Estructura de segmentos con timestamps                      │
│  └── Clasificación: GANADOR / PERDEDOR / NEUTRO                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
┌───────────────────────┐ ┌─────────────────────────┐
│  GANADORES            │ │  PERDEDORES / NEUTROS    │
│  Brief Engine         │ │  Autopsy Engine          │
│                       │ │                          │
│  Genera briefs para   │ │  Diagnostica por qué     │
│  los 4 formatos       │ │  falló y propone         │
│  restantes            │ │  reformat + nuevo brief  │
└──────────┬────────────┘ └────────────┬─────────────┘
           │                           │
           └──────────────┬────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CAPA 4: GOOGLE DOC EXPORT                      │
│                                                                  │
│  Genera documento estructurado en Google Docs                    │
│  Sube a carpeta específica de Google Drive                       │
│  Nombre del doc: [FECHA] Brief — [Nombre del Ad Ganador]         │
└─────────────────────────────────────────────────────────────────┘
```

---

## CAPA 1: DATA INGESTION

### Endpoint principal
```
GET /v21.0/act_{ad_account_id}/ads
```

### Campos que se extraen por ad
```python
fields = [
    "id",
    "name",
    "status",
    "created_time",
    "creative{id,name,video_id,thumbnail_url,asset_feed_spec}",
    "adset{name,targeting}",
    "campaign{name,objective}",
    "insights{
        spend,
        impressions,
        clicks,
        ctr,
        purchase_roas,
        video_play_actions,
        video_thruplay_watched_actions,
        video_p25_watched_actions,
        video_p50_watched_actions,
        video_p75_watched_actions,
        video_p100_watched_actions,
        cost_per_action_type,
        date_start,
        date_stop
    }"
]
```

### Filtros aplicados
- Status: `ACTIVE` (solo ads corriendo)
- Date preset: `last_30_days`
- Solo ads de tipo `VIDEO`
- Ordenado por `spend DESC` para tomar el top 10

### Cálculo de Hook Rate
```python
hook_rate = video_play_actions_3s / impressions * 100
# Threshold ganador: >= 30%
```

---

## CAPA 2: ALGORITMO DE SCORING (Ganadores vs Perdedores)

### Fórmula del Performance Score

Cada ad recibe una puntuación de 0 a 100 basada en:

```python
def calculate_performance_score(ad_metrics):
    scores = {}
    
    # CTR (peso: 25%)
    # Benchmark Hair Biolabs España: comparado contra promedio de la cuenta
    ctr_score = normalize(ad_metrics['ctr'], min=0.5, max=4.0) * 25
    
    # ROAS (peso: 30%)
    # Threshold mínimo rentable: 2.0x, objetivo: 3.5x+
    roas_score = normalize(ad_metrics['purchase_roas'], min=1.0, max=5.0) * 30
    
    # Hook Rate — 3s views / impressions (peso: 20%)
    # Threshold ganador: 30%+
    hook_rate = ad_metrics['video_3s_views'] / ad_metrics['impressions']
    hook_score = normalize(hook_rate, min=0.10, max=0.50) * 20
    
    # Hold Rate — ThruPlays / impressions (peso: 15%)
    # Indica que el mensaje engancha hasta el final
    hold_rate = ad_metrics['thruplay'] / ad_metrics['impressions']
    hold_score = normalize(hold_rate, min=0.03, max=0.20) * 15
    
    # Días activo sin pausar (peso: 10%)
    # Proxy de rentabilidad: si Meta sigue gastando, está convirtiendo
    days_active = (today - ad_metrics['created_time']).days
    days_score = normalize(days_active, min=1, max=60) * 10
    
    total = ctr_score + roas_score + hook_score + hold_score + days_score
    return round(total, 2)
```

### Clasificación por score
```
>= 70  → GANADOR   (genera brief de nuevos formatos)
40-69  → NEUTRO    (monitorear, sin acción inmediata)
< 40   → PERDEDOR  (genera diagnóstico + brief reformateado)
```

---

## CAPA 3: CLASSIFICATION ENGINE

### Paso 1: Extracción de frames
```bash
# 1 frame cada 5 segundos, máximo 20 frames por video
ffmpeg -i {video_path} -vf "fps=1/5" -frames:v 20 frame_%03d.jpg
```

### Paso 2: Transcripción
```python
# Whisper API — modelo large-v3
# Idioma: es (español)
# Output: texto con timestamps por segmento
```

### Paso 3: Prompt al LLM (Clasificación de formato)

**System prompt:**
```
Eres un experto en creative strategy para Meta Ads, especializado en 
Direct Response y video advertising para el mercado español de 
Health & Beauty. Tu tarea es analizar ads de video y clasificarlos 
con precisión en uno de 5 formatos creativos propietarios.
```

**User prompt (simplificado):**
```
Analiza este ad de video de Hair Biolabs España.

TRANSCRIPCIÓN:
{transcription_with_timestamps}

FRAMES EXTRAÍDOS: [imágenes adjuntas]
MÉTRICAS: CTR: {ctr}% | ROAS: {roas}x | Hook Rate: {hook_rate}% | ThruPlay: {thruplay}%

FORMATOS DISPONIBLES:
[Los 5 formatos con sus definiciones completas del Excel]

Devuelve un JSON con:
{
  "formato_detectado": "nombre exacto del formato",
  "confianza": 0-100,
  "justificacion": "por qué es este formato, con timestamps específicos",
  "deseo_avatar": "...",
  "situacion_avatar": "...",
  "angulo_ganador": "...",
  "mecanismo": "...",
  "villain": "...",
  "nivel_awareness": "problem-aware | solution-aware | product-aware",
  "segmentos": [
    {"nombre": "Hook", "timestamp_inicio": "0:00", "timestamp_fin": "0:06", "descripcion": "..."},
    ...
  ],
  "elementos_que_funcionan": ["lista de elementos clave del ad"],
  "clasificacion_performance": "GANADOR | NEUTRO | PERDEDOR",
  "score": 0-100
}
```

---

## LOS 5 FORMATOS CREATIVOS

Estos son los formatos del sistema, extraídos del Excel de referencia.

### Formato 1: Reaction Style Hook x 3D Authority Mechanism (UGC Hybrid)
**Estructura:** Split-screen con creador en modo "Reaction Channel" (setup de micrófono, backdrop de podcast/consulta) + animación 3D médica/científica en la mitad inferior. El creador reacciona y comenta la animación, pivotando hacia el mecanismo del producto.
**Segmentos:**
- Hook (0-6s): Split-screen creador reaccionando + animación impactante
- Mecanismo Pivot (6-22s): Animación 3D del problema a nivel celular
- Prueba social + Reveal (22-33s): Before/after personal + producto físico
- Demostración + animación dual (33-52s): Aplicación + animación del mecanismo de acción
- Offer Stack + CTA (52s+): Stack de oferta con urgencia

**Señales de identificación:** setup de "React Channel", animación 3D simultánea, creador que ES el testimonio, lenguaje muy conversacional y de calle

### Formato 2: Anti-Product Paradigm Shift x Stage Classification Listicle
**Estructura:** Narrador de autoridad que invalida el acto de "comprar productos" como solución, pivotando hacia un sistema personalizado basado en el estadio del problema. Heavy uso de categorización y clasificación visual.
**Segmentos:**
- Hook (0-6s): Declaración que invalida la lógica del consumidor ("lo estás haciendo mal")
- Pain Matrix (6-15s): Carrusel de productos genéricos que han fallado
- Paradigm Shift (15-26s): La autoridad explica por qué todos los productos fallan (problema de categorización)
- Stage Classification (26-41s): Grid visual clasificando estadios del problema
- Brand Trust + CTA (41s+): Credenciales, escala, lead gen de bajo friction

**Señales de identificación:** narrador 50+, lenguaje clínico y empático, grids de categorización, CTA de consulta gratuita (no compra directa)

### Formato 3: Organic Podcast Leak x Scientific Bottleneck Education Framework
**Estructura:** Formato que simula un clip orgánico de podcast educativo. La narradora se posiciona como truth-teller de la industria. Descarta soluciones una por una antes de revelar el "bottleneck" científico real (un problema anatómico o fisiológico subterráneo) y el ingrediente/mecanismo que lo resuelve.
**Segmentos:**
- Hook (0-4s): Declaración de industria corrupta o verdad suprimida
- Alternative Rejection Carousel (4-15s): Descarte sistemático de soluciones comunes con X gráficos
- Bottleneck Education (15-34s): Explicación del problema fisiológico real que nadie explica
- Institutional Authority (34-54s): "Científicos de [institución]" descubren el compuesto clave
- Ingredient Stack (54-70s): Sinergia de ingredientes como listicle hablado
- Low-Friction Close (70s+): Precio bajo, garantía, CTA suave

**Señales de identificación:** setup de podcast o sofá casual, X rojos sobre competidores, metáfora biológica central ("no está muriendo, está hambrienta"), referencia a institución académica, precio ancla bajo al final

### Formato 4: The Salon Secret x Structural Cortical Degradation Hook
**Estructura:** Narrativa en primera persona de una consumidora real que descubrió la causa real de su problema a través de una figura de autoridad de proximidad (hairstylist, esteticista, farmacéutica de barrio) que le reveló algo que los médicos no detectan. Heavy on storytelling cinematográfico antes del pitch.
**Segmentos:**
- Hook + Reaction Blend (0-11s): Banner de alto impacto + creadora respondiendo
- Storyteller Introduction (11-26s): La narradora sitúa la historia en tiempo y lugar específico
- The Discovery Narrative (26-66s): B-roll del ambiente (salón, consulta) + el momento de revelación
- Anatomical Breakdown (66-109s): La figura de autoridad explica el problema a nivel celular/estructural
- Hidden Deficit Pitch (109-158s): El testimonio de la experta + setup del mineral/ingrediente oculto
- Cliffhanger + CTA: Termina con information asymmetry ("tu médico no lo mide")

**Señales de identificación:** storytelling en primera persona muy detallado, figura de autoridad de proximidad (no médico famoso), back-room isolation moment, 3D cross-section de cabello/piel, cliffhanger sin cierre completo en el video

### Formato 5: Emotional Agitation Montage x 650nm Cellular Photobiomodulation Reveal
**Estructura:** Los primeros 35-40 segundos son pura agitación emocional: montaje rápido de todos los pain points cotidianos del avatar. Luego pivota a autoridad científica extrema (dermatólogos, estudios peer-reviewed, wavelengths específicas). El contraste emocional/científico es el mecanismo central.
**Segmentos:**
- Demoralizing Hook (0-3s): Imagen clínica de daño máximo + texto de golpe emocional
- Relatable Defeat Montage (3-14s): Compilación rápida de UGC mostrando pain points diarios
- Treatment Rejection Loop (14-22s): Invalidación de soluciones con side effects específicos
- Gender/Identity Frame (22-38s): Contraste de cómo el problema afecta la identidad
- Scientific Epiphany (38-50s): Pivot a autoridad clínica, scanner, monitor de diagnóstico
- Biological Mechanism (50-65s): Animación 3D del problema a nivel celular
- Clinical Solution Reveal (65-77s+): Dermatólogo + device + wavelength específica + resultados

**Señales de identificación:** opening con imagen de daño máximo, montaje con 5+ clips de pain points, invalidación de Minoxidil u equivalente por nombre, contraste identitario (social), número de wavelength específico (650nm), citation de journal en pantalla

---

## CAPA 3B: BRIEF GENERATION ENGINE (para GANADORES)

### Lógica principal
Para cada ad GANADOR, se genera un brief por cada uno de los 4 formatos que NO es el formato original.

**Input del Brief Engine:**
```json
{
  "formato_original": "Formato 3: Organic Podcast Leak...",
  "deseo_avatar": "...",
  "situacion_avatar": "...",
  "angulo_ganador": "...",
  "mecanismo": "...",
  "villain": "...",
  "nivel_awareness": "problem-aware",
  "producto": "Hair Biolabs [nombre del producto específico]",
  "mercado": "España",
  "formatos_objetivo": ["Formato 1", "Formato 2", "Formato 4", "Formato 5"]
}
```

**Output por cada nuevo formato:**

```markdown
## [NOMBRE DEL FORMATO]

### Por qué este formato puede ganar
[2-3 párrafos de justificación estratégica: qué hace este formato 
que el original no hace, qué segmento del avatar captura mejor, 
por qué el mecanismo se traduce bien a este formato]

### Explicación del formato
[Descripción técnica de cómo se estructura el video: segmentos, 
tiempos, lógica narrativa]

### Estructura de segmentos
| Segmento | Tiempo | Descripción | Texto overlay |
|----------|--------|-------------|---------------|
| Hook     | 0-6s   | ...         | ...           |
| ...      | ...    | ...         | ...           |

### Speech completo (listo para grabar)
[Texto en párrafo corrido, en español de España, tal como lo 
diría el creador. Sin puntos de guión, flujo natural de habla]

### Prompts de Seadance por segmento
**Segmento 1 - Hook:**
Prompt: [Descripción visual ultra-detallada de la escena para 
generar con Seadance: encuadre, iluminación, actriz/actor, 
props, texto overlay, estética]

**Segmento 2 - [Nombre]:**
Prompt: [...]

[Un prompt por segmento clave del video]

### Notas de producción
[Especificaciones técnicas: ratio (9:16), duración objetivo, 
tipo de creador recomendado, props necesarios, setup de cámara]
```

---

## CAPA 3C: AUTOPSY ENGINE (para PERDEDORES)

### Diagnóstico de fallo

**Prompt al LLM:**
```
Analiza este ad de Hair Biolabs España que tiene bajo performance.

CLASIFICACIÓN: PERDEDOR (Score: {score}/100)
MÉTRICAS: CTR: {ctr}% | ROAS: {roas}x | Hook Rate: {hook_rate}% | ThruPlay: {thruplay}%
FORMATO DETECTADO: {formato}
TRANSCRIPCIÓN: {transcription}
FRAMES: [imágenes]

Diagnóstica exactamente por qué este ad falla. Analiza:
1. ¿El hook captura en 3 segundos? ¿Por qué sí o no?
2. ¿El nivel de awareness coincide con el formato?
3. ¿El mecanismo es creíble y específico?
4. ¿La oferta final está bien construida?
5. ¿El CTA es claro?
6. ¿El formato es el correcto para este mensaje?

Luego recomienda el mejor formato alternativo y justifica por qué 
ese formato convertiría mejor este mismo mensaje.

Devuelve JSON con:
{
  "fallos_detectados": ["lista específica de problemas"],
  "fallo_principal": "el problema más crítico",
  "formato_recomendado": "nombre del formato alternativo",
  "justificacion_cambio": "por qué este formato lo haría mejor",
  "elementos_rescatables": ["qué se puede mantener del ad original"]
}
```

**Output en el Doc:**
```markdown
## ANÁLISIS DE AD — BAJO PERFORMANCE

**Score:** {score}/100 | **Clasificación:** PERDEDOR

### Diagnóstico
**Fallo principal:** [descripción del problema más crítico]

**Fallos detectados:**
- [Fallo 1 con explicación específica]
- [Fallo 2 con explicación específica]
- [...]

### Propuesta de reforma
**Formato recomendado:** [Nombre del formato]
**Por qué funcionaría mejor:** [Justificación estratégica]

### Brief del ad reformateado
[Brief completo con el mismo contenido pero en el nuevo formato,
incluyendo speech + estructura de segmentos + prompts de Seadance]
```

---

## CAPA 4: GOOGLE DOC EXPORT

### Estructura del documento generado

```
[FECHA] | Análisis de Ads — Hair Biolabs España

═══════════════════════════════════════
RESUMEN EJECUTIVO
═══════════════════════════════════════
- Total ads analizados: X
- Ganadores identificados: X
- Perdedores identificados: X
- Briefs generados: X

═══════════════════════════════════════
PARTE 1: ADS GANADORES — BRIEFS NUEVOS
═══════════════════════════════════════

## Ad Ganador #1: [Nombre del ad]
Score: X/100 | Formato: [Nombre] | CTR: X% | ROAS: Xx

### Formato original detectado
[Análisis del ad ganador]

### Brief — Formato [X]: [Nombre]
[Brief completo]
[Prompts de Seadance por segmento]

### Brief — Formato [X]: [Nombre]
[...]

### Brief — Formato [X]: [Nombre]
[...]

### Brief — Formato [X]: [Nombre]
[...]

---

## Ad Ganador #2: [Nombre del ad]
[...]

═══════════════════════════════════════
PARTE 2: ADS CON BAJO PERFORMANCE
═══════════════════════════════════════

## Ad Perdedor #1: [Nombre del ad]
Score: X/100 | Formato: [Nombre] | CTR: X% | ROAS: Xx

### Diagnóstico
[...]

### Brief reformateado
[...]
```

### Naming convention de los docs
```
[YYYY-MM-DD] HairBiolabs ES — Brief Batch #{n}
```

### Carpeta de destino en Drive
```
Google Drive > [Carpeta específica de Hair Biolabs] > Briefs Generados > {año} > {mes}
```

---

## STACK TÉCNICO

| Componente | Herramienta | Justificación |
|---|---|---|
| Meta API | `facebook-business` Python SDK v21 | Oficial, estable |
| Video download | `yt-dlp` | Más robusto que youtube-dl para URLs de Meta |
| Frame extraction | `ffmpeg` | Estándar de industria |
| Audio transcription | OpenAI Whisper API (`whisper-1`) | Mejor accuracy para español |
| Vision + Classification | Claude claude-sonnet-4-20250514 (Vision) | Mejor reasoning para análisis de video frames |
| Brief Generation | Claude claude-sonnet-4-20250514 | Calidad de escritura necesaria para speech en español |
| Google Docs export | Google Docs API v1 + Google Drive API v3 | Misma cloud app que Shopify sheets |
| Scheduler | GitHub Actions (cron) | Ya lo usas para otros reporters |
| Base de datos | Supabase | Almacena ads procesados, evita reprocesar |
| Secrets management | GitHub Secrets | Consistente con infraestructura actual |

---

## ESTRUCTURA DE ARCHIVOS DEL PROYECTO

```
hair-biolabs-brief-system/
├── .github/
│   └── workflows/
│       └── daily_analysis.yml          # Cron diario 9:00 AM + dispatch manual
├── src/
│   ├── __init__.py
│   ├── meta_client.py                  # Meta Marketing API wrapper
│   ├── media_processor.py              # ffmpeg + Whisper
│   ├── classifier.py                   # Format + performance classification
│   ├── brief_engine.py                 # Generación de briefs (ganadores)
│   ├── autopsy_engine.py               # Diagnóstico de perdedores
│   ├── google_docs_exporter.py         # Creación y upload de Google Docs
│   ├── database.py                     # Supabase client
│   └── prompts/
│       ├── system_prompt_classifier.txt
│       ├── system_prompt_brief.txt
│       └── system_prompt_autopsy.txt
├── config/
│   └── settings.py                     # Thresholds, IDs, config central
├── scripts/
│   └── run_manual.py                   # Trigger manual desde CLI
├── tests/
│   ├── test_meta_client.py
│   ├── test_classifier.py
│   └── test_brief_engine.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## VARIABLES DE ENTORNO REQUERIDAS

```bash
# Meta API
META_ACCESS_TOKEN=           # System User token con ads_read + ads_management
META_AD_ACCOUNT_ID=act_2217973965310655
META_APP_ID=                 # ID de la Meta App a crear

# OpenAI (Whisper)
OPENAI_API_KEY=              # Para transcripción de video

# Anthropic (Claude)
ANTHROPIC_API_KEY=           # Para clasificación y generación de briefs

# Google APIs (reutilizar de Shopify sheets)
GOOGLE_SERVICE_ACCOUNT_JSON= # JSON del service account
GOOGLE_DRIVE_FOLDER_ID=      # ID de la carpeta destino en Drive

# Supabase
SUPABASE_URL=
SUPABASE_KEY=

# Config
TOP_N_ADS=10                 # Cuántos ads analizar por run
WINNER_SCORE_THRESHOLD=70
LOSER_SCORE_THRESHOLD=40
ANALYSIS_DATE_PRESET=last_30_days
```

---

## GITHUB ACTIONS WORKFLOW

```yaml
name: Hair Biolabs Ad Brief Generator

on:
  schedule:
    - cron: '0 8 * * *'  # 9:00 AM España (UTC+1 en horario de verano)
  workflow_dispatch:       # Trigger manual desde GitHub Actions UI
    inputs:
      top_n:
        description: 'Número de ads a analizar'
        required: false
        default: '10'
      force_reprocess:
        description: 'Reprocesar ads ya analizados?'
        required: false
        type: boolean
        default: false

jobs:
  generate-briefs:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          apt-get install -y ffmpeg
      
      - name: Run brief generation
        env:
          META_ACCESS_TOKEN: ${{ secrets.META_ACCESS_TOKEN }}
          META_AD_ACCOUNT_ID: ${{ secrets.META_AD_ACCOUNT_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
          GOOGLE_DRIVE_FOLDER_ID: ${{ secrets.GOOGLE_DRIVE_FOLDER_ID }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TOP_N_ADS: ${{ github.event.inputs.top_n || '10' }}
        run: python scripts/run_manual.py
```

---

## SCHEMA DE BASE DE DATOS (Supabase)

### Tabla: `ads`
```sql
CREATE TABLE ads (
  id              TEXT PRIMARY KEY,           -- Meta Ad ID
  name            TEXT,
  created_time    TIMESTAMPTZ,
  spend           DECIMAL,
  impressions     INTEGER,
  ctr             DECIMAL,
  purchase_roas   DECIMAL,
  hook_rate       DECIMAL,
  thruplay_rate   DECIMAL,
  days_active     INTEGER,
  performance_score DECIMAL,
  classification  TEXT,                       -- GANADOR | NEUTRO | PERDEDOR
  formato_detectado TEXT,
  avatar_deseo    TEXT,
  avatar_situacion TEXT,
  angulo          TEXT,
  mecanismo       TEXT,
  villain         TEXT,
  nivel_awareness TEXT,
  video_url       TEXT,
  transcription   TEXT,
  analysis_json   JSONB,                      -- Full JSON del clasificador
  processed_at    TIMESTAMPTZ DEFAULT NOW(),
  last_seen_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabla: `briefs`
```sql
CREATE TABLE briefs (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  ad_id           TEXT REFERENCES ads(id),
  tipo            TEXT,                       -- GANADOR_BRIEF | AUTOPSY
  formato_origen  TEXT,
  formato_destino TEXT,
  brief_content   TEXT,                       -- Brief completo en markdown
  google_doc_url  TEXT,
  generated_at    TIMESTAMPTZ DEFAULT NOW()
);
```

---

## FLUJO DE EJECUCIÓN DETALLADO

```python
# Pseudocódigo del flujo principal

def main():
    # 1. Conectar a Meta API
    meta = MetaClient(token=META_ACCESS_TOKEN, account=META_AD_ACCOUNT_ID)
    
    # 2. Descargar top N ads activos por spend
    raw_ads = meta.get_top_video_ads(n=TOP_N_ADS, date_preset="last_30_days")
    
    # 3. Filtrar ads ya procesados (Supabase check)
    new_ads = db.filter_unprocessed(raw_ads)
    
    winners, losers = [], []
    
    for ad in new_ads:
        # 4. Descargar video
        video_path = download_video(ad.creative.video_url)
        
        # 5. Extraer frames y transcribir
        frames = extract_frames(video_path, fps_interval=5, max_frames=20)
        transcription = transcribe_audio(video_path, language="es")
        
        # 6. Calcular performance score
        score = calculate_performance_score(ad.metrics)
        classification = classify_performance(score)
        
        # 7. Clasificar formato con Claude Vision
        analysis = classify_format(frames, transcription, ad.metrics)
        
        # 8. Guardar en Supabase
        db.upsert_ad({...ad, score, classification, analysis})
        
        if classification == "GANADOR":
            winners.append(ad)
        elif classification == "PERDEDOR":
            losers.append(ad)
    
    all_briefs = []
    
    # 9. Generar briefs para ganadores
    for winner in winners:
        other_formats = get_other_formats(winner.analysis.formato_detectado)
        for formato in other_formats:
            brief = generate_winner_brief(winner, formato)
            all_briefs.append(brief)
            db.insert_brief(winner.id, "GANADOR_BRIEF", brief)
    
    # 10. Generar autopsy para perdedores
    for loser in losers:
        autopsy = generate_autopsy(loser)
        all_briefs.append(autopsy)
        db.insert_brief(loser.id, "AUTOPSY", autopsy)
    
    # 11. Exportar a Google Docs
    if all_briefs:
        doc_url = export_to_google_docs(winners, losers, all_briefs)
        print(f"Brief generado: {doc_url}")
```

---

## ORDEN DE CONSTRUCCIÓN (FASES)

### Fase 1: Fundación (2-3 días)
- [ ] Crear Meta App en developers.facebook.com
- [ ] Obtener System User token con permisos correctos
- [ ] Configurar repo en GitHub con secrets
- [ ] Implementar `meta_client.py` y verificar que devuelve los 10 ads correctamente
- [ ] Configurar Supabase con los schemas definidos

### Fase 2: Media Processing (1-2 días)
- [ ] Implementar `media_processor.py` (ffmpeg + yt-dlp)
- [ ] Integrar Whisper API para transcripción en español
- [ ] Test con 3 ads reales de Hair Biolabs

### Fase 3: Classification Engine (2-3 días)
- [ ] Implementar `classifier.py` con los 5 formatos como contexto
- [ ] Calibrar el algoritmo de scoring con ads reales conocidos
- [ ] Validar manualmente las clasificaciones de 10 ads

### Fase 4: Brief Engine (3-4 días)
- [ ] Implementar `brief_engine.py` con los prompts completos
- [ ] Implementar `autopsy_engine.py`
- [ ] Afinar el speech generator para que suene a español de España (no latinoamericano)
- [ ] Test generando briefs para los 5 formatos

### Fase 5: Export + Automation (2 días)
- [ ] Implementar `google_docs_exporter.py`
- [ ] Configurar GitHub Actions con cron + manual dispatch
- [ ] Test end-to-end completo
- [ ] Primera ejecución real con Hair Biolabs

**Total estimado: 10-14 días de desarrollo**

---

## CONSIDERACIONES IMPORTANTES

### Sobre la calidad de los briefs
El brief engine necesita los siguientes elementos en su system prompt para que el output sea de calidad profesional:
- Todos los datos del producto Hair Biolabs (mecanismo, ingredientes, claims legales permitidos en España)
- Los 5 formatos completos con sus descripciones del Excel como referencia
- Instrucciones específicas de tono: español de España (no latinoamericano), habla natural, sin gerundios de apertura
- El brief del ejemplo adjunto (Tarjeta 2 ComfortSleep) como referencia de formato y nivel de detalle

### Sobre los prompts de Seadance
Cada prompt de Seadance para los frames del brief debe incluir:
- Tipo de toma (selfie, studio, split-screen, b-roll clínico...)
- Descripción de la persona (edad aproximada, ropa, expresión)
- Props específicos (producto, almohada, micrófono...)
- Iluminación y fondo
- Texto overlay que aparecería en el video
- Estética visual de referencia (UGC raw, clínico, podcast, emocional...)

### Sobre el rate limiting de Meta API
- Límite: 200 calls por hora por app
- Con 10 ads y 3-4 calls por ad = ~40 calls por run
- Sin problema de rate limiting

### Sobre costes estimados de API por run diario
| API | Uso estimado | Coste aprox. |
|---|---|---|
| Whisper (transcripción) | 10 videos × 90s = 15min | ~$0.18/run |
| Claude claude-sonnet-4-20250514 (clasificación + briefs) | ~50k tokens/run | ~$0.75/run |
| Google Docs API | Gratuito hasta límites altos | $0 |
| Meta API | Gratuita | $0 |
| **Total** | | **~$1/día** |

---

## PENDIENTES QUE REQUIEREN INPUT ADICIONAL

- [ ] **Productos específicos de Hair Biolabs España:** El brief engine necesita saber exactamente qué productos hay (nombres, mecanismo oficial, ingredientes clave, claims permitidos). Proporcionar ficha de producto.
- [ ] **Folder ID de Google Drive:** Confirmar la carpeta exacta donde irán los briefs.
- [ ] **Ejemplos de ads ganadores históricos:** Si hay ads pasados que ya se saben ganadores, usarlos para calibrar el scoring.
- [ ] **Creadores disponibles:** Para los prompts de Seadance, saber qué tipo de perfil de creador tiene disponible el equipo (fisio mujer 30s, UGC creator casual, actor médico...).
- [ ] **Claims legales Spain:** Qué claims de salud están permitidos en España para el producto. Esto afecta directamente el speech del brief.

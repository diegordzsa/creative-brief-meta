import os
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        val = st.secrets.get(key, None)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)


# --- Anthropic (single AI provider for transcription + classification + briefs) ---
ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY")

# --- Google ---
GOOGLE_SERVICE_ACCOUNT_JSON = _get_secret("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_DRIVE_FOLDER_ID = _get_secret("GOOGLE_DRIVE_FOLDER_ID")

# --- Supabase ---
SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")

# --- Media Processing ---
FRAMES_FPS_INTERVAL = 5
MAX_FRAMES_PER_VIDEO = 20

# --- OpenAI (DALL-E 3 storyboards) ---
OPENAI_API_KEY = _get_secret("OPENAI_API_KEY")

# --- LLM ---
CLASSIFIER_MODEL = "claude-sonnet-4-6"

# --- Hair Biolabs Product Data ---
PRODUCT_DATA = {
    "brand": "Hair Biolabs",
    "market": "España",
    "language": "es-ES",
    "manufacturing": "EU-certified (GMP, ISO 22716), Alaquas, Valencia",
    "products": [
        {
            "name": "REDENSIFY™ Triple Action Serum",
            "price_range": "€49.90–€69.90",
            "type": "serum",
        },
        {
            "name": "Double Action Anti-Hair Loss Serum 1+1",
            "price_range": "€69.90",
            "type": "serum",
        },
        {
            "name": "Complete Hair Strengthening Pack",
            "price_range": "€69.90–€79.90",
            "type": "pack",
        },
        {
            "name": "Anti-Hair Loss Serum",
            "price_range": "€49.90–€69.90",
            "type": "serum",
        },
    ],
    "key_ingredients": [
        "Scutellaria baicalensis root extract",
        "wheat germ extract",
        "soy germ extract",
        "oleanolic acid",
        "biotin tripeptide-1",
        "acetyl tetrapeptide-3",
        "pumpkin seed extract",
        "millet extract",
        "caffeine",
        "aloe vera leaf juice",
    ],
    "claims": {
        "30_days": "60% less hair fall",
        "60_days": "Baby hairs emergence",
        "90_days": "38,000+ new hairs in 3 months",
        "120_days": "75% density increase",
    },
    "timeline_phases": [
        {"phase": "Initial", "duration": "30-45 days", "result": "Less shedding, stronger hair"},
        {"phase": "Growth", "duration": "60 days", "result": "Baby hairs emergence"},
        {"phase": "Transformation", "duration": "90 days", "result": "75% density increase"},
    ],
}

# --- Creative Formats ---
CREATIVE_FORMATS = {
    "formato_1": {
        "number": 1,
        "name": "Reaction Style Hook x 3D Authority Mechanism (UGC Hybrid)",
        "structure": "Split-screen con creador en modo 'Reaction Channel' + animación 3D médica/científica. El creador reacciona y comenta la animación, pivotando hacia el mecanismo del producto.",
        "segments": [
            {"name": "Hook", "time": "0-6s", "description": "Split-screen creador reaccionando + animación impactante"},
            {"name": "Mecanismo Pivot", "time": "6-22s", "description": "Animación 3D del problema a nivel celular"},
            {"name": "Prueba social + Reveal", "time": "22-33s", "description": "Before/after personal + producto físico"},
            {"name": "Demostración + animación dual", "time": "33-52s", "description": "Aplicación + animación del mecanismo de acción"},
            {"name": "Offer Stack + CTA", "time": "52s+", "description": "Stack de oferta con urgencia"},
        ],
        "signals": "setup de 'React Channel', animación 3D simultánea, creador que ES el testimonio, lenguaje conversacional y de calle",
    },
    "formato_2": {
        "number": 2,
        "name": "Anti-Product Paradigm Shift x Stage Classification Listicle",
        "structure": "Narrador de autoridad que invalida el acto de 'comprar productos' como solución, pivotando hacia un sistema personalizado basado en el estadio del problema.",
        "segments": [
            {"name": "Hook", "time": "0-6s", "description": "Declaración que invalida la lógica del consumidor"},
            {"name": "Pain Matrix", "time": "6-15s", "description": "Carrusel de productos genéricos que han fallado"},
            {"name": "Paradigm Shift", "time": "15-26s", "description": "La autoridad explica por qué todos los productos fallan"},
            {"name": "Stage Classification", "time": "26-41s", "description": "Grid visual clasificando estadios del problema"},
            {"name": "Brand Trust + CTA", "time": "41s+", "description": "Credenciales, escala, lead gen de bajo friction"},
        ],
        "signals": "narrador 50+, lenguaje clínico y empático, grids de categorización, CTA de consulta gratuita",
    },
    "formato_3": {
        "number": 3,
        "name": "Organic Podcast Leak x Scientific Bottleneck Education Framework",
        "structure": "Clip orgánico de podcast educativo. La narradora descarta soluciones una por una antes de revelar el 'bottleneck' científico real y el ingrediente que lo resuelve.",
        "segments": [
            {"name": "Hook", "time": "0-4s", "description": "Declaración de industria corrupta o verdad suprimida"},
            {"name": "Alternative Rejection Carousel", "time": "4-15s", "description": "Descarte sistemático de soluciones comunes con X gráficos"},
            {"name": "Bottleneck Education", "time": "15-34s", "description": "Explicación del problema fisiológico real"},
            {"name": "Institutional Authority", "time": "34-54s", "description": "Científicos de institución descubren el compuesto clave"},
            {"name": "Ingredient Stack", "time": "54-70s", "description": "Sinergia de ingredientes como listicle hablado"},
            {"name": "Low-Friction Close", "time": "70s+", "description": "Precio bajo, garantía, CTA suave"},
        ],
        "signals": "setup de podcast o sofá casual, X rojos sobre competidores, metáfora biológica central, referencia a institución académica, precio ancla bajo",
    },
    "formato_4": {
        "number": 4,
        "name": "The Salon Secret x Structural Cortical Degradation Hook",
        "structure": "Narrativa en primera persona de consumidora real que descubrió la causa real a través de una figura de autoridad de proximidad (hairstylist, esteticista, farmacéutica).",
        "segments": [
            {"name": "Hook + Reaction Blend", "time": "0-11s", "description": "Banner de alto impacto + creadora respondiendo"},
            {"name": "Storyteller Introduction", "time": "11-26s", "description": "La narradora sitúa la historia en tiempo y lugar específico"},
            {"name": "The Discovery Narrative", "time": "26-66s", "description": "B-roll del ambiente + momento de revelación"},
            {"name": "Anatomical Breakdown", "time": "66-109s", "description": "La figura de autoridad explica el problema a nivel celular"},
            {"name": "Hidden Deficit Pitch", "time": "109-158s", "description": "Testimonio de la experta + setup del mineral/ingrediente oculto"},
            {"name": "Cliffhanger + CTA", "time": "158s+", "description": "Information asymmetry — 'tu médico no lo mide'"},
        ],
        "signals": "storytelling en primera persona detallado, figura de autoridad de proximidad, 3D cross-section de cabello/piel, cliffhanger sin cierre completo",
    },
    "formato_5": {
        "number": 5,
        "name": "Emotional Agitation Montage x 650nm Cellular Photobiomodulation Reveal",
        "structure": "Primeros 35-40s de agitación emocional pura, luego pivot a autoridad científica extrema. El contraste emocional/científico es el mecanismo central.",
        "segments": [
            {"name": "Demoralizing Hook", "time": "0-3s", "description": "Imagen clínica de daño máximo + texto de golpe emocional"},
            {"name": "Relatable Defeat Montage", "time": "3-14s", "description": "Compilación rápida de UGC mostrando pain points diarios"},
            {"name": "Treatment Rejection Loop", "time": "14-22s", "description": "Invalidación de soluciones con side effects específicos"},
            {"name": "Gender/Identity Frame", "time": "22-38s", "description": "Contraste de cómo el problema afecta la identidad"},
            {"name": "Scientific Epiphany", "time": "38-50s", "description": "Pivot a autoridad clínica, scanner, monitor de diagnóstico"},
            {"name": "Biological Mechanism", "time": "50-65s", "description": "Animación 3D del problema a nivel celular"},
            {"name": "Clinical Solution Reveal", "time": "65-77s+", "description": "Dermatólogo + device + wavelength específica + resultados"},
        ],
        "signals": "opening con imagen de daño máximo, montaje con 5+ clips de pain points, invalidación de Minoxidil por nombre, contraste identitario, wavelength 650nm, citation de journal",
    },
}

# --- Format Reference Videos (from creative formats spreadsheet, Column 5) ---
FORMAT_REFERENCE_VIDEOS = {
    "formato_1": "https://drive.google.com/file/d/1jCZ7Nq9r2huSboszuKX1Y7WNwTliFaQM/view",
    "formato_2": "https://drive.google.com/file/d/1ObKYgT6G_Z4jre3YeNNRYpdfJbbGItZJ/view",
    "formato_3": "https://drive.google.com/file/d/1ro2a8M7y_-KPlaVziG5fM7MI2o-maSJc/view",
    "formato_4": "https://drive.google.com/file/d/19U-v5ONYeECTE9dGKeC1ZWxCy6obuEVI/view",
    "formato_5": "https://drive.google.com/file/d/18ucej2W8Hpcv8yJpBobaxihcV7oYCUht/view",
}

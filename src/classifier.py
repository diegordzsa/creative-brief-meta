import base64
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

MOCK_CLASSIFICATION = {
    "formato_detectado": "Formato 3: Organic Podcast Leak x Scientific Bottleneck Education Framework",
    "confianza": 87,
    "justificacion": "El ad presenta un setup de podcast casual (sofá, iluminación cálida) con la narradora posicionándose como truth-teller de la industria. En 0:00-0:06 declara que 'el 80% de los productos anticaída no funcionan', descartando alternativas con X gráficos entre 0:06-0:15. El bottleneck científico se revela en 0:15-0:25 (folículo muriendo por falta de nutrientes). La referencia institucional aparece en 0:25-0:40 ('científicos en Suiza'). Cierre con precio bajo y CTA suave en 0:55+.",
    "deseo_avatar": "Recuperar densidad capilar y dejar de perder pelo cada día",
    "situacion_avatar": "Mujer 30-55 que ha probado múltiples productos sin resultado y empieza a perder confianza",
    "angulo_ganador": "La causa real no es el pelo que se cae, sino el folículo que se muere por falta de nutrientes específicos",
    "mecanismo": "Acetyl tetrapeptide-3 reactiva folículos dormidos estimulando células madre del bulbo capilar + Scutellaria baicalensis reduce inflamación del cuero cabelludo",
    "villain": "La industria de productos genéricos anticaída que no atacan la raíz del problema",
    "nivel_awareness": "problem-aware",
    "segmentos": [
        {"nombre": "Hook", "timestamp_inicio": "0:00", "timestamp_fin": "0:06", "descripcion": "Declaración impactante: 80% de productos no funcionan"},
        {"nombre": "Alternative Rejection Carousel", "timestamp_inicio": "0:06", "timestamp_fin": "0:15", "descripcion": "Descarte de champús, ampollas, biotina"},
        {"nombre": "Bottleneck Education", "timestamp_inicio": "0:15", "timestamp_fin": "0:25", "descripcion": "Revelación: el folículo se muere por falta de nutrientes"},
        {"nombre": "Institutional Authority", "timestamp_inicio": "0:25", "timestamp_fin": "0:40", "descripcion": "Referencia a científicos en Suiza + acetyl tetrapeptide-3"},
        {"nombre": "Ingredient Stack", "timestamp_inicio": "0:40", "timestamp_fin": "0:55", "descripcion": "REDENSIFY + Scutellaria baicalensis + resultados en 30/90 días"},
        {"nombre": "Low-Friction Close", "timestamp_inicio": "0:55", "timestamp_fin": "1:10", "descripcion": "Testimonio personal + oferta con envío gratis + CTA"},
    ],
    "elementos_que_funcionan": [
        "Hook con estadística específica (80%) que genera curiosidad",
        "Descarte de alternativas crea credibilidad antes del pitch",
        "Mecanismo científico específico (acetyl tetrapeptide-3) da autoridad",
        "Testimonio personal con fotos como prueba social",
        "CTA suave con envío gratis reduce fricción",
    ],
}


class Classifier:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.mock_mode = not api_key
        self.system_prompt = (PROMPTS_DIR / "system_prompt_classifier.txt").read_text(encoding="utf-8")
        if self.mock_mode:
            logger.warning("ANTHROPIC_API_KEY not set — Classifier running in MOCK mode")

    def classify(self, frames: list[str], transcription: str, metrics: dict[str, Any]) -> dict[str, Any]:
        if self.mock_mode:
            logger.info("Mock mode: returning sample classification")
            return MOCK_CLASSIFICATION

        return self._call_claude(frames, transcription, metrics)

    def _call_claude(self, frames: list[str], transcription: str, metrics: dict[str, Any]) -> dict[str, Any]:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        content: list[dict] = []

        intro = f"Analiza este ad de video de Hair Biolabs España.\n\nTRANSCRIPCIÓN:\n{transcription}\n"

        if metrics:
            intro += (
                f"\nMÉTRICAS:\n"
                f"- CTR: {metrics.get('ctr', 0):.2f}%\n"
                f"- ROAS: {metrics.get('purchase_roas', 0):.2f}x\n"
                f"- Hook Rate: {metrics.get('hook_rate', 0):.1f}%\n"
                f"- Hold Rate (ThruPlay/Impressions): {metrics.get('hold_rate', 0):.2%}\n"
                f"- Spend: €{metrics.get('spend', 0):.2f}\n"
                f"- Impressions: {int(metrics.get('impressions', 0)):,}\n"
            )

        intro += "\nFRAMES EXTRAÍDOS:"

        content.append({
            "type": "text",
            "text": intro,
        })

        for frame_path in frames:
            if Path(frame_path).exists():
                with open(frame_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_data,
                    },
                })

        content.append({
            "type": "text",
            "text": """Devuelve ÚNICAMENTE un JSON válido (sin markdown, sin backticks) con esta estructura exacta:
{
  "formato_detectado": "nombre exacto del formato (Formato 1/2/3/4/5: nombre completo)",
  "confianza": 0-100,
  "justificacion": "por qué es este formato, con timestamps específicos",
  "deseo_avatar": "el deseo principal del avatar",
  "situacion_avatar": "la situación actual del avatar",
  "angulo_ganador": "el ángulo principal del ad",
  "mecanismo": "el mecanismo revelado en el ad",
  "villain": "el villano del ad",
  "nivel_awareness": "problem-aware | solution-aware | product-aware",
  "segmentos": [
    {"nombre": "nombre del segmento", "timestamp_inicio": "M:SS", "timestamp_fin": "M:SS", "descripcion": "qué pasa en este segmento"}
  ],
  "elementos_que_funcionan": ["lista de elementos clave del ad"]
}""",
        })

        response = client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": content}],
        )

        raw_text = response.content[0].text.strip()
        return json.loads(raw_text)

import json
import logging
from pathlib import Path
from typing import Any

from config.settings import CREATIVE_FORMATS

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _get_other_formats(detected_format: str) -> list[dict[str, Any]]:
    detected_key = None
    for key, fmt in CREATIVE_FORMATS.items():
        if fmt["name"].lower() in detected_format.lower() or key.replace("_", " ") in detected_format.lower():
            detected_key = key
            break

    if not detected_key:
        for key in CREATIVE_FORMATS:
            if key[-1] in detected_format:
                detected_key = key
                break

    return [
        {"key": k, **v}
        for k, v in CREATIVE_FORMATS.items()
        if k != detected_key
    ]


def _build_format_description(fmt: dict[str, Any]) -> str:
    segments_text = "\n".join(
        f"  - {s['name']} ({s['time']}): {s['description']}"
        for s in fmt.get("segments", [])
    )
    return f"""**{fmt['name']}**
Estructura: {fmt['structure']}
Segmentos:
{segments_text}
Señales: {fmt.get('signals', '')}"""


class BriefEngine:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.mock_mode = not api_key
        self.system_prompt = (PROMPTS_DIR / "system_prompt_brief.txt").read_text(encoding="utf-8")
        if self.mock_mode:
            logger.warning("ANTHROPIC_API_KEY not set — BriefEngine running in MOCK mode")

    def generate_briefs(self, ad: dict[str, Any]) -> list[dict[str, Any]]:
        analysis = ad.get("analysis", {})
        detected_format = analysis.get("formato_detectado", "")
        other_formats = _get_other_formats(detected_format)

        briefs = []
        for fmt in other_formats:
            brief = self._generate_single_brief(ad, analysis, fmt)
            briefs.append({
                "formato_origen": detected_format,
                "formato_destino": fmt["name"],
                "content": brief,
            })
        return briefs

    def _generate_single_brief(self, ad: dict[str, Any], analysis: dict[str, Any], target_format: dict[str, Any]) -> str:
        if self.mock_mode:
            return self._mock_brief(ad, analysis, target_format)

        return self._call_claude(ad, analysis, target_format)

    def _call_claude(self, ad: dict[str, Any], analysis: dict[str, Any], target_format: dict[str, Any]) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        format_desc = _build_format_description(target_format)

        metrics = ad.get("metrics", {})
        metrics_line = ""
        if metrics.get("ctr") or metrics.get("purchase_roas"):
            metrics_line = f"\n- **Métricas:** CTR {metrics.get('ctr', 0):.2f}% | ROAS {metrics.get('purchase_roas', 0):.2f}x | Hook Rate {metrics.get('hook_rate', 0):.1f}%"

        user_prompt = f"""Genera un brief completo para un nuevo ad de Hair Biolabs España.

## AD ANALIZADO
- **Nombre:** {ad.get('name', '')}
- **Formato detectado:** {analysis.get('formato_detectado', '')}{metrics_line}

## ELEMENTOS DEL AD QUE DEBES MANTENER
- **Deseo del avatar:** {analysis.get('deseo_avatar', '')}
- **Situación del avatar:** {analysis.get('situacion_avatar', '')}
- **Ángulo ganador:** {analysis.get('angulo_ganador', '')}
- **Mecanismo:** {analysis.get('mecanismo', '')}
- **Villain:** {analysis.get('villain', '')}
- **Nivel de awareness:** {analysis.get('nivel_awareness', '')}

## FORMATO OBJETIVO (para el nuevo brief)
{format_desc}

## INSTRUCCIONES
Genera el brief completo con:
1. Por qué este formato puede ganar (2-3 párrafos)
2. Explicación del formato
3. Estructura de segmentos (tabla markdown)
4. Speech completo listo para grabar (español de España, habla natural)
5. Prompts de Seadance por segmento (descripción visual ultra-detallada)
6. Notas de producción (ratio 9:16, duración, tipo de creador, props, cámara)"""

        response = client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return response.content[0].text

    def _mock_brief(self, ad: dict[str, Any], analysis: dict[str, Any], target_format: dict[str, Any]) -> str:
        segments_table = "\n".join(
            f"| {s['name']} | {s['time']} | {s['description']} | [texto overlay] |"
            for s in target_format.get("segments", [])
        )

        return f"""## {target_format['name']}

### Por qué este formato puede ganar
El ad original en formato "{analysis.get('formato_detectado', '')}" ha demostrado que el ángulo "{analysis.get('angulo_ganador', '')}" conecta fuertemente con el avatar. El formato {target_format['name']} permite reformular este mismo mensaje aprovechando una estructura narrativa diferente que puede capturar segmentos del público que no responden al formato original.

La ventaja específica de este formato es su estructura: {target_format['structure']}

Al mantener el mecanismo ({analysis.get('mecanismo', '')}) pero cambiando la forma de presentarlo, ampliamos el reach sin diluir el mensaje que ya sabemos que funciona.

### Explicación del formato
{target_format['structure']}

Señales clave: {target_format.get('signals', '')}

### Estructura de segmentos
| Segmento | Tiempo | Descripción | Texto overlay |
|----------|--------|-------------|---------------|
{segments_table}

### Speech completo (listo para grabar)
[MOCK — En producción, aquí iría el speech completo en español de España, escrito en flujo natural de habla, sin puntos de guión, tal como lo diría el creador a cámara. El speech mantendría el ángulo ganador "{analysis.get('angulo_ganador', '')}" y el mecanismo "{analysis.get('mecanismo', '')}" adaptados a la estructura narrativa de este formato.]

### Prompts de Seadance por segmento
{chr(10).join(f'**Segmento: {s["name"]} ({s["time"]})**{chr(10)}Prompt: [MOCK — Descripción visual ultra-detallada para Seadance: encuadre, iluminación, persona, props Hair Biolabs, texto overlay, estética]{chr(10)}' for s in target_format.get('segments', []))}

### Notas de producción
- **Ratio:** 9:16 (vertical, optimizado para Stories/Reels)
- **Duración objetivo:** {target_format['segments'][-1]['time'] if target_format.get('segments') else '60s+'}
- **Tipo de creador:** [Según formato]
- **Props necesarios:** Producto Hair Biolabs (REDENSIFY™ o Anti-Hair Loss Serum), setup según formato
- **Setup de cámara:** iPhone/smartphone para UGC, estudio para formatos de autoridad
"""

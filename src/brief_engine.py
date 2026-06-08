import json
import logging
import re
from pathlib import Path
from typing import Any

from config.settings import CREATIVE_FORMATS, FORMAT_REFERENCE_VIDEOS

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


def build_header_data(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "deseo": analysis.get("deseo_avatar", ""),
        "avatar_situacion": analysis.get("situacion_avatar", ""),
        "angulo_ganador": analysis.get("angulo_ganador", ""),
        "mecanismo": analysis.get("mecanismo", ""),
        "villain": analysis.get("villain", ""),
        "nivel_awareness": analysis.get("nivel_awareness", ""),
        "formato_detectado": analysis.get("formato_detectado", ""),
    }


def _parse_json_response(text: str) -> dict[str, Any]:
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    return json.loads(text.strip())


class BriefEngine:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
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
        for idx, fmt in enumerate(other_formats, start=1):
            brief = self._generate_single_brief(ad, analysis, fmt)
            ref_video = FORMAT_REFERENCE_VIDEOS.get(fmt["key"], "")
            brief["formato_origen"] = detected_format
            brief["formato_destino"] = fmt["name"]
            brief["formato_numero"] = fmt["number"]
            brief["formato_total"] = len(other_formats)
            brief["video_referencia"] = ref_video
            briefs.append(brief)
        return briefs

    def _generate_single_brief(self, ad: dict[str, Any], analysis: dict[str, Any], target_format: dict[str, Any]) -> dict[str, Any]:
        if self.mock_mode:
            return self._mock_brief(ad, analysis, target_format)
        return self._call_claude(ad, analysis, target_format)

    def _call_claude(self, ad: dict[str, Any], analysis: dict[str, Any], target_format: dict[str, Any]) -> dict[str, Any]:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        format_desc = _build_format_description(target_format)

        user_prompt = f"""Genera un brief para un nuevo ad de Hair Biolabs España en el formato indicado.

## AD GANADOR ANALIZADO
- **Formato detectado:** {analysis.get('formato_detectado', '')}

## ELEMENTOS QUE SE MANTIENEN (NO cambiar)
- **Deseo del avatar:** {analysis.get('deseo_avatar', '')}
- **Situación del avatar:** {analysis.get('situacion_avatar', '')}
- **Ángulo ganador:** {analysis.get('angulo_ganador', '')}
- **Mecanismo:** {analysis.get('mecanismo', '')}
- **Villain:** {analysis.get('villain', '')}
- **Nivel de awareness:** {analysis.get('nivel_awareness', '')}

## FORMATO OBJETIVO (el nuevo video debe seguir esta estructura)
{format_desc}

Genera el JSON con: explicacion_formato, nota_antes_de_grabar, escenas (exactamente 9), speech_completo."""

        response = client.messages.create(
            model=self.model,
            max_tokens=6000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = response.content[0].text
        try:
            parsed = _parse_json_response(raw_text)
        except (json.JSONDecodeError, ValueError):
            logger.error("Failed to parse brief JSON, returning raw text as fallback")
            return {
                "explicacion": raw_text,
                "escenas": [],
                "speech": raw_text,
                "nota_legal": None,
            }

        return {
            "explicacion": parsed.get("explicacion_formato", ""),
            "escenas": parsed.get("escenas", []),
            "speech": parsed.get("speech_completo", ""),
            "nota_legal": parsed.get("nota_antes_de_grabar"),
        }

    def _mock_brief(self, ad: dict[str, Any], analysis: dict[str, Any], target_format: dict[str, Any]) -> dict[str, Any]:
        escenas = [
            {"numero": i, "etiqueta": f"Escena {i} — {seg['name']}", "descripcion_visual": seg["description"]}
            for i, seg in enumerate(target_format.get("segments", [])[:9], start=1)
        ]
        while len(escenas) < 9:
            n = len(escenas) + 1
            escenas.append({"numero": n, "etiqueta": f"Escena {n}", "descripcion_visual": "Escena adicional del formato"})

        return {
            "explicacion": f"Se mapeó el ángulo ganador ({analysis.get('angulo_ganador', '')}) a la estructura del formato {target_format['name']}. {target_format['structure']}",
            "escenas": escenas,
            "speech": f"[MOCK — En producción, aquí iría el speech completo en español de España, manteniendo el ángulo ganador \"{analysis.get('angulo_ganador', '')}\" y el mecanismo \"{analysis.get('mecanismo', '')}\" adaptados a la estructura narrativa de {target_format['name']}. El speech sería texto corrido natural, listo para grabar tal cual.]",
            "nota_legal": None,
        }

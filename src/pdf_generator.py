import io
import logging
from pathlib import Path
from typing import Any

from fpdf import FPDF

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).parent / "fonts"

FONT_SEARCH_PATHS = [
    FONTS_DIR / "DejaVuSans.ttf",
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
]

FONT_BOLD_SEARCH_PATHS = [
    FONTS_DIR / "DejaVuSans-Bold.ttf",
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
]

PINK = (233, 30, 143)
DARK = (33, 33, 33)
GRAY = (100, 100, 100)
LIGHT_BG = (245, 245, 245)


def _find_font(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


class BriefPDFGenerator:
    def __init__(self):
        self.pdf = None

    def generate(
        self,
        header_data: dict[str, Any],
        briefs: list[dict[str, Any]],
        storyboard_images: dict[str, bytes],
    ) -> bytes:
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        self.pdf = pdf
        pdf.set_auto_page_break(auto=True, margin=20)

        font_path = _find_font(FONT_SEARCH_PATHS)
        bold_path = _find_font(FONT_BOLD_SEARCH_PATHS)

        if font_path:
            pdf.add_font("brief", "", str(font_path), uni=True)
            if bold_path:
                pdf.add_font("brief", "B", str(bold_path), uni=True)
            else:
                pdf.add_font("brief", "B", str(font_path), uni=True)
            self._font_family = "brief"
        else:
            self._font_family = "Helvetica"
            logger.warning("No Unicode font found — falling back to Helvetica (accented chars may break)")

        self._write_header_page(header_data, len(briefs))

        for brief in briefs:
            fmt_key = brief.get("formato_destino", "")
            storyboard_bytes = storyboard_images.get(fmt_key, b"")
            self._write_format_page(brief, storyboard_bytes)

        buf = io.BytesIO()
        pdf.output(buf)
        return buf.getvalue()

    def _set_font(self, style: str = "", size: int = 11):
        self.pdf.set_font(self._font_family, style, size)

    def _write_header_page(self, header: dict[str, Any], num_formats: int):
        pdf = self.pdf
        pdf.add_page()

        self._set_font("B", 22)
        pdf.set_text_color(*PINK)
        pdf.cell(0, 12, "BRIEF EDITOR · Hair Biolabs España", new_x="LMARGIN", new_y="NEXT")

        self._set_font("", 10)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 6, f"España · {num_formats} vídeos a montar", new_x="LMARGIN", new_y="NEXT")

        pdf.set_draw_color(*PINK)
        pdf.set_line_width(0.8)
        pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
        pdf.ln(8)

        self._section_title("Qué hay que hacer (lee esto primero)")
        self._body_text(
            f"Tienes un vídeo GANADOR que ya funciona (formato: {header.get('formato_detectado', '')}). "
            "NO cambiamos el mensaje. Lo único que vamos a hacer es cambiar el FORMATO: "
            "la forma en la que presentamos la misma información, llevándola a cada uno de los "
            "formatos de abajo. Se mantiene EXACTAMENTE el mismo deseo y el mismo avatar/situación del ganador."
        )
        pdf.ln(4)

        self._section_title("Deseo que se mantiene (NO cambiar)")
        self._body_text(header.get("deseo", ""))
        pdf.ln(3)

        self._section_title("Avatar / situación que se mantiene (NO cambiar)")
        self._body_text(header.get("avatar_situacion", ""))
        pdf.ln(3)

        self._section_title("Situación / ángulo")
        angulo = header.get("angulo_ganador", "")
        mecanismo = header.get("mecanismo", "")
        villain = header.get("villain", "")
        self._body_text(f"Situación / ángulo: {angulo}")
        if mecanismo:
            self._body_text(f"Mecanismo: {mecanismo}")
        if villain:
            self._body_text(f"Villain: {villain}")
        pdf.ln(3)

        self._section_title("Nivel de awareness")
        self._body_text(header.get("nivel_awareness", ""))
        pdf.ln(3)

        self._set_font("", 9)
        pdf.set_text_color(*GRAY)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=0, h=5, text=(
            "Para cada formato tienes abajo: el título, una foto de referencia-guía de la escena "
            "(es solo guía visual de qué montar, no el anuncio final), una breve explicación "
            "del formato y el speech en párrafo listo para grabar."
        ), new_x="LMARGIN", new_y="NEXT")

    def _write_format_page(self, brief: dict[str, Any], storyboard_bytes: bytes):
        pdf = self.pdf
        pdf.add_page()

        num = brief.get("formato_numero", 0)
        total = brief.get("formato_total", 0)
        name = brief.get("formato_destino", "")

        self._set_font("B", 18)
        pdf.set_text_color(*PINK)
        pdf.cell(0, 10, f"Formato {num}/{total} · {name}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        if storyboard_bytes:
            try:
                img_stream = io.BytesIO(storyboard_bytes)
                pdf.image(img_stream, x=10, w=190)
                pdf.ln(3)
            except Exception as e:
                logger.error(f"Failed to embed storyboard image: {e}")

        self._set_font("", 8)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 4, "↑ Foto de referencia-GUÍA de la escena (qué montar · no es el anuncio final)", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        self._section_title("Explicación del formato")
        self._body_text(brief.get("explicacion", ""))
        pdf.ln(3)

        nota = brief.get("nota_legal")
        if nota:
            self._set_font("", 9)
            pdf.set_text_color(*GRAY)
            pdf.set_fill_color(*LIGHT_BG)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=0, h=5, text=f"■■ Notación antes de grabar (formato profesional · nexo legal): {nota}", fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

        self._section_title("Speech (en párrafo · grabar tal cual)")
        self._body_text(brief.get("speech", ""))
        pdf.ln(3)

        ref_video = brief.get("video_referencia", "")
        if ref_video:
            self._set_font("", 8)
            pdf.set_text_color(*GRAY)
            pdf.cell(0, 4, f"Video de referencia del formato: {ref_video}", new_x="LMARGIN", new_y="NEXT")

    def _section_title(self, text: str):
        self._set_font("B", 12)
        self.pdf.set_text_color(*DARK)
        self.pdf.set_x(self.pdf.l_margin)
        self.pdf.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.pdf.ln(1)

    def _body_text(self, text: str):
        if not text:
            return
        self._set_font("", 10)
        self.pdf.set_text_color(*DARK)
        self.pdf.set_x(self.pdf.l_margin)
        self.pdf.multi_cell(w=0, h=5, text=text, new_x="LMARGIN", new_y="NEXT")

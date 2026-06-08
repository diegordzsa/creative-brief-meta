import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


class StoryboardGenerator:
    def __init__(self, openai_api_key: str = ""):
        self.mock_mode = not openai_api_key
        self.api_key = openai_api_key
        if self.mock_mode:
            logger.warning("OPENAI_API_KEY not set — StoryboardGenerator using Pillow fallback")

    def generate_storyboard(self, scenes: list[dict[str, Any]], format_name: str) -> bytes:
        if self.mock_mode or not scenes:
            return self._generate_placeholder_grid(scenes, format_name)
        return self._generate_dalle_grid(scenes, format_name)

    def _generate_dalle_grid(self, scenes: list[dict[str, Any]], format_name: str) -> bytes:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        scene_descriptions = []
        for s in scenes[:9]:
            num = s.get("numero", 0)
            label = s.get("etiqueta", "")
            desc = s.get("descripcion_visual", "")
            scene_descriptions.append(f"Panel {num} (label: \"{label}\"): {desc}")

        scenes_text = "\n".join(scene_descriptions)

        prompt = f"""Create a professional 3x3 storyboard grid for a video ad. The grid has 9 numbered panels (1-9), arranged 3 columns by 3 rows. Each panel shows a different scene from the ad.

Format: {format_name}

The 9 scenes:
{scenes_text}

Style: Photo-realistic reference storyboard. Each panel has a small green numbered circle in the top-left corner and a short white text label at the bottom. Clean, professional look. The panels should show realistic people, products, and settings as described. Spanish market, European setting."""

        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1792x1024",
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url
            import urllib.request
            with urllib.request.urlopen(image_url) as resp:
                image_bytes = resp.read()

            return self._add_number_overlays(image_bytes, scenes)

        except Exception as e:
            logger.error(f"DALL-E 3 generation failed: {e}. Falling back to placeholder.")
            return self._generate_placeholder_grid(scenes, format_name)

    def _add_number_overlays(self, image_bytes: bytes, scenes: list[dict[str, Any]]) -> bytes:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(io.BytesIO(image_bytes))
        draw = ImageDraw.Draw(img)

        w, h = img.size
        cols, rows = 3, 3
        cell_w, cell_h = w // cols, h // rows

        try:
            font = ImageFont.truetype("arial.ttf", max(20, cell_w // 15))
        except OSError:
            font = ImageFont.load_default()

        for i in range(9):
            row_idx, col_idx = divmod(i, cols)
            cx = col_idx * cell_w + 25
            cy = row_idx * cell_h + 15
            r = max(16, cell_w // 20)

            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#4CAF50")
            num_text = str(i + 1)
            bbox = font.getbbox(num_text)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy - th // 2 - 2), num_text, fill="white", font=font)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def _generate_placeholder_grid(self, scenes: list[dict[str, Any]], format_name: str) -> bytes:
        from PIL import Image, ImageDraw, ImageFont

        grid_w, grid_h = 1800, 1200
        cols, rows = 3, 3
        cell_w, cell_h = grid_w // cols, grid_h // rows
        padding = 4

        img = Image.new("RGB", (grid_w, grid_h), "#F5F5F5")
        draw = ImageDraw.Draw(img)

        bg_colors = ["#E3F2FD", "#FFF3E0", "#E8F5E9", "#FCE4EC", "#F3E5F5",
                      "#E0F7FA", "#FFF9C4", "#F1F8E9", "#EFEBE9"]

        try:
            font_title = ImageFont.truetype("arial.ttf", 22)
            font_label = ImageFont.truetype("arial.ttf", 16)
            font_desc = ImageFont.truetype("arial.ttf", 13)
            font_num = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font_title = ImageFont.load_default()
            font_label = font_title
            font_desc = font_title
            font_num = font_title

        while len(scenes) < 9:
            n = len(scenes) + 1
            scenes.append({"numero": n, "etiqueta": f"Escena {n}", "descripcion_visual": ""})

        for i in range(9):
            row_idx, col_idx = divmod(i, cols)
            x0 = col_idx * cell_w + padding
            y0 = row_idx * cell_h + padding
            x1 = (col_idx + 1) * cell_w - padding
            y1 = (row_idx + 1) * cell_h - padding

            draw.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=bg_colors[i], outline="#BDBDBD", width=1)

            scene = scenes[i]
            num = scene.get("numero", i + 1)
            label = scene.get("etiqueta", "")
            desc = scene.get("descripcion_visual", "")

            cr = 16
            cx, cy = x0 + 20, y0 + 20
            draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill="#4CAF50")
            num_text = str(num)
            bbox = font_num.getbbox(num_text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy - th // 2 - 2), num_text, fill="white", font=font_num)

            label_y = y0 + 45
            max_label_w = cell_w - padding * 2 - 20
            self._draw_wrapped_text(draw, label, font_label, x0 + 10, label_y, max_label_w, "#212121", max_lines=2)

            desc_y = label_y + 45
            max_desc_w = cell_w - padding * 2 - 20
            max_desc_h = y1 - desc_y - 10
            self._draw_wrapped_text(draw, desc, font_desc, x0 + 10, desc_y, max_desc_w, "#616161", max_lines=max_desc_h // 18)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    @staticmethod
    def _draw_wrapped_text(draw: Any, text: str, font: Any, x: int, y: int, max_width: int, fill: str, max_lines: int = 5):
        if not text:
            return
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test = f"{current_line} {word}".strip()
            bbox = font.getbbox(test)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for i, line in enumerate(lines[:max_lines]):
            if i == max_lines - 1 and len(lines) > max_lines:
                line = line[:max(0, len(line) - 3)] + "..."
            draw.text((x, y + i * 18), line, fill=fill, font=font)

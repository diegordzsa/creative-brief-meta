import base64
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MOCK_TRANSCRIPTION = """[0:00 - 0:06] ¿Sabías que el 80% de los productos anticaída no funcionan porque no atacan la raíz del problema?
[0:06 - 0:15] Yo llevaba años probando champús, ampollas, biotina... y nada. Cada vez perdía más pelo.
[0:15 - 0:25] Hasta que una dermatóloga me explicó algo que cambió todo: el problema no es el pelo que se cae, es el folículo que se está muriendo por falta de nutrientes específicos.
[0:25 - 0:40] Resulta que hay un compuesto, el acetyl tetrapeptide-3, que científicos en Suiza descubrieron que reactiva los folículos dormidos estimulando las células madre del bulbo capilar.
[0:40 - 0:55] Hair Biolabs tiene el REDENSIFY con este compuesto más Scutellaria baicalensis, que reduce la inflamación del cuero cabelludo. En 30 días notas menos caída, y en 90 días ves pelos nuevos.
[0:55 - 1:10] Yo llevo 4 meses y la diferencia es brutal. Mira, aquí tengo las fotos. Ahora mismo tienen oferta con envío gratis. El enlace está aquí abajo."""


class MediaProcessor:
    def __init__(self, anthropic_api_key: str = ""):
        self.anthropic_api_key = anthropic_api_key
        self.mock_mode = not anthropic_api_key
        if self.mock_mode:
            logger.warning("ANTHROPIC_API_KEY not set — MediaProcessor running in MOCK mode")

    def download_video(self, video_url: str, output_dir: str | None = None) -> str:
        if self.mock_mode:
            mock_path = os.path.join(output_dir or tempfile.gettempdir(), "mock_video.mp4")
            logger.info(f"Mock mode: would download {video_url} to {mock_path}")
            return mock_path

        output_dir = output_dir or tempfile.mkdtemp(prefix="hb_video_")
        output_path = os.path.join(output_dir, "video.mp4")

        cmd = [
            "yt-dlp",
            "--no-check-certificates",
            "-o", output_path,
            video_url,
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return output_path

    def extract_frames(self, video_path: str, fps_interval: int = 5, max_frames: int = 20) -> list[str]:
        if self.mock_mode:
            logger.info(f"Mock mode: would extract frames from {video_path}")
            return [f"mock_frame_{i:03d}.jpg" for i in range(min(12, max_frames))]

        output_dir = os.path.join(os.path.dirname(video_path), "frames")
        os.makedirs(output_dir, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", f"fps=1/{fps_interval}",
            "-frames:v", str(max_frames),
            os.path.join(output_dir, "frame_%03d.jpg"),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        frames = sorted(Path(output_dir).glob("frame_*.jpg"))
        return [str(f) for f in frames]

    def _extract_audio(self, video_path: str) -> str:
        audio_path = video_path.rsplit(".", 1)[0] + ".mp3"
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "4",
            audio_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return audio_path

    def transcribe_audio(self, video_path: str, language: str = "es") -> str:
        if self.mock_mode:
            logger.info("Mock mode: returning sample transcription")
            return MOCK_TRANSCRIPTION

        import anthropic

        audio_path = self._extract_audio(video_path)

        with open(audio_path, "rb") as f:
            audio_data = base64.standard_b64encode(f.read()).decode("utf-8")

        client = anthropic.Anthropic(api_key=self.anthropic_api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "audio/mpeg",
                            "data": audio_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Transcribe this audio in {language} (Spanish). "
                            "Return ONLY the transcription with timestamps in this exact format, one segment per line:\n"
                            "[M:SS - M:SS] transcribed text here\n\n"
                            "Group the text into natural segments of 5-15 seconds each. "
                            "Be precise with the timestamps. Do not add any commentary or headers."
                        ),
                    },
                ],
            }],
        )

        return response.content[0].text.strip()

    def process_video_file(self, video_path: str, fps_interval: int = 5, max_frames: int = 20) -> dict[str, Any]:
        if self.mock_mode:
            frames = self.extract_frames(video_path, fps_interval, max_frames)
            transcription = self.transcribe_audio(video_path)
            return {
                "frames": frames,
                "transcription": transcription,
                "video_path": video_path,
            }

        frames = self.extract_frames(video_path, fps_interval, max_frames)
        transcription = self.transcribe_audio(video_path)

        stable_frames = []
        stable_dir = tempfile.mkdtemp(prefix="hb_frames_")
        for i, frame in enumerate(frames):
            dest = os.path.join(stable_dir, f"frame_{i:03d}.jpg")
            os.replace(frame, dest)
            stable_frames.append(dest)

        return {
            "frames": stable_frames,
            "transcription": transcription,
            "video_path": video_path,
        }

    def process_video(self, video_url: str, fps_interval: int = 5, max_frames: int = 20) -> dict[str, Any]:
        if self.mock_mode:
            video_path = self.download_video(video_url)
            frames = self.extract_frames(video_path, fps_interval, max_frames)
            transcription = self.transcribe_audio(video_path)
            return {
                "frames": frames,
                "transcription": transcription,
                "video_path": video_path,
            }

        with tempfile.TemporaryDirectory(prefix="hb_") as tmpdir:
            video_path = self.download_video(video_url, tmpdir)
            frames = self.extract_frames(video_path, fps_interval, max_frames)
            transcription = self.transcribe_audio(video_path)

            stable_frames = []
            stable_dir = tempfile.mkdtemp(prefix="hb_frames_")
            for i, frame in enumerate(frames):
                dest = os.path.join(stable_dir, f"frame_{i:03d}.jpg")
                os.replace(frame, dest)
                stable_frames.append(dest)

            return {
                "frames": stable_frames,
                "transcription": transcription,
                "video_path": video_path,
            }

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"

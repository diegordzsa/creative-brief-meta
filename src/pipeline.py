import logging
from typing import Any, Callable

from config.settings import ANTHROPIC_API_KEY, GOOGLE_DRIVE_FOLDER_ID, GOOGLE_SERVICE_ACCOUNT_JSON, SUPABASE_KEY, SUPABASE_URL
from src.media_processor import MediaProcessor
from src.classifier import Classifier
from src.brief_engine import BriefEngine
from src.google_docs_exporter import GoogleDocsExporter
from src.database import create_database

logger = logging.getLogger(__name__)


def analyze_video(
    video_url: str,
    on_progress: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    def progress(step: str, detail: str = ""):
        logger.info(f"[{step}] {detail}")
        if on_progress:
            on_progress(step, detail)

    media = MediaProcessor(anthropic_api_key=ANTHROPIC_API_KEY)
    classifier = Classifier(api_key=ANTHROPIC_API_KEY)
    brief_engine = BriefEngine(api_key=ANTHROPIC_API_KEY)

    progress("download", "Downloading and processing video...")
    media_result = media.process_video(video_url)

    progress("classify", "Classifying creative format...")
    analysis = classifier.classify(
        frames=media_result["frames"],
        transcription=media_result["transcription"],
        metrics={},
    )

    progress("briefs", "Generating briefs for 4 alternate formats...")
    ad = {
        "id": video_url,
        "name": video_url.split("/")[-1] if "/" in video_url else video_url,
        "video_url": video_url,
        "transcription": media_result["transcription"],
        "frames": media_result["frames"],
        "analysis": analysis,
        "metrics": {},
    }
    briefs = brief_engine.generate_briefs(ad)

    progress("done", "Analysis complete.")

    return {
        "video_url": video_url,
        "transcription": media_result["transcription"],
        "frames": media_result["frames"],
        "analysis": analysis,
        "briefs": briefs,
        "ad": ad,
    }


def analyze_video_file(
    video_path: str,
    file_name: str,
    on_progress: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    def progress(step: str, detail: str = ""):
        logger.info(f"[{step}] {detail}")
        if on_progress:
            on_progress(step, detail)

    media = MediaProcessor(anthropic_api_key=ANTHROPIC_API_KEY)
    classifier = Classifier(api_key=ANTHROPIC_API_KEY)
    brief_engine = BriefEngine(api_key=ANTHROPIC_API_KEY)

    progress("download", "Processing uploaded video...")
    media_result = media.process_video_file(video_path)

    progress("classify", "Classifying creative format...")
    analysis = classifier.classify(
        frames=media_result["frames"],
        transcription=media_result["transcription"],
        metrics={},
    )

    progress("briefs", "Generating briefs for 4 alternate formats...")
    ad = {
        "id": file_name,
        "name": file_name,
        "video_url": f"upload://{file_name}",
        "transcription": media_result["transcription"],
        "frames": media_result["frames"],
        "analysis": analysis,
        "metrics": {},
    }
    briefs = brief_engine.generate_briefs(ad)

    progress("done", "Analysis complete.")

    return {
        "video_url": f"upload://{file_name}",
        "transcription": media_result["transcription"],
        "frames": media_result["frames"],
        "analysis": analysis,
        "briefs": briefs,
        "ad": ad,
    }


def export_to_google_docs(result: dict[str, Any]) -> str:
    exporter = GoogleDocsExporter(
        service_account_json=GOOGLE_SERVICE_ACCOUNT_JSON,
        drive_folder_id=GOOGLE_DRIVE_FOLDER_ID,
    )
    return exporter.export_single_analysis(
        analysis=result["analysis"],
        briefs=result["briefs"],
        video_url=result["video_url"],
        transcription=result["transcription"],
    )


def save_to_database(result: dict[str, Any]) -> None:
    db = create_database(url=SUPABASE_URL, key=SUPABASE_KEY)
    db.upsert_ad(result["ad"])
    for brief in result["briefs"]:
        db.insert_brief(
            ad_id=result["video_url"],
            tipo="BRIEF",
            brief_content=brief["content"],
            formato_origen=brief["formato_origen"],
            formato_destino=brief["formato_destino"],
        )

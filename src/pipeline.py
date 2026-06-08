import logging
from datetime import datetime, timezone
from typing import Any, Callable

from config.settings import (
    ANTHROPIC_API_KEY,
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    OPENAI_API_KEY,
    SUPABASE_KEY,
    SUPABASE_URL,
)
from src.media_processor import MediaProcessor
from src.classifier import Classifier
from src.brief_engine import BriefEngine, build_header_data
from src.storyboard_generator import StoryboardGenerator
from src.pdf_generator import BriefPDFGenerator
from src.google_docs_exporter import GoogleDocsExporter
from src.database import create_database

logger = logging.getLogger(__name__)


def _run_pipeline(
    media_result: dict[str, Any],
    file_name: str,
    video_url: str,
    on_progress: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    def progress(step: str, detail: str = ""):
        logger.info(f"[{step}] {detail}")
        if on_progress:
            on_progress(step, detail)

    classifier = Classifier(api_key=ANTHROPIC_API_KEY)
    brief_engine = BriefEngine(api_key=ANTHROPIC_API_KEY)
    storyboard_gen = StoryboardGenerator(openai_api_key=OPENAI_API_KEY)

    progress("classify", "Classifying creative format...")
    analysis = classifier.classify(
        frames=media_result["frames"],
        transcription=media_result["transcription"],
        metrics={},
    )

    progress("briefs", "Generating briefs for alternate formats...")
    ad = {
        "id": video_url,
        "name": file_name,
        "video_url": video_url,
        "transcription": media_result["transcription"],
        "frames": media_result["frames"],
        "analysis": analysis,
        "metrics": {},
    }
    briefs = brief_engine.generate_briefs(ad)
    header_data = build_header_data(analysis)

    progress("storyboards", "Generating storyboard reference images...")
    storyboard_images = {}
    for brief in briefs:
        fmt_name = brief.get("formato_destino", "")
        scenes = brief.get("escenas", [])
        try:
            img_bytes = storyboard_gen.generate_storyboard(scenes, fmt_name)
            storyboard_images[fmt_name] = img_bytes
        except Exception as e:
            logger.error(f"Storyboard generation failed for {fmt_name}: {e}")
            storyboard_images[fmt_name] = b""

    progress("pdf", "Generating PDF brief...")
    pdf_gen = BriefPDFGenerator()
    try:
        pdf_bytes = pdf_gen.generate(header_data, briefs, storyboard_images)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        pdf_bytes = b""

    progress("done", "Analysis complete.")

    return {
        "video_url": video_url,
        "transcription": media_result["transcription"],
        "frames": media_result["frames"],
        "analysis": analysis,
        "briefs": briefs,
        "header_data": header_data,
        "storyboard_images": storyboard_images,
        "pdf_bytes": pdf_bytes,
        "ad": ad,
    }


def analyze_video(
    video_url: str,
    on_progress: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    def progress(step: str, detail: str = ""):
        logger.info(f"[{step}] {detail}")
        if on_progress:
            on_progress(step, detail)

    media = MediaProcessor(anthropic_api_key=ANTHROPIC_API_KEY)
    progress("download", "Downloading and processing video...")
    media_result = media.process_video(video_url)

    file_name = video_url.split("/")[-1] if "/" in video_url else video_url
    return _run_pipeline(media_result, file_name, video_url, on_progress)


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
    progress("download", "Processing uploaded video...")
    media_result = media.process_video_file(video_path)

    return _run_pipeline(media_result, file_name, f"upload://{file_name}", on_progress)


def export_pdf_to_drive(result: dict[str, Any]) -> str:
    exporter = GoogleDocsExporter(
        service_account_json=GOOGLE_SERVICE_ACCOUNT_JSON,
        drive_folder_id=GOOGLE_DRIVE_FOLDER_ID,
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"[{today}] HairBiolabs ES — Brief.pdf"
    return exporter.upload_pdf_to_drive(result["pdf_bytes"], filename)


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
            brief_content=brief.get("speech", ""),
            formato_origen=brief["formato_origen"],
            formato_destino=brief["formato_destino"],
        )


def save_session(result: dict[str, Any], username: str, source_name: str) -> str | None:
    try:
        db = create_database(url=SUPABASE_URL, key=SUPABASE_KEY)

        serializable_briefs = []
        for b in result.get("briefs", []):
            serializable_briefs.append({
                k: v for k, v in b.items()
                if isinstance(v, (str, int, float, bool, list, dict, type(None)))
            })

        session_data = {
            "username": username,
            "source_name": source_name,
            "video_url": result.get("video_url", ""),
            "formato_detectado": result.get("header_data", {}).get("formato_detectado", ""),
            "header_data": result.get("header_data", {}),
            "briefs": serializable_briefs,
            "pdf_storage_path": "",
        }

        session_id = db.save_session(session_data)

        pdf_bytes = result.get("pdf_bytes", b"")
        if pdf_bytes:
            try:
                pdf_path = db.upload_pdf(session_id, pdf_bytes)
                db.update_session_pdf_path(session_id, pdf_path)
            except Exception as e:
                logger.warning(f"PDF upload failed (session still saved): {e}")

        return session_id
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        return None


def get_recent_sessions(username: str, limit: int = 10) -> list[dict]:
    try:
        db = create_database(url=SUPABASE_URL, key=SUPABASE_KEY)
        return db.get_recent_sessions(username, limit)
    except Exception as e:
        logger.error(f"Failed to fetch sessions: {e}")
        return []


def get_session_pdf(pdf_storage_path: str) -> bytes:
    try:
        db = create_database(url=SUPABASE_URL, key=SUPABASE_KEY)
        return db.download_pdf(pdf_storage_path)
    except Exception as e:
        logger.error(f"Failed to download PDF: {e}")
        return b""

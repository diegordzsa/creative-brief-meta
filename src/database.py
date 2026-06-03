import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class MockDatabase:
    def __init__(self):
        self._ads: dict[str, dict] = {}
        self._briefs: list[dict] = []

    def upsert_ad(self, ad_data: dict[str, Any]) -> None:
        self._ads[ad_data.get("video_url") or ad_data["id"]] = {
            **ad_data,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Mock DB: upserted ad {ad_data.get('video_url', ad_data.get('id', ''))}")

    def insert_brief(self, ad_id: str, tipo: str, brief_content: str, formato_origen: str = "", formato_destino: str = "", google_doc_url: str = "") -> None:
        self._briefs.append({
            "ad_id": ad_id,
            "tipo": tipo,
            "formato_origen": formato_origen,
            "formato_destino": formato_destino,
            "brief_content": brief_content,
            "google_doc_url": google_doc_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Mock DB: inserted brief for {ad_id} ({tipo}: {formato_origen} → {formato_destino})")

    def get_by_video_url(self, url: str) -> dict | None:
        return self._ads.get(url)


class SupabaseDatabase:
    def __init__(self, url: str, key: str):
        from supabase import create_client
        self.client = create_client(url, key)

    def upsert_ad(self, ad_data: dict[str, Any]) -> None:
        analysis = ad_data.get("analysis", {})
        row = {
            "id": ad_data.get("video_url") or ad_data.get("id", ""),
            "name": ad_data.get("name", ""),
            "video_url": ad_data.get("video_url", ""),
            "formato_detectado": analysis.get("formato_detectado"),
            "confianza": analysis.get("confianza"),
            "avatar_deseo": analysis.get("deseo_avatar"),
            "avatar_situacion": analysis.get("situacion_avatar"),
            "angulo": analysis.get("angulo_ganador"),
            "mecanismo": analysis.get("mecanismo"),
            "villain": analysis.get("villain"),
            "nivel_awareness": analysis.get("nivel_awareness"),
            "transcription": ad_data.get("transcription", ""),
            "analysis_json": json.dumps(analysis),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.client.table("ads").upsert(row).execute()

    def insert_brief(self, ad_id: str, tipo: str, brief_content: str, formato_origen: str = "", formato_destino: str = "", google_doc_url: str = "") -> None:
        row = {
            "ad_id": ad_id,
            "tipo": tipo,
            "formato_origen": formato_origen,
            "formato_destino": formato_destino,
            "brief_content": brief_content,
            "google_doc_url": google_doc_url,
        }
        self.client.table("briefs").insert(row).execute()

    def get_by_video_url(self, url: str) -> dict | None:
        response = self.client.table("ads").select("*").eq("video_url", url).execute()
        return response.data[0] if response.data else None


def create_database(url: str = "", key: str = "") -> MockDatabase | SupabaseDatabase:
    if url and key:
        logger.info("Using Supabase database")
        return SupabaseDatabase(url, key)
    logger.warning("SUPABASE credentials not set — using in-memory mock database")
    return MockDatabase()

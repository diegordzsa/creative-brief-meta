import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class MockDatabase:
    def __init__(self):
        self._ads: dict[str, dict] = {}
        self._briefs: list[dict] = []
        self._sessions: dict[str, dict] = {}
        self._pdf_store: dict[str, bytes] = {}

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

    def save_session(self, session_data: dict[str, Any]) -> str:
        import uuid
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            **session_data,
            "id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Mock DB: saved session {session_id}")
        return session_id

    def get_recent_sessions(self, username: str, limit: int = 10) -> list[dict]:
        user_sessions = [s for s in self._sessions.values() if s.get("username") == username]
        user_sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return user_sessions[:limit]

    def upload_pdf(self, session_id: str, pdf_bytes: bytes) -> str:
        path = f"pdfs/{session_id}.pdf"
        self._pdf_store[path] = pdf_bytes
        logger.info(f"Mock DB: stored PDF at {path}")
        return path

    def update_session_pdf_path(self, session_id: str, pdf_path: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["pdf_storage_path"] = pdf_path

    def download_pdf(self, storage_path: str) -> bytes:
        return self._pdf_store.get(storage_path, b"")


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

    def save_session(self, session_data: dict[str, Any]) -> str:
        row = {
            "username": session_data["username"],
            "source_name": session_data["source_name"],
            "video_url": session_data.get("video_url", ""),
            "formato_detectado": session_data.get("formato_detectado", ""),
            "header_data": json.dumps(session_data.get("header_data", {})),
            "briefs_json": json.dumps(session_data.get("briefs", [])),
            "pdf_storage_path": session_data.get("pdf_storage_path", ""),
        }
        result = self.client.table("sessions").insert(row).execute()
        return result.data[0]["id"]

    def get_recent_sessions(self, username: str, limit: int = 10) -> list[dict]:
        response = (
            self.client.table("sessions")
            .select("id, source_name, formato_detectado, header_data, briefs_json, pdf_storage_path, created_at")
            .eq("username", username)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def upload_pdf(self, session_id: str, pdf_bytes: bytes) -> str:
        path = f"{session_id}.pdf"
        self.client.storage.from_("pdfs").upload(
            path, pdf_bytes, {"content-type": "application/pdf"}
        )
        return path

    def update_session_pdf_path(self, session_id: str, pdf_path: str) -> None:
        self.client.table("sessions").update(
            {"pdf_storage_path": pdf_path}
        ).eq("id", session_id).execute()

    def download_pdf(self, storage_path: str) -> bytes:
        return self.client.storage.from_("pdfs").download(storage_path)


def create_database(url: str = "", key: str = "") -> MockDatabase | SupabaseDatabase:
    if url and key:
        logger.info("Using Supabase database")
        return SupabaseDatabase(url, key)
    logger.warning("SUPABASE credentials not set — using in-memory mock database")
    return MockDatabase()

import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class GoogleDocsExporter:
    def __init__(self, service_account_json: str = "", drive_folder_id: str = ""):
        self.drive_folder_id = drive_folder_id
        self.mock_mode = not service_account_json
        self._docs_service = None
        self._drive_service = None

        if self.mock_mode:
            logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON not set — GoogleDocsExporter running in MOCK mode")
        else:
            self._init_services(service_account_json)

    def _init_services(self, service_account_json: str):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_dict = json.loads(service_account_json)
        scopes = [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        self._docs_service = build("docs", "v1", credentials=creds)
        self._drive_service = build("drive", "v3", credentials=creds)

    def export_single_analysis(
        self,
        analysis: dict[str, Any],
        briefs: list[dict[str, Any]],
        video_url: str = "",
        transcription: str = "",
    ) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        title = f"[{today}] HairBiolabs ES — Análisis de Ad"

        if self.mock_mode:
            return self._mock_single_export(title, analysis, briefs, video_url, transcription)

        doc_id = self._create_doc(title)
        self._populate_single_analysis(doc_id, analysis, briefs, video_url, transcription)

        if self.drive_folder_id:
            self._move_to_folder(doc_id)

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        logger.info(f"Google Doc created: {doc_url}")
        return doc_url

    def _create_doc(self, title: str) -> str:
        doc = self._docs_service.documents().create(body={"title": title}).execute()
        return doc["documentId"]

    def _move_to_folder(self, doc_id: str):
        file = self._drive_service.files().get(fileId=doc_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents", []))
        self._drive_service.files().update(
            fileId=doc_id,
            addParents=self.drive_folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()

    def _populate_single_analysis(
        self,
        doc_id: str,
        analysis: dict[str, Any],
        briefs: list[dict[str, Any]],
        video_url: str,
        transcription: str,
    ):
        requests = []
        insert_index = 1

        def add_text(text: str, style: str = "NORMAL_TEXT") -> int:
            nonlocal insert_index
            requests.append({
                "insertText": {"location": {"index": insert_index}, "text": text + "\n"}
            })
            end_index = insert_index + len(text)
            if style != "NORMAL_TEXT":
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": insert_index, "endIndex": end_index + 1},
                        "paragraphStyle": {"namedStyleType": style},
                        "fields": "namedStyleType",
                    }
                })
            insert_index = end_index + 1
            return insert_index

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        add_text(f"{today} | Análisis de Ad — Hair Biolabs España", "HEADING_1")
        add_text("")

        if video_url:
            add_text(f"Video: {video_url}")
            add_text("")

        add_text("CLASIFICACIÓN", "HEADING_2")
        add_text(f"Formato detectado: {analysis.get('formato_detectado', '')}")
        add_text(f"Confianza: {analysis.get('confianza', 0)}%")
        add_text(f"Deseo del avatar: {analysis.get('deseo_avatar', '')}")
        add_text(f"Situación del avatar: {analysis.get('situacion_avatar', '')}")
        add_text(f"Ángulo ganador: {analysis.get('angulo_ganador', '')}")
        add_text(f"Mecanismo: {analysis.get('mecanismo', '')}")
        add_text(f"Villain: {analysis.get('villain', '')}")
        add_text(f"Nivel awareness: {analysis.get('nivel_awareness', '')}")
        add_text("")

        segments = analysis.get("segmentos", [])
        if segments:
            add_text("SEGMENTOS DETECTADOS", "HEADING_2")
            for seg in segments:
                add_text(f"[{seg.get('timestamp_inicio', '')} - {seg.get('timestamp_fin', '')}] {seg.get('nombre', '')}: {seg.get('descripcion', '')}")
            add_text("")

        if analysis.get("elementos_que_funcionan"):
            add_text("ELEMENTOS QUE FUNCIONAN", "HEADING_2")
            for elem in analysis["elementos_que_funcionan"]:
                add_text(f"• {elem}")
            add_text("")

        if transcription:
            add_text("TRANSCRIPCIÓN", "HEADING_2")
            add_text(transcription)
            add_text("")

        if briefs:
            add_text("BRIEFS GENERADOS", "HEADING_2")
            add_text("")
            for brief in briefs:
                add_text(f"Brief — {brief.get('formato_destino', '')}", "HEADING_3")
                add_text(f"(Formato origen: {brief.get('formato_origen', '')})")
                add_text("")
                add_text(brief.get("content", ""))
                add_text("")

        if requests:
            self._docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()

    def upload_pdf_to_drive(self, pdf_bytes: bytes, filename: str) -> str:
        if self.mock_mode:
            mock_url = f"https://drive.google.com/file/d/MOCK_{filename.replace(' ', '_')}/view"
            logger.info(f"Mock PDF upload: {mock_url}")
            return mock_url

        from googleapiclient.http import MediaIoBaseUpload

        file_metadata = {
            "name": filename,
            "mimeType": "application/pdf",
        }
        if self.drive_folder_id:
            file_metadata["parents"] = [self.drive_folder_id]

        media = MediaIoBaseUpload(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            resumable=True,
        )

        file = self._drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()

        file_url = file.get("webViewLink", f"https://drive.google.com/file/d/{file['id']}/view")
        logger.info(f"PDF uploaded to Drive: {file_url}")
        return file_url

    def _mock_single_export(
        self,
        title: str,
        analysis: dict[str, Any],
        briefs: list[dict[str, Any]],
        video_url: str,
        transcription: str,
    ) -> str:
        logger.info(f"Mock export: '{title}'")
        logger.info(f"  Format: {analysis.get('formato_detectado', '')}, Briefs: {len(briefs)}")

        doc_content = [f"# {title}\n"]
        if video_url:
            doc_content.append(f"Video: {video_url}\n")

        doc_content.append("## CLASIFICACIÓN")
        doc_content.append(f"- Formato: {analysis.get('formato_detectado', '')}")
        doc_content.append(f"- Confianza: {analysis.get('confianza', 0)}%")
        doc_content.append(f"- Avatar: {analysis.get('deseo_avatar', '')}")
        doc_content.append(f"- Mecanismo: {analysis.get('mecanismo', '')}")
        doc_content.append(f"- Villain: {analysis.get('villain', '')}\n")

        if briefs:
            doc_content.append("## BRIEFS GENERADOS\n")
            for b in briefs:
                doc_content.append(f"### Brief — {b.get('formato_destino', '')}")
                content = b.get("content", "")
                doc_content.append(content[:500] + "...\n" if len(content) > 500 else content + "\n")

        mock_url = f"https://docs.google.com/document/d/MOCK_{title.replace(' ', '_')}/edit"
        logger.info(f"Mock doc URL: {mock_url}")
        return mock_url

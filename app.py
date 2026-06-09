import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import streamlit_authenticator as stauth
import tempfile
import os
from datetime import datetime, timezone
from src.pipeline import (
    analyze_video, analyze_video_file, export_pdf_to_drive,
    save_session, get_recent_sessions, get_session_pdf,
)

st.set_page_config(
    page_title="Hair Biolabs — Creative Brief Generator",
    page_icon="\U0001f487",
    layout="wide",
)

creds = {"usernames": {}}
try:
    users = st.secrets["credentials"]["usernames"]
    for username in users:
        user = users[username]
        creds["usernames"][str(username)] = {
            "name": str(user["name"]),
            "email": str(user["email"]),
            "password": str(user["password"]),
        }
except Exception:
    pass

if "remember_me_pref" not in st.session_state:
    st.session_state["remember_me_pref"] = True

_cookie_expiry = 30 if st.session_state["remember_me_pref"] else 0

authenticator = stauth.Authenticate(
    credentials=creds,
    cookie_name="hb_brief_auth",
    cookie_key=str(st.secrets.get("auth", {}).get("cookie_key", "dev_fallback_key_change_me")),
    cookie_expiry_days=_cookie_expiry,
    auto_hash=False,
)

if not st.session_state.get("authentication_status"):
    remember = st.checkbox("Recordarme", value=st.session_state["remember_me_pref"])
    if remember != st.session_state["remember_me_pref"]:
        st.session_state["remember_me_pref"] = remember
        if not remember:
            authenticator.cookie_controller.delete_cookie()
        st.rerun()

authenticator.login(location="main")

if st.session_state.get("authentication_status"):
    authenticator.logout("Cerrar sesion", location="sidebar")
    st.sidebar.write(f"Hola, **{st.session_state.get('name', '')}**")

    # --- Session history sidebar ---
    st.sidebar.divider()
    st.sidebar.markdown("**Historial reciente**")

    _hist_username = st.session_state.get("username", "unknown")
    if "_history_cache" not in st.session_state:
        st.session_state["_history_cache"] = get_recent_sessions(_hist_username, limit=10)

    _hist_sessions = st.session_state["_history_cache"]

    if not _hist_sessions:
        st.sidebar.caption("Sin sesiones anteriores")
    else:
        for _s in _hist_sessions:
            _created = _s.get("created_at", "")
            try:
                _dt = datetime.fromisoformat(str(_created).replace("Z", "+00:00"))
                _date_label = _dt.strftime("%d %b %Y · %H:%M")
            except (ValueError, AttributeError):
                _date_label = str(_created)[:16] if _created else "—"

            _source = _s.get("source_name", "—")
            if len(_source) > 35:
                _source = _source[:32] + "..."

            _formato = _s.get("formato_detectado", "")
            if _formato and len(_formato) > 30:
                _formato = _formato.split(":")[0] if ":" in _formato else _formato[:30]

            _btn_label = f"{_date_label}\n{_source}"
            if _formato:
                _btn_label += f"\n{_formato}"

            if st.sidebar.button(_btn_label, key=f"hist_{_s['id']}", use_container_width=True):
                st.session_state["viewing_history"] = _s["id"]
                st.session_state.pop("result", None)
                st.rerun()

    st.sidebar.divider()

    st.title("Hair Biolabs — Creative Brief Generator")
    st.markdown("Sube un video o pega un enlace para analizar el formato creativo y generar briefs para los formatos alternativos.")

    tab_url, tab_upload = st.tabs(["Pegar enlace", "Subir archivo"])

    with tab_url:
        video_url = st.text_input("Video URL", placeholder="https://example.com/video.mp4")
        analyze_url = st.button("Analizar", type="primary", disabled=not video_url, key="btn_url")

    with tab_upload:
        uploaded_file = st.file_uploader("Sube un video MP4", type=["mp4"])
        analyze_upload = st.button("Analizar", type="primary", disabled=uploaded_file is None, key="btn_upload")

    def _make_progress_callback(status_widget):
        def on_progress(step: str, detail: str):
            labels = {
                "download": "⬇️ Descargando y procesando video...",
                "classify": "\U0001f50d Clasificando formato creativo...",
                "briefs": "✍️ Generando briefs para formatos alternativos...",
                "storyboards": "\U0001f3a8 Generando storyboards de referencia...",
                "pdf": "\U0001f4c4 Generando PDF del brief...",
                "done": "✅ Analisis completo!",
            }
            status_widget.update(label=labels.get(step, detail))
            status_widget.write(detail)
        return on_progress

    if analyze_url:
        st.session_state.pop("viewing_history", None)
        progress = st.status("Analizando video...", expanded=True)
        try:
            result = analyze_video(video_url, on_progress=_make_progress_callback(progress))
            progress.update(label="✅ Analisis completo!", state="complete", expanded=False)
            st.session_state["result"] = result
            _username = st.session_state.get("username", "unknown")
            save_session(result, _username, video_url)
            st.session_state.pop("_history_cache", None)
        except Exception as e:
            progress.update(label="❌ Error", state="error", expanded=False)
            st.error(f"Error al analizar el video: {e}")

    if analyze_upload and uploaded_file is not None:
        st.session_state.pop("viewing_history", None)
        progress = st.status("Analizando video...", expanded=True)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        try:
            result = analyze_video_file(tmp_path, uploaded_file.name, on_progress=_make_progress_callback(progress))
            progress.update(label="✅ Analisis completo!", state="complete", expanded=False)
            st.session_state["result"] = result
            _username = st.session_state.get("username", "unknown")
            save_session(result, _username, uploaded_file.name)
            st.session_state.pop("_history_cache", None)
        except Exception as e:
            progress.update(label="❌ Error", state="error", expanded=False)
            st.error(f"Error al analizar el video: {e}")
        finally:
            os.unlink(tmp_path)

    # --- Viewing a historical session ---
    if "viewing_history" in st.session_state and "result" not in st.session_state:
        import json as _json
        _session_id = st.session_state["viewing_history"]
        _hist_list = st.session_state.get("_history_cache", [])
        _hist_session = next((s for s in _hist_list if s["id"] == _session_id), None)

        if _hist_session:
            _hd = _hist_session.get("header_data", {})
            if isinstance(_hd, str):
                _hd = _json.loads(_hd)

            _hb = _hist_session.get("briefs_json", [])
            if isinstance(_hb, str):
                _hb = _json.loads(_hb)

            st.info("Estas viendo una sesion anterior. Analiza un nuevo video para crear una sesion nueva.")
            st.divider()

            st.subheader("Video ganador analizado")
            st.markdown(f"**Formato detectado:** {_hd.get('formato_detectado', '')}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Deseo (NO cambiar):**  \n{_hd.get('deseo', '')}")
                st.markdown(f"**Nivel awareness:** {_hd.get('nivel_awareness', '')}")
            with col2:
                st.markdown(f"**Avatar / situacion (NO cambiar):**  \n{_hd.get('avatar_situacion', '')}")

            with st.expander("Angulo ganador y mecanismo"):
                st.markdown(f"**Angulo:** {_hd.get('angulo_ganador', '')}")
                st.markdown(f"**Mecanismo:** {_hd.get('mecanismo', '')}")
                st.markdown(f"**Villain:** {_hd.get('villain', '')}")

            st.divider()

            _pdf_path = _hist_session.get("pdf_storage_path", "")
            if _pdf_path:
                _pdf_data = get_session_pdf(_pdf_path)
                if _pdf_data:
                    _created = _hist_session.get("created_at", "")
                    try:
                        _dt = datetime.fromisoformat(str(_created).replace("Z", "+00:00"))
                        _date_str = _dt.strftime("%Y-%m-%d")
                    except (ValueError, AttributeError):
                        _date_str = "unknown"
                    st.download_button(
                        label="\U0001f4e5 Descargar PDF",
                        data=_pdf_data,
                        file_name=f"brief_{_date_str}_hair_biolabs.pdf",
                        mime="application/pdf",
                        type="primary",
                    )
                else:
                    st.warning("No se pudo descargar el PDF")
            else:
                st.caption("PDF no disponible para esta sesion")

            st.divider()

            st.subheader("Briefs generados")
            if _hb:
                _tabs = st.tabs([str(b.get("formato_numero", i + 1)) for i, b in enumerate(_hb)])
                for _tab, _brief in zip(_tabs, _hb):
                    with _tab:
                        st.markdown(f"### {_brief.get('formato_numero', '')}. {_brief.get('formato_destino', '')}")
                        st.markdown("**Explicacion del formato**")
                        st.markdown(_brief.get("explicacion", ""))
                        _nota = _brief.get("nota_legal")
                        if _nota:
                            st.info(f"**Notacion antes de grabar (nexo legal):** {_nota}")
                        st.markdown("**Speech (en parrafo · grabar tal cual)**")
                        st.markdown(_brief.get("speech", ""))
                        _ref = _brief.get("video_referencia", "")
                        if _ref:
                            st.caption(f"Video de referencia del formato: {_ref}")

    if "result" in st.session_state:
        result = st.session_state["result"]
        analysis = result["analysis"]
        briefs = result["briefs"]
        header_data = result.get("header_data", {})
        storyboard_images = result.get("storyboard_images", {})
        pdf_bytes = result.get("pdf_bytes", b"")

        st.divider()

        # --- Header: what stays the same ---
        st.subheader("Video ganador analizado")
        st.markdown(f"**Formato detectado:** {header_data.get('formato_detectado', '')}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Deseo (NO cambiar):**  \n{header_data.get('deseo', '')}")
            st.markdown(f"**Nivel awareness:** {header_data.get('nivel_awareness', '')}")
        with col2:
            st.markdown(f"**Avatar / situacion (NO cambiar):**  \n{header_data.get('avatar_situacion', '')}")

        with st.expander("Angulo ganador y mecanismo"):
            st.markdown(f"**Angulo:** {header_data.get('angulo_ganador', '')}")
            st.markdown(f"**Mecanismo:** {header_data.get('mecanismo', '')}")
            st.markdown(f"**Villain:** {header_data.get('villain', '')}")

        if result.get("transcription"):
            with st.expander("Transcripcion completa"):
                st.text(result["transcription"])

        st.divider()

        # --- Download + Upload buttons ---
        col_dl, col_drive = st.columns(2)

        with col_dl:
            if pdf_bytes:
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                st.download_button(
                    label="\U0001f4e5 Descargar PDF",
                    data=pdf_bytes,
                    file_name=f"brief_{today}_hair_biolabs.pdf",
                    mime="application/pdf",
                    type="primary",
                )
            else:
                st.warning("PDF no disponible")

        with col_drive:
            if st.button("☁️ Subir PDF a Google Drive"):
                if pdf_bytes:
                    with st.spinner("Subiendo PDF a Google Drive..."):
                        drive_url = export_pdf_to_drive(result)
                    st.success(f"PDF subido: {drive_url}")
                else:
                    st.warning("No hay PDF para subir")

        st.divider()

        # --- Briefs by format ---
        st.subheader("Briefs generados")

        tabs = st.tabs([str(b.get("formato_numero", i+1)) for i, b in enumerate(briefs)])
        for tab, brief in zip(tabs, briefs):
            with tab:
                st.markdown(f"### {brief.get('formato_numero', '')}. {brief.get('formato_destino', '')}")

                fmt_name = brief.get("formato_destino", "")
                img_bytes = storyboard_images.get(fmt_name, b"")
                if img_bytes:
                    st.image(img_bytes, caption="Foto de referencia-GUIA de la escena (que montar · no es el anuncio final)", use_container_width=True)

                st.markdown("**Explicacion del formato**")
                st.markdown(brief.get("explicacion", ""))

                nota = brief.get("nota_legal")
                if nota:
                    st.info(f"**Notacion antes de grabar (nexo legal):** {nota}")

                st.markdown("**Speech (en parrafo · grabar tal cual)**")
                st.markdown(brief.get("speech", ""))

                ref_video = brief.get("video_referencia", "")
                if ref_video:
                    st.caption(f"Video de referencia del formato: {ref_video}")

elif st.session_state.get("authentication_status") is False:
    st.error("Usuario o contrasena incorrectos")
else:
    st.info("Introduce tus credenciales para acceder")

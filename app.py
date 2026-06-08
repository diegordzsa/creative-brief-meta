import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import streamlit_authenticator as stauth
import tempfile
import os
from datetime import datetime, timezone
from src.pipeline import analyze_video, analyze_video_file, export_pdf_to_drive, save_to_database

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

authenticator = stauth.Authenticate(
    credentials=creds,
    cookie_name="hb_brief_auth",
    cookie_key=str(st.secrets.get("auth", {}).get("cookie_key", "dev_fallback_key_change_me")),
    cookie_expiry_days=30 if st.session_state["remember_me_pref"] else 0,
    auto_hash=False,
)

authenticator.login(location="main")

if not st.session_state.get("authentication_status"):
    remember = st.checkbox("Recordarme", value=st.session_state["remember_me_pref"])
    st.session_state["remember_me_pref"] = remember

if st.session_state.get("authentication_status"):
    authenticator.logout("Cerrar sesion", location="sidebar")
    st.sidebar.write(f"Hola, **{st.session_state.get('name', '')}**")

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
        progress = st.status("Analizando video...", expanded=True)
        result = analyze_video(video_url, on_progress=_make_progress_callback(progress))
        progress.update(label="✅ Analisis completo!", state="complete", expanded=False)
        st.session_state["result"] = result

    if analyze_upload and uploaded_file is not None:
        progress = st.status("Analizando video...", expanded=True)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        try:
            result = analyze_video_file(tmp_path, uploaded_file.name, on_progress=_make_progress_callback(progress))
        finally:
            os.unlink(tmp_path)
        progress.update(label="✅ Analisis completo!", state="complete", expanded=False)
        st.session_state["result"] = result

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
        col_dl, col_drive, col_db = st.columns(3)

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

        with col_db:
            if st.button("\U0001f4be Guardar en base de datos"):
                with st.spinner("Guardando en base de datos..."):
                    save_to_database(result)
                st.success("Guardado en base de datos.")

        st.divider()

        # --- Briefs by format ---
        st.subheader("Briefs generados")

        tabs = st.tabs([f"Formato {b.get('formato_numero', i+1)}/{b.get('formato_total', len(briefs))}" for i, b in enumerate(briefs)])
        for tab, brief in zip(tabs, briefs):
            with tab:
                st.markdown(f"### {brief.get('formato_destino', '')}")

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

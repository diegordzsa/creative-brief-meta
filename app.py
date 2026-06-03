import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import streamlit_authenticator as stauth
import tempfile
import os
from src.pipeline import analyze_video, analyze_video_file, export_to_google_docs, save_to_database

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

authenticator = stauth.Authenticate(
    credentials=creds,
    cookie_name="hb_brief_auth",
    cookie_key=str(st.secrets.get("auth", {}).get("cookie_key", "dev_fallback_key_change_me")),
    cookie_expiry_days=30,
    auto_hash=False,
)

authenticator.login(location="main")

if st.session_state.get("authentication_status"):
    authenticator.logout("Cerrar sesion", location="sidebar")
    st.sidebar.write(f"Hola, **{st.session_state.get('name', '')}**")

    st.title("Hair Biolabs — Creative Brief Generator")
    st.markdown("Provide a video URL or upload an MP4 file to analyze the creative format and generate briefs for the 4 alternate formats.")

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
                "download": "⬇️ Downloading and processing video...",
                "classify": "\U0001f50d Classifying creative format...",
                "briefs": "✍️ Generating briefs for 4 alternate formats...",
                "done": "✅ Analysis complete!",
            }
            status_widget.update(label=labels.get(step, detail))
            status_widget.write(detail)
        return on_progress

    if analyze_url:
        progress = st.status("Analyzing video...", expanded=True)
        result = analyze_video(video_url, on_progress=_make_progress_callback(progress))
        progress.update(label="✅ Analysis complete!", state="complete", expanded=False)
        st.session_state["result"] = result

    if analyze_upload and uploaded_file is not None:
        progress = st.status("Analyzing video...", expanded=True)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        try:
            result = analyze_video_file(tmp_path, uploaded_file.name, on_progress=_make_progress_callback(progress))
        finally:
            os.unlink(tmp_path)
        progress.update(label="✅ Analysis complete!", state="complete", expanded=False)
        st.session_state["result"] = result

    if "result" in st.session_state:
        result = st.session_state["result"]
        analysis = result["analysis"]
        briefs = result["briefs"]

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Clasificacion")
            st.metric("Formato detectado", analysis.get("formato_detectado", ""))
            st.metric("Confianza", f"{analysis.get('confianza', 0)}%")
            st.markdown(f"**Deseo del avatar:** {analysis.get('deseo_avatar', '')}")
            st.markdown(f"**Situacion del avatar:** {analysis.get('situacion_avatar', '')}")

        with col2:
            st.subheader("Elementos clave")
            st.markdown(f"**Angulo ganador:** {analysis.get('angulo_ganador', '')}")
            st.markdown(f"**Mecanismo:** {analysis.get('mecanismo', '')}")
            st.markdown(f"**Villain:** {analysis.get('villain', '')}")
            st.markdown(f"**Nivel awareness:** {analysis.get('nivel_awareness', '')}")

        segments = analysis.get("segmentos", [])
        if segments:
            st.subheader("Segmentos detectados")
            seg_data = [
                {
                    "Segmento": s.get("nombre", ""),
                    "Inicio": s.get("timestamp_inicio", ""),
                    "Fin": s.get("timestamp_fin", ""),
                    "Descripcion": s.get("descripcion", ""),
                }
                for s in segments
            ]
            st.table(seg_data)

        elements = analysis.get("elementos_que_funcionan", [])
        if elements:
            st.subheader("Elementos que funcionan")
            for elem in elements:
                st.markdown(f"- {elem}")

        if result.get("transcription"):
            with st.expander("Transcripcion completa"):
                st.text(result["transcription"])

        st.divider()
        st.subheader("Briefs generados")

        tabs = st.tabs([b.get("formato_destino", f"Brief {i+1}") for i, b in enumerate(briefs)])
        for tab, brief in zip(tabs, briefs):
            with tab:
                st.caption(f"Formato origen: {brief.get('formato_origen', '')}")
                st.markdown(brief.get("content", ""))

        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("Exportar a Google Docs"):
                with st.spinner("Creating Google Doc..."):
                    doc_url = export_to_google_docs(result)
                st.success(f"Document created: {doc_url}")

        with col_b:
            if st.button("Guardar en base de datos"):
                with st.spinner("Saving to database..."):
                    save_to_database(result)
                st.success("Saved to database.")

elif st.session_state.get("authentication_status") is False:
    st.error("Usuario o contrasena incorrectos")
else:
    st.info("Introduce tus credenciales para acceder")

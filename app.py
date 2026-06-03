import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import streamlit_authenticator as stauth
from src.pipeline import analyze_video, export_to_google_docs, save_to_database

st.set_page_config(
    page_title="Hair Biolabs — Creative Brief Generator",
    page_icon="\U0001f487",
    layout="wide",
)

credentials = dict(st.secrets.get("credentials", {"usernames": {}}))
if "usernames" in credentials:
    credentials["usernames"] = {
        k: dict(v) for k, v in credentials["usernames"].items()
    }

authenticator = stauth.Authenticate(
    credentials={"credentials": credentials},
    cookie_name="hb_brief_auth",
    cookie_key=st.secrets.get("auth", {}).get("cookie_key", "dev_fallback_key_change_me"),
    cookie_expiry_days=30,
)

authenticator.login(location="main")

if st.session_state.get("authentication_status"):
    authenticator.logout("Cerrar sesion", location="sidebar")
    st.sidebar.write(f"Hola, **{st.session_state.get('name', '')}**")

    st.title("Hair Biolabs — Creative Brief Generator")
    st.markdown("Paste a video URL to analyze the creative format and generate briefs for the 4 alternate formats.")

    video_url = st.text_input("Video URL", placeholder="https://example.com/video.mp4")

    if st.button("Analizar", type="primary", disabled=not video_url):
        progress = st.status("Analyzing video...", expanded=True)

        def on_progress(step: str, detail: str):
            labels = {
                "download": "⬇️ Downloading and processing video...",
                "classify": "\U0001f50d Classifying creative format...",
                "briefs": "✍️ Generating briefs for 4 alternate formats...",
                "done": "✅ Analysis complete!",
            }
            progress.update(label=labels.get(step, detail))
            progress.write(detail)

        result = analyze_video(video_url, on_progress=on_progress)
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

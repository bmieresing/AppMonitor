import streamlit as st

st.set_page_config(layout="wide", page_title="App Monitor")

# Verificar autenticación (solo activo en Streamlit Community Cloud)
user_info = st.user
if user_info.email is not None:
    allowed = st.secrets.get("auth", {}).get("allowed_emails", [])
    if user_info.email not in allowed:
        st.error("Acceso no autorizado.")
        st.stop()

# Contenido placeholder
st.title("App Monitor")
if user_info.email:
    st.success(f"Bienvenido, {user_info.email}")
st.info("Datos próximamente.")

import streamlit as st

st.set_page_config(layout="wide", page_title="App Monitor")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("App Monitor")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if pwd == st.secrets["app_password"]:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()

st.title("App Monitor")
st.info("Datos próximamente.")

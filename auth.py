import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def login_page():
    st.title("Acesso ao Sistema")

    aba = st.radio("Selecione", ["Entrar", "Criar Conta"], horizontal=True)

    if aba == "Entrar":
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                if res.user:
                    st.session_state["user"] = res.user
                    st.experimental_rerun()
                else:
                    st.error("E-mail ou senha incorretos.")
            except Exception as e:
                st.error(f"Erro no login: {e}")

    else:
        email = st.text_input("E-mail para cadastro")
        senha = st.text_input("Crie uma senha forte", type="password")

        if st.button("Criar Conta"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": senha})
                st.success("Conta criada. Verifique seu e-mail para confirmar o cadastro.")
            except Exception as e:
                st.error(f"Erro ao criar conta: {e}")

def logout():
    st.session_state.clear()
    st.experimental_rerun()

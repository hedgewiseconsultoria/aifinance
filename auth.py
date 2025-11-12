import streamlit as st
from supabase import create_client
import os

# -----------------------------
# CONFIGURAÇÕES INICIAIS
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# LOGIN E CADASTRO
# -----------------------------
def login_page():
    # Layout centralizado
    st.markdown(
        """
        <style>
        .centered-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding-top: 40px;
        }
        .app-logo {
            width: 110px;
            margin-bottom: 10px;
        }
        .app-title {
            width: 200px;
            margin-bottom: 30px;
        }
        .auth-box {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 30px 40px;
            width: 400px;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.05);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Container principal
    st.markdown('<div class="centered-container">', unsafe_allow_html=True)

    # Exibe as imagens (certifique-se que os arquivos estão na pasta do app ou na pasta 'assets')
    st.image("logo_hedgewise.png", use_column_width=False, width=110)
    st.image("FinanceAI_1.png", use_column_width=False, width=200)

    st.markdown('<div class="auth-box">', unsafe_allow_html=True)
    st.subheader("Acesso ao Sistema")

    aba = st.radio("Selecione", ["Entrar", "Criar Conta"], horizontal=True)

    # --- LOGIN EXISTENTE ---
    if aba == "Entrar":
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                if res.user:
                    st.session_state["user"] = res.user
                    st.experimental_rerun()
                else:
                    st.error("E-mail ou senha incorretos.")
            except Exception:
                st.error("Erro ao autenticar. Verifique as credenciais.")

    # --- CADASTRO NOVO ---
    else:
        email = st.text_input("E-mail para cadastro")
        senha = st.text_input("Crie uma senha forte", type="password")

        if st.button("Criar Conta", use_container_width=True):
            try:
                res = supabase.auth.sign_up({"email": email, "password": senha})
                st.success("Conta criada. Verifique seu e-mail para confirmar o cadastro.")
            except Exception as e:
                st.error(f"Erro ao criar conta: {e}")

    st.markdown("</div></div>", unsafe_allow_html=True)


# -----------------------------
# LOGOUT
# -----------------------------
def logout():
    st.session_state.clear()
    st.experimental_rerun()

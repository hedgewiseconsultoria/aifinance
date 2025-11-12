import streamlit as st
from supabase import create_client
from PIL import Image

# -----------------------------
# 1. CONFIGURAÇÃO SUPABASE
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Caminho da imagem do nome do app
LOGO1_FILENAME = "FinanceAI_1.png"


# -----------------------------
# 2. FUNÇÃO DE CABEÇALHO
# -----------------------------
def load_header():
    """Renderiza o cabeçalho padrão do app."""
    try:
        logo = Image.open(LOGO1_FILENAME)
        col1, col2 = st.columns([2, 5])
        with col1:
            st.image(logo, width=600)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("Traduzindo números em histórias que façam sentido...")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")


# -----------------------------
# 3. PÁGINA DE LOGIN / CADASTRO
# -----------------------------
def login_page():
    """Renderiza a tela de autenticação com Supabase Auth."""
    load_header()

    # Caixa central de autenticação
    st.markdown(
        """
        <style>
        .auth-box {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 10px;
            padding: 30px 40px;
            width: 420px;
            margin: 0 auto;
            box-shadow: 0px 4px 12px rgba(0,0,0,0.05);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="auth-box">', unsafe_allow_html=True)
    st.subheader("Acesso ao Sistema")

    aba = st.radio("Selecione", ["Entrar", "Criar Conta"], horizontal=True)

    # --- Login Existente ---
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

    # --- Criação de Conta ---
    else:
        email = st.text_input("E-mail para cadastro")
        senha = st.text_input("Crie uma senha forte", type="password")

        if st.button("Criar Conta", use_container_width=True):
            try:
                res = supabase.auth.sign_up({"email": email, "password": senha})
                st.success("Conta criada. Verifique seu e-mail para confirmar o cadastro.")
            except Exception as e:
                st.error(f"Erro ao criar conta: {e}")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 4. LOGOUT
# -----------------------------
def logout():
    """Finaliza a sessão do usuário."""
    st.session_state.clear()
    st.experimental_rerun()

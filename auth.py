import streamlit as st
from supabase import create_client
from PIL import Image

# -----------------------------
# 1. CONFIGURAÇÃO SUPABASE
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
LOGO1_FILENAME = "FinanceAI_1.png"


# -----------------------------
# 2. FUNÇÃO DE CABEÇALHO
# -----------------------------
def load_header(show_user: bool = True):
    try:
        logo = Image.open(LOGO1_FILENAME)
        col1, col2 = st.columns([2, 5])
        with col1:
            st.image(logo, width=600)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("Traduzindo números em histórias que façam sentido...")

            if show_user and "user" in st.session_state:
                user = st.session_state["user"]
                user_email = getattr(user, "email", None) or user.get("email")
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(f"👤 **{user_email}**")
                with col_b:
                    if st.button("Sair", use_container_width=True):
                        logout()
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")


# -----------------------------
# 3. PÁGINA DE LOGIN / CADASTRO / RECUPERAÇÃO
# -----------------------------
def login_page():
    load_header(show_user=False)

    # --- Corrige URLs com fragmento (#access_token)
    st.markdown(
        """
        <script>
        const hash = window.location.hash;
        if (hash && hash.includes("access_token")) {
            const newUrl = window.location.href.replace("#", "?");
            window.location.replace(newUrl);
        }
        </script>
        """,
        unsafe_allow_html=True
    )

    # --- Detecta parâmetros da URL
    params = st.query_params
    access_token = None
    tipo = None

    if "access_token" in params:
        access_token = params["access_token"][0] if isinstance(params["access_token"], list) else params["access_token"]
    if "type" in params:
        tipo = params["type"][0] if isinstance(params["type"], list) else params["type"]

    # --- Se veio de link de recuperação ---
    if access_token and tipo == "recovery":
        st.subheader("Redefinindo senha...")
        try:
            nova_senha = st.session_state.get("pending_password")
            if not nova_senha:
                st.warning("Sessão expirada. Por favor, volte à tela de recuperação e repita o processo.")
                return
            supabase.auth.update_user({"password": nova_senha}, access_token=access_token)
            st.success("✅ Senha redefinida com sucesso! Você já pode entrar novamente.")
            st.session_state.clear()
            return
        except Exception as e:
            st.error(f"Erro ao redefinir senha: {e}")
            return

    # --- Estilos personalizados ---
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1rem; }
        div[data-testid="stRadio"] > div { justify-content: center; }
        input[type="email"], input[type="password"], input[type="text"] {
            border: 1px solid #0A2342 !important;
            border-radius: 6px !important;
            padding: 8px 10px !important;
        }
        input:focus {
            border-color: #007BFF !important;
            box-shadow: 0 0 4px #007BFF !important;
        }
        button[kind="primary"] {
            background-color: #0A2342 !important;
            color: white !important;
            border-radius: 6px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # --- Tela principal ---
    st.subheader("Acesso ao Sistema")
    aba = st.radio("Selecione", ["Entrar", "Criar Conta", "Esqueci a Senha"], horizontal=True)

    # --- LOGIN ---
    if aba == "Entrar":
        email = st.text_input("E-mail", key="email_login")
        senha = st.text_input("Senha", type="password", key="senha_login")
        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Entrar", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                    if res.user:
                        st.session_state["user"] = supabase.auth.get_user().user
                        _safe_rerun()
                    else:
                        st.error("E-mail ou senha incorretos.")
                except Exception as e:
                    st.error(f"Erro ao autenticar: {e}")

    # --- CRIAR CONTA ---
    elif aba == "Criar Conta":
        email = st.text_input("E-mail para cadastro", key="email_signup")
        senha = st.text_input("Crie uma senha forte", type="password", key="senha_signup")
        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Criar Conta", use_container_width=True):
                try:
                    supabase.auth.sign_up({"email": email, "password": senha})
                    st.success("Conta criada! Verifique seu e-mail para confirmar o cadastro.")
                except Exception as e:
                    st.error(f"Erro ao criar conta: {e}")

    # --- RECUPERAÇÃO DE SENHA ---
    else:
        email = st.text_input("Digite seu e-mail cadastrado", key="email_recovery")
        nova_senha = st.text_input("Crie uma nova senha forte", type="password", key="nova_senha_recovery")
        confirmar = st.text_input("Confirme a nova senha", type="password", key="confirmar_recovery")

        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Enviar redefinição", use_container_width=True):
                if not email:
                    st.error("Informe seu e-mail cadastrado.")
                    return
                if not nova_senha or not confirmar:
                    st.error("Informe e confirme a nova senha.")
                    return
                if nova_senha != confirmar:
                    st.error("As senhas não coincidem.")
                    return
                st.session_state["pending_password"] = nova_senha
                try:
                    redirect_to = "https://inteligenciafinanceira.streamlit.app"
                    supabase.auth.reset_password_for_email(email, options={"redirect_to": redirect_to})
                    st.success("✅ Um e-mail foi enviado! Clique no botão de confirmação para ativar a nova senha.")
                except Exception as e:
                    st.error(f"Erro ao enviar e-mail: {e}")


# -----------------------------
# 4. LOGOUT
# -----------------------------
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    _safe_rerun()


# -----------------------------
# 5. RERUN COMPATÍVEL
# -----------------------------
def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

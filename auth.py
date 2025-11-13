import streamlit as st
from supabase import create_client
from PIL import Image
from urllib.parse import parse_qs, urlparse

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
    """Renderiza o cabeçalho padrão do app."""
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
    """Renderiza a tela de autenticação com Supabase Auth."""
    load_header(show_user=False)

    # --- Detecta se o link contém parâmetros de recuperação ---
    query_params = st.query_params
    if "type" in query_params and query_params["type"] == "recovery":
        st.session_state["reset_mode"] = True
        st.session_state["access_token"] = query_params.get("access_token")

    # --- Estilos personalizados ---
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
        }
        div[data-testid="stRadio"] > div {
            justify-content: center;
        }
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

    # 🔹 Se o usuário acessou via link de redefinição
    if st.session_state.get("reset_mode", False):
        st.subheader("Redefinir Senha")
        nova_senha = st.text_input("Digite a nova senha", type="password", key="nova_senha")
        confirmar = st.text_input("Confirme a nova senha", type="password", key="confirmar_senha")

        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Atualizar Senha", use_container_width=True):
                if nova_senha != confirmar:
                    st.error("As senhas não coincidem.")
                elif len(nova_senha) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres.")
                else:
                    try:
                        token = st.session_state.get("access_token")
                        if not token:
                            st.error("Token de redefinição inválido ou expirado.")
                            return

                        # Atualiza a senha usando o token temporário
                        supabase.auth.update_user({"password": nova_senha}, access_token=token)

                        st.success("Senha atualizada com sucesso! Você já pode entrar novamente.")
                        st.session_state["reset_mode"] = False
                        st.session_state.pop("access_token", None)
                    except Exception as e:
                        st.error(f"Erro ao redefinir senha: {e}")
        return  # Evita exibir as abas normais

    # 🔹 Exibe as abas normais
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
                        user_data = supabase.auth.get_user()
                        if user_data and user_data.user:
                            st.session_state["user"] = user_data.user

                            try:
                                supabase.table("users_profiles").upsert({
                                    "id": str(user_data.user.id),
                                    "plano": "free"
                                }).execute()
                            except Exception as e:
                                if st.secrets.get("DEBUG", False):
                                    st.warning(f"Falha ao criar/atualizar perfil do usuário: {e}")

                            _safe_rerun()
                        else:
                            st.error("Erro ao recuperar dados do usuário autenticado.")
                    else:
                        st.error("E-mail ou senha incorretos.")
                except Exception:
                    st.error("Erro ao autenticar. Verifique as credenciais.")

    # --- CRIAÇÃO DE CONTA ---
    elif aba == "Criar Conta":
        email = st.text_input("E-mail para cadastro", key="email_signup")
        senha = st.text_input("Crie uma senha forte", type="password", key="senha_signup")

        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Criar Conta", use_container_width=True):
                try:
                    res = supabase.auth.sign_up({"email": email, "password": senha})
                    st.success("Conta criada! Verifique seu e-mail para confirmar o cadastro.")
                except Exception as e:
                    st.error(f"Erro ao criar conta: {e}")

    # --- RECUPERAÇÃO DE SENHA ---
    else:
        email = st.text_input("Digite seu e-mail cadastrado", key="email_recovery")
        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Enviar link de redefinição", use_container_width=True):
                try:
                    supabase.auth.reset_password_for_email(email)
                    st.success("Um link de redefinição foi enviado para seu e-mail.")
                except Exception:
                    st.error("Erro ao enviar link. Verifique o e-mail informado.")


# -----------------------------
# 4. LOGOUT
# -----------------------------
def logout():
    """Finaliza a sessão do usuário."""
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    _safe_rerun()


# -----------------------------
# 5. FUNÇÃO DE RERUN COMPATÍVEL
# -----------------------------
def _safe_rerun():
    """Executa rerun compatível com diferentes versões do Streamlit."""
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

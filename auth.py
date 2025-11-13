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

    # --- Injeta script para capturar parâmetros do fragmento da URL (#)
    st.markdown(
        """
        <script>
        const params = new URLSearchParams(window.location.hash.substring(1));
        if (params.get("type") === "recovery") {
            sessionStorage.setItem("reset_mode", "true");
            window.location.hash = "";  // limpa o hash da URL
            window.location.reload();   // recarrega a página já no modo reset
        }
        </script>
        """,
        unsafe_allow_html=True,
    )

    # --- Ativa modo de redefinição se foi detectado o parâmetro ---
    if session_storage_reset_mode():
        st.session_state["reset_mode"] = True

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
        unsafe_allow_html=True,
    )

    # 🔹 Se o usuário acessou via link de redefinição
    if st.session_state.get("reset_mode", False):
        st.subheader("🔐 Redefinir Senha")
        st.info("Você acessou através do link de redefinição de senha enviado por e-mail.")
        nova_senha = st.text_input("Digite a nova senha", type="password", key="nova_senha")
        confirmar = st.text_input("Confirme a nova senha", type="password", key="confirmar_senha")

        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Atualizar Senha", use_container_width=True):
                if nova_senha == confirmar:
                    try:
                        supabase.auth.update_user({"password": nova_senha})
                        st.success("✅ Senha atualizada com sucesso! Você já pode entrar novamente.")
                        st.session_state["reset_mode"] = False
                        clear_session_storage_reset_flag()
                    except Exception as e:
                        st.error(f"Erro ao redefinir senha: {e}")
                else:
                    st.error("As senhas não coincidem.")
        return

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
                                    st.warning(f"Falha ao criar/atualizar perfil: {e}")
                            _safe_rerun()
                        else:
                            st.error("Erro ao recuperar dados do usuário.")
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
# 5. FUNÇÃO AUXILIAR PARA SESSIONSTORAGE (browser)
# -----------------------------
def session_storage_reset_mode():
    """Verifica se o modo de redefinição foi armazenado no sessionStorage via JS."""
    try:
        val = st.session_state.get("_js_reset_mode", None)
        return val == "true"
    except Exception:
        return False


def clear_session_storage_reset_flag():
    """Remove o indicador de reset_mode do sessionStorage no navegador."""
    st.markdown(
        """
        <script>
        sessionStorage.removeItem("reset_mode");
        </script>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# 6. FUNÇÃO DE RERUN COMPATÍVEL
# -----------------------------
def _safe_rerun():
    """Executa rerun compatível com diferentes versões do Streamlit."""
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

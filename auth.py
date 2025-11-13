import streamlit as st
from supabase import create_client
from PIL import Image
from datetime import datetime, timedelta
import uuid
from cryptography.fernet import Fernet

# -----------------------------
# 1. CONFIGURAÇÃO SUPABASE
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
FERNET_KEY = st.secrets["FERNET_KEY"]
SITE_URL = st.secrets["SITE_URL"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(FERNET_KEY)
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

    # --- Detecta se o link contém reset_token ---
    query_params = st.query_params
    if "reset_token" in query_params:
        reset_token = query_params["reset_token"][0]
        handle_password_reset(reset_token)
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

    # --- Tela padrão ---
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
        nova_senha = st.text_input("Crie uma nova senha forte", type="password", key="senha_recovery")
        confirmar = st.text_input("Confirme a nova senha", type="password", key="confirmar_recovery")

        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Enviar redefinição", use_container_width=True):
                if not email or not nova_senha or not confirmar:
                    st.warning("Preencha todos os campos.")
                elif nova_senha != confirmar:
                    st.error("As senhas não coincidem.")
                else:
                    try:
                        encrypted = cipher.encrypt(nova_senha.encode()).decode()
                        token = str(uuid.uuid4())
                        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
                        supabase.table("password_resets").insert({
                            "email": email,
                            "reset_token": token,
                            "encrypted_password": encrypted,
                            "expires_at": expires_at
                        }).execute()

                        redirect_url = f"{SITE_URL}?reset_token={token}"
                        supabase.auth.reset_password_for_email(email, options={"redirect_to": redirect_url})
                        st.success("Um e-mail foi enviado. Clique no botão 'Confirmar Redefinição' para concluir a troca da senha.")
                    except Exception as e:
                        st.error(f"Erro ao enviar redefinição: {e}")


# -----------------------------
# 4. FUNÇÃO DE PROCESSAMENTO DO RESET
# -----------------------------
def handle_password_reset(reset_token: str):
    """Processa a redefinição de senha após o clique no e-mail."""
    st.subheader("Redefinição de Senha")

    try:
        result = supabase.table("password_resets").select("*").eq("reset_token", reset_token).execute()
        if not result.data or len(result.data) == 0:
            st.error("Link inválido ou expirado.")
            return

        reset_data = result.data[0]
        expires_at = datetime.fromisoformat(reset_data["expires_at"].replace("Z", "+00:00"))
        if datetime.utcnow() > expires_at:
            st.error("Este link expirou. Solicite uma nova redefinição.")
            supabase.table("password_resets").delete().eq("reset_token", reset_token).execute()
            return

        nova_senha = cipher.decrypt(reset_data["encrypted_password"].encode()).decode()
        email = reset_data["email"]

        # 🔹 Atualiza a senha no Supabase
        res = supabase.auth.sign_in_with_password({"email": email, "password": nova_senha})
        if res.user:
            supabase.auth.update_user({"password": nova_senha})
            supabase.table("password_resets").delete().eq("reset_token", reset_token).execute()
            st.success("✅ Senha redefinida com sucesso! Você já pode entrar novamente.")
        else:
            st.warning("Clique novamente no botão do e-mail para confirmar a redefinição.")
    except Exception as e:
        st.error(f"Erro ao processar redefinição: {e}")


# -----------------------------
# 5. LOGOUT
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
# 6. FUNÇÃO DE RERUN COMPATÍVEL
# -----------------------------
def _safe_rerun():
    """Executa rerun compatível com diferentes versões do Streamlit."""
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

import streamlit as st
from supabase import create_client
from PIL import Image
import uuid
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

# -----------------------------
# 1. CONFIGURAÇÕES INICIAIS
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
FERNET_KEY = st.secrets["FERNET_KEY"]
SITE_URL = st.secrets["SITE_URL"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
fernet = Fernet(FERNET_KEY.encode())
LOGO1_FILENAME = "FinanceAI_1.png"


# -----------------------------
# 2. FUNÇÕES DE SEGURANÇA
# -----------------------------
def encrypt_password(password: str) -> str:
    """Criptografa senha temporária."""
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Descriptografa senha armazenada."""
    return fernet.decrypt(encrypted.encode()).decode()


def store_temp_password(email: str, password: str, validity_minutes=20):
    """Salva senha criptografada na tabela temporária."""
    token = str(uuid.uuid4())
    encrypted = encrypt_password(password)
    expires_at = (datetime.utcnow() + timedelta(minutes=validity_minutes)).isoformat() + "Z"
    supabase.table("password_resets").insert({
        "email": email,
        "reset_token": token,
        "encrypted_password": encrypted,
        "expires_at": expires_at
    }).execute()
    return token


def fetch_temp_password(reset_token: str):
    """Busca e remove senha pendente (caso ainda válida)."""
    res = supabase.table("password_resets").select("*").eq("reset_token", reset_token).execute()
    rows = res.data if hasattr(res, "data") else res
    if not rows:
        return None
    row = rows[0]
    # Confere validade
    if datetime.fromisoformat(row["expires_at"].replace("Z", "")) < datetime.utcnow():
        supabase.table("password_resets").delete().eq("reset_token", reset_token).execute()
        return None
    supabase.table("password_resets").delete().eq("reset_token", reset_token).execute()
    return row


# -----------------------------
# 3. CABEÇALHO PADRÃO
# -----------------------------
def load_header(show_user: bool = True):
    """Renderiza o cabeçalho do app."""
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
                email = getattr(user, "email", None) or user.get("email")
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(f"👤 **{email}**")
                with col_b:
                    if st.button("Sair", use_container_width=True):
                        logout()
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")


# -----------------------------
# 4. LOGIN / CADASTRO / RECUPERAÇÃO
# -----------------------------
def login_page():
    load_header(show_user=False)

    # Corrige URL fragmento (#access_token)
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

    params = st.query_params
    access_token = params.get("access_token", [None])[0] if isinstance(params.get("access_token"), list) else params.get("access_token")
    tipo = params.get("type", [None])[0] if isinstance(params.get("type"), list) else params.get("type")
    reset_token = params.get("reset_token", [None])[0] if isinstance(params.get("reset_token"), list) else params.get("reset_token")

    # --- Caso o usuário tenha clicado no link do e-mail ---
    if access_token and (tipo == "recovery" or tipo is None) and reset_token:
        st.subheader("Redefinindo senha...")
        try:
            row = fetch_temp_password(reset_token)
            if not row:
                st.error("Token expirado ou inválido. Repita o processo de redefinição.")
                return
            decrypted = decrypt_password(row["encrypted_password"])
            supabase.auth.update_user({"password": decrypted}, access_token=access_token)
            st.success("✅ Senha redefinida com sucesso! Você já pode entrar novamente.")
            return
        except Exception as e:
            st.error(f"Erro ao redefinir senha: {e}")
            return

    # --- Estilos ---
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

    # --- CADASTRO ---
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
                try:
                    token = store_temp_password(email, nova_senha)
                    redirect_to = f"{SITE_URL}?reset_token={token}"
                    supabase.auth.reset_password_for_email(email, options={"redirect_to": redirect_to})
                    st.success("✅ Um e-mail foi enviado! Clique no botão de confirmação para ativar a nova senha.")
                except Exception as e:
                    st.error(f"Erro ao enviar e-mail: {e}")


# -----------------------------
# 5. LOGOUT E RERUN
# -----------------------------
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    _safe_rerun()


def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

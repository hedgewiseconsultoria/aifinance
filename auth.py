import streamlit as st
from supabase import create_client
from PIL import Image
from datetime import datetime, timedelta
import uuid
import re
from cryptography.fernet import Fernet

# -----------------------------
# 1. CONFIGURAÇÃO SUPABASE
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
FERNET_KEY = st.secrets.get("FERNET_KEY", Fernet.generate_key().decode())
SITE_URL = st.secrets["SITE_URL"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)
LOGO1_FILENAME = "FinanceAI_1.png"


# -----------------------------
# Helpers
# -----------------------------

def format_cnpj(raw: str) -> str:
    """Remove tudo que nao for digito e formata no padrao 00.000.000/0000-00
    Retorna a string formatada ou a string original se nao houver 14 digitos."""
    digits = re.sub(r"\D", "", (raw or ""))
    if len(digits) != 14:
        return raw
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


# -----------------------------
# 2. FUNÇÃO DE CABEÇALHO
# -----------------------------
def load_header(show_user: bool = True):
    """Renderiza o cabeçalho padrão do app."""
    try:
        logo = Image.open(LOGO1_FILENAME)
        col1, col2 = st.columns([1, 5])
        with col1:
            st.image(logo, width=600)
        with col2:
            st.markdown('<div class="main-header" style="margin-top: 0.2em;">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
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

    # --------------------------
    # CONVERSÃO DO # -> ? (TOKEN)
    # --------------------------
    st.markdown(
        """
        <script>
        (function() {
            const hash = window.location.hash;
            if (hash && hash.includes("access_token")) {
                const newUrl = window.location.href.replace("#", "?");
                window.location.replace(newUrl);
            }
        })();
        </script>
        """,
        unsafe_allow_html=True
    )

    # ---------------------------------------
    # Estilos personalizados
    # ---------------------------------------
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

    # -----------------------------
    # GUI normal
    # -----------------------------
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
                    res = supabase.auth.sign_in_with_password(
                        {"email": email, "password": senha}
                    )
                    if res and getattr(res, 'user', None) or (isinstance(res, dict) and res.get('user')):
                        # obter user por método confiável
                        user_data = supabase.auth.get_user()
                        if user_data and getattr(user_data, 'user', None):
                            st.session_state["user"] = user_data.user
                            try:
                                # Garantir que exista um registro em users_profiles
                                supabase.table("users_profiles").upsert({
                                    "id": str(user_data.user.id),
                                    "plano": "free"
                                }).execute()
                            except Exception:
                                pass
                            _safe_rerun()
                        else:
                            st.error("Erro ao recuperar dados do usuário autenticado.")
                    else:
                        st.error("E-mail ou senha incorretos.")
                except Exception:
                    st.error("Erro ao autenticar. Verifique as credenciais.")

    # --- CRIAR CONTA ---
    elif aba == "Criar Conta":
        st.info("Preencha os dados abaixo. O plano padrão é 'free'.")
        email = st.text_input("E-mail para cadastro", key="email_signup")
        senha = st.text_input("Crie uma senha forte", type="password", key="senha_signup")
        nome = st.text_input("Nome completo", key="nome_signup")
        empresa = st.text_input("Empresa", key="empresa_signup")
        cnpj_raw = st.text_input("CNPJ (apenas números ou já formatado)", key="cnpj_signup")
        socios = st.text_input("Sócios (nome1, nome2...)", key="socios_signup")
        plano = st.radio("Plano", ["free", "premium"], index=0, horizontal=True)

        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Criar Conta", use_container_width=True):
                # validações simples
                if not email or not senha or not nome:
                    st.warning("Preencha ao menos e-mail, senha e nome.")
                else:
                    # formatar/validar cnpj
                    cnpj_digits = re.sub(r"\D", "", cnpj_raw or "")
                    if cnpj_raw and len(cnpj_digits) != 14:
                        st.error("CNPJ inválido. Deve conter 14 dígitos (somente números).")
                    else:
                        cnpj_formatted = format_cnpj(cnpj_raw) if cnpj_raw else None
                        try:
                            res = supabase.auth.sign_up({"email": email, "password": senha})
                            # res pode conter user.id dependendo da versão do client
                            user_id = None
                            if getattr(res, 'user', None):
                                user_id = str(res.user.id)
                            elif isinstance(res, dict) and res.get('user'):
                                user_id = str(res['user'].get('id'))

                            # Se não veio user_id (algumas vezes requer confirmação), geramos um id temporário
                            if not user_id:
                                user_id = str(uuid.uuid4())

                            # Inserir/atualizar perfil no supabase
                            profile = {
                                "id": user_id,
                                "nome": nome,
                                "empresa": empresa,
                                "cnpj": cnpj_formatted,
                                "socios": socios,
                                "plano": plano
                            }
                            try:
                                supabase.table("users_profiles").upsert(profile).execute()
                            except Exception as e:
                                st.warning(f"Conta criada, mas houve problema ao inserir o perfil: {e}")

                            st.success("Conta criada! Verifique seu e-mail para confirmar o cadastro.")
                        except Exception as e:
                            st.error(f"Erro ao criar conta: {e}")

    # --- ESQUECI A SENHA ---
    else:
        st.info("Digite o e-mail cadastrado. Você receberá um link para redefinir a senha (fluxo padrão do Supabase).")
        email = st.text_input("Digite seu e-mail cadastrado", key="email_recovery")

        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            if st.button("Enviar redefinição", use_container_width=True):
                if not email:
                    st.warning("Informe o e-mail cadastrado.")
                else:
                    try:
                        # Usar o fluxo padrão do Supabase para redefinição de senha.
                        # Não armazenamos a nova senha localmente — o Supabase cuidará do processo.
                        supabase.auth.reset_password_for_email(email)
                        st.success("Um e-mail foi enviado com instruções para redefinir sua senha.")
                        st.caption("Se você configurou um redirect customizado no Supabase Auth, verifique se o domínio do SITE_URL está listado nas URLs de redirecionamento.")
                    except Exception as e:
                        st.error(f"Erro ao enviar redefinição: {e}")


# -------------------------------------
# 4. PROCESSAMENTO DO RESET DE SENHA (LEGADO - PODE SER REMOVIDO)
# -------------------------------------
# Mantive a função caso você ainda queira controlar o fluxo manualmente. Note que,
# com o fluxo padrão do Supabase (`reset_password_for_email`) não é necessário usá-la.

def handle_password_reset(reset_token: str, access_token: str):
    st.subheader("Redefinição de Senha")

    try:
        result = supabase.table("password_resets").select("*").eq("reset_token", reset_token).execute()
        rows = result.data if hasattr(result, "data") else result

        if not rows:
            st.error("Link inválido ou expirado.")
            return

        reset_data = rows[0]

        expires_at = reset_data.get("expires_at")
        if expires_at:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.utcnow() > expires_dt:
                st.error("Este link expirou. Solicite uma nova redefinição.")
                supabase.table("password_resets").delete().eq("reset_token", reset_token).execute()
                return

        encrypted = reset_data.get("encrypted_password")
        if not encrypted:
            st.error("Não há nova senha armazenada para este link.")
            return

        nova_senha = cipher.decrypt(encrypted.encode()).decode()

        # Atualizar senha com access_token (se fornecido pelo Supabase no link)
        if access_token:
            supabase.auth.update_user({"password": nova_senha}, access_token=access_token)
            supabase.table("password_resets").delete().eq("reset_token", reset_token).execute()
            st.success("✅ Senha redefinida com sucesso! Você já pode entrar.")
        else:
            st.error("Access token ausente no link. Utilize o fluxo padrão de redefinição do Supabase ou verifique as configurações de redirect.")

    except Exception as e:
        st.error(f"Erro ao processar redefinição: {e}")


# -----------------------------
# 5. LOGOUT
# -----------------------------
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    _safe_rerun()


# -----------------------------
# 6. RERUN (reusado)
# -----------------------------
# _safe_rerun já definido acima


# -----------------------------
# 7. MAIN
# -----------------------------
if __name__ == "__main__":
    login_page()

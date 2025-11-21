import streamlit as st
from supabase import create_client
from PIL import Image
import re
import uuid
from datetime import datetime

# -----------------------------
# CONFIG
# -----------------------------
SITE_URL = "https://inteligenciafinanceira.streamlit.app"  # provided by user
RESET_ROUTE = "/reset-password"
RESET_REDIRECT = SITE_URL + RESET_ROUTE

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
LOGO_URL = "https://raw.githubusercontent.com/hedgewiseconsultoria/aifinance/f620b7be17cfb9b40f12c96c5bbeec46fad85ad4/FinanceAI_1.png"

# -----------------------------
# Helpers
# -----------------------------

def format_cnpj(raw: str) -> str:
    digits = re.sub(r"\D", "", (raw or ""))
    if len(digits) != 14:
        return raw
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


# Small JS helper to convert hash fragment to query string so Streamlit can read tokens
def inject_hash_to_query_js():
    js = """
    <script>
    (function(){
      try{
        const hash = window.location.hash;
        if (hash && hash.includes('access_token')) {
          const newUrl = window.location.href.replace('#', '?');
          window.history.replaceState(null, '', newUrl);
        }
      }catch(e){console.log(e)}
    })();
    </script>
    """
    st.components.v1.html(js)


# -----------------------------
# Header
# -----------------------------

def load_header(show_user: bool = True):
    """Renderiza o cabeçalho padrão do app."""
    try:
        logo = Image.open(LOGO_URL)
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
    except Exception:
        st.title("Análise Financeira Inteligente")
        st.markdown("---")


# -----------------------------
# Signup / Login / Recovery UI
# -----------------------------

def login_page():
    load_header(show_user=False)

    # Restore previous styled input boxes
    st.markdown(
        """
        <style>
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

    st.subheader("Acesso ao sistema")
    aba = st.radio("", ["Entrar", "Criar Conta", "Esqueci a Senha"], index=0, horizontal=True)

    if aba == "Entrar":
        email = st.text_input("E-mail", key="email_login")
        senha = st.text_input("Senha", type="password", key="senha_login")
        if st.button("Entrar"):
            if not email or not senha:
                st.warning("Informe e-mail e senha")
            else:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                    # supabase client returns dict-like or object depending on version
                    user = None
                    if isinstance(res, dict):
                        user = res.get('user')
                    else:
                        user = getattr(res, 'user', None)
                    if user:
                        st.session_state['user'] = user
                        # ensure profile exists
                        try:
                            supabase.table('users_profiles').upsert({'id': str(user.get('id') if isinstance(user, dict) else user.id), 'plano': 'free'}).execute()
                        except Exception:
                            pass
                        st.success("Login efetuado")
                        _safe_rerun()
                    else:
                        st.error("E-mail ou senha incorretos")
                except Exception as e:
                    st.error(f"Erro ao autenticar: {e}")

    elif aba == "Criar Conta":
        st.info("Preencha os dados para criar sua conta. O plano padrão é 'free'.")
        email = st.text_input("E-mail para cadastro", key="email_signup")
        senha = st.text_input("Crie uma senha forte", type="password", key="senha_signup")
        nome = st.text_input("Nome completo", key="nome_signup")
        empresa = st.text_input("Empresa", key="empresa_signup")
        cnpj_raw = st.text_input("CNPJ (apenas números ou já formatado)", key="cnpj_signup")
        socios = st.text_input("Sócios (separados por vírgula)", key="socios_signup")
        plano = st.radio("Plano", ["free", "premium"], index=0, horizontal=True)

        # mostra preview formatado do cnpj
        if cnpj_raw:
            st.caption(f"CNPJ formatado (preview): {format_cnpj(cnpj_raw)}")

        if st.button("Criar Conta"):
            if not email or not senha or not nome:
                st.warning("Preencha ao menos e-mail, senha e nome.")
            else:
                cnpj_digits = re.sub(r"\D", "", cnpj_raw or "")
                if cnpj_raw and len(cnpj_digits) != 14:
                    st.error("CNPJ inválido. Deve conter 14 dígitos (somente números).")
                else:
                    cnpj_formatted = format_cnpj(cnpj_raw) if cnpj_raw else None
                    try:
                        res = supabase.auth.sign_up({"email": email, "password": senha},)
                        user_id = None
                        if isinstance(res, dict):
                            if res.get('user'):
                                user_id = str(res['user'].get('id'))
                        else:
                            user_obj = getattr(res, 'user', None)
                            if user_obj:
                                user_id = str(user_obj.id)

                        if not user_id:
                            # sign_up sometimes requires verification and doesn't return id; generate placeholder
                            user_id = str(uuid.uuid4())

                        profile = {
                            'id': user_id,
                            'nome': nome,
                            'empresa': empresa,
                            'cnpj': cnpj_formatted,
                            'socios': socios,
                            'plano': plano
                        }
                        try:
                            supabase.table('users_profiles').upsert(profile).execute()
                        except Exception as e:
                            st.warning(f"Conta criada, mas não foi possível inserir o perfil: {e}")

                        st.success("Conta criada. Verifique seu e-mail para confirmar (se aplicável).")
                    except Exception as e:
                        st.error(f"Erro ao criar conta: {e}")

    else:  # Esqueci a Senha
        st.info("Digite o e-mail cadastrado para receber o link de redefinição.")
        email = st.text_input("E-mail cadastrado", key="email_recovery")
        if st.button("Enviar redefinição"):
            if not email:
                st.warning("Informe o e-mail.")
            else:
                try:
                    # Recomenda-se configurar o template do Supabase para usar {{ .RedirectTo }}
                    supabase.auth.reset_password_for_email(email)
                    st.success("E-mail enviado. Verifique sua caixa de entrada.")
                    st.caption("IMPORTANTE: configure no Supabase Authentication → URL Configuration o Site URL e Redirect URLs (inclua: " + SITE_URL + ")")
                except Exception as e:
                    st.error(f"Erro ao solicitar redefinição: {e}")


# -----------------------------
# Página de redefinição integrada (rota RESET_ROUTE)
# -----------------------------

def reset_password_page():
    # Forçar conversão de fragment -> query
    inject_hash_to_query_js()

    st.title("Redefinição de senha")
    params = st.experimental_get_query_params()
    # supabase may send 'access_token' or 'token' depending on flow
    access_token = params.get('access_token', [None])[0] or params.get('token', [None])[0]

    if not access_token:
        st.info("Aguardando token de redefinição. Clique no link do e-mail de recuperação para abrir esta página.")
        st.write("Se o link vier com '#access_token=...', o fragment será convertido automaticamente.")
        return

    st.success("Token detectado — continue para redefinir sua senha.")
    nova = st.text_input("Nova senha", type="password", key="nova_pwd")
    nova2 = st.text_input("Repita a nova senha", type="password", key="nova_pwd2")

    if st.button("Redefinir senha"):
        if not nova or nova != nova2:
            st.error("As senhas não coincidem ou estão vazias.")
            return
        try:
            res = supabase.auth.update_user({"password": nova}, access_token=access_token)
            # verificar retorno
            ok = False
            if isinstance(res, dict):
                ok = bool(res.get('user')) or (res.get('status_code') in (200, 201))
            else:
                ok = getattr(res, 'user', None) is not None

            if ok:
                st.success("Senha redefinida com sucesso! Tente entrar com a nova senha.")
            else:
                st.error(f"Falha ao redefinir senha. Resposta do Supabase: {res}")
        except Exception as e:
            st.error(f"Erro ao atualizar senha: {e}")


# -----------------------------
# Logout
# -----------------------------

def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    _safe_rerun()


# -----------------------------
# Router: detect reset route
# -----------------------------

def main():
    params = st.experimental_get_query_params()

    # 1 — Auto-detectar token de recuperação enviado pelo Supabase
    if "access_token" in params or "token" in params or params.get("type", [None])[0] == "recovery":
        reset_password_page()
        return

    # 2 — Compatibilidade com rotas alternativas
    if params.get('reset', [None])[0] == '1' or params.get('page', [None])[0] == 'reset':
        reset_password_page()
        return

    # 3 — Abre login se nada acima foi detectado
    login_page()


if __name__ == '__main__':
    main()

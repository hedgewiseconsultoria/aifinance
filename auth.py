# ============================================================
# auth.py — Fluxo completo de autenticação + reset password
# Revisado e corrigido para uso com Streamlit + Supabase (2025)
# ============================================================

import streamlit as st
from supabase import create_client
from PIL import Image
import re
import uuid

# ==========================
# CONFIGURAÇÕES
# ==========================

SITE_URL = "https://inteligenciafinanceira.streamlit.app"
RESET_URL = "https://hedgewiseconsultoria.github.io/aifinance/redirect.htm"

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
LOGO_URL = "FinanceAI_1.png"


# ==========================
# AUXILIARES
# ==========================

def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def format_cnpj(raw: str) -> str:
    digits = re.sub(r"\D", "", (raw or ""))
    if len(digits) != 14:
        return raw
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def extract_user_field(user, field, default=""):
    """Compatibilidade universal: aceita dict OU objeto User."""
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(field, default)
    return getattr(user, field, default)


# ==========================
# HEADER
# ==========================

def load_header(show_user=True):
    try:
        logo = Image.open(LOGO_URL)
        col1, col2 = st.columns([2, 5])
        with col1:
            st.image(logo, width=600)
        with col2:
            st.markdown(
                '<div style="font-size:28px; font-weight:600; color:#0A2342; margin-top:0.2em;">'
                'Análise Financeira Inteligente</div>',
                unsafe_allow_html=True,
            )
            st.caption("Transformando números em histórias que façam sentido...")

            if show_user and "user" in st.session_state:
                user = st.session_state.get("user")
                email = extract_user_field(user, "email", "")

                colA, colB = st.columns([5, 1])
                with colA:
                    st.markdown(f"👤 **{email}**")
                with colB:
                    if st.button("Sair", use_container_width=True):
                        logout()

        st.markdown("---")

    except Exception:
        st.title("Análise Financeira Inteligente")
        st.markdown("---")


# ==========================
# LOGIN / CADASTRO / RESET
# ==========================

def login_page():
    load_header(show_user=False)

    st.markdown("""
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
    """, unsafe_allow_html=True)

    st.subheader("Acesso ao sistema")
    aba = st.radio("", ["Entrar", "Criar Conta", "Esqueci a Senha"], horizontal=True)

    # --------------------------
    # LOGIN
    # --------------------------
    if aba == "Entrar":
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            if not email or not senha:
                st.warning("Informe e-mail e senha.")
                return

            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": senha
                })

                user = res.user

                if user is None:
                    st.error("E-mail ou senha incorretos.")
                    return

                st.session_state["user"] = user

                # atualizar perfil básico se id existir
                user_id = extract_user_field(user, "id", None)
                if user_id:
                    try:
                        supabase.table("users_profiles").upsert(
                            {"id": user_id, "plano": "free"}
                        ).execute()
                    except:
                        pass

                _safe_rerun()

            except Exception as e:
                st.error(f"Erro: {e}")

    # --------------------------
    # CRIAR CONTA
    # --------------------------
    elif aba == "Criar Conta":
        st.info("Preencha os dados para criar sua conta.")

        email = st.text_input("E-mail para cadastro")
        senha = st.text_input("Crie uma senha forte", type="password")
        nome = st.text_input("Nome completo")
        empresa = st.text_input("Empresa")
        cnpj_field = st.text_input("CNPJ (opcional)")
        socios = st.text_input("Sócios (separados por vírgula)")
        plano = st.radio("Plano", ["free", "premium"], horizontal=True)

        if cnpj_field:
            st.caption(f"CNPJ formatado: {format_cnpj(cnpj_field)}")

        if st.button("Criar Conta"):
            if not email or not senha or not nome:
                st.warning("Preencha e-mail, senha e nome.")
                return

            try:
                res = supabase.auth.sign_up({"email": email, "password": senha})
                user = res.user

                # pegar ID do usuário recém-criado
                user_id = extract_user_field(user, "id", str(uuid.uuid4()))

                supabase.table("users_profiles").upsert({
                    "id": user_id,
                    "nome": nome,
                    "empresa": empresa,
                    "cnpj": format_cnpj(cnpj_field),
                    "socios": socios,
                    "plano": plano,
                }).execute()

                st.success("Conta criada! Verifique seu e-mail para confirmar o cadastro.")

            except Exception as e:
                st.error(f"Erro ao criar conta: {e}")

    # --------------------------
    # ESQUECI A SENHA
    # --------------------------
    else:
        email = st.text_input("E-mail cadastrado")

        if st.button("Enviar redefinição"):
            if not email:
                st.warning("Informe o e-mail.")
                return

            try:
                supabase.auth.reset_password_for_email(
                    email,
                    options={"redirect_to": RESET_URL}
                )
                st.success("E-mail enviado! Verifique sua caixa de entrada.")

            except Exception as e:
                st.error(f"Erro ao solicitar redefinição: {e}")


# ==========================
# PÁGINA DE REDEFINIÇÃO — 100% CORRIGIDA
# ==========================

def reset_password_page():
    load_header(show_user=False)
    st.subheader("Redefinir Senha")

    params = st.experimental_get_query_params()

    access_token = (
        params.get("access_token", [None])[0]
        or params.get("token", [None])[0]
    )
    refresh_token = params.get("refresh_token", [None])[0]

    nova = st.text_input("Nova senha", type="password")
    nova2 = st.text_input("Repita a nova senha", type="password")

    if st.button("Redefinir senha"):
        if nova != nova2:
            st.error("As senhas não coincidem.")
            return

        if not access_token:
            st.warning("Token ainda não recebido. Aguarde 1–2 segundos e tente novamente.")
            return

        try:
            supabase.auth.set_session(access_token, refresh_token)
        except Exception as e:
            st.error(f"Falha ao criar sessão a partir dos tokens: {e}")
            return

        try:
            supabase.auth.update_user({"password": nova})
            st.success("Senha redefinida com sucesso! Agora você já pode fazer login.")
        except Exception as e:
            st.error(f"Erro ao atualizar senha: {e}")


# ==========================
# LOGOUT
# ==========================

def logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    st.session_state.clear()
    _safe_rerun()


# ==========================
# MAIN
# ==========================

def main():
    params = st.experimental_get_query_params()

    if (
        "reset" in params
        or "access_token" in params
        or "token" in params
        or params.get("type", [""])[0] == "recovery"
    ):
        reset_password_page()
        return

    login_page()


if __name__ == "__main__":
    main()


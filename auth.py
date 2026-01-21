# ============================================================
# auth.py — Autenticação completa Streamlit + Supabase
# Layout profissional, estável e sem HTML fantasma
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
# UTILITÁRIOS
# ==========================

def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def format_cnpj(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) != 14:
        return raw
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def extract_user_field(user, field, default=""):
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(field, default)
    return getattr(user, field, default)


# ==========================
# ESTILO (STREAMLIT NATIVO)
# ==========================

def load_auth_styles():
    st.markdown("""
    <style>
    /* Card central usando container nativo */
    div[data-testid="stVerticalBlock"]:has(
        input[type="email"],
        input[type="password"],
        button
    ) {
        max-width: 440px;
        margin: 2.5rem auto;
        padding: 2.2rem;
        border-radius: 14px;
        background-color: #ffffff;
        box-shadow: 0 8px 28px rgba(0,0,0,0.08);
    }

    input {
        border-radius: 8px !important;
        padding: 10px 12px !important;
    }

    button {
        border-radius: 8px !important;
        height: 42px;
    }
    </style>
    """, unsafe_allow_html=True)


# ==========================
# HEADER
# ==========================

def load_header(show_user=True):
    try:
        col1, col2 = st.columns([2, 6])

        with col1:
            st.image(LOGO_URL, width=220)

        with col2:
            st.markdown(
                "<div style='font-size:28px;font-weight:600;color:#0A2342;'>"
                "Análise Financeira Inteligente</div>",
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

        st.divider()

    except Exception:
        st.title("Análise Financeira Inteligente")
        st.divider()


# ==========================
# LOGIN / CADASTRO / RESET
# ==========================

def login_page():
    load_header(show_user=False)

    # Colunas largas e estáveis
    col_left, col_center, col_right = st.columns([3, 4, 3])

    with col_center:
        st.subheader("Acesso ao sistema")

        aba = st.radio(
            "",
            ["Entrar", "Criar Conta", "Esqueci a Senha"],
            horizontal=True
        )

        st.markdown("---")

        # -------- LOGIN --------
        if aba == "Entrar":
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")

            if st.button("Entrar", use_container_width=True):
                if not email or not senha:
                    st.warning("Informe e-mail e senha.")
                    return

                try:
                    res = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": senha
                    })

                    if not res.user:
                        st.error("E-mail ou senha inválidos.")
                        return

                    st.session_state["user"] = res.user
                    _safe_rerun()

                except Exception as e:
                    st.error(f"Erro: {e}")

        # -------- CADASTRO --------
        elif aba == "Criar Conta":
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            nome = st.text_input("Nome completo")

            if st.button("Criar conta", use_container_width=True):
                try:
                    res = supabase.auth.sign_up({
                        "email": email,
                        "password": senha
                    })

                    uid = extract_user_field(res.user, "id", str(uuid.uuid4()))
                    supabase.table("users_profiles").upsert({
                        "id": uid,
                        "nome": nome,
                        "plano": "free"
                    }).execute()

                    st.success("Conta criada! Verifique seu e-mail.")

                except Exception as e:
                    st.error(f"Erro: {e}")

        # -------- RESET --------
        else:
            email = st.text_input("E-mail cadastrado")

            if st.button("Enviar redefinição", use_container_width=True):
                try:
                    supabase.auth.reset_password_for_email(
                        email,
                        options={"redirect_to": RESET_URL}
                    )
                    st.success("E-mail enviado! Verifique sua caixa de entrada.")
                except Exception as e:
                    st.error(f"Erro: {e}")



# ==========================
# REDEFINIÇÃO DE SENHA
# ==========================

def reset_password_page():
    load_header(show_user=False)
    load_auth_styles()

    _, center, _ = st.columns([2, 3, 2])

    with center:
        st.subheader("Redefinir senha")

        params = st.experimental_get_query_params()

        access_token = (
            params.get("access_token", [None])[0]
            or params.get("token", [None])[0]
        )
        refresh_token = params.get("refresh_token", [None])[0]

        nova = st.text_input("Nova senha", type="password")
        nova2 = st.text_input("Repita a nova senha", type="password")

        if st.button("Redefinir senha", use_container_width=True):
            if nova != nova2:
                st.error("As senhas não coincidem.")
                return

            if not access_token:
                st.warning("Token ainda não recebido. Aguarde alguns segundos.")
                return

            try:
                supabase.auth.set_session(access_token, refresh_token)
                supabase.auth.update_user({"password": nova})
                st.success("Senha redefinida com sucesso! Você já pode fazer login.")
            except Exception as e:
                st.error(f"Erro ao redefinir senha: {e}")


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
    else:
        login_page()


if __name__ == "__main__":
    main()


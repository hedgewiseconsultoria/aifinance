# ============================================================
# auth.py — Autenticação Streamlit + Supabase
# Layout profissional, centralizado e estável
# ============================================================

import streamlit as st
from supabase import create_client
from PIL import Image
import re
import uuid
from datetime import datetime, timedelta  # <<< AJUSTE

# ==========================
# CONFIGURAÇÕES
# ==========================

SITE_URL = "https://inteligenciafinanceira.streamlit.app"
RESET_URL = "https://hedgewiseconsultoria.github.io/aifinance/redirect.htm"

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

#supabase_admin = create_client(
  #  SUPABASE_URL,
    #SUPABASE_SERVICE_ROLE_KEY
#)

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
# HEADER
# ==========================

def load_header(show_user=True):
    try:
        logo = Image.open(LOGO_URL)
        col1, col2 = st.columns([2, 6])

        with col1:
            st.image(logo, width=420)

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

        st.markdown("---")

    except Exception:
        st.title("Análise Financeira Inteligente")
        st.markdown("---")


# ==========================
# ESTILO
# ==========================

def load_auth_styles():
    st.markdown("""
    <style>
        .auth-wrapper {
            display: flex;
            justify-content: center;
        }

        .auth-card {
            width: 100%;
            max-width: 440px;
            padding: 2.2rem;
            border-radius: 14px;
            background-color: #ffffff;
            box-shadow: 0 8px 28px rgba(0,0,0,0.08);
            margin-top: 2rem;
        }

        input[type="email"], input[type="password"], input[type="text"] {
            border-radius: 8px !important;
            padding: 10px 12px !important;
            border: 1px solid #CED4DA !important;
        }

        input:focus {
            border-color: #0A2342 !important;
            box-shadow: 0 0 0 2px rgba(10,35,66,0.15) !important;
        }

        button[kind="primary"] {
            background-color: #0A2342 !important;
            border-radius: 8px !important;
            height: 42px;
        }
    </style>
    """, unsafe_allow_html=True)


# ==========================
# LOGIN / CADASTRO / RESET
# ==========================

def login_page():
    load_header(show_user=False)
    load_auth_styles()

    col_left, col_center, col_right = st.columns([2, 3, 2])

    with col_center:
        with st.container():

            st.subheader("Acesso ao sistema")

            aba = st.radio(
                "",
                ["Entrar", "Criar Conta", "Esqueci a Senha"],
                horizontal=True
            )

            # -------- LOGIN --------
            if aba == "Entrar":
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")

                if st.button("Entrar", use_container_width=True):
                    if not email or not senha:
                        st.warning("Informe e-mail e senha.")
                    else:
                        try:
                            res = supabase.auth.sign_in_with_password({
                                "email": email,
                                "password": senha
                            })

                            user = res.user
                            if not user:
                                st.error("E-mail ou senha inválidos.")
                                return

                            st.session_state["user"] = user

                            user_id = extract_user_field(user, "id", None)
                            if user_id:
                                supabase.table("users_profiles") \
                                    .select("id") \
                                    .eq("id", user_id) \
                                    .single() \
                                    .execute()


                            _safe_rerun()

                        except Exception as e:
                            st.error(f"Erro: {e}")

            # -------- CADASTRO --------
            elif aba == "Criar Conta":
                st.info("Crie sua conta gratuitamente e teste por 7 dias.")

                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                nome = st.text_input("Nome completo")
                empresa = st.text_input("Empresa")
                cnpj = st.text_input("CNPJ (opcional)")
                socios = st.text_input("Sócios (separados por vírgula)")

                if cnpj:
                    st.caption(f"CNPJ formatado: {format_cnpj(cnpj)}")

                # -------- LGPD + TRIAL --------
                trial_inicio = datetime.utcnow()
                trial_fim = trial_inicio + timedelta(days=7)

                aceite_lgpd = st.checkbox(
                    "Li e concordo com a Política de Privacidade e com o tratamento "
                    "dos meus dados financeiros."
                )

                with st.expander("🔒 Política de Privacidade (LGPD)"):
                    st.markdown("""
                    - O aplicativo permite o envio voluntário de extratos bancários e dados financeiros  
                    - As informações são utilizadas exclusivamente para análise financeira personalizada  
                    - Os dados são armazenados em ambiente seguro, com criptografia e controle de acesso  
                    - O acesso é restrito exclusivamente ao usuário responsável pelo envio  
                    - O serviço é oferecido em período de teste gratuito por 7 dias  
                    - Após o período de teste, a continuidade depende da contratação do plano premium  
                    - O usuário pode solicitar a exclusão definitiva dos dados a qualquer momento  
                    """)

                if st.button("Criar conta", use_container_width=True):
                    if not email or not senha or not nome:
                        st.warning("Preencha e-mail, senha e nome.")
                        return

                    if not aceite_lgpd:
                        st.warning("É necessário aceitar a Política de Privacidade para continuar.")
                        return

                    try:
                        res = supabase.auth.sign_up({
                            "email": email,
                            "password": senha
                        })

                        user = res.user
                        user_id = extract_user_field(user, "id", str(uuid.uuid4()))

                        supabase.table("users_profiles").update({
                            "nome": nome,
                            "empresa": empresa,
                            "cnpj": format_cnpj(cnpj),
                            "socios": socios,
                            "lgpd_consentimento": True
                        }).eq("id", user_id).execute()

                        st.success("Conta criada! Você possui 7 dias de teste gratuito.")

                    except Exception as e:
                        st.error(f"Erro ao criar conta: {e}")

            # -------- RESET --------
            else:
                email = st.text_input("E-mail cadastrado")

                if st.button("Enviar redefinição", use_container_width=True):
                    if not email:
                        st.warning("Informe o e-mail.")
                    else:
                        try:
                            supabase.auth.reset_password_for_email(
                                email,
                                options={"redirect_to": RESET_URL}
                            )
                            st.success("E-mail enviado! Verifique sua caixa de entrada.")
                        except Exception as e:
                            st.error(f"Erro: {e}")


# ==========================
# RESET PASSWORD
# ==========================

def reset_password_page():
    load_header(show_user=False)
    load_auth_styles()

    col_left, col_center, col_right = st.columns([2, 3, 2])

    with col_center:
        with st.container():
            st.markdown('<div class="auth-wrapper"><div class="auth-card">', unsafe_allow_html=True)

            st.subheader("Redefinir senha")

            params = st.experimental_get_query_params()
            access_token = params.get("access_token", [None])[0] or params.get("token", [None])[0]
            refresh_token = params.get("refresh_token", [None])[0]

            nova = st.text_input("Nova senha", type="password")
            nova2 = st.text_input("Repita a nova senha", type="password")

            if st.button("Redefinir senha", use_container_width=True):
                if nova != nova2:
                    st.error("As senhas não coincidem.")
                    return

                if not access_token:
                    st.warning("Token ainda não recebido.")
                    return

                try:
                    supabase.auth.set_session(access_token, refresh_token)
                    supabase.auth.update_user({"password": nova})
                    st.success("Senha redefinida com sucesso!")
                except Exception as e:
                    st.error(f"Erro: {e}")


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
        or params.get("type", [""])[0] == "recovery"
    ):
        reset_password_page()
    else:
        login_page()


if __name__ == "__main__":
    main()







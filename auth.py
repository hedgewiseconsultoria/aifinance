import streamlit as st
from supabase import create_client

# ================================
# CONFIGURAÇÃO SUPABASE
# ================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
REDIRECT_URL = st.secrets["REDIRECT_URL"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ================================
# PÁGINA DE LOGIN
# ================================
def login_page():
    st.title("🔐 Acesso ao Hedgewise FinanceAI")

    st.markdown("Entre com uma conta social ou com e-mail e senha para continuar:")

    # --- LINKS DE LOGIN SOCIAL ---
    oauth_links = {
        "Google": f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={REDIRECT_URL}",
        "Apple": f"{SUPABASE_URL}/auth/v1/authorize?provider=apple&redirect_to={REDIRECT_URL}",
        "Facebook": f"{SUPABASE_URL}/auth/v1/authorize?provider=facebook&redirect_to={REDIRECT_URL}"
    }

    for prov, link in oauth_links.items():
        st.markdown(f"[Entrar com {prov}]({link})")

    st.markdown("---")
    st.subheader("Ou entre com e-mail e senha:")

    email = st.text_input("E-mail")
    password = st.text_input("Senha", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Entrar"):
            try:
                user = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = user.user
                st.rerun()
            except Exception:
                st.error("❌ Erro ao entrar. Verifique e-mail/senha ou confirme seu cadastro.")
    with col2:
        if st.button("Criar conta"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("Conta criada! Confirme pelo e-mail antes de acessar.")
            except Exception as e:
                st.error(f"Erro ao criar conta: {e}")


# ================================
# LOGOUT
# ================================
def logout():
    st.session_state.pop("user", None)
    st.success("Sessão encerrada.")
    st.experimental_rerun()
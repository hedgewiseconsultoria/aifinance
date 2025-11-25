# auth.py — versão final (OPÇÃO A) — compatível com supabase-py antigo
"""
Auth helper para Streamlit + Supabase (versão antiga do supabase-py).

Características:
- Envio de recovery via POST /auth/v1/recover (requests) para garantir que o template
  correto seja usado no Supabase V2.
- Detecta rota /reset-password via JS (Streamlit não expõe path) e aciona a página de reset.
- Converte hash (#access_token=...) em query params (?access_token=...) para que o app
  capture tokens enviados quando disponíveis.
- Mantém layout, estilos e fluxos do seu código anterior.
"""

import streamlit as st
from supabase import create_client
from PIL import Image
import re
import uuid
import requests
from urllib.parse import urlencode, urlparse, parse_qs

# ==========================
# CONFIGURAÇÕES BÁSICAS
# ==========================
SITE_URL = "https://inteligenciafinanceira.streamlit.app"
RESET_ROUTE = "/reset-password"
RESET_REDIRECT = SITE_URL + RESET_ROUTE   # usado no e-mail

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
LOGO_URL = "FinanceAI_1.png"

# ==========================
# UTILITÁRIOS / JS HELPERS
# ==========================
def inject_js_hash_to_query():
    """
    Injeta JS que converte uma URL com hash
    (#access_token=...&refresh_token=...) em query params (?access_token=...&refresh_token=...).
    Deve ser chamado logo no início da renderização.
    """
    js = """
    <script>
    (function(){
      try{
        const h = window.location.hash;
        if (h && (h.includes('access_token') || h.includes('refresh_token'))) {
          const query = h.substring(1); // remove #
          const newUrl = window.location.href.split('#')[0] + '?' + query;
          window.history.replaceState(null, '', newUrl);
        }
      }catch(e){console && console.log(e)}
    })();
    </script>
    """
    st.components.v1.html(js, height=0)

def inject_js_path_detector():
    """
    Injeta JS que envia mensagem para o Streamlit quando o pathname terminar em /reset-password.
    Ao detectar, altera a query para ?reset=1 para que o Python identifique e mostre a página correta.
    """
    js = """
    <script>
    (function(){
      try{
        const path = window.location.pathname;
        if (path && path.endsWith("/reset-password")) {
          // adiciona ?reset=1 preservando query existente
          const hasQuery = window.location.search && window.location.search.length > 0;
          if (!hasQuery || !window.location.search.includes("reset=")) {
            const newSearch = (hasQuery ? window.location.search + "&reset=1" : "?reset=1");
            const newUrl = window.location.origin + window.location.pathname + newSearch + window.location.hash;
            window.history.replaceState(null, '', newUrl);
          }
        }
      } catch(e){console && console.log(e)}
    })();
    </script>
    """
    st.components.v1.html(js, height=0)

def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

# ==========================
# AUXILIARES
# ==========================
def format_cnpj(raw: str) -> str:
    digits = re.sub(r"\D", "", (raw or ""))
    if len(digits) != 14:
        return raw
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"

# ==========================
# HEADER UI
# ==========================
def load_header(show_user=True):
    try:
        logo = Image.open(LOGO_URL)
        col1, col2 = st.columns([2, 5])
        with col1:
            st.image(logo, width=600)
        with col2:
            st.markdown(
                '<div style="font-size:28px; font-weight:600; color:#0A2342; margin-top:0.2em;">Análise Financeira Inteligente</div>',
                unsafe_allow_html=True,
            )
            st.caption("Traduzindo números em histórias que façam sentido...")
            if show_user and "user" in st.session_state:
                user = st.session_state.get("user")
                email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
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
# LOGIN / CADASTRO / RECUPERAÇÃO
# ==========================
def login_page():
    load_header(show_user=False)

    st.markdown(
        """
        <style>
        input[type="email"], input[type="password"], input[type="text"] {
            border: 1px solid #0A2342 !important;
            border-radius: 6px !important;
            padding: 8px 10px !important;
        }
        input:focus { border-color: #007BFF !important; box-shadow: 0 0 4px #007BFF !important; }
        button[kind="primary"] { background-color: #0A2342 !important; color: white !important; border-radius: 6px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Acesso ao sistema")
    aba = st.radio("", ["Entrar", "Criar Conta", "Esqueci a Senha"], horizontal=True)

    # LOGIN
    if aba == "Entrar":
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if not email or not senha:
                st.warning("Informe e-mail e senha.")
                return
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                user = res.get("user") if isinstance(res, dict) else getattr(res, "user", None)
                if not user:
                    st.error("E-mail ou senha incorretos")
                    return
                st.session_state["user"] = user
                try:
                    supabase.table("users_profiles").upsert({"id": user.get("id"), "plano": "free"}).execute()
                except Exception:
                    pass
                _safe_rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

    # CRIAR CONTA
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
                user = res.user if hasattr(res, "user") else (res.get("user") if isinstance(res, dict) else None)
                user_id = user.id if user else str(uuid.uuid4())
                supabase.table("users_profiles").upsert({
                    "id": user_id,
                    "nome": nome,
                    "empresa": empresa,
                    "cnpj": format_cnpj(cnpj_field),
                    "socios": socios,
                    "plano": plano
                }).execute()
                st.success("Conta criada. Verifique seu e-mail para confirmar o cadastro.")
            except Exception as e:
                st.error(f"Erro ao criar conta: {e}")

    # RECUPERAÇÃO DE SENHA — OPÇÃO A (HTTP MANUAL)
    else:
        email = st.text_input("E-mail cadastrado")
        if st.button("Enviar redefinição"):
            if not email:
                st.warning("Informe o e-mail.")
            else:
                try:
                    url = f"{SUPABASE_URL}/auth/v1/recover"
                    headers = {
                        "apikey": SUPABASE_KEY,
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "email": email,
                        "redirect_to": RESET_REDIRECT
                    }

                    r = requests.post(url, json=payload, headers=headers, timeout=10)

                    if r.status_code in (200, 201):
                        st.success("E-mail enviado. Verifique sua caixa de entrada.")
                    else:
                        # tenta mostrar mensagem útil
                        try:
                            err = r.json()
                        except Exception:
                            err = r.text
                        st.error(f"Erro ao solicitar redefinição: {err}")
                except Exception as e:
                    st.error(f"Erro ao solicitar redefinição: {e}")

# ==========================
# PÁGINA DE REDEFINIÇÃO
# ==========================
def reset_password_page():
    """
    Página exibida para redefinir a senha.
    Aceita:
    - tokens via query (?access_token=...&refresh_token=...)
    - ou sem tokens (neste caso instruí o usuário a abrir o email e usar o link)
    """
    inject_js_hash_to_query()
    st.title("Redefinição de senha")

    params = st.experimental_get_query_params()
    access_token = params.get("access_token", [None])[0]
    refresh_token = params.get("refresh_token", [None])[0]

    # Se não houver token, informa instruções
    if not access_token:
        st.info("Abra o e-mail de recuperação e clique no botão 'Redefinir Senha' para que o link contenha os tokens necessários. Se o link vier sem tokens, contate o suporte.")
        # Também podemos mostrar um campo alternativo para colar o link (opcional)
        pasted = st.text_area("Cole aqui o link de recuperação (se você tiver):", height=80)
        if pasted and "access_token=" in pasted:
            try:
                # extrai tokens do link colado
                parsed = urlparse(pasted)
                q = parsed.fragment or parsed.query
                # fragment style: access_token=...&refresh_token=...
                if parsed.fragment:
                    frag_qs = dict(pair.split("=", 1) for pair in parsed.fragment.split("&") if "=" in pair)
                    access_token = frag_qs.get("access_token")
                    refresh_token = frag_qs.get("refresh_token")
                else:
                    parsed_qs = parse_qs(parsed.query)
                    access_token = parsed_qs.get("access_token", [None])[0]
                    refresh_token = parsed_qs.get("refresh_token", [None])[0]
                st.experimental_set_query_params(access_token=access_token or "", refresh_token=refresh_token or "")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Não foi possível extrair tokens do link colado: {e}")
        return

    nova = st.text_input("Nova senha", type="password")
    nova2 = st.text_input("Repita a nova senha", type="password")

    if st.button("Redefinir senha"):
        if not nova or nova != nova2:
            st.error("As senhas não coincidem.")
            return

        # restaurar sessão usando AccessToken + RefreshToken (SDK antigo: exchange_token)
        try:
            tokens = {"access_token": access_token}
            if refresh_token:
                tokens["refresh_token"] = refresh_token

            # Algumas versões do SDK aceitam dict, outras não — envolver em try/except
            try:
                supabase.auth.exchange_token(tokens)
            except Exception:
                # fallback: tentar set_session se disponível
                try:
                    supabase.auth.set_session(access_token, refresh_token)
                except Exception:
                    # ultima tentativa: set_session com dict
                    try:
                        supabase.auth.set_session(tokens)
                    except Exception as e:
                        raise e

        except Exception as e:
            st.error(f"Erro ao restaurar sessão: {e}")
            return

        # atualizar a senha
        try:
            supabase.auth.update_user({"password": nova})
            st.success("Senha redefinida com sucesso! Agora você pode fazer login.")
        except Exception as e:
            st.error(f"Erro ao atualizar senha: {e}")

# ==========================
# LOGOUT
# ==========================
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    _safe_rerun()

# ==========================
# MAIN
# ==========================
def main():
    # garante chaves de sessão usadas pelo detector JS
    if 'init_auth_js' not in st.session_state:
        st.session_state['init_auth_js'] = True

    # 1) detecta hash -> query (para tokens)
    inject_js_hash_to_query()

    # 2) detecta path /reset-password e transforma em ?reset=1
    inject_js_path_detector()

    # 3) Se a query explicitamente pede reset, abre a página de redefinição
    params = st.experimental_get_query_params()
    if "reset" in params:
        reset_password_page()
        return

    # 4) Se houver tokens na query, também abrir
    if ("access_token" in params) or ("token" in params) or (params.get("type", [""])[0] == "recovery"):
        reset_password_page()
        return

    # 5) caso padrão: tela de login
    login_page()

if __name__ == "__main__":
    main()

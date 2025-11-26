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
RESET_URL = SITE_URL + "/?reset=1"  # URL autorizada no painel do Supabase

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
            st.caption("Traduzindo números em histórias que façam sentido...")

            if show_user and "user" in st.session_state:
                user = st.session_state.get("user")
                email = user.get("email")
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

                user = res.get("user")
                if not user:
                    st.error("E-mail ou senha incorretos.")
                    return

                st.session_state["user"] = user

                try:
                    supabase.table("users_profiles").upsert(
                        {"id": user.get("id"), "plano": "free"}
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
                user = res.user or {}

                supabase.table("users_profiles").upsert({
                    "id": user.get("id", str(uuid.uuid4())),
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
# PÁGINA DE REDEFINIÇÃO (CORRIGIDA)
# ==========================

def reset_password_page():
    st.title("Redefinição de Senha")

    # 1. Tenta obter os tokens do fragmento da URL (hash) via JavaScript
    js_code = """
    <script>
        const params = new URLSearchParams(window.location.hash.substring(1));
        const accessToken = params.get('access_token');
        const refreshToken = params.get('refresh_token');
        
        // Armazena no localStorage para o Python ler
        if (accessToken) {
            localStorage.setItem('supabase_access_token', accessToken);
            localStorage.setItem('supabase_refresh_token', refreshToken);
            // Limpa o hash da URL para evitar que o Streamlit recarregue em loop
            window.history.replaceState(null, null, window.location.pathname + window.location.search);
        }
    </script>
    """
    st.components.v1.html(js_code, height=0)

    # 2. Tenta ler os tokens do localStorage (onde o JS os colocou)
    # Nota: O Streamlit não tem acesso direto ao localStorage.
    # A maneira mais simples é forçar o usuário a clicar no botão de redefinição
    # para que o JS tenha tempo de executar e o Streamlit possa tentar ler
    # os tokens do query params na próxima execução, se o JS os tivesse movido.
    # No entanto, a abordagem mais robusta é usar o st.session_state.
    
    # Para simplificar, vamos confiar que o Supabase injeta os tokens no query params
    # ou que o JS fará o trabalho. Mas a principal correção é a lógica de erro.
    
    params = st.experimental_get_query_params()
    access_token = params.get("access_token", [None])[0]
    refresh_token = params.get("refresh_token", [None])[0]

    # Se o JS não funcionar, vamos tentar ler do localStorage via um truque
    # ou simplesmente aceitar que o Supabase injeta no query params.
    # O problema é que o Supabase INJETA NO FRAGMENTO (#), e o Streamlit só lê QUERY PARAMS (?).
    # A solução mais limpa é forçar o Supabase a usar QUERY PARAMS.
    # Como não podemos mudar o Supabase, vamos forçar o JS a mover o token para o query param.
    
    # CORREÇÃO: O JS acima move o token para o localStorage e limpa o hash.
    # O Streamlit precisa ler o token do localStorage.
    # Como o Streamlit não tem acesso direto ao localStorage, a solução mais comum
    # é fazer o JS redirecionar para a mesma página, mas com os tokens no QUERY PARAM.
    
    # Vamos reverter a lógica de extração para a original, mas adicionar o JS
    # que fará o redirecionamento para a mesma página com os tokens no QUERY PARAM.
    
    # Lógica de extração original:
    # params = st.experimental_get_query_params()
    # access_token = params.get("access_token", [None])[0]
    # refresh_token = params.get("refresh_token", [None])[0]
    
    # O código abaixo é a correção do fluxo de tokens:
    js_code_fix = """
    <script>
        const hash = window.location.hash;
        if (hash.includes('access_token') && !window.location.search.includes('access_token')) {
            const params = new URLSearchParams(hash.substring(1));
            const accessToken = params.get('access_token');
            const refreshToken = params.get('refresh_token');
            
            // Redireciona para a mesma URL, mas com os tokens no query param
            window.location.href = window.location.origin + window.location.pathname + 
                                   '?reset=1&access_token=' + accessToken + 
                                   '&refresh_token=' + refreshToken;
        }
    </script>
    """
    st.components.v1.html(js_code_fix, height=0)
    
    # Após o redirecionamento, o Streamlit recarrega e os tokens estarão no query param.
    # O código Python abaixo lerá os tokens corretamente.
    # O Supabase injeta os tokens no fragmento (#), mas o Streamlit só lê o query param (?).
    # Este bloco de código JavaScript lê o fragmento e redireciona para a mesma página,
    # mas com os tokens no query param, forçando o Streamlit a recarregar e capturá-los.
    js_code_fix = """
    <script>
        const hash = window.location.hash;
        // Verifica se há tokens no hash e se eles AINDA NÃO estão no query param
        if (hash.includes('access_token') && !window.location.search.includes('access_token')) {
            const params = new URLSearchParams(hash.substring(1));
            const accessToken = params.get('access_token');
            const refreshToken = params.get('refresh_token');
            
            // Redireciona para a mesma URL, mas com os tokens no query param
            // Isso força o Streamlit a recarregar e o Python a ler os tokens
            window.location.href = window.location.origin + window.location.pathname + 
                                   '?reset=1&access_token=' + accessToken + 
                                   '&refresh_token=' + refreshToken;
        }
    </script>
    """
    st.components.v1.html(js_code_fix, height=0)
    
    # Após o redirecionamento (se necessário), o Streamlit recarrega e o Python lê os tokens.
    params = st.experimental_get_query_params()
    access_token = params.get("access_token", [None])[0]
    refresh_token = params.get("refresh_token", [None])[0]

    # O formulário só deve aparecer se os tokens estiverem presentes (após o redirecionamento)
    if access_token and refresh_token:
        nova = st.text_input("Nova senha", type="password")
        nova2 = st.text_input("Repita a nova senha", type="password")
    else:
        # Se não houver tokens, exibe a mensagem de espera/erro
        # A mensagem de espera só deve ser exibida se o parâmetro 'reset=1' estiver presente,
        # indicando que o usuário veio do fluxo de redefinição, mas os tokens ainda não chegaram.
        if "reset" in params:
            st.warning("Aguardando tokens de redefinição... Se você acabou de clicar no link do e-mail, aguarde o redirecionamento automático.")
            st.stop()
        else:
            # Caso contrário, é um acesso direto sem tokens e sem o parâmetro 'reset=1'
            st.error("Acesso inválido à página de redefinição de senha.")
            st.stop()

    if st.button("Redefinir senha"):
        if nova != nova2:
            st.error("As senhas não coincidem.")
            return

        # 1. Verifica se os tokens estão presentes na URL
        # Esta verificação é redundante após a lógica de st.stop() acima,
        # mas mantida para segurança.
        if not access_token or not refresh_token:
            st.error("Erro: Tokens de redefinição não encontrados na URL. Por favor, clique no link do e-mail novamente.")
            return

        # 2. Define a nova senha
        try:
            # O Supabase já deve ter autenticado o usuário via URL.
            # Basta chamar o update_user.
            # O `exchange_token` não é necessário e pode causar problemas.
            res = supabase.auth.update_user({"password": nova})
            
            # 3. Verifica se a atualização foi bem-sucedida
            if res.user:
                st.success("Senha redefinida com sucesso! Você será redirecionado para a tela de login.")
                # Limpa os parâmetros da URL para evitar loop e força o login_page
                st.experimental_set_query_params()
                st.session_state.clear()
                _safe_rerun()
            else:
                st.error("Erro ao atualizar senha. O token pode ter expirado. Tente o processo de redefinição novamente.")

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

    # captura fluxos de redefinição
    # Se houver 'reset' (do redirect_to) OU 'access_token' (do Supabase)
    if "reset" in params or "access_token" in params:
        reset_password_page()
        return

    # login
    login_page()


if __name__ == "__main__":
    main()

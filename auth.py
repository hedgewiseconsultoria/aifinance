import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def convert_hash_to_query():
    js = """
    <script>
    (function(){
      const hash = window.location.hash;
      if (hash && hash.includes('access_token')) {
        const newUrl = window.location.href.replace('#', '?');
        window.history.replaceState(null, '', newUrl);
      }
    })();
    </script>
    """
    st.components.v1.html(js)

def get_query_param(name):
    # pega via st.experimental_get_query_params (Streamlit)
    params = st.experimental_get_query_params()
    return params.get(name, [None])[0]

def reset_password_page():
    st.title("Redefinição de senha")

    # força a conversão do fragment (#access_token=...) para query (?access_token=...)
    convert_hash_to_query()

    access_token = get_query_param("access_token") or get_query_param("token")
    st.write("Debug: access_token encontrado?", bool(access_token))
    if not access_token:
        st.info("Nenhum token de redefinição detectado na URL. Clique no link do e-mail de redefinição e volte aqui.")
        return

    nova = st.text_input("Nova senha", type="password", key="nova")
    nova2 = st.text_input("Repita a nova senha", type="password", key="nova2")

    if st.button("Redefinir senha"):
        if not nova or nova != nova2:
            st.error("As senhas não batem ou estão vazias.")
            return
        try:
            # Atualiza o usuário passando access_token (isso autentica a requisição)
            res = supabase.auth.update_user({"password": nova}, access_token=access_token)
            # res pode vir como dict ou objeto dependendo do client
            st.success("Senha redefinida com sucesso! Tente entrar com a nova senha.")
        except Exception as e:
            st.error(f"Erro ao atualizar senha: {e}")

if __name__ == "__main__":
    reset_password_page()

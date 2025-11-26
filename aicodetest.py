import streamlit as st
import pandas as pd
import json
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from google import genai
from google.genai import types
import traceback
import math
import hashlib
from datetime import datetime, timedelta

# integração auth/supabase (arquivo auth.py que você forneceu)
from auth import (
    login_page,
    logout,
    supabase,
    reset_password_page,
    )

# funções de relatórios (arquivo reports_functions.py)
from reports_functions import secao_relatorios_dashboard

# ----------------------
# PLANO DE CONTAS
# ----------------------
PLANO_DE_CONTAS = {
    "sinteticos": [
        {
            "codigo": "OP",
            "nome": "Atividades Operacionais",
            "tipo_fluxo": "OPERACIONAL",
            "contas": [
                {"codigo": "OP-01", "nome": "Receitas de Vendas"},
                {"codigo": "OP-02", "nome": "Receitas de Serviços"},
                {"codigo": "OP-03", "nome": "Outras Receitas Operacionais"},
                {"codigo": "OP-04", "nome": "Custos Operacionais"},
                {"codigo": "OP-05", "nome": "Despesas Administrativas"},
                {"codigo": "OP-06", "nome": "Despesas Comerciais"},
                {"codigo": "OP-07", "nome": "Despesas com Pessoal"},
                {"codigo": "OP-08", "nome": "Impostos e Contribuições"},
                {"codigo": "OP-09", "nome": "Tarifas Bancárias e Serviços"}
            ]
        },
        {
            "codigo": "INV",
            "nome": "Atividades de Investimento",
            "tipo_fluxo": "INVESTIMENTO",
            "contas": [
                {"codigo": "INV-01", "nome": "Aquisição de Imobilizado"},
                {"codigo": "INV-02", "nome": "Aplicações Financeiras"},
                {"codigo": "INV-03", "nome": "Alienação de Ativos"}
            ]
        },
        {
            "codigo": "FIN",
            "nome": "Atividades de Financiamento",
            "tipo_fluxo": "FINANCIAMENTO",
            "contas": [
                {"codigo": "FIN-01", "nome": "Empréstimos Recebidos"},
                {"codigo": "FIN-02", "nome": "Pagamento de Empréstimos"},
                {"codigo": "FIN-03", "nome": "Juros sobre Empréstimos e Financiamentos"},
                {"codigo": "FIN-04", "nome": "Aporte de Sócios"},
                {"codigo": "FIN-05", "nome": "Retirada de Sócios / Pró-labore e Despesas Pessoais"}
            ]
        },
        {
            "codigo": "NE",
            "nome": "Ajustes e Transferências Internas",
            "tipo_fluxo": "NEUTRO",
            "contas": [
                {"codigo": "NE-01", "nome": "Transferências entre Contas"},
                {"codigo": "NE-02", "nome": "Ajustes e Estornos"}
            ]
        }
    ]
}

# --- THEME / CSS ---
PRIMARY_COLOR = "#0A2342"
BACKGROUND_COLOR = "#F0F2F6"
ACCENT_COLOR = "#007BFF"
REPORT_BACKGROUND = "#F9F5EB"
LOGO1_FILENAME = "FinanceAI_1.png"
LOGO_FILENAME = "logo_hedgewise.png"

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="logo_hedgewise.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🔥 Ajuste essencial para reset password funcionar

st.markdown(
    f"""
    <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {{
            background-color: {BACKGROUND_COLOR} !important;
            color: #000000 !important;
        }}
        .stButton>button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: bold;
        }}
        .report-box {{
            background-color: {REPORT_BACKGROUND};
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #DDDDDD;
        }}
        .main-header {{
            font-size: 1.8em;
            font-weight: 800;
            color: {PRIMARY_COLOR};
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# --- session_state defaults ---
if 'df_transacoes_editado' not in st.session_state:
    st.session_state['df_transacoes_editado'] = pd.DataFrame()
if 'contexto_adicional' not in st.session_state:
    st.session_state['contexto_adicional'] = ""

# --- Gemini client init (non-fatal if missing) ---
client = None
try:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=gemini_key)
except Exception:
    client = None

# --- PYDANTIC MODELS ---
class Transacao(BaseModel):
    data: str
    descricao: str
    valor: float
    tipo_movimentacao: str
    conta_analitica: str

class AnaliseCompleta(BaseModel):
    transacoes: List[Transacao]
    saldo_final: Optional[float] = None

# --- HELPERS ---
def formatar_brl(valor: float) -> str:
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP_SEP").replace(".", ",").replace("TEMP_SEP", ".")
        return "R$ " + valor_brl
    except Exception:
        return f"R$ {valor:.2f}"

def enriquecer_com_plano_contas(df: pd.DataFrame) -> pd.DataFrame:
    mapa_contas = {}
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        for conta in sintetico["contas"]:
            mapa_contas[conta["codigo"]] = {
                "nome_conta": conta["nome"],
                "codigo_sintetico": sintetico["codigo"],
                "nome_sintetico": sintetico["nome"],
                "tipo_fluxo": sintetico["tipo_fluxo"]
            }
    df = df.copy()
    df['nome_conta'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('nome_conta', 'Não classificado'))
    df['codigo_sintetico'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('codigo_sintetico', 'NE'))
    df['nome_sintetico'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('nome_sintetico', 'Não classificado'))
    df['tipo_fluxo'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('tipo_fluxo', 'NEUTRO'))

    def _label_from_code(code):
        try:
            if code is None or (isinstance(code, float) and pd.isna(code)):
                return ''
        except Exception:
            pass
        nome = mapa_contas.get(code, {}).get('nome_conta', '')
        if nome:
            return f"{code} - {nome}"
        return str(code)

    df['conta_display'] = df['conta_analitica'].map(lambda x: _label_from_code(x))
    return df

# --- PROMPT (OPÇÃO B: string normal + format) ---
def gerar_prompt_com_plano_contas() -> str:
    contas_str = "### PLANO DE CONTAS ###\n\n"
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        contas_str += "{} - {} (Tipo: {})\n".format(sintetico['codigo'], sintetico['nome'], sintetico['tipo_fluxo'])
        for conta in sintetico["contas"]:
            contas_str += "  - {}: {}\n".format(conta['codigo'], conta['nome'])
        contas_str += "\n"

    prompt_template = """
Você é um especialista em extração e classificação de dados financeiros.

{contas_str}

Extraia todas as transações deste extrato bancário em PDF e classifique cada transação de acordo com o PLANO DE CONTAS acima.

INSTRUÇÕES CRÍTICAS:
1. Use EXATAMENTE os códigos do plano de contas.
2. Retorne APENAS um JSON válido.
3. Siga os códigos do plano de contas sem inventar novos códigos.

O JSON de saída deve ter o seguinte formato:

{{
  "transacoes": [
    {{
      "data": "DD/MM/AAAA",
      "descricao": "...",
      "valor": 123.45,
      "tipo_movimentacao": "DEBITO",
      "conta_analitica": "OP-04"
    }}
  ],
  "saldo_final": 0.0
}}

IMPORTANTE:
- "valor" deve ser sempre número positivo.
- "tipo_movimentacao" deve ser "CREDITO" ou "DEBITO".
- O JSON DEVE SER VÁLIDO — NÃO coloque comentários nem texto fora do JSON.
"""

    return prompt_template.format(contas_str=contas_str)


# --- FUNÇÃO QUE CHAMA A GEMINI (cached) ---
@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')
    prompt_analise = gerar_prompt_com_plano_contas()

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AnaliseCompleta,
        temperature=0.2
    )
    try:
        if client is None:
            raise ValueError("Cliente Gemini não inicializado. Configure GEMINI_API_KEY em secrets.")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[pdf_part, prompt_analise],
            config=config,
        )

        response_json = json.loads(response.text)
        dados_pydantic = AnaliseCompleta(**response_json)
        return dados_pydantic.model_dump()
    except Exception as e:
        error_message = str(e)
        if "503 UNAVAILABLE" in error_message or "model is overloaded" in error_message:
            st.error(f"O modelo Gemini está temporariamente indisponível ao processar '{filename}'.")
            st.info("Tente novamente em alguns minutos.")
        elif "Invalid API key" in error_message or "401" in error_message or "permission" in error_message.lower():
            st.error("Problema de autenticação com a Gemini API. Verifique a sua chave (GEMINI_API_KEY).")
        else:
            st.error(f"Ocorreu um erro ao processar '{filename}': {error_message}")
        return {
            'transacoes': [],
            'saldo_final': 0.0
        }

# --- CABEÇALHO UI ---
def load_header():
    try:
        logo = Image.open(LOGO1_FILENAME)
        col1, col2 = st.columns([2, 5])
        with col1:
            st.image(logo, width=1000)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("Traduzindo números em histórias que façam sentido...")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")

# --------------------------
# AUTENTICAÇÃO E MENU
# --------------------------

params = st.experimental_get_query_params()

# 🔥 INÍCIO DO AJUSTE: Tratar o fluxo de redefinição de senha
is_reset_flow = (
    "reset" in params
    or "access_token" in params
    or "refresh_token" in params
    or params.get("type", [""])[0] == "recovery"
)

if is_reset_flow:
    reset_password_page()
    st.stop()
# 🔥 FIM DO AJUSTE

# Se usuário não logado → tela de login
if "user" not in st.session_state:
    login_page()
    st.stop()

# Se logado → interface normal
user = st.session_state["user"]
# Note: user pode ser um objeto de autenticação ou um dicionário.
user_email = getattr(user, 'email', user.get('email', '')) if isinstance(user, dict) or hasattr(user, 'email') else ''
st.sidebar.write(f"Olá, {user_email}")

if st.sidebar.button("Sair"):
    logout()

load_header()

st.sidebar.title("Navegação")
page = st.sidebar.radio("Seções:", ["Upload e Extração", "Revisão de Dados", "Dashboard & Relatórios"])


# --------------------------
# 1. Upload e Extração
# --------------------------
if page == "Upload e Extração":
    st.markdown("### 1. Upload e Extração de Dados")
    st.markdown("Faça o upload dos extratos em PDF. O sistema irá extrair as transações e classificá-las conforme o plano de contas. Após revisão você poderá salvar as transações no banco de dados.")

    with st.expander("Plano de Contas Utilizado", expanded=False):
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            st.markdown("**{} - {}** ({})".format(sintetico['codigo'], sintetico['nome'], sintetico['tipo_fluxo']))
            for conta in sintetico["contas"]:
                st.markdown("  - `{}`: {}".format(conta['codigo'], conta['nome']))

    with st.expander("Upload de Arquivos", expanded=True):
        uploaded_files = st.file_uploader(
            "Selecione os arquivos PDF dos seus extratos bancários",
            type="pdf",
            accept_multiple_files=True,
            key="pdf_uploader",
            help="Os PDFs devem ter texto selecionável (não apenas imagem)."
        )

    if uploaded_files:
        if st.button(f"Executar Extração e Classificação ({len(uploaded_files)} arquivos)", key="analyze_btn"):
            todas_transacoes = []
            extraction_status = st.empty()
            extraction_status.info("Iniciando extração e classificação.")
            user_id = None
            try:
                user_id = user.id if hasattr(user, "id") else user.get("id")
            except Exception:
                user_id = None

            for i, uploaded_file in enumerate(uploaded_files):
                extraction_status.info(f"Processando arquivo {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
                pdf_bytes = uploaded_file.getvalue()

                # calcula hash e verifica duplicidade (metadados)
                file_hash = hashlib.sha256(pdf_bytes).hexdigest()
                try:
                    existente = supabase.table("extratos").select("*").eq("hash_arquivo", file_hash).execute()
                    existente_data = getattr(existente, "data", existente)
                    already_exists = bool(existente_data)
                except Exception:
                    existente_data = None
                    already_exists = False

                if already_exists:
                    extraction_status.warning(f"O arquivo {uploaded_file.name} já foi registrado anteriormente. Pulando registro duplicado, mas extração será tentada.")

                # tenta salvar PDF no Storage com nome único
                try:
                    if user_id:
                        supabase.storage.from_("extratos").upload(f"{user_id}/{file_hash}_{uploaded_file.name}", pdf_bytes)
                except Exception:
                    pass

                # registra metadados do extrato (se ainda não registrado)
                try:
                    if not already_exists:
                        resultado = supabase.table("extratos").insert({
                            "user_id": user_id,
                            "nome_arquivo": uploaded_file.name,
                            "hash_arquivo": file_hash
                        }).execute()
                        extrato_id = resultado.data[0]["id"] if resultado.data else None
                    else:
                        extrato_id = existente_data[0]["id"] if existente_data else None
                except Exception:
                    extrato_id = None

                # chama a função que usa Gemini / extração
                dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name, client)
                transacoes = dados_dict.get('transacoes', [])

                # Anotar cada transação com extrato_id (para manter vínculo)
                for t in transacoes:
                    try:
                        t['extrato_id'] = extrato_id
                    except Exception:
                        t.update({'extrato_id': extrato_id})

                todas_transacoes.extend(transacoes)

            df_transacoes = pd.DataFrame(todas_transacoes)

            if df_transacoes.empty:
                extraction_status.error("❌ Nenhuma transação válida foi extraída. Verifique se o PDF contém texto legível e se o arquivo não está corrompido.")
                st.session_state['df_transacoes_editado'] = pd.DataFrame()
            else:
                extraction_status.success("✅ Extração de {} transações concluída!".format(len(todas_transacoes)))

                # Normalizações
                df_transacoes['valor'] = pd.to_numeric(df_transacoes['valor'], errors='coerce').fillna(0)
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'], errors='coerce', dayfirst=True)
                df_transacoes['tipo_movimentacao'] = df_transacoes['tipo_movimentacao'].fillna('DEBITO')
                df_transacoes['conta_analitica'] = df_transacoes['conta_analitica'].fillna('NE-02')

                # Enriquecer com plano de contas
                df_transacoes = enriquecer_com_plano_contas(df_transacoes)

                # Guardar no session_state para revisão manual posterior
                st.session_state['df_transacoes_editado'] = df_transacoes
                st.success("✅ Dados carregados e classificados localmente. Vá para 'Revisão de Dados' para confirmar e gravar no banco de dados.")

    # Exibir lista de extratos já carregados (ID, nome_arquivo, criado_em)
    st.subheader("Extratos já carregados")
    try:
        user_id = user.id if hasattr(user, "id") else user.get("id")
        extratos_existentes = supabase.table("extratos").select("id, nome_arquivo, criado_em").eq("user_id", user_id).order("criado_em", desc=True).execute()
        extratos_data = getattr(extratos_existentes, "data", extratos_existentes)
        if not extratos_data:
            st.info("Nenhum extrato carregado ainda.")
        else:
            df_extratos = pd.DataFrame(extratos_data)
            if 'criado_em' in df_extratos.columns:
                try:
                    df_extratos["criado_em"] = pd.to_datetime(df_extratos["criado_em"]).dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    pass
            st.dataframe(df_extratos[['id', 'nome_arquivo', 'criado_em']], use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao buscar extratos: {e}")

# --------------------------
# 2. Revisão de Dados
# --------------------------
elif page == "Revisão de Dados":
    st.markdown("### 2. Revisão e Correção Manual dos Dados")

    if not st.session_state.get('df_transacoes_editado', pd.DataFrame()).empty:
        st.info("Revise as classificações e corrija manualmente qualquer erro.")

        # preparar opcoes
        opcoes_contas = []
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            for conta in sintetico["contas"]:
                opcoes_contas.append("{} - {}".format(conta['codigo'], conta['nome']))

        df_display_edit = st.session_state['df_transacoes_editado'].copy()
        if 'conta_display' not in df_display_edit.columns:
            df_display_edit = enriquecer_com_plano_contas(df_display_edit)

        # se extrato_id existe, inclui na edição (nada impede leitura)
        columns_for_editor = ['data', 'descricao', 'valor', 'tipo_movimentacao', 'conta_display', 'nome_conta', 'tipo_fluxo']
        if 'extrato_id' in df_display_edit.columns:
            columns_for_editor.append('extrato_id')

        with st.expander("Editar Transações", expanded=True):
            edited_df = st.data_editor(
                df_display_edit[columns_for_editor],
                width='stretch',
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                    "descricao": st.column_config.TextColumn("Descrição", width="large"),
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                    "tipo_movimentacao": st.column_config.SelectboxColumn("Tipo", options=["CREDITO", "DEBITO"], required=True),
                    "conta_display": st.column_config.SelectboxColumn("Conta (código - nome)", options=opcoes_contas, required=True, help="Selecione a conta no formato código - nome"),
                    "nome_conta": st.column_config.TextColumn("Nome da Conta", disabled=True),
                    "tipo_fluxo": st.column_config.TextColumn("Tipo de Fluxo", disabled=True),
                },
                num_rows="dynamic",
                key="data_editor_transacoes"
            )

        if st.button("Confirmar Dados e Salvar no Banco de Dados", key="generate_report_btn"):
            try:
                # extrair conta_analitica
                if 'conta_display' in edited_df.columns:
                    edited_df['conta_analitica'] = edited_df['conta_display'].apply(lambda x: x.split(' - ')[0].strip() if isinstance(x, str) and ' - ' in x else x)

                # reenriquecer
                edited_df = enriquecer_com_plano_contas(edited_df)

                # preparar para salvar
                df_to_save = edited_df.copy()
                df_to_save["data"] = pd.to_datetime(df_to_save["data"], errors="coerce").dt.strftime("%Y-%m-%d")
                df_to_save["valor"] = pd.to_numeric(df_to_save["valor"], errors="coerce").fillna(0)

                # colunas válidas (preservar extrato_id se presente)
                colunas_validas = ["data", "descricao", "valor", "tipo_movimentacao", "conta_analitica"]
                if 'extrato_id' in df_to_save.columns:
                    colunas_validas.append('extrato_id')
                df_to_save = df_to_save[colunas_validas]

                # delete old transactions of user
                try:
                    user_id = user.id if hasattr(user, "id") else user.get("id")
                    supabase.table("transacoes").delete().eq("user_id", user_id).execute()
                except Exception:
                    st.warning("Aviso: não foi possível deletar transações antigas no Supabase (verifique permissões). Prosseguindo para inserção.")

                # inserir novas transacoes (mantendo extrato_id)
                records = df_to_save.to_dict(orient="records")
                for rec in records:
                    rec["user_id"] = user_id
                    if "extrato_id" not in rec:
                        rec["extrato_id"] = None
                try:
                    supabase.table("transacoes").insert(records).execute()
                except Exception as e:
                    st.error(f"Erro ao inserir transações no Supabase: {e}")
                    if st.secrets.get("DEBUG", False):
                        st.code(traceback.format_exc())
                    raise

                st.session_state['df_transacoes_editado'] = edited_df
                st.success("Transações revisadas salvas com sucesso no banco de dados! Agora você pode acessar Dashboard & Relatórios.")
            except Exception as e:
                st.error(f"Erro ao confirmar e salvar: {e}")
                if st.secrets.get("DEBUG", False):
                    st.code(traceback.format_exc())
    else:
        st.warning("Nenhum dado processado encontrado. Volte para a seção 'Upload e Extração'.")

# --------------------------
# 3. Dashboard & Relatórios
# --------------------------
elif page == "Dashboard & Relatórios":
    st.markdown("### 3. Relatórios Gerenciais e Dashboard")
    st.markdown("Selecione o período para gerar os relatórios e dashboard:")

    col1, col2 = st.columns(2)
    with col1:
        data_inicial_str = st.text_input("Data Inicial (DD/MM/AAAA)", "")
    with col2:
        data_final_str = st.text_input("Data Final (DD/MM/AAAA)", "")

    if st.button("Gerar Relatórios e Dashboard"):
        try:
            data_inicial = pd.to_datetime(data_inicial_str, format='%d/%m/%Y', errors='coerce')
            data_final = pd.to_datetime(data_final_str, format='%d/%m/%Y', errors='coerce')

            if pd.isna(data_inicial) or pd.isna(data_final):
                st.error("Formato de data inválido. Use DD/MM/AAAA.")
            else:
                data_inicial_iso = data_inicial.strftime('%Y-%m-%d')
                data_final_iso = data_final.strftime('%Y-%m-%d')
                user_id = user.id if hasattr(user, "id") else user.get("id")
                resultado = supabase.table("transacoes").select("*").eq("user_id", user_id).gte("data", data_inicial_iso).lte("data", data_final_iso).execute()
                resultado_data = getattr(resultado, "data", resultado)
                if not resultado_data:
                    st.warning("Nenhuma transação encontrada no período selecionado.")
                else:
                    df_relatorio = pd.DataFrame(resultado_data)
                    df_relatorio["data"] = pd.to_datetime(df_relatorio["data"], errors="coerce")
                    df_relatorio["valor"] = pd.to_numeric(df_relatorio["valor"], errors="coerce").fillna(0)
                    df_relatorio = enriquecer_com_plano_contas(df_relatorio)
                    st.session_state['df_transacoes_editado'] = df_relatorio.copy()
                    st.success(f"{len(df_relatorio)} transações carregadas para o período selecionado.")
        except Exception as e:
            st.error(f"Erro ao gerar relatórios: {e}")
            if st.secrets.get("DEBUG", False):
                st.code(traceback.format_exc())

    if not st.session_state.get('df_transacoes_editado', pd.DataFrame()).empty:
        df_final = st.session_state['df_transacoes_editado'].copy()
        try:
            secao_relatorios_dashboard(df_final, PLANO_DE_CONTAS)
        except Exception as e:
            st.error(f"Erro ao gerar relatórios/ dashboard: {e}")
            if st.secrets.get("DEBUG", False):
                st.code(traceback.format_exc())
    else:
        st.info("Nenhum dado disponível. Faça upload de extratos na seção 'Upload e Extração' ou carregue transações do banco.")

# --- Footer ---
st.markdown("---")
try:
    footer_logo = Image.open(LOGO_FILENAME)
    footer_col1, footer_col2 = st.columns([1, 35])
    with footer_col1:
        st.image(footer_logo, width=40)
    with footer_col2:
        st.markdown("""<p style="font-size: 0.9rem; color: #6c757d; margin: 0;">
        Análise de Extrato Empresarial | Dados extraídos e classificados com IA.
        </p>""", unsafe_allow_html=True)
except Exception:
    st.markdown("""<p style="font-size: 0.9rem; color: #6c757d; margin: 0;">
    Análise de Extrato Empresarial | Dados extraídos e classificados com IA.
    </p>""", unsafe_allow_html=True)

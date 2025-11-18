# app_supabase.py (salve como aicodetest_final.py)
import streamlit as st
import pandas as pd
import json
import io
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from google import genai
from google.genai import types
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
import traceback
import math

# Inserções para Supabase / autenticação
from auth import login_page, logout, supabase
import hashlib
from datetime import datetime, timedelta

# Importar as funções de relatórios do novo arquivo
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
                {"codigo": "OP-07", "nome": "Despesas Pessoais Misturadas"},
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
                {"codigo": "FIN-05", "nome": "Retirada de Sócios / Pró-labore"}
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

# --- 1. CONFIGURAÇÃO DE SEGURANÇA E TEMA ---
PRIMARY_COLOR = "#0A2342"
SECONDARY_COLOR = "#000000"
BACKGROUND_COLOR = "#F0F2F6"
ACCENT_COLOR = "#007BFF"
NEGATIVE_COLOR = "#DC3545"
FINANCING_COLOR = "#FFC107"
INVESTMENT_COLOR = "#28A745"
REPORT_BACKGROUND = "#F9F5EB"

LOGO1_FILENAME = "FinanceAI_1.png"

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="logo_hedgewise.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Forçar modo claro
st.markdown(
    """
    <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {
            background-color: #F0F2F6 !important;
            color: #000000 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
        }
        @media (prefers-color-scheme: dark) {
            html {
                color-scheme: light !important;
        }
        }
    </style>
    """,
    unsafe_allow_html=True
)

# CSS customizado
st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: {BACKGROUND_COLOR};
        }}
        .stButton>button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border-radius: 5px;
            padding: 10px 20px;
            border: none;
            font-weight: bold;
        }}
        .stButton>button:hover {{
            background-color: {ACCENT_COLOR};
            color: white;
        }}
        .stTextInput>div>div>input, .stDateInput>div>div>input {{
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
            border-radius: 5px;
        }}
        .report-box {{
            background-color: {REPORT_BACKGROUND};
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #DDDDDD;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        .fluxo-table .dataframe {{
            font-size: 14px;
        }}
        .main-header {{
            font-size: 2.5em;
            font-weight: bold;
            color: {PRIMARY_COLOR};
            margin-top: 0.5em;
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# --- MODELOS DE DADOS (PYDANTIC) ---
class Transacao(BaseModel):
    data: str = Field(..., description="Data da transação no formato AAAA-MM-DD.")
    descricao: str = Field(..., description="Descrição da transação.")
    valor: float = Field(..., description="Valor da transação, sempre positivo.")
    tipo_movimentacao: str = Field(..., description="Tipo de movimentação: DEBITO ou CREDITO.")
    conta_analitica: str = Field(..., description="Código da conta analítica do plano de contas (ex: OP-01, FIN-05). Use NE-02 para transações não classificadas.")

class AnaliseCompleta(BaseModel):
    transacoes: List[Transacao]
    saldo_final: Optional[float] = Field(None, description="Saldo final do extrato, se disponível.")

# --- FUNÇÕES AUXILIARES ---

# --- FUNÇÃO DE FORMATAÇÃO BRL ---
def formatar_brl(valor: float) -> str:
    """Formata um valor float para a moeda Real Brasileiro (R$ xx.xxx,xx)."""
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP_SEP").replace(".", ",").replace("TEMP_SEP", ".")
        return "R$ " + valor_brl
    except Exception:
        return f"R$ {valor:.2f}"

# --- FUNÇÃO PARA GERAR PROMPT COM PLANO DE CONTAS ---
def gerar_prompt_com_plano_contas() -> str:
    contas_str = "### PLANO DE CONTAS ###\n\n"
    
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        contas_str += f"{sintetico['codigo']} - {sintetico['nome']} (Tipo: {sintetico['tipo_fluxo']})\n"
        for conta in sintetico["contas"]:
            contas_str += f"  - {conta['codigo']}: {conta['nome']}\n"
        contas_str += "\n"
    
    prompt = f"""Você é um especialista em extração e classificação de dados financeiros.

{contas_str}

Extraia todas as transações deste extrato bancário em PDF e classifique cada transação de acordo com o PLANO DE CONTAS acima.

INSTRUÇÕES CRÍTICAS:
1. Use EXATAMENTE os códigos de conta analítica listados acima (ex: OP-01, OP-05, INV-01, FIN-05, etc.)
2. Analise cuidadosamente cada transação para determinar a conta mais apropriada.
3. Retiradas de sócios e pró-labore devem ser classificadas como FIN-05.
4. Receitas operacionais: OP-01 (vendas), OP-02 (serviços), OP-03 (outras).
5. Despesas operacionais: OP-04 (CMV), OP-05 (administrativas), OP-06 (comerciais), OP-08 (impostos), OP-09 (tarifas).
6. Investimentos: INV-01 (compra de ativos), INV-02 (aplicações), INV-03 (venda de ativos).
7. Financiamentos: FIN-01 (empréstimos recebidos), FIN-02 (pagamento de empréstimos), FIN-03 (juros).
8. IMPORTANTE — Transferências NEUTRAS (NE-01 ou NE-02): Use APENAS quando detectar uma saída de uma conta corrente E uma entrada de MESMO VALOR em outra conta no MESMO DIA. Caso contrário, classifique normalmente nas outras categorias.

Retorne um objeto JSON com o formato do schema indicado, usando valor POSITIVO para 'valor' e classificando como 'DEBITO' ou 'CREDITO'.
"""
    return prompt

# --- FUNÇÃO DE CHAMADA DA API PARA EXTRAÇÃO ---
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
        # A chave 'client' é passada, mas a inicialização do cliente deve ocorrer no escopo principal
        # ou ser resolvida pelo ambiente do Streamlit Cloud (secrets)
        # Assumindo que 'client' é uma instância válida de genai.Client
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
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
            st.info("Isso pode ocorrer quando a demanda na API está alta. Tente novamente em alguns minutos.")
        elif "Invalid API key" in error_message or "401" in error_message or "permission" in error_message.lower():
            st.error("Problema de autenticação com a Gemini API. Verifique a sua chave (GEMINI_API_KEY).")
        else:
            st.error(f"Ocorreu um erro ao processar '{filename}'. Verifique o arquivo e tente novamente.")
        return {
            'transacoes': [],
            'saldo_final': 0.0
        }

# --- FUNÇÃO PARA ENRIQUECER DADOS COM PLANO DE CONTAS ---
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

# --- FUNÇÃO DE CABEÇALHO ---
def load_header():
    try:
        logo = Image.open(LOGO1_FILENAME)
        col1, col2 = st.columns([2,5])
        with col1:
            st.image(logo, width=600)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("Traduzindo números em histórias que façam sentido...")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")

# --------------------------
# INTEGRAÇÃO DE AUTENTICAÇÃO
# --------------------------
# Impede acesso à app sem autenticação
if "user" not in st.session_state:
    login_page()
    st.stop()
else:
    user = st.session_state["user"]
    st.sidebar.write(f"Olá, {user.email}")
    if st.sidebar.button("Sair"):
        logout()

# Carrega cabeçalho (mantendo sua estrutura)
load_header()

st.sidebar.title("Navegação")
page = st.sidebar.radio("Seções:", ["Upload e Extração", "Revisão de Dados", "Dashboard & Relatórios"])

# A inicialização do cliente Gemini é feita no Streamlit Cloud via secrets.
# Se a variável de ambiente GEMINI_API_KEY estiver configurada, o cliente será inicializado automaticamente.
# Caso contrário, a função analisar_extrato irá lidar com o erro.
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    # Se a chave não estiver nos secrets, o erro será tratado na função analisar_extrato
    # ou o app irá parar se a chave for obrigatória.
    # Para manter a compatibilidade com o código original, vamos apenas inicializar o cliente.
    # Se a chave não estiver configurada, o erro será lançado na primeira chamada à API.
    pass

# ============================================
# 1. Upload e Extração (com integração Supabase) - CÓDIGO ORIGINAL
# ============================================
if page == "Upload e Extração":
    st.markdown("### 1. Upload e Extração de Dados")
    st.markdown("Faça o upload dos extratos em PDF. O sistema irá extrair as transações e classificá-las conforme o plano de contas.")

    with st.expander("Plano de Contas Utilizado", expanded=False):
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            st.markdown(f"**{sintetico['codigo']} - {sintetico['nome']}** ({sintetico['tipo_fluxo']})")
            for conta in sintetico["contas"]:
                st.markdown(f"  - `{conta['codigo']}`: {conta['nome']}")

    # BLOCO DE UPLOAD INTEGRADO
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
            extraction_status.info("Iniciando extração e classificação...")
            
            user_id = user.id
            for i, uploaded_file in enumerate(uploaded_files):
                extraction_status.info(f"Processando arquivo {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
                pdf_bytes = uploaded_file.getvalue()

                # calcula hash e verifica duplicidade
                file_hash = hashlib.sha256(pdf_bytes).hexdigest()
                existente = supabase.table("extratos").select("*").eq("hash_arquivo", file_hash).execute()
                if existente.data:
                    extraction_status.warning(f"O arquivo {uploaded_file.name} já foi enviado anteriormente. Pulando.")
                    continue

                # opcional: salva o PDF no Storage (pasta por usuário)
                try:
                    supabase.storage.from_("extratos").upload(f"{user_id}/{uploaded_file.name}", pdf_bytes)
                except Exception:
                    pass

                # registra metadados do extrato
                resultado = supabase.table("extratos").insert({
                    "user_id": user_id,
                    "nome_arquivo": uploaded_file.name,
                    "hash_arquivo": file_hash
                }).execute()
                extrato_id = resultado.data[0]["id"] if resultado.data else None

                # chama a função que usa Gemini / extração
                dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name, client)
                transacoes = dados_dict.get('transacoes', [])
                todas_transacoes.extend(transacoes)

            df_transacoes = pd.DataFrame(todas_transacoes)

            if df_transacoes.empty:
                extraction_status.error("Nenhuma transação válida foi extraída. Verifique se o PDF contém texto legível e se o arquivo não está corrompido.")
                st.session_state['df_transacoes_editado'] = pd.DataFrame()
            else:
                extraction_status.success(f"Extração de {len(todas_transacoes)} transações concluída!")

                df_transacoes['valor'] = pd.to_numeric(df_transacoes['valor'], errors='coerce').fillna(0)
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'], errors='coerce', dayfirst=True)
                df_transacoes['tipo_movimentacao'] = df_transacoes['tipo_movimentacao'].fillna('DEBITO')
                df_transacoes['conta_analitica'] = df_transacoes['conta_analitica'].fillna('NE-02')

                df_transacoes = enriquecer_com_plano_contas(df_transacoes)

                st.session_state['df_transacoes_editado'] = df_transacoes
                st.success("Dados carregados e classificados. Você pode revisar as entradas na seção 'Revisão de Dados'.")

    # Listagem de extratos já carregados
    st.subheader("Extratos já carregados")
    try:
        extratos_existentes = supabase.table("extratos").select("id, nome_arquivo, criado_em").eq("user_id", user.id).order("criado_em", desc=True).execute()
        if not extratos_existentes.data:
            st.info("Nenhum extrato carregado ainda.")
        else:
            df_extratos = pd.DataFrame(extratos_existentes.data)
            df_extratos["criado_em"] = pd.to_datetime(df_extratos["criado_em"]).dt.strftime("%d/%m/%Y %H:%M")
            st.dataframe(df_extratos, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao buscar extratos: {e}")

# =========================
# 2. Revisão de Dados
# =========================
elif page == "Revisão de Dados":
    st.markdown("### 2. Revisão e Correção Manual dos Dados")
    
    if not st.session_state.get('df_transacoes_editado', pd.DataFrame()).empty:
        st.info("Revise as classificações e corrija manualmente qualquer erro.")
        
        opcoes_contas = []
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            for conta in sintetico["contas"]:
                opcoes_contas.append(f"{conta['codigo']} - {conta['nome']}")
        
        # Garante que a coluna 'conta_display' exista para o editor
        df_display_edit = st.session_state['df_transacoes_editado'].copy()
        if 'conta_display' not in df_display_edit.columns:
             df_display_edit = enriquecer_com_plano_contas(df_display_edit)

        with st.expander("Editar Transações", expanded=True):
            edited_df = st.data_editor(
                df_display_edit[['data', 'descricao', 'valor', 'tipo_movimentacao', 'conta_display', 'nome_conta', 'tipo_fluxo']],
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
        
        if st.button("Confirmar Dados e Gerar Relatórios", key="generate_report_btn"):
            try:
                # 1. Ajustar conta_analitica a partir da coluna conta_display
                if 'conta_display' in edited_df.columns:
                    edited_df['conta_analitica'] = edited_df['conta_display'].apply(
                        lambda x: x.split(' - ')[0].strip() if isinstance(x, str) and ' - ' in x else x
                     )
            
                # 2. Reenriquecer com plano de contas
                edited_df = enriquecer_com_plano_contas(edited_df)

                # 3. Preparar DataFrame para inserir no Supabase
                df_to_save = edited_df.copy()
                df_to_save["data"] = pd.to_datetime(df_to_save["data"], errors="coerce").dt.strftime("%Y-%m-%d")
                df_to_save["valor"] = pd.to_numeric(df_to_save["valor"], errors="coerce").fillna(0)

                # 4. Remover colunas desnecessárias antes de salvar
                colunas_validas = ["data", "descricao", "valor", "tipo_movimentacao", "conta_analitica"]
                df_to_save = df_to_save[colunas_validas]

                # 5. Deletar transações anteriores do usuário
                supabase.table("transacoes").delete().eq("user_id", user.id).execute()

                # 6. Inserir as novas transações no Supabase
                records = df_to_save.to_dict(orient="records")
                for rec in records:
                    rec["user_id"] = user.id
                    rec["extrato_id"] = None  # opcional, caso você use depois
                supabase.table("transacoes").insert(records).execute()

                # 7. Salvar no session_state
                st.session_state['df_transacoes_editado'] = edited_df

                st.success("Transações revisadas salvas com sucesso no banco de dados! Agora você pode acessar Dashboard & Relatórios.")

            except Exception as e:
                st.error(f"Erro ao salvar transações no Supabase: {e}")

# =========================
# 3. Dashboard & Relatórios
# =========================
elif page == "Dashboard & Relatórios":
    st.markdown("### 3. Relatórios Gerenciais e Dashboard")
    
    st.markdown("#### Selecione o período para gerar os relatórios e dashboards:")
    
    # --- Interface de seleção de data aprimorada (do refactored) ---
    col1, col2 = st.columns(2)
    with col1:
        data_inicial_str = st.text_input("Data Inicial (DD/MM/AAAA)", "")
    with col2:
        data_final_str = st.text_input("Data Final (DD/MM/AAAA)", "")

    if st.button("Gerar Relatórios e Dashboard"):
        try:
            # Conversão das datas com validação
            data_inicial = pd.to_datetime(data_inicial_str, format='%d/%m/%Y', errors='coerce')
            data_final = pd.to_datetime(data_final_str, format='%d/%m/%Y', errors='coerce')

            if pd.isna(data_inicial) or pd.isna(data_final):
                st.error("Formato de data inválido. Use DD/MM/AAAA.")
            else:
                # O Supabase espera o formato ISO (AAAA-MM-DD) para a consulta
                data_inicial_iso = data_inicial.strftime('%Y-%m-%d')
                data_final_iso = data_final.strftime('%Y-%m-%d')
                
                resultado = supabase.table("transacoes").select("*").eq("user_id", user.id).gte("data", data_inicial_iso).lte("data", data_final_iso).execute()
                if not resultado.data:
                    st.warning("Nenhuma transação encontrada no período selecionado.")
                else:
                    df_relatorio = pd.DataFrame(resultado.data)
                    # A coluna 'data' do Supabase é string, precisa ser convertida para datetime
                    df_relatorio["data"] = pd.to_datetime(df_relatorio["data"], errors="coerce")
                    df_relatorio["valor"] = pd.to_numeric(df_relatorio["valor"], errors="coerce").fillna(0)
                    df_relatorio = enriquecer_com_plano_contas(df_relatorio)
                    
                    st.session_state['df_transacoes_editado'] = df_relatorio.copy()
                    st.success(f"{len(df_relatorio)} transações carregadas para o período selecionado.")
        except Exception as e:
            st.error(f"Erro ao gerar relatórios: {e}")

    # Se há dados no estado (carregados por upload ou por consulta), use-os
    if not st.session_state.get('df_transacoes_editado', pd.DataFrame()).empty:
        df_final = st.session_state['df_transacoes_editado'].copy()
        # Chama a função refatorada do reports_functions.py
        secao_relatorios_dashboard(df_final, PLANO_DE_CONTAS)
    else:
        st.info("Nenhum dado disponível. Faça upload de extratos na seção 'Upload e Extração' ou use o filtro para carregar transações previamente enviadas.")

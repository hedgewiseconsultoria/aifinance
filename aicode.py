import streamlit as st
import pandas as pd
import json
import io
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai
from google.genai import types
import altair as alt
import plotly.express as px
import numpy as np

# --- PLANO DE CONTAS (JSON) INTEGRADO ---
PLANO_DE_CONTAS = {
    "plano_de_contas": [
        {"codigo": "1", "nome": "Entradas Operacionais", "tipo_fluxo": "operacional", "contas": [
            {"codigo": "1.1", "nome": "Receitas de Vendas"},
            {"codigo": "1.2", "nome": "Receitas de Servicos"},
            {"codigo": "1.3", "nome": "Outras Receitas Operacionais"}
        ]},
        {"codigo": "2", "nome": "Saidas Operacionais", "tipo_fluxo": "operacional", "contas": [
            {"codigo": "2.1", "nome": "Custos de Mercadorias Vendidas (CMV)"},
            {"codigo": "2.2", "nome": "Despesas Administrativas"},
            {"codigo": "2.3", "nome": "Despesas Comerciais"},
            {"codigo": "2.4", "nome": "Despesas Pessoais Misturadas"},
            {"codigo": "2.5", "nome": "Impostos e Contribuicoes"},
            {"codigo": "2.6", "nome": "Tarifas Bancarias e Servicos"}
        ]},
        {"codigo": "3", "nome": "Atividades de Investimento", "tipo_fluxo": "investimento", "contas": [
            {"codigo": "3.1", "nome": "Aquisicao de Imobilizado"},
            {"codigo": "3.2", "nome": "Aplicacoes Financeiras"},
            {"codigo": "3.3", "nome": "Alienacao de Ativos"}
        ]},
        {"codigo": "4", "nome": "Atividades de Financiamento", "tipo_fluxo": "financiamento", "contas": [
            {"codigo": "4.1", "nome": "Emprestimos Recebidos"},
            {"codigo": "4.2", "nome": "Pagamento de Emprestimos"},
            {"codigo": "4.3", "nome": "Juros sobre Emprestimos e Financiamentos"},
            {"codigo": "4.4", "nome": "Aporte de Socios"},
            {"codigo": "4.5", "nome": "Retirada de Socios / Pro-labore"}
        ]},
        {"codigo": "5", "nome": "Ajustes e Transferencias Internas", "tipo_fluxo": "neutro", "contas": [
            {"codigo": "5.1", "nome": "Transferencias entre Contas"},
            {"codigo": "5.2", "nome": "Ajustes e Estornos"}
        ]}
    ]
}

# --- FUNÇÃO DE FORMATAÇÃO BRL ---
def formatar_brl(valor: float) -> str:
    valor_us = f"{valor:,.2f}"
    valor_brl = valor_us.replace(",", "TEMP_SEP").replace(".", ",").replace("TEMP_SEP", ".")
    return "R$ " + valor_brl

# --- 1. CONFIGURAÇÃO DE SEGURANÇA E TEMA ---
PRIMARY_COLOR = "#0A2342"
SECONDARY_COLOR = "#000000"
BACKGROUND_COLOR = "#F0F2F6"
ACCENT_COLOR = "#007BFF"
NEGATIVE_COLOR = "#DC3545"
FINANCING_COLOR = "#FFC107"
REPORT_BACKGROUND = "#F9F5EB"
LOGO_FILENAME = "logo_hedgewise.png"

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="logo_hedgewise.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# (CSS igual ao original) - mantido
st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: {BACKGROUND_COLOR};
        }}
        [data-testid="stSidebar"] {{
            background-color: white;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        [data-testid="stSidebar"] .stButton>button {{
            width: 100%;
            margin-bottom: 10px;
        }}
        .main-header {{
            color: {SECONDARY_COLOR};
            font-size: 2.5em;
            padding-bottom: 10px;
        }}
        .kpi-container {{
            background-color: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 6px 15px 0 rgba(0, 0, 0, 0.08);
            margin-bottom: 20px;
            height: 100%;
        }}
        [data-testid="stMetricLabel"] label {{
            font-weight: 600 !important;
            color: #6c757d;
        }}
        [data-testid="stMetricValue"] {{
            font-size: 1.8em !important;
            color: {SECONDARY_COLOR};
        }}
        button[data-baseweb="tab"] {{
            color: #6c757d;
            border-bottom: 2px solid transparent;
            font-weight: 600;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {PRIMARY_COLOR};
            border-bottom: 3px solid {PRIMARY_COLOR} !important;
        }}
        h2 {{
            color: {PRIMARY_COLOR};
            border-left: 5px solid {PRIMARY_COLOR};
            padding-left: 10px;
            margin-top: 20px;
            margin-bottom: 20px;
        }}
        .stButton>button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            border: none;
            transition: background-color 0.3s, transform 0.2s;
        }}
        .stButton>button:hover {{
            background-color: #1C3757;
            color: white;
            transform: scale(1.05);
        }}
        .report-textarea, .report-textarea > div, .report-textarea textarea {{
            background-color: {REPORT_BACKGROUND} !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
            font-family: Roboto, sans-serif !important;
            font-size: 1.0em !important;
            color: {SECONDARY_COLOR} !important;
            border: 1px solid #ddd !important;
        }}
        .context-input > div, .context-input > div > textarea {{
            background-color: white !important;
            color: {SECONDARY_COLOR} !important;
            border: 1px solid #ddd !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
        }}
        .stPlotlyChart {{
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    """,
    unsafe_allow_html=True
)

# Inicializa o estado da sessão (mantém chaves originais)
if 'df_transacoes_editado' not in st.session_state:
    st.session_state['df_transacoes_editado'] = pd.DataFrame()
if 'relatorio_consolidado' not in st.session_state:
    st.session_state['relatorio_consolidado'] = "Aguardando análise de dados..."
if 'contexto_adicional' not in st.session_state:
    st.session_state['contexto_adicional'] = ""

# Inicializa o cliente Gemini
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except (KeyError, AttributeError):
    st.error("ERRO: Chave 'GEMINI_API_KEY' não encontrada. Configure-a para rodar a aplicação.")
    st.stop()

# --- 2. DEFINIÇÃO DO SCHEMA PYDANTIC (mantido) ---
class Transacao(BaseModel):
    data: str = Field(description="A data da transacao no formato 'DD/MM/AAAA'.")
    descricao: str = Field(description="Descricao detalhada da transacao.")
    valor: float = Field(description="O valor numerico da transacao. Sempre positivo.")
    tipo_movimentacao: str = Field(description="Classificacao da movimentacao: 'DEBITO' ou 'CREDITO'.")
    categoria_sugerida: str = Field(description="Sugestao de categoria mais relevante.")
    categoria_dcf: str = Field(description="Classificacao DCF: 'OPERACIONAL', 'INVESTIMENTO' ou 'FINANCIAMENTO'.")
    entidade: str = Field(description="Classificacao binaria: 'EMPRESARIAL' ou 'PESSOAL'.")

class AnaliseCompleta(BaseModel):
    transacoes: List[Transacao] = Field(description="Lista de transacoes extraidas do documento.")
    relatorio_inicial: str = Field(description="Confirmacao de extracao dos dados deste extrato.")
    saldo_final: float = Field(description="O saldo final da conta no extrato.")

# --- 3. FUNÇÃO DE CHAMADA DA API PARA EXTRAÇÃO (ajustada para fornecer plano de contas) ---
@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    # Inclui o plano de contas no prompt para orientar a classificacao
    plano_str = json.dumps(PLANO_DE_CONTAS, ensure_ascii=False)
    prompt_analise = (
        f"Voce e um especialista em extracao e classificacao de dados financeiros. "
        f"Extraia todas as transacoes deste extrato bancario em PDF ('{filename}') e classifique cada transacao nas categorias 'categoria_dcf' (OPERACIONAL, INVESTIMENTO, FINANCIAMENTO) "
        "e 'entidade' (EMPRESARIAL ou PESSOAL). A seguir esta o plano de contas que voce deve usar como referencia para classificar (nao altere os codigos):\n"
        f"{plano_str}\n"
        "Preencha a estrutura JSON rigorosamente. Use valor POSITIVO para 'valor' e classifique estritamente como 'DEBITO' ou 'CREDITO'."
    )
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AnaliseCompleta,
        temperature=0.2
    )
    try:
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
            st.error(f"⚠️ ERRO DE CAPACIDADE DA API: O modelo Gemini esta sobrecarregado (503 UNAVAILABLE) ao processar {filename}.")
            st.info("Este e um erro temporario do servidor da API. Por favor, tente novamente em alguns minutos.")
        else:
            print(f"Erro ao chamar a Gemini API para {filename}: {error_message}")
        return {
            'transacoes': [],
            'saldo_final': 0.0,
            'relatorio_inicial': f"**Falha na Extracao:** Ocorreu um erro ao processar o arquivo {filename}. Motivo: {error_message}"
        }

# --- 3.1. FUNCAO PARA GERAR RELATORIO MENSAL E INDICADORES ---
def gerar_relatorio_mensal_e_indicadores(df_transacoes: pd.DataFrame) -> dict:
    df = df_transacoes.copy()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df = df.dropna(subset=['data'])
    df['fluxo'] = df.apply(lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], axis=1)
    df['mes_ano'] = df['data'].dt.to_period('M').astype(str)

    # Agregar por mes e tipo DCF
    agregados = df.groupby(['mes_ano', 'categoria_dcf'])['fluxo'].sum().unstack(fill_value=0).reset_index()

    # Garantir colunas padrao
    for col in ['OPERACIONAL', 'INVESTIMENTO', 'FINANCIAMENTO']:
        if col not in agregados.columns:
            agregados[col] = 0.0

    # Entradas operacionais: somatorio de creditos operacionais (apenas creditos)
    entradas_operacionais = df[(df['categoria_dcf'] == 'OPERACIONAL') & (df['fluxo'] > 0)].groupby('mes_ano')['fluxo'].sum()
    entradas_operacionais = entradas_operacionais.reindex(agregados['mes_ano']).fillna(0).values

    operacional = agregados['OPERACIONAL'].values
    investimento = agregados['INVESTIMENTO'].values
    financiamento = agregados['FINANCIAMENTO'].values

    # Calculo dos indicadores (tratando divisao por zero)
    margem_operacional = np.where(entradas_operacionais != 0, operacional / entradas_operacionais, np.nan)
    intensidade_investimento = np.where(operacional != 0, investimento / operacional, np.nan)
    intensidade_financiamento = np.where(operacional != 0, financiamento / operacional, np.nan)

    indicadores = pd.DataFrame({
        'mes_ano': agregados['mes_ano'],
        'margem_operacional': margem_operacional,
        'intensidade_investimento': intensidade_investimento,
        'intensidade_financiamento': intensidade_financiamento
    })

    # Resumo consolidado para quick KPIs
    resumo = {
        'total_periodo': df['fluxo'].sum(),
        'operacional_total': df[df['categoria_dcf'] == 'OPERACIONAL']['fluxo'].sum(),
        'investimento_total': df[df['categoria_dcf'] == 'INVESTIMENTO']['fluxo'].sum(),
        'financiamento_total': df[df['categoria_dcf'] == 'FINANCIAMENTO']['fluxo'].sum(),
        'pessoal_total': df[df['entidade'] == 'PESSOAL']['fluxo'].sum()
    }

    return {
        'agregados': agregados,
        'indicadores': indicadores,
        'resumo': resumo
    }

# --- 3.2. FUNCAO DE GERAÇÃO DE RELATORIO CONSOLIDADO (AJUSTADA) ---
def gerar_relatorio_final_economico(df_transacoes: pd.DataFrame, contexto_adicional: str, client: genai.Client) -> str:
    # Calcula relatorio mensal e indicadores localmente e inclui no prompt para a IA
    rel_mensal = gerar_relatorio_mensal_e_indicadores(df_transacoes)
    agregados = rel_mensal['agregados']
    indicadores = rel_mensal['indicadores']
    resumo = rel_mensal['resumo']

    # Construi um sumario sintetico para passar ao modelo
    linhas_ag = []
    for _, row in agregados.iterrows():
        linhas_ag.append(f"{row['mes_ano']}: OPERACIONAL={row.get('OPERACIONAL',0):.2f}, INVESTIMENTO={row.get('INVESTIMENTO',0):.2f}, FINANCIAMENTO={row.get('FINANCIAMENTO',0):.2f}")
    resumo_text = "\n".join(linhas_ag)

    # Construcao do prompt (mais orientado a evolucao e indicadores)
    contexto_prompt = (f"\n\n--- CONTEXTO ADICIONAL DO EMPREENDEDOR ---\n{contexto_adicional}\n--- FIM DO CONTEXTO ---\n") if contexto_adicional else ""

    prompt_analise = (
        "Voce e um consultor financeiro especializado em PMEs. Abaixo segue um resumo sintetico do fluxo de caixa por mes (OPERACIONAL, INVESTIMENTO, FINANCIAMENTO). "
        "Calcule tendencias, variações mensais e interprete os seguintes indicadores por mes: margem_operacional (OPERACIONAL/Entradas Operacionais), "
        "intensidade_investimento (INVESTIMENTO/OPERACIONAL) e intensidade_financiamento (FINANCIAMENTO/OPERACIONAL). "
        "Retorne um relatorio conciso e acionavel (max 220 palavras) com: 1) resumo de tendencia, 2) pontos de alerta, 3) 3 acoes praticas priorizadas. "
        f"\n\nDADOS_SINTETICOS:\n{resumo_text}\n\nINDICADORES_POR_MES:\n{indicadores.to_csv(index=False)}{contexto_prompt}"
    )

    config = types.GenerateContentConfig(temperature=0.4)
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt_analise],
            config=config,
        )
        # Retorna o texto diretamente
        return response.text
    except Exception as e:
        return f"**Falha na Geracao do Relatorio Consolidado:** Ocorreu um erro ao gerar o relatório analitico. Motivo: {e}"

# --- 4. FUNCAO DE CABECALHO (mantida) ---
def load_header():
    try:
        logo = Image.open(LOGO_FILENAME)
        col1, col2 = st.columns([1, 10])
        with col1:
            st.image(logo, width=120)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("O horizonte do pequeno empreendedor")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")

# --- 5. FUNCAO PARA CRIAR GRÁFICOS DO DASHBOARD (AJUSTADA PARA INCLUIR GRAFICO DE INDICADORES) ---
def criar_dashboard(df: pd.DataFrame):
    st.subheader("Dashboard: Análise de Fluxo de Caixa")
    if df.empty:
        st.info("Nenhum dado disponivel para o dashboard. Por favor, analise e confirme as transacoes na aba anterior.")
        return

    try:
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
        df.dropna(subset=['data'], inplace=True)
        df['fluxo'] = df.apply(lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], axis=1)
        df['mes_ano'] = df['data'].dt.to_period('M').astype(str)

        # Gerar relatorio mensal e indicadores
        rel = gerar_relatorio_mensal_e_indicadores(df)
        agregados = rel['agregados']
        indicadores = rel['indicadores']

        # 1) Tabela mes a mes (sintetica)
        st.markdown("### Demonstracao Mensal - Sintetica (por Grupo)")
        st.dataframe(agregados.style.format({
            'OPERACIONAL': '{:,.2f}', 'INVESTIMENTO': '{:,.2f}', 'FINANCIAMENTO': '{:,.2f}'
        }), use_container_width=True)

        # 2) Grafico de barras: Fluxo por DCF (mensal)
        st.markdown("### Comparativo Mensal de Fluxo de Caixa pelo Metodo DCF com Retiradas Pessoais")
        df_dcf_agrupado = df.groupby(['mes_ano', 'categoria_dcf'])['fluxo'].sum().reset_index()
        df_pessoal = df[df['entidade'] == 'PESSOAL'].groupby('mes_ano')['fluxo'].sum().reset_index()
        df_pessoal['categoria_dcf'] = 'PESSOAL'
        df_combinado = pd.concat([df_dcf_agrupado, df_pessoal], ignore_index=True)

        fig_dcf = px.bar(
            df_combinado,
            x='mes_ano',
            y='fluxo',
            color='categoria_dcf',
            barmode='group',
            title='Fluxo de Caixa por DCF e Retiradas Pessoais',
            labels={'fluxo': 'Fluxo (R$)', 'mes_ano': 'Mês/Ano', 'categoria_dcf': 'Categoria'},
            color_discrete_map={
                'OPERACIONAL': ACCENT_COLOR,
                'INVESTIMENTO': PRIMARY_COLOR,
                'FINANCIAMENTO': FINANCING_COLOR,
                'PESSOAL': NEGATIVE_COLOR
            }
        )
        fig_dcf.update_layout(height=420, plot_bgcolor='white', font=dict(family="Roboto"))
        st.plotly_chart(fig_dcf, use_container_width=True)

        # 3) Grafico de indicadores (linhas)
        st.markdown("### Evolucao Mensal dos Indicadores")
        indicadores_plot = indicadores.copy()
        # Converte para porcentagem para exibir (multiplica por 100)
        indicadores_plot['margem_operacional_pct'] = indicadores_plot['margem_operacional'] * 100
        indicadores_plot['intensidade_investimento_pct'] = indicadores_plot['intensidade_investimento'] * 100
        indicadores_plot['intensidade_financiamento_pct'] = indicadores_plot['intensidade_financiamento'] * 100

        fig_ind = px.line(
            indicadores_plot.melt(id_vars='mes_ano', value_vars=['margem_operacional_pct','intensidade_investimento_pct','intensidade_financiamento_pct'], var_name='indicador', value_name='valor_pct'),
            x='mes_ano', y='valor_pct', color='indicador', markers=True,
            title='Indicadores Financeiros (% )', labels={'valor_pct':'Percentual (%)', 'mes_ano':'Mês/Ano', 'indicador':'Indicador'}
        )
        fig_ind.update_layout(height=360, plot_bgcolor='white', font=dict(family="Roboto"))
        st.plotly_chart(fig_ind, use_container_width=True)

        st.caption("Margem Operacional = OPERACIONAL / Entradas Operacionais. Intensidade_investimento = INVESTIMENTO / OPERACIONAL. Intensidade_financiamento = FINANCIAMENTO / OPERACIONAL.")

        # 4) Pie chart para distribuicao de despesas (mantido)
        st.markdown("### Distribuicao de Despesas por Categoria Sugerida")
        df_despesas = df[df['tipo_movimentacao'] == 'DEBITO'].groupby('categoria_sugerida')['valor'].sum().reset_index()
        if not df_despesas.empty:
            fig_pie = px.pie(
                df_despesas,
                values='valor',
                names='categoria_sugerida',
                title='Distribuicao de Despesas',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_layout(height=400, font=dict(family="Roboto"))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Nenhuma despesa encontrada para distribuicao.")

    except Exception as e:
        import traceback
        st.error(f"Erro ao gerar o dashboard: {e}")
        st.code(f"Detalhes do erro:\n{traceback.format_exc()}")

# --- 6. INTERFACE STREAMLIT PRINCIPAL (mantida com pequenos ajustes) ---
load_header()

st.sidebar.title("Navegacao")
page = st.sidebar.radio("Secoes", ["Upload e Extracao", "Revisao de Dados", "Dashboard & Relatorios"])

if page == "Upload e Extracao":
    st.markdown("### 1. Upload e Extracao de Dados")
    st.markdown("Faça o upload dos extratos em PDF. O sistema ira extrair as transacoes e classificalas.")

    with st.expander("Upload de Arquivos", expanded=True):
        col_upload, col_contexto = st.columns([1, 1])
        with col_upload:
            uploaded_files = st.file_uploader(
                "Selecione os arquivos PDF dos seus extratos bancarios",
                type="pdf",
                accept_multiple_files=True,
                key="pdf_uploader",
                help="Os PDFs devem ter texto selecionavel. Você pode selecionar múltiplos arquivos para uma analise consolidada."
            )
        with col_contexto:
            st.markdown('<div class="context-input">', unsafe_allow_html=True)
            contexto_adicional_input = st.text_area(
                "2. Contexto Adicional para a Analise (Opcional)",
                value=st.session_state.get('contexto_adicional', ''),
                placeholder="Ex: 'Todos os depositos em dinheiro (cash) sao provenientes de vendas diretas.'",
                key="contexto_input",
                help="Use este campo para fornecer a IA informacoes contextuais que nao estao nos extratos."
            )
            st.markdown('</div>', unsafe_allow_html=True)

    if contexto_adicional_input != st.session_state.get('contexto_adicional', ''):
        st.session_state['contexto_adicional'] = contexto_adicional_input

    if uploaded_files:
        if st.button(f"3. Executar Extracao e Classificacao ({len(uploaded_files)} arquivos)", key="analyze_btn"):
            todas_transacoes = []
            saldos_finais = 0.0
            extraction_status = st.status("Iniciando extracao e classificacao...", expanded=True)
            for i, uploaded_file in enumerate(uploaded_files):
                extraction_status.write(f"Extraindo dados do arquivo {i+1} de {len(uploaded_files)}: **{uploaded_file.name}**")
                pdf_bytes = uploaded_file.getvalue()
                with extraction_status:
                    dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name, client)
                todas_transacoes.extend(dados_dict['transacoes'])
                saldos_finais += dados_dict.get('saldo_final', 0.0)
            df_transacoes = pd.DataFrame(todas_transacoes)
            if df_transacoes.empty:
                extraction_status.error("❌ Nenhuma transacao valida foi extraida. Verifique as mensagens de erro acima.")
                st.session_state['df_transacoes_editado'] = pd.DataFrame()
            else:
                extraction_status.update(label=f"✅ Extracao de {len(todas_transacoes)} transacoes concluida!", state="complete", expanded=False)
                df_transacoes['valor'] = pd.to_numeric(df_transacoes['valor'], errors='coerce').fillna(0)
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'], errors='coerce', dayfirst=True)
                df_transacoes['tipo_movimentacao'] = df_transacoes['tipo_movimentacao'].fillna('DEBITO')
                df_transacoes['entidade'] = df_transacoes['entidade'].fillna('EMPRESARIAL')
                df_transacoes['categoria_dcf'] = df_transacoes['categoria_dcf'].fillna('OPERACIONAL')
                st.session_state['df_transacoes_editado'] = df_transacoes
                st.session_state['saldos_finais'] = saldos_finais
                st.session_state['relatorio_consolidado'] = "Aguardando geracao do relatorio..."
                st.rerun()

elif page == "Revisao de Dados":
    st.markdown("### 4. Revisao e Correcao Manual dos Dados")
    if not st.session_state['df_transacoes_editado'].empty:
        st.info("⚠️ **IMPORTANTE:** Revise as colunas **'Entidade'** (Empresarial/Pessoal) e **'Classificacao DCF'** e corrija manualmente qualquer erro.")
        with st.expander("Editar Transacoes", expanded=True):
            edited_df = st.data_editor(
                st.session_state['df_transacoes_editado'],
                width='stretch',
                column_config={
                    "data": st.column_config.DateColumn("Data", format="YYYY-MM-DD", required=True),
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %0.2f", required=True),
                    "tipo_movimentacao": st.column_config.SelectboxColumn("Tipo", options=["CREDITO", "DEBITO"], required=True),
                    "categoria_dcf": st.column_config.SelectboxColumn("Classificacao DCF", options=["OPERACIONAL", "INVESTIMENTO", "FINANCIAMENTO"], required=True),
                    "entidade": st.column_config.SelectboxColumn("Entidade", options=["EMPRESARIAL", "PESSOAL"], required=True),
                },
                num_rows="dynamic",
                key="data_editor_transacoes"
            )
        if st.button("5. Gerar Relatorio e Dashboard com Dados Corrigidos", key="generate_report_btn"):
            st.session_state['df_transacoes_editado'] = edited_df
            with st.spinner("Gerando Relatorio de Analise Consolidada..."):
                relatorio_consolidado = gerar_relatorio_final_economico(
                    edited_df,
                    st.session_state.get('contexto_adicional', ''),
                    client
                )
            st.session_state['relatorio_consolidado'] = relatorio_consolidado
            st.success("Relatorio gerado! Acesse a secao **Dashboard & Relatórios** para ver os gráficos e a análise completa.")
    else:
        st.warning("Nenhum dado processado encontrado. Volte para a secao **Upload e Extracao** e execute a extração dos seus arquivos PDF.")

elif page == "Dashboard & Relatorios":
    st.markdown("### 6. Relatorios Gerenciais e Dashboard")
    if not st.session_state['df_transacoes_editado'].empty:
        df_final = st.session_state['df_transacoes_editado']
        total_credito = df_final[df_final['tipo_movimentacao'] == 'CREDITO']['valor'].sum()
        total_debito = df_final[df_final['tipo_movimentacao'] == 'DEBITO']['valor'].sum()
        saldo_periodo = total_credito - total_debito
        st.markdown("### Resumo Financeiro CONSOLIDADO do Periodo (Pos-Correcao)")
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            st.metric("Total de Creditos", formatar_brl(total_credito))
            st.markdown('</div>', unsafe_allow_html=True)
        with kpi_col2:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            st.metric("Total de Debitos", formatar_brl(total_debito))
            st.markdown('</div>', unsafe_allow_html=True)
        with kpi_col3:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            delta_color = "normal" if saldo_periodo >= 0 else "inverse"
            st.metric("Resultado do Periodo", formatar_brl(saldo_periodo), delta_color=delta_color)
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")
        if st.session_state['relatorio_consolidado'] and st.session_state['relatorio_consolidado'] not in ["Aguardando analise de dados...", "Aguardando geracao do relatorio..."]:
            st.subheader("Relatorio de Analise Consolidada")
            st.markdown('<div class="report-textarea">', unsafe_allow_html=True)
            st.text_area(
                label="",
                value=st.session_state['relatorio_consolidado'],
                height=300,
                key="final_report_display",
                disabled=True
            )
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")
        else:
            st.warning("Pressione o botao **'Gerar Relatorio e Dashboard com Dados Corrigidos'** na secao anterior para gerar a analise em texto.")
            st.markdown("---")
        criar_dashboard(df_final)
        if st.button("Exportar Relatorio como CSV"):
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar CSV",
                data=csv,
                file_name="relatorio_hedgewise.csv",
                mime="text/csv"
            )
    else:
        st.warning("Nenhum dado processado encontrado. Volte para a secao **Upload e Extracao** e execute a extracao dos seus arquivos PDF.")

# --- Rodape (mantido) ---
st.markdown("---")
try:
    footer_logo = Image.open(LOGO_FILENAME)
    footer_col1, footer_col2 = st.columns([1, 35])
    with footer_col1:
        st.image(footer_logo, width=40)
    with footer_col2:
        st.markdown("""<p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 15px;">Analise de Extrato Empresarial | Dados extraidos e classificados com IA.</p>""", unsafe_allow_html=True)
except Exception:
    st.markdown("""<p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 15px;">Analise de Extrato Empresarial | Dados extraidos e classificados com IA.</p>""", unsafe_allow_html=True)

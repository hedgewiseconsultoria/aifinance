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

# ----------------------
# PLANO DE CONTAS (SINTETICO + ANALITICO)
# ----------------------
PLANO_DE_CONTAS = {
    "sinteticos": [
        {
            "codigo": "OP",
            "nome": "Atividades Operacionais",
            "tipo_fluxo": "OPERACIONAL",
            "contas": [
                {"codigo": "OP-01", "nome": "Receitas de Vendas"},
                {"codigo": "OP-02", "nome": "Receitas de Servicos"},
                {"codigo": "OP-03", "nome": "Outras Receitas Operacionais"},
                {"codigo": "OP-04", "nome": "Custos de Mercadorias Vendidas (CMV)"},
                {"codigo": "OP-05", "nome": "Despesas Administrativas"},
                {"codigo": "OP-06", "nome": "Despesas Comerciais"},
                {"codigo": "OP-07", "nome": "Despesas Pessoais Misturadas"},
                {"codigo": "OP-08", "nome": "Impostos e Contribuicoes"},
                {"codigo": "OP-09", "nome": "Tarifas Bancarias e Servicos"}
            ]
        },
        {
            "codigo": "INV",
            "nome": "Atividades de Investimento",
            "tipo_fluxo": "INVESTIMENTO",
            "contas": [
                {"codigo": "INV-01", "nome": "Aquisicao de Imobilizado"},
                {"codigo": "INV-02", "nome": "Aplicacoes Financeiras"},
                {"codigo": "INV-03", "nome": "Alienacao de Ativos"}
            ]
        },
        {
            "codigo": "FIN",
            "nome": "Atividades de Financiamento",
            "tipo_fluxo": "FINANCIAMENTO",
            "contas": [
                {"codigo": "FIN-01", "nome": "Emprestimos Recebidos"},
                {"codigo": "FIN-02", "nome": "Pagamento de Emprestimos"},
                {"codigo": "FIN-03", "nome": "Juros sobre Emprestimos e Financiamentos"},
                {"codigo": "FIN-04", "nome": "Aporte de Socios"},
                {"codigo": "FIN-05", "nome": "Retirada de Socios / Pro-labore"}
            ]
        },
        {
            "codigo": "NE",
            "nome": "Ajustes e Transferencias Internas",
            "tipo_fluxo": "NEUTRO",
            "contas": [
                {"codigo": "NE-01", "nome": "Transferencias entre Contas"},
                {"codigo": "NE-02", "nome": "Ajustes e Estornos"}
            ]
        }
    ]
}

# utilitarias para acessar listas
def listar_sinteticos_options():
    return [f"{s['codigo']} - {s['nome']}" for s in PLANO_DE_CONTAS['sinteticos']]

def listar_analiticas_options():
    opts = []
    for s in PLANO_DE_CONTAS['sinteticos']:
        for a in s['contas']:
            opts.append(f"{s['codigo']}|{a['codigo']} - {a['nome']}")
    return opts

# map categoria_dcf -> codigo sintetico
CATEGORIA_TO_SINTETICO = {
    'OPERACIONAL': 'OP',
    'INVESTIMENTO': 'INV',
    'FINANCIAMENTO': 'FIN'
}

# ----------------------
# formata BRL
# ----------------------
def formatar_brl(valor: float) -> str:
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP_SEP").replace(".", ",").replace("TEMP_SEP", ".")
        return "R$ " + valor_brl
    except Exception:
        return "R$ 0,00"

# ----------------------
# tema e configs (mantidos)
# ----------------------
PRIMARY_COLOR = "#0A2342"
SECONDARY_COLOR = "#000000"
BACKGROUND_COLOR = "#F0F2F6"
ACCENT_COLOR = "#007BFF"
NEGATIVE_COLOR = "#DC3545"
FINANCING_COLOR = "#FFC107"
REPORT_BACKGROUND = "#F9F5EB"
LOGO_FILENAME = "logo_hedgewise.png"

st.set_page_config(
    page_title="Hedgewise | Analise Financeira Inteligente",
    page_icon="logo_hedgewise.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# css (mantido)
st.markdown(
    f"""
    <style>
        .stApp {{ background-color: {BACKGROUND_COLOR}; }}
        [data-testid="stSidebar"] {{ background-color: white; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .main-header {{ color: {SECONDARY_COLOR}; font-size: 2.2em; padding-bottom: 8px; }}
        .kpi-container {{ background-color: white; padding: 16px; border-radius: 12px; box-shadow: 0 6px 15px 0 rgba(0,0,0,0.08); margin-bottom: 10px; }}
        .report-textarea, .report-textarea > div, .report-textarea textarea {{ background-color: {REPORT_BACKGROUND} !important; border-radius: 8px !important; }}
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------
# estado da sessao
# ----------------------
if 'df_transacoes_editado' not in st.session_state:
    st.session_state['df_transacoes_editado'] = pd.DataFrame()
if 'relatorio_consolidado' not in st.session_state:
    st.session_state['relatorio_consolidado'] = "Aguardando analise de dados..."
if 'contexto_adicional' not in st.session_state:
    st.session_state['contexto_adicional'] = ""

# cliente Gemini
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except Exception:
    client = None

# ----------------------
# Pydantic schemas (mantidos)
# ----------------------
class Transacao(BaseModel):
    data: str
    descricao: str
    valor: float
    tipo_movimentacao: str
    categoria_sugerida: str
    categoria_dcf: str
    entidade: str

class AnaliseCompleta(BaseModel):
    transacoes: List[Transacao]
    relatorio_inicial: str
    saldo_final: float

# ----------------------
# chamada API (inclui plano de contas para orientar classificacao)
# ----------------------
@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')
    plano_str = json.dumps(PLANO_DE_CONTAS, ensure_ascii=False)
    prompt_analise = (
        f"Voce e um especialista em extracao e classificacao de dados financeiros. "
        f"Extraia todas as transacoes deste extrato bancario em PDF ('{filename}') e classifique cada transacao nas seguintes chaves: 'categoria_sugerida' (descricao curta), 'categoria_dcf' (OPERACIONAL, INVESTIMENTO ou FINANCIAMENTO) e 'entidade' (EMPRESARIAL ou PESSOAL). "
        "Use o plano de contas abaixo como referencia para sugerir uma conta analitica e sintetica apropriada. Retorne JSON estrito conforme o schema.

"
        f"PLANO_DE_CONTAS={plano_str}

"
        "Regras: valor deve ser positivo; tipo_movimentacao: CREDITO ou DEBITO; categoria_dcf deve ser uma das tres opcoes."
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
        return {'transacoes': [], 'saldo_final': 0.0, 'relatorio_inicial': f'Erro: {e}'}

# ----------------------
# Funcoes de consolidacao e indicadores (agora usam conta_sintetica/analitica)
# ----------------------
def aplicar_plano_de_contas_no_df(df: pd.DataFrame) -> pd.DataFrame:
    """Garante colunas conta_sintetica e conta_analitica com defaults baseados em categoria_dcf e categoria_sugerida."""
    df = df.copy()
    # criar fluxo (positivo para creditos, negativo para debitos)
    df['fluxo'] = df.apply(lambda r: r['valor'] if r['tipo_movimentacao'] == 'CREDITO' else -r['valor'], axis=1)
    # padronizar datas
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    # conta sintetica default
    df['conta_sintetica'] = df['categoria_dcf'].map(CATEGORIA_TO_SINTETICO).fillna('NE')
    # tenta mapear analitica por substring na categoria_sugerida
    analiticas = listar_analiticas_options()
    nomes_analiticas = [opt.split(' - ',1)[1].lower() for opt in analiticas]
    codigos_analiticas = [opt.split(' - ',1)[0] for opt in analiticas]
    def achar_analitica(desc):
        if not isinstance(desc, str):
            return f"NE|NE-01 - Outros"
        d = desc.lower()
        for i,n in enumerate(nomes_analiticas):
            if n.split() and any(tok in d for tok in n.split()[:3]):
                return codigos_analiticas[i] + ' - ' + nomes_analiticas[i].title()
        # fallback
        return f"NE|NE-01 - Outros"
    df['conta_analitica'] = df['categoria_sugerida'].apply(achar_analitica)
    # normalize formats for select options (sintetica show as CODE - Name)
    sint_opts_map = {s['codigo']: f"{s['codigo']} - {s['nome']}" for s in PLANO_DE_CONTAS['sinteticos']}
    df['conta_sintetica_label'] = df['conta_sintetica'].map(sint_opts_map).fillna('NE - Ajustes/Transferencias')
    return df


def gerar_relatorio_mensal_e_indicadores(df_transacoes: pd.DataFrame) -> dict:
    df = df_transacoes.copy()
    df = aplicar_plano_de_contas_no_df(df)
    df = df.dropna(subset=['data'])
    df['mes_ano'] = df['data'].dt.to_period('M').astype(str)

    # Mapear tipo_fluxo com base em conta_sintetica
    tipo_map = {s['codigo']: s['tipo_fluxo'] for s in PLANO_DE_CONTAS['sinteticos']}
    df['tipo_fluxo'] = df['conta_sintetica'].map(tipo_map).fillna('NEUTRO')

    # Agregar por mes e por tipo_fluxo
    agregados = df.groupby(['mes_ano', 'tipo_fluxo'])['fluxo'].sum().unstack(fill_value=0).reset_index()
    # garantir colunas
    for col in ['OPERACIONAL', 'INVESTIMENTO', 'FINANCIAMENTO']:
        if col not in agregados.columns:
            agregados[col] = 0.0

    # Entradas operacionais (creditos classificados como OPERACIONAL)
    entradas_operacionais = df[(df['tipo_fluxo'] == 'OPERACIONAL') & (df['fluxo'] > 0)].groupby('mes_ano')['fluxo'].sum()
    entradas_operacionais = entradas_operacionais.reindex(agregados['mes_ano']).fillna(0).values

    operacional = agregados['OPERACIONAL'].values
    investimento = agregados['INVESTIMENTO'].values
    financiamento = agregados['FINANCIAMENTO'].values

    margem_operacional = np.where(entradas_operacionais != 0, operacional / entradas_operacionais, np.nan)
    intensidade_investimento = np.where(operacional != 0, investimento / operacional, np.nan)
    intensidade_financiamento = np.where(operacional != 0, financiamento / operacional, np.nan)

    indicadores = pd.DataFrame({
        'mes_ano': agregados['mes_ano'],
        'margem_operacional': margem_operacional,
        'intensidade_investimento': intensidade_investimento,
        'intensidade_financiamento': intensidade_financiamento
    })

    resumo = {
        'total_periodo': df['fluxo'].sum(),
        'operacional_total': df[df['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum(),
        'investimento_total': df[df['tipo_fluxo'] == 'INVESTIMENTO']['fluxo'].sum(),
        'financiamento_total': df[df['tipo_fluxo'] == 'FINANCIAMENTO']['fluxo'].sum(),
        'pessoal_total': df[df['entidade'] == 'PESSOAL']['fluxo'].sum()
    }

    return {'agregados': agregados, 'indicadores': indicadores, 'resumo': resumo}

# ----------------------
# Relatorio consolidado (prompt ajustado para incluir indicadores)
# ----------------------
def gerar_relatorio_final_economico(df_transacoes: pd.DataFrame, contexto_adicional: str, client: genai.Client) -> str:
    rel = gerar_relatorio_mensal_e_indicadores(df_transacoes)
    agregados = rel['agregados']
    indicadores = rel['indicadores']

    linhas_ag = []
    for _, row in agregados.iterrows():
        linhas_ag.append(f"{row['mes_ano']}: OPERACIONAL={row.get('OPERACIONAL',0):.2f}, INVESTIMENTO={row.get('INVESTIMENTO',0):.2f}, FINANCIAMENTO={row.get('FINANCIAMENTO',0):.2f}")
    resumo_text = "
".join(linhas_ag)

    contexto_prompt = f"

--- CONTEXTO ADICIONAL ---
{contexto_adicional}
--- FIM DO CONTEXTO ---
" if contexto_adicional else ""

    prompt_analise = (
        "Voce e um consultor financeiro para PMEs. A seguir ha dados sinteticos mensais do fluxo por tipo (OPERACIONAL, INVESTIMENTO, FINANCIAMENTO) e os indicadores calculados: margem_operacional, intensidade_investimento e intensidade_financiamento. "
        "Interprete tendencia, identifique alertas e proponha 3 acoes praticas e priorizadas. Responda em texto simples (max 220 palavras)." 
        f"

DADOS_SINTETICOS:
{resumo_text}

INDICADORES_POR_MES:
{indicadores.to_csv(index=False)}{contexto_prompt}"
    )

    if client is None:
        # fallback: gerar texto simples local
        texto = "Prezado(a) cliente,
Segue analise sintetica: 
"
        texto += "
".join(linhas_ag[:6])
        texto += "
Sem acesso ao modelo de linguagem para analise textual automatizada."
        return texto

    config = types.GenerateContentConfig(temperature=0.4)
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt_analise],
            config=config,
        )
        return response.text
    except Exception as e:
        return f"Erro na geracao do relatorio analitico: {e}"

# ----------------------
# UI: header
# ----------------------

def load_header():
    try:
        logo = Image.open(LOGO_FILENAME)
        col1, col2 = st.columns([1, 10])
        with col1:
            st.image(logo, width=100)
        with col2:
            st.markdown('<div class="main-header">Analise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("O horizonte do pequeno empreendedor")
        st.markdown('---')
    except Exception:
        st.title('Hedgewise | Analise Financeira Inteligente')
        st.markdown('---')

# ----------------------
# Dashboard (usa as novas colunas)
# ----------------------

def criar_dashboard(df: pd.DataFrame):
    st.subheader('Dashboard: Analise de Fluxo de Caixa')
    if df.empty:
        st.info('Nenhum dado disponivel para o dashboard.')
        return
    df = df.copy()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df = df.dropna(subset=['data'])
    rel = gerar_relatorio_mensal_e_indicadores(df)
    agregados = rel['agregados']
    indicadores = rel['indicadores']

    st.markdown('### Demonstracao Mensal - Sintetica (por Tipo de Fluxo)')
    st.dataframe(agregados.style.format({'OPERACIONAL':'{:,.2f}','INVESTIMENTO':'{:,.2f}','FINANCIAMENTO':'{:,.2f}'}), use_container_width=True)

    st.markdown('### Comparativo Mensal de Flux de Caixa (por Tipo e Retiradas Pessoais)')
    df['mes_ano'] = df['data'].dt.to_period('M').astype(str)
    df_plot = df.groupby(['mes_ano', 'tipo_fluxo'])['fluxo'].sum().reset_index()
    # inserir PESSOAL
    df_pessoal = df[df['entidade']=='PESSOAL'].groupby('mes_ano')['fluxo'].sum().reset_index()
    if not df_pessoal.empty:
        df_pessoal['tipo_fluxo'] = 'PESSOAL'
        df_plot = pd.concat([df_plot, df_pessoal], ignore_index=True)

    fig = px.bar(df_plot, x='mes_ano', y='fluxo', color='tipo_fluxo', barmode='group', labels={'fluxo':'Fluxo (R$)','mes_ano':'Mês/Ano', 'tipo_fluxo':'Categoria'})
    fig.update_layout(height=420, plot_bgcolor='white')
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('### Evolucao Mensal dos Indicadores')
    ind_plot = indicadores.copy()
    ind_plot['margem_operacional_pct'] = ind_plot['margem_operacional'] * 100
    ind_plot['intensidade_investimento_pct'] = ind_plot['intensidade_investimento'] * 100
    ind_plot['intensidade_financiamento_pct'] = ind_plot['intensidade_financiamento'] * 100
    dfm = ind_plot.melt(id_vars='mes_ano', value_vars=['margem_operacional_pct','intensidade_investimento_pct','intensidade_financiamento_pct'], var_name='indicador', value_name='valor_pct')
    fig_ind = px.line(dfm, x='mes_ano', y='valor_pct', color='indicador', markers=True, labels={'valor_pct':'Percentual (%)','mes_ano':'Mês/Ano'})
    fig_ind.update_layout(height=360, plot_bgcolor='white')
    st.plotly_chart(fig_ind, use_container_width=True)

    st.caption('Margem Operacional = OPERACIONAL / Entradas Operacionais. Intensidade_investimento = INVESTIMENTO / OPERACIONAL. Intensidade_financiamento = FINANCIAMENTO / OPERACIONAL.')

# ----------------------
# APP principal
# ----------------------
load_header()
st.sidebar.title('Navegacao')
page = st.sidebar.radio('Secoes', ['Upload e Extracao', 'Revisao de Dados', 'Dashboard & Relatorios'])

if page == 'Upload e Extracao':
    st.markdown('### 1. Upload e Extracao de Dados')
    with st.expander('Upload de Arquivos', expanded=True):
        col_u, col_c = st.columns([1,1])
        with col_u:
            uploaded_files = st.file_uploader('Selecione os arquivos PDF dos seus extratos bancarios', type='pdf', accept_multiple_files=True)
        with col_c:
            contexto_adicional_input = st.text_area('Contexto Adicional (Opcional)', value=st.session_state.get('contexto_adicional',''))
    if contexto_adicional_input != st.session_state.get('contexto_adicional',''):
        st.session_state['contexto_adicional'] = contexto_adicional_input

    if uploaded_files:
        if st.button(f'Executar Extracao e Classificacao ({len(uploaded_files)} arquivos)'):
            todas_trans = []
            for f in uploaded_files:
                bytes_pdf = f.getvalue()
                dados = analisar_extrato(bytes_pdf, f.name, client) if client is not None else {'transacoes':[], 'saldo_final':0.0, 'relatorio_inicial':'Sem cliente'}
                todas_trans.extend(dados.get('transacoes', []))
            df = pd.DataFrame(todas_trans)
            if df.empty:
                st.error('Nenhuma transacao extraida.')
            else:
                # normalizacoes basicas
                df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
                df['tipo_movimentacao'] = df['tipo_movimentacao'].fillna('DEBITO')
                df['entidade'] = df['entidade'].fillna('EMPRESARIAL')
                df['categoria_dcf'] = df['categoria_dcf'].fillna('OPERACIONAL')
                # aplicar plano defaults
                df = aplicar_plano_de_contas_no_df(df)
                st.session_state['df_transacoes_editado'] = df
                st.success('Extracao concluida. Verifique e ajuste os lancamentos na aba Revisao de Dados.')

elif page == 'Revisao de Dados':
    st.markdown('### 2. Revisao e Correcao Manual dos Dados')
    df = st.session_state.get('df_transacoes_editado', pd.DataFrame())
    if df.empty:
        st.warning('Nenhum dado processado encontrado. Execute a extracao primeiro.')
    else:
        st.info('Revise Entidade, Classificacao DCF, Conta Sintetica e Conta Analitica. Use as opcoes do plano de contas.')
        # garantir colunas para edicao
        if 'conta_sintetica_label' not in df.columns:
            df = aplicar_plano_de_contas_no_df(df)
        # preparar opcoes
        sint_opts = listar_sinteticos_options()
        anal_opts = listar_analiticas_options()

        # data editor com selectboxes para contas
        col_config = {
            'data': st.column_config.DateColumn('Data', format='YYYY-MM-DD'),
            'valor': st.column_config.NumberColumn('Valor (R$)', format='R$ %0.2f'),
            'tipo_movimentacao': st.column_config.SelectboxColumn('Tipo', options=['CREDITO','DEBITO']),
            'categoria_dcf': st.column_config.SelectboxColumn('Classificacao DCF', options=['OPERACIONAL','INVESTIMENTO','FINANCIAMENTO']),
            'entidade': st.column_config.SelectboxColumn('Entidade', options=['EMPRESARIAL','PESSOAL']),
            'conta_sintetica_label': st.column_config.SelectboxColumn('Conta Sintetica', options=sint_opts),
            'conta_analitica': st.column_config.SelectboxColumn('Conta Analitica', options=anal_opts)
        }

        edited = st.data_editor(df, column_config=col_config, num_rows='dynamic', use_container_width=True)

        if st.button('Aplicar Ajustes e Gerar Relatorio'):
            # sincronizar conta_sintetica codigo a partir do label selecionado
            def extrair_codigo_sint(label):
                if isinstance(label, str) and ' - ' in label:
                    return label.split(' - ',1)[0]
                return 'NE'
            edited['conta_sintetica'] = edited['conta_sintetica_label'].apply(extrair_codigo_sint)
            # padroniza conta_analitica para forma codigo|descricao
            def padroniza_analitica(val):
                if isinstance(val, str) and '|' in val:
                    return val
                return str(val)
            edited['conta_analitica'] = edited['conta_analitica'].apply(padroniza_analitica)
            st.session_state['df_transacoes_editado'] = edited
            # gerar relatorio consolidado via IA
            with st.spinner('Gerando relatorio consolidado...'):
                texto = gerar_relatorio_final_economico(edited, st.session_state.get('contexto_adicional',''), client)
            st.session_state['relatorio_consolidado'] = texto
            st.success('Ajustes aplicados e relatorio gerado. Confira o Dashboard.')

elif page == 'Dashboard & Relatorios':
    st.markdown('### 3. Relatorios Gerenciais e Dashboard')
    df = st.session_state.get('df_transacoes_editado', pd.DataFrame())
    if df.empty:
        st.warning('Nenhum dado processado encontrado. Volte para Upload e execucao da extracao.')
    else:
        total_credito = df[df['tipo_movimentacao']=='CREDITO']['valor'].sum()
        total_debito = df[df['tipo_movimentacao']=='DEBITO']['valor'].sum()
        saldo_periodo = total_credito - total_debito
        k1,k2,k3 = st.columns(3)
        with k1:
            st.metric('Total de Creditos', formatar_brl(total_credito))
        with k2:
            st.metric('Total de Debitos', formatar_brl(total_debito))
        with k3:
            st.metric('Resultado do Periodo', formatar_brl(saldo_periodo))
        st.markdown('---')
        if st.session_state.get('relatorio_consolidado') and st.session_state['relatorio_consolidado'] != 'Aguardando analise de dados...':
            st.subheader('Relatorio de Analise Consolidada')
            st.markdown('<div class="report-textarea">', unsafe_allow_html=True)
            st.text_area('', value=st.session_state['relatorio_consolidado'], height=260)
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('---')
        criar_dashboard(df)
        if st.button('Exportar CSV'):
            st.download_button('Baixar CSV', data=df.to_csv(index=False).encode('utf-8'), file_name='relatorio_hedgewise.csv')

# rodape
st.markdown('---')
try:
    footer_logo = Image.open(LOGO_FILENAME)
    c1,c2 = st.columns([1,30])
    with c1:
        st.image(footer_logo, width=40)
    with c2:
        st.markdown('<p style="font-size:0.8rem;color:#6c757d">Analise de Extrato Empresarial | Dados extraidos e classificados com IA.</p>', unsafe_allow_html=True)
except Exception:
    st.markdown('<p style="font-size:0.8rem;color:#6c757d">Analise de Extrato Empresarial | Dados extraidos e classificados com IA.</p>', unsafe_allow_html=True)

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
import plotly.graph_objects as go

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
                {"codigo": "OP-02", "nome": "Receitas de Servicos"},
                {"codigo": "OP-03", "nome": "Outras Receitas Operacionais"},
                {"codigo": "OP-04", "nome": "Custos Operacionais"},
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

# --- FUNÇÃO DE FORMATAÇÃO BRL ---
def formatar_brl(valor: float) -> str:
    """Formata um valor float para a moeda Real Brasileiro (R$ xx.xxx,xx)."""
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
INVESTMENT_COLOR = "#28A745"
REPORT_BACKGROUND = "#F9F5EB"

LOGO_FILENAME = "logo_hedgewise.png"

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="logo_hedgewise.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
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
        .fluxo-table {{
            background-color: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    """,
    unsafe_allow_html=True
)

# Inicializa o estado da sessão
if 'df_transacoes_editado' not in st.session_state:
    st.session_state['df_transacoes_editado'] = pd.DataFrame()
if 'contexto_adicional' not in st.session_state:
    st.session_state['contexto_adicional'] = ""

# Inicializa o cliente Gemini
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except (KeyError, AttributeError):
    st.error("ERRO: Chave 'GEMINI_API_KEY' não encontrada. Configure-a para rodar a aplicação.")
    st.stop()

# --- 2. DEFINIÇÃO DO SCHEMA PYDANTIC ---
class Transacao(BaseModel):
    """Representa uma única transação no extrato bancário."""
    data: str = Field(description="A data da transação no formato 'DD/MM/AAAA'.")
    descricao: str = Field(description="Descrição detalhada da transação.")
    valor: float = Field(description="O valor numérico da transação. Sempre positivo.")
    tipo_movimentacao: str = Field(description="Classificação da movimentação: 'DEBITO' ou 'CREDITO'.")
    conta_analitica: str = Field(description="Código da conta analítica do plano de contas (ex: OP-01, INV-02, FIN-05).")

class AnaliseCompleta(BaseModel):
    """Contém a lista de transações extraídas."""
    transacoes: List[Transacao] = Field(description="Uma lista de objetos 'Transacao' extraídos do documento.")
    saldo_final: float = Field(description="O saldo final da conta no extrato. Use zero se não for encontrado.")

# --- 3. FUNÇÃO PARA GERAR PROMPT COM PLANO DE CONTAS ---
def gerar_prompt_com_plano_contas() -> str:
    """Gera o prompt incluindo o plano de contas para a IA."""
    contas_str = "### PLANO DE CONTAS ###\n\n"
    
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        contas_str += f"**{sintetico['codigo']} - {sintetico['nome']}** (Tipo: {sintetico['tipo_fluxo']})\n"
        for conta in sintetico["contas"]:
            contas_str += f"  - {conta['codigo']}: {conta['nome']}\n"
        contas_str += "\n"
    
    prompt = f"""Você é um especialista em extração e classificação de dados financeiros.

{contas_str}

Extraia todas as transações deste extrato bancário em PDF e classifique cada transação de acordo com o PLANO DE CONTAS acima.

INSTRUÇÕES CRÍTICAS:
1. Use EXATAMENTE os códigos de conta analítica listados acima (ex: OP-01, OP-05, INV-01, FIN-05, etc.)
2. Analise cuidadosamente cada transação para determinar a conta mais apropriada
3. Retiradas de sócios e pró-labore devem ser classificados como FIN-05
4. Receitas operacionais: OP-01 (vendas), OP-02 (serviços), OP-03 (outras)
5. Despesas operacionais: OP-04 (CMV), OP-05 (administrativas), OP-06 (comerciais), OP-08 (impostos), OP-09 (tarifas)
6. Investimentos: INV-01 (compra de ativos), INV-02 (aplicações), INV-03 (venda de ativos)
7. Financiamentos: FIN-01 (empréstimos recebidos), FIN-02 (pagamento de empréstimos), FIN-03 (juros)
8. **IMPORTANTE - Transferências NEUTRAS (NE-01 ou NE-02)**: Use APENAS quando detectar uma saída de uma conta corrente E uma entrada de MESMO VALOR em outra conta no MESMO DIA. Isso evita classificação errônea como receita ou despesa. Se não houver correspondência exata de valores e datas, classifique normalmente nas outras categorias.

Use valor POSITIVO para 'valor' e classifique como 'DEBITO' ou 'CREDITO'.
"""
    return prompt

# --- 4. FUNÇÃO DE CHAMADA DA API PARA EXTRAÇÃO ---
@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
    """Chama a Gemini API para extrair dados estruturados usando o plano de contas."""
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')
    prompt_analise = gerar_prompt_com_plano_contas()
    
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
            st.error(f"⚠️ ERRO DE CAPACIDADE DA API: O modelo Gemini está sobrecarregado (503 UNAVAILABLE) ao processar {filename}.")
            st.info("Este é um erro temporário do servidor da API. Por favor, tente novamente em alguns minutos.")
        else:
            print(f"Erro ao chamar a Gemini API para {filename}: {error_message}")
        return {
            'transacoes': [],
            'saldo_final': 0.0
        }

# --- 5. FUNÇÃO PARA ENRIQUECER DADOS COM PLANO DE CONTAS ---
def enriquecer_com_plano_contas(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona informações do plano de contas ao DataFrame."""
    # Criar mapeamento de contas
    mapa_contas = {}
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        for conta in sintetico["contas"]:
            mapa_contas[conta["codigo"]] = {
                "nome_conta": conta["nome"],
                "codigo_sintetico": sintetico["codigo"],
                "nome_sintetico": sintetico["nome"],
                "tipo_fluxo": sintetico["tipo_fluxo"]
            }
    
    # Enriquecer DataFrame
    df['nome_conta'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('nome_conta', 'Não classificado'))
    df['codigo_sintetico'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('codigo_sintetico', 'NE'))
    df['nome_sintetico'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('nome_sintetico', 'Não classificado'))
    df['tipo_fluxo'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('tipo_fluxo', 'NEUTRO'))
    
    return df

# --- 6. FUNÇÃO PARA CRIAR RELATÓRIO DE FLUXO DE CAIXA ---
def criar_relatorio_fluxo_caixa(df: pd.DataFrame):
    """Cria um relatório detalhado de fluxo de caixa com meses em colunas lado a lado."""
    st.subheader("Relatório de Fluxo de Caixa")
    
    if df.empty:
        st.info("Nenhum dado disponível. Por favor, processe os extratos primeiro.")
        return
    
    # Preparar dados
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df.dropna(subset=['data'], inplace=True)
    df['mes_ano'] = df['data'].dt.to_period('M')
    df['fluxo'] = df.apply(
        lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'],
        axis=1
    )
    
    # Filtrar apenas operações válidas (excluir NEUTRO)
    df_fluxo = df[df['tipo_fluxo'] != 'NEUTRO'].copy()
    
    # Obter meses únicos ordenados
    meses = sorted(df_fluxo['mes_ano'].unique())
    
    # Dicionário para mapear meses em português
    meses_pt = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    
    # Criar colunas de meses formatadas
    colunas_meses = []
    for mes in meses:
        mes_nome = meses_pt[mes.month]
        ano = mes.year % 100  # Pega apenas os 2 últimos dígitos do ano
        colunas_meses.append(f"{mes_nome}/{ano:02d}")
    
    # Coletar todas as contas únicas por tipo de fluxo
    todas_contas = df_fluxo.groupby(['tipo_fluxo', 'conta_analitica', 'nome_conta']).size().reset_index()[
        ['tipo_fluxo', 'conta_analitica', 'nome_conta']
    ]
    
    # Criar estrutura do relatório
    relatorio_linhas = []
    
    # 1. ATIVIDADES OPERACIONAIS
    relatorio_linhas.append({'Categoria': '**ATIVIDADES OPERACIONAIS**', 'tipo': 'header'})
    
    contas_op = todas_contas[todas_contas['tipo_fluxo'] == 'OPERACIONAL'].sort_values('conta_analitica')
    for _, conta in contas_op.iterrows():
        linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
        for mes in meses:
            df_mes_conta = df_fluxo[
                (df_fluxo['mes_ano'] == mes) & 
                (df_fluxo['conta_analitica'] == conta['conta_analitica'])
            ]
            valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha[mes_col] = valor
        relatorio_linhas.append(linha)
    
    # Total Operacional
    linha_total_op = {'Categoria': '**Total Caixa Operacional**', 'tipo': 'total'}
    for mes in meses:
        df_mes_op = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'OPERACIONAL')]
        valor = df_mes_op['fluxo'].sum() if not df_mes_op.empty else 0
        mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
        linha_total_op[mes_col] = valor
    relatorio_linhas.append(linha_total_op)
    relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
    # 2. ATIVIDADES DE INVESTIMENTO
    contas_inv = todas_contas[todas_contas['tipo_fluxo'] == 'INVESTIMENTO'].sort_values('conta_analitica')
    if not contas_inv.empty:
        relatorio_linhas.append({'Categoria': '**ATIVIDADES DE INVESTIMENTO**', 'tipo': 'header'})
        
        for _, conta in contas_inv.iterrows():
            linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
            for mes in meses:
                df_mes_conta = df_fluxo[
                    (df_fluxo['mes_ano'] == mes) & 
                    (df_fluxo['conta_analitica'] == conta['conta_analitica'])
                ]
                valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
                mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)
        
        # Total Investimento
        linha_total_inv = {'Categoria': '**Total Caixa de Investimento**', 'tipo': 'total'}
        for mes in meses:
            df_mes_inv = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'INVESTIMENTO')]
            valor = df_mes_inv['fluxo'].sum() if not df_mes_inv.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha_total_inv[mes_col] = valor
        relatorio_linhas.append(linha_total_inv)
        relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
    # 3. ATIVIDADES DE FINANCIAMENTO
    contas_fin = todas_contas[todas_contas['tipo_fluxo'] == 'FINANCIAMENTO'].sort_values('conta_analitica')
    if not contas_fin.empty:
        relatorio_linhas.append({'Categoria': '**ATIVIDADES DE FINANCIAMENTO**', 'tipo': 'header'})
        
        for _, conta in contas_fin.iterrows():
            linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
            for mes in meses:
                df_mes_conta = df_fluxo[
                    (df_fluxo['mes_ano'] == mes) & 
                    (df_fluxo['conta_analitica'] == conta['conta_analitica'])
                ]
                valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
                mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)
        
        # Total Financiamento
        linha_total_fin = {'Categoria': '**Total Caixa de Financiamento**', 'tipo': 'total'}
        for mes in meses:
            df_mes_fin = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'FINANCIAMENTO')]
            valor = df_mes_fin['fluxo'].sum() if not df_mes_fin.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha_total_fin[mes_col] = valor
        relatorio_linhas.append(linha_total_fin)
        relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
    # 4. CAIXA GERADO NO MÊS
    linha_separador = {'Categoria': '═' * 50, 'tipo': 'separator'}
    for mes_col in colunas_meses:
        linha_separador[mes_col] = ''
    relatorio_linhas.append(linha_separador)
    
    linha_caixa_gerado = {'Categoria': '**CAIXA GERADO NO MÊS**', 'tipo': 'total'}
    for mes in meses:
        df_mes_total = df_fluxo[df_fluxo['mes_ano'] == mes]
        valor = df_mes_total['fluxo'].sum() if not df_mes_total.empty else 0
        mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
        linha_caixa_gerado[mes_col] = valor
    relatorio_linhas.append(linha_caixa_gerado)
    
    # Criar DataFrame
    df_relatorio = pd.DataFrame(relatorio_linhas)
    
    # Preencher NaN com valores vazios antes de formatar
    df_relatorio = df_relatorio.fillna('')
    
    # Formatar valores monetários
    for col in colunas_meses:
        if col in df_relatorio.columns:
            df_relatorio[col] = df_relatorio[col].apply(
                lambda x: formatar_brl(x) if isinstance(x, (int, float)) and x != 0 else ''
            )
    
    # Remover coluna 'tipo'
    df_display = df_relatorio.drop(columns=['tipo'])
    
    # Exibir tabela
    st.markdown('<div class="fluxo-table">', unsafe_allow_html=True)
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Categoria": st.column_config.TextColumn("Categoria", width="large"),
            **{col: st.column_config.TextColumn(col, width="medium") for col in colunas_meses}
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    return None

# --- 7. FUNÇÃO PARA CRIAR GRÁFICO DE INDICADORES ---
def criar_grafico_indicadores(df: pd.DataFrame):
    """Cria gráfico com evolução dos indicadores financeiros."""
    st.subheader("Evolução dos Indicadores Financeiros")
    
    if df.empty:
        st.info("Nenhum dado disponível para indicadores.")
        return
    
    # Preparar dados
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df.dropna(subset=['data'], inplace=True)
    df['mes_ano'] = df['data'].dt.to_period('M')
    df['fluxo'] = df.apply(
        lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'],
        axis=1
    )
    
    # Filtrar apenas operações válidas (excluir NEUTRO)
    df_fluxo = df[df['tipo_fluxo'] != 'NEUTRO'].copy()
    
    meses = sorted(df_fluxo['mes_ano'].unique())
    indicadores_data = []
    
    for mes in meses:
        df_mes = df_fluxo[df_fluxo['mes_ano'] == mes]
        mes_str = mes.strftime('%m/%Y')
        
        # Calcular componentes
        caixa_op = df_mes[df_mes['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()
        caixa_inv = df_mes[df_mes['tipo_fluxo'] == 'INVESTIMENTO']['fluxo'].sum()
        caixa_fin = df_mes[df_mes['tipo_fluxo'] == 'FINANCIAMENTO']['fluxo'].sum()
        
        entradas_op = df_mes[
            (df_mes['tipo_fluxo'] == 'OPERACIONAL') & 
            (df_mes['tipo_movimentacao'] == 'CREDITO')
        ]['valor'].sum()
        
        # Calcular indicadores
        margem_caixa_op = (caixa_op / entradas_op * 100) if entradas_op > 0 else 0
        intensidade_inv = (caixa_inv / caixa_op * 100) if caixa_op != 0 else 0
        intensidade_fin = (caixa_fin / caixa_op * 100) if caixa_op != 0 else 0
        
        indicadores_data.append({
            'Mês': mes_str,
            'Margem de Caixa Operacional (%)': margem_caixa_op,
            'Intensidade de Investimento (%)': intensidade_inv,
            'Intensidade de Financiamento (%)': intensidade_fin
        })
    
    df_indicadores = pd.DataFrame(indicadores_data)
    
    # Criar gráfico
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_indicadores['Mês'],
        y=df_indicadores['Margem de Caixa Operacional (%)'],
        mode='lines+markers',
        name='Margem de Caixa Operacional',
        line=dict(color=ACCENT_COLOR, width=3)
    ))
    
    fig.add_trace(go.Scatter(
        x=df_indicadores['Mês'],
        y=df_indicadores['Intensidade de Investimento (%)'],
        mode='lines+markers',
        name='Intensidade de Investimento',
        line=dict(color=INVESTMENT_COLOR, width=3)
    ))
    
    fig.add_trace(go.Scatter(
        x=df_indicadores['Mês'],
        y=df_indicadores['Intensidade de Financiamento (%)'],
        mode='lines+markers',
        name='Intensidade de Financiamento',
        line=dict(color=FINANCING_COLOR, width=3)
    ))
    
    fig.update_layout(
        title='Indicadores Financeiros (%)',
        xaxis_title='Mês',
        yaxis_title='Percentual (%)',
        height=400,
        plot_bgcolor='white',
        font=dict(family="Roboto"),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Explicação dos indicadores
    with st.expander("📊 Entenda os Indicadores"):
        st.markdown("""
        **Margem de Caixa Operacional**: Percentual do caixa operacional em relação às entradas operacionais. 
        Indica a eficiência operacional na geração de caixa.
        
        **Intensidade de Investimento**: Percentual do caixa de investimento em relação ao caixa operacional. 
        Indica quanto da geração operacional está sendo investido.
        
        **Intensidade de Financiamento**: Percentual do caixa de financiamento em relação ao caixa operacional. 
        Indica a dependência de fontes externas de capital.
        """)
    
    st.markdown("---")


# --- FUNÇÃO: CÁLCULO DO SCORE FINANCEIRO BASEADO EM FLUXO DE CAIXA ---
def calcular_score_fluxo(df: pd.DataFrame):
    """
    Calcula o Score Financeiro com base nos três indicadores:
    - Margem de Caixa Operacional (MCO)
    - Intensidade de Investimentos (I_INV)
    - Intensidade de Financiamentos (I_FIN)
    Retorna um dicionário com score_final, pontos por indicador e valores dos indicadores.
    """
    # Preparar dados (mesma lógica usada nos gráficos)
    df = df.copy()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df.dropna(subset=['data'], inplace=True)
    df['fluxo'] = df.apply(lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], axis=1)
    df_fluxo = df[df['tipo_fluxo'] != 'NEUTRO'].copy()

    caixa_op = df_fluxo[df_fluxo['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()
    caixa_inv = df_fluxo[df_fluxo['tipo_fluxo'] == 'INVESTIMENTO']['fluxo'].sum()
    caixa_fin = df_fluxo[df_fluxo['tipo_fluxo'] == 'FINANCIAMENTO']['fluxo'].sum()

    entradas_op = df_fluxo[(df_fluxo['tipo_fluxo'] == 'OPERACIONAL') & (df_fluxo['tipo_movimentacao'] == 'CREDITO')]['valor'].sum()

    # Indicadores (tratar divisões por zero)
    margem_op = (caixa_op / entradas_op) if entradas_op > 0 else 0.0
    # Intensidade de investimentos: considerar sinal natural (investimento tipicamente negativo)
    # Queremos o percentual positivo representando "quanto do caixa operacional está sendo consumido por investimentos"
    intensidade_inv = (abs(min(caixa_inv, 0)) / caixa_op) if caixa_op != 0 else 0.0
    intensidade_fin = (caixa_fin / caixa_op) if caixa_op != 0 else 0.0

    # Pontuação Margem Operacional (0-100)
    if margem_op >= 0.20:
        p_op = 100
    elif margem_op >= 0.15:
        p_op = 80
    elif margem_op >= 0.10:
        p_op = 60
    elif margem_op >= 0.05:
        p_op = 40
    elif margem_op >= 0.0:
        p_op = 20
    else:
        p_op = 0

    # Pontuação Intensidade de Investimentos (I_INV em proporção, ex: 0.25 = 25%)
    # Faixas: 0-30% muito baixo risco (100), 30-70% baixo(80), 70-100%(50), >100%(20)
    if intensidade_inv <= 0.30:
        p_inv = 100
    elif intensidade_inv <= 0.70:
        p_inv = 80
    elif intensidade_inv <= 1.0:
        p_inv = 50
    else:
        p_inv = 20

    # Pontuação Intensidade de Financiamentos (condicional)
    # Se financiamento >= 0 (entradas de recursos)
    if intensidade_fin >= 0:
        if intensidade_fin <= 0.30:
            p_fin = 100
        elif intensidade_fin <= 1.0:
            p_fin = 70
        else:
            # >100% -> depende da margem operacional
            if margem_op >= 0.10:
                p_fin = 50
            else:
                p_fin = 30
    else:
        # financiamento < 0 (saídas: amortização, distribuição)
        if margem_op >= 0.15:
            p_fin = 100
        elif margem_op >= 0.10:
            p_fin = 70
        elif margem_op >= 0.05:
            p_fin = 40
        else:
            p_fin = 10

    # Score Final: pesos conforme metodologia final
    score_final = 0.5 * p_op + 0.3 * p_fin + 0.2 * p_inv
    score_final = round(float(score_final), 1)

    return {
        'score_final': score_final,
        'pontos': {'margem': p_op, 'investimento': p_inv, 'financiamento': p_fin},
        'valores': {'margem_op': margem_op, 'intensidade_inv': intensidade_inv, 'intensidade_fin': intensidade_fin},
        'componentes': {'caixa_operacional': caixa_op, 'caixa_investimento': caixa_inv, 'caixa_financiamento': caixa_fin, 'entradas_operacionais': entradas_op}
    }


# --- 8. FUNÇÃO PARA CRIAR DASHBOARD ---
def criar_dashboard(df: pd.DataFrame):
    """Cria dashboard com gráficos de análise."""
    st.subheader("Dashboard: Análise de Fluxo de Caixa")
    
    if df.empty:
        st.info("Nenhum dado disponível para o dashboard.")
        return

    try:
        # Preparar dados
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
        df.dropna(subset=['data'], inplace=True)
        df['fluxo'] = df.apply(
            lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'],
            axis=1
        )
        df['mes_ano_str'] = df['data'].dt.strftime('%Y-%m')
        
        # Filtrar apenas operações válidas (excluir NEUTRO)
        df_fluxo = df[df['tipo_fluxo'] != 'NEUTRO'].copy()
        
        # 1. Gráfico de Barras por Tipo de Fluxo
        st.markdown("#### Fluxo de Caixa Mensal por Categoria DCF")
        
        df_fluxo_agrupado = df_fluxo.groupby(['mes_ano_str', 'tipo_fluxo'])['fluxo'].sum().reset_index()
        
        fig_dcf = px.bar(
            df_fluxo_agrupado,
            x='mes_ano_str',
            y='fluxo',
            color='tipo_fluxo',
            barmode='group',
            title='Evolução do Fluxo de Caixa por Tipo',
            labels={'fluxo': 'Fluxo (R$)', 'mes_ano_str': 'Mês/Ano', 'tipo_fluxo': 'Tipo de Fluxo'},
            color_discrete_map={
                'OPERACIONAL': ACCENT_COLOR,
                'INVESTIMENTO': INVESTMENT_COLOR,
                'FINANCIAMENTO': FINANCING_COLOR
            }
        )
        fig_dcf.update_layout(height=400, plot_bgcolor='white', font=dict(family="Roboto"))
        st.plotly_chart(fig_dcf, use_container_width=True)
        
        st.markdown("---")

        # 2. Gráfico de Pizza: Caixa Operacional vs Retiradas Pessoais
        st.markdown("#### Comparativo: Caixa Operacional vs Retiradas Pessoais")
        
        caixa_operacional = df_fluxo[df_fluxo['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()
        
        # Retiradas pessoais são da conta FIN-05 e devem ser negativas (débitos)
        retiradas_pessoais = abs(df[
            (df['conta_analitica'] == 'FIN-05') & 
            (df['tipo_movimentacao'] == 'DEBITO')
        ]['valor'].sum())
        
        if caixa_operacional > 0 or retiradas_pessoais > 0:
            dados_comparativo = pd.DataFrame({
                'Categoria': ['Caixa Operacional Gerado', 'Retiradas Pessoais (Sócios/Pró-labore)'],
                'Valor': [caixa_operacional, retiradas_pessoais]
            })
            
            fig_comparativo = px.pie(
                dados_comparativo,
                values='Valor',
                names='Categoria',
                title='Distribuição: Geração Operacional vs Retiradas',
                color_discrete_sequence=[ACCENT_COLOR, NEGATIVE_COLOR],
                hole=0.3
            )
            
            fig_comparativo.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Percentual: %{percent}<extra></extra>'
            )
            
            fig_comparativo.update_layout(
                height=400, 
                font=dict(family="Roboto"),
                showlegend=True
            )
            
            st.plotly_chart(fig_comparativo, use_container_width=True)
            
            # Análise contextual
            if caixa_operacional <= 0:
                st.error("🚨 O caixa operacional está negativo — não há sustentabilidade para retiradas pessoais neste período.")
            else:
                percentual_retiradas = (retiradas_pessoais / caixa_operacional * 100)
                if percentual_retiradas > 80:
                    st.warning("⚠️ As retiradas pessoais representam mais de 80% do caixa operacional. Avalie a sustentabilidade do negócio.")
                elif percentual_retiradas > 50:
                    st.info("ℹ️ As retiradas pessoais consomem mais de 50% do caixa operacional. Monitore a evolução deste indicador.")
                else:
                    st.success("✅ As retiradas pessoais estão em nível saudável em relação ao caixa operacional.")
        else:
            st.info("Não há dados suficientes para comparação entre caixa operacional e retiradas pessoais.")
        
        st.markdown("---")
        
        # 3. Distribuição de Despesas por Conta Analítica
        st.markdown("#### Distribuição de Despesas por Conta")
        df_despesas = df_fluxo[df_fluxo['tipo_movimentacao'] == 'DEBITO'].groupby('nome_conta')['valor'].sum().reset_index()
        df_despesas = df_despesas.sort_values('valor', ascending=False).head(10)
        
        if not df_despesas.empty:
            fig_pie = px.pie(
                df_despesas,
                values='valor',
                names='nome_conta',
                title='Top 10 Categorias de Despesas',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_layout(height=400, font=dict(family="Roboto"))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Nenhuma despesa encontrada para distribuição.")

    except Exception as e:
        import traceback
        st.error(f"Erro ao gerar o dashboard: {e}")
        st.code(f"Detalhes do erro:\n{traceback.format_exc()}")

# --- 9. FUNÇÃO DE CABEÇALHO ---
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

# --- 10. INTERFACE STREAMLIT PRINCIPAL ---
load_header()

st.sidebar.title("Navegação")
page = st.sidebar.radio("Seções", ["Upload e Extração", "Revisão de Dados", "Dashboard & Relatórios"])

if page == "Upload e Extração":
    st.markdown("### 1. Upload e Extração de Dados")
    st.markdown("Faça o upload dos extratos em PDF. O sistema irá extrair as transações e classificá-las conforme o plano de contas.")

    with st.expander("Plano de Contas Utilizado", expanded=False):
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            st.markdown(f"**{sintetico['codigo']} - {sintetico['nome']}** ({sintetico['tipo_fluxo']})")
            for conta in sintetico["contas"]:
                st.markdown(f"  - `{conta['codigo']}`: {conta['nome']}")

    with st.expander("Upload de Arquivos", expanded=True):
        uploaded_files = st.file_uploader(
            "Selecione os arquivos PDF dos seus extratos bancários",
            type="pdf",
            accept_multiple_files=True,
            key="pdf_uploader",
            help="Os PDFs devem ter texto selecionável."
        )

    if uploaded_files:
        if st.button(f"Executar Extração e Classificação ({len(uploaded_files)} arquivos)", key="analyze_btn"):
            todas_transacoes = []
            extraction_status = st.status("Iniciando extração e classificação...", expanded=True)
            
            for i, uploaded_file in enumerate(uploaded_files):
                extraction_status.write(f"Extraindo dados do arquivo {i+1} de {len(uploaded_files)}: **{uploaded_file.name}**")
                pdf_bytes = uploaded_file.getvalue()
                
                with extraction_status:
                    dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name, client)
                
                todas_transacoes.extend(dados_dict['transacoes'])
            
            df_transacoes = pd.DataFrame(todas_transacoes)
            
            if df_transacoes.empty:
                extraction_status.error("❌ Nenhuma transação válida foi extraída.")
                st.session_state['df_transacoes_editado'] = pd.DataFrame()
            else:
                extraction_status.update(
                    label=f"✅ Extração de {len(todas_transacoes)} transações concluída!", 
                    state="complete", 
                    expanded=False
                )
                
                df_transacoes['valor'] = pd.to_numeric(df_transacoes['valor'], errors='coerce').fillna(0)
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'], errors='coerce', dayfirst=True)
                df_transacoes['tipo_movimentacao'] = df_transacoes['tipo_movimentacao'].fillna('DEBITO')
                df_transacoes['conta_analitica'] = df_transacoes['conta_analitica'].fillna('NE-02')
                
                # Enriquecer com plano de contas
                df_transacoes = enriquecer_com_plano_contas(df_transacoes)
                
                st.session_state['df_transacoes_editado'] = df_transacoes
                st.rerun()

elif page == "Revisão de Dados":
    st.markdown("### 2. Revisão e Correção Manual dos Dados")
    
    if not st.session_state['df_transacoes_editado'].empty:
        st.info("⚠️ **IMPORTANTE:** Revise as classificações e corrija manualmente qualquer erro.")
        
        # Preparar opções de contas para o editor
        opcoes_contas = []
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            for conta in sintetico["contas"]:
                opcoes_contas.append(conta["codigo"])
        
        with st.expander("Editar Transações", expanded=True):
            edited_df = st.data_editor(
                st.session_state['df_transacoes_editado'][
                    ['data', 'descricao', 'valor', 'tipo_movimentacao', 'conta_analitica', 'nome_conta', 'tipo_fluxo']
                ],
                width='stretch',
                column_config={
                    "data": st.column_config.DateColumn("Data", format="YYYY-MM-DD", required=True),
                    "descricao": st.column_config.TextColumn("Descrição", width="large"),
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                    "tipo_movimentacao": st.column_config.SelectboxColumn(
                        "Tipo", 
                        options=["CREDITO", "DEBITO"], 
                        required=True
                    ),
                    "conta_analitica": st.column_config.SelectboxColumn(
                        "Conta Analítica", 
                        options=opcoes_contas, 
                        required=True
                    ),
                    "nome_conta": st.column_config.TextColumn("Nome da Conta", disabled=True),
                    "tipo_fluxo": st.column_config.TextColumn("Tipo de Fluxo", disabled=True),
                },
                num_rows="dynamic",
                key="data_editor_transacoes"
            )
        
        if st.button("Confirmar Dados e Gerar Relatórios", key="generate_report_btn"):
            # Enriquecer novamente após edições
            edited_df = enriquecer_com_plano_contas(edited_df)
            st.session_state['df_transacoes_editado'] = edited_df
            st.success("✅ Dados confirmados! Acesse a seção **Dashboard & Relatórios** para ver as análises.")
    else:
        st.warning("Nenhum dado processado encontrado. Volte para a seção **Upload e Extração**.")


elif page == "Dashboard & Relatórios":
    st.markdown("### 3. Relatórios Gerenciais e Dashboard")
    
    if not st.session_state['df_transacoes_editado'].empty:
        df_final = st.session_state['df_transacoes_editado'].copy()

        # ------- CÁLCULO E EXIBIÇÃO DO SCORE FINANCEIRO -------
        try:
            resultado_score = calcular_score_fluxo(df_final)
            score = resultado_score['score_final']
            margem_op = resultado_score['valores']['margem_op']
            i_inv = resultado_score['valores']['intensidade_inv']
            i_fin = resultado_score['valores']['intensidade_fin']

            
            # --- NOVO CÁLCULO DE INDICADORES (baseado em média mensal) ---
            df_final["Data"] = pd.to_datetime(df_final["Data"], errors="coerce")
            df_final["mes_ano"] = df_final["Data"].dt.to_period("M")

            indicadores_mensais = []
            for mes, grupo in df_final.groupby("mes_ano"):
                caixa_op = grupo.loc[grupo["Grupo"] == "Operacional", "Valor"].sum()
                caixa_inv = grupo.loc[grupo["Grupo"] == "Investimento", "Valor"].sum()
                caixa_fin = grupo.loc[grupo["Grupo"] == "Financiamento", "Valor"].sum()
                entradas_op = grupo.loc[(grupo["Grupo"] == "Operacional") & (grupo["Valor"] > 0), "Valor"].sum()

                margem_op = (caixa_op / entradas_op) if entradas_op != 0 else 0
                intensidade_inv = (caixa_inv / caixa_op) if caixa_op != 0 else 0
                intensidade_fin = (caixa_fin / caixa_op) if caixa_op != 0 else 0

                indicadores_mensais.append({
                    "Mes": str(mes),
                    "Margem de Caixa Operacional (%)": margem_op,
                    "Intensidade de Investimento (%)": intensidade_inv,
                    "Intensidade de Financiamento (%)": intensidade_fin
                })

            df_indicadores = pd.DataFrame(indicadores_mensais)

            # Cálculo das médias mensais (para exibição no topo do dashboard)
            margem_media = df_indicadores["Margem de Caixa Operacional (%)"].mean()
            inv_media = df_indicadores["Intensidade de Investimento (%)"].mean()
            fin_media = df_indicadores["Intensidade de Financiamento (%)"].mean()
            
            # --- BLOCO DE MÉTRICAS (usando médias mensais) ---
            st.markdown("#### 📊 Indicadores-Chave de Performance (KPI)")
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)

            with col_s1:
                st.metric("🔹 Score Financeiro (0–100)", f"{score:.1f}")
            with col_s2:
                st.metric("🏦 Margem de Caixa Operacional (média)", f"{margem_media:.1%}")
            with col_s3:
                st.metric("💰 Intensidade de Investimento (média)", f"{inv_media:.1%}")
            with col_s4:
                st.metric("📈 Intensidade de Financiamento (média)", f"{fin_media:.1%}" if pd.notna(fin_media) else "—")

            st.markdown('---')

        except Exception as e:
            st.error(f"Erro ao calcular o score: {e}")

        # ------- RELATÓRIOS E GRÁFICOS -------
        criar_relatorio_fluxo_caixa(df_final)
        criar_grafico_indicadores(df_final)
        criar_dashboard(df_final)

        # ------- EXPORTAÇÃO -------
        st.markdown("---")
        st.markdown("##### 📤 Exportar Dados")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Baixar Transações Detalhadas (CSV)"):
                csv = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Baixar CSV de Transações",
                    data=csv,
                    file_name="transacoes_hedgewise.csv",
                    mime="text/csv"
                )

    else:
        st.warning("Nenhum dado processado encontrado. Volte para a seção **Upload e Extração**.")

# --- Rodapé ---
st.markdown("---")
try:
    footer_logo = Image.open(LOGO_FILENAME)
    footer_col1, footer_col2 = st.columns([1, 35])
    with footer_col1:
        st.image(footer_logo, width=40)
    with footer_col2:
        st.markdown("""<p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 15px;">
        Análise de Extrato Empresarial | Dados extraídos e classificados com IA usando Plano de Contas estruturado.
        </p>""", unsafe_allow_html=True)
except Exception:
    st.markdown("""<p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 15px;">
    Análise de Extrato Empresarial | Dados extraídos e classificados com IA usando Plano de Contas estruturado.
    </p>""", unsafe_allow_html=True)

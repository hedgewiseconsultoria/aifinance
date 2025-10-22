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
import plotly.express as px  # Adicionado para gráficos interativos mais profissionais

# --- FUNÇÃO DE FORMATAÇÃO BRL ---
def formatar_brl(valor: float) -> str:
    """
    Formata um valor float para a moeda Real Brasileiro (R$ xx.xxx,xx).
    """
    valor_us = f"{valor:,.2f}"
    
    # 1. Troca o separador de milhares US (vírgula) por um temporário
    valor_brl = valor_us.replace(",", "TEMP_SEP")
    
    # 2. Troca o separador decimal US (ponto) por vírgula BR
    valor_brl = valor_brl.replace(".", ",")
    
    # 3. Troca o separador temporário por ponto BR (milhares)
    valor_brl = valor_brl.replace("TEMP_SEP", ".")
    
    return "R$ " + valor_brl


# --- 1. CONFIGURAÇÃO DE SEGURANÇA E TEMA ---

PRIMARY_COLOR = "#0A2342"   # Azul Marinho Escuro
SECONDARY_COLOR = "#000000" # Preto
BACKGROUND_COLOR = "#F0F2F6" # Cinza Claro
ACCENT_COLOR = "#007BFF" # Azul de Destaque (Gráfico Operacional)
NEGATIVE_COLOR = "#DC3545" # Vermelho (Gráfico Pessoal)
FINANCING_COLOR = "#FFC107" # Amarelo/Dourado

LOGO_FILENAME = "logo_hedgewise.png" 

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"  # Sidebar expandida por padrão para navegação
)

# Adiciona CSS customizado para o tema - Expandido para mais profissionalismo
st.markdown(
    f"""
    <style>
        /* Fundo da Aplicação */
        .stApp {{
            background-color: {BACKGROUND_COLOR};
        }}
        /* Sidebar */
        [data-testid="stSidebar"] {{
            background-color: white;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        [data-testid="stSidebar"] .stButton>button {{
            width: 100%;
            margin-bottom: 10px;
        }}
        /* Header Principal */
        .main-header {{
            color: {SECONDARY_COLOR};
            font-size: 2.5em;
            padding-bottom: 10px;
        }}
        /* Container dos Widgets/KPIs - Estilo de Card Profissional */
        .kpi-container {{
            background-color: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 6px 15px 0 rgba(0, 0, 0, 0.08);
            margin-bottom: 20px;
            height: 100%;
        }}
        /* Estilos de Métricas */
        [data-testid="stMetricLabel"] label {{
            font-weight: 600 !important;
            color: #6c757d;
        }}
        [data-testid="stMetricValue"] {{
            font-size: 1.8em !important;
            color: {SECONDARY_COLOR};
        }}
        /* Estilo para Abas (Tabs) */
        button[data-baseweb="tab"] {{
            color: #6c757d;
            border-bottom: 2px solid transparent;
            font-weight: 600;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {PRIMARY_COLOR};
            border-bottom: 3px solid {PRIMARY_COLOR} !important;
        }}
        /* Títulos */
        h2 {{
            color: {PRIMARY_COLOR};
            border-left: 5px solid {PRIMARY_COLOR};
            padding-left: 10px;
            margin-top: 20px;
            margin-bottom: 20px;
        }}
        /* Botões */
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
        /* CORREÇÃO DO RELATÓRIO FINAL: Garante fundo BRANCO e cor PRETA */
        .report-textarea > div > label {{
            display: none; /* Remove o label do text_area */
        }}
        .report-textarea > div > div {{
            background-color: white !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
            font-family: Roboto, sans-serif !important; 
            font-size: 1.0em !important;
            color: #000000 !important; 
            border: 1px solid #ddd;
        }}
        .report-textarea textarea {{
             color: #000000 !important; 
             background-color: white !important; /* Garante o fundo branco */
        }}
        
        /* NOVO: CORREÇÃO DO CAMPO CONTEXTO ADICIONAL PARA BRANCO */
        .context-input > div > textarea {{
            background-color: white !important;
            color: #000000 !important;
            border: 1px solid #ddd !important;
        }}
        /* Gráficos */
        .stPlotlyChart {{
            border-radius: 8px;
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
if 'relatorio_consolidado' not in st.session_state:
    st.session_state['relatorio_consolidado'] = "Aguardando análise de dados..."
if 'contexto_adicional' not in st.session_state:
    st.session_state['contexto_adicional'] = ""

# Inicializa o cliente Gemini
try:
    # A API key deve estar em st.secrets
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
    categoria_sugerida: str = Field(description="Sugestão de categoria mais relevante (Ex: Alimentação, Salário, Investimento, Serviço).")
    categoria_dcf: str = Field(description="Classificação DCF: 'OPERACIONAL', 'INVESTIMENTO' ou 'FINANCIAMENTO'.")
    entidade: str = Field(description="Classificação binária: 'EMPRESARIAL' ou 'PESSOAL'.")

class AnaliseCompleta(BaseModel):
    """Contém a lista de transações E o relatório de análise inicial."""
    transacoes: List[Transacao] = Field(description="Uma lista de objetos 'Transacao' extraídos do documento.")
    relatorio_inicial: str = Field(description="Confirmação de extração dos dados deste extrato. Use: 'Extração concluída. Saldo final: [Valor Formatado em BRL].'")
    saldo_final: float = Field(description="O saldo final da conta no extrato. Use zero se não for encontrado.")


# --- 3. FUNÇÃO DE CHAMADA DA API PARA EXTRAÇÃO ---

@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
    """Chama a Gemini API para extrair dados estruturados e classificar DCF e Entidade."""
    
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    prompt_analise = (
        f"Você é um especialista em extração e classificação de dados financeiros. "
        f"Extraia todas as transações deste extrato bancário em PDF ('{filename}') e "
        "classifique cada transação rigorosamente nas categorias 'categoria_dcf' (OPERACIONAL, INVESTIMENTO, FINANCIAMENTO) "
        "e 'entidade' (EMPRESARIAL ou PESSOAL). "
        "A maioria das movimentações deve ser EMPRESARIAL, mas retiradas de sócios ou gastos pessoais devem ser PESSOAL. "
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
            st.error(f"⚠️ ERRO DE CAPACIDADE DA API: O modelo Gemini está sobrecarregado (503 UNAVAILABLE) ao processar {filename}.")
            st.info("Este é um erro temporário do servidor da API. Por favor, tente novamente em alguns minutos.")
        else:
            print(f"Erro ao chamar a Gemini API para {filename}: {error_message}")

        return {
            'transacoes': [], 
            'saldo_final': 0.0, 
            'relatorio_inicial': f"**Falha na Extração:** Ocorreu um erro ao processar o arquivo {filename}. Motivo: {error_message}"
        }


# --- 3.1. FUNÇÃO DE GERAÇÃO DE RELATÓRIO CONSOLIDADO (ECONÔMICO) ---

def gerar_relatorio_final_economico(df_transacoes: pd.DataFrame, contexto_adicional: str, client: genai.Client) -> str:
    """Gera o relatório final, enviando apenas os KPIs e a distribuição de fluxo (texto/tabela)."""
    
    # 1. Pré-cálculo dos KPIs no Python 
    df_transacoes['fluxo'] = df_transacoes.apply(
        lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], 
        axis=1
    )
    resumo_dcf = df_transacoes.groupby('categoria_dcf')['fluxo'].sum()
    resumo_entidade = df_transacoes.groupby('entidade')['fluxo'].sum()
    saldo_operacional = resumo_dcf.get('OPERACIONAL', 0.0)
    
    texto_resumo = f"""
    1. Saldo Líquido do Período: {formatar_brl(df_transacoes['fluxo'].sum())}
    2. Saldo Operacional (DCF): {formatar_brl(saldo_operacional)}
    3. Resumo por Entidade (Fluxo):
       - Empresarial: {formatar_brl(resumo_entidade.get('EMPRESARIAL', 0.0))}
       - Pessoal (Retiradas): {formatar_brl(resumo_entidade.get('PESSOAL', 0.0))}
    4. Distribuição por DCF (Fluxo):
       - Operacional: {formatar_brl(resumo_dcf.get('OPERACIONAL', 0.0))}
       - Investimento: {formatar_brl(resumo_dcf.get('INVESTIMENTO', 0.0))}
       - Financiamento: {formatar_brl(resumo_dcf.get('FINANCIAMENTO', 0.0))}
    """
    
    contexto_prompt = ""
    if contexto_adicional:
        contexto_prompt = f"\n\n--- CONTEXTO ADICIONAL DO EMPREENDEDOR ---\n{contexto_adicional}\n--- FIM DO CONTEXTO ---\n"
        
    # PROMPT DE RELATÓRIO OTIMIZADO - RIGOROSO CONTRA NEGRITO (**) E TEXTO SIMPLES
    prompt_analise = (
        "Você é um consultor financeiro inteligente especializado em PME (Pequenas e Médias Empresas). "
        "Sua tarefa é analisar os KPIs CALCULADOS e CONSOLIDADOS fornecidos abaixo. "
        "Gere um relatório EXTREMAMENTE CONCISO e ACIONÁVEL, com **no máximo 180 palavras**. "
        
        f"{contexto_prompt}"
        
        "Use o seguinte formato, com quebras de linha (enter) após cada parágrafo. "
        "**NÃO USE NEGRITO (**) ou outros caracteres especiais (exceto R$ e vírgulas) no corpo do texto.** "
        "O texto deve ser plano, simples e sem formatação Markdown. Garanta que o texto siga estritamente este formato: "
        
        "Prezado(a) cliente,\n"
        "Segue análise concisa dos KPIs para sua PME, focada em gestão de caixa e sustentabilidade:\n\n"
        
        "1. Desempenho Operacional: (Comente o saldo líquido gerado pela atividade OPERACIONAL). "
        "2. Análise Pessoal vs. Empresarial: (Comente o impacto do fluxo PESSOAL no caixa. Use o valor R$ X para o pessoal e R$ Y para o operacional). "
        "3. Sugestões Estratégicas: (Sugestões acionáveis para otimizar o capital de giro, focando em Financiamento e Pessoal). "
        "4. Remuneração Ideal / Projeção: (Comente se as retiradas atuais são sustentáveis e estime um valor ideal de pró-labore mensal para os próximos 3 meses. Use o valor R$ Z)."
        
        "Use o formato brasileiro (ponto para milhares e vírgula para decimais) e o prefixo R$."
        
        "\n\n--- DADOS CONSOLIDADOS (KPIs) ---\n"
        f"{texto_resumo}"
    )
    
    config = types.GenerateContentConfig(temperature=0.4)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[prompt_analise], 
            config=config,
        )
        return response.text
    except Exception as e:
        return f"**Falha na Geração do Relatório Consolidado:** Ocorreu um erro ao gerar o relatório analítico. Motivo: {e}"

# --- 4. FUNÇÃO DE CABEÇALHO ---
def load_header():
    try:
        logo = Image.open(LOGO_FILENAME)
        col1, col2 = st.columns([1, 6])
        with col1:
            st.image(logo, width=100)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("O horizonte do pequeno empreendedor")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")


# --- 5. FUNÇÃO PARA CRIAR GRÁFICOS DO DASHBOARD (MELHORADA) ---

def criar_dashboard(df: pd.DataFrame):
    """
    Cria um dashboard enriquecido com múltiplas visualizações interativas usando Plotly para profissionalismo.
    - Gráfico de linha DCF (mantido, mas com Plotly para interatividade)
    - Pie chart para distribuição de categorias sugeridas
    - Bar chart agrupado para fluxo por entidade e mês
    """
    st.subheader("Dashboard: Análise de Fluxo de Caixa")
    
    if df.empty:
        st.info("Nenhum dado disponível para o dashboard. Por favor, analise e confirme as transações na aba anterior.")
        return

    try:
        # 1. Pré-processamento e Cálculo do Fluxo
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True) 
        df.dropna(subset=['data'], inplace=True)
        
        df['fluxo'] = df.apply(
            lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], 
            axis=1
        )

        df['mes_ano_str'] = df['data'].dt.strftime('%Y-%m')
        
        # 2. Gráfico de Linha DCF com Plotly para interatividade
        st.markdown("### Comparativo Mensal de Fluxo de Caixa pelo Método DCF")
        
        df_dcf_agrupado = df.groupby(['mes_ano_str', 'categoria_dcf'])['fluxo'].sum().reset_index()
        
        fig_dcf = px.line(
            df_dcf_agrupado, 
            x='mes_ano_str', 
            y='fluxo', 
            color='categoria_dcf',
            title='Fluxo de Caixa por DCF',
            labels={'fluxo': 'Fluxo (R$)', 'mes_ano_str': 'Mês/Ano', 'categoria_dcf': 'Categoria DCF'},
            color_discrete_map={
                'OPERACIONAL': ACCENT_COLOR,
                'INVESTIMENTO': PRIMARY_COLOR,
                'FINANCIAMENTO': FINANCING_COLOR
            }
        )
        fig_dcf.update_layout(height=400, plot_bgcolor='white', font=dict(family="Roboto"))
        st.plotly_chart(fig_dcf, use_container_width=True)
        st.caption("O fluxo **OPERACIONAL** é o principal indicador de saúde (o negócio em si).")

        # 3. Novo: Pie Chart para Distribuição de Categorias Sugeridas (Despesas)
        st.markdown("### Distribuição de Despesas por Categoria Sugerida")
        df_despesas = df[df['tipo_movimentacao'] == 'DEBITO'].groupby('categoria_sugerida')['valor'].sum().reset_index()
        if not df_despesas.empty:
            fig_pie = px.pie(
                df_despesas, 
                values='valor', 
                names='categoria_sugerida',
                title='Distribuição de Despesas',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_layout(height=400, font=dict(family="Roboto"))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Nenhuma despesa encontrada para distribuição.")

        # 4. Novo: Bar Chart Agrupado para Fluxo por Entidade e Mês
        st.markdown("### Fluxo por Entidade (Empresarial vs. Pessoal)")
        df_entidade_agrupado = df.groupby(['mes_ano_str', 'entidade'])['fluxo'].sum().reset_index()
        fig_bar = px.bar(
            df_entidade_agrupado, 
            x='mes_ano_str', 
            y='fluxo', 
            color='entidade',
            barmode='group',
            title='Fluxo por Entidade',
            labels={'fluxo': 'Fluxo (R$)', 'mes_ano_str': 'Mês/Ano', 'entidade': 'Entidade'},
            color_discrete_map={
                'EMPRESARIAL': ACCENT_COLOR,
                'PESSOAL': NEGATIVE_COLOR
            }
        )
        fig_bar.update_layout(height=400, plot_bgcolor='white', font=dict(family="Roboto"))
        st.plotly_chart(fig_bar, use_container_width=True)
        st.caption("Analise o impacto das retiradas pessoais no fluxo empresarial.")

    except Exception as e:
        import traceback
        st.error(f"Erro ao gerar o dashboard: {e}")
        st.code(f"Detalhes do erro:\n{traceback.format_exc()}")


# --- 6. INTERFACE STREAMLIT PRINCIPAL ---

load_header()

# Sidebar para navegação profissional
st.sidebar.title("Navegação")
page = st.sidebar.radio("Seções", ["Upload e Extração", "Revisão de Dados", "Dashboard & Relatórios"])

if page == "Upload e Extração":
    st.markdown("## 1. Upload e Extração de Dados")
    st.markdown("Faça o upload dos extratos em PDF. O sistema irá extrair as transações e classificá-las em DCF e Entidade (Empresarial/Pessoal).")

    col_upload, col_contexto = st.columns([1, 1])
    
    with col_upload:
        uploaded_files = st.file_uploader(
            "Selecione os arquivos PDF dos seus extratos bancários",
            type="pdf",
            accept_multiple_files=True,
            key="pdf_uploader",
            help="Os PDFs devem ter texto selecionável. Você pode selecionar múltiplos arquivos para uma análise consolidada."
        )

    with col_contexto:
        # APLICAÇÃO DA CLASSE CSS PARA MUDAR O FUNDO PARA BRANCO
        st.markdown('<div class="context-input">', unsafe_allow_html=True)
        contexto_adicional_input = st.text_area(
            "2. Contexto Adicional para a Análise (Opcional)",
            value=st.session_state.get('contexto_adicional', ''), 
            placeholder="Ex: 'Todos os depósitos em dinheiro (cash) são provenientes de vendas diretas.'",
            key="contexto_input",
            help="Use este campo para fornecer à IA informações contextuais que não estão nos extratos."
        )
        st.markdown('</div>', unsafe_allow_html=True)


    if contexto_adicional_input != st.session_state.get('contexto_adicional', ''):
        st.session_state['contexto_adicional'] = contexto_adicional_input

    if uploaded_files: 
        
        if st.button(f"3. Executar Extração e Classificação ({len(uploaded_files)} arquivos)", key="analyze_btn"):
            
            todas_transacoes = []
            saldos_finais = 0.0
            
            extraction_status = st.status("Iniciando extração e classificação...", expanded=True)
            
            for i, uploaded_file in enumerate(uploaded_files):
                extraction_status.write(f"Extraindo dados do arquivo {i+1} de {len(uploaded_files)}: **{uploaded_file.name}**")
                
                pdf_bytes = uploaded_file.getvalue()
                with extraction_status:
                    dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name, client)

                todas_transacoes.extend(dados_dict['transacoes'])
                saldos_finais += dados_dict['saldo_final']
            
            df_transacoes = pd.DataFrame(todas_transacoes)
            
            if df_transacoes.empty:
                extraction_status.error("❌ Nenhuma transação válida foi extraída. Verifique as mensagens de erro acima.")
                st.session_state['df_transacoes_editado'] = pd.DataFrame()
            else:
                extraction_status.update(label=f"✅ Extração de {len(todas_transacoes)} transações concluída!", state="complete", expanded=False)
                
                df_transacoes['valor'] = pd.to_numeric(df_transacoes['valor'], errors='coerce').fillna(0)
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'], errors='coerce', dayfirst=True)
                
                # Limpeza e garantia de tipos
                df_transacoes['tipo_movimentacao'] = df_transacoes['tipo_movimentacao'].fillna('DEBITO')
                df_transacoes['entidade'] = df_transacoes['entidade'].fillna('EMPRESARIAL')
                df_transacoes['categoria_dcf'] = df_transacoes['categoria_dcf'].fillna('OPERACIONAL')
                
                st.session_state['df_transacoes_editado'] = df_transacoes
                st.session_state['saldos_finais'] = saldos_finais
                st.session_state['relatorio_consolidado'] = "Aguardando geração do relatório..."
                
                st.rerun()

elif page == "Revisão de Dados":
    if not st.session_state['df_transacoes_editado'].empty:
        
        st.markdown("---")
        st.markdown("## 4. Revisão e Correção Manual dos Dados")
        st.info("⚠️ **IMPORTANTE:** Revise as colunas **'Entidade'** (Empresarial/Pessoal) e **'Classificação DCF'** e corrija manualmente qualquer erro.")
        
        edited_df = st.data_editor(
            st.session_state['df_transacoes_editado'],
            width='stretch',
            column_config={
                "data": st.column_config.DateColumn("Data", format="YYYY-MM-DD", required=True),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %0.2f", required=True), 
                "tipo_movimentacao": st.column_config.SelectboxColumn("Tipo", options=["CREDITO", "DEBITO"], required=True),
                "categoria_dcf": st.column_config.SelectboxColumn("Classificação DCF", options=["OPERACIONAL", "INVESTIMENTO", "FINANCIAMENTO"], required=True),
                "entidade": st.column_config.SelectboxColumn("Entidade", options=["EMPRESARIAL", "PESSOAL"], required=True),
            },
            num_rows="dynamic",
            key="data_editor_transacoes"
        )

        if st.button("5. Gerar Relatório e Dashboard com Dados Corrigidos", key="generate_report_btn"):
            
            st.session_state['df_transacoes_editado'] = edited_df
            
            with st.spinner("Gerando Relatório de Análise Consolidada..."):
                relatorio_consolidado = gerar_relatorio_final_economico(
                    edited_df, 
                    st.session_state.get('contexto_adicional', ''), 
                    client
                )
            
            st.session_state['relatorio_consolidado'] = relatorio_consolidado
            
            st.success("Relatório gerado! Acesse a seção **Dashboard & Relatórios** para ver os gráficos e a análise completa.")
        
        
        elif uploaded_files and 'df_transacoes_editado' not in st.session_state:
            st.info("Pressione o botão 'Executar Extração e Classificação' para iniciar a análise.")
    else:
        st.warning("Nenhum dado processado encontrado. Volte para a seção **Upload e Extração** e execute a extração dos seus arquivos PDF.")

elif page == "Dashboard & Relatórios":
    st.markdown("## 6. Relatórios Gerenciais e Dashboard")

    if not st.session_state['df_transacoes_editado'].empty:
        df_final = st.session_state['df_transacoes_editado']
        
        # --- Exibição de KPIs Consolidados ---
        total_credito = df_final[df_final['tipo_movimentacao'] == 'CREDITO']['valor'].sum()
        total_debito = df_final[df_final['tipo_movimentacao'] == 'DEBITO']['valor'].sum()
        saldo_periodo = total_credito - total_debito
        
        st.markdown("### Resumo Financeiro CONSOLIDADO do Período (Pós-Correção)")
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        
        with kpi_col1:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            st.metric("Total de Créditos", formatar_brl(total_credito)) 
            st.markdown('</div>', unsafe_allow_html=True)

        with kpi_col2:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            st.metric("Total de Débitos", formatar_brl(total_debito))
            st.markdown('</div>', unsafe_allow_html=True)

        with kpi_col3:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            delta_color = "normal" if saldo_periodo >= 0 else "inverse"
            st.metric("Resultado do Período", formatar_brl(saldo_periodo), delta_color=delta_color)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")

        # 6.1. Exibe o Relatório de Análise (Fundo BRANCO, Sem Label)
        if st.session_state['relatorio_consolidado'] and st.session_state['relatorio_consolidado'] not in ["Aguardando análise de dados...", "Aguardando geração do relatório..."]:
            st.subheader("Relatório de Análise Consolidada")
            
            st.markdown('<div class="report-textarea">', unsafe_allow_html=True)
            st.text_area(
                label="", # Label vazio
                value=st.session_state['relatorio_consolidado'], 
                height=300, 
                key="final_report_display", 
                disabled=True
            )
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")
        else:
            st.warning("Pressione o botão **'Gerar Relatório e Dashboard com Dados Corrigidos'** na seção anterior para gerar a análise em texto.")
            st.markdown("---")

        # 6.2. Cria os Gráficos Enriquecidos
        criar_dashboard(df_final)
        
        # Novo: Botão para Exportar Relatório
        if st.button("Exportar Relatório como CSV"):
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar CSV",
                data=csv,
                file_name="relatorio_hedgewise.csv",
                mime="text/csv"
            )
    else:
        st.warning("Nenhum dado processado encontrado. Volte para a seção **Upload e Extração** e execute a extração dos seus arquivos PDF.")

# --- Rodapé ---
st.markdown("---")
try:
    footer_logo = Image.open(LOGO_FILENAME)
    footer_col1, footer_col2 = st.columns([1, 4]) 
    with footer_col1:
        st.image(footer_logo, width=40)
    with footer_col2:
        st.markdown("""<p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 5px;">Análise de Extrato Empresarial | Dados extraídos e classificados com IA.</p>""", unsafe_allow_html=True)
except Exception:
    st.markdown("""<p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 10px;">Análise de Extrato Empresarial | Dados extraídos e classificados com IA.</p>""", unsafe_allow_html=True)

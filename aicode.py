import streamlit as st
import pandas as pd
import json
import io
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai
from google.genai import types
import calendar

# --- FUNÇÃO DE FORMATAÇÃO BRL (MANTIDA) ---
def formatar_brl(valor: float) -> str:
    """
    Formata um valor float para a moeda Real Brasileiro (R$ xx.xxx,xx).
    """
    # Usa a formatação nativa (locale) com uma abordagem manual simples
    # para garantir a portabilidade do separador de milhares (ponto) 
    # e separador decimal (vírgula).
    valor_us = f"{valor:,.2f}"
    
    # 1. Troca o separador de milhares US (vírgula) por um temporário
    valor_brl = valor_us.replace(",", "TEMP_SEP")
    
    # 2. Troca o separador decimal US (ponto) por vírgula BR
    valor_brl = valor_brl.replace(".", ",")
    
    # 3. Troca o separador temporário por ponto BR (milhares)
    valor_brl = valor_brl.replace("TEMP_SEP", ".")
    
    return "R$ " + valor_brl
# --- FIM FUNÇÃO DE FORMATAÇÃO BRL ---


# --- 1. CONFIGURAÇÃO DE SEGURANÇA E TEMA ---

# Cores baseadas na logo Hedgewise
PRIMARY_COLOR = "#0A2342"   # Azul Marinho Escuro (para botões, links)
SECONDARY_COLOR = "#000000" # Preto (para títulos e texto principal)
BACKGROUND_COLOR = "#F0F2F6" # Cinza Claro (fundo sutil)
ACCENT_COLOR = "#007BFF" # Azul de Destaque para Fluxo Positivo
NEGATIVE_COLOR = "#DC3545" # Vermelho para Fluxo Negativo
FINANCING_COLOR = "#FFC107" # Amarelo/Dourado para Financiamento

# Nome do arquivo da logo no formato PNG
LOGO_FILENAME = "logo_hedgewise.png" 

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="📈",
    layout="wide"
)

# Adiciona CSS customizado para o tema
st.markdown(
    f"""
    <style>
        /* Estilo para o Botão Principal */
        .stButton>button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            border: none;
            transition: background-color 0.3s;
        }}
        .stButton>button:hover {{
            background-color: #1C3757; 
            color: white;
        }}
        /* Fundo da Aplicação */
        .stApp {{
            background-color: {BACKGROUND_COLOR};
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
            box-shadow: 0 6px 15px 0 rgba(0, 0, 0, 0.08); /* Sombra mais suave */
            margin-bottom: 20px;
            height: 100%; /* Garante altura uniforme */
        }}
        /* Estilos de Métricas */
        [data-testid="stMetricLabel"] label {{
            font-weight: 600 !important;
            color: #6c757d; /* Texto cinza suave para a label */
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
    </style>
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
    # Tenta carregar a chave de API dos secrets do Streamlit Cloud
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except (KeyError, AttributeError):
    st.error("ERRO: Chave 'GEMINI_API_KEY' não encontrada nos secrets do Streamlit. Por favor, configure-a para rodar a aplicação.")
    st.stop()


# --- 2. DEFINIÇÃO DO SCHEMA PYDANTIC (Estrutura de Saída ÚNICA E OTIMIZADA) ---

class Transacao(BaseModel):
    """Representa uma única transação no extrato bancário."""
    data: str = Field(
        # OTIMIZAÇÃO: Descrição mais curta
        description="A data da transação no formato 'DD/MM/AAAA'."
    )
    descricao: str = Field(
        description="Descrição detalhada da transação."
    )
    valor: float = Field(
        description="O valor numérico da transação. Sempre positivo."
    )
    tipo_movimentacao: str = Field(
        description="Classificação da movimentação: 'DEBITO' ou 'CREDITO'."
    )
    categoria_sugerida: str = Field(
        # OTIMIZAÇÃO: Exemplos de categorias mais concisos
        description="Sugestão de categoria mais relevante (Ex: Alimentação, Salário, Investimento, Serviço)."
    )
    categoria_dcf: str = Field( 
        description="Classificação DCF: 'OPERACIONAL', 'INVESTIMENTO' ou 'FINANCIAMENTO'."
    )
    entidade: str = Field(
        description="Classificação binária: 'EMPRESARIAL' ou 'PESSOAL'."
    )

class AnaliseCompleta(BaseModel):
    """Contém a lista de transações E o relatório de análise inicial."""
    transacoes: List[Transacao] = Field(
        description="Uma lista de objetos 'Transacao' extraídos do documento."
    )
    relatorio_inicial: str = Field(
        # Instrução para um relatório inicial conciso (confirmação)
        description="Confirmação de extração dos dados deste extrato. Use: 'Extração concluída. Saldo final: [Valor Formatado em BRL].'"
    )
    saldo_final: float = Field(
        description="O saldo final da conta no extrato. Use zero se não for encontrado."
    )


# --- 3. FUNÇÃO DE CHAMADA DA API PARA EXTRAÇÃO E RELATÓRIO INICIAL ---

@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
    """Chama a Gemini API para extrair dados estruturados e classificar DCF e Entidade."""
    
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    # PROMPT DE EXTRAÇÃO OTIMIZADO (FOCADO E CONCISO)
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
        response_schema=AnaliseCompleta, # NOVO SCHEMA
        temperature=0.2 # Baixa temperatura para foco na extração
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
        
        # TRATAMENTO ESPECÍFICO PARA ERRO DE SOBRECARGA DA API (503 UNAVAILABLE)
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
    """Gera o relatório final, enviando apenas os KPIs e a distribuição de fluxo (texto/tabela),
    NÃO O JSON COMPLETO do DataFrame, para máxima economia de tokens."""
    
    # 1. Pré-cálculo dos KPIs no Python (Tokens Zero)
    
    # Cria a coluna de Fluxo
    df_transacoes['fluxo'] = df_transacoes.apply(
        lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], 
        axis=1
    )
    
    # Resumo por DCF e Entidade (o que o LLM precisa analisar)
    resumo_dcf = df_transacoes.groupby('categoria_dcf')['fluxo'].sum()
    resumo_entidade = df_transacoes.groupby('entidade')['fluxo'].sum()
    
    # Cálculo do saldo operacional
    saldo_operacional = resumo_dcf.get('OPERACIONAL', 0.0)
    
    # Geração de texto conciso de contexto para o Prompt
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
        
    # PROMPT DE RELATÓRIO OTIMIZADO (FOCADO EM VALOR DE NEGÓCIOS E CONCISÃO)
    prompt_analise = (
        "Você é um consultor financeiro inteligente especializado em PME (Pequenas e Médias Empresas). "
        "Sua tarefa é analisar os KPIs CALCULADOS e CONSOLIDADOS fornecidos abaixo, que já incorporam as correções do usuário. "
        "Gere um relatório EXTREMAMENTE CONCISO e ACIONÁVEL, com **no máximo 180 palavras**, focado em gestão de caixa e sustentabilidade. "
        
        f"{contexto_prompt}"
        
        "É mandatório que você inclua as seguintes análises, separadas por parágrafos curtos: "
        "1. Desempenho Operacional: Calcule e comente o saldo líquido gerado pela atividade OPERACIONAL (saúde do negócio). "
        "2. Análise Pessoal vs. Empresarial: Comente o impacto do fluxo PESSOAL no caixa. O saldo operacional é suficiente para cobrir as retiradas? "
        "3. Sugestões Estratégicas: Sugestões acionáveis para otimizar o capital de giro, com base nas categorias de maior gasto (se perceptível). "
        "4. Remuneração Ideal / Projeção: Comente se as retiradas atuais são sustentáveis e estime um valor ideal de pró-labore mensal para os próximos 3 meses, sem comprometer o negócio."
        
        # INSTRUÇÃO ADICIONAL PARA EVITAR PROBLEMAS DE FORMATAÇÃO
        "Use apenas texto simples e Markdown básico (como negrito `**`). EVITE listas complexas ou tabelas. Use o formato brasileiro (ponto para milhares e vírgula para decimais) e o prefixo R$."
        
        "\n\n--- DADOS CONSOLIDADOS (KPIs) ---\n"
        f"{texto_resumo}"
    )
    
    config = types.GenerateContentConfig(temperature=0.4)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[prompt_analise], # Chamada muito mais leve (só texto)
            config=config,
        )
        return response.text
    except Exception as e:
        return f"**Falha na Geração do Relatório Consolidado:** Ocorreu um erro ao gerar o relatório analítico. Motivo: {e}"

# --- 4. FUNÇÃO DE CABEÇALHO ---

def load_header():
    """Carrega o logo e exibe o título principal usando st.columns para melhor layout."""
    try:
        # AQUI BUSCA O ARQUIVO .PNG
        logo = Image.open(LOGO_FILENAME)
        
        col1, col2 = st.columns([1, 6])
        
        with col1:
            st.image(logo, width=100)
            
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("O horizonte do pequeno empreendedor")
            
        st.markdown("---")
        
    except FileNotFoundError:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.warning(f"Atenção: O arquivo da logo '{LOGO_FILENAME}' não foi encontrado. O título é exibido sozinho.")
        st.markdown("---")
    except Exception as e:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.error(f"Erro ao carregar a logo: {e}")
        st.markdown("---")


# --- 5. FUNÇÃO PARA CRIAR GRÁFICOS DO DASHBOARD (AJUSTE DO GRÁFICO OPERACIONAL VS PESSOAL) ---

def criar_dashboard(df: pd.DataFrame):
    """
    Cria os gráficos de fluxo de caixa mensal, focando no comparativo Operacional vs. Pessoal.
    """
    st.subheader("Dashboard: Fluxo de Caixa Mensal por Entidade e DCF")
    
    if df.empty:
        st.info("Nenhum dado disponível para o dashboard. Por favor, analise e confirme as transações na aba anterior.")
        return

    try:
        # 1. Pré-processamento e Cálculo do Fluxo
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True) 
        df.dropna(subset=['data'], inplace=True) # Remove linhas com data inválida
        
        # Cria a coluna de Fluxo: Crédito - Débito
        df['fluxo'] = df.apply(
            lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], 
            axis=1
        )

        # FIX: Criar a coluna mes_ano_str aqui para ser usada nos gráficos
        df['mes_ano_str'] = df['data'].dt.to_period('M').astype(str) # Converte para Period e depois para String (YYYY-MM)
        
        # 2. Agrupamento e Pivotação dos Dados para o KPI FOCADO: Operacional Líquido vs. Pessoal
        
        # Filtra e agrupa o Fluxo Operacional (Geração de Caixa da Atividade Principal)
        df_operacional = df[df['categoria_dcf'] == 'OPERACIONAL']
        df_operacional_mensal = df_operacional.groupby('mes_ano_str')['fluxo'].sum().reset_index()
        df_operacional_mensal.rename(columns={'fluxo': 'OPERACIONAL_LIQUIDO'}, inplace=True)

        # Filtra e agrupa o Fluxo Pessoal (Retiradas, o peso do gasto pessoal)
        df_pessoal = df[df['entidade'] == 'PESSOAL']
        df_pessoal_mensal = df_pessoal.groupby('mes_ano_str')['fluxo'].sum().reset_index()
        df_pessoal_mensal.rename(columns={'fluxo': 'FLUXO_PESSOAL'}, inplace=True)
        
        # Junta os dois DataFrames
        df_kpi_comparativo = pd.merge(
            df_operacional_mensal, 
            df_pessoal_mensal, 
            on='mes_ano_str', 
            how='outer'
        ).fillna(0)
        
        # Garante a ordenação
        df_kpi_comparativo.sort_values(by='mes_ano_str', inplace=True)
        df_kpi_comparativo.set_index('mes_ano_str', inplace=True)
        
        # 3. Criação do Primeiro Gráfico (KPI FOCADO: Operacional vs. Pessoal) - GRÁFICO DE BARRAS AGRUPADAS
        st.markdown("### 📊 Geração de Caixa: O Operacional Suporta o Pessoal?")
        st.info("Este gráfico compara o resultado líquido da sua atividade principal (fluxo 'OPERACIONAL') com o total de retiradas e gastos pessoais ('FLUXO PESSOAL') a cada mês.")
        
        st.bar_chart(
            df_kpi_comparativo,
            y=['OPERACIONAL_LIQUIDO', 'FLUXO_PESSOAL'], 
            # Cores: Operacional Positivo (Azul de Destaque) e Pessoal Negativo (Vermelho)
            color=[ACCENT_COLOR, NEGATIVE_COLOR], 
            height=350
        )
        st.caption("O ideal é que o **OPERACIONAL LÍQUIDO** seja significativamente maior (positivo) do que o **FLUXO PESSOAL** (geralmente negativo) para sustentar o capital de giro.")
        
        st.markdown("---")


        # 4. Análise DCF (Gráfico de Linhas - MANTIDO)
        st.markdown("### Comparativo Mensal de Fluxo de Caixa pelo Método DCF (Operacional, Investimento, Financiamento)")
        
        # Agrupamento DCF - Agora usando 'mes_ano_str' que existe em 'df'
        df_dcf_agrupado = df.groupby(['mes_ano_str', 'categoria_dcf'])['fluxo'].sum().reset_index()
        
        # Pivota a tabela para ter categorias DCF como colunas
        df_dcf_pivot = df_dcf_agrupado.pivot(index='mes_ano_str', columns='categoria_dcf', values='fluxo').fillna(0)

        # Garante que as colunas críticas existam e define a ordem
        dcf_columns = ['OPERACIONAL', 'INVESTIMENTO', 'FINANCIAMENTO']
        for col in dcf_columns:
            if col not in df_dcf_pivot.columns:
                df_dcf_pivot[col] = 0.0
                
        # Define as cores para o gráfico de linhas DCF
        DCF_COLORS = [
            PRIMARY_COLOR,  # OPERACIONAL (Azul Escuro)
            ACCENT_COLOR,   # INVESTIMENTO (Azul de Destaque)
            FINANCING_COLOR # FINANCIAMENTO (Amarelo/Warning)
        ]

        st.line_chart(
            df_dcf_pivot[dcf_columns], # Garante a ordem das colunas
            color=DCF_COLORS,
            height=350
        )
        st.caption("O fluxo **OPERACIONAL** é o principal indicador de saúde (o negócio em si). Fluxo de **INVESTIMENTO** mostra o gasto em ativos ou vendas de ativos. Fluxo de **FINANCIAMENTO** mostra entrada/saída de capital de terceiros ou sócios.")


    except Exception as e:
        import traceback
        st.error(f"Erro ao gerar o dashboard: {e}")
        st.code(f"Detalhes do erro:\n{traceback.format_exc()}")


# --- 6. INTERFACE STREAMLIT PRINCIPAL ---

load_header()

tab1, tab2 = st.tabs(["📊 Análise e Correção de Dados", "📈 Dashboard & Fluxo de Caixa"])

with tab1:
    st.markdown("## 1. Upload e Extração de Dados")
    st.markdown("Faça o upload dos extratos em PDF. O sistema irá extrair as transações e classificá-las em DCF e Entidade (Empresarial/Pessoal).")

    col_upload, col_contexto = st.columns([1, 1])
    
    with col_upload:
        # Permite múltiplos arquivos
        uploaded_files = st.file_uploader(
            "Selecione os arquivos PDF dos seus extratos bancários",
            type="pdf",
            accept_multiple_files=True,
            key="pdf_uploader",
            help="Os PDFs devem ter texto selecionável. Você pode selecionar múltiplos arquivos para uma análise consolidada."
        )

    with col_contexto:
        # Caixa de texto para contexto adicional
        contexto_adicional_input = st.text_area(
            "2. Contexto Adicional para a Análise (Opcional)",
            value=st.session_state.get('contexto_adicional', ''), 
            placeholder="Ex: 'Todos os depósitos em dinheiro (cash) são provenientes de vendas diretas.'",
            key="contexto_input",
            help="Use este campo para fornecer à IA informações contextuais que não estão nos extratos."
        )


    # Verifica se o contexto foi alterado e o atualiza no estado
    if contexto_adicional_input != st.session_state.get('contexto_adicional', ''):
        st.session_state['contexto_adicional'] = contexto_adicional_input


    if uploaded_files: # Verifica se há arquivos
        
        # Botão para iniciar a análise
        if st.button(f"3. Executar Extração e Classificação ({len(uploaded_files)} arquivos)", key="analyze_btn"):
            
            # --- Fase de Extração ---
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
            
            # 4. Consolidação e salvamento no estado da sessão
            df_transacoes = pd.DataFrame(todas_transacoes)
            
            if df_transacoes.empty:
                extraction_status.error("❌ Nenhuma transação válida foi extraída. Verifique as mensagens de erro acima.")
                st.session_state['df_transacoes_editado'] = pd.DataFrame()
            else:
                extraction_status.update(label=f"✅ Extração de {len(todas_transacoes)} transações concluída!", state="complete", expanded=False)
                
                # Formatação e ordenação inicial
                df_transacoes['valor'] = pd.to_numeric(df_transacoes['valor'], errors='coerce').fillna(0)
                
                # Converte para datetime e mantém o tipo nativo do Pandas.
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'], errors='coerce', dayfirst=True)
                
                # Limpeza e garantia de tipos (Robustez contra dados faltantes do Gemini)
                df_transacoes['tipo_movimentacao'] = df_transacoes['tipo_movimentacao'].fillna('DEBITO')
                df_transacoes['entidade'] = df_transacoes['entidade'].fillna('EMPRESARIAL') # Default mais seguro
                df_transacoes['categoria_dcf'] = df_transacoes['categoria_dcf'].fillna('OPERACIONAL')
                
                # Armazena o DataFrame extraído para a edição
                st.session_state['df_transacoes_editado'] = df_transacoes
                st.session_state['saldos_finais'] = saldos_finais
                
                # Limpa o relatório antigo
                st.session_state['relatorio_consolidado'] = "Aguardando geração do relatório..."
                
                # Força uma reexecução para renderizar a tabela de edição
                st.rerun()

        
        # --- Fase de Edição e Geração de Relatório ---
        
        if not st.session_state['df_transacoes_editado'].empty:
            
            st.markdown("---")
            st.markdown("## 4. Revisão e Correção Manual dos Dados")
            st.info("⚠️ **IMPORTANTE:** Revise as colunas **'Entidade'** (Empresarial/Pessoal) e **'Classificação DCF'** e corrija manualmente qualquer erro. Estes dados corrigidos serão usados no relatório e Dashboard.")
            
            # st.data_editor permite a edição interativa dos dados
            edited_df = st.data_editor(
                st.session_state['df_transacoes_editado'],
                width='stretch',
                column_config={
                    "data": st.column_config.DateColumn("Data", format="YYYY-MM-DD", required=True),
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %0.2f", required=True), 
                    "tipo_movimentacao": st.column_config.SelectboxColumn(
                        "Tipo", 
                        options=["CREDITO", "DEBITO"], 
                        required=True
                    ),
                    "categoria_dcf": st.column_config.SelectboxColumn(
                        "Classificação DCF", 
                        options=["OPERACIONAL", "INVESTIMENTO", "FINANCIAMENTO"], 
                        required=True
                    ),
                    "entidade": st.column_config.SelectboxColumn(
                        "Entidade", 
                        options=["EMPRESARIAL", "PESSOAL"], 
                        required=True
                    ),
                },
                num_rows="dynamic",
                key="data_editor_transacoes"
            )

            if st.button("5. Gerar Relatório e Dashboard com Dados Corrigidos", key="generate_report_btn"):
                
                # 1. Armazena a versão editada no estado
                st.session_state['df_transacoes_editado'] = edited_df
                
                # 2. Geração do Relatório Consolidado (CHAMADA ÚNICA E ECONÔMICA)
                with st.spinner("Gerando Relatório de Análise Consolidada (com dados corrigidos e KPIs calculados no Python)..."):
                    relatorio_consolidado = gerar_relatorio_final_economico(
                        edited_df, 
                        st.session_state.get('contexto_adicional', ''), 
                        client
                    )
                
                # 3. Armazena o relatório e força o recálculo dos KPIs
                st.session_state['relatorio_consolidado'] = relatorio_consolidado
                
                st.success("Relatório gerado! Acesse a aba **Dashboard & Fluxo de Caixa** para ver os gráficos e a análise completa.")
            
            
            elif uploaded_files and 'df_transacoes_editado' not in st.session_state:
                st.info("Pressione o botão 'Executar Extração e Classificação' para iniciar a análise.")

with tab2:
    st.markdown("## 6. Relatórios Gerenciais e Dashboard")

    if not st.session_state['df_transacoes_editado'].empty:
        df_final = st.session_state['df_transacoes_editado']
        
        # --- Exibição de KPIs Consolidados ---
        
        # Recálculo dos KPIs com os dados mais recentes (editados)
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

        # 6.1. Exibe o Relatório de Análise (COM AJUSTE DE FORMATAÇÃO)
        if st.session_state['relatorio_consolidado'] and st.session_state['relatorio_consolidado'] not in ["Aguardando análise de dados...", "Aguardando geração do relatório..."]:
            st.subheader("Relatório de Análise Consolidada (Texto)")
            
            # **AJUSTE DE FORMATAÇÃO**
            # Usamos um bloco de Markdown com estilo para controlar a exibição do texto
            st.markdown(
                f"""
                <div style="background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                    {st.session_state['relatorio_consolidado']}
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("---")
        else:
            st.warning("Pressione o botão **'Gerar Relatório e Dashboard com Dados Corrigidos'** na aba anterior para gerar a análise em texto.")
            st.markdown("---")

        # 6.2. Cria os Gráficos
        criar_dashboard(df_final)
    else:
        st.warning("Nenhum dado processado encontrado. Volte para a aba **Análise e Correção de Dados** e execute a extração dos seus arquivos PDF.")

# --- Rodapé ---
st.markdown("---")
try:
    footer_logo = Image.open(LOGO_FILENAME)
    
    footer_col1, footer_col2 = st.columns([1, 4]) 
    
    with footer_col1:
        st.image(footer_logo, width=40)
        
    with footer_col2:
        st.markdown(
            """
            <p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 5px;">
                Análise de Extrato Empresarial | Dados extraídos e classificados com IA.
            </p>
            """,
            unsafe_allow_html=True
        )
        
except Exception:
    st.markdown(
        """
        <p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 10px;">
            Análise de Extrato Empresarial | Dados extraídos e classificados com IA.
        </p>
        """,
        unsafe_allow_html=True
    )

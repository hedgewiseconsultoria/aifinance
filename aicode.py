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

# --- 1. CONFIGURAÇÃO DE SEGURANÇA E TEMA ---

# Cores baseadas na logo Hedgewise
PRIMARY_COLOR = "#0A2342"   # Azul Marinho Escuro (para botões, links)
SECONDARY_COLOR = "#000000" # Preto (para títulos e texto principal)
BACKGROUND_COLOR = "#F0F2F6" # Cinza Claro (fundo sutil)
ACCENT_COLOR = "#007BFF" # Azul de Destaque para Fluxo Positivo
NEGATIVE_COLOR = "#DC3545" # Vermelho para Fluxo Negativo

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

# Inicializa o estado da sessão para armazenar o DataFrame
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


# --- 2. DEFINIÇÃO DO SCHEMA PYDANTIC (Estrutura de Saída) ---

class Transacao(BaseModel):
    """Representa uma única transação no extrato bancário."""
    data: str = Field(
        description="A data da transação no formato 'DD/MM/AAAA' ou 'AAAA-MM-DD'."
    )
    descricao: str = Field(
        description="Descrição detalhada da transação, como o nome do estabelecimento ou tipo de serviço."
    )
    valor: float = Field(
        description="O valor numérico da transação. Sempre positivo. Ex: 150.75"
    )
    tipo_movimentacao: str = Field(
        description="Classificação da movimentação: 'DEBITO' ou 'CREDITO'."
    )
    categoria_sugerida: str = Field(
        description="Sugestão de categoria mais relevante para esta transação (Ex: 'Alimentação', 'Transporte', 'Salário', 'Investimento', 'Serviços')."
    )
    categoria_dcf: str = Field( 
        description="Classificação da transação para o Demonstrativo de Fluxo de Caixa (DCF): 'OPERACIONAL', 'INVESTIMENTO' ou 'FINANCIAMENTO'."
    )
    entidade: str = Field(
        description="Classificação binária para identificar a origem/destino da movimentação: 'EMPRESARIAL' (relacionada ao negócio) ou 'PESSOAL' (retiradas dos sócios ou gastos pessoais detectados)."
    )

class ExtratoBancarioCompleto(BaseModel):
    """Contém a lista de transações e o relatório de análise."""
    transacoes: List[Transacao] = Field(
        description="Uma lista de objetos 'Transacao' extraídos do documento."
    )
    saldo_final: float = Field(
        description="O saldo final da conta no extrato. Use zero se não for encontrado."
    )
    relatorio_analise: str = Field(
        description="Confirmação de extração dos dados deste extrato. Use 'Extração de dados concluída com sucesso.'"
    )


# --- 3. FUNÇÃO DE CHAMADA DA API PARA EXTRAÇÃO ---

@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
    """Chama a Gemini API para extrair dados estruturados e classificar DCF e Entidade."""
    
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    prompt_analise = (
        f"Você é um especialista em extração e classificação de dados financeiros. "
        f"Seu trabalho é extrair todas as transações deste extrato bancário em PDF do arquivo '{filename}' e "
        "classificar cada transação rigorosamente em uma 'categoria_dcf' ('OPERACIONAL', 'INVESTIMENTO' ou 'FINANCIAMENTO') E "
        "em uma 'entidade' ('EMPRESARIAL' ou 'PESSOAL'). "
        "Use o contexto de que a maioria das movimentações devem ser EMPRESARIAIS, mas qualquer retirada para sócios, pagamento de contas pessoais ou compras não relacionadas ao CNPJ deve ser classificada como PESSOAL. "
        "Não gere relatórios. Preencha apenas a estrutura JSON rigorosamente. "
        "Use sempre o valor positivo para 'valor' e classifique estritamente como 'DEBITO' ou 'CREDITO'."
    )
    
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ExtratoBancarioCompleto,
        temperature=0.2 # Baixa temperatura para foco na extração
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=[pdf_part, prompt_analise],
            config=config,
        )
        
        response_json = json.loads(response.text)
        dados_pydantic = ExtratoBancarioCompleto(**response_json)
        
        return dados_pydantic.model_dump()
    
    except Exception as e:
        error_message = str(e)
        
        # TRATAMENTO ESPECÍFICO PARA ERRO DE SOBRECARGA DA API (503 UNAVAILABLE)
        if "503 UNAVAILABLE" in error_message or "model is overloaded" in error_message:
            st.error(f"⚠️ ERRO DE CAPACIDADE DA API: O modelo Gemini está sobrecarregado (503 UNAVAILABLE) ao processar {filename}.")
            st.info("Este é um erro temporário do servidor da API. Por favor, tente novamente em alguns minutos. O problema não está no seu código ou no seu PDF.")
        else:
            # Erro genérico (API Key errada, PDF ilegível, etc.)
            print(f"Erro ao chamar a Gemini API para {filename}: {error_message}")

        return {
            'transacoes': [], 
            'saldo_final': 0.0, 
            'relatorio_analise': f"**Falha na Extração:** Ocorreu um erro ao processar o arquivo {filename}. Motivo: {error_message}"
        }

# --- 3.1. FUNÇÃO DE GERAÇÃO DE RELATÓRIO CONSOLIDADO ---

def gerar_relatorio_consolidado(df_transacoes: pd.DataFrame, contexto_adicional: str, client: genai.Client) -> str:
    """Gera o relatório de análise consolidado, agora mais conciso e focado no split Entidade/DCF. 
       Aplica filtro de colunas e formatação de data para reduzir o payload de JSON."""
    
    # CRITICAL FIX: Criar uma cópia do DF e formatar/filtrar colunas para reduzir o tamanho do JSON payload
    df_temp = df_transacoes.copy()
    
    # 1. Formatar a data para uma string simples (YYYY-MM-DD) antes de serializar
    df_temp['data'] = df_temp['data'].dt.strftime('%Y-%m-%d')
    
    # 2. Selecionar apenas as colunas essenciais para a análise do LLM
    df_analise = df_temp[['data', 'descricao', 'valor', 'tipo_movimentacao', 
                          'categoria_sugerida', 'categoria_dcf', 'entidade']]
    
    # Gerar o JSON a partir do DF filtrado (muito menor)
    transacoes_json = df_analise.to_json(orient='records', date_format='iso', indent=2)
    
    # Adiciona o contexto do usuário ao prompt
    contexto_prompt = ""
    if contexto_adicional:
        contexto_prompt = f"\n\n--- CONTEXTO ADICIONAL DO EMPREENDEDOR ---\n{contexto_adicional}\n--- FIM DO CONTEXTO ---\n"
    
    # Prompt de relatório ajustado
    prompt_analise = (
        "Você é um analista financeiro de elite, especializado em PME (Pequenas e Médias Empresas). "
        "Seu trabalho é analisar o conjunto de transações CONSOLIDADAS (incluindo as correções manuais do usuário) fornecido abaixo em JSON. "
        "Todas as transações estão classificadas em 'OPERACIONAL', 'INVESTIMENTO', 'FINANCIAMENTO' (DCF) e 'EMPRESARIAL' ou 'PESSOAL' (Entidade). "
        "Gere um relatório de análise EXTREMAMENTE CONCISO, FOCADO E ACIONÁVEL, voltado para a gestão de caixa. "
        
        f"{contexto_prompt}"
        
        "É mandatório que você inclua as seguintes análises, separadas por parágrafos curtos: "
        "1. Desempenho Operacional: Calcule e detalhe o saldo líquido total gerado pela atividade OPERACIONAL. Este é o fluxo de caixa central da empresa. "
        "2. Análise Pessoal vs. Empresarial: Calcule e comente o impacto do fluxo PESSOAL (saídas PESSOAIS, como pró-labore, retiradas indevidas) no caixa da empresa. O saldo operacional foi suficiente para cobrir as retiradas? "
        "3. Sugestões Estratégicas: Sugestões acionáveis para otimizar o capital de giro e melhorar o fluxo operacional com base nas categorias de maior gasto. "
        "Use apenas texto simples e Markdown básico (como negrito `**`). Não use listas, headings ou símbolos de moeda (R$) no corpo do relatório."
        "\n\n--- DADOS CONSOLIDADOS (JSON) ---\n"
        f"{transacoes_json}"
    )
    
    config = types.GenerateContentConfig(temperature=0.4)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=[prompt_analise],
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
            st.markdown('<div class="main-header">Hedgewise</div>', unsafe_allow_html=True)
            st.caption("Análise Financeira Inteligente para PME")
            
        st.markdown("---")
        
    except FileNotFoundError:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.warning(f"Atenção: O arquivo da logo '{LOGO_FILENAME}' não foi encontrado. O título é exibido sozinho.")
        st.markdown("---")
    except Exception as e:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.error(f"Erro ao carregar a logo: {e}")
        st.markdown("---")


# --- 5. FUNÇÃO PARA CRIAR GRÁFICOS DO DASHBOARD ---

def criar_dashboard(df: pd.DataFrame):
    """Cria os gráficos de fluxo de caixa mensal separados por Entidade (Empresarial/Pessoal)."""
    st.subheader("Dashboard: Fluxo de Caixa Mensal por Entidade")
    
    if df.empty:
        st.info("Nenhum dado disponível para o dashboard. Por favor, analise e confirme as transações na aba anterior.")
        return

    try:
        # 1. Pré-processamento e Cálculo do Fluxo
        # Converte a data para datetime e extrai Mês/Ano (garantindo que só datas válidas prossigam)
        # Usa dayfirst=True para tratar formato brasileiro DD/MM/AAAA
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True) 
        df.dropna(subset=['data'], inplace=True) # Remove linhas com data inválida
        df['mes_ano'] = df['data'].dt.to_period('M')

        # Cria a coluna de Fluxo: Crédito - Débito
        df['fluxo'] = df.apply(
            lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], 
            axis=1
        )
        
        # 2. Agrupamento e Pivotação dos Dados
        df_agrupado = df.groupby(['mes_ano', 'entidade'])['fluxo'].sum().reset_index()
        # Formata mes_ano para string para uso no gráfico (YYYY-MM)
        df_agrupado['mes_ano_str'] = df_agrupado['mes_ano'].dt.strftime('%Y-%m')

        # Pivota a tabela para ter Entidades como colunas para o gráfico
        df_pivot = df_agrupado.pivot(index='mes_ano_str', columns='entidade', values='fluxo').fillna(0)

        # Garante que as colunas críticas existam
        required_columns = ['EMPRESARIAL', 'PESSOAL']
        for col in required_columns:
            if col not in df_pivot.columns:
                df_pivot[col] = 0.0
        
        # Reordena o índice para garantir a ordem cronológica
        df_pivot.sort_index(inplace=True)
        
        # 3. Criação do Gráfico (Fluxo de Caixa Mensal)
        st.markdown("### Comparativo Mensal de Fluxo (R$)")
        
        # Calcula o Fluxo de Caixa Total
        df_pivot['Fluxo_Caixa_Total'] = df_pivot['EMPRESARIAL'] + df_pivot['PESSOAL']

        # CORREÇÃO CRÍTICA: st.bar_chart não aceita dicionário para color. 
        # Passamos as colunas Y e uma lista de cores na ordem correta.
        st.bar_chart(
            df_pivot,
            y=['EMPRESARIAL', 'PESSOAL'], # Colunas Y explícitas
            color=[PRIMARY_COLOR, NEGATIVE_COLOR], # Lista de cores na mesma ordem
            height=350
        )
        st.caption("O fluxo **PESSOAL** representa as retiradas ou gastos do sócio (geralmente negativo). O fluxo **EMPRESARIAL** (negócio principal) deve ser positivo.")
        
        
        # Gráfico de Linha (Capacidade de Cobertura)
        st.markdown("### Saldo de Caixa Total no Mês (Empresarial + Pessoal)")
        st.line_chart(
            df_pivot['Fluxo_Caixa_Total'],
            color=ACCENT_COLOR,
            height=350
        )
        st.caption("Linha do tempo: Se o valor estiver acima de zero, o caixa da empresa cresceu no mês. Se estiver abaixo, o caixa diminuiu.")

    except Exception as e:
        st.error(f"Erro ao gerar o dashboard: {e}")
        st.info("Verifique se as colunas 'entidade', 'valor' e 'data' estão preenchidas corretamente no Data Editor.")


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
            value=st.session_state['contexto_adicional'], # Mantém o valor
            placeholder="Ex: 'Todos os depósitos em dinheiro (cash) são provenientes de vendas diretas.'",
            key="contexto_input",
            help="Use este campo para fornecer à IA informações contextuais que não estão nos extratos."
        )


    # Verifica se o contexto foi alterado e o atualiza no estado
    if contexto_adicional_input != st.session_state['contexto_adicional']:
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
                    # Chama a função, que agora é cacheável corretamente
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
                # FIX: Substitui use_container_width=True por width='stretch'
                width='stretch',
                column_config={
                    # Data: Exibida como string, mas formatada para edição
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
                
                # 2. Geração do Relatório Consolidado (SEGUNDA CHAMADA AO GEMINI)
                with st.spinner("Gerando Relatório de Análise Consolidada (usando dados corrigidos)..."):
                    relatorio_consolidado = gerar_relatorio_consolidado(
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
            st.metric("Total de Créditos", f"R$ {total_credito:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)

        with kpi_col2:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            st.metric("Total de Débitos", f"R$ {total_debito:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)

        with kpi_col3:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            delta_color = "normal" if saldo_periodo >= 0 else "inverse"
            st.metric("Resultado do Período", f"R$ {saldo_periodo:,.2f}", delta_color=delta_color)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")

        # 6.1. Exibe o Relatório de Análise
        if st.session_state['relatorio_consolidado'] and st.session_state['relatorio_consolidado'] not in ["Aguardando análise de dados...", "Aguardando geração do relatório..."]:
            st.subheader("Relatório de Análise Consolidada (Texto)")
            st.markdown(st.session_state['relatorio_consolidado'])
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
    # 1. Tenta carregar a imagem local (PNG)
    footer_logo = Image.open(LOGO_FILENAME)
    
    # 2. Cria colunas para o rodapé: uma pequena para a logo e o restante para o texto
    footer_col1, footer_col2 = st.columns([1, 4]) 
    
    with footer_col1:
        # Exibe a logo (tamanho reduzido para rodapé)
        st.image(footer_logo, width=40)
        
    with footer_col2:
        # Exibe o texto de informação (com um pequeno padding para alinhar com o logo)
        st.markdown(
            """
            <p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 5px;">
                Análise de Extrato Empresarial | Dados extraídos e classificados com Gemini 2.5 Pro.
            </p>
            """,
            unsafe_allow_html=True
        )
        
except Exception:
    st.markdown(
        """
        <p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 10px;">
            Análise de Extrato Empresarial | Dados extraídos e classificados com Gemini 2.5 Pro.
        </p>
        """,
        unsafe_allow_html=True
    )

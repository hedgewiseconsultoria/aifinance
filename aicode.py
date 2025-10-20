import streamlit as st
import pandas as pd
import json
import io
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai
from google.genai import types

# --- 1. CONFIGURAÇÃO DE SEGURANÇA E TEMA ---

# Cores baseadas na logo Hedgewise
PRIMARY_COLOR = "#0A2342"   # Azul Marinho Escuro (para botões, links)
SECONDARY_COLOR = "#000000" # Preto (para títulos e texto principal)
BACKGROUND_COLOR = "#F0F2F6" # Cinza Claro (fundo sutil)
ACCENT_COLOR = "#007BFF" # Azul de Destaque para Fluxo Positivo
NEGATIVE_COLOR = "#DC3545" # Vermelho para Fluxo Negativo

# Nome do arquivo da logo disponível localmente (AJUSTADO PARA .PNG)
LOGO_FILENAME = "logo_hedgewise.png" 
LOGO_URL = "logo_hedgewise.png" 

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
        .reportview-container {{
            background: {BACKGROUND_COLOR};
        }}
        /* Header Principal (Agora usado apenas para a linha divisória) */
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
        .stMetric label {{
            font-weight: 600 !important;
            color: #6c757d; /* Texto cinza suave para a label */
        }}
        .stMetric div[data-testid="stMetricValue"] {{
            font-size: 1.8em !important;
            color: {SECONDARY_COLOR};
        }}
        
        /* O CSS do rodapé fixo foi removido para usar widgets nativos (st.columns) */
    </style>
    """,
    unsafe_allow_html=True
)

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
    # NOVO: Campo para a classificação DCF
    categoria_dcf: str = Field( 
        description="Classificação da transação para o Demonstrativo de Fluxo de Caixa (DCF): 'OPERACIONAL', 'INVESTIMENTO' ou 'FINANCIAMENTO'."
    )

class ExtratoBancarioCompleto(BaseModel):
    """Contém a lista de transações e o relatório de análise."""
    
    transacoes: List[Transacao] = Field(
        description="Uma lista de objetos 'Transacao' extraídos do documento."
    )
    saldo_final: float = Field(
        description="O saldo final da conta no extrato. Use zero se não for encontrado."
    )
    # O relatório individual foi simplificado para ser apenas uma confirmação, 
    # pois a análise avançada será feita de forma consolidada.
    relatorio_analise: str = Field(
        description="Confirmação de extração dos dados deste extrato. Use 'Extração de dados concluída com sucesso.'"
    )


# --- 3. FUNÇÃO DE CHAMADA DA API PARA EXTRAÇÃO ---

@st.cache_data(show_spinner="Analisando PDF com Gemini (pode demorar até 30 segundos)...")
def analisar_extrato(pdf_bytes: bytes, filename: str) -> dict:
    """Chama a Gemini API para extrair dados estruturados e classificar DCF por transação."""
    
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    # Prompt focado em extração e classificação
    prompt_analise = (
        f"Você é um especialista em extração e classificação de dados financeiros. "
        f"Seu trabalho é extrair todas as transações deste extrato bancário em PDF do arquivo '{filename}' e "
        "classificar cada transação rigorosamente em uma 'categoria_dcf' como 'OPERACIONAL', 'INVESTIMENTO' ou 'FINANCIAMENTO'. "
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
        st.error(f"Erro ao chamar a Gemini API para {filename}: {e}")
        st.info("Verifique se o PDF está legível e se a API Key está configurada corretamente.")
        return {
            'transacoes': [], 
            'saldo_final': 0.0, 
            'relatorio_analise': f"**Falha na Extração:** Ocorreu um erro ao processar o arquivo {filename}. Motivo: {e}"
        }

# --- 3.1. FUNÇÃO DE GERAÇÃO DE RELATÓRIO CONSOLIDADO ---

def gerar_relatorio_consolidado(df_transacoes: pd.DataFrame) -> str:
    """Gera o relatório de análise consolidado enviando os dados agregados para o Gemini."""
    
    # Prepara os dados para análise
    # Converte o DataFrame de transações consolidadas para uma string JSON
    transacoes_json = df_transacoes.to_json(orient='records', date_format='iso', indent=2)
    
    prompt_analise = (
        "Você é um analista financeiro de elite, especializado na metodologia do Demonstrativo de Fluxo de Caixa (DCF) para micro e pequenas empresas (PME). "
        "Seu trabalho é analisar o conjunto de transações CONSOLIDADAS (de múltiplas contas) fornecido abaixo em JSON. "
        "Todas as transações já estão classificadas em 'OPERACIONAL', 'INVESTIMENTO' e 'FINANCIAMENTO' (campo 'categoria_dcf'). "
        "Gere um relatório de análise AVANÇADA, TÉCNICA E DIRETA AO PONTO para a gestão de caixa da empresa, focado na geração de capital. "
        "É mandatório que você inclua as seguintes seções: "
        "1. Sumário Executivo Consolidado: Breve resumo sobre a saúde financeira geral no período. "
        "2. Análise de Fluxo de Caixa DCF: Calcule e detalhe o saldo líquido total gerado por cada uma das três atividades (OPERACIONAL, INVESTIMENTO e FINANCIAMENTO). Este é o ponto mais importante para o empreendedor. "
        "3. Principais Tendências de Gastos: Liste e comente as 3 Categorias de Maior Impacto (baseadas em 'categoria_sugerida') e sua implicação no caixa. "
        "4. Sugestões Estratégicas: Sugestões acionáveis para otimizar o capital de giro e melhorar o fluxo operacional. "
        "Use apenas texto simples e Markdown básico (como negrito `**` e listas). Evite códigos LaTeX ou símbolos de moeda (R$) em valores monetários no corpo do relatório, use apenas números. "
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
        # Tenta carregar a imagem da logo (.PNG)
        logo = Image.open(LOGO_FILENAME)
        
        # Cria colunas para o layout do cabeçalho: 1 para o logo (pequeno) e 6 para o título
        col1, col2 = st.columns([1, 6])
        
        with col1:
            # Exibe a logo com largura de 100px
            st.image(logo, width=100)
            
        with col2:
            # Exibe o título principal do projeto
            st.title("Análise Financeira Inteligente")
            
        # Adiciona uma linha horizontal para separar o cabeçalho do conteúdo principal
        st.markdown("---")
        
    except FileNotFoundError:
        st.title("Análise Financeira Inteligente")
        st.warning(f"Atenção: O arquivo da logo '{LOGO_FILENAME}' não foi encontrado. O título é exibido sozinho.")
        st.markdown("---")
    except Exception as e:
        st.title("Análise Financeira Inteligente")
        st.error(f"Erro ao carregar a logo: {e}")
        st.markdown("---")


# --- 5. INTERFACE STREAMLIT ---

# 5.1. CABEÇALHO PERSONALIZADO COM LOGO
load_header()

st.markdown("Faça o upload de **todos** os extratos bancários em PDF para extração estruturada de dados e geração de um relatório de análise financeira consolidada.")

# Permite múltiplos arquivos
uploaded_files = st.file_uploader(
    "Selecione os arquivos PDF dos seus extratos bancários",
    type="pdf",
    accept_multiple_files=True,
    help="Os PDFs devem ter texto selecionável. Você pode selecionar múltiplos arquivos de contas diferentes para uma análise consolidada."
)

if uploaded_files: # Verifica se há arquivos
    
    # Botão para iniciar a análise
    if st.button(f"Executar Análise CONSOLIDADA ({len(uploaded_files)} arquivos)", key="analyze_btn"):
        
        # Estruturas para agregação
        todas_transacoes = []
        saldos_finais = 0.0
        
        # 1. Loop para extração de dados e agregação
        extraction_status = st.empty()
        extraction_status.info("Iniciando extração e classificação DCF por arquivo...")
        
        for i, uploaded_file in enumerate(uploaded_files):
            extraction_status.info(f"Extraindo dados do arquivo {i+1} de {len(uploaded_files)}: **{uploaded_file.name}**")
            
            pdf_bytes = uploaded_file.getvalue()
            # Chama a função de extração (que também classifica DCF)
            dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name)

            # Agregação
            todas_transacoes.extend(dados_dict['transacoes'])
            saldos_finais += dados_dict['saldo_final']
        
        # 2. Consolidação final
        df_transacoes = pd.DataFrame(todas_transacoes)
        
        # Checa se há dados válidos para prosseguir
        if df_transacoes.empty:
            extraction_status.error("Nenhuma transação válida foi extraída de todos os arquivos. A análise consolidada não pode ser realizada.")
            total_credito, total_debito, saldo_periodo = 0, 0, 0
            relatorio_consolidado = "**Falha na Análise Consolidada:** Nenhum dado extraído."
        else:
            extraction_status.success(f"✅ Extração de {len(todas_transacoes)} transações concluída! Gerando relatório consolidado...")

            # 3. Cálculos de KPI consolidados
            total_credito = df_transacoes[df_transacoes['tipo_movimentacao'] == 'CREDITO']['valor'].sum()
            total_debito = df_transacoes[df_transacoes['tipo_movimentacao'] == 'DEBITO']['valor'].sum()
            saldo_periodo = total_credito - total_debito
            
            # 4. Geração do Relatório Consolidado (SEGUNDA CHAMADA AO GEMINI)
            with st.spinner("Gerando Relatório de Análise Consolidada..."):
                relatorio_consolidado = gerar_relatorio_consolidado(df_transacoes)
            
            extraction_status.empty() # Limpa a mensagem de status da extração
            st.success("✅ Análise Consolidada Concluída com Sucesso!")


        # --- Exibição de KPIs Consolidados ---
        st.markdown("## Resumo Financeiro CONSOLIDADO do Período")
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        with kpi_col1:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            st.metric("Total de Créditos (Consolidado)", f"R$ {total_credito:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)

        with kpi_col2:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            st.metric("Total de Débitos (Consolidado)", f"R$ {total_debito:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)

        with kpi_col3:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            # Determina a cor do resultado do período
            delta_color = "normal" if saldo_periodo >= 0 else "inverse"
            st.metric("Resultado do Período (Consolidado)", f"R$ {saldo_periodo:,.2f}", delta_color=delta_color)
            st.markdown('</div>', unsafe_allow_html=True)

        with kpi_col4:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            # Nota: A soma dos saldos finais é uma métrica meramente informativa.
            st.metric("Soma dos Saldos Finais", f"R$ {saldos_finais:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)


        # --- Apresentação de Resultados (Relatório e Tabela) ---
        
        st.markdown("---")
        
        col_relatorio, col_tabela = st.columns([1, 1])

        with col_relatorio:
            st.subheader("Relatório de Análise de Fluxo de Caixa (DCF) Consolidada")
            # Exibe o relatório consolidado
            st.markdown(relatorio_consolidado)

        with col_tabela:
            st.subheader("Dados Extraídos e Estruturados (Consolidado)")
            # Exibe o DataFrame Consolidado
            st.dataframe(
                df_transacoes, 
                use_container_width=True,
                column_config={
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %0.2f"),
                    "categoria_dcf": st.column_config.TextColumn("Classificação DCF") # Exibe a nova coluna
                }
            )

        st.markdown("---")
        
# 5.2. RODAPÉ COM LOGO E INFORMAÇÕES (AJUSTADO PARA ARQUIVO LOCAL)

st.markdown("---") # Linha divisória para o rodapé
try:
    # 1. Tenta carregar a imagem local (AGORA .PNG)
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
                Análise de Extrato Empresarial | Dados extraídos com Gemini 2.5 Pro.
            </p>
            """,
            unsafe_allow_html=True
        )
        
except FileNotFoundError:
    # Fallback se o arquivo local não for encontrado
    st.markdown(
        """
        <p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 10px;">
            Análise de Extrato Empresarial | Dados extraídos com Gemini 2.5 Pro.
            (Logo do rodapé não encontrada.)
        </p>
        """,
        unsafe_allow_html=True
    )
except Exception as e:
    st.error(f"Erro ao carregar a logo do rodapé: {e}")

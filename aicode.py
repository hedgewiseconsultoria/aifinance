import streamlit as st
import pandas as pd
import json
import io
from PIL import Image # Importação da PIL para a logo
# A importação do BaseModel é necessária para tipagem
from pydantic import BaseModel, Field
from typing import List
from google import genai
from google.genai import types

# --- 1. CONFIGURAÇÃO DE SEGURANÇA E TEMA ---

# Cores baseadas na logo Hedgewise
PRIMARY_COLOR = "#0A2342"   # Azul Marinho Escuro (para botões, links)
SECONDARY_COLOR = "#000000" # Preto (para títulos e texto principal)
BACKGROUND_COLOR = "#F0F2F6" # Cinza Claro (fundo sutil)
ACCENT_COLOR = "#007BFF" # Azul de Destaque para Fluxo Positivo
NEGATIVE_COLOR = "#DC3545" # Vermelho para Fluxo Negativo

# Nome do arquivo da logo disponível localmente
LOGO_FILENAME = "logo_hedgewise.jpg" 
# NOTA: Para o rodapé, que usa HTML/CSS, é necessário uma URL pública.
# Mantenho a variável, mas limpo o placeholder.
LOGO_URL = "logo_hedgewise.jpg" # Substituir por URL pública se for usar em produção

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
        /* Rodapé Fixo com Logo */
        #st-pages-footer {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #f8f9fa; /* Fundo leve para o rodapé */
            border-top: 1px solid #e9ecef;
            padding: 5px 20px;
            z-index: 10;
        }}
        .footer-content {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .footer-logo {{
            height: 30px; 
            margin-right: 15px;
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

class ExtratoBancarioCompleto(BaseModel):
    """Contém a lista de transações e o relatório de análise."""
    
    transacoes: List[Transacao] = Field(
        description="Uma lista de objetos 'Transacao' extraídos do documento."
    )
    saldo_final: float = Field(
        description="O saldo final da conta no extrato. Use zero se não for encontrado."
    )
    relatorio_analise: str = Field(
        description=(
            "Análise financeira AVANÇADA e detalhada para o empreendedor. "
            "Inclua as seguintes seções: 1. Sumário Executivo, 2. Análise de Fluxo de Caixa (Total Débito/Crédito e Saldo Médio), 3. ANÁLISE DO DEMONSTRATIVO DE FLUXO DE CAIXA (DCF): Detalhe o saldo líquido gerado pelas atividades OPERACIONAIS, de INVESTIMENTO e de FINANCIAMENTO. 4. Tendências de Gastos (As 3 Categorias de Maior Impacto e a que mais Cresceu), 5. Sugestões Estratégicas para Otimização de Capital."
        )
    )


# --- 3. FUNÇÃO DE CHAMADA DA API ---

# O tipo de retorno foi alterado para 'dict' para ser serializável pelo Streamlit Cache
@st.cache_data(show_spinner="Analisando PDF com Gemini (pode demorar até 30 segundos)...")
def analisar_extrato(pdf_bytes: bytes) -> dict:
    """Chama a Gemini API para extrair dados e gerar o relatório estruturado."""
    
    # Prepara a parte do arquivo PDF
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    # Prompt instruindo o modelo a gerar a análise avançada
    prompt_analise = (
        "Você é um analista financeiro especializado em micro e pequenas empresas (PME), focado na metodologia do **Demonstrativo de Fluxo de Caixa (DCF)**. "
        "Seu trabalho é extrair todas as transações deste extrato bancário em PDF e, "
        "simultaneamente, gerar um relatório de análise AVANÇADA, TÉCNICA E DIRETA AO PONTO. " 
        "Ao gerar o 'relatorio_analise', **é mandatório** que você classifique cada transação como 'OPERACIONAL', 'INVESTIMENTO' ou 'FINANCIAMENTO' para calcular o fluxo de caixa líquido gerado por cada uma dessas três atividades. "
        "Ao formatar o relatório, **use apenas texto simples e Markdown básico (como negrito `**` e listas)**. É **fundamental** que você evite: "
        "1. **Códigos LaTeX ou caracteres especiais**."
        "2. **Símbolos de moeda (R$) ou separadores de milhar (ponto/vírgula)** em valores monetários no corpo do relatório. Use apenas números no formato de texto simples, por exemplo: 'O caixa líquido foi de 2227.39'. A exibição da moeda e formatação final será feita pela interface. " 
        "Preencha rigorosamente a estrutura JSON fornecida, em particular o campo 'relatorio_analise', "
        "garantindo que o relatório seja detalhado, profissional e contenha insights acionáveis sobre o fluxo de caixa do empreendedor, destacando o CAIXA GERADO PELA ATIVIDADE OPERACIONAL. "
        "Use sempre o valor positivo para 'valor' e classifique estritamente como 'DEBITO' ou 'CREDITO'."
    )
    
    # Configuração de geração para JSON estruturado
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ExtratoBancarioCompleto,
        # Aumentar a temperatura levemente para dar criatividade na análise, mantendo a estrutura
        temperature=0.4 
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro', # Modelo PRO para maior precisão e raciocínio complexo
            contents=[pdf_part, prompt_analise],
            config=config,
        )
        
        # Converte a string JSON de resposta em um objeto Pydantic
        response_json = json.loads(response.text)
        dados_pydantic = ExtratoBancarioCompleto(**response_json)
        
        # Retorna o objeto Pydantic como um dicionário Python padrão,
        # que o Streamlit consegue serializar e cachear sem erros.
        return dados_pydantic.model_dump()
    
    except Exception as e:
        st.error(f"Erro ao chamar a Gemini API: {e}")
        st.info("Verifique se o PDF está legível e se a API Key está configurada corretamente.")
        st.stop()


# --- 4. FUNÇÃO DE CABEÇALHO (NOVO AJUSTE) ---

def load_header():
    """Carrega o logo e exibe o título principal usando st.columns para melhor layout."""
    try:
        # Tenta carregar a imagem da logo
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

st.markdown("Faça o upload de um extrato bancário em PDF para extração estruturada de dados e geração de um relatório de análise financeira avançada.")

uploaded_file = st.file_uploader(
    "Selecione o arquivo PDF do seu extrato bancário",
    type="pdf",
    help="O PDF deve ter texto selecionável (não ser uma imagem escaneada)."
)

if uploaded_file is not None:
    # Lendo o arquivo em bytes
    pdf_bytes = uploaded_file.getvalue()
    
    # Botão para iniciar a análise
    if st.button("Executar Análise Inteligente", key="analyze_btn"):
        
        # 1. Chamar a função de análise
        dados_dict = analisar_extrato(pdf_bytes) # Recebe um dicionário agora

        # 3. Conversão para DataFrame (para exibição e cálculo de KPIs)
        df_transacoes = pd.DataFrame(dados_dict['transacoes'])
        
        # 4. Cálculos de KPI para o frontend (opcional)
        total_credito = df_transacoes[df_transacoes['tipo_movimentacao'] == 'CREDITO']['valor'].sum()
        total_debito = df_transacoes[df_transacoes['tipo_movimentacao'] == 'DEBITO']['valor'].sum()
        saldo_periodo = total_credito - total_debito
        
        st.success("✅ Extração e Análise Concluídas com Sucesso!")

        # --- Exibição de KPIs ---
        st.markdown("## Resumo Financeiro do Período")
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
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
            # Determina a cor do resultado do período
            delta_color = "normal" if saldo_periodo >= 0 else "inverse"
            st.metric("Resultado do Período", f"R$ {saldo_periodo:,.2f}", delta_color=delta_color)
            st.markdown('</div>', unsafe_allow_html=True)

        with kpi_col4:
            st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
            st.metric("Saldo Final do Extrato", f"R$ {dados_dict['saldo_final']:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)


        # --- Apresentação de Resultados (Relatório e Tabela) ---
        
        st.markdown("---")
        
        col_relatorio, col_tabela = st.columns([1, 1])

        with col_relatorio:
            st.subheader("Relatório de Análise Financeira Avançada")
            # O relatório vem como string do campo 'relatorio_analise' do dicionário
            st.markdown(dados_dict['relatorio_analise'])

        with col_tabela:
            st.subheader("Dados Extraídos e Estruturados")
            # Exibe o DataFrame
            st.dataframe(
                df_transacoes, 
                use_container_width=True,
                column_config={
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %0.2f"),
                }
            )

        st.markdown("---")
        
# 5.2. RODAPÉ COM LOGO E INFORMAÇÕES
# Usando o st.empty para simular o rodapé fixo (não é estritamente fixo, mas é o último elemento)
st.markdown(
    f"""
    <div id="st-pages-footer">
        <div class="footer-content">
            <!-- NOTA: Para exibir a logo no rodapé via HTML, você deve usar uma URL pública. -->
            <img src="{LOGO_URL}" alt="Logo Hedgewise Footer" class="footer-logo">
            <p style="font-size: 0.8rem; color: #6c757d; margin: 0;">
                Análise de Extrato Empresarial | Dados extraídos com Gemini 2.5 Pro.
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

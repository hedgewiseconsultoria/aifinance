import streamlit as st
import pandas as pd
import json
import io
# A importação do BaseModel é necessária para tipagem, mas o Pydantic
# não está mais sendo retornado diretamente pela função cacheada.
from pydantic import BaseModel, Field
from typing import List
from google import genai
from google.genai import types

# --- 1. CONFIGURAÇÃO DE SEGURANÇA E TEMA ---

# Cores baseadas na logo Hedgewise
PRIMARY_COLOR = "#0A2342"  # Azul Marinho Escuro (para botões, links)
SECONDARY_COLOR = "#000000"  # Preto (para títulos e texto principal)
BACKGROUND_COLOR = "#F0F2F6" # Cinza Claro (fundo sutil)

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="📈",
    layout="wide"
)

# Adiciona CSS customizado para o tema
st.markdown(
    f"""
    <style>
        .stButton>button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            border: none;
        }}
        .stButton>button:hover {{
            background-color: #1C3757; 
            color: white;
        }}
        .reportview-container {{
            background: {BACKGROUND_COLOR};
        }}
        .main-header {{
            color: {SECONDARY_COLOR};
            font-size: 2.5em;
            border-bottom: 2px solid {PRIMARY_COLOR};
            padding-bottom: 10px;
        }}
        .kpi-container {{
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.1);
            margin-bottom: 15px;
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
            "Inclua as seguintes seções: 1. Sumário Executivo, 2. Análise de Fluxo de Caixa (Total Débito/Crédito e Saldo Médio), 3. Tendências de Gastos (As 3 Categorias de Maior Impacto e a que mais Cresceu), 4. Sugestões Estratégicas para Otimização de Capital."
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
        "Você é um analista financeiro especializado em micro e pequenas empresas (PME). "
        "Seu trabalho é extrair todas as transações deste extrato bancário em PDF e, "
        "simultaneamente, gerar um relatório de análise avançada. "
        "Preencha rigorosamente a estrutura JSON fornecida, em particular o campo 'relatorio_analise', "
        "garantindo que o relatório seja detalhado, profissional e contenha insights acionáveis sobre o fluxo de caixa do empreendedor."
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
        
        # CORREÇÃO CRÍTICA: Retorna o objeto Pydantic como um dicionário Python padrão,
        # que o Streamlit consegue serializar e cachear sem erros.
        return dados_pydantic.model_dump()
    
    except Exception as e:
        st.error(f"Erro ao chamar a Gemini API: {e}")
        st.info("Verifique se o PDF está legível e se a API Key está configurada corretamente.")
        st.stop()


# --- 4. INTERFACE STREAMLIT ---

st.markdown('<p class="main-header">📈 Hedgewise: Análise de Extrato Empresarial</p>', unsafe_allow_html=True)
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

        # 2. Re-envelopar o dicionário em Pydantic para acesso fácil (opcional, mas bom para tipagem)
        # Ou simplesmente acessar os dados via chaves do dicionário (dados_dict['transacoes'])
        # Para simplificar, vamos usar o dicionário diretamente (dados_dict)
        
        # 3. Conversão para DataFrame (para exibição e cálculo de KPIs)
        df_transacoes = pd.DataFrame(dados_dict['transacoes'])
        
        # 4. Cálculos de KPI para o frontend (opcional)
        total_credito = df_transacoes[df_transacoes['tipo_movimentacao'] == 'CREDITO']['valor'].sum()
        total_debito = df_transacoes[df_transacoes['tipo_movimentacao'] == 'DEBITO']['valor'].sum()
        saldo_periodo = total_credito - total_debito
        
        st.success("✅ Extração e Análise Concluídas com Sucesso!")

        # --- Exibição de KPIs ---
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
            st.metric("Resultado do Período", f"R$ {saldo_periodo:,.2f}", delta_color=("inverse" if saldo_periodo < 0 else "normal"))
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
        st.caption(f"Dados extraídos com Gemini 2.5 Pro. Saldo Final do Extrato: R$ {dados_dict['saldo_final']:,.2f}")

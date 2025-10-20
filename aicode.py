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
# O cache_data agora usa o nome do arquivo como parte da chave para diferenciar
@st.cache_data(show_spinner="Analisando PDF com Gemini (pode demorar até 30 segundos)...")
def analisar_extrato(pdf_bytes: bytes, filename: str) -> dict:
    """Chama a Gemini API para extrair dados e gerar o relatório estruturado."""
    
    # Prepara a parte do arquivo PDF
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    # Prompt instruindo o modelo a gerar a análise avançada
    prompt_analise = (
        f"Você é um analista financeiro especializado em micro e pequenas empresas (PME), focado na metodologia do **Demonstrativo de Fluxo de Caixa (DCF)**. "
        f"Este extrato se refere ao arquivo '{filename}'. " # Adicionando o nome do arquivo ao prompt
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
        
        # Retorna o objeto Pydantic como um dicionário Python padrão
        return dados_pydantic.model_dump()
    
    except Exception as e:
        st.error(f"Erro ao chamar a Gemini API para {filename}: {e}")
        st.info("Verifique se o PDF está legível e se a API Key está configurada corretamente.")
        # Retorna estrutura vazia em caso de falha para não interromper a análise dos outros arquivos
        return {
            'transacoes': [], 
            'saldo_final': 0.0, 
            'relatorio_analise': f"**Falha na Análise:** Ocorreu um erro ao processar o arquivo {filename}. Motivo: {e}"
        }


# --- 4. FUNÇÃO DE CABEÇALHO ---

def load_header():
    """Carrega o logo e exibe o título principal usando st.columns para melhor layout."""
    try:
        # Tenta carregar a imagem da logo (AGORA .PNG)
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

# AJUSTADO: Permite múltiplos arquivos
uploaded_files = st.file_uploader(
    "Selecione os arquivos PDF dos seus extratos bancários",
    type="pdf",
    accept_multiple_files=True,
    help="Os PDFs devem ter texto selecionável (não ser imagens escaneadas). Você pode selecionar múltiplos arquivos de contas diferentes."
)

if uploaded_files: # Verifica se há arquivos
    
    # Botão para iniciar a análise
    if st.button(f"Executar Análise Inteligente ({len(uploaded_files)} arquivos)", key="analyze_btn"):
        
        # Estruturas para agregação
        todas_transacoes = []
        relatorios_combinados = ""
        saldos_finais = 0.0
        
        # 1. Loop sobre cada arquivo e chama a análise
        with st.spinner("Processando todos os extratos..."):
            for i, uploaded_file in enumerate(uploaded_files):
                st.info(f"Analisando arquivo {i+1} de {len(uploaded_files)}: **{uploaded_file.name}**")
                
                pdf_bytes = uploaded_file.getvalue()
                dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name)

                # Agregação
                todas_transacoes.extend(dados_dict['transacoes'])
                saldos_finais += dados_dict['saldo_final']
                
                relatorios_combinados += (
                    f"\n\n---\n\n## Relatório Individual: {uploaded_file.name}\n\n"
                    f"{dados_dict['relatorio_analise']}"
                )
        
        # 2. Consolidação final
        df_transacoes = pd.DataFrame(todas_transacoes)
        
        # 3. Cálculos de KPI consolidados
        if not df_transacoes.empty:
            total_credito = df_transacoes[df_transacoes['tipo_movimentacao'] == 'CREDITO']['valor'].sum()
            total_debito = df_transacoes[df_transacoes['tipo_movimentacao'] == 'DEBITO']['valor'].sum()
            saldo_periodo = total_credito - total_debito
            
            st.success(f"✅ Extração e Análise Concluídas com Sucesso! {len(todas_transacoes)} transações agregadas de {len(uploaded_files)} contas.")
        else:
            total_credito = 0
            total_debito = 0
            saldo_periodo = 0
            st.warning("Nenhuma transação válida foi extraída de todos os arquivos.")


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
            # Nota: O saldo final somado pode ser impreciso e deve ser usado com cautela.
            st.metric("Soma dos Saldos Finais", f"R$ {saldos_finais:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)


        # --- Apresentação de Resultados (Relatório e Tabela) ---
        
        st.markdown("---")
        
        col_relatorio, col_tabela = st.columns([1, 1])

        with col_relatorio:
            st.subheader("Relatórios de Análise Detalhada (Por Extrato)")
            # O relatório agora é a concatenação de todas as análises
            st.markdown(relatorios_combinados)

        with col_tabela:
            st.subheader("Dados Extraídos e Estruturados (Consolidado)")
            # Exibe o DataFrame Consolidado
            st.dataframe(
                df_transacoes, 
                use_container_width=True,
                column_config={
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %0.2f"),
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
                Análise de Extrato Empresarial | Inteligência Financeira Aplicada
            </p>
            """,
            unsafe_allow_html=True
        )
        
except FileNotFoundError:
    # Fallback se o arquivo local não for encontrado
    st.markdown(
        """
        <p style="font-size: 0.8rem; color: #6c757d; margin: 0; padding-top: 10px;">
            Análise de Extrato Empresarial | Inteligência Financeira Aplicada
            (Logo do rodapé não encontrada.)
        </p>
        """,
        unsafe_allow_html=True
    )
except Exception as e:
    st.error(f"Erro ao carregar a logo do rodapé: {e}")



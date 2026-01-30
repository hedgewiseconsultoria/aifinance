import streamlit as st
import pandas as pd
import json
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from google import genai
from google.genai import types
import traceback
import math
import hashlib
from datetime import datetime, timedelta, timezone
from streamlit_option_menu import option_menu

# integração auth/supabase (arquivo auth.py que você forneceu)
from auth import (
    login_page,
    logout,
    supabase,
    reset_password_page,
)

# funções de relatórios (arquivo reports_functions.py)
from reports_functions import secao_relatorios_dashboard

import streamlit.components.v1 as components

import re

def normalizar_descricao(descricao: str) -> str:
    """
    Normaliza descrições bancárias para evitar erros repetidos de classificação.
    """
    if not descricao:
        return ""

    descricao = descricao.lower()
    descricao = re.sub(r"\d+", "", descricao)      # remove números
    descricao = re.sub(r"[^\w\s]", "", descricao)  # remove pontuação
    descricao = re.sub(r"\s+", " ", descricao)     # normaliza espaços
    return descricao.strip()

def buscar_classificacao_memoria(user_id, descricao_normalizada, supabase):
    """
    Busca uma classificação já corrigida anteriormente pelo mesmo usuário.
    Retorna None se não existir.
    """
    res = (
        supabase
        .table("classificacao_memoria")
        .select("conta_classificada")
        .eq("user_id", user_id)
        .eq("descricao_normalizada", descricao_normalizada)
        .limit(1)
        .execute()
    )

    if res.data:
        return res.data[0]["conta_classificada"]

    return None


# --------------------------
# MERCADO PAGO – ASSINATURA
# --------------------------
MP_SUBSCRIPTION_URL = "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_plan_id=9fec9be34af54104a543026f1f13ebcb"


def verificar_trial(perfil):
    trial_fim = perfil.get("trial_fim")
    if not trial_fim:
        return True, None

    fim = datetime.fromisoformat(trial_fim.replace("Z", "+00:00"))
    agora = datetime.now(timezone.utc)

    dias_restantes = (fim - agora).days
    return agora <= fim, max(dias_restantes, 0)



# ----------------------
# PLANO DE CONTAS (COMENTADO)
# ----------------------
PLANO_DE_CONTAS = {
    "sinteticos": [
        {
            "codigo": "OP",
            "nome": "Atividades Operacionais",
            "tipo_fluxo": "OPERACIONAL",
            "descricao": (
                "Movimentações ligadas ao funcionamento normal da empresa. "
                "Inclui receitas, custos e despesas do dia a dia do negócio."
            ),
            "contas": [
                {
                    "codigo": "OP-01",
                    "nome": "Receitas de Vendas",
                    "descricao": "Entradas de dinheiro provenientes da venda de produtos."
                },
                {
                    "codigo": "OP-02",
                    "nome": "Receitas de Serviços",
                    "descricao": "Valores recebidos pela prestação de serviços."
                },
                {
                    "codigo": "OP-03",
                    "nome": "Outras Receitas Operacionais",
                    "descricao": "Entradas operacionais não recorrentes ou pontuais."
                },
                {
                    "codigo": "OP-04",
                    "nome": "Custos Operacionais",
                    "descricao": "Gastos diretamente ligados à produção ou entrega do produto ou serviço."
                },
                {
                    "codigo": "OP-05",
                    "nome": "Despesas Administrativas",
                    "descricao": "Despesas de estrutura e gestão, como aluguel, sistemas e contador."
                },
                {
                    "codigo": "OP-06",
                    "nome": "Despesas Comerciais",
                    "descricao": "Gastos com vendas, marketing, anúncios e comissões."
                },
                {
                    "codigo": "OP-07",
                    "nome": "Despesas com Pessoal",
                    "descricao": "Salários, encargos, benefícios e custos relacionados à equipe."
                },
                {
                    "codigo": "OP-08",
                    "nome": "Impostos e Contribuições",
                    "descricao": "Tributos pagos pela empresa sobre receitas, folha ou operação."
                },
                {
                    "codigo": "OP-09",
                    "nome": "Tarifas Bancárias e Serviços",
                    "descricao": "Tarifas, taxas bancárias e serviços financeiros."
                },
            ],
        },
        {
            "codigo": "INV",
            "nome": "Atividades de Investimento",
            "tipo_fluxo": "INVESTIMENTO",
            "descricao": (
                "Movimentações relacionadas à aquisição ou venda de ativos "
                "e aplicações visando crescimento ou estrutura da empresa."
            ),
            "contas": [
                {
                    "codigo": "INV-01",
                    "nome": "Aquisição de Imobilizado",
                    "descricao": "Compra de máquinas, equipamentos, veículos ou bens duráveis."
                },
                {
                    "codigo": "INV-02",
                    "nome": "Aplicações Financeiras",
                    "descricao": "Valores aplicados para rendimento financeiro."
                },
                {
                    "codigo": "INV-03",
                    "nome": "Alienação de Ativos",
                    "descricao": "Venda de bens ou ativos da empresa."
                },
            ],
        },
        {
            "codigo": "FIN",
            "nome": "Atividades de Financiamento",
            "tipo_fluxo": "FINANCIAMENTO",
            "descricao": (
                "Movimentações ligadas a empréstimos, financiamentos "
                "e relação financeira com os sócios."
            ),
            "contas": [
                {
                    "codigo": "FIN-01",
                    "nome": "Empréstimos Recebidos",
                    "descricao": "Entrada de recursos provenientes de empréstimos ou financiamentos."
                },
                {
                    "codigo": "FIN-02",
                    "nome": "Pagamento de Empréstimos",
                    "descricao": "Saídas para pagamento de parcelas de empréstimos."
                },
                {
                    "codigo": "FIN-03",
                    "nome": "Juros sobre Empréstimos e Financiamentos",
                    "descricao": "Custo financeiro dos empréstimos e financiamentos."
                },
                {
                    "codigo": "FIN-04",
                    "nome": "Aporte de Sócios",
                    "descricao": "Capital colocado pelos sócios na empresa."
                },
                {
                    "codigo": "FIN-05",
                    "nome": "Retirada de Sócios / Pró-labore e Despesas Pessoais",
                    "descricao": "Retiradas de recursos feitas pelos sócios."
                },
            ],
        },
        {
            "codigo": "NE",
            "nome": "Ajustes e Transferências Internas",
            "tipo_fluxo": "NEUTRO",
            "descricao": (
                "Movimentações que não impactam o resultado financeiro, "
                "usadas apenas para organização e correção."
            ),
            "contas": [
                {
                    "codigo": "NE-01",
                    "nome": "Transferências entre Contas",
                    "descricao": "Movimentação de valores entre contas bancárias da empresa."
                },
                {
                    "codigo": "NE-02",
                    "nome": "Ajustes e Estornos",
                    "descricao": "Correções ou estornos de lançamentos incorretos."
                },
            ],
        },
    ]
}

# --- THEME / CSS ---
PRIMARY_COLOR = "#0A2342"
BACKGROUND_COLOR = "#F0F2F6"
ACCENT_COLOR = "#007BFF"
REPORT_BACKGROUND = "#F9F5EB"
LOGO1_FILENAME = "FinanceAI_1.png"
LOGO_FILENAME = "logo_hedgewise.png"

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="logo_hedgewise.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 🔥 Ajuste essencial para reset password funcionar
st.markdown(
    f"""
    <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {{
            background-color: {BACKGROUND_COLOR} !important;
            color: #000000 !important;
        }}
        .stButton>button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: bold;
        }}
        .report-box {{
            background-color: {REPORT_BACKGROUND};
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #DDDDDD;
        }}
        .main-header {{
            font-size: 1.8em;
            font-weight: 800;
            color: {PRIMARY_COLOR};
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- session_state defaults ---
if "df_transacoes_editado" not in st.session_state:
    st.session_state["df_transacoes_editado"] = pd.DataFrame()
if "contexto_adicional" not in st.session_state:
    st.session_state["contexto_adicional"] = ""

# --- Gemini client init ---
client = None
try:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=gemini_key)
except Exception:
    client = None


# --- MODELS ---
class Transacao(BaseModel):
    data: str
    descricao: str
    valor: float
    tipo_movimentacao: str
    conta_analitica: str


class AnaliseCompleta(BaseModel):
    transacoes: List[Transacao]
    saldo_final: Optional[float] = None


# --- HELPERS ---
def formatar_brl(valor: float) -> str:
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP_SEP").replace(".", ",").replace("TEMP_SEP", ".")
        return "R$ " + valor_brl
    except Exception:
        return f"R$ {valor:.2f}"


def enriquecer_com_plano_contas(df: pd.DataFrame) -> pd.DataFrame:
    mapa_contas = {}
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        for conta in sintetico["contas"]:
            mapa_contas[conta["codigo"]] = {
                "nome_conta": conta["nome"],
                "codigo_sintetico": sintetico["codigo"],
                "nome_sintetico": sintetico["nome"],
                "tipo_fluxo": sintetico["tipo_fluxo"],
            }

    df = df.copy()
    df["nome_conta"] = df["conta_analitica"].map(lambda x: mapa_contas.get(x, {}).get("nome_conta", "Não classificado"))
    df["codigo_sintetico"] = df["conta_analitica"].map(lambda x: mapa_contas.get(x, {}).get("codigo_sintetico", "NE"))
    df["nome_sintetico"] = df["conta_analitica"].map(lambda x: mapa_contas.get(x, {}).get("nome_sintetico", "Não classificado"))
    df["tipo_fluxo"] = df["conta_analitica"].map(lambda x: mapa_contas.get(x, {}).get("tipo_fluxo", "NEUTRO"))

    def _label_from_code(code):
        try:
            if code is None or (isinstance(code, float) and pd.isna(code)):
                return ""
        except Exception:
            pass
        nome = mapa_contas.get(code, {}).get("nome_conta", "")
        if nome:
            return f"{code} - {nome}"
        return str(code)

    df["conta_display"] = df["conta_analitica"].map(lambda x: _label_from_code(x))
    return df


# --- PROMPT ---
def gerar_prompt_com_plano_contas() -> str:
    contas_str = "### PLANO DE CONTAS ###\n\n"
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        contas_str += "{} - {} (Tipo: {})\n".format(
            sintetico["codigo"], sintetico["nome"], sintetico["tipo_fluxo"]
        )
        for conta in sintetico["contas"]:
            contas_str += "  - {}: {}\n".format(conta["codigo"], conta["nome"])
        contas_str += "\n"

    prompt_template = """
Você é um especialista em extração e classificação de dados financeiros.

{contas_str}

Extraia todas as transações deste extrato bancário em PDF e classifique cada transação de acordo com o PLANO DE CONTAS acima.

INSTRUÇÕES CRÍTICAS:
1. Use EXATAMENTE os códigos do plano de contas.
2. Retorne APENAS um JSON válido.
3. Siga os códigos do plano de contas sem inventar novos códigos.
4. Extraia SOMENTE transações que representem movimentação financeira real (entrada ou saída de dinheiro).

REGRAS DE EXCLUSÃO (MUITO IMPORTANTE):
- NÃO considere como transação linhas que representem:
  • Saldo anterior
  • Saldo inicial
  • Saldo final
  • Saldo disponível
  • Saldo em conta
  • Saldo do dia
  • Totalizador de saldo
- Linhas de saldo NÃO devem aparecer na lista "transacoes".
- Saldo NÃO é transação, NÃO possui tipo_movimentacao e NÃO deve ser classificado no plano de contas.

O JSON de saída deve ter o seguinte formato:

{{
  "transacoes": [
    {{
      "data": "DD/MM/AAAA",
      "descricao": "...",
      "valor": 123.45,
      "tipo_movimentacao": "CREDITO",
      "conta_analitica": "OP-04"
    }}
  ],
  "saldo_final": 0.0
}}

IMPORTANTE:
- "valor" deve ser sempre número positivo.
- "tipo_movimentacao" deve ser "CREDITO" ou "DEBITO".
- O campo "transacoes" deve conter APENAS eventos de movimentação financeira.
- Linhas informativas, saldos ou totais NÃO devem ser retornadas como transação.
- O JSON DEVE SER VÁLIDO — NÃO coloque comentários nem texto fora do JSON.
"""

    return prompt_template.format(contas_str=contas_str)


# --- Gemini ---
@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    prompt_analise = gerar_prompt_com_plano_contas()

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AnaliseCompleta,
        temperature=0.2,
    )
    try:
        if client is None:
            raise ValueError(
                "Cliente Gemini não inicializado. Configure GEMINI_API_KEY em secrets."
            )
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[pdf_part, prompt_analise],
            config=config,
        )

        response_json = json.loads(response.text)
        dados_pydantic = AnaliseCompleta(**response_json)
        return dados_pydantic.model_dump()
    except Exception as e:
        error_message = str(e)
        if "503 UNAVAILABLE" in error_message or "model is overloaded" in error_message:
            st.error(
                f"O modelo Gemini está temporariamente indisponível ao processar '{filename}'."
            )
            st.info("Tente novamente em alguns minutos.")
        elif (
            "Invalid API key" in error_message
            or "401" in error_message
            or "permission" in error_message.lower()
        ):
            st.error("Problema de autenticação com a Gemini API.")
        else:
            st.error(f"Ocorreu um erro ao processar '{filename}': {error_message}")
        return {"transacoes": [], "saldo_final": 0.0}


# --- HEADER ---
def load_header():
    try:
        logo = Image.open(LOGO1_FILENAME)
        col1, col2 = st.columns([2, 5])
        with col1:
            st.image(logo, width=1000)
        with col2:
            st.markdown(
                '<div class="main-header">Análise Financeira Inteligente</div>',
                unsafe_allow_html=True,
            )
            st.caption("Traduzindo números em histórias que façam sentido...")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")


# --------------------------
# AUTENTICAÇÃO E MENU
# --------------------------

params = st.experimental_get_query_params()

# 🔥 Tratar o fluxo de redefinição de senha
is_reset_flow = (
    "reset" in params
    or "access_token" in params
    or "refresh_token" in params
    or params.get("type", [""])[0] == "recovery"
)

if is_reset_flow:
    reset_password_page()
    st.stop()

# 🔥 Se usuário não logado → login
if "user" not in st.session_state:
    login_page()
    st.stop()


# ============ AJUSTE CRÍTICO ==============
# Compatibilidade total com user objeto OU dict
user = st.session_state["user"]


# ===== CONTROLE DE TRIAL (PATCH MÍNIMO) =====
if isinstance(user, dict):
    user_id = user.get("id")
else:
    user_id = getattr(user, "id", None)

perfil = (
    supabase.table("users_profiles")
    .select("*")
    .eq("id", user_id)
    .single()
    .execute()
    .data
)


trial_ativo, dias_restantes = verificar_trial(perfil)

if trial_ativo:
    st.info(f"🟢 Período de teste ativo — restam {dias_restantes} dias.")
else:
    st.warning("🔴 Seu período de teste terminou. Algumas funcionalidades estão bloqueadas.")
# ===========================================



if isinstance(user, dict):
    user_email = user.get("email", "")
else:
    user_email = getattr(user, "email", "")
# ===========================================

# ================================
# SIDEBAR PROFISSIONAL COMPLETO
# ================================
try:
    from streamlit_option_menu import option_menu
    _HAS_OPTION_MENU = True
except Exception:
    _HAS_OPTION_MENU = False

def render_sidebar():
    # ======== LOGO NO TOPO ========
    try:
        logo = Image.open(LOGO1_FILENAME)
        st.sidebar.image(logo, use_container_width=True)
    except Exception:
        st.sidebar.markdown(
            "<h2 style='color:#0A2342; font-weight:700;'>Hedgewise</h2>",
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("<hr style='margin:6px 0;'>", unsafe_allow_html=True)

    # ======== MENU ========
    if _HAS_OPTION_MENU:
        with st.sidebar:
            escolha = option_menu(
                menu_title="Menu",
                options=["Upload", "Revisão","Dashboard", "Perfil", "Planos", "Configurações", "Sair"],
                icons=["cloud-upload","pencil-square","bar-chart-fill", "person-circle", "credit-card-2-back","gear-fill", "box-arrow-right"],
                menu_icon="list",
                default_index=0,
                styles={
                    "container": {"padding":"0!important", "background-color":"#FFFFFF"},
                    "menu-title": {"font-size":"15px", "color":"#0A2342", "font-weight":"700", "padding-bottom":"4px"},
                    "icon": {"color": "#0A2342", "font-size":"18px"},
                    "nav-link": {
                        "font-size":"14px",
                        "color":"#0A2342",
                        "text-align":"left",
                        "padding":"6px",
                        "margin":"2px",
                        "border-radius":"6px"
                    },
                    "nav-link-selected": {"background-color":"#0A2342", "color":"white"},
                }
            )
    else:
        with st.sidebar:
            st.markdown("<div style='font-size:15px; color:#0A2342; font-weight:700;'>Menu</div>", unsafe_allow_html=True)
            escolha = st.radio(
                "",
                ["Dashboard", "Upload", "Revisão", "Perfil", "Planos", "Configurações", "Sair"],
                index=0,
            )

    # ======== OLÁ, USUÁRIO (APÓS MENU) ========
    st.sidebar.markdown("<hr style='margin:6px 0;'>", unsafe_allow_html=True)
    st.sidebar.markdown(
        f"""
        <div style="font-size:14px; color:#0A2342; padding:6px 0;">
            Olá, <strong>{user_email}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ======== SAIR DO MENU ========
    if escolha == "Sair":
        logout()
        st.stop()

    return escolha

# Executar o menu e obter a página atual
page = render_sidebar()


# --------------------------
# 1. Upload e Extração
# --------------------------
if page == "Upload":
    st.markdown("### 1. Upload e Extração de Dados") # Adicionei um emoji

    # NOVO TEXTO APRIMORADO E ADAPTADO AO CONTEXTO
    st.markdown(
        """
         **Bem-vindo(a) ao seu assistente financeiro inteligente!** 
         
        Para gerar a análise financeira, envie seus extratos bancários em PDF:
      
       
        1.  **Envie** o(s) seu(s) extrato(s) bancário(s) no formato **PDF** na seção abaixo (Upload de Arquivos).
        2.  Nossa IA **extrairá automaticamente** e **classificará** as transações de acordo com o nosso **Plano de Contas**.        
        3.  Você poderá revisar os dados e ajustar as classificações na seção **Revisão**.
        4.  Gere o seu Score Financeiro + Dashboard completo na seção **Dashboard**. 

               
        Consulte o Plano de Contas para detalhes sobre categorias.
        """
    )

    with st.expander("Plano de Contas Utilizado", expanded=False):
        st.caption(
            "Este é o plano de contas utilizado pela IA para classificar automaticamente "
            "as movimentações financeiras."
        )

        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            # Título do grupo sintético
            st.markdown(
                f"#### {sintetico['codigo']} — {sintetico['nome']} "
                f"({sintetico['tipo_fluxo']})"
            )  

            # Descrição do grupo
            if "descricao" in sintetico:
                st.markdown(f"📝 {sintetico['descricao']}")

            # Contas analíticas
            for conta in sintetico["contas"]:
                st.markdown(
                    f"- **{conta['codigo']} – {conta['nome']}**"
                    + (
                        f"<br><small>{conta['descricao']}</small>"
                        if "descricao" in conta
                        else ""
                    ),
                    unsafe_allow_html=True
                )

            st.markdown("---")

    with st.expander("Upload de Arquivos", expanded=True):
        uploaded_files = st.file_uploader(
            "Selecione PDFs",
            type="pdf",
            accept_multiple_files=True,
            key="pdf_uploader",
        )

    if not trial_ativo:
        st.warning("Funcionalidades de análise estão disponíveis apenas para o plano premium.")
        st.stop()


    if uploaded_files:
        st.success("✅ Arquivos prontos para processamento!") # Feedback visual
        if st.button(
            f"Executar Extração e Classificação ({len(uploaded_files)} arquivos)",
            key="analyze_btn",
        ):
            todas_transacoes = []
            extraction_status = st.empty()
            extraction_status.info("Iniciando extração.")


            # ============== USER ID AJUSTADO ================
            if isinstance(user, dict):
                user_id = user.get("id")
            else:
                user_id = getattr(user, "id", None)
            # =================================================

            for i, uploaded_file in enumerate(uploaded_files):
                extraction_status.info(
                    f"Processando arquivo {i+1}/{len(uploaded_files)}: {uploaded_file.name}"
                )
                pdf_bytes = uploaded_file.getvalue()

                # gerar hash do arquivo (identidade do PDF, não do extrato)
                file_hash = hashlib.sha256(pdf_bytes).hexdigest()

                # armazenar PDF no Storage
                if not user_id:
                    st.error("Usuário não identificado.")
                    st.stop()

                storage_path = f"{user_id}/{file_hash}_{uploaded_file.name}"

                try:
                    supabase.storage.from_("extratos").upload(
                        path=storage_path,
                        file=pdf_bytes,
                        file_options={"upsert": "true"}
                    )
                except Exception as e:
                    st.error(f"Erro ao enviar arquivo para o storage: {e}")
                    st.stop()

                # 🔑 SEMPRE criar um novo extrato
                try:
                    resultado = (
                        supabase.table("extratos")
                        .insert(
                            {
                                "user_id": user_id,
                                "nome_arquivo": uploaded_file.name,
                                "hash_arquivo": file_hash,
                                "arquivo_url": storage_path,
                            }
                        )
                        .execute()
                    )

                    extrato_id = resultado.data[0]["id"]
                except Exception as e:
                    st.error(f"Erro ao salvar metadados do extrato: {e}")
                    st.stop()



                # Extração com Gemini
                dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name, client)
                transacoes = dados_dict.get("transacoes", [])

                try:
                    memoria = (
                        supabase.table("classificacao_memoria")
                        .select("descricao_normalizada, conta_analitica")
                        .eq("user_id", user_id)
                        .execute()
                    )

                    memoria_data = memoria.data if memoria.data else []
                    mapa_memoria = {
                        m["descricao_normalizada"]: m["conta_analitica"]
                        for m in memoria_data
                    }

                    for t in transacoes:
                        desc_norm = normalizar_descricao(t.get("descricao", ""))

                        if desc_norm in mapa_memoria:
                            t["conta_analitica"] = mapa_memoria[desc_norm]
                            t["origem_classificacao"] = "memoria_usuario"
                        else:
                            t["origem_classificacao"] = "gemini"

                except Exception as e:
                    st.warning(f"Aviso: memória de classificação não aplicada ({e})")
                
                # vincular extrato_id
                for t in transacoes:
                    try:
                        t["extrato_id"] = extrato_id
                    except Exception:
                        t.update({"extrato_id": extrato_id})

                todas_transacoes.extend(transacoes)

            df_transacoes = pd.DataFrame(todas_transacoes)

            if df_transacoes.empty:
                extraction_status.error(
                    "❌ Nenhuma transação válida foi extraída."
                )
                st.session_state["df_transacoes_editado"] = pd.DataFrame()
            else:
                extraction_status.success(
                    f"✅ Extração de {len(todas_transacoes)} transações concluída!"
                )

                # Normalizações
                df_transacoes["valor"] = (
                    pd.to_numeric(df_transacoes["valor"], errors="coerce").fillna(0)
                )
                df_transacoes["data"] = pd.to_datetime(
                    df_transacoes["data"], errors="coerce", dayfirst=True
                )
                df_transacoes["tipo_movimentacao"] = df_transacoes[
                    "tipo_movimentacao"
                ].fillna("DEBITO")
                df_transacoes["conta_analitica"] = df_transacoes[
                    "conta_analitica"
                ].fillna("NE-02")

                df_transacoes = enriquecer_com_plano_contas(df_transacoes)

                st.session_state["df_transacoes_editado"] = df_transacoes
                st.success(
                    "Dados carregados e classificados. Vá para 'Revisão de Dados'."
                )

    # Extratos já carregados
    st.subheader("Extratos já carregados")
    try:

        # ============== USER ID AJUSTADO ================
        if isinstance(user, dict):
            user_id = user.get("id")
        else:
            user_id = getattr(user, "id", None)
        # =================================================

        extratos_existentes = (
            supabase.table("extratos")
            .select("id, nome_arquivo, criado_em")
            .eq("user_id", user_id)
            .order("criado_em", desc=True)
            .execute()
        )
        extratos_data = getattr(extratos_existentes, "data", extratos_existentes)

        if not extratos_data:
            st.info("Nenhum extrato carregado ainda.")
        else:
            df_extratos = pd.DataFrame(extratos_data)
            if "criado_em" in df_extratos.columns:
                try:
                    df_extratos["criado_em"] = (
                        pd.to_datetime(df_extratos["criado_em"])
                        .dt.strftime("%d/%m/%Y %H:%M")
                    )
                except Exception:
                    pass
            st.dataframe(
                df_extratos[["id", "nome_arquivo", "criado_em"]],
                use_container_width=True,
            )
    except Exception as e:
        st.error(f"Erro ao buscar extratos: {e}")


# --------------------------
# 2. Revisão de Dados
# --------------------------
elif page == "Revisão":
    st.markdown("### 2. Revisão e Correção Manual dos Dados")

    if not st.session_state.get("df_transacoes_editado", pd.DataFrame()).empty:
        st.info("Revise as classificações manualmente.")

        opcoes_contas = []
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            for conta in sintetico["contas"]:
                opcoes_contas.append(f"{conta['codigo']} - {conta['nome']}")

        df_display_edit = st.session_state["df_transacoes_editado"].copy()
        if "conta_display" not in df_display_edit.columns:
            df_display_edit = enriquecer_com_plano_contas(df_display_edit)

        columns_for_editor = [
            "data",
            "descricao",
            "valor",
            "tipo_movimentacao",
            "conta_display",
            "nome_conta",
            "tipo_fluxo",
        ]
        if "extrato_id" in df_display_edit.columns:
            columns_for_editor.append("extrato_id")

        with st.expander("Editar Transações", expanded=True):
            edited_df = st.data_editor(
                df_display_edit[columns_for_editor],
                width="stretch",
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "descricao": st.column_config.TextColumn("Descrição", width="large"),
                    "valor": st.column_config.NumberColumn(
                        "Valor (R$)", format="R$ %.2f"
                    ),
                    "tipo_movimentacao": st.column_config.SelectboxColumn(
                        "Tipo", options=["CREDITO", "DEBITO"]
                    ),
                    "conta_display": st.column_config.SelectboxColumn(
                        "Conta (código - nome)", options=opcoes_contas
                    ),
                    "nome_conta": st.column_config.TextColumn(
                        "Nome da Conta", disabled=True
                    ),
                    "tipo_fluxo": st.column_config.TextColumn(
                        "Tipo de Fluxo", disabled=True
                    ),
                },
                num_rows="dynamic",
                key="data_editor_transacoes",
            )

        if st.button("Confirmar Dados e Salvar no Banco de Dados"):
            try:
                if "conta_display" in edited_df.columns:
                    edited_df["conta_analitica"] = edited_df["conta_display"].apply(
                        lambda x: x.split(" - ")[0].strip()
                        if isinstance(x, str) and " - " in x
                        else x
                    )

                edited_df = enriquecer_com_plano_contas(edited_df)

                df_to_save = edited_df.copy()
                df_to_save["data"] = (
                    pd.to_datetime(df_to_save["data"], errors="coerce")
                    .dt.strftime("%Y-%m-%d")
                )
                df_to_save["valor"] = (
                    pd.to_numeric(df_to_save["valor"], errors="coerce").fillna(0)
                )

                colunas_validas = [
                    "data",
                    "descricao",
                    "valor",
                    "tipo_movimentacao",
                    "conta_analitica",
                ]
                if "extrato_id" in df_to_save.columns:
                    colunas_validas.append("extrato_id")
                df_to_save = df_to_save[colunas_validas]

                # ============== USER ID AJUSTADO ================
                if isinstance(user, dict):
                    user_id = user.get("id")
                else:
                    user_id = getattr(user, "id", None)
                # =================================================

               # try:
                   # supabase.table("transacoes").delete().eq("user_id", user_id).execute()
                #except Exception:
                  #  st.warning(
                   #     "Aviso: não foi possível deletar transações antigas (permissões Supabase)."
                  #  )

                try:
                    # Identificar os extratos envolvidos
                    extrato_ids = df_to_save["extrato_id"].dropna().unique().tolist()

                    # Apagar somente as transações que pertencem aos mesmos extratos
                    for ex_id in extrato_ids:
                        supabase.table("transacoes").delete().eq("extrato_id", ex_id).execute()

                except Exception as e:
                    st.warning(
                        f"Aviso: não foi possível remover transações antigas dos extratos reprocessados. Detalhes: {e}"
                     ) 

                records = df_to_save.to_dict(orient="records")
                for rec in records:
                    rec["user_id"] = user_id
                    if "extrato_id" not in rec:
                        rec["extrato_id"] = None

                try:
                    supabase.table("transacoes").insert(records).execute()
                except Exception as e:
                    st.error(f"Erro ao inserir transações: {e}")
                    raise

                
                try:
                    memoria_unica = {}

                    for _, row in edited_df.iterrows():
                        if row.get("origem_classificacao") == "memoria_usuario":
                            continue  # não reaprender o que já veio da memória

                        descricao_norm = normalizar_descricao(row.get("descricao", ""))

                        chave = (user_id, descricao_norm)

                        memoria_unica[chave] = {
                            "user_id": user_id,
                            "descricao_normalizada": descricao_norm,
                            "conta_analitica": row.get("conta_analitica"),
                            "criado_em": datetime.utcnow().isoformat()
                        }

                    if memoria_unica:
                        supabase.table("classificacao_memoria").upsert(
                            list(memoria_unica.values()),
                            on_conflict="user_id,descricao_normalizada"
                        ).execute()

                except Exception as e:
                    st.warning(f"Aviso: memória de classificação não atualizada ({e})")
    
                
                st.session_state["df_transacoes_editado"] = edited_df
                st.success("Transações salvas com sucesso!")
            except Exception as e:
                st.error(f"Erro ao confirmar e salvar: {e}")

    else:
        st.warning("Nenhum dado processado. Volte à etapa 'Upload e Extração'.")


# --------------------------
# 3. Dashboard & Relatórios
# --------------------------
elif page == "Dashboard":
    st.markdown("### 3. Relatórios Gerenciais e Dashboard")

    # === CSS para os date_input ===
    st.markdown(
        """
        <style>
            /* Estilização para os campos de data */
            div[data-baseweb="input"] input {
                border: 2px solid #0A2342 !important;
                border-radius: 6px !important;
                padding: 8px 10px !important;
            }
            div[data-baseweb="input"] input:focus {
                border-color: #007BFF !important;
                box-shadow: 0 0 4px #007BFF !important;
            }
            /* Título da seção de datas */
            .period-title {
                font-size: 18px;
                font-weight: 600;
                color: #0A2342;
                margin-bottom: 15px;
                margin-top: 20px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # === Seleção de período ===
    st.markdown('<div class="period-title">📅 Selecione o Período de Análise</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        data_inicial = st.date_input(
            "Data Inicial",
            value=datetime.now() - timedelta(days=90),  # Padrão: últimos 3 meses
            format="DD/MM/YYYY",
            help="Clique para selecionar a data",
            key="dt_ini"
        )
    
    with col2:
        data_final = st.date_input(
            "Data Final",
            value=datetime.now(),  # Padrão: hoje
            format="DD/MM/YYYY",
            help="Clique para selecionar a data",
            key="dt_fim"
        )
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)  # Espaçamento
        gerar = st.button("🔄 Gerar", use_container_width=True, type="primary")

    st.markdown("---")

    # === Lógica de geração de relatórios ===
    if gerar:
        try:
            # Validar se as datas foram selecionadas
            if data_inicial is None or data_final is None:
                st.error("Por favor, selecione ambas as datas.")
            elif data_inicial > data_final:
                st.error("A data inicial não pode ser maior que a data final.")
            else:
                # Converter para string ISO
                data_inicial_iso = data_inicial.strftime("%Y-%m-%d")
                data_final_iso = data_final.strftime("%Y-%m-%d")

                # USER ID
                if isinstance(user, dict):
                    user_id = user.get("id")
                else:
                    user_id = getattr(user, "id", None)

                # Buscar transações no Supabase
                with st.spinner("Carregando transações..."):
                    resultado = (
                        supabase.table("transacoes")
                        .select("*")
                        .eq("user_id", user_id)
                        .gte("data", data_inicial_iso)
                        .lte("data", data_final_iso)
                        .execute()
                    )

                    resultado_data = getattr(resultado, "data", resultado)

                    if not resultado_data:
                        st.warning(f"Nenhuma transação encontrada no período de {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}.")
                    else:
                        df_relatorio = pd.DataFrame(resultado_data)
                        df_relatorio["data"] = pd.to_datetime(df_relatorio["data"], errors="coerce")
                        df_relatorio["valor"] = pd.to_numeric(df_relatorio["valor"], errors="coerce").fillna(0)
                        df_relatorio = enriquecer_com_plano_contas(df_relatorio)

                        st.session_state["df_transacoes_editado"] = df_relatorio.copy()
                        
                        # Feedback visual
                        periodo_str = f"{data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"
                        st.success(f"✅ {len(df_relatorio)} transações carregadas para o período: {periodo_str}")

        except Exception as e:
            st.error(f"Erro ao gerar relatórios: {e}")

    # === Dashboard / Relatórios ===
    if not st.session_state.get("df_transacoes_editado", pd.DataFrame()).empty:
        df_final = st.session_state["df_transacoes_editado"].copy()
        
        # Mostrar info do período carregado
        if not df_final.empty and 'data' in df_final.columns:
            df_final_datas = df_final[df_final['data'].notna()]
            if not df_final_datas.empty:
                data_min = df_final_datas['data'].min()
                data_max = df_final_datas['data'].max()
                st.info(f"📊 Exibindo análise do período: {data_min.strftime('%d/%m/%Y')} a {data_max.strftime('%d/%m/%Y')}")
        
        try:
            secao_relatorios_dashboard(df_final, PLANO_DE_CONTAS)
        except Exception as e:
            st.error(f"Erro ao gerar relatórios/dashboard: {e}")
    else:
        st.info("👆 Selecione um período acima e clique em 'Gerar' para visualizar o dashboard.")

# --------------------------
# 4. Perfil do Usuário 
# --------------------------

elif page == "Perfil":

    # === CSS IGUAL AO DA TELA DE LOGIN ===
    st.markdown("""
        <style>
            input[type="text"], input[type="email"], textarea {
                border: 1px solid #0A2342 !important;
                border-radius: 6px !important;
                padding: 8px 10px !important;
            }
            input[type="text"]:focus, input[type="email"]:focus, textarea:focus {
                border-color: #007BFF !important;
                box-shadow: 0 0 4px #007BFF !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("### 4. Meu Perfil")

    # Extrair user_id e email — compatível com dict/obj
    if isinstance(user, dict):
        user_id = user.get("id")
        email_user = user.get("email", "")
    else:
        user_id = getattr(user, "id", None)
        email_user = getattr(user, "email", "")

    if not user_id:
        st.error("Não foi possível identificar o usuário logado.")
        st.stop()

    st.write(f"**E-mail:** {email_user}")
    st.markdown("---")

    # Buscar no banco
    try:
        perfil_res = supabase.table("users_profiles").select("*").eq("id", user_id).execute()
        perfil_data = getattr(perfil_res, "data", perfil_res)
        perfil = perfil_data[0] if perfil_data else {}
    except Exception as e:
        st.error(f"Erro ao carregar perfil: {e}")
        perfil = {}

    # Formulário
    nome = st.text_input("Nome completo", perfil.get("nome", ""))
    empresa = st.text_input("Empresa", perfil.get("empresa", ""))
    cnpj = st.text_input("CNPJ (opcional)", perfil.get("cnpj", ""))
    socios = st.text_area("Sócios (separados por vírgula)", perfil.get("socios", ""))

    st.markdown("---")

    # Exibir plano atual
    plano = perfil.get("plano", "free")
    st.info(f" **Plano atual:** `{plano.upper()}`")
    st.caption("Mudanças de plano podem ser feitas na aba *Planos*.")

    # Botão salvar
    if st.button("Salvar Alterações"):
        try:
            supabase.table("users_profiles").upsert(
                {
                    "id": user_id,
                    "nome": nome,
                    "empresa": empresa,
                    "cnpj": cnpj,
                    "socios": socios,
                    "plano": plano  # Mantém o plano atual
                }
            ).execute()
            st.success("Perfil atualizado com sucesso!")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

# --------------------------
# 5. PLANOS
# --------------------------


elif page == "Planos":
    st.markdown("### 5. Planos e Assinaturas")

    # --- Pegar plano atual do usuário ---
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        st.error("Usuário não identificado.")
        st.stop()

    try:
        res = supabase.table("users_profiles").select("plano").eq("id", user_id).execute()
        plano_atual = res.data[0]["plano"].lower() if res.data else "free"
    except:
        plano_atual = "free"

    st.info(f"**Seu plano atual:** `{plano_atual.upper()}`")
    st.markdown("---")

    # CSS dos cards (agora com altura mínima e fundo correto)
    st.markdown("""
    <style>
        .card-plano {
            background: white;
            border: 2px solid #0A2342;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 6px 16px rgba(10, 35, 66, 0.12);
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .titulo-plano {
            font-size: 26px;
            font-weight: 800;
            color: #0A2342;
            margin-bottom: 12px;
        }
        .preco-plano {
            font-size: 36px;
            font-weight: 900;
            color: #007BFF;
            margin: 16px 0;
        }
        .lista-beneficios {
            font-size: 15px;
            line-height: 1.7;
            margin: 16px 0;
            flex-grow: 1;
        }
    </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div class="card-plano">
            <div class="titulo-plano">Plano FREE(TRIAL)</div>
            <p style="color:#555; margin-bottom:16px;">Ideal para começar</p>
            <div class="lista-beneficios">
                Upload de extratos (PDF)<br>
                Classificação automática com IA<br>
                Dashboard<br>
                Score de saúde financeira<br>
                Relatório de fluxo de caixa
            </div>
            <div class="preco-plano">R$ 0<small style="font-size:18px;">/mês</small></div>
            <button style='background:#6c757d; color:white; padding:12px; border:none; border-radius:8px; width:100%; font-weight:bold; cursor:not-allowed;'>
            Plano gratuito permanente
            </button>

        </div>
        """, unsafe_allow_html=True)
    
    
    with col2:
        st.markdown(f"""
        <div class="card-plano">
            <div class="titulo-plano">Plano PREMIUM</div>
            <p style="color:#555; margin-bottom:16px;">Para quem quer performance máxima</p>
            <div class="lista-beneficios">
                Tudo do FREE (TRIAL) +<br>
                Comparativos mensais e anuais<br>
                Backup prioritário e histórico ilimitado<br>
                Suporte por WhatsApp
            </div>
            <div class="preco-plano">
                <span style="text-decoration: line-through; color:#999; font-size:22px;">
                    R$ 29,90
                </span><br>
                <span style="color:#007BFF;">
                    R$ 19,82
                </span>
                <small style="font-size:18px;">/mês</small>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if plano_atual == "premium":
            st.markdown(
                "<button style='background:#28a745; color:white; padding:14px; border:none; border-radius:10px; width:100%; font-weight:bold; font-size:18px;'>Você já é PREMIUM</button>",
                unsafe_allow_html=True
            )

        else:
           

            components.html(
                f"""
                <button
                    style="
                        background:#007BFF;
                        color:white;            
                        padding:14px;
                        border:none;
                        border-radius:10px;
                        width:100%;
                        font-weight:bold;
                        font-size:18px;
                        cursor:pointer;
                    "
                    onclick="window.open('{MP_SUBSCRIPTION_URL}', '_blank')"
                >
                    Quero ser Premium
                </button>
                """,
                height=70
            )




# --------------------------
# 6. CONFIGURAÇÕES
# --------------------------
elif page == "Configurações":

    st.markdown("""
        <style>
            .config-card {
                border: 1px solid #0A2342;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 12px;
                background-color: #F8FBFF;
            }
            .config-titulo {
                font-size: 20px; 
                font-weight: 700; 
                color: #0A2342;
            }
            input[type="password"] {
                border: 1px solid #0A2342 !important;
                border-radius: 6px !important;
                padding: 8px 10px !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("### 6. Configurações")

    if isinstance(user, dict):
        user_id = user.get("id")
        email_user = user.get("email", "")
    else:
        user_id = getattr(user, "id", None)
        email_user = getattr(user, "email", "")

    if not user_id:
        st.error("Não foi possível identificar o usuário logado.")
        st.stop()

    # buscar configurações simples (se existirem)
    try:
        res = supabase.table("users_profiles").select("moeda, formato_data").eq("id", user_id).execute()
        dados_cfg = getattr(res, "data", res)
        dados_cfg = dados_cfg[0] if dados_cfg else {}
    except:
        dados_cfg = {}

    moeda_atual = dados_cfg.get("moeda", "BRL")
    formato_atual = dados_cfg.get("formato_data", "br")

    st.markdown('<div class="config-card">', unsafe_allow_html=True)
    st.markdown('<div class="config-titulo">Preferências Básicas</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        moeda = st.selectbox("Moeda padrão:", ["BRL (R$)", "USD ($)", "EUR (€)"], index=0 if moeda_atual=="BRL" else 1 if moeda_atual=="USD" else 2)
        formato_data = st.selectbox("Formato de data:", ["Brasil (DD/MM/AAAA)", "Internacional (YYYY-MM-DD)"], index=0 if formato_atual=="br" else 1)

    with col2:
        st.markdown("**Alterar senha**")
        nova = st.text_input("Nova senha", type="password")
        nova2 = st.text_input("Repita a nova senha", type="password")

        if st.button("Alterar senha"):
            if not nova or not nova2:
                st.warning("Preencha os dois campos de senha.")
            elif nova != nova2:
                st.error("As senhas não coincidem.")
            else:
                try:
                    # utiliza supabase auth para atualizar a senha do usuário atual
                    supabase.auth.update_user({"password": nova})
                    st.success("Senha atualizada com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao alterar senha: {e}")

    # salvar preferências
    if st.button("Salvar preferências"):
        try:
            supabase.table("users_profiles").update({
                "moeda": "BRL" if "BRL" in moeda else "USD" if "USD" in moeda else "EUR",
                "formato_data": "br" if "Brasil" in formato_data else "iso"
            }).eq("id", user_id).execute()
            st.success("Preferências salvas!")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Erro ao salvar preferências: {e}")

    st.markdown('</div>', unsafe_allow_html=True)


# --------------------------
# --- Footer ----
# --------------------------
st.markdown("---")
try:
    footer_logo = Image.open(LOGO_FILENAME)
    col1, col2 = st.columns([1, 20])
    with col1:
        st.image(footer_logo, width=40)
    with col2:
        st.markdown(
            "<p style='font-size:0.9rem; color:#6c757d; margin:0;'>Análise de Extrato Empresarial | Dados extraídos e classificados com IA.</p>",
            unsafe_allow_html=True
        )
except Exception:
    st.markdown(
        "<p style='font-size:0.9rem; color:#6c757d; margin:0;'>Análise de Extrato Empresarial | Dados extraídos e classificados com IA.</p>",
        unsafe_allow_html=True
    )

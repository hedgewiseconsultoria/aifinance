# app_supabase.py  (salve como app_supabase.txt ou .py)
import streamlit as st
import pandas as pd
import json
import io
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from google import genai
from google.genai import types
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
import traceback
import math

# Inserções para Supabase / autenticação
from auth import login_page, logout, supabase
import hashlib
from datetime import datetime, timedelta

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
                {"codigo": "OP-02", "nome": "Receitas de Serviços"},
                {"codigo": "OP-03", "nome": "Outras Receitas Operacionais"},
                {"codigo": "OP-04", "nome": "Custos Operacionais"},
                {"codigo": "OP-05", "nome": "Despesas Administrativas"},
                {"codigo": "OP-06", "nome": "Despesas Comerciais"},
                {"codigo": "OP-07", "nome": "Despesas Pessoais Misturadas"},
                {"codigo": "OP-08", "nome": "Impostos e Contribuições"},
                {"codigo": "OP-09", "nome": "Tarifas Bancárias e Serviços"}
            ]
        },
        {
            "codigo": "INV",
            "nome": "Atividades de Investimento",
            "tipo_fluxo": "INVESTIMENTO",
            "contas": [
                {"codigo": "INV-01", "nome": "Aquisição de Imobilizado"},
                {"codigo": "INV-02", "nome": "Aplicações Financeiras"},
                {"codigo": "INV-03", "nome": "Alienação de Ativos"}
            ]
        },
        {
            "codigo": "FIN",
            "nome": "Atividades de Financiamento",
            "tipo_fluxo": "FINANCIAMENTO",
            "contas": [
                {"codigo": "FIN-01", "nome": "Empréstimos Recebidos"},
                {"codigo": "FIN-02", "nome": "Pagamento de Empréstimos"},
                {"codigo": "FIN-03", "nome": "Juros sobre Empréstimos e Financiamentos"},
                {"codigo": "FIN-04", "nome": "Aporte de Sócios"},
                {"codigo": "FIN-05", "nome": "Retirada de Sócios / Pró-labore"}
            ]
        },
        {
            "codigo": "NE",
            "nome": "Ajustes e Transferências Internas",
            "tipo_fluxo": "NEUTRO",
            "contas": [
                {"codigo": "NE-01", "nome": "Transferências entre Contas"},
                {"codigo": "NE-02", "nome": "Ajustes e Estornos"}
            ]
        }
    ]
}

# --- FUNÇÃO DE FORMATAÇÃO BRL ---
def formatar_brl(valor: float) -> str:
    """Formata um valor float para a moeda Real Brasileiro (R$ xx.xxx,xx)."""
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP_SEP").replace(".", ",").replace("TEMP_SEP", ".")
        return "R$ " + valor_brl
    except Exception:
        return f"R$ {valor:.2f}"

# --- FUNÇÃO LOCAL: GERAR MINI-RELATÓRIO ---
def gerar_mini_relatorio_local(score: float, indicadores: Dict[str, float], retiradas_pessoais_val: float):
    """Gera HTML limpo do mini-relatório (pronto para st.markdown com unsafe_allow_html=True)."""
    gco = indicadores.get('gco', 0.0)
    entradas_op = indicadores.get('entradas_operacionais', 0.0)
    autossuf = indicadores.get('autossuficiencia', 0.0)
    taxa_reinv = indicadores.get('taxa_reinvestimento', 0.0)
    peso_retiradas = indicadores.get('peso_retiradas', 0.0)

    def cor_icone(valor, tipo="financeiro", contexto_caixa_negativo=False):
        if tipo == "financeiro":
            if contexto_caixa_negativo:
                return "NEGATIVO"
            return "POSITIVO" if valor > 0 else ("NEUTRO" if valor == 0 else "NEGATIVO")
        if tipo == "autossuficiencia":
            if valor == float('inf') or valor > 1.0:
                return "ALTO"
            elif valor >= 0.5:
                return "MEDIO"
            else:
                return "BAIXO"
        return ""

    def span_valor(valor_formatado, cor):
        return f"<span style='font-weight:700;'>{cor} {valor_formatado}</span>"

    if score >= 85:
        resumo = "Situação muito saudável: boa geração de caixa e equilíbrio nas finanças."
        classe_texto = "Classe A – Excelente: finanças equilibradas e bom controle de caixa."
    elif score >= 70:
        resumo = "Situação estável, mas requer acompanhamento de retiradas e uso de financiamentos."
        classe_texto = "Classe B – Boa: estrutura financeira estável, mantenha o acompanhamento periódico."
    elif score >= 55:
        if gco > 0:
            resumo = "Situação aceitável: o caixa operacional está positivo, mas o score indica que há espaço para melhorar a eficiência financeira."
            classe_texto = "Classe C – Moderado: o caixa é positivo e a autossuficiência é boa; acompanhe retiradas e mantenha disciplina financeira."
        else:
            resumo = "Caixa pressionado — atenção às despesas fixas e retiradas para evitar desequilíbrio."
            classe_texto = "Classe D – Alto risco: atenção às despesas e à liquidez, recomenda-se reforçar o caixa."
    elif score >= 40:
        if gco > 0 and autossuf >= 1.0:
            resumo = "Situação aceitável, mas exige disciplina para manter o equilíbrio do caixa."
            classe_texto = "Classe C – Moderado: o caixa é positivo e a autossuficiência é boa; acompanhe retiradas e mantenha disciplina financeira."
        else:
            resumo = "Risco elevado: o caixa tende a ficar pressionado se não houver ajuste nas retiradas e custos."
            classe_texto = "Classe D – Alto risco: atenção às despesas e à liquidez, recomenda-se reforçar o caixa."
    else:
        resumo = "Situação crítica: priorize ações imediatas para reforçar o caixa e renegociar dívidas."
        classe_texto = "Classe E – Crítico: risco elevado de desequilíbrio financeiro, ações corretivas imediatas são recomendadas."

    if gco > 0:
        comentario_gco = "isso contribui positivamente para a saúde financeira e reduz o risco da empresa."
    elif gco == 0:
        comentario_gco = "a neutralidade indica que o negócio está apenas se mantendo, sem gerar caixa adicional."
    else:
        comentario_gco = "este valor negativo aumenta o risco e indica que a operação está consumindo mais do que gera."

    if gco < 0:
        comentario_retiradas = "O caixa operacional está negativo; não há sustentabilidade para retiradas neste período."
    elif retiradas_pessoais_val <= 0:
        comentario_retiradas = "Não houve retiradas pessoais, o que ajuda na preservação do caixa."
    elif retiradas_pessoais_val < 0.3 * max(entradas_op, 1):
        comentario_retiradas = "Retiradas em nível saudável, sem comprometer o caixa."
    elif retiradas_pessoais_val < 0.6 * max(entradas_op, 1):
        comentario_retiradas = "Retiradas moderadas, que merecem monitoramento."
    else:
        comentario_retiradas = "Retiradas elevadas, que aumentam o risco financeiro e reduzem a folga de caixa."

    if autossuf == float('inf') or autossuf > 1.5:
        comentario_autossuf = "Excelente autossuficiência: o negócio gera caixa suficiente para cobrir retiradas e investimentos."
    elif autossuf >= 1.0:
        comentario_autossuf = "Autossuficiência adequada, com boa capacidade de financiar obrigações internas."
    elif autossuf >= 0.5:
        comentario_autossuf = "Autossuficiência parcial: é preciso reforçar geração interna de caixa."
    else:
        comentario_autossuf = "Baixo nível de autossuficiência: o negócio depende de capital externo, elevando o risco."

    recs = []
    if gco <= 0:
        recs.append("Revise as entradas operacionais e priorize ações que aumentem as vendas ou captação de receitas.")
    if peso_retiradas > 0.5 or (entradas_op > 0 and (retiradas_pessoais_val / entradas_op) > 0.5):
        recs.append("Reduza retiradas pessoais para preservar caixa operacional.")
    if taxa_reinv >= 0.30:
        recs.append("Bom nível de reinvestimento — mantenha disciplina para colher ganhos futuros.")
    if autossuf < 0.5:
        recs.append("Aumente a autossuficiência operacional antes de expandir investimentos.")
    if not recs:
        recs.append("Mantenha controles atuais de custos e planejamento financeiro.")

    val_gco = span_valor(formatar_brl(gco), cor_icone(gco, "financeiro"))
    val_retir = span_valor(formatar_brl(retiradas_pessoais_val), cor_icone(retiradas_pessoais_val, "financeiro", contexto_caixa_negativo=(gco < 0)))
    aut_text = "∞" if autossuf == float('inf') else f"{autossuf:.2f}"
    val_aut = span_valor(aut_text, cor_icone(autossuf, "autossuficiencia"))

    html = (
        "<div style='line-height:1.6;font-size:15px;'>"
        f"<b>Score Financeiro:</b> {score:.1f}<br><br>"
        f"<b>Resumo:</b> {resumo}<br><br>"
        f"<b>Caixa operacional gerado (período):</b> {val_gco} — {comentario_gco}<br>"
        f"<b>Retiradas de sócios:</b> {val_retir} — {comentario_retiradas}<br>"
        f"<b>Autossuficiência operacional:</b> {val_aut} — {comentario_autossuf}<br><br>"
        f"<b>Recomendações práticas:</b> {' '.join(recs)}"
        "</div>"
    )

    return html, classe_texto

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
LOGO1_FILENAME = "FinanceAI_1.png"

st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon="logo_hedgewise.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Forçar modo claro
st.markdown(
    """
    <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {
            background-color: #F0F2F6 !important;
            color: #000000 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
        }
        @media (prefers-color-scheme: dark) {
            html {
                color-scheme: light !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True
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
            font-size: 1.7em;
            padding-bottom: 2px;
            font-weight:800;
        }}
        .kpi-container {{
            background-color: white;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 6px 15px 0 rgba(0, 0, 0, 0.06);
            margin-bottom: 18px;
        }}
        h2 {{
            color: {PRIMARY_COLOR};
            border-left: 5px solid {PRIMARY_COLOR};
            padding-left: 10px;
            margin-top: 20px;
            margin-bottom: 16px;
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
            transform: scale(1.03);
        }}
        .fluxo-table {{
            background-color: white;
            border-radius: 8px;
            padding: 14px;
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

# Inicializa o cliente Gemini (mantendo a forma original de chamada)
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except (KeyError, AttributeError):
    st.error("ERRO: Chave 'GEMINI_API_KEY' não encontrada. Configure-a para rodar a aplicação.")
    st.stop()

# DEBUG flag (opcional, configurável em secrets)
DEBUG = bool(st.secrets.get("DEBUG", False))

# --- 2. DEFINIÇÃO DO SCHEMA PYDANTIC ---
class Transacao(BaseModel):
    data: str = Field(description="A data da transação no formato 'DD/MM/AAAA'.")
    descricao: str = Field(description="Descrição detalhada da transação.")
    valor: float = Field(description="O valor numérico da transação. Sempre positivo.")
    tipo_movimentacao: str = Field(description="Classificação da movimentação: 'DEBITO' ou 'CREDITO'.")
    conta_analitica: str = Field(description="Código da conta analítica do plano de contas (ex: OP-01, INV-02, FIN-05).")

class AnaliseCompleta(BaseModel):
    transacoes: List[Transacao] = Field(description="Uma lista de objetos 'Transacao' extraídos do documento.")
    saldo_final: float = Field(description="O saldo final da conta no extrato. Use zero se não for encontrado.")

# -----------------------
# CLASSES DE INDICADORES
# -----------------------
class IndicadoresFluxo:
    def __init__(self, df: pd.DataFrame):
        self.df_raw = df.copy()
        self.df = self._prepare(df.copy())
        self.meses = self._obter_meses()
    
    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['data']).copy()
        df['fluxo'] = df.apply(lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], axis=1)
        df['mes_ano'] = df['data'].dt.to_period('M')
        return df

    def _obter_meses(self):
        df_fluxo = self.df[self.df['tipo_fluxo'] != 'NEUTRO']
        meses = sorted(df_fluxo['mes_ano'].unique())
        return meses

    def total_entradas_operacionais(self):
        df_fluxo = self.df
        return df_fluxo[(df_fluxo['tipo_fluxo']=='OPERACIONAL') & (df_fluxo['tipo_movimentacao']=='CREDITO')]['valor'].sum()

    def caixa_operacional_total(self):
        df_fluxo = self.df
        return df_fluxo[df_fluxo['tipo_fluxo']=='OPERACIONAL']['fluxo'].sum()

    def caixa_investimento_total(self):
        return self.df[self.df['tipo_fluxo']=='INVESTIMENTO']['fluxo'].sum()

    def caixa_financiamento_total(self):
        return self.df[self.df['tipo_fluxo']=='FINANCIAMENTO']['fluxo'].sum()

    def retirada_pessoal_total(self):
        return abs(self.df[(self.df['conta_analitica']=='FIN-05') & (self.df['tipo_movimentacao']=='DEBITO')]['valor'].sum())

    def margem_caixa_operacional(self):
        entradas_op = self.total_entradas_operacionais()
        caixa_op = self.caixa_operacional_total()
        return (caixa_op / entradas_op) if entradas_op > 0 else 0.0

    def intensidade_investimento(self):
        caixa_op = self.caixa_operacional_total()
        caixa_inv = self.caixa_investimento_total()
        return (abs(caixa_inv) / caixa_op) if caixa_op != 0 else 0.0

    def intensidade_financiamento(self):
        caixa_op = self.caixa_operacional_total()
        caixa_fin = self.caixa_financiamento_total()
        return (caixa_fin / caixa_op) if caixa_op != 0 else 0.0

    def peso_retiradas(self):
        total_saidas = self.df[self.df['tipo_movimentacao']=='DEBITO']['valor'].sum()
        retiradas = self.retirada_pessoal_total()
        return (retiradas / total_saidas) if total_saidas != 0 else 0.0

    def crescimento_entradas(self):
        meses = self.meses
        if len(meses) < 2:
            return 0.0
        ultimo = meses[-1]
        anterior = meses[-2]
        entradas_ultimo = self.df[(self.df['mes_ano']==ultimo) & (self.df['tipo_fluxo']=='OPERACIONAL') & (self.df['tipo_movimentacao']=='CREDITO')]['valor'].sum()
        entradas_anterior = self.df[(self.df['mes_ano']==anterior) & (self.df['tipo_fluxo']=='OPERACIONAL') & (self.df['tipo_movimentacao']=='CREDITO')]['valor'].sum()
        if entradas_anterior == 0:
            return (entradas_ultimo - entradas_anterior) / (entradas_ultimo) if entradas_ultimo != 0 else 0.0
        return (entradas_ultimo - entradas_anterior) / entradas_anterior

    def taxa_reinvestimento(self):
        caixa_op = self.caixa_operacional_total()
        caixa_inv = self.caixa_investimento_total()
        return (abs(caixa_inv) / caixa_op) if caixa_op != 0 else 0.0

    def autossuficiencia_operacional(self):
        gco = self.caixa_operacional_total()
        inv = abs(self.caixa_investimento_total())
        retir = self.retirada_pessoal_total()
        denom = inv + retir
        if denom == 0:
            return float('inf') if gco > 0 else 0.0
        return gco / denom

    def resumo_indicadores(self) -> Dict[str, float]:
        return {
            "gco": self.caixa_operacional_total(),
            "entradas_operacionais": self.total_entradas_operacionais(),
            "margem_op": self.margem_caixa_operacional(),
            "intensidade_inv": self.intensidade_investimento(),
            "intensidade_fin": self.intensidade_financiamento(),
            "peso_retiradas": self.peso_retiradas(),
            "crescimento_entradas": self.crescimento_entradas(),
            "taxa_reinvestimento": self.taxa_reinvestimento(),
            "autossuficiencia": self.autossuficiencia_operacional()
        }

# -----------------------
# SCORE CALCULATOR
# -----------------------
class ScoreCalculator:
    def __init__(self, pesos: Optional[Dict[str, float]] = None):
        self.pesos = pesos or {
            "gco": 25,
            "margem_op": 10,
            "peso_retiradas": 15,
            "intensidade_fin": 15,
            "crescimento_entradas": 15,
            "taxa_reinvestimento": 10,
            "autossuficiencia": 10
        }
        total = sum(self.pesos.values())
        if total != 100:
            for k in self.pesos:
                self.pesos[k] = self.pesos[k] * 100.0 / total

    def normalizar_gco(self, gco: float, entradas_op: float) -> float:
        if entradas_op <= 0:
            return 0.0
        ratio = gco / entradas_op
        if ratio >= 0.20:
            return 100.0
        elif ratio >= 0.10:
            return 80.0
        elif ratio >= 0.05:
            return 60.0
        elif ratio >= 0.0:
            return 40.0
        else:
            return 0.0

    def normalizar_margem(self, margem: float) -> float:
        return self.normalizar_gco(margem * 1.0, 1.0) if margem is not None else 0.0

    def normalizar_peso_retiradas(self, peso: float) -> float:
        if peso <= 0.20:
            return 100.0
        elif peso <= 0.30:
            return 80.0
        elif peso <= 0.50:
            return 50.0
        elif peso <= 0.80:
            return 20.0
        else:
            return 0.0

    def normalizar_intensidade_fin(self, intensidade: float, margem_op: float) -> float:
        if intensidade >= 0:
            if intensidade <= 0.30:
                return 100.0
            elif intensidade <= 1.0:
                return 70.0
            else:
                return 50.0 if margem_op >= 0.10 else 30.0
        else:
            if margem_op >= 0.15:
                return 100.0
            elif margem_op >= 0.10:
                return 70.0
            elif margem_op >= 0.05:
                return 40.0
            else:
                return 10.0

    def normalizar_crescimento(self, crescimento: float) -> float:
        if crescimento >= 0.10:
            return 100.0
        elif crescimento >= 0.03:
            return 70.0
        elif crescimento >= -0.05:
            return 50.0
        else:
            return 20.0

    def normalizar_reinvestimento(self, taxa: float) -> float:
        if taxa >= 0.30:
            return 100.0
        elif taxa >= 0.10:
            return 80.0
        elif taxa > 0:
            return 60.0
        else:
            return 20.0

    def normalizar_autossuficiencia(self, autossuf: float) -> float:
        if math.isinf(autossuf):
            return 100.0
        if autossuf >= 1.5:
            return 100.0
        elif autossuf >= 1.0:
            return 80.0
        elif autossuf >= 0.5:
            return 50.0
        else:
            return 20.0

    def calcular_score(self, indicadores: Dict[str, float]) -> Dict[str, Any]:
        notas = {}
        notas['gco'] = self.normalizar_gco(indicadores.get('gco', 0.0), indicadores.get('entradas_operacionais', 0.0))
        notas['margem_op'] = self.normalizar_margem(indicadores.get('margem_op', 0.0))
        notas['peso_retiradas'] = self.normalizar_peso_retiradas(indicadores.get('peso_retiradas', 0.0))
        notas['intensidade_fin'] = self.normalizar_intensidade_fin(indicadores.get('intensidade_fin', 0.0), indicadores.get('margem_op', 0.0))
        notas['crescimento_entradas'] = self.normalizar_crescimento(indicadores.get('crescimento_entradas', 0.0))
        notas['taxa_reinvestimento'] = self.normalizar_reinvestimento(indicadores.get('taxa_reinvestimento', 0.0))
        notas['autossuficiencia'] = self.normalizar_autossuficiencia(indicadores.get('autossuficiencia', 0.0))

        score = 0.0
        contributions = {}
        for key, peso in self.pesos.items():
            nota = notas.get(key, 0.0)
            contrib = nota * (peso / 100.0)
            contributions[key] = round(contrib, 2)
            score += contrib

        score = round(score, 1)

        return {
            "score": score,
            "notas": notas,
            "contribuicoes": contributions,
            "pesos": self.pesos
        }

# --- 3. FUNÇÃO PARA GERAR PROMPT COM PLANO DE CONTAS ---
def gerar_prompt_com_plano_contas() -> str:
    contas_str = "### PLANO DE CONTAS ###\n\n"
    
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        contas_str += f"{sintetico['codigo']} - {sintetico['nome']} (Tipo: {sintetico['tipo_fluxo']})\n"
        for conta in sintetico["contas"]:
            contas_str += f"  - {conta['codigo']}: {conta['nome']}\n"
        contas_str += "\n"
    
    prompt = f"""Você é um especialista em extração e classificação de dados financeiros.

{contas_str}

Extraia todas as transações deste extrato bancário em PDF e classifique cada transação de acordo com o PLANO DE CONTAS acima.

INSTRUÇÕES CRÍTICAS:
1. Use EXATAMENTE os códigos de conta analítica listados acima (ex: OP-01, OP-05, INV-01, FIN-05, etc.)
2. Analise cuidadosamente cada transação para determinar a conta mais apropriada.
3. Retiradas de sócios e pró-labore devem ser classificadas como FIN-05.
4. Receitas operacionais: OP-01 (vendas), OP-02 (serviços), OP-03 (outras).
5. Despesas operacionais: OP-04 (CMV), OP-05 (administrativas), OP-06 (comerciais), OP-08 (impostos), OP-09 (tarifas).
6. Investimentos: INV-01 (compra de ativos), INV-02 (aplicações), INV-03 (venda de ativos).
7. Financiamentos: FIN-01 (empréstimos recebidos), FIN-02 (pagamento de empréstimos), FIN-03 (juros).
8. IMPORTANTE — Transferências NEUTRAS (NE-01 ou NE-02): Use APENAS quando detectar uma saída de uma conta corrente E uma entrada de MESMO VALOR em outra conta no MESMO DIA. Caso contrário, classifique normalmente nas outras categorias.

Retorne um objeto JSON com o formato do schema indicado, usando valor POSITIVO para 'valor' e classificando como 'DEBITO' ou 'CREDITO'.
"""
    return prompt

# --- 4. FUNÇÃO DE CHAMADA DA API PARA EXTRAÇÃO ---
@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None})
def analisar_extrato(pdf_bytes: bytes, filename: str, client: genai.Client) -> dict:
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

        if DEBUG:
            try:
                st.text("DEBUG: resposta bruta da API (prefix):")
                st.text(response.text[:2000])
            except Exception:
                pass

        response_json = json.loads(response.text)
        dados_pydantic = AnaliseCompleta(**response_json)
        return dados_pydantic.model_dump()
    except Exception as e:
        error_message = str(e)
        if "503 UNAVAILABLE" in error_message or "model is overloaded" in error_message:
            st.error(f"O modelo Gemini está temporariamente indisponível ao processar '{filename}'.")
            st.info("Isso pode ocorrer quando a demanda na API está alta. Tente novamente em alguns minutos.")
        elif "Invalid API key" in error_message or "401" in error_message or "permission" in error_message.lower():
            st.error("Problema de autenticação com a Gemini API. Verifique a sua chave (GEMINI_API_KEY).")
        else:
            if DEBUG:
                st.error(f"Erro ao chamar a Gemini API para '{filename}': {error_message}")
                st.code(traceback.format_exc())
            else:
                st.error(f"Ocorreu um erro ao processar '{filename}'. Verifique o arquivo e tente novamente.")
        return {
            'transacoes': [],
            'saldo_final': 0.0
        }

# --- 5. FUNÇÃO PARA ENRIQUECER DADOS COM PLANO DE CONTAS ---
def enriquecer_com_plano_contas(df: pd.DataFrame) -> pd.DataFrame:
    mapa_contas = {}
    for sintetico in PLANO_DE_CONTAS["sinteticos"]:
        for conta in sintetico["contas"]:
            mapa_contas[conta["codigo"]] = {
                "nome_conta": conta["nome"],
                "codigo_sintetico": sintetico["codigo"],
                "nome_sintetico": sintetico["nome"],
                "tipo_fluxo": sintetico["tipo_fluxo"]
            }
    
    df = df.copy()
    df['nome_conta'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('nome_conta', 'Não classificado'))
    df['codigo_sintetico'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('codigo_sintetico', 'NE'))
    df['nome_sintetico'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('nome_sintetico', 'Não classificado'))
    df['tipo_fluxo'] = df['conta_analitica'].map(lambda x: mapa_contas.get(x, {}).get('tipo_fluxo', 'NEUTRO'))
    
    def _label_from_code(code):
        try:
            if code is None or (isinstance(code, float) and pd.isna(code)):
                return ''
        except Exception:
            pass
        nome = mapa_contas.get(code, {}).get('nome_conta', '')
        if nome:
            return f"{code} - {nome}"
        return str(code)

    df['conta_display'] = df['conta_analitica'].map(lambda x: _label_from_code(x))

    return df

# --- 6. FUNÇÃO PARA CRIAR RELATÓRIO DE FLUXO DE CAIXA ---
def criar_relatorio_fluxo_caixa(df: pd.DataFrame):
    st.subheader("Relatório de Fluxo de Caixa")
    
    if df.empty:
        st.info("Nenhum dado disponível. Por favor, processe os extratos primeiro.")
        return
    
    df = df.copy()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df.dropna(subset=['data'], inplace=True)
    df['mes_ano'] = df['data'].dt.to_period('M')
    df['fluxo'] = df.apply(lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], axis=1)
    
    df_fluxo = df[df['tipo_fluxo'] != 'NEUTRO'].copy()
    meses = sorted(df_fluxo['mes_ano'].unique())
    meses_pt = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    
    colunas_meses = []
    for mes in meses:
        mes_nome = meses_pt[mes.month]
        ano = mes.year % 100
        colunas_meses.append(f"{mes_nome}/{ano:02d}")
    
    todas_contas = df_fluxo.groupby(['tipo_fluxo', 'conta_analitica', 'nome_conta']).size().reset_index()[['tipo_fluxo', 'conta_analitica', 'nome_conta']]
    relatorio_linhas = []
    
    relatorio_linhas.append({'Categoria': '**ATIVIDADES OPERACIONAIS**', 'tipo': 'header'})
    
    contas_op = todas_contas[todas_contas['tipo_fluxo'] == 'OPERACIONAL'].sort_values('conta_analitica')
    for _, conta in contas_op.iterrows():
        linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
        for mes in meses:
            df_mes_conta = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['conta_analitica'] == conta['conta_analitica'])]
            valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha[mes_col] = valor
        relatorio_linhas.append(linha)
    
    linha_total_op = {'Categoria': '**Total Caixa Operacional**', 'tipo': 'total'}
    for mes in meses:
        df_mes_op = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'OPERACIONAL')]
        valor = df_mes_op['fluxo'].sum() if not df_mes_op.empty else 0
        mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
        linha_total_op[mes_col] = valor
    relatorio_linhas.append(linha_total_op)
    relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
    contas_inv = todas_contas[todas_contas['tipo_fluxo'] == 'INVESTIMENTO'].sort_values('conta_analitica')
    if not contas_inv.empty:
        relatorio_linhas.append({'Categoria': '**ATIVIDADES DE INVESTIMENTO**', 'tipo': 'header'})
        for _, conta in contas_inv.iterrows():
            linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
            for mes in meses:
                df_mes_conta = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['conta_analitica'] == conta['conta_analitica'])]
                valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
                mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)
        linha_total_inv = {'Categoria': '**Total Caixa de Investimento**', 'tipo': 'total'}
        for mes in meses:
            df_mes_inv = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'INVESTIMENTO')]
            valor = df_mes_inv['fluxo'].sum() if not df_mes_inv.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha_total_inv[mes_col] = valor
        relatorio_linhas.append(linha_total_inv)
        relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
    contas_fin = todas_contas[todas_contas['tipo_fluxo'] == 'FINANCIAMENTO'].sort_values('conta_analitica')
    if not contas_fin.empty:
        relatorio_linhas.append({'Categoria': '**ATIVIDADES DE FINANCIAMENTO**', 'tipo': 'header'})
        for _, conta in contas_fin.iterrows():
            linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
            for mes in meses:
                df_mes_conta = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['conta_analitica'] == conta['conta_analitica'])]
                valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
                mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)
        linha_total_fin = {'Categoria': '**Total Caixa de Financiamento**', 'tipo': 'total'}
        for mes in meses:
            df_mes_fin = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'FINANCIAMENTO')]
            valor = df_mes_fin['fluxo'].sum() if not df_mes_fin.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha_total_fin[mes_col] = valor
        relatorio_linhas.append(linha_total_fin)
        relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
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
    
    df_relatorio = pd.DataFrame(relatorio_linhas)
    df_relatorio = df_relatorio.fillna('')
    for col in colunas_meses:
        if col in df_relatorio.columns:
            df_relatorio[col] = df_relatorio[col].apply(lambda x: formatar_brl(x) if isinstance(x, (int, float)) and x != 0 else '')
    df_display = df_relatorio.drop(columns=['tipo'])
    st.markdown('<div class="fluxo-table">', unsafe_allow_html=True)
    st.dataframe(df_display, use_container_width=True, hide_index=True, height=800, column_config={"Categoria": st.column_config.TextColumn("Categoria", width="large"), **{col: st.column_config.TextColumn(col, width="medium") for col in colunas_meses}})
    st.markdown('</div>', unsafe_allow_html=True)
    return None

# --- 7. FUNÇÃO PARA CRIAR GRÁFICO DE INDICADORES ---
def criar_grafico_indicadores(df: pd.DataFrame):
    st.subheader("Evolução dos Indicadores Financeiros")
    
    if df.empty:
        st.info("Nenhum dado disponível para indicadores.")
        return
    
    df2 = df.copy()
    df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
    df2.dropna(subset=['data'], inplace=True)
    df2['mes_ano'] = df2['data'].dt.to_period('M')
    df2['fluxo'] = df2.apply(lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], axis=1)
    df_fluxo = df2[df2['tipo_fluxo'] != 'NEUTRO'].copy()
    
    meses = sorted(df_fluxo['mes_ano'].unique())
    indicadores_data = []
    for mes in meses:
        df_mes = df_fluxo[df_fluxo['mes_ano'] == mes]
        mes_str = mes.strftime('%m/%Y')
        caixa_op = df_mes[df_mes['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()
        caixa_inv = df_mes[df_mes['tipo_fluxo'] == 'INVESTIMENTO']['fluxo'].sum()
        caixa_fin = df_mes[df_mes['tipo_fluxo'] == 'FINANCIAMENTO']['fluxo'].sum()
        entradas_op = df_mes[(df_mes['tipo_fluxo'] == 'OPERACIONAL') & (df_mes['tipo_movimentacao'] == 'CREDITO')]['valor'].sum()
        margem_caixa_op = (caixa_op / entradas_op * 100) if entradas_op > 0 else 0.0
        intensidade_inv = (abs(caixa_inv) / caixa_op * 100) if caixa_op != 0 else 0.0
        intensidade_fin = (caixa_fin / caixa_op * 100) if caixa_op != 0 else 0.0
        retiradas = abs(df_mes[(df_mes['conta_analitica']=='FIN-05') & (df_mes['tipo_movimentacao']=='DEBITO')]['valor'].sum())
        peso_retiradas = (retiradas / df_mes[df_mes['tipo_movimentacao']=='DEBITO']['valor'].sum() * 100) if df_mes[df_mes['tipo_movimentacao']=='DEBITO']['valor'].sum() != 0 else 0.0
        indicadores_data.append({
            'Mês': mes_str,
            'Margem de Caixa Operacional (%)': margem_caixa_op,
            'Intensidade de Investimento (%)': intensidade_inv,
            'Intensidade de Financiamento (%)': intensidade_fin,
            'Peso de Retiradas (%)': peso_retiradas
        })
    
    df_indicadores = pd.DataFrame(indicadores_data)
    fig = go.Figure()
    if not df_indicadores.empty:
        fig.add_trace(go.Scatter(x=df_indicadores['Mês'], y=df_indicadores['Margem de Caixa Operacional (%)'], mode='lines+markers', name='Margem de Caixa Operacional (%)', line=dict(color=ACCENT_COLOR, width=3)))
        fig.add_trace(go.Scatter(x=df_indicadores['Mês'], y=df_indicadores['Intensidade de Investimento (%)'], mode='lines+markers', name='Intensidade de Investimento (%)', line=dict(color=INVESTMENT_COLOR, width=3)))
        fig.add_trace(go.Scatter(x=df_indicadores['Mês'], y=df_indicadores['Intensidade de Financiamento (%)'], mode='lines+markers', name='Intensidade de Financiamento (%)', line=dict(color=FINANCING_COLOR, width=3)))
        fig.add_trace(go.Scatter(x=df_indicadores['Mês'], y=df_indicadores['Peso de Retiradas (%)'], mode='lines+markers', name='Peso de Retiradas (%)', line=dict(color=NEGATIVE_COLOR, width=3, dash='dash')))
    fig.update_layout(title='Indicadores Financeiros (%) ao longo do tempo', xaxis_title='Mês', yaxis_title='Percentual (%)', height=420, plot_bgcolor='white', font=dict(family="Roboto"), hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Entenda os indicadores"):
        st.markdown("""
        **Margem de Caixa Operacional**: percentual do caixa operacional em relação às entradas operacionais.
        Indica a eficiência operacional na geração de caixa.
        
        **Intensidade de Investimento**: percentual do caixa de investimento em relação ao caixa operacional.
        Indica quanto da geração operacional está sendo investido (pode reduzir caixa no curto prazo, mas fortalecer no longo prazo).
        
        **Intensidade de Financiamento**: percentual do caixa de financiamento em relação ao caixa operacional.
        Indica a dependência de fontes externas de capital (empréstimos, aportes).
        
        **Peso de Retiradas**: percentual das retiradas pessoais sobre o total de saídas.
        Indica o impacto das retiradas dos sócios no fluxo do negócio.
        """)
    st.markdown("---")

# --- 8. FUNÇÃO: CÁLCULO DO SCORE FINANCEIRO ---
def calcular_score_fluxo(df: pd.DataFrame):
    try:
        indicadores_calc = IndicadoresFluxo(df)
        indicadores = indicadores_calc.resumo_indicadores()
        score_calc = ScoreCalculator()
        resultado = score_calc.calcular_score(indicadores)
        resultado_full = {
            'score_final': resultado['score'],
            'notas': resultado['notas'],
            'contribuicoes': resultado['contribuicoes'],
            'pesos': resultado['pesos'],
            'valores': indicadores,
            'componentes': {
                'caixa_operacional': indicadores.get('gco', 0.0),
                'entradas_operacionais': indicadores.get('entradas_operacionais', 0.0),
                'caixa_investimento': indicadores.get('intensidade_inv', 0.0),
                'caixa_financiamento': indicadores.get('intensidade_fin', 0.0)
            }
        }
        return resultado_full
    except Exception as e:
        if DEBUG:
            st.error(f"Erro no cálculo dos indicadores/score: {e}")
            st.code(traceback.format_exc())
        return {
            'score_final': 0.0,
            'notas': {},
            'contribuicoes': {},
            'pesos': {},
            'valores': {},
            'componentes': {}
        }

# --- 9. FUNÇÃO PARA CRIAR DASHBOARD ---
def criar_dashboard(df: pd.DataFrame):
    st.subheader("Dashboard: Análise de Fluxo de Caixa")
    
    if df.empty:
        st.info("Nenhum dado disponível para o dashboard.")
        return

    try:
        df2 = df.copy()
        df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
        df2.dropna(subset=['data'], inplace=True)
        df2['fluxo'] = df2.apply(lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], axis=1)
        df2['mes_ano_str'] = df2['data'].dt.strftime('%Y-%m')
        df_fluxo = df2[df2['tipo_fluxo'] != 'NEUTRO'].copy()
        
        st.markdown("Fluxo de Caixa Mensal por Categoria")
        df_fluxo_agrupado = df_fluxo.groupby(['mes_ano_str', 'tipo_fluxo'])['fluxo'].sum().reset_index()
        fig_dcf = px.bar(df_fluxo_agrupado, x='mes_ano_str', y='fluxo', color='tipo_fluxo', barmode='group', title='Evolução do Fluxo de Caixa por Tipo', labels={'fluxo': 'Fluxo (R$)', 'mes_ano_str': 'Mês/Ano', 'tipo_fluxo': 'Tipo de Fluxo'}, color_discrete_map={'OPERACIONAL': ACCENT_COLOR, 'INVESTIMENTO': INVESTMENT_COLOR, 'FINANCIAMENTO': FINANCING_COLOR})
        fig_dcf.update_layout(height=400, plot_bgcolor='white', font=dict(family="Roboto"))
        st.plotly_chart(fig_dcf, use_container_width=True)
        st.markdown("---")

        st.markdown("Comparativo: Caixa Operacional vs Retiradas Pessoais")
        caixa_operacional = df_fluxo[df_fluxo['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()
        retiradas_pessoais = abs(df2[(df2['conta_analitica'] == 'FIN-05') & (df2['tipo_movimentacao'] == 'DEBITO')]['valor'].sum())
        
        if caixa_operacional > 0 or retiradas_pessoais > 0:
            dados_comparativo = pd.DataFrame({'Categoria': ['Caixa Operacional Gerado', 'Retiradas Pessoais (Sócios/Pró-labore)'], 'Valor': [caixa_operacional, retiradas_pessoais]})
            fig_comparativo = px.pie(dados_comparativo, values='Valor', names='Categoria', title='Distribuição: Geração Operacional vs Retiradas', hole=0.3)
            fig_comparativo.update_traces(textposition='inside', textinfo='percent+label', hovertemplate='<b>%{label}</b><br>Valor: %{value:.2f}<extra></extra>')
            fig_comparativo.update_layout(height=400, font=dict(family="Roboto"), showlegend=True)
            st.plotly_chart(fig_comparativo, use_container_width=True)
            if caixa_operacional <= 0:
                st.error("O caixa operacional está negativo — não há sustentabilidade para retiradas pessoais neste período.")
            else:
                percentual_retiradas = (retiradas_pessoais / caixa_operacional * 100) if caixa_operacional != 0 else 0
                if percentual_retiradas > 80:
                    st.warning("As retiradas pessoais representam mais de 80% do caixa operacional. Avalie a sustentabilidade do negócio.")
                elif percentual_retiradas > 50:
                    st.info("As retiradas pessoais consomem mais de 50% do caixa operacional. Monitore a evolução deste indicador.")
                else:
                    st.success("As retiradas pessoais estão em nível saudável em relação ao caixa operacional.")
        else:
            st.info("Não há dados suficientes para comparação entre caixa operacional e retiradas pessoais.")
        st.markdown("---")
        
        st.markdown("Distribuição de Despesas por Conta")
        df_despesas = df_fluxo[df_fluxo['tipo_movimentacao'] == 'DEBITO'].groupby('nome_conta')['valor'].sum().reset_index()
        df_despesas = df_despesas.sort_values('valor', ascending=False).head(10)
        if not df_despesas.empty:
            fig_pie = px.pie(df_despesas, values='valor', names='nome_conta', title='Top 10 Categorias de Despesa', color_discrete_sequence=px.colors.qualitative.Set3)
            fig_pie.update_layout(height=400, font=dict(family="Roboto"))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Nenhuma despesa encontrada para distribuição.")
    except Exception as e:
        st.error(f"Erro ao gerar o dashboard: {e}")
        if DEBUG:
            st.code(traceback.format_exc())

# --- 10. FUNÇÃO DE CABEÇALHO ---
def load_header():
    try:
        logo = Image.open(LOGO1_FILENAME)
        col1, col2 = st.columns([2,5])
        with col1:
            st.image(logo, width=600)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("Traduzindo números em histórias que façam sentido...")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")

# --------------------------
# INTEGRAÇÃO DE AUTENTICAÇÃO
# --------------------------
# Impede acesso à app sem autenticação
if "user" not in st.session_state:
    login_page()
    st.stop()
else:
    user = st.session_state["user"]
    st.sidebar.write(f"Olá, {user.email}")
    if st.sidebar.button("Sair"):
        logout()

# Carrega cabeçalho (mantendo sua estrutura)
load_header()

st.sidebar.title("Navegação")
page = st.sidebar.radio("Seções:", ["Upload e Extração", "Revisão de Dados", "Dashboard & Relatórios"])

# ============================================
# Upload e Extração (com integração Supabase)
# ============================================
if page == "Upload e Extração":
    st.markdown("### 1. Upload e Extração de Dados")
    st.markdown("Faça o upload dos extratos em PDF. O sistema irá extrair as transações e classificá-las conforme o plano de contas.")

    with st.expander("Plano de Contas Utilizado", expanded=False):
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            st.markdown(f"**{sintetico['codigo']} - {sintetico['nome']}** ({sintetico['tipo_fluxo']})")
            for conta in sintetico["contas"]:
                st.markdown(f"  - `{conta['codigo']}`: {conta['nome']}")

    # BLOCO DE UPLOAD INTEGRADO
    with st.expander("Upload de Arquivos", expanded=True):
        uploaded_files = st.file_uploader(
            "Selecione os arquivos PDF dos seus extratos bancários",
            type="pdf",
            accept_multiple_files=True,
            key="pdf_uploader",
            help="Os PDFs devem ter texto selecionável (não apenas imagem)."
        )

    if uploaded_files:
        if st.button(f"Executar Extração e Classificação ({len(uploaded_files)} arquivos)", key="analyze_btn"):
            todas_transacoes = []
            extraction_status = st.empty()
            extraction_status.info("Iniciando extração e classificação...")
            
            user_id = user.id
            for i, uploaded_file in enumerate(uploaded_files):
                extraction_status.info(f"Processando arquivo {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
                pdf_bytes = uploaded_file.getvalue()

                # calcula hash e verifica duplicidade
                file_hash = hashlib.sha256(pdf_bytes).hexdigest()
                existente = supabase.table("extratos").select("*").eq("hash_arquivo", file_hash).execute()
                if existente.data:
                    extraction_status.warning(f"O arquivo {uploaded_file.name} já foi enviado anteriormente. Pulando.")
                    continue

                # opcional: salva o PDF no Storage (pasta por usuário)
             
                    pass

                # registra metadados do extrato
                #resultado = # [REMOVIDO] inserção imediata suprimida (Upload ajustado)
                extrato_id = resultado.data[0]["id"] if resultado.data else None

                # chama a função que usa Gemini / extração
                dados_dict = analisar_extrato(pdf_bytes, uploaded_file.name, client)
                transacoes = dados_dict.get('transacoes', [])
                todas_transacoes.extend(transacoes)

                # salva as transações na tabela 'transacoes' associadas ao extrato
                if transacoes and extrato_id is not None:
                    df_temp = pd.DataFrame(transacoes)
                    registros = df_temp.to_dict(orient='records')
                    for r in registros:
                        r['user_id'] = user_id
                        r['extrato_id'] = extrato_id
                    try:
                        supabase.table('transacoes').insert(registros).execute()
                    except Exception as e:
                        if DEBUG:
                            st.error(f"Erro ao salvar transações no Supabase: {e}")

            df_transacoes = pd.DataFrame(todas_transacoes)

            if df_transacoes.empty:
                extraction_status.error("Nenhuma transação válida foi extraída. Verifique se o PDF contém texto legível e se o arquivo não está corrompido.")
                st.session_state['df_transacoes_editado'] = pd.DataFrame()
            else:
                extraction_status.success(f"Extração de {len(todas_transacoes)} transações concluída!")

                df_transacoes['valor'] = pd.to_numeric(df_transacoes['valor'], errors='coerce').fillna(0)
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'], errors='coerce', dayfirst=True)
                df_transacoes['tipo_movimentacao'] = df_transacoes['tipo_movimentacao'].fillna('DEBITO')
                df_transacoes['conta_analitica'] = df_transacoes['conta_analitica'].fillna('NE-02')

                df_transacoes = enriquecer_com_plano_contas(df_transacoes)

                st.session_state['df_transacoes_editado'] = df_transacoes
                st.success("Dados carregados e classificados. Você pode revisar as entradas na seção 'Revisão de Dados'.")

    # Listagem de extratos já carregados
    st.subheader("Extratos já carregados")
    try:
        extratos_existentes = supabase.table("extratos").select("id, nome_arquivo, criado_em").eq("user_id", user.id).order("criado_em", desc=True).execute()
        if not extratos_existentes.data:
            st.info("Nenhum extrato carregado ainda.")
        else:
            df_extratos = pd.DataFrame(extratos_existentes.data)
            df_extratos["criado_em"] = pd.to_datetime(df_extratos["criado_em"]).dt.strftime("%d/%m/%Y %H:%M")
            st.dataframe(df_extratos, use_container_width=True)
    except Exception as e:
        if DEBUG:
            st.error(f"Erro ao buscar extratos: {e}")

# =========================
# Revisão de Dados
# =========================
elif page == "Revisão de Dados":
    st.markdown("### 2. Revisão e Correção Manual dos Dados")
    
    if not st.session_state['df_transacoes_editado'].empty:
        st.info("Revise as classificações e corrija manualmente qualquer erro.")
        
        opcoes_contas = []
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            for conta in sintetico["contas"]:
                opcoes_contas.append(f"{conta['codigo']} - {conta['nome']}")
        
        with st.expander("Editar Transações", expanded=True):
            edited_df = st.data_editor(
                st.session_state['df_transacoes_editado'][['data', 'descricao', 'valor', 'tipo_movimentacao', 'conta_display', 'nome_conta', 'tipo_fluxo']],
                width='stretch',
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                    "descricao": st.column_config.TextColumn("Descrição", width="large"),
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                    "tipo_movimentacao": st.column_config.SelectboxColumn("Tipo", options=["CREDITO", "DEBITO"], required=True),
                    "conta_display": st.column_config.SelectboxColumn("Conta (código - nome)", options=opcoes_contas, required=True, help="Selecione a conta no formato código - nome"),
                    "nome_conta": st.column_config.TextColumn("Nome da Conta", disabled=True),
                    "tipo_fluxo": st.column_config.TextColumn("Tipo de Fluxo", disabled=True),
                },
                num_rows="dynamic",
                key="data_editor_transacoes"
            )
        
        if st.button("Confirmar Dados e Gerar Relatórios", key="generate_report_btn"):
            try:
                if 'conta_display' in edited_df.columns:
                    edited_df['conta_analitica'] = edited_df['conta_display'].apply(lambda x: x.split(' - ')[0].strip() if isinstance(x, str) and ' - ' in x else x)
            except Exception:
                pass
            edited_df = enriquecer_com_plano_contas(edited_df)
            st.session_state['df_transacoes_editado'] = edited_df
            st.success("Dados confirmados! Acesse a seção 'Dashboard & Relatórios' para ver as análises.")
    else:
        st.warning("Nenhum dado processado encontrado. Volte para a seção 'Upload e Extração'.")

# =========================
# Dashboard & Relatórios
# =========================
elif page == "Dashboard & Relatórios":
    st.markdown("### 3. Relatórios Gerenciais e Dashboard")
    
    # Filtros de período que alimentam toda a Parte 3
    st.markdown("Selecione o período para gerar os relatórios e dashboards:")
    col1, col2 = st.columns(2)
    data_inicial = col1.date_input("De", value=pd.to_datetime("2024-01-01"))
    data_final = col2.date_input("Até", value=pd.to_datetime("today"))
    
    if st.button("Gerar Relatórios e Dashboard"):
        try:
            resultado = supabase.table("transacoes").select("*").eq("user_id", user.id).gte("data", data_inicial.isoformat()).lte("data", data_final.isoformat()).execute()
            if not resultado.data:
                st.warning("Nenhuma transação encontrada no período selecionado.")
            else:
                df_relatorio = pd.DataFrame(resultado.data)
                df_relatorio["data"] = pd.to_datetime(df_relatorio["data"], errors="coerce")
                df_relatorio["valor"] = pd.to_numeric(df_relatorio["valor"], errors="coerce").fillna(0)
                # Enriquecer com plano de contas caso necessário
                df_relatorio = enriquecer_com_plano_contas(df_relatorio)
                
                # Atualiza o estado para que o restante do pipeline use este DataFrame
                st.session_state['df_transacoes_editado'] = df_relatorio.copy()
                st.success(f"{len(df_relatorio)} transações carregadas para o período selecionado.")
        except Exception as e:
            st.error(f"Erro ao gerar relatórios: {e}")
            if DEBUG:
                st.code(traceback.format_exc())
    
    # Se há dados no estado (carregados por upload ou por consulta), use-os
    if not st.session_state['df_transacoes_editado'].empty:
        df_final = st.session_state['df_transacoes_editado'].copy()
        try:
            resultado_score = calcular_score_fluxo(df_final)
            score = resultado_score['score_final']
            valores = resultado_score.get('valores', {})
            notas = resultado_score.get('notas', {})
            contribs = resultado_score.get('contribuicoes', {})
            pesos = resultado_score.get('pesos', {})

            st.markdown("Indicadores e Score")
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)

            with col_s1:
                st.metric("Score Financeiro (0–100)", f"{score:.1f}")
            with col_s2:
                margem_op = valores.get('margem_op', 0.0)
                st.metric("Margem de Caixa Operacional", f"{margem_op:.2f}")
            with col_s3:
                retiradas = valores.get('peso_retiradas', 0.0)
                st.metric("Peso de Retiradas", f"{retiradas:.2f}")
            with col_s4:
                autossuf = valores.get('autossuficiencia', 0.0)
                aut_text = "∞" if autossuf == float('inf') else f"{autossuf:.2f}"
                st.metric("Autossuficiência Operacional", aut_text)

            st.markdown("---")
            criar_dashboard(df_final)
            criar_grafico_indicadores(df_final)
            criar_relatorio_fluxo_caixa(df_final)

            # Exibir detalhes do score e contribuições
            with st.expander("Detalhes do Score"):
                st.write("Notas normalizadas por componente:")
                st.dataframe(pd.DataFrame(resultado_score.get('notas', {}), index=[0]).T.rename(columns={0: "Nota"}))
                st.write("Contribuições para o score:")
                st.dataframe(pd.DataFrame(resultado_score.get('contribuicoes', {}), index=[0]).T.rename(columns={0: "Contribuição"}))
        except Exception as e:
            st.error(f"Erro ao processar dashboard: {e}")
            if DEBUG:
                st.code(traceback.format_exc())
    else:
        st.info("Nenhum dado disponível. Faça upload de extratos na seção 'Upload e Extração' ou use o filtro para carregar transações previamente enviadas.")

# --- Revisão: gravação no Supabase ajustada ---
# (Fluxo: atualiza se hash igual, substitui transações antigas e grava revisadas)

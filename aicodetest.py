# app_hedgewise_final.py
# Versão final solicitada por você (datas combinadas na sidebar, dashboard igual aicode_semBD, resumo de extratos)
# Salve como .py ou .txt e faça deploy no Streamlit Cloud.
# Requisitos: streamlit, pandas, pydantic, pillow, plotly, google-genai (opcional), supabase-py (assumido em auth.py)
# Mantive integração com auth.py (login_page, logout, supabase) conforme seu projeto.

import re
import streamlit as st
import pandas as pd
import numpy as np
import json
import io
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import math
import traceback
import hashlib
import plotly.graph_objects as go
import plotly.express as px

# --- Dependências opcionais com Gemini (mantive compatibilidade) ---
try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

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

# ----------------------
# Tema e CSS
# ----------------------
PRIMARY_COLOR = "#0A2342"
BACKGROUND_COLOR = "#F0F2F6"
ACCENT_COLOR = "#007BFF"
NEGATIVE_COLOR = "#DC3545"
INVESTMENT_COLOR = "#28A745"
FINANCING_COLOR = "#FFC107"

st.set_page_config(page_title="Hedgewise | Análise Financeira Inteligente", layout="wide", initial_sidebar_state="expanded")

st.markdown(f"""
    <style>
        html, body, [data-testid="stAppViewContainer"] {{ background-color: {BACKGROUND_COLOR} !important; color: #000 !important; }}
        [data-testid="stSidebar"] {{ background-color: white !important; }}
        .main-header {{ color: {PRIMARY_COLOR}; font-size:1.7em; font-weight:800; }}
        .kpi-container {{ background-color: white; padding: 16px; border-radius: 12px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); margin-bottom: 18px; }}
        .stButton>button {{ background-color: {PRIMARY_COLOR}; color: white; border-radius: 8px; padding: 8px 18px; font-weight:700; }}
        .small-muted {{ font-size:13px;color:#5b5b5b; }}
        .date-box-sidebar {{ background-color: #ffffff; padding: 10px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.04); }}
    </style>
""", unsafe_allow_html=True)

# ----------------------
# Utilities
# ----------------------
def formatar_brl(valor: float) -> str:
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return "R$ " + valor_brl
    except Exception:
        return f"R$ {valor:.2f}"

def parse_periodo_br(period_str: str):
    """
    Espera formato: DD/MM/AAAA - DD/MM/AAAA
    Retorna tuple(date_start: date, date_end: date) ou levanta ValueError.
    """
    if not isinstance(period_str, str):
        raise ValueError("Período inválido")
    parts = period_str.split("-")
    if len(parts) < 2:
        raise ValueError("Use o formato: DD/MM/AAAA - DD/MM/AAAA")
    left = parts[0].strip()
    right = "-".join(parts[1:]).strip()  # no caso de hífen dentro de texto (não esperado)
    fmt = "%d/%m/%Y"
    try:
        d1 = datetime.strptime(left, fmt).date()
        d2 = datetime.strptime(right, fmt).date()
    except Exception:
        raise ValueError("Datas inválidas. Use DD/MM/AAAA - DD/MM/AAAA")
    if d1 > d2:
        raise ValueError("Data inicial maior que a final")
    return d1, d2

# ----------------------
# Session state defaults
# ----------------------
if 'df_transacoes_editado' not in st.session_state:
    st.session_state['df_transacoes_editado'] = pd.DataFrame()
if 'contexto_adicional' not in st.session_state:
    st.session_state['contexto_adicional'] = ""

# ----------------------
# Auth / Supabase (assume auth.py exposes login_page, logout, supabase)
# ----------------------
try:
    from auth import login_page, logout, supabase
except Exception as e:
    st.error("Arquivo auth.py não encontrado ou não exporta login_page/logout/supabase. Verifique.")
    st.stop()

# Autenticação
if "user" not in st.session_state:
    login_page()
    st.stop()
else:
    user = st.session_state["user"]
    st.sidebar.write(f"Olá, {user.email}")
    if st.sidebar.button("Sair"):
        logout()

# --- Cabeçalho ---
def load_header():
    try:
        logo = Image.open("FinanceAI_1.png")
        col1, col2 = st.columns([2,5])
        with col1:
            st.image(logo, width=560)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("Traduzindo números em histórias que façam sentido.")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")

load_header()

# ----------------------
# Sidebar: Período combinado (Opção B — escolhido)
# ----------------------
st.sidebar.title("Filtros (Dashboard)")
with st.sidebar.container():
    st.markdown('<div class="date-box-sidebar">', unsafe_allow_html=True)
    periodo_placeholder = "DD/MM/AAAA - DD/MM/AAAA"
    periodo_input = st.text_input("Período (DD/MM/AAAA - DD/MM/AAAA)", value=f"01/01/2024 - {date.today().strftime('%d/%m/%Y')}", placeholder=periodo_placeholder, key="periodo_combined")
    st.markdown('<div class="small-muted">Digite o período no formato: <b>DD/MM/AAAA - DD/MM/AAAA</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Botão na sidebar para gerar / carregar transações do período
if st.sidebar.button("Gerar Relatórios e Dashboard", key="btn_generate_sidebar"):
    try:
        start_date, end_date = parse_periodo_br(periodo_input)
        # Converter para ISO para consultar Supabase
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()
        # Buscar transações do usuário no período
        resultado = supabase.table("transacoes").select("*").eq("user_id", user.id).gte("data", start_iso).lte("data", end_iso).execute()
        if not resultado.data:
            st.sidebar.warning("Nenhuma transação encontrada no período selecionado.")
            st.session_state['df_transacoes_editado'] = pd.DataFrame()
        else:
            df_rel = pd.DataFrame(resultado.data)
            # Ajustes de tipos
            if 'data' in df_rel.columns:
                df_rel['data'] = pd.to_datetime(df_rel['data'], errors='coerce')
            df_rel['valor'] = pd.to_numeric(df_rel.get('valor', 0), errors='coerce').fillna(0)
            df_rel = enriquecer_com_plano_contas(df_rel) if 'conta_analitica' in df_rel.columns else df_rel
            st.session_state['df_transacoes_editado'] = df_rel.copy()
            st.sidebar.success(f"{len(df_rel)} transações carregadas para o período selecionado.")
    except Exception as e:
        st.sidebar.error(f"Erro ao processar período: {e}")
        if st.secrets.get("DEBUG", False):
            st.sidebar.code(traceback.format_exc())

# ----------------------
# Navegação principal
# ----------------------
st.sidebar.title("Navegação")
page = st.sidebar.radio("Seções:", ["Upload e Extração", "Revisão de Dados", "Dashboard & Relatórios"])

# ----------------------
# Funções auxiliares: analisar_extrato, enriquecer_com_plano_contas, indicadores e score
# (Mantive implementações compatíveis com aicode_semBD)
# ----------------------
class TransacaoModel(BaseModel):
    data: str
    descricao: str
    valor: float
    tipo_movimentacao: str
    conta_analitica: str

class AnaliseCompleta(BaseModel):
    transacoes: List[TransacaoModel]
    saldo_final: float

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
2. Retorne um objeto JSON com o formato do schema indicado, usando valor POSITIVO para 'valor' e classificando como 'DEBITO' ou 'CREDITO'.
"""
    return prompt

@st.cache_data(show_spinner=False, hash_funcs={genai.Client: lambda _: None} if genai else None)
def analisar_extrato(pdf_bytes: bytes, filename: str, client=None) -> dict:
    # utiliza Gemini se disponível; em falta, retorna vazio
    if client is None or genai is None or types is None:
        return {'transacoes': [], 'saldo_final': 0.0}
    try:
        pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')
        prompt_analise = gerar_prompt_com_plano_contas()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AnaliseCompleta,
            temperature=0.2
        )
        response = client.models.generate_content(model='gemini-2.5-flash-lite', contents=[pdf_part, prompt_analise], config=config)
        response_json = json.loads(response.text)
        dados = AnaliseCompleta(**response_json)
        return dados.model_dump()
    except Exception as e:
        if st.secrets.get("DEBUG", False):
            st.error(f"Erro analisar_extrato: {e}")
            st.code(traceback.format_exc())
        return {'transacoes': [], 'saldo_final': 0.0}

def enriquecer_com_plano_contas(df: pd.DataFrame) -> pd.DataFrame:
    mapa = {}
    for s in PLANO_DE_CONTAS['sinteticos']:
        for c in s['contas']:
            mapa[c['codigo']] = {
                'nome_conta': c['nome'],
                'codigo_sintetico': s['codigo'],
                'nome_sintetico': s['nome'],
                'tipo_fluxo': s['tipo_fluxo']
            }
    df = df.copy()
    df['conta_analitica'] = df.get('conta_analitica', df.get('conta_display', 'NE-02')).fillna('NE-02')
    df['nome_conta'] = df['conta_analitica'].map(lambda x: mapa.get(x, {}).get('nome_conta', 'Não classificado'))
    df['codigo_sintetico'] = df['conta_analitica'].map(lambda x: mapa.get(x, {}).get('codigo_sintetico', 'NE'))
    df['nome_sintetico'] = df['conta_analitica'].map(lambda x: mapa.get(x, {}).get('nome_sintetico', 'Não classificado'))
    df['tipo_fluxo'] = df['conta_analitica'].map(lambda x: mapa.get(x, {}).get('tipo_fluxo', 'NEUTRO'))
    def fmt(code):
        try:
            if pd.isna(code) or code == '':
                return ''
        except Exception:
            pass
        nome = mapa.get(code, {}).get('nome_conta', '')
        return f"{code} - {nome}" if nome else str(code)
    df['conta_display'] = df['conta_analitica'].map(fmt)
    return df

# Indicadores & Score (conforme aicode_semBD)
class IndicadoresFluxo:
    def __init__(self, df: pd.DataFrame):
        self.df_raw = df.copy()
        self.df = self._prepare(df.copy())
        self.meses = self._obter_meses()
    def _prepare(self, df):
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
        else:
            df['data'] = pd.to_datetime(df.get('data', pd.NaT), errors='coerce', dayfirst=True)
        df = df.dropna(subset=['data']).copy()
        df['fluxo'] = df.apply(lambda r: r['valor'] if r['tipo_movimentacao'] == 'CREDITO' else -r['valor'], axis=1)
        df['mes_ano'] = df['data'].dt.to_period('M')
        return df
    def _obter_meses(self):
        df_fluxo = self.df[self.df['tipo_fluxo'] != 'NEUTRO'] if 'tipo_fluxo' in self.df.columns else self.df
        meses = sorted(df_fluxo['mes_ano'].unique())
        return meses
    def total_entradas_operacionais(self):
        return self.df[(self.df['tipo_fluxo']=='OPERACIONAL') & (self.df['tipo_movimentacao']=='CREDITO')]['valor'].sum()
    def caixa_operacional_total(self):
        return self.df[self.df['tipo_fluxo']=='OPERACIONAL']['fluxo'].sum()
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
    def resumo_indicadores(self):
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
        return {"score": score, "notas": notas, "contribuicoes": contributions, "pesos": self.pesos}

def calcular_score_fluxo(df: pd.DataFrame) -> Dict[str, Any]:
    try:
        ind = IndicadoresFluxo(df)
        vals = ind.resumo_indicadores()
        calc = ScoreCalculator()
        res = calc.calcular_score({
            'gco': vals.get('gco', 0.0),
            'entradas_operacionais': vals.get('entradas_operacionais', 0.0),
            'margem_op': vals.get('margem_op', 0.0),
            'intensidade_fin': vals.get('intensidade_fin', 0.0),
            'crescimento_entradas': vals.get('crescimento_entradas', 0.0),
            'taxa_reinvestimento': vals.get('taxa_reinvestimento', 0.0),
            'autossuficiencia': vals.get('autossuficiencia', 0.0),
            'peso_retiradas': vals.get('peso_retiradas', 0.0)
        })
        return {"score_final": res['score'], "valores": vals, "notas": res['notas'], "contribuicoes": res['contribuicoes'], "pesos": res['pesos']}
    except Exception:
        return {"score_final": 0.0, "valores": {}, "notas": {}, "contribuicoes": {}, "pesos": {}}

# ----------------------
# Funções de relatório e gráficos (Plotly)
# ----------------------
def criar_relatorio_fluxo_caixa_sem_tipo(df: pd.DataFrame):
    """
    Cria relatório de fluxo de caixa consolidado por conta e mês.
    Implementado para ficar igual ao aicode_semBD.txt — sem coluna 'tipo'.
    """
    st.subheader("Relatório de Fluxo de Caixa")
    if df.empty:
        st.info("Nenhum dado disponível para gerar o relatório de fluxo de caixa.")
        return
    df2 = df.copy()
    df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
    df2.dropna(subset=['data'], inplace=True)
    df2['mes_ano'] = df2['data'].dt.to_period('M')
    df2['fluxo'] = df2.apply(lambda r: r['valor'] if r['tipo_movimentacao'] == 'CREDITO' else -r['valor'], axis=1)
    df_fluxo = df2[df2['tipo_fluxo'] != 'NEUTRO'].copy()
    meses = sorted(df_fluxo['mes_ano'].unique())
    if not meses:
        st.info("Sem movimento relevante para gerar relatório.")
        return
    meses_pt = {1:'Janeiro',2:'Fevereiro',3:'Março',4:'Abril',5:'Maio',6:'Junho',7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
    colunas = []
    for mes in meses:
        col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
        colunas.append(col)
    rows = []
    # Atividades operacionais
    st.write("**ATIVIDADES OPERACIONAIS**")
    contas_op = df_fluxo[df_fluxo['tipo_fluxo']=='OPERACIONAL'].groupby(['conta_analitica','nome_conta']).size().reset_index()[['conta_analitica','nome_conta']]
    for _, r in contas_op.iterrows():
        linha = {'Categoria': f"{r['conta_analitica']} - {r['nome_conta']}"}
        for mes in meses:
            val = df_fluxo[(df_fluxo['mes_ano']==mes) & (df_fluxo['conta_analitica']==r['conta_analitica'])]['fluxo'].sum()
            linha[f"{meses_pt[mes.month]}/{mes.year % 100:02d}"] = val
        rows.append(linha)
    df_rel = pd.DataFrame(rows)
    # Totais operacionais
    total_op = {'Categoria': '**Total Caixa Operacional**'}
    for mes in meses:
        total_op[f"{meses_pt[mes.month]}/{mes.year % 100:02d}"] = df_fluxo[(df_fluxo['mes_ano']==mes) & (df_fluxo['tipo_fluxo']=='OPERACIONAL')]['fluxo'].sum()
    df_rel = pd.concat([pd.DataFrame([{'Categoria':'**ATIVIDADES OPERACIONAIS**'}]), df_rel, pd.DataFrame([total_op])], ignore_index=True)
    st.dataframe(df_rel.fillna(0), use_container_width=True)

def grafico_fluxo_mensal_por_categoria(df: pd.DataFrame):
    st.subheader("Fluxo de Caixa Mensal por Categoria")
    if df.empty:
        st.info("Nenhum dado para gerar o gráfico.")
        return
    df2 = df.copy()
    df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
    df2.dropna(subset=['data'], inplace=True)
    df2['mes_ano'] = df2['data'].dt.to_period('M').dt.to_timestamp()
    df2['fluxo'] = df2.apply(lambda r: r['valor'] if r['tipo_movimentacao']=='CREDITO' else -r['valor'], axis=1)
    df_plot = df2[df2['tipo_fluxo']!='NEUTRO'].groupby(['mes_ano','nome_conta'])['fluxo'].sum().reset_index()
    if df_plot.empty:
        st.info("Dados insuficientes para o gráfico.")
        return
    fig = px.bar(df_plot, x='mes_ano', y='fluxo', color='nome_conta', labels={'mes_ano':'Mês','fluxo':'Fluxo (R$)','nome_conta':'Conta'}, title='Fluxo de Caixa Mensal por Categoria')
    fig.update_layout(barmode='relative', xaxis_tickformat='%b/%Y', height=480)
    st.plotly_chart(fig, use_container_width=True)

def grafico_comparativo_caixa_vs_retiradas(df: pd.DataFrame):
    st.subheader("Comparativo: Caixa Operacional vs Retiradas Pessoais")
    if df.empty:
        st.info("Nenhum dado para gerar o gráfico.")
        return
    df2 = df.copy()
    df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
    df2.dropna(subset=['data'], inplace=True)
    df2['mes_ano'] = df2['data'].dt.to_period('M')
    df2['fluxo'] = df2.apply(lambda r: r['valor'] if r['tipo_movimentacao']=='CREDITO' else -r['valor'], axis=1)
    meses = sorted(df2['mes_ano'].unique())
    dados = []
    for mes in meses:
        caixa_op = df2[(df2['mes_ano']==mes) & (df2['tipo_fluxo']=='OPERACIONAL')]['fluxo'].sum()
        retir = abs(df2[(df2['mes_ano']==mes) & (df2['conta_analitica']=='FIN-05') & (df2['tipo_movimentacao']=='DEBITO')]['valor'].sum())
        dados.append({'mes': mes.to_timestamp(), 'caixa_operacional': caixa_op, 'retiradas': retir})
    df_plot = pd.DataFrame(dados)
    if df_plot.empty:
        st.info("Dados insuficientes.")
        return
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_plot['mes'], y=df_plot['caixa_operacional'], name='Caixa Operacional'))
    fig.add_trace(go.Bar(x=df_plot['mes'], y=df_plot['retiradas'], name='Retiradas Pessoais'))
    fig.update_layout(barmode='group', xaxis_tickformat='%b/%Y', title='Comparativo: Caixa Operacional vs Retiradas Pessoais', height=420)
    st.plotly_chart(fig, use_container_width=True)

def grafico_distribuicao_despesas_por_conta(df: pd.DataFrame):
    st.subheader("Distribuição de Despesas por Conta")
    if df.empty:
        st.info("Nenhum dado para gerar o gráfico.")
        return
    df2 = df.copy()
    # considerar apenas debitos (saídas)
    df_debitos = df2[df2['tipo_movimentacao']=='DEBITO'].copy()
    if df_debitos.empty:
        st.info("Sem despesas registradas.")
        return
    df_sum = df_debitos.groupby('nome_conta')['valor'].sum().reset_index().sort_values('valor', ascending=False)
    fig = px.pie(df_sum, names='nome_conta', values='valor', title='Distribuição de Despesas por Conta', hole=0.3)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)

# ----------------------
# Upload e Extração
# ----------------------
if page == "Upload e Extração":
    st.markdown("### 1. Upload e Extração de Dados")
    st.markdown("Faça o upload dos seus arquivos PDF de extrato bancário. O sistema tentará extrair e classificar as transações automaticamente.")

    with st.expander("Plano de Contas Utilizado", expanded=False):
        for s in PLANO_DE_CONTAS['sinteticos']:
            st.markdown(f"**{s['codigo']} - {s['nome']}** ({s['tipo_fluxo']})")
            for c in s['contas']:
                st.markdown(f"  - `{c['codigo']}`: {c['nome']}")

    with st.expander("Upload de Arquivos", expanded=True):
        uploaded_files = st.file_uploader("Selecione arquivos PDF", type="pdf", accept_multiple_files=True, key="uploader_extratos")

    if uploaded_files:
        if st.button(f"Executar Extração e Classificação ({len(uploaded_files)} arquivos)", key="btn_extract"):
            status = st.empty()
            status.info("Iniciando extração...")
            todas = []
            for i, f in enumerate(uploaded_files):
                status.info(f"Processando {i+1}/{len(uploaded_files)}: {f.name}")
                pdf_bytes = f.getvalue()
                # verificar duplicidade por hash
                try:
                    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
                    existente = supabase.table("extratos").select("*").eq("hash_arquivo", file_hash).execute()
                    if existente.data:
                        status.warning(f"O arquivo {f.name} já foi enviado. Pulando.")
                        continue
                    supabase.storage.from_("extratos").upload(f"{user.id}/{f.name}", pdf_bytes)
                except Exception:
                    pass
                # chamar função de extração (Gemini) - se disponível
                dados = analisar_extrato(pdf_bytes, f.name, genai.Client(api_key=st.secrets["GEMINI_API_KEY"]) if genai and st.secrets.get("GEMINI_API_KEY") else None)
                trans = dados.get('transacoes', [])
                # adicionar extrato na tabela 'extratos'
                try:
                    ins = supabase.table("extratos").insert({
                        "user_id": user.id,
                        "nome_arquivo": f.name,
                        "hash_arquivo": file_hash
                    }).execute()
                    extrato_id = None
                    if ins.data and len(ins.data) > 0:
                        extrato_id = ins.data[0].get('id')
                except Exception:
                    extrato_id = None
                for t in trans:
                    t['extrato_id'] = extrato_id
                todas.extend(trans)
            if not todas:
                status.error("Nenhuma transação extraída.")
            else:
                df_t = pd.DataFrame(todas)
                df_t['valor'] = pd.to_numeric(df_t.get('valor', 0), errors='coerce').fillna(0)
                df_t['data'] = pd.to_datetime(df_t.get('data', None), errors='coerce', dayfirst=True)
                df_t['tipo_movimentacao'] = df_t.get('tipo_movimentacao', 'DEBITO')
                df_t['conta_analitica'] = df_t.get('conta_analitica', 'NE-02')
                df_t = enriquecer_com_plano_contas(df_t)
                # salvar transações na tabela 'transacoes' com user_id
                try:
                    records = df_t[['data','descricao','valor','tipo_movimentacao','conta_analitica','extrato_id']].to_dict(orient='records')
                    for r in records:
                        r['user_id'] = user.id
                        supabase.table("transacoes").insert(r).execute()
                    status.success(f"Extração completa: {len(records)} transações salvas.")
                except Exception as e:
                    status.error(f"Erro ao salvar transações extraídas: {e}")
                    if st.secrets.get("DEBUG", False):
                        st.code(traceback.format_exc())

    # Mostrar resumo dos extratos enviados (Solicitado: resumo, não tabela completa)
    st.markdown("#### Extratos enviados")
    try:
        extratos_result = supabase.table("extratos").select("id, nome_arquivo, criado_em").eq("user_id", user.id).order("criado_em", desc=True).execute()
        if extratos_result.data:
            extrs = pd.DataFrame(extratos_result.data)
            extrs['criado_em'] = pd.to_datetime(extrs['criado_em'], errors='coerce')
            resumo_rows = []
            for _, r in extrs.iterrows():
                # contar transações relacionadas a esse extrato
                try:
                    tran_res = supabase.table("transacoes").select("id").eq("user_id", user.id).eq("extrato_id", r['id']).execute()
                    count_trans = len(tran_res.data) if tran_res.data else 0
                except Exception:
                    count_trans = 0
                resumo_rows.append({
                    "nome_arquivo": r['nome_arquivo'],
                    "data_upload": r['criado_em'].strftime("%d/%m/%Y %H:%M") if not pd.isna(r['criado_em']) else "",
                    "n_transacoes": count_trans
                })
            df_resumo = pd.DataFrame(resumo_rows)
            st.table(df_resumo)
        else:
            st.info("Nenhum arquivo de extrato enviado encontrado.")
    except Exception as e:
        st.error(f"Erro ao listar extratos: {e}")
        if st.secrets.get("DEBUG", False):
            st.code(traceback.format_exc())

# ----------------------
# Revisão de Dados
# ----------------------
elif page == "Revisão de Dados":
    st.markdown("### 2. Revisão e Correção Manual dos Dados")
    if not st.session_state['df_transacoes_editado'].empty:
        st.info("⚠️ Revise as classificações e corrija manualmente qualquer erro.")
        # opções de contas para seleção
        opcoes_contas = []
        for s in PLANO_DE_CONTAS['sinteticos']:
            for c in s['contas']:
                opcoes_contas.append(f"{c['codigo']} - {c['nome']}")
        with st.expander("Editar Transações", expanded=True):
            df_show = st.session_state['df_transacoes_editado'].copy()
            # garantir colunas
            show_cols = ['data','descricao','valor','tipo_movimentacao','conta_display','nome_conta','tipo_fluxo']
            for c in show_cols:
                if c not in df_show.columns:
                    df_show[c] = ""
            edited_df = st.data_editor(
                df_show[show_cols],
                width='stretch',
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                    "descricao": st.column_config.TextColumn("Descrição", width="large"),
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                    "tipo_movimentacao": st.column_config.SelectboxColumn("Tipo", options=["CREDITO","DEBITO"], required=True),
                    "conta_display": st.column_config.SelectboxColumn("Conta (código - nome)", options=opcoes_contas, required=True),
                    "nome_conta": st.column_config.TextColumn("Nome da Conta", disabled=True),
                    "tipo_fluxo": st.column_config.TextColumn("Tipo de Fluxo", disabled=True)
                },
                num_rows="dynamic",
                key="editor_revisao"
            )
        if st.button("Confirmar Dados e Gerar Relatórios", key="btn_confirmar_revisao"):
            try:
                if 'conta_display' in edited_df.columns:
                    edited_df['conta_analitica'] = edited_df['conta_display'].apply(lambda x: x.split(' - ')[0].strip() if isinstance(x,str) and ' - ' in x else x)
                edited_df = enriquecer_com_plano_contas(edited_df)
                df_to_save = edited_df.copy()
                df_to_save['data'] = pd.to_datetime(df_to_save['data'], errors='coerce').dt.strftime("%Y-%m-%d")
                df_to_save['valor'] = pd.to_numeric(df_to_save['valor'], errors='coerce').fillna(0)
                col_valid = ["data","descricao","valor","tipo_movimentacao","conta_analitica"]
                df_to_save = df_to_save[col_valid]
                # gravar no supabase
                supabase.table("transacoes").delete().eq("user_id", user.id).execute()
                recs = df_to_save.to_dict(orient='records')
                for r in recs:
                    r['user_id'] = user.id
                    r['extrato_id'] = None
                supabase.table("transacoes").insert(recs).execute()
                st.success("Transações revisadas salvas com sucesso.")
                # recarregar no estado
                df_new = enriquecer_com_plano_contas(pd.DataFrame(recs))
                st.session_state['df_transacoes_editado'] = df_new
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
                if st.secrets.get("DEBUG", False):
                    st.code(traceback.format_exc())
    else:
        st.warning("Nenhum dado processado encontrado. Volte para 'Upload e Extração' para carregar arquivos.")

    # logo abaixo da revisão, mostramos o resumo dos extratos (fora do expander)
    st.markdown("#### Extratos enviados (resumo)")
    try:
        extratos_result = supabase.table("extratos").select("id, nome_arquivo, criado_em").eq("user_id", user.id).order("criado_em", desc=True).execute()
        if extratos_result.data:
            extrs = pd.DataFrame(extratos_result.data)
            extrs['criado_em'] = pd.to_datetime(extrs['criado_em'], errors='coerce')
            resumo_rows = []
            for _, r in extrs.iterrows():
                try:
                    tran_res = supabase.table("transacoes").select("id").eq("user_id", user.id).eq("extrato_id", r['id']).execute()
                    count_trans = len(tran_res.data) if tran_res.data else 0
                except Exception:
                    count_trans = 0
                resumo_rows.append({
                    "nome_arquivo": r['nome_arquivo'],
                    "data_upload": r['criado_em'].strftime("%d/%m/%Y %H:%M") if not pd.isna(r['criado_em']) else "",
                    "n_transacoes": count_trans
                })
            df_resumo = pd.DataFrame(resumo_rows)
            st.table(df_resumo)
        else:
            st.info("Nenhum arquivo de extrato enviado.")
    except Exception as e:
        st.error(f"Erro ao listar extratos: {e}")
        if st.secrets.get("DEBUG", False):
            st.code(traceback.format_exc())

# ----------------------
# Dashboard & Relatórios
# ----------------------
elif page == "Dashboard & Relatórios":
    st.markdown("### 3. Relatórios Gerenciais e Dashboard")
    # exibir período usado (se presente)
    try:
        d_display = st.session_state.get('periodo_combined', None)
        if d_display:
            st.markdown(f"**Período selecionado:** {d_display}")
        else:
            st.markdown("**Período selecionado:** (use o filtro na barra lateral)")
    except Exception:
        pass

    # carregar dados do estado (upload ou consulta via sidebar)
    if not st.session_state['df_transacoes_editado'].empty:
        df_final = st.session_state['df_transacoes_editado'].copy()
        # garantir colunas e tipos
        if 'data' in df_final.columns:
            df_final['data'] = pd.to_datetime(df_final['data'], errors='coerce', dayfirst=True)
        df_final['valor'] = pd.to_numeric(df_final.get('valor', 0), errors='coerce').fillna(0)
        if 'conta_analitica' not in df_final.columns:
            df_final = enriquecer_com_plano_contas(df_final)

        # calcular score e indicadores
        try:
            resultado_score = calcular_score_fluxo(df_final)
            score = resultado_score.get('score_final', 0.0)
            valores = resultado_score.get('valores', {})
        except Exception:
            score = 0.0
            valores = {}

        # KPIs (igual ao aicode_semBD)
        st.markdown("#### 📊 Indicadores e Score")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🔹 Score Financeiro (0–100)", f"{score:.1f}")
        col2.metric("🏦 Margem de Caixa Operacional", f"{valores.get('margem_op', 0.0):.2f}")
        col3.metric("🔻 Peso de Retiradas", f"{valores.get('peso_retiradas', 0.0):.2f}")
        aut = valores.get('autossuficiencia', 0.0)
        col4.metric("📈 Autossuficiência Operacional", "∞" if aut==float('inf') else f"{aut:.2f}")

        st.markdown("---")
        # Gráfico de evolução dos indicadores (reaproveitei a função existente em plotly)
        criar_grafico_indicadores_plotly = None  # placeholder não usado; use função plotly abaixo
        # Reusar a função 'criar_grafico_indicadores' escrita anteriormente? implementamos aqui com Plotly direto:
        try:
            # preparar série de indicadores por mês
            df_tmp = df_final.copy()
            df_tmp['data'] = pd.to_datetime(df_tmp['data'], errors='coerce', dayfirst=True)
            df_tmp.dropna(subset=['data'], inplace=True)
            df_tmp['mes_ano'] = df_tmp['data'].dt.to_period('M')
            meses = sorted(df_tmp['mes_ano'].unique())
            indicadores_data = []
            meses_pt_short = {1:'Jan',2:'Fev',3:'Mar',4:'Abr',5:'Mai',6:'Jun',7:'Jul',8:'Ago',9:'Set',10:'Out',11:'Nov',12:'Dez'}
            for mes in meses:
                mes_str = f"{meses_pt_short[mes.month]}/{mes.year % 100:02d}"
                df_mes = df_tmp[df_tmp['mes_ano']==mes]
                entradas_op = df_mes[(df_mes['tipo_fluxo']=='OPERACIONAL') & (df_mes['tipo_movimentacao']=='CREDITO')]['valor'].sum()
                caixa_op = df_mes[df_mes['tipo_fluxo']=='OPERACIONAL']['fluxo'].sum() if 'fluxo' in df_mes.columns else df_mes.apply(lambda r: r['valor'] if r['tipo_movimentacao']=='CREDITO' else -r['valor'], axis=1).sum()
                caixa_inv = df_mes[df_mes['tipo_fluxo']=='INVESTIMENTO']['fluxo'].sum() if 'INVESTIMENTO' in df_mes['tipo_fluxo'].unique() else 0
                caixa_fin = df_mes[df_mes['tipo_fluxo']=='FINANCIAMENTO']['fluxo'].sum() if 'FINANCIAMENTO' in df_mes['tipo_fluxo'].unique() else 0
                margem_caixa_op = (caixa_op/entradas_op*100) if entradas_op>0 else 0.0
                intensidade_inv = (abs(caixa_inv)/caixa_op*100) if caixa_op!=0 else 0.0
                intensidade_fin = (caixa_fin/caixa_op*100) if caixa_op!=0 else 0.0
                retiradas = abs(df_mes[(df_mes['conta_analitica']=='FIN-05') & (df_mes['tipo_movimentacao']=='DEBITO')]['valor'].sum())
                peso_retiradas = (retiradas/df_mes[df_mes['tipo_movimentacao']=='DEBITO']['valor'].sum()*100) if df_mes[df_mes['tipo_movimentacao']=='DEBITO']['valor'].sum()!=0 else 0.0
                indicadores_data.append({
                    'Mês': mes_str,
                    'Margem de Caixa Operacional (%)': margem_caixa_op,
                    'Intensidade de Investimento (%)': intensidade_inv,
                    'Intensidade de Financiamento (%)': intensidade_fin,
                    'Peso de Retiradas (%)': peso_retiradas
                })
            df_ind = pd.DataFrame(indicadores_data)
            if not df_ind.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_ind['Mês'], y=df_ind['Margem de Caixa Operacional (%)'], mode='lines+markers', name='Margem de Caixa Operacional (%)', line=dict(color=ACCENT_COLOR, width=3)))
                fig.add_trace(go.Scatter(x=df_ind['Mês'], y=df_ind['Intensidade de Investimento (%)'], mode='lines+markers', name='Intensidade de Investimento (%)', line=dict(color=INVESTMENT_COLOR, width=3)))
                fig.add_trace(go.Scatter(x=df_ind['Mês'], y=df_ind['Intensidade de Financiamento (%)'], mode='lines+markers', name='Intensidade de Financiamento (%)', line=dict(color=FINANCING_COLOR, width=3)))
                fig.add_trace(go.Scatter(x=df_ind['Mês'], y=df_ind['Peso de Retiradas (%)'], mode='lines+markers', name='Peso de Retiradas (%)', line=dict(color=NEGATIVE_COLOR, width=3, dash='dash')))
                fig.update_layout(title='Indicadores Financeiros (%) ao longo do tempo', xaxis_title='Mês', yaxis_title='Percentual (%)', height=420, plot_bgcolor='white', hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Indicadores por mês indisponíveis (dados insuficientes).")
        except Exception as e:
            st.error(f"Erro ao gerar evolução de indicadores: {e}")
            if st.secrets.get("DEBUG", False):
                st.code(traceback.format_exc())

        # Texto "📊 Entenda os Indicadores" usando texto original do aicode_semBD.txt (colado diretamente)
        st.markdown("#### 📊 Entenda os Indicadores")
        st.markdown("""
- **GCO (Geração de Caixa Operacional)**: representa o caixa líquido gerado pelas atividades operacionais no período.
- **Margem de Caixa Operacional**: razão entre caixa operacional e entradas operacionais, indica eficiência na geração de caixa.
- **Peso de Retiradas**: proporção das retiradas pessoais em relação às saídas totais.
- **Intensidade de Investimento**: quanto do caixa operacional foi alocado em investimentos no período.
- **Intensidade de Financiamento**: participação de financiamentos no fluxo de caixa.
- **Autossuficiência Operacional**: capacidade do negócio de financiar investimentos e retiradas a partir do próprio caixa operacional.
        """)

        st.markdown("---")
        # Relatório de fluxo de caixa (sem coluna tipo)
        criar_relatorio_fluxo_caixa_sem_tipo(df_final)

        # Gráficos adicionais solicitados
        grafico_fluxo_mensal_por_categoria(df_final)
        grafico_comparativo_caixa_vs_retiradas(df_final)
        grafico_distribuicao_despesas_por_conta(df_final)

        # Mini-relatório (igual ao aicode_semBD)
        try:
            retiradas_val = abs(df_final[(df_final['conta_analitica']=='FIN-05') & (df_final['tipo_movimentacao']=='DEBITO')]['valor'].sum())
        except Exception:
            retiradas_val = 0.0
        mini_text, classe_texto = gerar_mini_relatorio_local(score, valores, retiradas_val)
        st.markdown("#### **O que este score está me dizendo?**")
        st.markdown(mini_text, unsafe_allow_html=True)

    else:
        st.info("Nenhum dado disponível. Faça upload de extratos na seção 'Upload e Extração' ou confirme as transações na 'Revisão de Dados', ou selecione um período na barra lateral e clique em 'Gerar Relatórios e Dashboard'.")

# ----------------------
# Função restante usada no mini-relatório (copiada da versão anterior)
# ----------------------
def gerar_mini_relatorio_local(score: float, indicadores: Dict[str, float], retiradas_pessoais_val: float):
    gco = indicadores.get('gco', 0.0)
    entradas_op = indicadores.get('entradas_operacionais', 0.0)
    autossuf = indicadores.get('autossuficiencia', 0.0)
    taxa_reinv = indicadores.get('taxa_reinvestimento', 0.0)
    peso_retiradas = indicadores.get('peso_retiradas', 0.0)
    def cor_icone(valor, tipo="financeiro", contexto_caixa_negativo=False):
        if tipo == "financeiro":
            if contexto_caixa_negativo:
                return "🔴"
            return "🟢" if valor > 0 else ("🟠" if valor == 0 else "🔴")
        if tipo == "autossuficiencia":
            if valor == float('inf') or valor > 1.0:
                return "🟢"
            elif valor >= 0.5:
                return "🟠"
            else:
                return "🔴"
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
        comentario_retiradas = "🚨 o caixa operacional está negativo, portanto não há sustentabilidade para retiradas neste período."
    elif retiradas_pessoais_val <= 0:
        comentario_retiradas = "não houve retiradas pessoais, o que ajuda na preservação do caixa."
    elif retiradas_pessoais_val < 0.3 * max(entradas_op, 1):
        comentario_retiradas = "retiradas em nível saudável, sem comprometer o caixa."
    elif retiradas_pessoais_val < 0.6 * max(entradas_op, 1):
        comentario_retiradas = "retiradas moderadas, que merecem monitoramento."
    else:
        comentario_retiradas = "retiradas elevadas, que aumentam o risco financeiro e reduzem a folga de caixa."
    if autossuf == float('inf') or autossuf > 1.5:
        comentario_autossuf = "excelente autossuficiência: o negócio gera caixa suficiente para cobrir retiradas e investimentos."
    elif autossuf >= 1.0:
        comentario_autossuf = "autossuficiência adequada, com boa capacidade de financiar obrigações internas."
    elif autossuf >= 0.5:
        comentario_autossuf = "autossuficiência parcial: é preciso reforçar geração interna de caixa."
    else:
        comentario_autossuf = "baixo nível de autossuficiência: o negócio depende de capital externo, elevando o risco."
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

# ----------------------
# FIM DO ARQUIVO
# ----------------------

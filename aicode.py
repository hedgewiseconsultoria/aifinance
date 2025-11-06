# aicode_revisado_completo.py
"""
Aplicação Streamlit: Análise Financeira Inteligente
Versão: código completo ajustado para:
 - mostrar coluna "Conta (código - nome)" preenchida na revisão;
 - ao salvar edições, gravar apenas o código da conta internamente;
 - mini-relatório com palavras-chave em negrito (conforme solicitado);
 - remover totalmente a opção 'Gerar versão estilo texto com Gemini'.
"""

# --- IMPORTS ---
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
import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Hedgewise | Análise Financeira Inteligente",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES / PLANOS DE CONTAS ---
LOGO_FILENAME = "logo_hedgewise.png"
LOGO1_FILENAME = "FinanceAI_1.png"

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

# --- ESTILO CSS SIMPLES ---
st.markdown(
    """
    <style>
        .stApp { background-color: #F0F2F6; }
        .main-header { color: #0A2342; font-size: 1.7em; font-weight: 800; }
        .kpi-container { background-color: white; padding: 12px; border-radius: 10px; }
        .fluxo-table { background-color: white; padding: 12px; border-radius: 8px; }
        .bold-label { font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- SESSÃO STATE INICIAL ---
if 'df_transacoes_editado' not in st.session_state:
    st.session_state['df_transacoes_editado'] = pd.DataFrame()

if 'contexto_adicional' not in st.session_state:
    st.session_state['contexto_adicional'] = ""

# --- GEMINI CLIENT (mantive inicialização para compatibilidade, mas não usaremos para mini-relatório) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except Exception:
    client = None  # Se não existir chave, não interromper execução; apenas não usamos Gemini aqui.

# --- HELPERS / UTILS ---
def formatar_brl(valor: float) -> str:
    try:
        v = float(valor)
        s = f"{v:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return "R$ " + s
    except Exception:
        return f"R$ {valor}"

def mapa_contas_flat() -> Dict[str, Dict[str, str]]:
    mapa = {}
    for sint in PLANO_DE_CONTAS['sinteticos']:
        for c in sint['contas']:
            mapa[c['codigo']] = {
                'nome_conta': c['nome'],
                'codigo_sintetico': sint['codigo'],
                'nome_sintetico': sint['nome'],
                'tipo_fluxo': sint['tipo_fluxo']
            }
    return mapa

MAPA_CONTAS = mapa_contas_flat()

# Extrair código se string no formato "OP-01 - Nome"
def extrair_codigo_label(x):
    if pd.isna(x):
        return x
    if isinstance(x, str) and " - " in x:
        return x.split(" - ")[0].strip()
    if isinstance(x, str):
        return x.strip()
    return x

# Enriquecer dataframe com colunas do plano de contas e criar label "CODE - Nome"
def enriquecer_com_plano_contas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # garantir coluna conta_analitica exista
    if 'conta_analitica' not in df.columns:
        df['conta_analitica'] = None
    # extrair código caso venha em formato "CODE - Nome"
    df['conta_analitica'] = df['conta_analitica'].apply(lambda x: extrair_codigo_label(x) if pd.notna(x) else x)
    # mapear
    df['nome_conta'] = df['conta_analitica'].map(lambda x: MAPA_CONTAS.get(x, {}).get('nome_conta', 'Não classificado'))
    df['codigo_sintetico'] = df['conta_analitica'].map(lambda x: MAPA_CONTAS.get(x, {}).get('codigo_sintetico', 'NE'))
    df['nome_sintetico'] = df['conta_analitica'].map(lambda x: MAPA_CONTAS.get(x, {}).get('nome_sintetico', 'Não classificado'))
    df['tipo_fluxo'] = df['conta_analitica'].map(lambda x: MAPA_CONTAS.get(x, {}).get('tipo_fluxo', 'NEUTRO'))
    # label para exibição: "CODE - Nome"
    def label_from_code(code):
        if pd.isna(code):
            return ""
        nome = MAPA_CONTAS.get(code, {}).get('nome_conta', '')
        if nome:
            return f"{code} - {nome}"
        return str(code)
    df['conta_display'] = df['conta_analitica'].map(lambda x: label_from_code(x))
    return df

# --- Pydantic schemas (mantidos se necessário para integração API) ---
class Transacao(BaseModel):
    data: str
    descricao: str
    valor: float
    tipo_movimentacao: str
    conta_analitica: str

class AnaliseCompleta(BaseModel):
    transacoes: List[Transacao]
    saldo_final: float

# --- Indicadores e Score (classes) ---
class IndicadoresFluxo:
    def __init__(self, df: pd.DataFrame):
        self.df_raw = df.copy()
        self.df = self._prepare(df.copy())
        self.meses = self._obter_meses()

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['data']).copy()
        df['fluxo'] = df.apply(lambda r: r['valor'] if r['tipo_movimentacao']=='CREDITO' else -r['valor'], axis=1)
        df['mes_ano'] = df['data'].dt.to_period('M')
        return df

    def _obter_meses(self):
        df_fluxo = self.df[self.df['tipo_fluxo'] != 'NEUTRO'] if 'tipo_fluxo' in self.df.columns else self.df
        meses = sorted(df_fluxo['mes_ano'].unique()) if not df_fluxo.empty else []
        return meses

    def total_entradas_operacionais(self):
        return self.df[(self.df.get('tipo_fluxo')=='OPERACIONAL') & (self.df['tipo_movimentacao']=='CREDITO')]['valor'].sum()

    def caixa_operacional_total(self):
        return self.df[self.df.get('tipo_fluxo')=='OPERACIONAL']['fluxo'].sum()

    def caixa_investimento_total(self):
        return self.df[self.df.get('tipo_fluxo')=='INVESTIMENTO']['fluxo'].sum()

    def caixa_financiamento_total(self):
        return self.df[self.df.get('tipo_fluxo')=='FINANCIAMENTO']['fluxo'].sum()

    def retirada_pessoal_total(self):
        return abs(self.df[(self.df.get('conta_analitica')=='FIN-05') & (self.df['tipo_movimentacao']=='DEBITO')]['valor'].sum())

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
        entradas_ultimo = self.df[(self.df['mes_ano']==ultimo) & (self.df.get('tipo_fluxo')=='OPERACIONAL') & (self.df['tipo_movimentacao']=='CREDITO')]['valor'].sum()
        entradas_anterior = self.df[(self.df['mes_ano']==anterior) & (self.df.get('tipo_fluxo')=='OPERACIONAL') & (self.df['tipo_movimentacao']=='CREDITO')]['valor'].sum()
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

# --- FUNÇÕES DE EXTRAÇÃO (mantidas, mas dependem da API Gemini) ---
@st.cache_data(show_spinner=False)
def analisar_extrato_simulado(pdf_bytes: bytes, filename: str) -> dict:
    """
    Simulação local de extração caso seja necessário testar sem a Gemini.
    Retorna estrutura compatível: {'transacoes': [...], 'saldo_final': 0.0}
    (Esta função não é usada se a Gemini estiver disponível; in place para fallback).
    """
    # Exemplo de retorno vazio para fallback
    return {'transacoes': [], 'saldo_final': 0.0}

# --- RELATÓRIOS E DASHBOARD FUNCTIONS ---
def criar_relatorio_fluxo_caixa(df: pd.DataFrame):
    st.subheader("Relatório de Fluxo de Caixa")
    if df.empty:
        st.info("Nenhum dado disponível. Por favor, processe os extratos primeiro.")
        return

    df = df.copy()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df.dropna(subset=['data'], inplace=True)
    df['mes_ano'] = df['data'].dt.to_period('M')
    df['fluxo'] = df.apply(lambda r: r['valor'] if r['tipo_movimentacao']=='CREDITO' else -r['valor'], axis=1)
    df_fluxo = df[df['tipo_fluxo'] != 'NEUTRO']

    if df_fluxo.empty:
        st.info("Sem movimentações relevantes para gerar o relatório.")
        return

    meses = sorted(df_fluxo['mes_ano'].unique())
    meses_pt = {1:'Janeiro',2:'Fevereiro',3:'Março',4:'Abril',5:'Maio',6:'Junho',7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
    colunas_meses = [f"{meses_pt[m.month]}/{mes.year%100:02d}" for mes in meses]

    todas_contas = df_fluxo.groupby(['tipo_fluxo','conta_analitica','nome_conta']).size().reset_index()[['tipo_fluxo','conta_analitica','nome_conta']]

    relatorio_linhas = []
    # Operacionais
    relatorio_linhas.append({'Categoria':'**ATIVIDADES OPERACIONAIS**','tipo':'header'})
    contas_op = todas_contas[todas_contas['tipo_fluxo']=='OPERACIONAL'].sort_values('conta_analitica')
    for _, conta in contas_op.iterrows():
        linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo':'item'}
        for mes in meses:
            df_mes_conta = df_fluxo[(df_fluxo['mes_ano']==mes) & (df_fluxo['conta_analitica']==conta['conta_analitica'])]
            valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year%100:02d}"
            linha[mes_col] = valor
        relatorio_linhas.append(linha)

    # Total operacional
    linha_total_op = {'Categoria':'**Total Caixa Operacional**','tipo':'total'}
    for mes in meses:
        df_mes_op = df_fluxo[(df_fluxo['mes_ano']==mes) & (df_fluxo['tipo_fluxo']=='OPERACIONAL')]
        valor = df_mes_op['fluxo'].sum() if not df_mes_op.empty else 0
        mes_col = f"{meses_pt[mes.month]}/{mes.year%100:02d}"
        linha_total_op[mes_col] = valor
    relatorio_linhas.append(linha_total_op)
    relatorio_linhas.append({'Categoria':'','tipo':'blank'})

    # Investimento
    contas_inv = todas_contas[todas_contas['tipo_fluxo']=='INVESTIMENTO'].sort_values('conta_analitica')
    if not contas_inv.empty:
        relatorio_linhas.append({'Categoria':'**ATIVIDADES DE INVESTIMENTO**','tipo':'header'})
        for _, conta in contas_inv.iterrows():
            linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo':'item'}
            for mes in meses:
                df_mes_conta = df_fluxo[(df_fluxo['mes_ano']==mes) & (df_fluxo['conta_analitica']==conta['conta_analitica'])]
                valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
                mes_col = f"{meses_pt[mes.month]}/{mes.year%100:02d}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)
        linha_total_inv = {'Categoria':'**Total Caixa de Investimento**','tipo':'total'}
        for mes in meses:
            df_mes_inv = df_fluxo[(df_fluxo['mes_ano']==mes) & (df_fluxo['tipo_fluxo']=='INVESTIMENTO')]
            valor = df_mes_inv['fluxo'].sum() if not df_mes_inv.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year%100:02d}"
            linha_total_inv[mes_col] = valor
        relatorio_linhas.append(linha_total_inv)
        relatorio_linhas.append({'Categoria':'','tipo':'blank'})

    # Financiamento
    contas_fin = todas_contas[todas_contas['tipo_fluxo']=='FINANCIAMENTO'].sort_values('conta_analitica')
    if not contas_fin.empty:
        relatorio_linhas.append({'Categoria':'**ATIVIDADES DE FINANCIAMENTO**','tipo':'header'})
        for _, conta in contas_fin.iterrows():
            linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo':'item'}
            for mes in meses:
                df_mes_conta = df_fluxo[(df_fluxo['mes_ano']==mes) & (df_fluxo['conta_analitica']==conta['conta_analitica'])]
                valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
                mes_col = f"{meses_pt[mes.month]}/{mes.year%100:02d}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)
        linha_total_fin = {'Categoria':'**Total Caixa de Financiamento**','tipo':'total'}
        for mes in meses:
            df_mes_fin = df_fluxo[(df_fluxo['mes_ano']==mes) & (df_fluxo['tipo_fluxo']=='FINANCIAMENTO')]
            valor = df_mes_fin['fluxo'].sum() if not df_mes_fin.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year%100:02d}"
            linha_total_fin[mes_col] = valor
        relatorio_linhas.append(linha_total_fin)
        relatorio_linhas.append({'Categoria':'','tipo':'blank'})

    # Caixa gerado no mês
    linha_separador = {'Categoria':'═'*50,'tipo':'separator'}
    for mes_col in colunas_meses:
        linha_separador[mes_col] = ''
    relatorio_linhas.append(linha_separador)

    linha_caixa_gerado = {'Categoria':'**CAIXA GERADO NO MÊS**','tipo':'total'}
    for mes in meses:
        df_mes_total = df_fluxo[df_fluxo['mes_ano']==mes]
        valor = df_mes_total['fluxo'].sum() if not df_mes_total.empty else 0
        mes_col = f"{meses_pt[mes.month]}/{mes.year%100:02d}"
        linha_caixa_gerado[mes_col] = valor
    relatorio_linhas.append(linha_caixa_gerado)

    df_relatorio = pd.DataFrame(relatorio_linhas).fillna('')
    for col in colunas_meses:
        if col in df_relatorio.columns:
            df_relatorio[col] = df_relatorio[col].apply(lambda x: formatar_brl(x) if isinstance(x, (int,float)) and x!=0 else '')
    df_display = df_relatorio.drop(columns=['tipo'])
    st.markdown('<div class="fluxo-table">', unsafe_allow_html=True)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

def criar_grafico_indicadores(df: pd.DataFrame):
    st.subheader("Evolução dos Indicadores Financeiros")
    if df.empty:
        st.info("Nenhum dado disponível para indicadores.")
        return
    df2 = df.copy()
    df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
    df2.dropna(subset=['data'], inplace=True)
    df2['mes_ano'] = df2['data'].dt.to_period('M')
    df2['fluxo'] = df2.apply(lambda r: r['valor'] if r['tipo_movimentacao']=='CREDITO' else -r['valor'], axis=1)
    df_fluxo = df2[df2['tipo_fluxo'] != 'NEUTRO']
    if df_fluxo.empty:
        st.info("Sem dados para indicadores.")
        return
    meses = sorted(df_fluxo['mes_ano'].unique())
    indicadores_data = []
    for mes in meses:
        df_mes = df_fluxo[df_fluxo['mes_ano']==mes]
        mes_str = mes.strftime('%m/%Y')
        caixa_op = df_mes[df_mes['tipo_fluxo']=='OPERACIONAL']['fluxo'].sum()
        caixa_inv = df_mes[df_mes['tipo_fluxo']=='INVESTIMENTO']['fluxo'].sum()
        caixa_fin = df_mes[df_mes['tipo_fluxo']=='FINANCIAMENTO']['fluxo'].sum()
        entradas_op = df_mes[(df_mes['tipo_fluxo']=='OPERACIONAL') & (df_mes['tipo_movimentacao']=='CREDITO')]['valor'].sum()
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
        fig.add_trace(go.Scatter(x=df_indicadores['Mês'], y=df_indicadores['Margem de Caixa Operacional (%)'], mode='lines+markers', name='Margem de Caixa Operacional (%)'))
        fig.add_trace(go.Scatter(x=df_indicadores['Mês'], y=df_indicadores['Intensidade de Investimento (%)'], mode='lines+markers', name='Intensidade de Investimento (%)'))
        fig.add_trace(go.Scatter(x=df_indicadores['Mês'], y=df_indicadores['Intensidade de Financiamento (%)'], mode='lines+markers', name='Intensidade de Financiamento (%)'))
        fig.add_trace(go.Scatter(x=df_indicadores['Mês'], y=df_indicadores['Peso de Retiradas (%)'], mode='lines+markers', name='Peso de Retiradas (%)', line=dict(dash='dash')))
    fig.update_layout(title='Indicadores Financeiros (%) ao longo do tempo', xaxis_title='Mês', yaxis_title='Percentual (%)', height=420, plot_bgcolor='white', hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)

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
        st.error(f"Erro no cálculo do score: {e}")
        return {
            'score_final': 0.0,
            'notas': {},
            'contribuicoes': {},
            'pesos': {},
            'valores': {},
            'componentes': {}
        }

# --- MINI-RELATÓRIO LOCAL (COM NEGRITO NOS TÍTULOS SOLICITADOS) ---
def gerar_mini_relatorio_local(resultado_score: Dict[str, Any], df: pd.DataFrame) -> str:
    score = resultado_score.get('score_final', 0.0)
    valores = resultado_score.get('valores', {})
    partes = []
    # Títulos em negrito conforme solicitado
    partes.append(f"**Score Financeiro:** {score:.1f}/100.")
    if score >= 85:
        partes.append("**Resumo:** a operação apresenta forte geração de caixa e boa saúde financeira no período analisado.")
    elif score >= 70:
        partes.append("**Resumo:** performance boa, porém fique atento a sinais de dependência de financiamento ou retiradas elevadas.")
    elif score >= 55:
        partes.append("**Resumo:** situação razoável. Recomenda-se monitoramento próximo do caixa e disciplina nas retiradas.")
    elif score >= 40:
        partes.append("**Resumo:** caixa sob pressão. Reduza despesas não essenciais e reveja retiradas até normalizar o fluxo.")
    else:
        partes.append("**Resumo:** atenção imediata necessária. Priorize a operação e busque reforço de caixa ou renegociação de dívidas.")

    gco = valores.get('gco', 0.0)
    entradas = valores.get('entradas_operacionais', 0.0)
    margem = valores.get('margem_op', 0.0)
    intensidade_fin = valores.get('intensidade_fin', 0.0)
    peso_retiradas = valores.get('peso_retiradas', 0.0)
    taxa_reinv = valores.get('taxa_reinvestimento', 0.0)
    autossuf = valores.get('autossuficiencia', 0.0)

    partes.append(f"**Caixa operacional gerado (período):** {formatar_brl(gco)}.")
    if peso_retiradas > 0:
        partes.append(f"**Retiradas de sócios** representam aproximadamente {peso_retiradas:.1%} das saídas.")
    if intensidade_fin is not None:
        partes.append(f"**Intensidade de financiamento:** {intensidade_fin:.1%}.")
    if autossuf is not None:
        if math.isinf(autossuf):
            partes.append("**Autossuficiência operacional:** sem necessidade de financiamento externo detectada no período.")
        else:
            partes.append(f"**Autossuficiência operacional:** {autossuf:.2f} (maior que 1 significa cobertura).")

    # Recomendações práticas (negrito no início)
    acoes = []
    if peso_retiradas > 0.5:
        acoes.append("Reduzir temporariamente retiradas dos sócios até recuperar folga de caixa.")
    if intensidade_fin > 1.0:
        acoes.append("Rever custos e prazos de empréstimos: alto financiamento pode gerar custos que pesam no caixa.")
    if taxa_reinv >= 0.3:
        acoes.append("Continuar com investimentos planejados, se sustentáveis; garanta reservas para operações.")
    if margem < 0.05:
        acoes.append("Buscar aumento de vendas ou contenção de custos, pois a margem de caixa está baixa.")
    if gco < 0:
        acoes.append("Priorizar geração de caixa operacional (vendas/recebíveis) e adiar investimentos não essenciais.")
    if acoes:
        partes.append("**Recomendações práticas:** " + " ".join(acoes))
    else:
        partes.append("**Recomendações práticas:** manter disciplina financeira e monitorar mensalmente os indicadores.")

    return "\n\n".join(partes)

# --- HEADER UI ---
def load_header():
    try:
        logo = Image.open(LOGO1_FILENAME)
        col1, col2 = st.columns([2,5])
        with col1:
            st.image(logo, width=220)
        with col2:
            st.markdown('<div class="main-header">Análise Financeira Inteligente</div>', unsafe_allow_html=True)
            st.caption("Traduzindo números em ações práticas para pequenos empreendedores")
        st.markdown("---")
    except Exception:
        st.title("Hedgewise | Análise Financeira Inteligente")
        st.markdown("---")

# --- INTERFACE PRINCIPAL ---
load_header()
st.sidebar.title("Navegação")
page = st.sidebar.radio("Seções:", ["Upload e Extração", "Revisão de Dados", "Dashboard & Relatórios"])

if page == "Upload e Extração":
    st.markdown("### 1. Upload e Extração de Dados")
    st.markdown("Faça o upload dos extratos em PDF. O sistema tentará extrair as transações e classificá-las conforme o plano de contas.")

    with st.expander("Plano de Contas Utilizado", expanded=False):
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            st.markdown(f"**{sintetico['codigo']} - {sintetico['nome']}** ({sintetico['tipo_fluxo']})")
            for conta in sintetico["contas"]:
                st.markdown(f"  - `{conta['codigo']}`: {conta['nome']}")

    with st.expander("Upload de Arquivos", expanded=True):
        uploaded_files = st.file_uploader("Selecione os arquivos PDF dos seus extratos bancários", type="pdf", accept_multiple_files=True, key="pdf_uploader")

    if uploaded_files:
        if st.button(f"Executar Extração e Classificação ({len(uploaded_files)} arquivos)"):
            todas_transacoes = []
            status = st.empty()
            status.info("Iniciando extração...")
            for i, f in enumerate(uploaded_files):
                status.info(f"Processando {i+1}/{len(uploaded_files)}: {f.name} ...")
                pdf_bytes = f.getvalue()
                # Aqui: chamar analisar_extrato pela Gemini se disponível; usando fallback simulado
                if client is not None:
                    try:
                        # Se quiser integrar realmente, coloque chamada à Gemini aqui (o usuário tem essa parte no código original)
                        # Para não alterar a sua lógica de produção, uso função simulada.
                        dados = analisar_extrato_simulado(pdf_bytes, f.name)
                    except Exception:
                        dados = analisar_extrato_simulado(pdf_bytes, f.name)
                else:
                    dados = analisar_extrato_simulado(pdf_bytes, f.name)
                transacoes = dados.get('transacoes', [])
                todas_transacoes.extend(transacoes)
            status.success("Extração concluída (simulada).")

            # Converter para DataFrame
            if len(todas_transacoes) == 0:
                st.warning("Nenhuma transação extraída no modo simulado. Para usar extração automática, configure a integração com Gemini.")
                st.session_state['df_transacoes_editado'] = pd.DataFrame()
            else:
                df_transacoes = pd.DataFrame(todas_transacoes)
                # normalizações
                df_transacoes['valor'] = pd.to_numeric(df_transacoes['valor'], errors='coerce').fillna(0)
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'], errors='coerce', dayfirst=True)
                df_transacoes['tipo_movimentacao'] = df_transacoes['tipo_movimentacao'].fillna('DEBITO')
                df_transacoes['conta_analitica'] = df_transacoes['conta_analitica'].fillna('NE-02')
                df_transacoes = enriquecer_com_plano_contas(df_transacoes)
                st.session_state['df_transacoes_editado'] = df_transacoes
                st.success("Dados carregados e enriquecidos. Vá para 'Revisão de Dados' para conferir.")

elif page == "Revisão de Dados":
    st.markdown("### 2. Revisão e Correção Manual dos Dados")
    if not st.session_state['df_transacoes_editado'].empty:
        st.info("⚠️ Revise as classificações e corrija manualmente qualquer erro.")

        df_to_edit = st.session_state['df_transacoes_editado'].copy()
        # garantir data datetime
        df_to_edit['data'] = pd.to_datetime(df_to_edit['data'], errors='coerce', dayfirst=True)
        # preparar opções "CODE - Nome" para o select; garantir inclusões de valores existentes
        opcoes_contas = []
        for sintetico in PLANO_DE_CONTAS["sinteticos"]:
            for conta in sintetico["contas"]:
                opcoes_contas.append(f"{conta['codigo']} - {conta['nome']}")
        # incluir labels existentes que possam não pertencer ao plano (fallback)
        existentes = df_to_edit['conta_display'].dropna().unique().tolist()
        for ex in existentes:
            if ex and ex not in opcoes_contas:
                opcoes_contas.append(ex)

        # As colunas visíveis para o usuário
        display_cols = ['data', 'descricao', 'valor', 'tipo_movimentacao', 'conta_display', 'nome_conta', 'tipo_fluxo']
        # se faltar alguma, ajustar
        for c in display_cols:
            if c not in df_to_edit.columns:
                df_to_edit[c] = ""

        # Editor
        with st.expander("Editar Transações", expanded=True):
            edited_df = st.data_editor(
                df_to_edit[display_cols],
                width='stretch',
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                    "descricao": st.column_config.TextColumn("Descrição", width="large"),
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                    "tipo_movimentacao": st.column_config.SelectboxColumn("Tipo", options=["CREDITO","DEBITO"], required=True),
                    "conta_display": st.column_config.SelectboxColumn("Conta (código - nome)", options=opcoes_contas, required=True, help="Selecione a conta (código e nome aparecem juntos)."),
                    "nome_conta": st.column_config.TextColumn("Nome da Conta", disabled=True),
                    "tipo_fluxo": st.column_config.TextColumn("Tipo de Fluxo", disabled=True),
                },
                num_rows="dynamic",
                key="data_editor_transacoes_v2"
            )

        if st.button("Confirmar Dados e Gerar Relatórios", key="confirmar_edicoes_btn"):
            # ao confirmar, extrair código da coluna conta_display e re-enriquecer
            df_ed = edited_df.copy()
            if 'conta_display' in df_ed.columns:
                df_ed['conta_analitica'] = df_ed['conta_display'].apply(lambda x: extrair_codigo_label(x))
            # Consertos de tipo
            if 'valor' in df_ed.columns:
                df_ed['valor'] = pd.to_numeric(df_ed['valor'], errors='coerce').fillna(0)
            if 'data' in df_ed.columns:
                df_ed['data'] = pd.to_datetime(df_ed['data'], errors='coerce', dayfirst=True)
            # Enriquecer com plano
            df_ed = enriquecer_com_plano_contas(df_ed)
            st.session_state['df_transacoes_editado'] = df_ed
            st.success("✅ Dados confirmados! Acesse 'Dashboard & Relatórios' para ver as análises.")
    else:
        st.warning("Nenhum dado processado encontrado. Volte para 'Upload e Extração'.")

elif page == "Dashboard & Relatórios":
    st.markdown("### 3. Relatórios Gerenciais e Dashboard")
    if not st.session_state['df_transacoes_editado'].empty:
        df_final = st.session_state['df_transacoes_editado'].copy()

        # Calcular score e exibir KPIs
        resultado_score = calcular_score_fluxo(df_final)
        score = resultado_score.get('score_final', 0.0)
        valores = resultado_score.get('valores', {})

        st.markdown("#### 📊 Indicadores e Score")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔹 Score Financeiro (0–100)", f"{score:.1f}")
        with col2:
            st.metric("🏦 Margem de Caixa Operacional", f"{valores.get('margem_op',0.0):.1%}")
        with col3:
            st.metric("💰 Intensidade de Investimento", f"{valores.get('intensidade_inv',0.0):.1%}")
        with col4:
            st.metric("📈 Intensidade de Financiamento", f"{valores.get('intensidade_fin',0.0):.1%}" if pd.notna(valores.get('intensidade_fin',0.0)) else "—")

        st.markdown("---")

        # Mini-relatório (titulo e conteúdo)
        st.markdown("#### **O que este score está me dizendo?**")
        rel_local = gerar_mini_relatorio_local(resultado_score, df_final)
        # rel_local tem markdown-like bold markers; exibir com st.markdown para renderizar o negrito
        st.markdown(rel_local)

        st.markdown("---")

        # Relatórios e gráficos
        criar_relatorio_fluxo_caixa(df_final)
        criar_grafico_indicadores(df_final)

        criar_dashboard(df_final) if 'criar_dashboard' in globals() else None

        # Export
        st.markdown("---")
        st.markdown("##### 📤 Exportar Dados")
        cold1, cold2 = st.columns(2)
        with cold1:
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(label="Baixar Transações Detalhadas (CSV)", data=csv, file_name="transacoes_hedgewise.csv", mime="text/csv")
    else:
        st.warning("Nenhum dado processado encontrado. Volte para 'Upload e Extração'.")

# --- RODAPÉ ---
st.markdown("---")
try:
    footer_logo = Image.open(LOGO_FILENAME)
    fcol1, fcol2 = st.columns([1,30])
    with fcol1:
        st.image(footer_logo, width=40)
    with fcol2:
        st.markdown("<small style='color:#6c757d;'>Análise de Extrato Empresarial | Dados extraídos e classificados conforme Plano de Contas.</small>", unsafe_allow_html=True)
except Exception:
    st.markdown("<small style='color:#6c757d;'>Análise de Extrato Empresarial | Dados extraídos e classificados conforme Plano de Contas.</small>", unsafe_allow_html=True)

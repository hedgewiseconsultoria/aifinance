import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
from typing import Dict, Any, List
from datetime import datetime, timedelta
import traceback

# Variáveis de cor
try:
    PRIMARY_COLOR = st.session_state.get('PRIMARY_COLOR', "#0A2342")
    SECONDARY_COLOR = st.session_state.get('SECONDARY_COLOR', "#000000")
    ACCENT_COLOR = st.session_state.get('ACCENT_COLOR', "#007BFF")
    NEGATIVE_COLOR = st.session_state.get('NEGATIVE_COLOR', "#DC3545")
    FINANCING_COLOR = st.session_state.get('FINANCING_COLOR', "#FFC107")
    INVESTMENT_COLOR = st.session_state.get('INVESTMENT_COLOR', "#28A745")
except:
    PRIMARY_COLOR = "#0A2342"
    SECONDARY_COLOR = "#000000"
    ACCENT_COLOR = "#007BFF"
    NEGATIVE_COLOR = "#DC3545"
    FINANCING_COLOR = "#FFC107"
    INVESTMENT_COLOR = "#28A745"


# ----------------------------------------------------------
# Formatador BRL
# ----------------------------------------------------------
def formatar_brl(valor: float) -> str:
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return "R$ " + valor_brl
    except:
        return f"R$ {valor:.2f}"


# ----------------------------------------------------------
# Mini-Relatório (Análise Rápida)
# ----------------------------------------------------------
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

    # Classificação textual do Score
    if score >= 85:
        resumo = "Situação muito saudável: boa geração de caixa e equilíbrio nas finanças."
        classe_texto = "Classe A – Excelente"
    elif score >= 70:
        resumo = "Situação estável, mas requer acompanhamento de retiradas e uso de financiamentos."
        classe_texto = "Classe B – Boa"
    elif score >= 55:
        if gco > 0:
            resumo = "Caixa positivo, mas com espaço para melhorar a eficiência financeira."
            classe_texto = "Classe C – Moderado"
        else:
            resumo = "Caixa pressionado — atenção aos custos e retiradas."
            classe_texto = "Classe D – Alto risco"
    elif score >= 40:
        if gco > 0 and autossuf >= 1.0:
            resumo = "Situação aceitável, mas exige disciplina."
            classe_texto = "Classe C – Moderado"
        else:
            resumo = "Risco elevado: caixa fraco e dependência de capital externo."
            classe_texto = "Classe D – Alto risco"
    else:
        resumo = "Situação crítica: ações imediatas são recomendadas."
        classe_texto = "Classe E – Crítico"

    if gco < 0:
        comentario_retiradas = "🚨 caixa negativo — retiradas não são sustentáveis neste período."
    elif retiradas_pessoais_val <= 0:
        comentario_retiradas = "Sem retiradas pessoais, o que preserva o caixa."
    elif retiradas_pessoais_val < 0.3 * max(entradas_op, 1):
        comentario_retiradas = "Retiradas em nível saudável."
    elif retiradas_pessoais_val < 0.6 * max(entradas_op, 1):
        comentario_retiradas = "Retiradas moderadas; acompanhe mensalmente."
    else:
        comentario_retiradas = "Retiradas elevadas, aumentando risco financeiro."

    aut_text = "∞" if autossuf == float('inf') else f"{autossuf:.2f}"

    html = f"""
    <div style='line-height:1.6; font-size:15px;'>
        <b>Resumo geral:</b> {resumo}<br><br>

        <b>Caixa operacional (período):</b>
        {span_valor(formatar_brl(gco), cor_icone(gco))}<br>

        <b>Retiradas de sócios:</b>
        {span_valor(formatar_brl(retiradas_pessoais_val), cor_icone(retiradas_pessoais_val, contexto_caixa_negativo=(gco < 0)))} —
        {comentario_retiradas}<br>

        <b>Autossuficiência operacional:</b>
        {span_valor(aut_text, cor_icone(autossuf, "autossuficiencia"))}<br><br>

        <b>Recomendação geral:</b>
        Avalie periodicamente custos, entradas e retiradas para manter o caixa saudável.
    </div>
    """

    return html, classe_texto


# ----------------------------------------------------------
# Indicadores do Fluxo
# ----------------------------------------------------------
class IndicadoresFluxo:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._processar_df()

    def _processar_df(self):
        if self.df.empty:
            self.df_fluxo = pd.DataFrame()
            return

        self.df['data'] = pd.to_datetime(self.df['data'], errors='coerce', dayfirst=True)
        self.df.dropna(subset=['data'], inplace=True)
        self.df['mes_ano'] = self.df['data'].dt.to_period('M')
        self.df['fluxo'] = self.df.apply(
            lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'],
            axis=1
        )
        self.df_fluxo = self.df[self.df['tipo_fluxo'] != 'NEUTRO'].copy()

    def resumo_indicadores(self) -> Dict[str, float]:

        if self.df_fluxo.empty:
            return {
                'gco': 0.0, 'entradas_operacionais': 0.0, 'margem_op': 0.0,
                'autossuficiencia': 0.0, 'taxa_reinvestimento': 0.0,
                'peso_retiradas': 0.0, 'intensidade_fin': 0.0,
                'crescimento_entradas': 0.0, 'retiradas_pessoais': 0.0
            }

        caixa_op = self.df_fluxo[self.df_fluxo['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()

        entradas_op = self.df_fluxo[
            (self.df_fluxo['tipo_fluxo'] == 'OPERACIONAL') &
            (self.df_fluxo['tipo_movimentacao'] == 'CREDITO')
        ]['valor'].sum()

        margem_op = (caixa_op / entradas_op) if entradas_op > 0 else 0.0

        retiradas_pessoais = abs(self.df[
            (self.df['conta_analitica'] == 'FIN-05') &
            (self.df['tipo_movimentacao'] == 'DEBITO')
        ]['valor'].sum())

        total_debitos = self.df[self.df['tipo_movimentacao'] == 'DEBITO']['valor'].sum()
        peso_retiradas = (retiradas_pessoais / total_debitos) if total_debitos > 0 else 0.0

        caixa_inv = self.df_fluxo[self.df_fluxo['tipo_fluxo'] == 'INVESTIMENTO']['fluxo'].sum()
        caixa_fin = self.df_fluxo[self.df_fluxo['tipo_fluxo'] == 'FINANCIAMENTO']['fluxo'].sum()

        denominador = abs(caixa_inv) + retiradas_pessoais
        autossuf = float('inf') if denominador == 0 else (caixa_op + caixa_fin) / denominador

        taxa_reinvest = (caixa_op - retiradas_pessoais) / caixa_op if caixa_op > 0 else 0.0

        meses = sorted(self.df_fluxo['mes_ano'].unique())
        crescimento = 0.0

        if len(meses) >= 2:
            ini = self.df_fluxo[
                (self.df_fluxo['mes_ano'] == meses[0]) &
                (self.df_fluxo['tipo_fluxo'] == 'OPERACIONAL') &
                (self.df_fluxo['tipo_movimentacao'] == 'CREDITO')
            ]['valor'].sum()

            fim = self.df_fluxo[
                (self.df_fluxo['mes_ano'] == meses[-1]) &
                (self.df_fluxo['tipo_fluxo'] == 'OPERACIONAL') &
                (self.df_fluxo['tipo_movimentacao'] == 'CREDITO')
            ]['valor'].sum()

            if ini > 0:
                crescimento = (fim - ini) / ini

        return {
            'gco': caixa_op,
            'entradas_operacionais': entradas_op,
            'margem_op': margem_op,
            'autossuficiencia': autossuf,
            'taxa_reinvestimento': taxa_reinvest,
            'peso_retiradas': peso_retiradas,
            'intensidade_inv': caixa_inv,
            'intensidade_fin': caixa_fin,
            'crescimento_entradas': crescimento,
            'retiradas_pessoais': retiradas_pessoais
        }


# ----------------------------------------------------------
# Score
# ----------------------------------------------------------
class ScoreCalculator:
    def __init__(self):
        self.pesos = {
            'gco': 25,
            'margem_op': 20,
            'peso_retiradas': 15,
            'autossuficiencia': 15,
            'taxa_reinvestimento': 10,
            'crescimento_entradas': 10,
            'intensidade_fin': 5
        }

    def normalizar_gco(self, gco, entradas):
        if entradas <= 0:
            return 0.0
        margem = gco / entradas
        if margem >= 0.3: return 100
        if margem >= 0.15: return 80
        if margem > 0: return 60
        if margem == 0: return 40
        if margem >= -0.1: return 20
        return 0

    def normalizar_margem(self, m):
        if m >= 0.3: return 100
        if m >= 0.15: return 80
        if m > 0: return 60
        if m == 0: return 40
        if m >= -0.1: return 20
        return 0

    def normalizar_peso_retiradas(self, p):
        if p <= 0.1: return 100
        if p <= 0.25: return 80
        if p <= 0.4: return 60
        if p <= 0.6: return 40
        return 20

    def normalizar_intensidade_fin(self, caixa_fin, margem_op):
        if margem_op > 0:
            if caixa_fin <= 0:
                return 100
            elif caixa_fin < 0.2 * margem_op:
                return 80
            else:
                return 60
        else:
            if caixa_fin <= 0:
                return 80
            elif caixa_fin < 0.5 * abs(margem_op):
                return 40
            else:
                return 20

    def normalizar_crescimento(self, c):
        if c >= 0.2: return 100
        if c >= 0.05: return 80
        if c >= 0: return 60
        return 40

    def normalizar_reinvestimento(self, r):
        if r >= 0.5: return 100
        if r >= 0.3: return 80
        if r >= 0.1: return 60
        return 20

    def normalizar_autossuficiencia(self, a):
        if math.isinf(a): return 100
        if a >= 1.5: return 100
        if a >= 1.0: return 80
        if a >= 0.5: return 50
        return 20

    def calcular_score(self, indicadores):

        notas = {
            'gco': self.normalizar_gco(indicadores['gco'], indicadores['entradas_operacionais']),
            'margem_op': self.normalizar_margem(indicadores['margem_op']),
            'peso_retiradas': self.normalizar_peso_retiradas(indicadores['peso_retiradas']),
            'autossuficiencia': self.normalizar_autossuficiencia(indicadores['autossuficiencia']),
            'taxa_reinvestimento': self.normalizar_reinvestimento(indicadores['taxa_reinvestimento']),
            'crescimento_entradas': self.normalizar_crescimento(indicadores['crescimento_entradas']),
            'intensidade_fin': self.normalizar_intensidade_fin(indicadores['intensidade_fin'], indicadores['margem_op']),
        }

        score = 0
        contribs = {}

        for k, peso in self.pesos.items():
            contrib = notas[k] * (peso / 100)
            contribs[k] = round(contrib, 2)
            score += contrib

        return {
            "score": round(score, 1),
            "notas": notas,
            "contribuicoes": contribs,
            "pesos": self.pesos
        }


# ----------------------------------------------------------
# Wrapper do Score
# ----------------------------------------------------------
def calcular_score_fluxo(df):
    try:
        ind = IndicadoresFluxo(df)
        valores = ind.resumo_indicadores()
        sc = ScoreCalculator()
        r = sc.calcular_score(valores)
        return {
            'score_final': r["score"],
            'notas': r["notas"],
            'contribuicoes': r["contribuicoes"],
            'pesos': r["pesos"],
            'valores': valores
        }
    except:
        return {
            'score_final': 0.0,
            'notas': {}, 'contribuicoes': {}, 'pesos': {},
            'valores': {}
        }


# ----------------------------------------------------------
# Relatório de Fluxo de Caixa (Tabela)
# ----------------------------------------------------------
def criar_relatorio_fluxo_caixa(df, PLANO_DE_CONTAS):

    st.subheader("Relatório de Fluxo de Caixa")

    if df.empty:
        st.info("Nenhum dado disponível.")
        return

    df = df.copy()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df.dropna(subset=['data'], inplace=True)
    df['mes_ano'] = df['data'].dt.to_period('M')
    df['fluxo'] = df.apply(lambda r: r['valor'] if r['tipo_movimentacao']=="CREDITO" else -r['valor'], axis=1)
    df_fluxo = df[df['tipo_fluxo'] != 'NEUTRO']

    meses = sorted(df_fluxo['mes_ano'].unique())
    meses_pt = {1:'Jan',2:'Fev',3:'Mar',4:'Abr',5:'Mai',6:'Jun',7:'Jul',8:'Ago',9:'Set',10:'Out',11:'Nov',12:'Dez'}

    colunas_meses = [f"{meses_pt[m.month]}/{str(m.year)[2:]}" for m in meses]

    todas_contas = df_fluxo.groupby(['tipo_fluxo','conta_analitica','nome_conta']).size().reset_index()[['tipo_fluxo','conta_analitica','nome_conta']]
    linhas = []

    def adicionar_bloco(tipo_fluxo, titulo):
        contas = todas_contas[todas_contas['tipo_fluxo']==tipo_fluxo].sort_values('conta_analitica')
        if contas.empty:
            return
        linhas.append({'Categoria': f"**{titulo}**", 'tipo':'header'})
        for _, c in contas.iterrows():
            item = {'Categoria': f"  {c['conta_analitica']} - {c['nome_conta']}", 'tipo':'item'}
            for m in meses:
                valor = df_fluxo[
                    (df_fluxo['mes_ano']==m) & 
                    (df_fluxo['conta_analitica']==c['conta_analitica'])
                ]['fluxo'].sum()
                item[f"{meses_pt[m.month]}/{str(m.year)[2:]}"] = valor
            linhas.append(item)

        tot = {'Categoria': f"**Total {titulo}**", 'tipo':'total'}
        for m in meses:
            tot[f"{meses_pt[m.month]}/{str(m.year)[2:]}"] = df_fluxo[
                (df_fluxo['mes_ano']==m) &
                (df_fluxo['tipo_fluxo']==tipo_fluxo)
            ]['fluxo'].sum()
        linhas.append(tot)
        linhas.append({'Categoria': '', 'tipo':'blank'})

    # Blocos
    adicionar_bloco('OPERACIONAL', 'Caixa Operacional')
    adicionar_bloco('INVESTIMENTO', 'Caixa de Investimento')
    adicionar_bloco('FINANCIAMENTO', 'Caixa de Financiamento')

    # Caixa Total
    linha_tot = {'Categoria': '**Caixa Gerado no Mês**', 'tipo':'total'}
    for m in meses:
        linha_tot[f"{meses_pt[m.month]}/{str(m.year)[2:]}"] = df_fluxo[df_fluxo['mes_ano']==m]['fluxo'].sum()
    linhas.append(linha_tot)

    df_rel = pd.DataFrame(linhas).fillna("")
    for col in colunas_meses:
        df_rel[col] = df_rel[col].apply(lambda v: formatar_brl(v) if isinstance(v,(int,float)) and v!=0 else "")

    df_show = df_rel.drop(columns=['tipo'])

    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        height=780,
        column_config={
            "Categoria": st.column_config.TextColumn("Categoria", width="large"),
            **{col: st.column_config.TextColumn(col, width="small") for col in colunas_meses}
        }
    )


# ----------------------------------------------------------
# Gráfico de Indicadores
# ----------------------------------------------------------
def criar_grafico_indicadores(df):

    st.subheader("Evolução dos Indicadores Financeiros")

    if df.empty:
        st.info("Nenhum dado disponível.")
        return

    df2 = df.copy()
    df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
    df2.dropna(subset=['data'], inplace=True)
    df2['mes_ano'] = df2['data'].dt.to_period('M')
    df2['fluxo'] = df2.apply(lambda r: r['valor'] if r['tipo_movimentacao']=="CREDITO" else -r['valor'], axis=1)
    df_fluxo = df2[df2['tipo_fluxo']!='NEUTRO']

    meses = sorted(df_fluxo['mes_ano'].unique())
    dados = []

    for m in meses:
        mdf = df_fluxo[df_fluxo['mes_ano']==m]
        entradas = mdf[(mdf['tipo_fluxo']=="OPERACIONAL") & (mdf['tipo_movimentacao']=="CREDITO")]['valor'].sum()
        op = mdf[mdf['tipo_fluxo']=="OPERACIONAL"]['fluxo'].sum()
        inv = mdf[mdf['tipo_fluxo']=="INVESTIMENTO"]['fluxo'].sum()
        fin = mdf[mdf['tipo_fluxo']=="FINANCIAMENTO"]['fluxo'].sum()
        total_deb = mdf[mdf['tipo_movimentacao']=="DEBITO"]['valor'].sum()
        retir = abs(mdf[(mdf['conta_analitica']=="FIN-05") & (mdf['tipo_movimentacao']=="DEBITO")]['valor'].sum())

        dados.append({
            "Mês": m.strftime('%m/%Y'),
            "Margem (%)": (op/entradas*100) if entradas>0 else 0,
            "Intensidade Invest (%)": (abs(inv)/op*100) if op!=0 else 0,
            "Intensidade Fin (%)": (fin/op*100) if op!=0 else 0,
            "Peso Retiradas (%)": (retir/total_deb*100) if total_deb else 0
        })

    df_ind = pd.DataFrame(dados)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_ind["Mês"], y=df_ind["Margem (%)"], mode="lines+markers", name="Margem (%)", line=dict(color=ACCENT_COLOR, width=3)))
    fig.add_trace(go.Scatter(x=df_ind["Mês"], y=df_ind["Intensidade Invest (%)"], mode="lines+markers", name="Investimento (%)", line=dict(color=INVESTMENT_COLOR, width=3)))
    fig.add_trace(go.Scatter(x=df_ind["Mês"], y=df_ind["Intensidade Fin (%)"], mode="lines+markers", name="Financiamento (%)", line=dict(color=FINANCING_COLOR, width=3)))
    fig.add_trace(go.Scatter(x=df_ind["Mês"], y=df_ind["Peso Retiradas (%)"], mode="lines+markers", name="Retiradas (%)", line=dict(color=NEGATIVE_COLOR, width=3, dash='dash')))

    fig.update_layout(height=420, plot_bgcolor="white", hovermode="x unified")

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📊 Entenda os indicadores"):
        st.markdown("""
        **Margem de Caixa Operacional** – eficiência do negócio em gerar caixa.

        **Intensidade de Investimento** – quanto do caixa está sendo reinvestido.

        **Intensidade de Financiamento** – dependência de empréstimos/aportes.

        **Peso das Retiradas** – impacto das retiradas sobre o caixa do período.
        """)


# ----------------------------------------------------------
# NOVO DASHBOARD (sem Top 5)
# ----------------------------------------------------------
def criar_dashboard(df):

    if df.empty:
        st.info("Nenhum dado disponível.")
        return

    df2 = df.copy()
    df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
    df2.dropna(subset=['data'], inplace=True)
    df2['fluxo'] = df2.apply(
        lambda row: row['valor'] if row['tipo_movimentacao']=="CREDITO" else -row['valor'],
        axis=1
    )
    df2['mes_ano_str'] = df2['data'].dt.strftime('%Y-%m')
    df_fluxo = df2[df2['tipo_fluxo']!='NEUTRO']

    # ============ Gráfico 1 – Operacional x Retiradas
    st.markdown("#### Comparativo: Caixa Operacional vs Retiradas Pessoais")

    caixa_operacional = df_fluxo[df_fluxo['tipo_fluxo']=="OPERACIONAL"]['fluxo'].sum()
    retiradas = abs(df2[(df2['conta_analitica']=="FIN-05") & (df2['tipo_movimentacao']=="DEBITO")]['valor'].sum())

    if caixa_operacional!=0 or retiradas!=0:
        df_comp = pd.DataFrame({
            "Categoria":["Caixa Operacional Gerado","Retiradas Pessoais"],
            "Valor":[caixa_operacional, retiradas]
        })
        fig1 = px.pie(
            df_comp, values="Valor", names="Categoria",
            hole=0.35,
            color="Categoria",
            color_discrete_map={
                "Caixa Operacional Gerado": ACCENT_COLOR,
                "Retiradas Pessoais": NEGATIVE_COLOR
            }
        )
        fig1.update_traces(textposition="inside", textinfo="label+percent")
        st.plotly_chart(fig1, use_container_width=True)

        if caixa_operacional <= 0:
            st.error("🚨 Caixa operacional negativo. Retiradas tornam-se insustentáveis.")
        elif retiradas > caixa_operacional:
            st.error("🚨 Retiradas maiores que o caixa gerado. Ajuste urgente.")
        elif retiradas > caixa_operacional*0.5:
            st.warning("⚠️ Más da metade do caixa operacional foi retirada.")
        elif retiradas > caixa_operacional*0.3:
            st.info("Retiradas moderadas. Acompanhe.")
        else:
            st.success("Retiradas em nível saudável.")
    else:
        st.info("Não há dados suficientes para o comparativo.")

    st.markdown("---")

    # ============ Gráfico 2 – Pizza das Saídas
    st.markdown("#### Distribuição das Saídas por Categoria")

    df_saidas = df2[df2['tipo_movimentacao']=="DEBITO"].copy()

    if not df_saidas.empty:
        df_saidas["valor_abs"] = df_saidas["valor"] * -1
        df_agr = df_saidas.groupby("conta_display")["valor_abs"].sum().reset_index()

        fig2 = px.pie(df_agr, values="valor_abs", names="conta_display", hole=0.35)
        fig2.update_traces(textposition="inside", textinfo="label+percent")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Nenhuma saída registrada.")


# ----------------------------------------------------------
# FUNÇÃO PRINCIPAL – REORGANIZADA
# ----------------------------------------------------------
def secao_relatorios_dashboard(df_transacoes, PLANO_DE_CONTAS):

    st.header("3. Relatórios Gerenciais e Dashboard")

    # --------------------------------------
    # 1) Abertura explicativa do Score
    # --------------------------------------
    st.markdown(f"""
    <div style='padding: 15px; background-color: #F9F5EB; border-radius: 10px; 
                border-left: 4px solid {ACCENT_COLOR}; font-size:15px; line-height:1.6;'>

        <h3 style='margin-top:0; color:{ACCENT_COLOR};'>O que é o Score Financeiro?</h3>
        <p>
            O <b>Score Financeiro</b> é um indicador que resume a saúde financeira do seu negócio 
            de forma simples e visual. Ele funciona como um <b>check-up do fluxo de caixa</b>:
            mostra se a empresa está gerando caixa, se os custos estão equilibrados e se as retiradas 
            dos sócios estão num nível sustentável.
        </p>

        <p>O Score avalia sete pilares importantes:</p>
        <ul>
            <li>Geração de Caixa Operacional</li>
            <li>Margem de Caixa</li>
            <li>Retiradas Pessoais</li>
            <li>Autossuficiência</li>
            <li>Reinvestimentos</li>
            <li>Crescimento das Entradas</li>
            <li>Dependência de Financiamentos</li>
        </ul>

        <p>
            Quanto mais perto de <b>100</b>, mais forte e sustentável está o negócio. 
            A seguir, você verá seu Score Financeiro e uma análise rápida com orientações práticas.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # --------------------------------------
    # 2) SCORE + ANÁLISE RÁPIDA
    # --------------------------------------
    st.markdown("### Score Financeiro e Análise Rápida")

    resultado_score = calcular_score_fluxo(df_transacoes)
    score = resultado_score["score_final"]
    indicadores = resultado_score["valores"]
    retiradas_val = indicadores.get("retiradas_pessoais", 0.0)

    html_rel, classe = gerar_mini_relatorio_local(score, indicadores, retiradas_val)

    colA, colB = st.columns([1,3])

    with colA:
        st.markdown(f"""
        <div style='text-align:center; padding: 10px; border: 2px solid {ACCENT_COLOR};
                    border-radius: 10px; background-color: #F9F5EB;'>
            <h1 style='color:{ACCENT_COLOR}; margin:0;'>{score:.1f}</h1>
            <p style='margin:0; font-weight: bold;'>Score Financeiro</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"<p style='text-align:center; font-weight:bold; margin-top:10px;'>{classe}</p>",
                    unsafe_allow_html=True)

    with colB:
        st.markdown(html_rel, unsafe_allow_html=True)

    st.markdown("---")

    # --------------------------------------
    # 3) ANÁLISE GERENCIAL
    # --------------------------------------
    st.subheader("Análise Gerencial do Caixa")
    criar_dashboard(df_transacoes)

    st.markdown("---")

    # --------------------------------------
    # 4) ANÁLISE AVANÇADA
    # --------------------------------------
    st.subheader("📊 Análise Avançada")
    st.markdown("Explore a estrutura completa do caixa e indicadores ao longo do tempo.")

    criar_grafico_indicadores(df_transacoes)
    criar_relatorio_fluxo_caixa(df_transacoes, PLANO_DE_CONTAS)

    # Detalhamento
    with st.expander("Detalhamento do Score Financeiro"):
        df_notas = pd.DataFrame({
            "Indicador": list(resultado_score["notas"].keys()),
            "Nota (0-100)": list(resultado_score["notas"].values()),
            "Peso (%)": [resultado_score["pesos"].get(k, 0) for k in resultado_score["notas"].keys()],
            "Contribuição para o Score": list(resultado_score["contribuicoes"].values())
        })
        st.dataframe(df_notas, hide_index=True)
        st.json(indicadores)

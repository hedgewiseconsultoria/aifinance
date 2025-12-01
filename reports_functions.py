# reports_functions.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
from typing import Dict, Any, List

# ---------- CORES (pegam do session_state se definido) ----------
try:
    PRIMARY_COLOR = st.session_state.get("PRIMARY_COLOR", "#0A2342")
    SECONDARY_COLOR = st.session_state.get("SECONDARY_COLOR", "#000000")
    ACCENT_COLOR = st.session_state.get("ACCENT_COLOR", "#007BFF")
    NEGATIVE_COLOR = st.session_state.get("NEGATIVE_COLOR", "#DC3545")
    FINANCING_COLOR = st.session_state.get("FINANCING_COLOR", "#FFC107")
    INVESTMENT_COLOR = st.session_state.get("INVESTMENT_COLOR", "#28A745")
except Exception:
    PRIMARY_COLOR = "#0A2342"
    SECONDARY_COLOR = "#000000"
    ACCENT_COLOR = "#007BFF"
    NEGATIVE_COLOR = "#DC3545"
    FINANCING_COLOR = "#FFC107"
    INVESTMENT_COLOR = "#28A745"


# ---------- FUNÇÃO AUX: formatar BRL ----------
def formatar_brl(valor: float) -> str:
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return "R$ " + valor_brl
    except Exception:
        try:
            return f"R$ {float(valor):,.2f}"
        except Exception:
            return "R$ 0,00"


# ---------- MINI-RELATÓRIO (Análise Rápida) ----------
def gerar_mini_relatorio_local(score: float, indicadores: Dict[str, float], retiradas_pessoais_val: float):
    """Retorna (html_text, classe_texto) para exibir análise rápida do score."""
    gco = indicadores.get("gco", 0.0)
    entradas_op = indicadores.get("entradas_operacionais", 0.0)
    autossuf = indicadores.get("autossuficiencia", 0.0)
    taxa_reinv = indicadores.get("taxa_reinvestimento", 0.0)
    peso_retiradas = indicadores.get("peso_retiradas", 0.0)

    def cor_icone(valor, tipo="financeiro", contexto_caixa_negativo=False):
        if tipo == "financeiro":
            if contexto_caixa_negativo:
                return "🔴"
            return "🟢" if valor > 0 else ("🟠" if valor == 0 else "🔴")
        if tipo == "autossuficiencia":
            if valor == float("inf") or valor > 1.0:
                return "🟢"
            elif valor >= 0.5:
                return "🟠"
            else:
                return "🔴"
        return ""

    def span_valor(valor_formatado, cor):
        return f"<span style='font-weight:700;'>{cor} {valor_formatado}</span>"

    # Resumo por score
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

    aut_text = "∞" if autossuf == float("inf") else f"{autossuf:.2f}"

    html = f"""
    <div style='line-height:1.6; font-size:15px;'>
        <b>Resumo geral:</b> {resumo}<br><br>

        <b>Caixa operacional (período):</b>
        {span_valor(formatar_brl(gco), cor_icone(gco))}<br><br>

        <b>Retiradas de sócios:</b>
        {span_valor(formatar_brl(retiradas_pessoais_val), cor_icone(retiradas_pessoais_val, contexto_caixa_negativo=(gco < 0)))} — {comentario_retiradas}<br><br>

        <b>Autossuficiência operacional:</b>
        {span_valor(aut_text, cor_icone(autossuf, "autossuficiencia"))}<br><br>

        <b>Recomendação geral:</b> Avalie periodicamente receitas, custos e retiradas para manter o caixa saudável.
    </div>
    """

    return html, classe_texto


# ---------- CLASSE: IndicadoresFluxo (mantém lógica) ----------
class IndicadoresFluxo:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._processar_df()

    def _processar_df(self):
        if self.df.empty:
            self.df_fluxo = pd.DataFrame()
            return
        # normalização básica
        if "data" in self.df.columns:
            self.df["data"] = pd.to_datetime(self.df["data"], errors="coerce", dayfirst=True)
        # garantir colunas esperadas em uppercase
        for col in ["tipo_fluxo", "tipo_movimentacao", "conta_analitica", "conta_display"]:
            if col in self.df.columns:
                try:
                    self.df[col] = self.df[col].astype(str).str.upper().str.strip()
                except Exception:
                    pass
        self.df = self.df.dropna(subset=["data"])
        self.df["mes_ano"] = self.df["data"].dt.to_period("M")
        self.df["fluxo"] = self.df.apply(
            lambda r: r["valor"] if r["tipo_movimentacao"] == "CREDITO" else -r["valor"], axis=1
        )
        self.df_fluxo = self.df[self.df["tipo_fluxo"] != "NEUTRO"].copy()

    def resumo_indicadores(self) -> Dict[str, float]:
        if self.df_fluxo.empty:
            return {
                "gco": 0.0,
                "entradas_operacionais": 0.0,
                "margem_op": 0.0,
                "autossuficiencia": 0.0,
                "taxa_reinvestimento": 0.0,
                "peso_retiradas": 0.0,
                "intensidade_fin": 0.0,
                "crescimento_entradas": 0.0,
                "retiradas_pessoais": 0.0,
            }

        caixa_op = self.df_fluxo[self.df_fluxo["tipo_fluxo"].str.contains("OPER", na=False)]["fluxo"].sum()

        entradas_op = self.df_fluxo[
            (self.df_fluxo["tipo_fluxo"].str.contains("OPER", na=False)) & (self.df_fluxo["tipo_movimentacao"] == "CREDITO")
        ]["valor"].sum()

        margem_op = (caixa_op / entradas_op) if entradas_op > 0 else 0.0

        retiradas_pessoais = abs(
            self.df[(self.df["conta_analitica"].str.contains("FIN-05|RET", na=False)) & (self.df["tipo_movimentacao"] == "DEBITO")]["valor"].sum()
        )

        total_debitos = self.df[self.df["tipo_movimentacao"] == "DEBITO"]["valor"].sum()
        peso_retiradas = (retiradas_pessoais / total_debitos) if total_debitos > 0 else 0.0

        caixa_inv = self.df_fluxo[self.df_fluxo["tipo_fluxo"].str.contains("INV", na=False)]["fluxo"].sum()
        caixa_fin = self.df_fluxo[self.df_fluxo["tipo_fluxo"].str.contains("FIN", na=False)]["fluxo"].sum()

        denominador = abs(caixa_inv) + retiradas_pessoais
        autossuf = float("inf") if denominador == 0 else (caixa_op + caixa_fin) / denominador

        taxa_reinvest = (caixa_op - retiradas_pessoais) / caixa_op if caixa_op > 0 else 0.0

        meses = sorted(self.df_fluxo["mes_ano"].unique())
        crescimento = 0.0
        if len(meses) >= 2:
            entradas_ini = self.df_fluxo[
                (self.df_fluxo["mes_ano"] == meses[0]) & (self.df_fluxo["tipo_fluxo"].str.contains("OPER", na=False)) & (self.df_fluxo["tipo_movimentacao"] == "CREDITO")
            ]["valor"].sum()
            entradas_fim = self.df_fluxo[
                (self.df_fluxo["mes_ano"] == meses[-1]) & (self.df_fluxo["tipo_fluxo"].str.contains("OPER", na=False)) & (self.df_fluxo["tipo_movimentacao"] == "CREDITO")
            ]["valor"].sum()
            if entradas_ini > 0:
                crescimento = (entradas_fim - entradas_ini) / entradas_ini

        return {
            "gco": caixa_op,
            "entradas_operacionais": entradas_op,
            "margem_op": margem_op,
            "autossuficiencia": autossuf,
            "taxa_reinvestimento": taxa_reinvest,
            "peso_retiradas": peso_retiradas,
            "intensidade_inv": caixa_inv,
            "intensidade_fin": caixa_fin,
            "crescimento_entradas": crescimento,
            "retiradas_pessoais": retiradas_pessoais,
        }


# ---------- ScoreCalculator (mantive a lógica) ----------
class ScoreCalculator:
    def __init__(self):
        self.pesos = {
            "gco": 25,
            "margem_op": 20,
            "peso_retiradas": 15,
            "autossuficiencia": 15,
            "taxa_reinvestimento": 10,
            "crescimento_entradas": 10,
            "intensidade_fin": 5,
        }

    def normalizar_gco(self, gco: float, entradas_op: float) -> float:
        if entradas_op <= 0:
            return 0.0
        margem = gco / entradas_op
        if margem >= 0.3:
            return 100.0
        elif margem >= 0.15:
            return 80.0
        elif margem > 0:
            return 60.0
        elif margem == 0:
            return 40.0
        elif margem >= -0.1:
            return 20.0
        else:
            return 0.0

    def normalizar_margem(self, margem_op: float) -> float:
        if margem_op >= 0.3:
            return 100.0
        elif margem_op >= 0.15:
            return 80.0
        elif margem_op > 0:
            return 60.0
        elif margem_op == 0:
            return 40.0
        elif margem_op >= -0.1:
            return 20.0
        else:
            return 0.0

    def normalizar_peso_retiradas(self, peso_retiradas: float) -> float:
        if peso_retiradas <= 0.1:
            return 100.0
        elif peso_retiradas <= 0.25:
            return 80.0
        elif peso_retiradas <= 0.4:
            return 60.0
        elif peso_retiradas <= 0.6:
            return 40.0
        else:
            return 20.0

    def normalizar_intensidade_fin(self, caixa_fin: float, margem_op: float) -> float:
        if margem_op > 0:
            if caixa_fin <= 0:
                return 100.0
            elif caixa_fin < 0.2 * margem_op:
                return 80.0
            else:
                return 60.0
        else:
            if caixa_fin <= 0:
                return 80.0
            elif caixa_fin < 0.5 * abs(margem_op):
                return 40.0
            else:
                return 20.0

    def normalizar_crescimento(self, crescimento: float) -> float:
        if crescimento >= 0.2:
            return 100.0
        elif crescimento >= 0.05:
            return 80.0
        elif crescimento >= 0:
            return 60.0
        else:
            return 40.0

    def normalizar_reinvestimento(self, taxa_reinv: float) -> float:
        if taxa_reinv >= 0.5:
            return 100.0
        elif taxa_reinv >= 0.3:
            return 80.0
        elif taxa_reinv >= 0.1:
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
        notas["gco"] = self.normalizar_gco(indicadores.get("gco", 0.0), indicadores.get("entradas_operacionais", 0.0))
        notas["margem_op"] = self.normalizar_margem(indicadores.get("margem_op", 0.0))
        notas["peso_retiradas"] = self.normalizar_peso_retiradas(indicadores.get("peso_retiradas", 0.0))
        notas["intensidade_fin"] = self.normalizar_intensidade_fin(indicadores.get("intensidade_fin", 0.0), indicadores.get("margem_op", 0.0))
        notas["crescimento_entradas"] = self.normalizar_crescimento(indicadores.get("crescimento_entradas", 0.0))
        notas["taxa_reinvestimento"] = self.normalizar_reinvestimento(indicadores.get("taxa_reinvestimento", 0.0))
        notas["autossuficiencia"] = self.normalizar_autossuficiencia(indicadores.get("autossuficiencia", 0.0))

        score = 0.0
        contributions = {}
        for key, peso in self.pesos.items():
            nota = notas.get(key, 0.0)
            contrib = nota * (peso / 100.0)
            contributions[key] = round(contrib, 2)
            score += contrib

        return {
            "score": round(score, 1),
            "notas": notas,
            "contribuicoes": contributions,
            "pesos": self.pesos,
        }


# ---------- Wrapper do cálculo do score ----------
def calcular_score_fluxo(df: pd.DataFrame):
    try:
        ind = IndicadoresFluxo(df)
        valores = ind.resumo_indicadores()
        sc = ScoreCalculator()
        r = sc.calcular_score(valores)
        return {
            "score_final": r["score"],
            "notas": r["notas"],
            "contribuicoes": r["contribuicoes"],
            "pesos": r["pesos"],
            "valores": valores,
            "componentes": {
                "caixa_operacional": valores.get("gco", 0.0),
                "entradas_operacionais": valores.get("entradas_operacionais", 0.0),
                "caixa_investimento": valores.get("intensidade_inv", 0.0),
                "caixa_financiamento": valores.get("intensidade_fin", 0.0),
            },
        }
    except Exception:
        return {"score_final": 0.0, "notas": {}, "contribuicoes": {}, "pesos": {}, "valores": {}}


# ---------- Relatório de Fluxo de Caixa (Tabela) ----------
def criar_relatorio_fluxo_caixa(df: pd.DataFrame, PLANO_DE_CONTAS: Dict[str, Any]):
    st.subheader("Relatório de Fluxo de Caixa")

    if df.empty:
        st.info("Nenhum dado disponível.")
        return

    # Normalizar colunas para evitar problemas de comparação
    df = df.copy()
    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
    for col in ["tipo_fluxo", "tipo_movimentacao", "conta_analitica", "conta_display"]:
        if col in df.columns:
            try:
                df[col] = df[col].astype(str).str.upper().str.strip()
            except Exception:
                pass

    df = df.dropna(subset=["data"])
    df["mes_ano"] = df["data"].dt.to_period("M")
    df["fluxo"] = df.apply(lambda r: r["valor"] if r["tipo_movimentacao"] == "CREDITO" else -r["valor"], axis=1)
    df_fluxo = df[df["tipo_fluxo"] != "NEUTRO"].copy()

    if df_fluxo.empty:
        st.info("Nenhum dado de fluxo (OPERACIONAL/INVESTIMENTO/FINANCIAMENTO) encontrado no período.")
        return

    meses = sorted(df_fluxo["mes_ano"].unique())
    meses_pt = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }

    colunas_meses = [f"{meses_pt[m.month]}/{str(m.year)[2:]}" for m in meses]

    todas_contas = df_fluxo.groupby(["tipo_fluxo", "conta_analitica", "nome_conta"]).size().reset_index()[
        ["tipo_fluxo", "conta_analitica", "nome_conta"]
    ]
    relatorio_linhas = []

    def bloco(tipo_fluxo_pattern: str, titulo: str):
        contas = todas_contas[todas_contas["tipo_fluxo"].str.contains(tipo_fluxo_pattern, na=False)].sort_values("conta_analitica")
        if contas.empty:
            return
        relatorio_linhas.append({"Categoria": f"**{titulo}**", "tipo": "header"})
        for _, conta in contas.iterrows():
            linha = {"Categoria": f"  {conta['conta_analitica']} - {conta['nome_conta']}", "tipo": "item"}
            for mes in meses:
                valor = df_fluxo[
                    (df_fluxo["mes_ano"] == mes) & (df_fluxo["conta_analitica"] == conta["conta_analitica"])
                ]["fluxo"].sum()
                mes_col = f"{meses_pt[mes.month]}/{str(mes.year)[2:]}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)

        linha_total = {"Categoria": f"**Total {titulo}**", "tipo": "total"}
        for mes in meses:
            valor = df_fluxo[
                (df_fluxo["mes_ano"] == mes) & (df_fluxo["tipo_fluxo"].str.contains(tipo_fluxo_pattern, na=False))
            ]["fluxo"].sum()
            mes_col = f"{meses_pt[mes.month]}/{str(mes.year)[2:]}"
            linha_total[mes_col] = valor
        relatorio_linhas.append(linha_total)
        relatorio_linhas.append({"Categoria": "", "tipo": "blank"})

    bloco("OPER", "ATIVIDADES OPERACIONAIS")
    bloco("INV", "ATIVIDADES DE INVESTIMENTO")
    bloco("FIN", "ATIVIDADES DE FINANCIAMENTO")

    # Caixa Gerado no mês
    linha_caixa = {"Categoria": "**CAIXA GERADO NO MÊS**", "tipo": "total"}
    for mes in meses:
        linha_caixa[f"{meses_pt[mes.month]}/{str(mes.year)[2:]}"] = df_fluxo[df_fluxo["mes_ano"] == mes]["fluxo"].sum()
    relatorio_linhas.append(linha_caixa)

    df_rel = pd.DataFrame(relatorio_linhas).fillna("")

    # Formatar valores
    for col in colunas_meses:
        if col in df_rel.columns:
            df_rel[col] = df_rel[col].apply(lambda x: formatar_brl(x) if isinstance(x, (int, float)) and x != 0 else "")

    df_display = df_rel.drop(columns=["tipo"])
    # Exibir
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=780,
        column_config={
            "Categoria": st.column_config.TextColumn("Categoria", width="large"),
            **{col: st.column_config.TextColumn(col, width="small") for col in colunas_meses}
        },
    )


# ---------- Gráfico de Indicadores ----------
def criar_grafico_indicadores(df: pd.DataFrame):
    st.subheader("Evolução dos Indicadores Financeiros")
    if df.empty:
        st.info("Nenhum dado disponível para indicadores.")
        return

    df2 = df.copy()
    if "data" in df2.columns:
        df2["data"] = pd.to_datetime(df2["data"], errors="coerce", dayfirst=True)
    for col in ["tipo_fluxo", "tipo_movimentacao", "conta_analitica", "conta_display"]:
        if col in df2.columns:
            try:
                df2[col] = df2[col].astype(str).str.upper().str.strip()
            except Exception:
                pass
    df2 = df2.dropna(subset=["data"])
    df2["mes_ano"] = df2["data"].dt.to_period("M")
    df2["fluxo"] = df2.apply(lambda r: r["valor"] if r["tipo_movimentacao"] == "CREDITO" else -r["valor"], axis=1)
    df_fluxo = df2[df2["tipo_fluxo"] != "NEUTRO"].copy()
    if df_fluxo.empty:
        st.info("Nenhum dado de fluxo para gerar indicadores.")
        return

    meses = sorted(df_fluxo["mes_ano"].unique())
    indicadores_data = []
    for mes in meses:
        df_mes = df_fluxo[df_fluxo["mes_ano"] == mes]
        caixa_op = df_mes[df_mes["tipo_fluxo"].str.contains("OPER", na=False)]["fluxo"].sum()
        caixa_inv = df_mes[df_mes["tipo_fluxo"].str.contains("INV", na=False)]["fluxo"].sum()
        caixa_fin = df_mes[df_mes["tipo_fluxo"].str.contains("FIN", na=False)]["fluxo"].sum()
        entradas_op = df_mes[(df_mes["tipo_fluxo"].str.contains("OPER", na=False)) & (df_mes["tipo_movimentacao"] == "CREDITO")]["valor"].sum()
        margem_caixa_op = (caixa_op / entradas_op * 100) if entradas_op > 0 else 0.0
        intensidade_inv = (abs(caixa_inv) / caixa_op * 100) if caixa_op != 0 else 0.0
        intensidade_fin = (caixa_fin / caixa_op * 100) if caixa_op != 0 else 0.0
        retiradas = abs(df_mes[(df_mes["conta_analitica"].str.contains("FIN-05|RET", na=False)) & (df_mes["tipo_movimentacao"] == "DEBITO")]["valor"].sum())
        total_debitos_mes = df_mes[df_mes["tipo_movimentacao"] == "DEBITO"]["valor"].sum()
        peso_retiradas = (retiradas / total_debitos_mes * 100) if total_debitos_mes != 0 else 0.0
        indicadores_data.append({
            "Mês": mes.strftime("%m/%Y"),
            "Margem de Caixa Operacional (%)": margem_caixa_op,
            "Intensidade de Investimento (%)": intensidade_inv,
            "Intensidade de Financiamento (%)": intensidade_fin,
            "Peso de Retiradas (%)": peso_retiradas,
        })

    df_ind = pd.DataFrame(indicadores_data)
    if df_ind.empty:
        st.info("Nenhum indicador computado.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_ind["Mês"], y=df_ind["Margem de Caixa Operacional (%)"], mode="lines+markers", name="Margem (%)", line=dict(color=ACCENT_COLOR, width=3)))
    fig.add_trace(go.Scatter(x=df_ind["Mês"], y=df_ind["Intensidade de Investimento (%)"], mode="lines+markers", name="Intensidade Invest (%)", line=dict(color=INVESTMENT_COLOR, width=3)))
    fig.add_trace(go.Scatter(x=df_ind["Mês"], y=df_ind["Intensidade de Financiamento (%)"], mode="lines+markers", name="Intensidade Fin (%)", line=dict(color=FINANCING_COLOR, width=3)))
    fig.add_trace(go.Scatter(x=df_ind["Mês"], y=df_ind["Peso de Retiradas (%)"], mode="lines+markers", name="Peso Retiradas (%)", line=dict(color=NEGATIVE_COLOR, width=3, dash="dash")))

    fig.update_layout(title="Evolução dos Indicadores Financeiros (%) ao longo do tempo", xaxis_title="Mês", yaxis_title="Percentual (%)", height=420, plot_bgcolor="white", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📊 Entenda os indicadores"):
        st.markdown("""
        **Margem de Caixa Operacional**: percentual do caixa operacional em relação às entradas operacionais.
        **Intensidade de Investimento**: quanto do caixa está sendo reinvestido.
        **Intensidade de Financiamento**: dependência de fontes externas (empréstimos, aportes).
        **Peso de Retiradas**: impacto das retiradas pessoais sobre as saídas do período.
        """)


# ---------- Dashboard (gráficos essenciais) ----------
def criar_dashboard(df: pd.DataFrame):
    st.subheader("Análise Gerencial do Caixa")

    if df.empty:
        st.info("Nenhum dado disponível para o dashboard.")
        return

    df2 = df.copy()
    if "data" in df2.columns:
        df2["data"] = pd.to_datetime(df2["data"], errors="coerce", dayfirst=True)
    for col in ["tipo_fluxo", "tipo_movimentacao", "conta_analitica", "conta_display"]:
        if col in df2.columns:
            try:
                df2[col] = df2[col].astype(str).str.upper().str.strip()
            except Exception:
                pass
    df2 = df2.dropna(subset=["data"])
    df2["fluxo"] = df2.apply(lambda r: r["valor"] if r["tipo_movimentacao"] == "CREDITO" else -r["valor"], axis=1)
    df2["mes_ano_str"] = df2["data"].dt.strftime("%Y-%m")
    df_fluxo = df2[df2["tipo_fluxo"] != "NEUTRO"].copy()

    # Comparativo: Caixa Operacional vs Retiradas
    caixa_operacional = df_fluxo[df_fluxo["tipo_fluxo"].str.contains("OPER", na=False)]["fluxo"].sum()
    retiradas = abs(df2[(df2["conta_analitica"].str.contains("FIN-05|RET", na=False)) & (df2["tipo_movimentacao"].str.contains("DEB", na=False))]["valor"].sum())

    if caixa_operacional != 0 or retiradas != 0:
        dados = pd.DataFrame({"Categoria": ["Caixa Operacional Gerado", "Retiradas Pessoais"], "Valor": [caixa_operacional, retiradas]})
        fig = px.pie(dados, values="Valor", names="Categoria", hole=0.35, color="Categoria", color_discrete_map={"Caixa Operacional Gerado": ACCENT_COLOR, "Retiradas Pessoais": NEGATIVE_COLOR})
        fig.update_traces(textposition="inside", textinfo="label+percent")
        st.plotly_chart(fig, use_container_width=True)

        if caixa_operacional <= 0:
            st.error("🚨 O Caixa Operacional está negativo ou zero. Retiradas não são sustentáveis.")
        elif retiradas > caixa_operacional:
            st.error("🚨 As retiradas foram maiores do que o caixa gerado. Ajuste urgente.")
        elif retiradas > caixa_operacional * 0.5:
            st.warning("⚠️ As retiradas representam mais de 50% do Caixa Operacional.")
        elif retiradas > caixa_operacional * 0.3:
            st.info("Retiradas moderadas — acompanhar mensalmente.")
        else:
            st.success("Retiradas em nível saudável.")
    else:
        st.info("Não há dados suficientes para o comparativo Caixa vs Retiradas.")

    st.markdown("---")

    # Pizza das saídas por categoria
    df_saidas = df2[df2["tipo_movimentacao"].str.contains("DEB", na=False)].copy()
    if not df_saidas.empty:
        df_saidas["valor_abs"] = df_saidas["valor"] * -1
        df_agr = df_saidas.groupby("conta_display")["valor_abs"].sum().reset_index().sort_values("valor_abs", ascending=False)
        if not df_agr.empty:
            fig2 = px.pie(df_agr, values="valor_abs", names="conta_display", hole=0.35)
            fig2.update_traces(textposition="inside", textinfo="label+percent")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Nenhuma categoria de saída encontrada.")
    else:
        st.info("Nenhuma saída (débito) registrada no período.")


# ---------- Função principal que será chamada pelo app ----------
def secao_relatorios_dashboard(df_transacoes: pd.DataFrame, PLANO_DE_CONTAS: Dict[str, Any]):
    """
    Função principal que monta a seção de Relatórios e Dashboard.
    Recebe DataFrame já enriquecido (mas fará normalização adicional).
    """

    st.header("3. Relatórios Gerenciais e Dashboard")

    # === Normalizações defensivas (importante para evitar gráficos vazios) ===
    df = df_transacoes.copy()
    if df.empty:
        st.info("Nenhum dado disponível para relatório.")
        return

    # normalizar colunas textuais (uppercase + strip)
    for col in ["tipo_fluxo", "tipo_movimentacao", "conta_analitica", "conta_display"]:
        if col in df.columns:
            try:
                df[col] = df[col].astype(str).str.upper().str.strip()
            except Exception:
                pass

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
        df = df.dropna(subset=["data"])

    # === 1) Abertura explicativa (HTML seguro) ===
    st.markdown(
        f"""
    <div style='padding: 15px; background-color: #F9F5EB; border-radius: 10px;
                border-left: 4px solid {ACCENT_COLOR}; font-size:15px; line-height:1.6;'>
        <h3 style='margin-top:0; color:{ACCENT_COLOR};'>O que é o Score Financeiro?</h3>
        <p>
            O <b>Score Financeiro</b> é um indicador que resume a saúde financeira do seu negócio 
            de forma simples e visual. Ele funciona como um <b>check-up do fluxo de caixa</b>:
            mostra se a empresa está gerando caixa, se os custos estão equilibrados e se as retiradas 
            dos sócios estão num nível sustentável. Quanto mais perto de <b>100</b>, mais forte e sustentável está o negócio. 
        </p>
            
            A seguir, você verá seu Score Financeiro e uma análise rápida com orientações práticas.
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # === 2) Score + análise rápida ===
    resultado_score = calcular_score_fluxo(df)
    score = resultado_score.get("score_final", 0.0)
    indicadores = resultado_score.get("valores", {})
    retiradas_pessoais_val = indicadores.get("retiradas_pessoais", 0.0)

    st.markdown("### Score Financeiro e Análise Rápida")

    html_relatorio, classe_texto = gerar_mini_relatorio_local(score, indicadores, retiradas_pessoais_val)

    col_score, col_resumo = st.columns([1, 3])

    with col_score:
        st.markdown(
            f"""
        <div style='text-align:center; padding: 10px; border: 2px solid {ACCENT_COLOR};
                    border-radius: 10px; background-color: #F9F5EB;'>
            <h1 style='color:{ACCENT_COLOR}; margin: 0;'>{score:.1f}</h1>
            <p style='margin: 0; font-weight: bold;'>Score Financeiro</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown(f"<p style='text-align:center; font-weight:bold; margin-top: 10px;'>{classe_texto}</p>", unsafe_allow_html=True)

    with col_resumo:
        st.markdown(html_relatorio, unsafe_allow_html=True)

    st.markdown("---")

    # === 3) Análise gerencial (gráficos essenciais) ===
    st.subheader("Análise Gerencial do Caixa")
    criar_dashboard(df)

    st.markdown("---")

    # === 4) Análise Avançada (se desejar aprofundar) ===
    st.subheader("📊 Análise Avançada")
    st.markdown("Explore a estrutura completa do caixa e a evolução dos indicadores ao longo do tempo.")

    criar_grafico_indicadores(df)
    criar_relatorio_fluxo_caixa(df, PLANO_DE_CONTAS)

    with st.expander("Detalhamento do Score Financeiro"):
        df_notas = pd.DataFrame({
            "Indicador": list(resultado_score.get("notas", {}).keys()),
            "Nota (0-100)": list(resultado_score.get("notas", {}).values()),
            "Peso (%)": [resultado_score.get("pesos", {}).get(k, 0) for k in resultado_score.get("notas", {}).keys()],
            "Contribuição para o Score": list(resultado_score.get("contribuicoes", {}).values())
        })
        st.dataframe(df_notas, hide_index=True)
        st.json(indicadores)

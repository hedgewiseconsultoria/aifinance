import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
from typing import Dict, Any, List
from datetime import datetime, timedelta
import traceback

# Variáveis de cor (assumindo que serão definidas no aicodetest.txt)
# Para evitar erros de referência, vou definir placeholders aqui, mas o código principal deve ter as corretas.
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

# --- FUNÇÃO DE FORMATAÇÃO BRL (Deve ser importada do aicodetest.txt) ---
# Assumindo que 'formatar_brl' e 'PLANO_DE_CONTAS' serão importados do arquivo principal.
# Para fins de teste e modularidade, vou incluir uma versão simples aqui.
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
    """Gera HTML limpo do mini-relatório (pronto para st.markdown com unsafe_allow_html=True),
    com linguagem simplificada e sem exibir a métrica de intensidade de financiamento.
    Retorna: (html, classe_texto)
    """
    # --- dados base ---
    gco = indicadores.get('gco', 0.0)
    entradas_op = indicadores.get('entradas_operacionais', 0.0)
    autossuf = indicadores.get('autossuficiencia', 0.0)
    taxa_reinv = indicadores.get('taxa_reinvestimento', 0.0)
    peso_retiradas = indicadores.get('peso_retiradas', 0.0)

    # --- funções auxiliares ---
    def cor_icone(valor, tipo="financeiro", contexto_caixa_negativo=False):
        """Retorna ícone colorido representando risco."""
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

    # --- resumo contextualizado (coerente com a classificação) ---
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

    # --- comentários ---
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

    # --- recomendações ---
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

    # --- formatação dos valores ---
    val_gco = span_valor(formatar_brl(gco), cor_icone(gco, "financeiro"))
    val_retir = span_valor(formatar_brl(retiradas_pessoais_val), cor_icone(retiradas_pessoais_val, "financeiro", contexto_caixa_negativo=(gco < 0)))
    aut_text = "∞" if autossuf == float('inf') else f"{autossuf:.2f}"
    val_aut = span_valor(aut_text, cor_icone(autossuf, "autossuficiencia"))

    # --- HTML final (sem classe dentro) ---
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

# --- CLASSE INDICADORES FLUXO ---
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
        # Filtrar apenas operações válidas (excluir NEUTRO)
        self.df_fluxo = self.df[self.df['tipo_fluxo'] != 'NEUTRO'].copy()

    def resumo_indicadores(self) -> Dict[str, float]:
        if self.df_fluxo.empty:
            return {
                'gco': 0.0, 'entradas_operacionais': 0.0, 'margem_op': 0.0,
                'autossuficiencia': 0.0, 'taxa_reinvestimento': 0.0,
                'peso_retiradas': 0.0, 'intensidade_fin': 0.0,
                'crescimento_entradas': 0.0, 'retiradas_pessoais': 0.0
            }

        # 1. Geração de Caixa Operacional (GCO)
        caixa_op = self.df_fluxo[self.df_fluxo['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()
        
        # 2. Entradas Operacionais (Receitas)
        entradas_op = self.df_fluxo[
            (self.df_fluxo['tipo_fluxo'] == 'OPERACIONAL') & 
            (self.df_fluxo['tipo_movimentacao'] == 'CREDITO')
        ]['valor'].sum()

        # 3. Margem de Caixa Operacional (%)
        margem_op = (caixa_op / entradas_op) if entradas_op > 0 else 0.0

        # 4. Retiradas Pessoais (FIN-05, Débito)
        retiradas_pessoais = abs(self.df[
            (self.df['conta_analitica'] == 'FIN-05') & 
            (self.df['tipo_movimentacao'] == 'DEBITO')
        ]['valor'].sum())

        # 5. Peso de Retiradas (%)
        total_debitos = self.df[self.df['tipo_movimentacao'] == 'DEBITO']['valor'].sum()
        peso_retiradas = (retiradas_pessoais / total_debitos) if total_debitos > 0 else 0.0

        # 6. Caixa de Investimento e Financiamento
        caixa_inv = self.df_fluxo[self.df_fluxo['tipo_fluxo'] == 'INVESTIMENTO']['fluxo'].sum()
        caixa_fin = self.df_fluxo[self.df_fluxo['tipo_fluxo'] == 'FINANCIAMENTO']['fluxo'].sum()

        # 7. Autossuficiência Operacional
        # (Caixa Operacional + Caixa Financiamento) / (Caixa Investimento + Retiradas)
        denominador_autossuf = abs(caixa_inv) + retiradas_pessoais
        numerador_autossuf = caixa_op + caixa_fin
        autossuficiencia = (numerador_autossuf / denominador_autossuf) if denominador_autossuf > 0 else float('inf')

        # 8. Taxa de Reinvestimento
        # Investimento / (Caixa Operacional + Financiamento)
        denominador_reinv = caixa_op + caixa_fin
        taxa_reinvestimento = (abs(caixa_inv) / denominador_reinv) if denominador_reinv > 0 else 0.0

        # 9. Intensidade de Financiamento
        intensidade_fin = (caixa_fin / abs(caixa_op)) if caixa_op != 0 else 0.0

        # 10. Crescimento das Entradas Operacionais (requer mais de um mês)
        crescimento_entradas = 0.0
        meses = sorted(self.df_fluxo['mes_ano'].unique())
        if len(meses) >= 2:
            # Agrupar entradas operacionais por mês
            entradas_mensais = self.df_fluxo[
                (self.df_fluxo['tipo_fluxo'] == 'OPERACIONAL') & 
                (self.df_fluxo['tipo_movimentacao'] == 'CREDITO')
            ].groupby('mes_ano')['valor'].sum()
            
            # Comparar o último mês com o primeiro mês
            entrada_final = entradas_mensais.iloc[-1]
            entrada_inicial = entradas_mensais.iloc[0]
            
            if entrada_inicial > 0:
                crescimento_entradas = (entrada_final - entrada_inicial) / entrada_inicial
            elif entrada_final > 0:
                crescimento_entradas = 1.0 # Crescimento de 0 para positivo é considerado alto
            else:
                crescimento_entradas = 0.0

        return {
            'gco': caixa_op,
            'entradas_operacionais': entradas_op,
            'margem_op': margem_op,
            'autossuficiencia': autossuficiencia,
            'taxa_reinvestimento': taxa_reinvestimento,
            'peso_retiradas': peso_retiradas,
            'intensidade_fin': intensidade_fin,
            'crescimento_entradas': crescimento_entradas,
            'retiradas_pessoais': retiradas_pessoais
        }

# --- CLASSE SCORE CALCULATOR ---
class ScoreCalculator:
    def __init__(self):
        # Pesos para cada indicador (soma deve ser 100)
        self.pesos = {
            'gco': 20, # Geração de Caixa Operacional (normalizado)
            'margem_op': 20, # Margem de Caixa Operacional (normalizado)
            'peso_retiradas': 15, # Peso das Retiradas (normalizado)
            'intensidade_fin': 15, # Intensidade de Financiamento (normalizado)
            'crescimento_entradas': 10, # Crescimento das Entradas (normalizado)
            'taxa_reinvestimento': 10, # Taxa de Reinvestimento (normalizado)
            'autossuficiencia': 10 # Autossuficiência Operacional (normalizado)
        }

    def normalizar_gco(self, gco: float, entradas_op: float) -> float:
        if gco > 0:
            return 100.0
        elif gco == 0:
            return 50.0
        else:
            return 0.0

    def normalizar_margem(self, margem_op: float) -> float:
        if margem_op >= 0.3:
            return 100.0
        elif margem_op >= 0.1:
            return 70.0
        elif margem_op > 0:
            return 40.0
        else:
            return 0.0

    def normalizar_peso_retiradas(self, peso_retiradas: float) -> float:
        if peso_retiradas <= 0.1:
            return 100.0
        elif peso_retiradas <= 0.3:
            return 70.0
        elif peso_retiradas <= 0.5:
            return 40.0
        else:
            return 10.0

    def normalizar_intensidade_fin(self, intensidade_fin: float, margem_op: float) -> float:
        if intensidade_fin <= 0:
            return 100.0 # Não está usando financiamento
        elif intensidade_fin <= 0.5 and margem_op >= 0.1:
            return 70.0 # Uso moderado e justificado
        elif intensidade_fin <= 1.0 and margem_op >= 0.05:
            return 40.0 # Uso alto, mas com alguma margem
        else:
            return 10.0 # Uso alto ou não justificado

    def normalizar_crescimento(self, crescimento: float) -> float:
        if crescimento >= 0.2:
            return 100.0
        elif crescimento >= 0.05:
            return 70.0
        elif crescimento >= 0:
            return 40.0
        else:
            return 10.0

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

# --- FUNÇÃO: CÁLCULO DO SCORE FINANCEIRO BASEADO EM FLUXO DE CAIXA ---
def calcular_score_fluxo(df: pd.DataFrame):
    """
    Usa IndicadoresFluxo + ScoreCalculator para retornar score e detalhes.
    """
    try:
        indicadores_calc = IndicadoresFluxo(df)
        indicadores = indicadores_calc.resumo_indicadores()
        score_calc = ScoreCalculator()
        resultado = score_calc.calcular_score(indicadores)
        
        # Complementar retorno com indicadores brutos e subscores
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
        # st.error(f"Erro no cálculo dos indicadores/score: {e}")
        # st.code(traceback.format_exc())
        return {
            'score_final': 0.0,
            'notas': {},
            'contribuicoes': {},
            'pesos': {},
            'valores': {},
            'componentes': {}
        }

# --- FUNÇÃO PARA CRIAR RELATÓRIO DE FLUXO DE CAIXA ---
def criar_relatorio_fluxo_caixa(df: pd.DataFrame, PLANO_DE_CONTAS: Dict[str, Any]):
    st.subheader("Relatório de Fluxo de Caixa (Método Direto)")
    
    if df.empty:
        st.info("Nenhum dado disponível. Por favor, processe os extratos primeiro.")
        return
    
    # Preparar dados
    df = df.copy()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df.dropna(subset=['data'], inplace=True)
    df['mes_ano'] = df['data'].dt.to_period('M')
    df['fluxo'] = df.apply(
        lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'],
        axis=1
    )
    
    # Filtrar apenas operações válidas (excluir NEUTRO)
    df_fluxo = df[df['tipo_fluxo'] != 'NEUTRO'].copy()
    
    # Obter meses únicos ordenados
    meses = sorted(df_fluxo['mes_ano'].unique())
    
    # Dicionário para mapear meses em português
    meses_pt = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    
    # Criar colunas de meses formatadas
    colunas_meses = []
    for mes in meses:
        mes_nome = meses_pt[mes.month]
        ano = mes.year % 100  # Pega apenas os 2 últimos dígitos do ano
        colunas_meses.append(f"{mes_nome}/{ano:02d}")
    
    # Coletar todas as contas únicas por tipo de fluxo
    todas_contas = df_fluxo.groupby(['tipo_fluxo', 'conta_analitica', 'nome_conta']).size().reset_index()[
        ['tipo_fluxo', 'conta_analitica', 'nome_conta']
    ]
    
    # Criar estrutura do relatório
    relatorio_linhas = []
    
    # 1. ATIVIDADES OPERACIONAIS
    relatorio_linhas.append({'Categoria': '**ATIVIDADES OPERACIONAIS**', 'tipo': 'header'})
    
    contas_op = todas_contas[todas_contas['tipo_fluxo'] == 'OPERACIONAL'].sort_values('conta_analitica')
    for _, conta in contas_op.iterrows():
        linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
        for mes in meses:
            df_mes_conta = df_fluxo[
                (df_fluxo['mes_ano'] == mes) & 
                (df_fluxo['conta_analitica'] == conta['conta_analitica'])
            ]
            valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha[mes_col] = valor
        relatorio_linhas.append(linha)
    
    # Total Operacional
    linha_total_op = {'Categoria': '**Total Caixa Operacional**', 'tipo': 'total'}
    for mes in meses:
        df_mes_op = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'OPERACIONAL')]
        valor = df_mes_op['fluxo'].sum() if not df_mes_op.empty else 0
        mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
        linha_total_op[mes_col] = valor
    relatorio_linhas.append(linha_total_op)
    relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
    # 2. ATIVIDADES DE INVESTIMENTO
    contas_inv = todas_contas[todas_contas['tipo_fluxo'] == 'INVESTIMENTO'].sort_values('conta_analitica')
    if not contas_inv.empty:
        relatorio_linhas.append({'Categoria': '**ATIVIDADES DE INVESTIMENTO**', 'tipo': 'header'})
        
        for _, conta in contas_inv.iterrows():
            linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
            for mes in meses:
                df_mes_conta = df_fluxo[
                    (df_fluxo['mes_ano'] == mes) & 
                    (df_fluxo['conta_analitica'] == conta['conta_analitica'])
                ]
                valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
                mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)
        
        # Total Investimento
        linha_total_inv = {'Categoria': '**Total Caixa de Investimento**', 'tipo': 'total'}
        for mes in meses:
            df_mes_inv = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'INVESTIMENTO')]
            valor = df_mes_inv['fluxo'].sum() if not df_mes_inv.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha_total_inv[mes_col] = valor
        relatorio_linhas.append(linha_total_inv)
        relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
    # 3. ATIVIDADES DE FINANCIAMENTO
    contas_fin = todas_contas[todas_contas['tipo_fluxo'] == 'FINANCIAMENTO'].sort_values('conta_analitica')
    if not contas_fin.empty:
        relatorio_linhas.append({'Categoria': '**ATIVIDADES DE FINANCIAMENTO**', 'tipo': 'header'})
        
        for _, conta in contas_fin.iterrows():
            linha = {'Categoria': f"  {conta['conta_analitica']} - {conta['nome_conta']}", 'tipo': 'item'}
            for mes in meses:
                df_mes_conta = df_fluxo[
                    (df_fluxo['mes_ano'] == mes) & 
                    (df_fluxo['conta_analitica'] == conta['conta_analitica'])
                ]
                valor = df_mes_conta['fluxo'].sum() if not df_mes_conta.empty else 0
                mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
                linha[mes_col] = valor
            relatorio_linhas.append(linha)
        
        # Total Financiamento
        linha_total_fin = {'Categoria': '**Total Caixa de Financiamento**', 'tipo': 'total'}
        for mes in meses:
            df_mes_fin = df_fluxo[(df_fluxo['mes_ano'] == mes) & (df_fluxo['tipo_fluxo'] == 'FINANCIAMENTO')]
            valor = df_mes_fin['fluxo'].sum() if not df_mes_fin.empty else 0
            mes_col = f"{meses_pt[mes.month]}/{mes.year % 100:02d}"
            linha_total_fin[mes_col] = valor
        relatorio_linhas.append(linha_total_fin)
        relatorio_linhas.append({'Categoria': '', 'tipo': 'blank'})
    
    # 4. CAIXA GERADO NO MÊS
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
    
    # Criar DataFrame
    df_relatorio = pd.DataFrame(relatorio_linhas)
    
    # Preencher NaN com valores vazios antes de formatar
    df_relatorio = df_relatorio.fillna('')
    
    # Formatar valores monetários
    for col in colunas_meses:
        if col in df_relatorio.columns:
            df_relatorio[col] = df_relatorio[col].apply(
                lambda x: formatar_brl(x) if isinstance(x, (int, float)) and x != 0 else ''
            )
    
    # Remover coluna 'tipo'
    df_display = df_relatorio.drop(columns=['tipo'])
    
    # Exibir tabela (altura aumentada para reduzir rolagem — cerca de 30 linhas visíveis)
    st.markdown('<div class="fluxo-table">', unsafe_allow_html=True)
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=800,
        column_config={
            "Categoria": st.column_config.TextColumn("Categoria", width="large"),
            **{col: st.column_config.TextColumn(col, width="medium") for col in colunas_meses}
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    return None

# --- FUNÇÃO PARA CRIAR GRÁFICO DE INDICADORES ---
def criar_grafico_indicadores(df: pd.DataFrame):
    """Cria gráfico com evolução dos indicadores financeiros."""
    st.subheader("Evolução dos Indicadores Financeiros")
    
    if df.empty:
        st.info("Nenhum dado disponível para indicadores.")
        return
    
    # Preparar dados
    df2 = df.copy()
    df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
    df2.dropna(subset=['data'], inplace=True)
    df2['mes_ano'] = df2['data'].dt.to_period('M')
    df2['fluxo'] = df2.apply(
        lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'],
        axis=1
    )
    
    # Filtrar apenas operações válidas (excluir NEUTRO)
    df_fluxo = df2[df2['tipo_fluxo'] != 'NEUTRO'].copy()
    
    meses = sorted(df_fluxo['mes_ano'].unique())
    indicadores_data = []
    
    for mes in meses:
        df_mes = df_fluxo[df_fluxo['mes_ano'] == mes]
        mes_str = mes.strftime('%m/%Y')
        
        # Calcular componentes
        caixa_op = df_mes[df_mes['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()
        caixa_inv = df_mes[df_mes['tipo_fluxo'] == 'INVESTIMENTO']['fluxo'].sum()
        caixa_fin = df_mes[df_mes['tipo_fluxo'] == 'FINANCIAMENTO']['fluxo'].sum()
        
        entradas_op = df_mes[
            (df_mes['tipo_fluxo'] == 'OPERACIONAL') & 
            (df_mes['tipo_movimentacao'] == 'CREDITO')
        ]['valor'].sum()
        
        # Calcular indicadores com tratamento de zero
        margem_caixa_op = (caixa_op / entradas_op * 100) if entradas_op > 0 else 0.0
        intensidade_inv = (abs(caixa_inv) / caixa_op * 100) if caixa_op != 0 else 0.0
        intensidade_fin = (caixa_fin / caixa_op * 100) if caixa_op != 0 else 0.0
        retiradas = abs(df_mes[(df_mes['conta_analitica']=='FIN-05') & (df_mes['tipo_movimentacao']=='DEBITO')]['valor'].sum())
        total_debitos_mes = df_mes[df_mes['tipo_movimentacao']=='DEBITO']['valor'].sum()
        peso_retiradas = (retiradas / total_debitos_mes * 100) if total_debitos_mes != 0 else 0.0
        
        indicadores_data.append({
            'Mês': mes_str,
            'Margem de Caixa Operacional (%)': margem_caixa_op,
            'Intensidade de Investimento (%)': intensidade_inv,
            'Intensidade de Financiamento (%)': intensidade_fin,
            'Peso de Retiradas (%)': peso_retiradas
        })
    
    df_indicadores = pd.DataFrame(indicadores_data)
    
    # Criar gráfico principal com múltiplas linhas
    fig = go.Figure()
    if not df_indicadores.empty:
        fig.add_trace(go.Scatter(
            x=df_indicadores['Mês'],
            y=df_indicadores['Margem de Caixa Operacional (%)'],
            mode='lines+markers',
            name='Margem de Caixa Operacional (%)',
            line=dict(color=ACCENT_COLOR, width=3)
        ))
        fig.add_trace(go.Scatter(
            x=df_indicadores['Mês'],
            y=df_indicadores['Intensidade de Investimento (%)'],
            mode='lines+markers',
            name='Intensidade de Investimento (%)',
            line=dict(color=INVESTMENT_COLOR, width=3)
        ))
        fig.add_trace(go.Scatter(
            x=df_indicadores['Mês'],
            y=df_indicadores['Intensidade de Financiamento (%)'],
            mode='lines+markers',
            name='Intensidade de Financiamento (%)',
            line=dict(color=FINANCING_COLOR, width=3)
        ))
        fig.add_trace(go.Scatter(
            x=df_indicadores['Mês'],
            y=df_indicadores['Peso de Retiradas (%)'],
            mode='lines+markers',
            name='Peso de Retiradas (%)',
            line=dict(color=NEGATIVE_COLOR, width=3, dash='dash')
        ))
    
    fig.update_layout(
        title='Evolução dos Indicadores Financeiros (%) ao longo do tempo',
        xaxis_title='Mês',
        yaxis_title='Percentual (%)',
        height=420,
        plot_bgcolor='white',
        font=dict(family="Roboto"),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Explicação dos indicadores
    with st.expander("📊 Entenda os indicadores"):
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

# --- FUNÇÃO PARA CRIAR DASHBOARD ---
def criar_dashboard(df: pd.DataFrame):
    """Cria dashboard com gráficos de análise."""
    st.subheader("Dashboard: Análise de Fluxo de Caixa")
    
    if df.empty:
        st.info("Nenhum dado disponível para o dashboard.")
        return

    try:
        # Preparar dados
        df2 = df.copy()
        df2['data'] = pd.to_datetime(df2['data'], errors='coerce', dayfirst=True)
        df2.dropna(subset=['data'], inplace=True)
        df2['fluxo'] = df2.apply(
            lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'],
            axis=1
        )
        df2['mes_ano_str'] = df2['data'].dt.strftime('%Y-%m')
        
        # Filtrar apenas operações válidas (excluir NEUTRO)
        df_fluxo = df2[df2['tipo_fluxo'] != 'NEUTRO'].copy()
        
        # 1. Gráfico de Barras por Tipo de Fluxo
        st.markdown("#### Fluxo de Caixa Mensal por Categoria")
        
        df_fluxo_agrupado = df_fluxo.groupby(['mes_ano_str', 'tipo_fluxo'])['fluxo'].sum().reset_index()
        
        fig_dcf = px.bar(
            df_fluxo_agrupado,
            x='mes_ano_str',
            y='fluxo',
            color='tipo_fluxo',
            barmode='group',
            title='Evolução do Fluxo de Caixa por Tipo',
            labels={'fluxo': 'Fluxo (R$)', 'mes_ano_str': 'Mês/Ano', 'tipo_fluxo': 'Tipo de Fluxo'},
            color_discrete_map={
                'OPERACIONAL': ACCENT_COLOR,
                'INVESTIMENTO': INVESTMENT_COLOR,
                'FINANCIAMENTO': FINANCING_COLOR
            }
        )
        fig_dcf.update_layout(height=400, plot_bgcolor='white', font=dict(family="Roboto"))
        st.plotly_chart(fig_dcf, use_container_width=True)
        
        st.markdown("---")

        # 2. Gráfico de Pizza: Caixa Operacional vs Retiradas Pessoais
        st.markdown("#### Comparativo: Caixa Operacional vs Retiradas Pessoais")
        
        caixa_operacional = df_fluxo[df_fluxo['tipo_fluxo'] == 'OPERACIONAL']['fluxo'].sum()
        
        # Retiradas pessoais são da conta FIN-05 e devem ser negativas (débitos)
        retiradas_pessoais = abs(df2[
            (df2['conta_analitica'] == 'FIN-05') & 
            (df2['tipo_movimentacao'] == 'DEBITO')
        ]['valor'].sum())
        
        if caixa_operacional > 0 or retiradas_pessoais > 0:
            dados_comparativo = pd.DataFrame({
                'Categoria': ['Caixa Operacional Gerado', 'Retiradas Pessoais (Sócios/Pró-labore)'],
                'Valor': [caixa_operacional, retiradas_pessoais]
            })
            
            fig_comparativo = px.pie(
                dados_comparativo,
                values='Valor',
                names='Categoria',
                title='Distribuição: Geração Operacional vs Retiradas',
                color_discrete_sequence=[ACCENT_COLOR, NEGATIVE_COLOR],
                hole=0.3
            )
            
            fig_comparativo.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>Valor: %{value:.2f}<br>Percentual: %{percent}<extra></extra>'
            )
            
            fig_comparativo.update_layout(
                height=400, 
                font=dict(family="Roboto"),
                showlegend=True
            )
            
            st.plotly_chart(fig_comparativo, use_container_width=True)
            
            # Análise contextual
            if caixa_operacional <= 0:
                st.warning("🚨 **Atenção**: O Caixa Operacional está negativo ou zero. As retiradas pessoais não são sustentáveis neste período.")
            elif retiradas_pessoais > caixa_operacional * 0.5:
                st.warning("⚠️ **Alerta**: As retiradas pessoais representam mais de 50% do Caixa Operacional gerado. Isso pode comprometer a capacidade de reinvestimento e a saúde financeira do negócio.")
            else:
                st.success("✅ **Saudável**: O Caixa Operacional gerado é suficiente para cobrir as retiradas pessoais, indicando sustentabilidade.")
        else:
            st.info("Não há dados de Caixa Operacional ou Retiradas Pessoais para o período selecionado.")

        st.markdown("---")

        # 3. Gráfico de Barras: Top 5 Contas de Débito (Saídas)
        st.markdown("#### Top 5 Contas de Débito (Saídas)")
        
        df_debitos = df2[df2['tipo_movimentacao'] == 'DEBITO'].copy()
        df_debitos_agrupado = df_debitos.groupby('conta_display')['valor'].sum().reset_index()
        df_debitos_agrupado['valor'] = df_debitos_agrupado['valor'] * -1 # Para exibir como negativo
        df_debitos_agrupado = df_debitos_agrupado.sort_values('valor', ascending=True).head(5)
        
        if not df_debitos_agrupado.empty:
            fig_top_debitos = px.bar(
                df_debitos_agrupado,
                x='valor',
                y='conta_display',
                orientation='h',
                title='Maiores Saídas (Débitos)',
                labels={'valor': 'Valor (R$)', 'conta_display': 'Conta'},
                color_discrete_sequence=[NEGATIVE_COLOR]
            )
            fig_top_debitos.update_layout(
                height=400, 
                plot_bgcolor='white', 
                font=dict(family="Roboto"),
                yaxis={'categoryorder':'total ascending'}
            )
            st.plotly_chart(fig_top_debitos, use_container_width=True)
        else:
            st.info("Nenhuma transação de débito encontrada para o período.")

        st.markdown("---")

        # 4. Gráfico de Barras: Top 5 Contas de Crédito (Entradas)
        st.markdown("#### Top 5 Contas de Crédito (Entradas)")
        
        df_creditos = df2[df2['tipo_movimentacao'] == 'CREDITO'].copy()
        df_creditos_agrupado = df_creditos.groupby('conta_display')['valor'].sum().reset_index()
        df_creditos_agrupado = df_creditos_agrupado.sort_values('valor', ascending=False).head(5)
        
        if not df_creditos_agrupado.empty:
            fig_top_creditos = px.bar(
                df_creditos_agrupado,
                x='valor',
                y='conta_display',
                orientation='h',
                title='Maiores Entradas (Créditos)',
                labels={'valor': 'Valor (R$)', 'conta_display': 'Conta'},
                color_discrete_sequence=[INVESTMENT_COLOR]
            )
            fig_top_creditos.update_layout(
                height=400, 
                plot_bgcolor='white', 
                font=dict(family="Roboto"),
                yaxis={'categoryorder':'total descending'}
            )
            st.plotly_chart(fig_top_creditos, use_container_width=True)
        else:
            st.info("Nenhuma transação de crédito encontrada para o período.")

    except Exception as e:
        st.error(f"Erro ao gerar dashboard: {e}")
        # st.code(traceback.format_exc())

# --- FUNÇÃO PRINCIPAL DA SEÇÃO 3 ---
def secao_relatorios_dashboard(df_transacoes: pd.DataFrame, PLANO_DE_CONTAS: Dict[str, Any]):
    st.header("3. Relatórios Gerenciais e Dashboard")
    
    # 1. Cálculo dos Indicadores e Score
    resultado_score = calcular_score_fluxo(df_transacoes)
    score = resultado_score['score_final']
    indicadores = resultado_score['valores']
    retiradas_pessoais_val = indicadores.get('retiradas_pessoais', 0.0)

    # 2. Mini-Relatório e Score
    st.markdown("#### Score Financeiro e Análise Rápida")
    
    html_relatorio, classe_texto = gerar_mini_relatorio_local(
        score, 
        indicadores, 
        retiradas_pessoais_val
    )
    
    col_score, col_resumo = st.columns([1, 3])
    
    with col_score:
        st.markdown(f"""
        <div style='text-align:center; padding: 10px; border: 2px solid {ACCENT_COLOR}; border-radius: 10px; background-color: #F9F5EB;'>
            <h1 style='color:{ACCENT_COLOR}; margin: 0;'>{score:.1f}</h1>
            <p style='margin: 0; font-weight: bold;'>Score Financeiro</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center; font-weight:bold; margin-top: 10px;'>{classe_texto}</p>", unsafe_allow_html=True)

    with col_resumo:
        st.markdown(html_relatorio, unsafe_allow_html=True)

    st.markdown("---")

    # 3. Dashboard
    criar_dashboard(df_transacoes)

    # 4. Gráfico de Indicadores
    criar_grafico_indicadores(df_transacoes)

    # 5. Relatório de Fluxo de Caixa (Tabela)
    criar_relatorio_fluxo_caixa(df_transacoes, PLANO_DE_CONTAS)

    st.markdown("---")
    
    # 6. Detalhes do Score (Opcional, para debug/análise avançada)
    with st.expander("Detalhes do Cálculo do Score"):
        st.markdown("#### Notas e Contribuições por Indicador")
        
        df_notas = pd.DataFrame({
            'Indicador': list(resultado_score['notas'].keys()),
            'Nota (0-100)': list(resultado_score['notas'].values()),
            'Peso (%)': [resultado_score['pesos'].get(k, 0) for k in resultado_score['notas'].keys()],
            'Contribuição para o Score': list(resultado_score['contribuicoes'].values())
        })
        
        st.dataframe(df_notas, hide_index=True)
        
        st.markdown("#### Valores Brutos dos Indicadores")
        st.json(indicadores)

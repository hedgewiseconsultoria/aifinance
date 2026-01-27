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

def formatar_brl(valor: float) -> str:
    """Formata um valor float para a moeda Real Brasileiro (R$ xx.xxx,xx)."""
    try:
        valor_us = f"{valor:,.2f}"
        valor_brl = valor_us.replace(",", "TEMP_SEP").replace(".", ",").replace("TEMP_SEP", ".")
        return "R$ " + valor_brl
    except Exception:
        return f"R$ {valor:.2f}"

# ====================================
# GAMIFICAÇÃO: BADGES E CONQUISTAS
# ====================================

def obter_badge_score(score: float) -> dict:
    """Retorna badge e mensagem motivacional baseado no score."""
    if score >= 85:
        return {
            'emoji': '🏆',
            'titulo': 'Campeão das Finanças!',
            'cor': '#FFD700',
            'mensagem': 'Parabéns! Seu negócio está no topo! Continue assim.',
            'nivel': 'OURO'
        }
    elif score >= 70:
        return {
            'emoji': '🥈',
            'titulo': 'Negócio Saudável',
            'cor': '#C0C0C0',
            'mensagem': 'Muito bem! Seu negócio está estável. Pequenos ajustes podem te levar ao ouro.',
            'nivel': 'PRATA'
        }
    elif score >= 55:
        return {
            'emoji': '🥉',
            'titulo': 'No Caminho Certo',
            'cor': '#CD7F32',
            'mensagem': 'Bom trabalho! Você está no caminho certo. Foque em melhorar o caixa.',
            'nivel': 'BRONZE'
        }
    elif score >= 40:
        return {
            'emoji': '⚠️',
            'titulo': 'Atenção Necessária',
            'cor': '#FFA500',
            'mensagem': 'Cuidado! Seu negócio precisa de atenção. Vamos trabalhar juntos para melhorar.',
            'nivel': 'ALERTA'
        }
    else:
        return {
            'emoji': '🚨',
            'titulo': 'Situação Crítica',
            'cor': '#DC3545',
            'mensagem': 'Momento de agir! Seu negócio precisa de ações urgentes. Não desanime, vamos reverter isso.',
            'nivel': 'CRÍTICO'
        }

def criar_barra_progresso_score(score: float) -> str:
    """Cria uma barra de progresso visual para o score."""
    porcentagem = min(score, 100)
    
    if score >= 85:
        cor = '#28A745'
    elif score >= 70:
        cor = '#007BFF'
    elif score >= 55:
        cor = '#FFC107'
    elif score >= 40:
        cor = '#FFA500'
    else:
        cor = '#DC3545'
    
    html = f"""
    <div style='width: 100%; background-color: #E0E0E0; border-radius: 10px; height: 30px; position: relative; margin: 15px 0;'>
        <div style='width: {porcentagem}%; background-color: {cor}; border-radius: 10px; height: 30px; transition: width 0.5s ease;'></div>
        <div style='position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-weight: bold; color: #000;'>
            {score:.1f}/100
        </div>
    </div>
    """
    return html

# ====================================
# MINI-RELATÓRIO COM STORYTELLING
# ====================================

def gerar_mini_relatorio_storytelling(score: float, indicadores: Dict[str, float], retiradas_pessoais_val: float):
    """
    Gera mini-relatório com storytelling e linguagem coloquial.
    Foca em contar a história financeira do negócio de forma acessível.
    """
    gco = indicadores.get('gco', 0.0)
    entradas_op = indicadores.get('entradas_operacionais', 0.0)
    autossuf = indicadores.get('autossuficiencia', 0.0)
    taxa_reinv = indicadores.get('taxa_reinvestimento', 0.0)
    peso_retiradas = indicadores.get('peso_retiradas', 0.0)
    
    badge = obter_badge_score(score)
    
    # História do Caixa Operacional
    if gco > 0:
        historia_caixa = f"💰 Ótima notícia! Seu negócio gerou <b>{formatar_brl(gco)}</b> de caixa operacional neste período. Isso significa que as vendas estão cobrindo os custos do dia a dia e ainda sobra dinheiro."
        emoji_caixa = "✅"
    elif gco == 0:
        historia_caixa = f"⚖️ Seu negócio está no ponto de equilíbrio - as entradas cobriram exatamente as saídas. É hora de pensar em como aumentar as vendas ou reduzir custos."
        emoji_caixa = "⚠️"
    else:
        historia_caixa = f"🚨 Atenção! Seu caixa operacional está <b>negativo em {formatar_brl(abs(gco))}</b>. Isso significa que você gastou mais do que ganhou nas operações do dia a dia."
        emoji_caixa = "❌"
    
    # História das Retiradas
    if gco < 0:
        historia_retiradas = f"🛑 Com o caixa operacional negativo, qualquer retirada pessoal está prejudicando ainda mais o negócio."
    elif retiradas_pessoais_val <= 0:
        historia_retiradas = f"👍 Você não fez retiradas pessoais neste período, o que está ajudando a fortalecer o caixa do negócio."
    else:
        percentual_ret = (retiradas_pessoais_val / max(entradas_op, 1)) * 100
        if percentual_ret < 30:
            historia_retiradas = f"✅ Suas retiradas de <b>{formatar_brl(retiradas_pessoais_val)}</b> estão em um nível saudável ({percentual_ret:.1f}% das entradas). Você está retirando o suficiente sem prejudicar o negócio."
        elif percentual_ret < 60:
            historia_retiradas = f"⚠️ Suas retiradas de <b>{formatar_brl(retiradas_pessoais_val)}</b> representam {percentual_ret:.1f}% das suas entradas. Dá pra continuar, mas fica de olho!"
        else:
            historia_retiradas = f"🚨 Cuidado! Você está retirando <b>{formatar_brl(retiradas_pessoais_val)}</b> ({percentual_ret:.1f}% das entradas). Isso é muito e pode quebrar o caixa do negócio."
    
    # História da Autossuficiência
    if autossuf == float('inf') or autossuf > 1.5:
        historia_autossuf = f"🌟 Seu negócio é super independente! Você consegue pagar tudo (retiradas e investimentos) com o dinheiro que entra das vendas."
    elif autossuf >= 1.0:
        historia_autossuf = f"👍 Seu negócio está se pagando! Você consegue cobrir as obrigações com o caixa que gera."
    elif autossuf >= 0.5:
        historia_autossuf = f"⚠️ Seu negócio está conseguindo cobrir metade das obrigações. Você ainda depende de empréstimos ou capital próprio pro resto."
    else:
        historia_autossuf = f"🚨 Seu negócio está muito dependente de dinheiro externo (empréstimos, aportes). Isso aumenta o risco!"
    
    # Dicas Práticas (linguagem coloquial)
    dicas = []
    if gco <= 0:
        dicas.append("🎯 <b>Prioridade #1:</b> Aumentar as vendas ou reduzir custos. Seu negócio precisa gerar mais caixa!")
    if peso_retiradas > 0.5 or (entradas_op > 0 and (retiradas_pessoais_val / entradas_op) > 0.5):
        dicas.append("💡 <b>Dica importante:</b> Reduza suas retiradas pessoais por enquanto. Deixe o dinheiro trabalhar no negócio.")
    if taxa_reinv >= 0.30:
        dicas.append("🚀 <b>Parabéns:</b> Você está reinvestindo no negócio! Continue assim que os resultados vão aparecer.")
    if autossuf < 0.5:
        dicas.append("⚡ <b>Meta:</b> Antes de investir mais, foque em fazer o negócio se pagar sozinho.")
    if score < 70 and gco > 0:
        dicas.append("📈 <b>Você está quase lá!</b> Com o caixa positivo, pequenos ajustes vão te levar ao próximo nível.")
    
    if not dicas:
        dicas.append("✨ <b>Continue assim!</b> Mantenha o controle e o planejamento que você está indo bem.")
    
    # Próximo Nível (gamificação)
    if score < 85:
        proximo_nivel = None
        if score >= 70:
            proximo_nivel = {'nome': 'Campeão (Ouro)', 'pontos_necessarios': 85 - score}
        elif score >= 55:
            proximo_nivel = {'nome': 'Negócio Saudável (Prata)', 'pontos_necessarios': 70 - score}
        elif score >= 40:
            proximo_nivel = {'nome': 'No Caminho Certo (Bronze)', 'pontos_necessarios': 55 - score}
        else:
            proximo_nivel = {'nome': 'Atenção Necessária', 'pontos_necessarios': 40 - score}
        
        texto_proximo = f"<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; border-radius: 10px; color: white; margin: 15px 0;'>" \
                       f"<b>🎯 Próximo Nível:</b> {proximo_nivel['nome']}<br>" \
                       f"<small>Você precisa de mais <b>{proximo_nivel['pontos_necessarios']:.1f} pontos</b> para alcançar!</small>" \
                       f"</div>"
    else:
        texto_proximo = "<div style='background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); padding: 15px; border-radius: 10px; color: #000; margin: 15px 0;'>" \
                       "<b>🏆 Você alcançou o nível máximo!</b> Mantenha essa excelência!" \
                       "</div>"
    
    # HTML final
    html = f"""
    <div style='background: white; border-radius: 15px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <div style='text-align: center; margin-bottom: 20px;'>
            <div style='font-size: 60px; margin-bottom: 10px;'>{badge['emoji']}</div>
            <h2 style='color: {badge['cor']}; margin: 10px 0;'>{badge['titulo']}</h2>
            <p style='color: #666; font-size: 16px; margin: 10px 0;'>{badge['mensagem']}</p>
        </div>
        
        <h3 style='color: {PRIMARY_COLOR}; border-bottom: 2px solid {ACCENT_COLOR}; padding-bottom: 10px; margin-top: 25px;'>
            📖 A História do Seu Negócio Neste Período
        </h3>
        
        <div style='line-height: 1.8; font-size: 15px; margin: 20px 0;'>
            <p><b>{emoji_caixa} Caixa Operacional:</b><br>{historia_caixa}</p>
            <p><b>💳 Suas Retiradas:</b><br>{historia_retiradas}</p>
            <p><b>🏢 Independência do Negócio:</b><br>{historia_autossuf}</p>
        </div>
        
        <h3 style='color: {PRIMARY_COLOR}; border-bottom: 2px solid {ACCENT_COLOR}; padding-bottom: 10px; margin-top: 25px;'>
            💡 Dicas Práticas Pra Você
        </h3>
        
        <div style='line-height: 1.8; font-size: 15px; margin: 20px 0;'>
            {"<br>".join(dicas)}
        </div>
        
        {texto_proximo}
    </div>
    """
    
    return html, badge

# ====================================
# GRÁFICOS MELHORADOS
# ====================================

def criar_grafico_top_saidas_melhorado(df: pd.DataFrame):
    """Cria gráfico de saídas com análise de vazamentos."""
    st.markdown("### 🔴 Onde Você Está Perdendo Dinheiro?")
    st.markdown("Identificar os maiores gastos é o primeiro passo para controlar o caixa.")
    
    df_debitos = df[df['tipo_movimentacao'] == 'DEBITO'].copy()
    df_debitos_agrupado = df_debitos.groupby('conta_display')['valor'].sum().reset_index()
    df_debitos_agrupado['valor_abs'] = df_debitos_agrupado['valor'].abs()
    df_debitos_agrupado = df_debitos_agrupado.sort_values('valor_abs', ascending=False).head(5)
    
    if not df_debitos_agrupado.empty:
        # Calcular percentuais
        total_saidas = df_debitos_agrupado['valor_abs'].sum()
        df_debitos_agrupado['percentual'] = (df_debitos_agrupado['valor_abs'] / total_saidas * 100).round(1)
        
        # Gráfico de barras horizontal com cores degradê
        fig = go.Figure()
        
        cores_gradiente = ['#DC3545', '#E74C3C', '#F1948A', '#FADBD8', '#F9E5E3']
        
        for idx, row in df_debitos_agrupado.iterrows():
            fig.add_trace(go.Bar(
                y=[row['conta_display']],
                x=[row['valor_abs']],
                orientation='h',
                marker=dict(color=cores_gradiente[idx % len(cores_gradiente)]),
                text=f"{formatar_brl(row['valor_abs'])} ({row['percentual']}%)",
                textposition='outside',
                hovertemplate=f"<b>{row['conta_display']}</b><br>" +
                             f"Valor: {formatar_brl(row['valor_abs'])}<br>" +
                             f"Representa {row['percentual']}% das saídas<extra></extra>",
                showlegend=False
            ))
        
        fig.update_layout(
            title=dict(
                text="Top 5 Maiores Gastos do Período",
                font=dict(size=18, color=PRIMARY_COLOR, family="Arial Black")
            ),
            xaxis_title="Valor Gasto (R$)",
            yaxis_title="",
            height=400,
            plot_bgcolor='#F9F9F9',
            paper_bgcolor='white',
            font=dict(family="Roboto", size=12),
            margin=dict(l=20, r=150, t=60, b=40)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Análise automática
        maior_gasto = df_debitos_agrupado.iloc[0]
        if maior_gasto['percentual'] > 40:
            st.warning(f"⚠️ **Atenção!** '{maior_gasto['conta_display']}' representa {maior_gasto['percentual']}% "
                      f"de todas as suas saídas ({formatar_brl(maior_gasto['valor_abs'])}). "
                      f"Esse é um ponto crítico para você revisar e tentar reduzir.")
        elif maior_gasto['percentual'] > 25:
            st.info(f"💡 Seu maior gasto é '{maior_gasto['conta_display']}' com {formatar_brl(maior_gasto['valor_abs'])} "
                   f"({maior_gasto['percentual']}%). Analise se há como otimizar esse valor.")
        else:
            st.success(f"✅ Seus gastos estão bem distribuídos! O maior é '{maior_gasto['conta_display']}' "
                      f"com {maior_gasto['percentual']}%, o que indica bom controle financeiro.")
    else:
        st.info("Não há registros de saídas para este período.")

def criar_grafico_top_entradas_melhorado(df: pd.DataFrame):
    """Cria gráfico de entradas com análise de concentração de receitas."""
    st.markdown("### 🟢 De Onde Vem o Seu Dinheiro?")
    st.markdown("Entender suas fontes de receita ajuda a planejar o crescimento do negócio.")
    
    df_creditos = df[df['tipo_movimentacao'] == 'CREDITO'].copy()
    df_creditos_agrupado = df_creditos.groupby('conta_display')['valor'].sum().reset_index()
    df_creditos_agrupado = df_creditos_agrupado.sort_values('valor', ascending=False).head(5)
    
    if not df_creditos_agrupado.empty:
        # Calcular percentuais
        total_entradas = df_creditos_agrupado['valor'].sum()
        df_creditos_agrupado['percentual'] = (df_creditos_agrupado['valor'] / total_entradas * 100).round(1)
        
        # Gráfico de barras horizontal com cores degradê
        fig = go.Figure()
        
        cores_gradiente = ['#28A745', '#48C774', '#69D391', '#8FE3AF', '#B5F3CD']
        
        for idx, row in df_creditos_agrupado.iterrows():
            fig.add_trace(go.Bar(
                y=[row['conta_display']],
                x=[row['valor']],
                orientation='h',
                marker=dict(color=cores_gradiente[idx % len(cores_gradiente)]),
                text=f"{formatar_brl(row['valor'])} ({row['percentual']}%)",
                textposition='outside',
                hovertemplate=f"<b>{row['conta_display']}</b><br>" +
                             f"Valor: {formatar_brl(row['valor'])}<br>" +
                             f"Representa {row['percentual']}% das entradas<extra></extra>",
                showlegend=False
            ))
        
        fig.update_layout(
            title=dict(
                text="Top 5 Maiores Fontes de Receita",
                font=dict(size=18, color=PRIMARY_COLOR, family="Arial Black")
            ),
            xaxis_title="Valor Recebido (R$)",
            yaxis_title="",
            height=400,
            plot_bgcolor='#F9F9F9',
            paper_bgcolor='white',
            font=dict(family="Roboto", size=12),
            margin=dict(l=20, r=150, t=60, b=40)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Análise automática de concentração
        maior_entrada = df_creditos_agrupado.iloc[0]
        if maior_entrada['percentual'] > 70:
            st.warning(f"⚠️ **Risco de Concentração!** '{maior_entrada['conta_display']}' representa "
                      f"{maior_entrada['percentual']}% de todas as suas entradas. "
                      f"Se essa fonte falhar, seu negócio pode ser muito afetado. Considere diversificar suas receitas.")
        elif maior_entrada['percentual'] > 50:
            st.info(f"💡 '{maior_entrada['conta_display']}' é sua principal fonte de receita ({maior_entrada['percentual']}%). "
                   f"É bom, mas pense em desenvolver outras fontes para reduzir riscos.")
        else:
            st.success(f"✅ Suas receitas estão bem diversificadas! '{maior_entrada['conta_display']}' "
                      f"representa {maior_entrada['percentual']}%, o que mostra resiliência do negócio.")
    else:
        st.info("Não há registros de entradas para este período.")

def criar_comparativo_caixa_retiradas_melhorado(df: pd.DataFrame):
    """Gráfico comparativo com melhor explicação."""
    st.markdown("### ⚖️ O Negócio Está Sustentando Suas Retiradas?")
    st.markdown("Este gráfico compara o dinheiro que o negócio gera com o quanto você retira dele.")
    
    # Calcular caixa operacional
    df_op = df[df['tipo_fluxo'] == 'OPERACIONAL'].copy()
    entradas_op = df_op[df_op['tipo_movimentacao'] == 'CREDITO']['valor'].sum()
    saidas_op = abs(df_op[df_op['tipo_movimentacao'] == 'DEBITO']['valor'].sum())
    caixa_operacional = entradas_op - saidas_op
    
    # Calcular retiradas
    retiradas_pessoais = abs(df[
        (df['conta_analitica'] == 'FIN-05') & 
        (df['tipo_movimentacao'] == 'DEBITO')
    ]['valor'].sum())
    
    if caixa_operacional > 0 or retiradas_pessoais > 0:
        # Criar gráfico de pizza melhorado
        dados = pd.DataFrame({
            'Categoria': ['💰 Caixa Gerado pelo Negócio', '💳 Você Retirou'],
            'Valor': [max(caixa_operacional, 0), retiradas_pessoais]
        })
        
        fig = go.Figure(data=[go.Pie(
            labels=dados['Categoria'],
            values=dados['Valor'],
            hole=0.4,
            marker=dict(colors=[ACCENT_COLOR, NEGATIVE_COLOR]),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate='<b>%{label}</b><br>Valor: %{value:,.2f}<br>Percentual: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title=dict(
                text="Geração de Caixa vs Retiradas Pessoais",
                font=dict(size=18, color=PRIMARY_COLOR, family="Arial Black")
            ),
            annotations=[dict(text=f'{formatar_brl(caixa_operacional + retiradas_pessoais)}<br>Total',
                             x=0.5, y=0.5, font_size=14, showarrow=False)],
            height=450,
            showlegend=True,
            font=dict(family="Roboto")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Análise com linguagem coloquial
        if caixa_operacional <= 0:
            st.error("🚨 **Alerta Vermelho!** Seu negócio não está gerando caixa operacional. "
                    "Qualquer retirada neste momento está 'comendo' o capital do negócio ou aumentando dívidas. "
                    "É urgente aumentar vendas ou reduzir custos!")
        elif retiradas_pessoais == 0:
            st.info(f"💡 Você gerou {formatar_brl(caixa_operacional)} e não fez retiradas. "
                   f"Isso é ótimo para fortalecer o caixa, mas lembre-se: você também precisa se pagar!")
        else:
            percentual = (retiradas_pessoais / caixa_operacional * 100)
            sobrou = caixa_operacional - retiradas_pessoais
            
            if percentual > 70:
                st.warning(f"⚠️ **Cuidado!** Você está retirando {percentual:.0f}% do caixa que gera. "
                          f"Sobram apenas {formatar_brl(sobrou)} para investir e lidar com imprevistos. "
                          f"Tente reduzir as retiradas para dar mais fôlego ao negócio.")
            elif percentual > 50:
                st.info(f"💡 Você está retirando {percentual:.0f}% do caixa gerado. "
                       f"Ainda sobram {formatar_brl(sobrou)} no negócio, mas não há muito espaço para manobra. "
                       f"Fique atento!")
            else:
                st.success(f"✅ **Excelente!** Você retira {percentual:.0f}% do caixa e deixa "
                          f"{formatar_brl(sobrou)} no negócio. Isso mostra disciplina financeira e "
                          f"permite que o negócio cresça!")
    else:
        st.info("Não há dados suficientes para gerar este comparativo.")

def criar_evolucao_fluxos_caixa(df: pd.DataFrame):
    """Gráfico de evolução dos três tipos de fluxo de caixa."""
    st.markdown("### 📊 Como Seu Dinheiro Circula no Tempo?")
    st.markdown("Acompanhe mês a mês de onde vem e para onde vai o dinheiro do negócio.")
    
    if df.empty:
        st.info("Não há dados suficientes para mostrar a evolução.")
        return
    
    df_copia = df.copy()
    df_copia['data'] = pd.to_datetime(df_copia['data'], errors='coerce')
    df_copia = df_copia.dropna(subset=['data'])
    
    if df_copia.empty:
        st.info("Não há dados com datas válidas.")
        return
    
    # Agrupar por mês e tipo de fluxo
    df_copia['mes'] = df_copia['data'].dt.to_period('M').astype(str)
    
    # Calcular saldo por tipo de fluxo
    df_copia['valor_ajustado'] = df_copia.apply(
        lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], 
        axis=1
    )
    
    resumo_mensal = df_copia.groupby(['mes', 'tipo_fluxo'])['valor_ajustado'].sum().reset_index()
    
    # Criar gráfico de linhas
    fig = go.Figure()
    
    cores_fluxo = {
        'OPERACIONAL': ACCENT_COLOR,
        'INVESTIMENTO': INVESTMENT_COLOR,
        'FINANCIAMENTO': FINANCING_COLOR,
        'NEUTRO': '#6C757D'
    }
    
    nomes_fluxo = {
        'OPERACIONAL': '💼 Operações do Dia a Dia',
        'INVESTIMENTO': '🚀 Investimentos',
        'FINANCIAMENTO': '💰 Empréstimos e Aportes',
        'NEUTRO': '↔️ Transferências'
    }
    
    for tipo_fluxo in resumo_mensal['tipo_fluxo'].unique():
        dados_fluxo = resumo_mensal[resumo_mensal['tipo_fluxo'] == tipo_fluxo]
        
        fig.add_trace(go.Scatter(
            x=dados_fluxo['mes'],
            y=dados_fluxo['valor_ajustado'],
            name=nomes_fluxo.get(tipo_fluxo, tipo_fluxo),
            mode='lines+markers',
            line=dict(color=cores_fluxo.get(tipo_fluxo, '#000000'), width=3),
            marker=dict(size=8),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                         'Mês: %{x}<br>' +
                         'Saldo: R$ %{y:,.2f}<extra></extra>'
        ))
    
    # Adicionar linha zero
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_layout(
        title=dict(
            text="Evolução Mensal dos Fluxos de Caixa",
            font=dict(size=18, color=PRIMARY_COLOR, family="Arial Black")
        ),
        xaxis_title="Mês",
        yaxis_title="Saldo (R$)",
        height=500,
        plot_bgcolor='#F9F9F9',
        paper_bgcolor='white',
        font=dict(family="Roboto"),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Análise em cards
    col1, col2, col3 = st.columns(3)
    
    # Fluxo Operacional
    fluxo_op = resumo_mensal[resumo_mensal['tipo_fluxo'] == 'OPERACIONAL']
    if not fluxo_op.empty:
        media_op = fluxo_op['valor_ajustado'].mean()
        with col1:
            cor_card = '#D4EDDA' if media_op > 0 else '#F8D7DA'
            emoji_card = '📈' if media_op > 0 else '📉'
            st.markdown(f"""
            <div style='background: {cor_card}; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid {ACCENT_COLOR};'>
                <div style='font-size: 40px;'>{emoji_card}</div>
                <h4>Operacional</h4>
                <p style='font-size: 20px; font-weight: bold; margin: 10px 0;'>{formatar_brl(media_op)}</p>
                <small>Média mensal</small>
            </div>
            """, unsafe_allow_html=True)
    
    # Fluxo de Investimento
    fluxo_inv = resumo_mensal[resumo_mensal['tipo_fluxo'] == 'INVESTIMENTO']
    if not fluxo_inv.empty:
        media_inv = fluxo_inv['valor_ajustado'].mean()
        with col2:
            emoji_inv = '🚀' if media_inv < 0 else '💵'
            texto_inv = 'Investindo' if media_inv < 0 else 'Desinvestindo'
            st.markdown(f"""
            <div style='background: #E8F5E9; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid {INVESTMENT_COLOR};'>
                <div style='font-size: 40px;'>{emoji_inv}</div>
                <h4>Investimentos</h4>
                <p style='font-size: 20px; font-weight: bold; margin: 10px 0;'>{formatar_brl(abs(media_inv))}</p>
                <small>{texto_inv}/mês</small>
            </div>
            """, unsafe_allow_html=True)
    
    # Fluxo de Financiamento
    fluxo_fin = resumo_mensal[resumo_mensal['tipo_fluxo'] == 'FINANCIAMENTO']
    if not fluxo_fin.empty:
        media_fin = fluxo_fin['valor_ajustado'].mean()
        with col3:
            emoji_fin = '💳' if media_fin > 0 else '💸'
            texto_fin = 'Captando' if media_fin > 0 else 'Pagando'
            st.markdown(f"""
            <div style='background: #FFF3CD; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid {FINANCING_COLOR};'>
                <div style='font-size: 40px;'>{emoji_fin}</div>
                <h4>Financiamentos</h4>
                <p style='font-size: 20px; font-weight: bold; margin: 10px 0;'>{formatar_brl(abs(media_fin))}</p>
                <small>{texto_fin}/mês</small>
            </div>
            """, unsafe_allow_html=True)

# ====================================
# CLASSE INDICADORES (mantida do original)
# ====================================

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

        if self.df.empty:
            self.df_fluxo = pd.DataFrame()
            return

        self.df['valor_ajustado'] = self.df.apply(
            lambda row: row['valor'] if row['tipo_movimentacao'] == 'CREDITO' else -row['valor'], axis=1
        )

        self.df_fluxo = self.df.groupby('tipo_fluxo')['valor_ajustado'].sum().reset_index()
        self.df_fluxo.columns = ['tipo_fluxo', 'saldo']

    def obter_saldo_por_tipo(self, tipo: str) -> float:
        if self.df_fluxo.empty:
            return 0.0
        linha = self.df_fluxo[self.df_fluxo['tipo_fluxo'] == tipo]
        return linha['saldo'].values[0] if not linha.empty else 0.0

    def obter_entradas_por_tipo(self, tipo: str) -> float:
        if self.df.empty:
            return 0.0
        df_tipo = self.df[self.df['tipo_fluxo'] == tipo]
        return df_tipo[df_tipo['tipo_movimentacao'] == 'CREDITO']['valor'].sum()

    def obter_saidas_por_tipo(self, tipo: str) -> float:
        if self.df.empty:
            return 0.0
        df_tipo = self.df[self.df['tipo_fluxo'] == tipo]
        return abs(df_tipo[df_tipo['tipo_movimentacao'] == 'DEBITO']['valor'].sum())

    def obter_retiradas_pessoais(self) -> float:
        if self.df.empty:
            return 0.0
        df_ret = self.df[
            (self.df['conta_analitica'] == 'FIN-05') & 
            (self.df['tipo_movimentacao'] == 'DEBITO')
        ]
        return abs(df_ret['valor'].sum())

def calcular_score_fluxo(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcula o score financeiro baseado em múltiplos indicadores."""
    ind = IndicadoresFluxo(df)
    
    gco = ind.obter_saldo_por_tipo('OPERACIONAL')
    entradas_op = ind.obter_entradas_por_tipo('OPERACIONAL')
    saidas_op = ind.obter_saidas_por_tipo('OPERACIONAL')
    
    investimentos = ind.obter_saidas_por_tipo('INVESTIMENTO')
    
    emprestimos_recebidos = ind.obter_entradas_por_tipo('FINANCIAMENTO')
    pagamentos_emprestimos = ind.obter_saidas_por_tipo('FINANCIAMENTO')
    
    retiradas_pessoais = ind.obter_retiradas_pessoais()
    
    # Indicadores
    if saidas_op > 0:
        margem_operacional = gco / saidas_op
    else:
        margem_operacional = 1.0 if gco >= 0 else -1.0
    
    total_saidas_nao_operacionais = investimentos + pagamentos_emprestimos + retiradas_pessoais
    if total_saidas_nao_operacionais > 0:
        autossuficiencia = gco / total_saidas_nao_operacionais
    else:
        autossuficiencia = float('inf') if gco > 0 else 0.0
    
    if entradas_op > 0:
        taxa_reinvestimento = investimentos / entradas_op
    else:
        taxa_reinvestimento = 0.0
    
    if emprestimos_recebidos > 0:
        cobertura_juros = gco / emprestimos_recebidos
    else:
        cobertura_juros = float('inf') if gco > 0 else 0.0
    
    if entradas_op > 0:
        peso_retiradas = retiradas_pessoais / entradas_op
    else:
        peso_retiradas = 1.0 if retiradas_pessoais > 0 else 0.0
    
    # Notas (0-100)
    nota_margem = max(0, min(100, 50 + margem_operacional * 100))
    
    if autossuficiencia == float('inf'):
        nota_autossuf = 100.0
    elif autossuficiencia >= 1.0:
        nota_autossuf = 80.0 + min(20, (autossuficiencia - 1.0) * 20)
    else:
        nota_autossuf = autossuficiencia * 80.0
    
    if taxa_reinvestimento <= 0.20:
        nota_reinv = 100.0 - (0.20 - taxa_reinvestimento) * 200
    elif taxa_reinvestimento <= 0.40:
        nota_reinv = 100.0
    else:
        nota_reinv = max(0, 100.0 - (taxa_reinvestimento - 0.40) * 100)
    
    if cobertura_juros == float('inf'):
        nota_cobertura = 100.0
    elif cobertura_juros >= 2.0:
        nota_cobertura = 100.0
    elif cobertura_juros >= 1.0:
        nota_cobertura = 50.0 + (cobertura_juros - 1.0) * 50.0
    else:
        nota_cobertura = max(0, cobertura_juros * 50.0)
    
    if peso_retiradas <= 0.30:
        nota_retiradas = 100.0
    elif peso_retiradas <= 0.60:
        nota_retiradas = 100.0 - ((peso_retiradas - 0.30) / 0.30) * 50.0
    else:
        nota_retiradas = max(0, 50.0 - ((peso_retiradas - 0.60) / 0.40) * 50.0)
    
    # Pesos
    pesos = {
        'margem_operacional': 0.30,
        'autossuficiencia': 0.25,
        'taxa_reinvestimento': 0.15,
        'cobertura_juros': 0.15,
        'peso_retiradas': 0.15
    }
    
    notas = {
        'margem_operacional': nota_margem,
        'autossuficiencia': nota_autossuf,
        'taxa_reinvestimento': nota_reinv,
        'cobertura_juros': nota_cobertura,
        'peso_retiradas': nota_retiradas
    }
    
    contribuicoes = {k: notas[k] * pesos[k] for k in notas.keys()}
    score_final = sum(contribuicoes.values())
    
    return {
        'score_final': score_final,
        'notas': notas,
        'pesos': pesos,
        'contribuicoes': contribuicoes,
        'valores': {
            'gco': gco,
            'margem_operacional': margem_operacional,
            'autossuficiencia': autossuficiencia,
            'taxa_reinvestimento': taxa_reinvestimento,
            'cobertura_juros': cobertura_juros,
            'peso_retiradas': peso_retiradas,
            'entradas_operacionais': entradas_op,
            'saidas_operacionais': saidas_op,
            'investimentos': investimentos,
            'emprestimos_recebidos': emprestimos_recebidos,
            'pagamentos_emprestimos': pagamentos_emprestimos,
            'retiradas_pessoais': retiradas_pessoais
        }
    }

def criar_relatorio_fluxo_caixa(df: pd.DataFrame, PLANO_DE_CONTAS: Dict[str, Any]):
    """Cria o relatório de fluxo de caixa em formato tabular."""
    st.markdown("### 📋 Relatório Detalhado de Fluxo de Caixa")
    st.markdown("Veja todos os movimentos organizados por tipo de atividade.")
    
    ind = IndicadoresFluxo(df)
    
    data_relatorio = []
    
    for sintetico in PLANO_DE_CONTAS.get('sinteticos', []):
        tipo_fluxo = sintetico['tipo_fluxo']
        nome_sintetico = sintetico['nome']
        
        entradas = ind.obter_entradas_por_tipo(tipo_fluxo)
        saidas = ind.obter_saidas_por_tipo(tipo_fluxo)
        saldo = ind.obter_saldo_por_tipo(tipo_fluxo)
        
        data_relatorio.append({
            'Atividade': nome_sintetico,
            'Entradas (R$)': entradas,
            'Saídas (R$)': saidas,
            'Saldo (R$)': saldo
        })
    
    df_relatorio = pd.DataFrame(data_relatorio)
    
    # Adicionar totais
    total_entradas = df_relatorio['Entradas (R$)'].sum()
    total_saidas = df_relatorio['Saídas (R$)'].sum()
    total_saldo = df_relatorio['Saldo (R$)'].sum()
    
    df_relatorio.loc[len(df_relatorio)] = {
        'Atividade': 'TOTAL',
        'Entradas (R$)': total_entradas,
        'Saídas (R$)': total_saidas,
        'Saldo (R$)': total_saldo
    }
    
    # Formatar valores
    df_relatorio['Entradas (R$)'] = df_relatorio['Entradas (R$)'].apply(formatar_brl)
    df_relatorio['Saídas (R$)'] = df_relatorio['Saídas (R$)'].apply(formatar_brl)
    df_relatorio['Saldo (R$)'] = df_relatorio['Saldo (R$)'].apply(formatar_brl)
    
    st.dataframe(df_relatorio, hide_index=True, use_container_width=True)
    
    # Insights
    if total_saldo > 0:
        st.success(f"✅ Seu saldo total no período foi positivo: {formatar_brl(total_saldo)}. O negócio aumentou o caixa!")
    elif total_saldo < 0:
        st.error(f"🚨 Seu saldo total no período foi negativo: {formatar_brl(abs(total_saldo))}. O caixa diminuiu!")
    else:
        st.info("⚖️ Seu saldo ficou neutro - entradas e saídas se equilibraram.")

# ====================================
# FUNÇÃO PRINCIPAL (NOVA)
# ====================================

def secao_relatorios_dashboard(df_transacoes: pd.DataFrame, PLANO_DE_CONTAS: Dict[str, Any]):
    """Função principal que monta o dashboard completo com storytelling."""
    
    st.markdown("""
    <style>
        .metric-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
            border: 2px solid #E0E0E0;
        }
        .section-divider {
            margin: 40px 0;
            border-bottom: 3px solid #0A2342;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("# 📊 Painel Financeiro do Seu Negócio")
    st.markdown("Aqui você tem uma visão completa da saúde financeira da sua empresa, com linguagem simples e dicas práticas!")
    
    # ====================================
    # 1. SCORE E ANÁLISE PRINCIPAL
    # ====================================
    
    resultado_score = calcular_score_fluxo(df_transacoes)
    score = resultado_score['score_final']
    indicadores = resultado_score['valores']
    retiradas_pessoais_val = indicadores.get('retiradas_pessoais', 0.0)
    
    html_relatorio, badge = gerar_mini_relatorio_storytelling(score, indicadores, retiradas_pessoais_val)
    
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.markdown("## 🏅 Seu Score Financeiro")
    
    col_score, col_analise = st.columns([1, 2])
    
    with col_score:
        # Badge visual
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, {badge['cor']} 0%, {PRIMARY_COLOR} 100%); 
                    padding: 30px; border-radius: 20px; text-align: center; color: white; box-shadow: 0 8px 16px rgba(0,0,0,0.2);'>
            <div style='font-size: 80px; margin-bottom: 10px;'>{badge['emoji']}</div>
            <h1 style='margin: 10px 0; font-size: 48px;'>{score:.0f}</h1>
            <p style='font-size: 18px; margin: 0;'>de 100 pontos</p>
            <p style='font-size: 16px; margin-top: 15px; font-weight: bold;'>{badge['nivel']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Barra de progresso
        st.markdown(criar_barra_progresso_score(score), unsafe_allow_html=True)
    
    with col_analise:
        st.markdown(html_relatorio, unsafe_allow_html=True)
    
    # ====================================
    # 2. EVOLUÇÃO DOS FLUXOS DE CAIXA
    # ====================================
    
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    criar_evolucao_fluxos_caixa(df_transacoes)
    
    # ====================================
    # 3. ANÁLISE DE SAÍDAS E ENTRADAS
    # ====================================
    
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    
    col_saidas, col_entradas = st.columns(2)
    
    with col_saidas:
        criar_grafico_top_saidas_melhorado(df_transacoes)
    
    with col_entradas:
        criar_grafico_top_entradas_melhorado(df_transacoes)
    
    # ====================================
    # 4. COMPARATIVO CAIXA VS RETIRADAS
    # ====================================
    
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    criar_comparativo_caixa_retiradas_melhorado(df_transacoes)
    
    # ====================================
    # 5. RELATÓRIO DETALHADO
    # ====================================
    
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    criar_relatorio_fluxo_caixa(df_transacoes, PLANO_DE_CONTAS)
    
    # ====================================
    # 6. DETALHES TÉCNICOS (EXPANDIDO)
    # ====================================
    
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    
    with st.expander("🔍 Detalhes Técnicos do Cálculo (Para Curiosos)"):
        st.markdown("### Como calculamos seu score?")
        st.markdown("Seu score é composto por 5 indicadores financeiros, cada um com um peso diferente:")
        
        df_notas = pd.DataFrame({
            'Indicador': [
                '💼 Margem Operacional',
                '🏢 Autossuficiência',
                '🚀 Taxa de Reinvestimento',
                '💰 Cobertura de Juros',
                '💳 Controle de Retiradas'
            ],
            'Nota (0-100)': [
                resultado_score['notas']['margem_operacional'],
                resultado_score['notas']['autossuficiencia'],
                resultado_score['notas']['taxa_reinvestimento'],
                resultado_score['notas']['cobertura_juros'],
                resultado_score['notas']['peso_retiradas']
            ],
            'Peso': [
                '30%',
                '25%',
                '15%',
                '15%',
                '15%'
            ],
            'Contribuição': [
                f"{resultado_score['contribuicoes']['margem_operacional']:.1f}",
                f"{resultado_score['contribuicoes']['autossuficiencia']:.1f}",
                f"{resultado_score['contribuicoes']['taxa_reinvestimento']:.1f}",
                f"{resultado_score['contribuicoes']['cobertura_juros']:.1f}",
                f"{resultado_score['contribuicoes']['peso_retiradas']:.1f}"
            ]
        })
        
        st.dataframe(df_notas, hide_index=True, use_container_width=True)
        
        st.markdown("### Valores Brutos Calculados")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Caixa Operacional", formatar_brl(indicadores['gco']))
            st.metric("Entradas Operacionais", formatar_brl(indicadores['entradas_operacionais']))
        
        with col2:
            st.metric("Saídas Operacionais", formatar_brl(indicadores['saidas_operacionais']))
            st.metric("Investimentos", formatar_brl(indicadores['investimentos']))
        
        with col3:
            st.metric("Retiradas Pessoais", formatar_brl(indicadores['retiradas_pessoais']))
            st.metric("Empréstimos Recebidos", formatar_brl(indicadores['emprestimos_recebidos']))

"""
relatorios.py — Análises (Pandas) e gráficos (Matplotlib) do EstoqueFácil.

Conteúdo da disciplina aplicado neste arquivo:
  - DataFrames (Pandas): filtros, agrupamentos (groupby), tabela dinâmica e somas.
  - Gráficos (Matplotlib): barras horizontais e verticais com dados reais do banco.

Observação técnica: usamos matplotlib.figure.Figure diretamente (sem pyplot),
que é a forma recomendada para aplicações web: não abre janelas nem acumula
figuras na memória.
"""

from datetime import datetime

import pandas as pd
from matplotlib.figure import Figure

from database import ErroDeNegocio, buscar_produtos, consultar

COR_PRINCIPAL = "#2563eb"
COR_SECUNDARIA = "#16a34a"


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
def _figura_vazia(titulo, mensagem="Ainda não há dados para exibir."):
    """Figura com aviso, usada quando não existem dados cadastrados."""
    figura = Figure(figsize=(7, 4))
    eixo = figura.subplots()
    eixo.set_title(titulo, fontweight="bold")
    eixo.text(0.5, 0.5, mensagem, ha="center", va="center", fontsize=12, color="gray")
    eixo.set_axis_off()
    return figura


def _grafico_barras_horizontais(df, coluna_rotulo, coluna_valor, titulo, rotulo_x, cor):
    """Monta um gráfico de barras horizontais (maior valor no topo)."""
    df = df.sort_values(coluna_valor, ascending=True)  # no eixo Y, o último fica no topo
    figura = Figure(figsize=(7, 4.5))
    eixo = figura.subplots()
    barras = eixo.barh(df[coluna_rotulo], df[coluna_valor], color=cor)
    eixo.bar_label(barras, padding=3)  # escreve o valor na ponta de cada barra
    eixo.set_title(titulo, fontweight="bold")
    eixo.set_xlabel(rotulo_x)
    eixo.spines[["top", "right"]].set_visible(False)
    eixo.margins(x=0.12)
    figura.tight_layout()
    return figura


# ---------------------------------------------------------------------------
# Gráfico 1 — produtos com maior estoque
# ---------------------------------------------------------------------------
def grafico_maior_estoque(quantidade_produtos=10):
    titulo = "Produtos com maior quantidade em estoque"
    produtos = buscar_produtos()
    produtos = produtos[produtos["quantidade"] > 0]
    if produtos.empty:
        return _figura_vazia(titulo, "Nenhum produto com estoque disponível.")
    maiores = produtos.nlargest(quantidade_produtos, "quantidade")
    return _grafico_barras_horizontais(
        maiores, "nome", "quantidade", titulo, "Unidades em estoque", COR_PRINCIPAL
    )


# ---------------------------------------------------------------------------
# Gráfico 2 — produtos mais vendidos
# ---------------------------------------------------------------------------
def tabela_mais_vendidos():
    """Soma as unidades vendidas por produto (apenas pedidos CONFIRMADOS)."""
    itens = consultar(
        """SELECT i.produto_id, p.nome, i.quantidade, i.preco_unitario
           FROM itens_pedido i
           JOIN pedidos pe ON pe.id = i.pedido_id
           JOIN produtos p ON p.id = i.produto_id
           WHERE pe.status = 'Confirmado'"""
    )
    if itens.empty:
        return pd.DataFrame(columns=["nome", "unidades", "receita"])
    itens["receita"] = itens["quantidade"] * itens["preco_unitario"]
    vendas = (
        itens.groupby(["produto_id", "nome"], as_index=False)
        .agg(unidades=("quantidade", "sum"), receita=("receita", "sum"))
        .sort_values("unidades", ascending=False)
        .reset_index(drop=True)
    )
    vendas["receita"] = vendas["receita"].round(2)
    return vendas.drop(columns="produto_id")


def grafico_mais_vendidos(quantidade_produtos=10):
    titulo = "Produtos mais vendidos (pedidos confirmados)"
    vendas = tabela_mais_vendidos()
    if vendas.empty:
        return _figura_vazia(titulo, "Nenhum pedido confirmado ainda.")
    return _grafico_barras_horizontais(
        vendas.head(quantidade_produtos), "nome", "unidades", titulo,
        "Unidades vendidas", COR_SECUNDARIA,
    )


# ---------------------------------------------------------------------------
# Relatório de pedidos por período
# ---------------------------------------------------------------------------
def _ler_data(texto, campo):
    """Aceita 31/12/2025 ou 2025-12-31."""
    texto = (texto or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    raise ErroDeNegocio(f"{campo} inválida. Use o formato DD/MM/AAAA (ex.: 31/12/2025).")


def relatorio_pedidos_periodo(data_inicio, data_fim):
    """
    Retorna (tabela, figura, resumo) dos pedidos criados entre as duas datas.
    A tabela traz, por dia: quantidade de pedidos por status e valor confirmado.
    """
    inicio = _ler_data(data_inicio, "Data inicial")
    fim = _ler_data(data_fim, "Data final")
    if inicio > fim:
        raise ErroDeNegocio("A data inicial não pode ser maior que a data final.")

    pedidos = consultar(
        """SELECT id, status, valor_total, data_criacao
           FROM pedidos
           WHERE data_criacao >= ? AND data_criacao <= ?
           ORDER BY data_criacao""",
        (inicio.strftime("%Y-%m-%d 00:00:00"), fim.strftime("%Y-%m-%d 23:59:59")),
    )

    colunas = ["Data", "Pedidos", "Confirmados", "Pendentes", "Cancelados", "Valor confirmado (R$)"]
    titulo = "Valor dos pedidos confirmados por dia"
    if pedidos.empty:
        return (
            pd.DataFrame(columns=colunas),
            _figura_vazia(titulo, "Nenhum pedido no período selecionado."),
            "Nenhum pedido encontrado no período.",
        )

    pedidos["dia"] = pd.to_datetime(pedidos["data_criacao"]).dt.date

    # Tabela dinâmica: linhas = dia, colunas = status, valores = contagem de pedidos
    contagem = pedidos.pivot_table(
        index="dia", columns="status", values="id", aggfunc="count", fill_value=0
    ).reindex(columns=["Confirmado", "Pendente", "Cancelado"], fill_value=0)

    # Soma do valor apenas dos pedidos confirmados em cada dia
    valor_por_dia = (
        pedidos[pedidos["status"] == "Confirmado"].groupby("dia")["valor_total"].sum()
    )

    tabela = pd.DataFrame(
        {
            "Pedidos": contagem.sum(axis=1),
            "Confirmados": contagem["Confirmado"],
            "Pendentes": contagem["Pendente"],
            "Cancelados": contagem["Cancelado"],
            "Valor confirmado (R$)": valor_por_dia.reindex(contagem.index, fill_value=0.0).round(2),
        }
    ).reset_index()
    tabela["Data"] = pd.to_datetime(tabela["dia"]).dt.strftime("%d/%m/%Y")
    tabela = tabela[colunas]

    # Gráfico de barras verticais
    figura = Figure(figsize=(7, 4))
    eixo = figura.subplots()
    barras = eixo.bar(tabela["Data"], tabela["Valor confirmado (R$)"], color=COR_PRINCIPAL)
    eixo.bar_label(barras, fmt="%.0f", padding=2, fontsize=8)
    eixo.set_title(titulo, fontweight="bold")
    eixo.set_ylabel("Valor (R$)")
    eixo.tick_params(axis="x", rotation=45, labelsize=8)
    eixo.spines[["top", "right"]].set_visible(False)
    figura.tight_layout()

    total_confirmado = float(tabela["Valor confirmado (R$)"].sum())
    valor_texto = f"{total_confirmado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    resumo = (
        f"{int(tabela['Pedidos'].sum())} pedido(s) no período — "
        f"{int(tabela['Confirmados'].sum())} confirmado(s), "
        f"{int(tabela['Pendentes'].sum())} pendente(s), "
        f"{int(tabela['Cancelados'].sum())} cancelado(s). "
        f"Valor confirmado: R$ {valor_texto}"
    )
    return tabela, figura, resumo

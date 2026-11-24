"""
dados_demo.py — Carrega dados FICTÍCIOS para demonstração (produtos, pedidos e movimentações).

Usa as mesmas funções do sistema (cadastrar_produto, criar_pedido, confirmar_pedido...),
então as regras de estoque são as mesmas do uso real. Só funciona com o banco vazio.
"""

from datetime import datetime, timedelta

from database import (
    ErroDeNegocio,
    buscar_produtos,
    cadastrar_produto,
    cancelar_pedido,
    confirmar_pedido,
    criar_pedido,
    transacao,
)

# (código, nome, categoria, preço, quantidade inicial, estoque mínimo)
PRODUTOS_DEMO = [
    ("P001", "Arroz 5kg", "Alimentos", 28.90, 40, 10),
    ("P002", "Feijão 1kg", "Alimentos", 8.50, 35, 10),
    ("P003", "Macarrão 500g", "Alimentos", 5.20, 60, 15),
    ("P004", "Café 500g", "Alimentos", 16.90, 8, 10),
    ("P005", "Refrigerante 2L", "Bebidas", 9.50, 24, 12),
    ("P006", "Suco de Uva 1L", "Bebidas", 7.80, 5, 8),
    ("P007", "Água Mineral 500ml", "Bebidas", 2.50, 100, 30),
    ("P008", "Detergente 500ml", "Limpeza", 2.99, 50, 20),
    ("P009", "Sabão em Pó 1kg", "Limpeza", 14.50, 18, 10),
    ("P010", "Shampoo 350ml", "Higiene", 12.90, 22, 8),
    ("P011", "Caderno 96 folhas", "Papelaria", 15.00, 30, 10),
    ("P012", "Caneta Azul", "Papelaria", 2.00, 0, 20),
]

# (dias atrás, cliente fictício, [(código, quantidade), ...], situação final)
PEDIDOS_DEMO = [
    (20, "Maria (demo)", [("P001", 2), ("P002", 3), ("P003", 4)], "Confirmado"),
    (18, "João (demo)", [("P007", 12), ("P005", 3)], "Confirmado"),
    (15, "Ana (demo)", [("P008", 4), ("P009", 2), ("P010", 1)], "Confirmado"),
    (12, "Carlos (demo)", [("P001", 3), ("P004", 2), ("P007", 6)], "Confirmado"),
    (9, "Fernanda (demo)", [("P011", 5), ("P005", 2)], "Confirmado"),
    (6, "Pedro (demo)", [("P003", 10), ("P002", 5), ("P001", 1)], "Confirmado"),
    (3, "Luciana (demo)", [("P007", 10), ("P006", 2), ("P004", 1)], "Confirmado"),
    (1, "Rafael (demo)", [("P009", 3), ("P008", 6)], "Confirmado"),
    (2, "Cliente cancelou (demo)", [("P001", 5)], "Cancelado"),
    (0, "Pedido aberto (demo)", [("P005", 4), ("P010", 2)], "Pendente"),
]


def _ajustar_datas(pedido_id, dias_atras):
    """Espalha as datas dos pedidos pelos últimos dias, para os relatórios ficarem interessantes."""
    data = (datetime.now() - timedelta(days=dias_atras)).replace(hour=10 + pedido_id % 8, minute=0, second=0)
    texto = data.strftime("%Y-%m-%d %H:%M:%S")
    with transacao() as conexao:
        conexao.execute(
            "UPDATE pedidos SET data_criacao = ?, data_atualizacao = ? WHERE id = ?",
            (texto, texto, pedido_id),
        )
        conexao.execute("UPDATE movimentacoes SET data = ? WHERE pedido_id = ?", (texto, pedido_id))


def carregar_dados_demonstracao():
    """Cadastra produtos e pedidos fictícios. Retorna um texto resumindo o que foi criado."""
    if not buscar_produtos().empty:
        raise ErroDeNegocio(
            "Os dados de demonstração só podem ser carregados quando não há produtos cadastrados."
        )

    ids = {}
    for codigo, nome, categoria, preco, quantidade, minimo in PRODUTOS_DEMO:
        ids[codigo] = cadastrar_produto(codigo, nome, categoria, preco, quantidade, minimo)

    # O estoque inicial foi "registrado" 25 dias atrás
    antigo = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d 09:00:00")
    with transacao() as conexao:
        conexao.execute("UPDATE movimentacoes SET data = ? WHERE pedido_id IS NULL", (antigo,))

    for dias_atras, cliente, itens, situacao in PEDIDOS_DEMO:
        itens_ids = [{"produto_id": ids[codigo], "quantidade": qtd} for codigo, qtd in itens]
        pedido_id = criar_pedido(cliente, itens_ids)
        if situacao in ("Confirmado", "Cancelado"):
            confirmar_pedido(pedido_id)
        if situacao == "Cancelado":
            cancelar_pedido(pedido_id)
        _ajustar_datas(pedido_id, dias_atras)

    return f"{len(PRODUTOS_DEMO)} produtos e {len(PEDIDOS_DEMO)} pedidos fictícios carregados."

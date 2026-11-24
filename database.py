"""
database.py — Camada de banco de dados do EstoqueFácil (SQLite + Pandas).

Aqui ficam TODAS as regras de negócio que mexem em produtos, estoque e pedidos.
A interface (app.py) apenas chama estas funções.

Conteúdo da disciplina aplicado neste arquivo:
  - Banco de dados: tabelas, chaves estrangeiras, consultas parametrizadas e transações.
  - DataFrames (Pandas): consultas de leitura retornam DataFrames prontos para análise.
"""

import math
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

# O arquivo do banco fica na mesma pasta do projeto e é criado automaticamente.
CAMINHO_BANCO = Path(__file__).parent / "estoquefacil.db"

STATUS_PEDIDO = ("Pendente", "Confirmado", "Cancelado")


class ErroDeNegocio(Exception):
    """Erro esperado (ex.: estoque insuficiente). A mensagem é mostrada ao usuário."""


# ---------------------------------------------------------------------------
# Conexão e transações
# ---------------------------------------------------------------------------
def agora():
    """Data/hora atual no formato texto aceito pelo SQLite."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def conectar():
    """Abre uma conexão com o SQLite (com chaves estrangeiras ativadas)."""
    conexao = sqlite3.connect(CAMINHO_BANCO, timeout=10, isolation_level=None)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


@contextmanager
def transacao():
    """
    Executa um bloco de comandos como uma TRANSAÇÃO.
    Se tudo der certo -> COMMIT (salva tudo).
    Se qualquer erro acontecer -> ROLLBACK (desfaz tudo, nada fica pela metade).
    O BEGIN IMMEDIATE trava o banco para escrita, evitando duas alterações
    simultâneas no mesmo estoque.
    """
    conexao = conectar()
    try:
        conexao.execute("BEGIN IMMEDIATE")
        yield conexao
        conexao.execute("COMMIT")
    except Exception:
        if conexao.in_transaction:
            conexao.execute("ROLLBACK")
        raise
    finally:
        conexao.close()


def consultar(sql, parametros=()):
    """Executa um SELECT (parametrizado) e devolve o resultado como DataFrame."""
    with closing(conectar()) as conexao:
        return pd.read_sql_query(sql, conexao, params=parametros)


def criar_banco():
    """Cria as tabelas na primeira execução (se ainda não existirem)."""
    with closing(conectar()) as conexao:
        conexao.executescript(
            """
            CREATE TABLE IF NOT EXISTS produtos (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo         TEXT    NOT NULL UNIQUE,
                nome           TEXT    NOT NULL,
                categoria      TEXT    NOT NULL,
                preco          REAL    NOT NULL CHECK (preco >= 0),
                quantidade     INTEGER NOT NULL DEFAULT 0 CHECK (quantidade >= 0),
                estoque_minimo INTEGER NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0)
            );

            CREATE TABLE IF NOT EXISTS pedidos (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente           TEXT NOT NULL,
                status            TEXT NOT NULL DEFAULT 'Pendente'
                                  CHECK (status IN ('Pendente', 'Confirmado', 'Cancelado')),
                valor_total       REAL NOT NULL DEFAULT 0,
                data_criacao      TEXT NOT NULL,
                data_atualizacao  TEXT
            );

            CREATE TABLE IF NOT EXISTS itens_pedido (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id       INTEGER NOT NULL
                                REFERENCES pedidos (id) ON DELETE CASCADE,
                produto_id      INTEGER NOT NULL
                                REFERENCES produtos (id) ON DELETE RESTRICT,
                quantidade      INTEGER NOT NULL CHECK (quantidade > 0),
                preco_unitario  REAL    NOT NULL CHECK (preco_unitario >= 0)
            );

            CREATE TABLE IF NOT EXISTS movimentacoes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id  INTEGER NOT NULL
                            REFERENCES produtos (id) ON DELETE CASCADE,
                tipo        TEXT    NOT NULL CHECK (tipo IN ('Entrada', 'Saída')),
                quantidade  INTEGER NOT NULL CHECK (quantidade > 0),
                motivo      TEXT,
                pedido_id   INTEGER REFERENCES pedidos (id) ON DELETE SET NULL,
                data        TEXT    NOT NULL
            );
            """
        )


# ---------------------------------------------------------------------------
# Validações (funções pequenas e reutilizáveis)
# ---------------------------------------------------------------------------
def _texto_obrigatorio(valor, campo, tamanho_maximo=100):
    texto = (valor or "").strip()
    if not texto:
        raise ErroDeNegocio(f"O campo '{campo}' é obrigatório. Preencha-o para continuar.")
    if len(texto) > tamanho_maximo:
        raise ErroDeNegocio(f"O campo '{campo}' aceita no máximo {tamanho_maximo} caracteres.")
    return texto


def numero_inteiro(valor, campo, minimo=0):
    """Garante um número inteiro maior ou igual a 'minimo'."""
    if valor is None or valor == "":
        raise ErroDeNegocio(f"Informe um valor para '{campo}'.")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroDeNegocio(f"'{campo}' deve ser um número.")
    if not math.isfinite(numero) or numero != int(numero):
        raise ErroDeNegocio(f"'{campo}' deve ser um número inteiro, sem casas decimais (exemplo: 3).")
    numero = int(numero)
    if numero < minimo:
        raise ErroDeNegocio(f"'{campo}' deve ser maior ou igual a {minimo}.")
    return numero


def _preco_valido(valor):
    if valor is None or valor == "":
        raise ErroDeNegocio("Informe o preço de venda.")
    try:
        preco = float(valor)
    except (TypeError, ValueError):
        raise ErroDeNegocio("O preço deve ser um número.")
    if not math.isfinite(preco) or preco < 0:
        raise ErroDeNegocio("O preço não pode ser negativo. Digite 0 ou um valor positivo (exemplo: 5.50).")
    return round(preco, 2)


def _validar_produto(codigo, nome, categoria, preco, estoque_minimo):
    """Valida e limpa os dados comuns de cadastro e edição."""
    codigo = _texto_obrigatorio(codigo, "Código", 30).upper()
    nome = _texto_obrigatorio(nome, "Nome")
    categoria = _texto_obrigatorio(categoria, "Categoria", 50)
    preco = _preco_valido(preco)
    estoque_minimo = numero_inteiro(estoque_minimo, "Estoque mínimo", 0)
    return codigo, nome, categoria, preco, estoque_minimo


# ---------------------------------------------------------------------------
# Produtos
# ---------------------------------------------------------------------------
def _buscar_produto_ou_erro(conexao, produto_id):
    linha = conexao.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    if linha is None:
        raise ErroDeNegocio("Produto não encontrado. Atualize a tela e tente novamente.")
    return linha


def _codigo_ja_existe(conexao, codigo, ignorar_id=None):
    linha = conexao.execute(
        "SELECT id FROM produtos WHERE codigo = ? AND id != ?",
        (codigo, ignorar_id or -1),
    ).fetchone()
    return linha is not None


def cadastrar_produto(codigo, nome, categoria, preco, quantidade, estoque_minimo):
    """Cadastra um produto. Se a quantidade inicial for > 0, registra uma entrada."""
    codigo, nome, categoria, preco, estoque_minimo = _validar_produto(
        codigo, nome, categoria, preco, estoque_minimo
    )
    quantidade = numero_inteiro(quantidade, "Quantidade em estoque", 0)

    with transacao() as conexao:
        if _codigo_ja_existe(conexao, codigo):
            raise ErroDeNegocio(f"Já existe um produto com o código '{codigo}'. Use outro código ou edite o produto existente.")
        cursor = conexao.execute(
            """INSERT INTO produtos (codigo, nome, categoria, preco, quantidade, estoque_minimo)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (codigo, nome, categoria, preco, quantidade, estoque_minimo),
        )
        produto_id = cursor.lastrowid
        if quantidade > 0:
            conexao.execute(
                """INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo, data)
                   VALUES (?, 'Entrada', ?, 'Estoque inicial', ?)""",
                (produto_id, quantidade, agora()),
            )
    return produto_id


def editar_produto(produto_id, codigo, nome, categoria, preco, estoque_minimo):
    """Edita dados do produto. A quantidade só muda por movimentações de estoque."""
    codigo, nome, categoria, preco, estoque_minimo = _validar_produto(
        codigo, nome, categoria, preco, estoque_minimo
    )
    with transacao() as conexao:
        _buscar_produto_ou_erro(conexao, produto_id)
        if _codigo_ja_existe(conexao, codigo, ignorar_id=produto_id):
            raise ErroDeNegocio(f"Já existe outro produto com o código '{codigo}'. Escolha um código diferente.")
        conexao.execute(
            """UPDATE produtos
               SET codigo = ?, nome = ?, categoria = ?, preco = ?, estoque_minimo = ?
               WHERE id = ?""",
            (codigo, nome, categoria, preco, estoque_minimo, produto_id),
        )


def excluir_produto(produto_id):
    """Exclui um produto que nunca foi usado em pedidos (o histórico dele também é apagado)."""
    with transacao() as conexao:
        produto = _buscar_produto_ou_erro(conexao, produto_id)
        usado = conexao.execute(
            "SELECT COUNT(*) FROM itens_pedido WHERE produto_id = ?", (produto_id,)
        ).fetchone()[0]
        if usado:
            raise ErroDeNegocio(
                f"'{produto['nome']}' não pode ser excluído porque aparece em pedidos. "
                "Para parar de vender, zere o estoque por uma saída."
            )
        conexao.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    return produto["nome"]


def obter_produto(produto_id):
    """Retorna um produto (dicionário) ou None."""
    with closing(conectar()) as conexao:
        linha = conexao.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    return dict(linha) if linha else None


def obter_produto_por_codigo(codigo):
    """Retorna o produto com este código (dicionário) ou None. Somente leitura."""
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None
    with closing(conectar()) as conexao:
        linha = conexao.execute("SELECT * FROM produtos WHERE codigo = ?", (codigo,)).fetchone()
    return dict(linha) if linha else None


def produto_tem_pedidos(produto_id):
    """True se o produto já aparece em algum pedido (nesse caso não pode ser excluído)."""
    with closing(conectar()) as conexao:
        total = conexao.execute(
            "SELECT COUNT(*) FROM itens_pedido WHERE produto_id = ?", (produto_id,)
        ).fetchone()[0]
    return total > 0


def buscar_produtos(termo=""):
    """Lista produtos (DataFrame). Se houver termo, filtra por nome ou código."""
    termo = (termo or "").strip()
    sql = "SELECT id, codigo, nome, categoria, preco, quantidade, estoque_minimo FROM produtos"
    parametros = ()
    if termo:
        # Escapa os curingas do LIKE para que o usuário possa digitar % ou _ normalmente
        seguro = termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        sql += " WHERE nome LIKE ? ESCAPE '\\' OR codigo LIKE ? ESCAPE '\\'"
        parametros = (f"%{seguro}%", f"%{seguro}%")
    sql += " ORDER BY nome"
    return consultar(sql, parametros)


def opcoes_produtos():
    """Lista de (texto, id) para preencher listas de seleção."""
    df = buscar_produtos()
    return [
        (f"{linha.codigo} — {linha.nome} (estoque: {linha.quantidade})", int(linha.id))
        for linha in df.itertuples()
    ]


# ---------------------------------------------------------------------------
# Controle de estoque
# ---------------------------------------------------------------------------
def registrar_movimentacao(produto_id, tipo, quantidade, motivo=""):
    """
    Registra uma Entrada ou Saída e atualiza a quantidade do produto.
    Impede saída maior que o estoque. Retorna a nova quantidade em estoque.
    """
    if tipo not in ("Entrada", "Saída"):
        raise ErroDeNegocio("Escolha o tipo de movimentação (Entrada ou Saída).")
    if produto_id is None:
        raise ErroDeNegocio("Selecione um produto.")
    quantidade = numero_inteiro(quantidade, "Quantidade", 1)
    motivo = (motivo or "").strip()[:200] or ("Entrada manual" if tipo == "Entrada" else "Saída manual")

    with transacao() as conexao:
        produto = _buscar_produto_ou_erro(conexao, produto_id)
        if tipo == "Saída":
            if quantidade > produto["quantidade"]:
                raise ErroDeNegocio(
                    f"Estoque insuficiente: '{produto['nome']}' tem apenas "
                    f"{produto['quantidade']} unidade(s). Reduza a quantidade ou registre uma entrada antes."
                )
            conexao.execute(
                "UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?",
                (quantidade, produto_id),
            )
        else:
            conexao.execute(
                "UPDATE produtos SET quantidade = quantidade + ? WHERE id = ?",
                (quantidade, produto_id),
            )
        conexao.execute(
            """INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo, data)
               VALUES (?, ?, ?, ?, ?)""",
            (produto_id, tipo, quantidade, motivo, agora()),
        )
        return conexao.execute(
            "SELECT quantidade FROM produtos WHERE id = ?", (produto_id,)
        ).fetchone()[0]


def historico_movimentacoes(limite=300):
    """Histórico de movimentações (mais recentes primeiro) como DataFrame."""
    return consultar(
        """SELECT m.id, m.data, p.codigo, p.nome, m.tipo, m.quantidade, m.motivo
           FROM movimentacoes m
           JOIN produtos p ON p.id = m.produto_id
           ORDER BY m.id DESC
           LIMIT ?""",
        (limite,),
    )


def produtos_estoque_baixo():
    """
    Produtos com quantidade menor ou igual ao estoque mínimo DELES (limite por produto).
    Usa um filtro booleano do Pandas sobre o DataFrame de produtos.
    """
    df = buscar_produtos()
    baixo = df[df["quantidade"] <= df["estoque_minimo"]].copy()
    baixo["situacao"] = baixo["quantidade"].apply(
        lambda qtd: "Sem estoque" if qtd == 0 else "Estoque baixo"
    )
    return baixo.sort_values("quantidade").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------
def criar_pedido(cliente, itens):
    """
    Cria um pedido PENDENTE (não mexe no estoque).
    'itens' é uma lista de dicionários: {"produto_id": 1, "quantidade": 2}.
    O preço de cada item é "congelado" no momento da criação.
    """
    cliente = (cliente or "").strip()[:100] or "Cliente não informado"
    if not itens:
        raise ErroDeNegocio("Adicione pelo menos um produto ao pedido.")

    # Junta itens repetidos do mesmo produto
    quantidades = {}
    for item in itens:
        qtd = numero_inteiro(item["quantidade"], "Quantidade", 1)
        quantidades[item["produto_id"]] = quantidades.get(item["produto_id"], 0) + qtd

    with transacao() as conexao:
        linhas = []
        for produto_id, qtd in quantidades.items():
            produto = _buscar_produto_ou_erro(conexao, produto_id)
            linhas.append((produto_id, qtd, produto["preco"]))
        total = round(sum(qtd * preco for _, qtd, preco in linhas), 2)

        cursor = conexao.execute(
            """INSERT INTO pedidos (cliente, status, valor_total, data_criacao, data_atualizacao)
               VALUES (?, 'Pendente', ?, ?, ?)""",
            (cliente, total, agora(), agora()),
        )
        pedido_id = cursor.lastrowid
        conexao.executemany(
            """INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario)
               VALUES (?, ?, ?, ?)""",
            [(pedido_id, produto_id, qtd, preco) for produto_id, qtd, preco in linhas],
        )
    return pedido_id


def _mudar_status(conexao, pedido_id, status_esperado, novo_status):
    """
    Troca o status do pedido SOMENTE se ele ainda estiver no status esperado.
    É isso que impede o estoque de ser atualizado duas vezes pelo mesmo pedido:
    a segunda tentativa não encontra o status esperado e é recusada.
    """
    cursor = conexao.execute(
        "UPDATE pedidos SET status = ?, data_atualizacao = ? WHERE id = ? AND status = ?",
        (novo_status, agora(), pedido_id, status_esperado),
    )
    return cursor.rowcount == 1


def confirmar_pedido(pedido_id):
    """Confirma um pedido pendente: confere o estoque e dá baixa nos produtos."""
    if pedido_id is None:
        raise ErroDeNegocio("Selecione um pedido.")

    with transacao() as conexao:
        pedido = conexao.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if pedido is None:
            raise ErroDeNegocio("Pedido não encontrado.")
        if pedido["status"] != "Pendente":
            raise ErroDeNegocio(
                f"O pedido #{pedido_id} está '{pedido['status']}' e não pode ser confirmado."
            )

        itens = conexao.execute(
            """SELECT i.produto_id, i.quantidade, p.nome, p.quantidade AS disponivel
               FROM itens_pedido i JOIN produtos p ON p.id = i.produto_id
               WHERE i.pedido_id = ?""",
            (pedido_id,),
        ).fetchall()

        # 1) Confere TODOS os itens antes de alterar qualquer coisa
        faltas = [
            f"{item['nome']} (pedido: {item['quantidade']}, disponível: {item['disponivel']})"
            for item in itens
            if item["quantidade"] > item["disponivel"]
        ]
        if faltas:
            raise ErroDeNegocio("Estoque insuficiente para: " + "; ".join(faltas) + ". Registre uma entrada na aba Estoque e tente de novo.")

        # 2) Marca como confirmado (só funciona se ainda estiver pendente)
        if not _mudar_status(conexao, pedido_id, "Pendente", "Confirmado"):
            raise ErroDeNegocio("Este pedido já foi processado.")

        # 3) Dá baixa no estoque e registra as movimentações
        for item in itens:
            conexao.execute(
                "UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?",
                (item["quantidade"], item["produto_id"]),
            )
            conexao.execute(
                """INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo, pedido_id, data)
                   VALUES (?, 'Saída', ?, ?, ?, ?)""",
                (item["produto_id"], item["quantidade"],
                 f"Pedido #{pedido_id} confirmado", pedido_id, agora()),
            )


def cancelar_pedido(pedido_id):
    """
    Cancela um pedido. Se ele estava CONFIRMADO, devolve os produtos ao estoque.
    Retorna True quando o estoque foi restaurado.
    """
    if pedido_id is None:
        raise ErroDeNegocio("Selecione um pedido.")

    with transacao() as conexao:
        pedido = conexao.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if pedido is None:
            raise ErroDeNegocio("Pedido não encontrado.")
        status_atual = pedido["status"]
        if status_atual == "Cancelado":
            raise ErroDeNegocio(f"O pedido #{pedido_id} já está cancelado.")

        if not _mudar_status(conexao, pedido_id, status_atual, "Cancelado"):
            raise ErroDeNegocio("Este pedido já foi processado.")

        if status_atual == "Confirmado":
            itens = conexao.execute(
                "SELECT produto_id, quantidade FROM itens_pedido WHERE pedido_id = ?",
                (pedido_id,),
            ).fetchall()
            for item in itens:
                conexao.execute(
                    "UPDATE produtos SET quantidade = quantidade + ? WHERE id = ?",
                    (item["quantidade"], item["produto_id"]),
                )
                conexao.execute(
                    """INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo, pedido_id, data)
                       VALUES (?, 'Entrada', ?, ?, ?, ?)""",
                    (item["produto_id"], item["quantidade"],
                     f"Cancelamento do pedido #{pedido_id}", pedido_id, agora()),
                )
    return status_atual == "Confirmado"


def listar_pedidos(status=None):
    """Histórico de pedidos (mais recentes primeiro). 'status' filtra, se informado."""
    df = consultar(
        """SELECT p.id, p.cliente, p.status, p.valor_total, p.data_criacao,
                  COALESCE(SUM(i.quantidade), 0) AS itens
           FROM pedidos p
           LEFT JOIN itens_pedido i ON i.pedido_id = p.id
           GROUP BY p.id
           ORDER BY p.id DESC"""
    )
    if status in STATUS_PEDIDO:
        df = df[df["status"] == status].reset_index(drop=True)
    return df


def itens_do_pedido(pedido_id):
    """Itens de um pedido, com subtotal calculado pelo Pandas."""
    df = consultar(
        """SELECT p.codigo, p.nome, i.quantidade, i.preco_unitario
           FROM itens_pedido i JOIN produtos p ON p.id = i.produto_id
           WHERE i.pedido_id = ?
           ORDER BY i.id""",
        (pedido_id,),
    )
    df["subtotal"] = (df["quantidade"] * df["preco_unitario"]).round(2)
    return df


def detalhe_pedido(pedido_id):
    """
    Dados de um pedido e seus itens, com o estoque disponível de cada produto.
    Somente leitura: serve para mostrar um resumo antes de confirmar/cancelar.
    """
    pedidos = consultar(
        "SELECT id, cliente, status, valor_total, data_criacao FROM pedidos WHERE id = ?",
        (pedido_id,),
    )
    if pedidos.empty:
        raise ErroDeNegocio("Pedido não encontrado. Atualize a tela e tente novamente.")
    itens = consultar(
        """SELECT p.codigo, p.nome, i.quantidade, i.preco_unitario, p.quantidade AS disponivel
           FROM itens_pedido i JOIN produtos p ON p.id = i.produto_id
           WHERE i.pedido_id = ?
           ORDER BY i.id""",
        (pedido_id,),
    )
    itens["subtotal"] = (itens["quantidade"] * itens["preco_unitario"]).round(2)
    return pedidos.iloc[0].to_dict(), itens


def opcoes_pedidos():
    """Lista de (texto, id) dos pedidos para as listas de seleção."""
    df = listar_pedidos()
    return [
        (f"#{l.id} · {l.cliente} · {l.status} · R$ {l.valor_total:.2f}", int(l.id))
        for l in df.itertuples()
    ]


# ---------------------------------------------------------------------------
# Indicadores do dashboard (calculados com Pandas)
# ---------------------------------------------------------------------------
def calcular_indicadores():
    produtos = buscar_produtos()
    pedidos = listar_pedidos()
    confirmados = pedidos[pedidos["status"] == "Confirmado"]
    return {
        "total_produtos": int(len(produtos)),
        "total_unidades": int(produtos["quantidade"].sum()),
        "total_pedidos": int(len(pedidos)),
        "pedidos_confirmados": int(len(confirmados)),
        "pedidos_pendentes": int((pedidos["status"] == "Pendente").sum()),
        "pedidos_cancelados": int((pedidos["status"] == "Cancelado").sum()),
        "valor_confirmado": round(float(confirmados["valor_total"].sum()), 2),
        "estoque_baixo": int(len(produtos_estoque_baixo())),
    }

"""
app.py — Interface web do EstoqueFácil (Gradio).

Para executar:  python app.py
O navegador abrirá em http://127.0.0.1:7860

Este arquivo só cuida da TELA: ele chama as funções de database.py (regras e banco)
e relatorios.py (Pandas + Matplotlib) e mostra os resultados ao usuário.

Padrões de interface usados em todo o sistema (consistência):
  - Mensagens: caixas coloridas com ícone e hora  ✅ sucesso · ⚠️ aviso · ❌ erro · ℹ️ informação
  - Botões: "Verbo + objeto", sem emojis. Azul = ação principal, vermelho = ação destrutiva.
  - Ações que não podem ser desfeitas (excluir produto, confirmar/cancelar pedido)
    pedem uma confirmação com resumo do que vai acontecer.
  - Valores em reais sempre no formato brasileiro: R$ 1.234,50
"""

import html
from datetime import datetime, timedelta

import gradio as gr
import pandas as pd

import database as db
import relatorios
from dados_demo import carregar_dados_demonstracao

CATEGORIAS = ["Alimentos", "Bebidas", "Limpeza", "Higiene", "Papelaria", "Outros"]
FILTROS_STATUS = ["Todos", "Pendente", "Confirmado", "Cancelado"]

CSS = """
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }
.card { border: 1px solid var(--border-color-primary); border-radius: 14px; padding: 18px 20px;
        background: var(--background-fill-secondary); }
.card .titulo { font-size: 0.85rem; opacity: 0.8; }
.card .valor { font-size: 2rem; font-weight: 700; margin: 4px 0; }
.card .detalhe { font-size: 0.8rem; opacity: 0.75; }
.card.alerta { border: 2px solid #dc2626; }

.msg { display: flex; gap: 10px; align-items: flex-start; padding: 10px 14px; margin: 6px 0;
       border-radius: 10px; border: 1px solid var(--border-color-primary);
       border-left-width: 6px; background: var(--background-fill-secondary); }
.msg-sucesso { border-left-color: #16a34a; }
.msg-erro    { border-left-color: #dc2626; }
.msg-aviso   { border-left-color: #d97706; }
.msg-info    { border-left-color: #2563eb; }
.msg-icone   { font-size: 1.1rem; line-height: 1.4; }
.msg-detalhe { margin-top: 2px; font-size: 0.92rem; }
.msg-hora    { margin-top: 2px; font-size: 0.75rem; opacity: 0.7; }
.msg ul      { margin: 6px 0 0 18px; padding: 0; }
"""

ICONES = {"sucesso": "✅", "erro": "❌", "aviso": "⚠️", "info": "ℹ️"}


# ---------------------------------------------------------------------------
# Mensagens padronizadas (sucesso, aviso, erro e informação)
# ---------------------------------------------------------------------------
def mensagem(tipo, texto, detalhe="", com_hora=True, html_extra=""):
    """
    Monta uma caixa de mensagem. 'texto' é a frase principal; 'detalhe' explica
    o que fazer a seguir. Erros e avisos usam role="alert" (leitores de tela leem na hora).
    """
    papel = "alert" if tipo in ("erro", "aviso") else "status"
    detalhe_html = f'<div class="msg-detalhe">{html.escape(detalhe)}</div>' if detalhe else ""
    hora_html = f'<div class="msg-hora">{datetime.now():%H:%M}</div>' if com_hora else ""
    return (
        f'<div class="msg msg-{tipo}" role="{papel}"><span class="msg-icone">{ICONES[tipo]}</span>'
        f'<div><strong>{html.escape(texto)}</strong>{detalhe_html}{html_extra}{hora_html}</div></div>'
    )


def sucesso(texto, detalhe=""):
    return mensagem("sucesso", texto, detalhe)


def aviso(texto, detalhe=""):
    return mensagem("aviso", texto, detalhe)


def nota(texto, detalhe=""):
    """Mensagem informativa fixa (sem hora)."""
    return mensagem("info", texto, detalhe, com_hora=False)


def erro(excecao):
    """Transforma uma exceção em mensagem amigável."""
    if isinstance(excecao, db.ErroDeNegocio):
        return mensagem("erro", str(excecao))
    print(f"[ERRO INESPERADO] {type(excecao).__name__}: {excecao}")
    return mensagem(
        "erro", "Ocorreu um erro inesperado e a operação não foi concluída.",
        "Tente novamente. Se o problema continuar, feche o programa (Ctrl+C no terminal) e abra de novo.")


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------
def brl(valor):
    """Formata número como moeda brasileira: 1234.5 -> R$ 1.234,50"""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def formatar_data(serie):
    return pd.to_datetime(serie).dt.strftime("%d/%m/%Y %H:%M")


def formatar_moeda(df, colunas):
    """Troca colunas numéricas por texto em reais (R$ 1.234,50) para exibir nas tabelas."""
    df = df.copy()
    for coluna in colunas:
        df[coluna] = df[coluna].map(brl)
    return df


# ---------------------------------------------------------------------------
# Tabelas prontas para exibição
# ---------------------------------------------------------------------------
def tabela_produtos(df):
    df = df.copy()
    df["situacao"] = [
        "Estoque baixo" if qtd <= minimo else "OK"
        for qtd, minimo in zip(df["quantidade"], df["estoque_minimo"])
    ]
    df = formatar_moeda(df, ["preco"])
    df = df[["codigo", "nome", "categoria", "preco", "quantidade", "estoque_minimo", "situacao"]]
    return df.rename(columns={
        "codigo": "Código", "nome": "Nome", "categoria": "Categoria", "preco": "Preço",
        "quantidade": "Estoque", "estoque_minimo": "Estoque mínimo", "situacao": "Situação",
    })


def tabela_estoque_baixo(df):
    return df[["codigo", "nome", "categoria", "quantidade", "estoque_minimo", "situacao"]].rename(columns={
        "codigo": "Código", "nome": "Nome", "categoria": "Categoria",
        "quantidade": "Estoque", "estoque_minimo": "Estoque mínimo", "situacao": "Situação",
    })


def tabela_movimentacoes(df):
    df = df.copy()
    df["data"] = formatar_data(df["data"])
    return df.drop(columns="id").rename(columns={
        "data": "Data", "codigo": "Código", "nome": "Produto", "tipo": "Tipo",
        "quantidade": "Quantidade", "motivo": "Motivo",
    })


def tabela_pedidos(df):
    df = formatar_moeda(df, ["valor_total"])
    df["data_criacao"] = formatar_data(df["data_criacao"])
    df = df[["id", "cliente", "status", "itens", "valor_total", "data_criacao"]]
    return df.rename(columns={
        "id": "Nº", "cliente": "Cliente", "status": "Situação", "itens": "Unidades",
        "valor_total": "Valor", "data_criacao": "Criado em",
    })


COLUNAS_ITENS = ["Código", "Produto", "Quantidade", "Preço unitário", "Subtotal"]


def detalhar_pedido(pedido_id):
    """Resumo + tabela de itens do pedido selecionado."""
    vazia = pd.DataFrame(columns=COLUNAS_ITENS)
    if pedido_id is None:
        return nota("Escolha um pedido na lista ou clique em uma linha do histórico para ver os itens."), vazia
    try:
        pedido, itens = db.detalhe_pedido(pedido_id)
    except db.ErroDeNegocio:
        return "", vazia
    itens = formatar_moeda(itens[["codigo", "nome", "quantidade", "preco_unitario", "subtotal"]],
                           ["preco_unitario", "subtotal"])
    itens.columns = COLUNAS_ITENS
    resumo = nota(f"Pedido #{pedido['id']} · {pedido['cliente']} · Situação: {pedido['status']}",
                  f"Valor total: {brl(pedido['valor_total'])}")
    return resumo, itens


def aviso_lista(total, mostrados, vazio, busca=""):
    """Texto curto sobre o que a tabela está mostrando (e o que fazer se estiver vazia)."""
    if total == 0:
        return nota(vazio)
    if mostrados == 0:
        return nota("Nenhum resultado para o filtro escolhido.",
                    "Limpe a pesquisa ou desmarque os filtros para ver tudo de novo.")
    return mensagem("info", f"Mostrando {mostrados} de {total}.", com_hora=False) if mostrados != total else ""


def html_cards(ind):
    """Cartões de indicadores do dashboard."""
    alerta = " alerta" if ind["estoque_baixo"] > 0 else ""
    situacao_baixo = "precisam de reposição" if ind["estoque_baixo"] else "tudo certo por aqui"
    detalhe_pedidos = (f"{ind['pedidos_confirmados']} confirmados · "
                       f"{ind['pedidos_pendentes']} pendentes · {ind['pedidos_cancelados']} cancelados")
    return f"""
    <div class="cards">
      <div class="card"><div class="titulo">Produtos cadastrados</div>
        <div class="valor">{ind['total_produtos']}</div><div class="detalhe">itens diferentes</div></div>
      <div class="card"><div class="titulo">Unidades em estoque</div>
        <div class="valor">{ind['total_unidades']}</div><div class="detalhe">soma de todos os produtos</div></div>
      <div class="card"><div class="titulo">Pedidos realizados</div>
        <div class="valor">{ind['total_pedidos']}</div><div class="detalhe">{detalhe_pedidos}</div></div>
      <div class="card"><div class="titulo">Valor dos pedidos confirmados</div>
        <div class="valor">{brl(ind['valor_confirmado'])}</div><div class="detalhe">somente confirmados</div></div>
      <div class="card{alerta}"><div class="titulo">{'⚠️ ' if alerta else ''}Estoque baixo</div>
        <div class="valor">{ind['estoque_baixo']}</div><div class="detalhe">{situacao_baixo}</div></div>
    </div>"""


def html_boas_vindas(ind):
    """Orientação para quem ainda não cadastrou nenhum produto."""
    if ind["total_produtos"] > 0:
        return ""
    return mensagem(
        "info", "Bem-vindo ao EstoqueFácil! Para começar:",
        com_hora=False,
        html_extra=("<ul><li>Abra a aba <b>Produtos</b> e cadastre seu primeiro produto.</li>"
                    "<li>Depois use <b>Pedidos</b> para registrar vendas — o estoque é atualizado sozinho.</li>"
                    "<li>Só quer conhecer o sistema? Use <b>Dados de demonstração</b> mais abaixo.</li>"
                    "<li>Dúvidas? Veja a aba <b>Ajuda</b>.</li></ul>"))


def resumo_estoque_baixo(df, com_dica=False):
    if df.empty:
        return mensagem("sucesso", "Tudo certo: nenhum produto com estoque baixo.", com_hora=False)
    detalhe = "Dica: clique em um produto da tabela para registrar uma entrada." if com_dica else ""
    return mensagem("aviso", f"{len(df)} produto(s) com estoque baixo ou zerado.", detalhe, com_hora=False)


def atualizar_lista(opcoes, valor_atual):
    """Atualiza as opções de uma lista de seleção mantendo a escolha atual (se ainda existir)."""
    ids = [valor for _, valor in opcoes]
    return gr.Dropdown(choices=opcoes, value=valor_atual if valor_atual in ids else None)


def opcoes_produtos_para_pedido():
    """Lista de produtos mostrando preço e estoque (o usuário não precisa lembrar de nada)."""
    df = db.buscar_produtos()
    return [(f"{l.codigo} — {l.nome} · {brl(l.preco)} · estoque: {l.quantidade}", int(l.id))
            for l in df.itertuples()]


def opcoes_pedidos_formatadas():
    df = db.listar_pedidos()
    return [(f"#{l.id} · {l.cliente} · {l.status} · {brl(l.valor_total)}", int(l.id))
            for l in df.itertuples()]


def produtos_filtrados(busca, so_baixo):
    df = db.buscar_produtos(busca)
    if so_baixo:
        df = df[df["quantidade"] <= df["estoque_minimo"]]
    return df


# ---------------------------------------------------------------------------
# Atualização geral da tela (chamada ao abrir o app e após cada operação)
# ---------------------------------------------------------------------------
def atualizar_tudo(busca, so_baixo, filtro_status, sel_editar, sel_estoque,
                   sel_produto_pedido, sel_pedido):
    indicadores = db.calcular_indicadores()
    baixo = db.produtos_estoque_baixo()
    baixo_exibicao = tabela_estoque_baixo(baixo)
    opcoes_prod = db.opcoes_produtos()
    opcoes_ped = opcoes_pedidos_formatadas()
    ids_pedidos = [valor for _, valor in opcoes_ped]
    status = None if filtro_status == "Todos" else filtro_status
    produtos = produtos_filtrados(busca, so_baixo)
    pedidos = db.listar_pedidos(status)
    resumo_ped, itens_ped = detalhar_pedido(sel_pedido if sel_pedido in ids_pedidos else None)
    return (
        html_cards(indicadores),                                                    # 1 cartões
        html_boas_vindas(indicadores),                                              # 2 boas-vindas
        resumo_estoque_baixo(baixo, com_dica=True),                                 # 3 resumo (dashboard)
        baixo_exibicao,                                                             # 4 tabela (dashboard)
        aviso_lista(indicadores["total_produtos"], len(produtos),
                    "Nenhum produto cadastrado ainda. Use o formulário acima para cadastrar o primeiro."),  # 5
        tabela_produtos(produtos),                                                  # 6 tabela de produtos
        atualizar_lista(opcoes_prod, sel_editar),                                   # 7 lista: editar
        atualizar_lista(opcoes_prod, sel_estoque),                                  # 8 lista: estoque
        tabela_movimentacoes(db.historico_movimentacoes()),                         # 9 histórico
        resumo_estoque_baixo(baixo),                                                # 10 resumo (estoque)
        baixo_exibicao,                                                             # 11 tabela (estoque)
        atualizar_lista(opcoes_produtos_para_pedido(), sel_produto_pedido),         # 12 lista: pedido
        atualizar_lista(opcoes_ped, sel_pedido),                                    # 13 lista: pedidos
        aviso_lista(indicadores["total_pedidos"], len(pedidos),
                    "Nenhum pedido criado ainda. Monte o primeiro na aba 'Novo pedido'."),  # 14
        tabela_pedidos(pedidos),                                                    # 15 histórico de pedidos
        resumo_ped,                                                                 # 16 resumo do pedido
        itens_ped,                                                                  # 17 itens do pedido
    )


# ---------------------------------------------------------------------------
# Dicas em tempo real (previnem erros antes de clicar no botão)
# ---------------------------------------------------------------------------
def dica_codigo(codigo):
    """Avisa na hora se o código digitado já existe."""
    if not (codigo or "").strip():
        return ""
    existente = db.obter_produto_por_codigo(codigo)
    if existente:
        return aviso(f"O código {existente['codigo']} já pertence a '{existente['nome']}'.",
                     "Escolha outro código ou edite o produto existente.")
    return mensagem("sucesso", "Código disponível.", com_hora=False)


def dica_movimentacao(produto_id, tipo, quantidade):
    """Mostra o estoque atual e como ele ficará depois da movimentação."""
    if produto_id is None:
        return nota("Escolha um produto para ver o estoque atual.")
    produto = db.obter_produto(produto_id)
    if produto is None:
        return ""
    atual = produto["quantidade"]
    try:
        qtd = db.numero_inteiro(quantidade, "Quantidade", 1)
    except db.ErroDeNegocio:
        return nota(f"Estoque atual de '{produto['nome']}': {atual} unidade(s).",
                    "Informe uma quantidade inteira maior que zero.")
    if tipo == "Saída":
        if qtd > atual:
            return aviso(f"Estoque atual: {atual}. Uma saída de {qtd} não será permitida.",
                         "Reduza a quantidade ou registre uma entrada antes.")
        return nota(f"Estoque atual: {atual} → depois da saída: {atual - qtd}.")
    return nota(f"Estoque atual: {atual} → depois da entrada: {atual + qtd}.")


# ---------------------------------------------------------------------------
# Ações: Produtos
# ---------------------------------------------------------------------------
def acao_cadastrar_produto(codigo, nome, categoria, preco, quantidade, minimo):
    try:
        db.cadastrar_produto(codigo, nome, categoria, preco, quantidade, minimo)
    except Exception as e:
        return erro(e), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
    # Sucesso: mensagem + limpa o formulário para o próximo cadastro
    mensagem_ok = sucesso(f"Produto '{nome.strip()}' cadastrado.",
                          f"Estoque inicial: {int(quantidade)} unidade(s). Ele já aparece na lista abaixo.")
    return mensagem_ok, "", "", None, 0, 5


def acao_carregar_produto(produto_id):
    """Preenche o formulário de edição quando um produto é escolhido."""
    if produto_id is None:
        # Nenhum produto escolhido: limpa os campos, mas mantém a última mensagem exibida
        return "", "", None, None, None, gr.skip()
    produto = db.obter_produto(produto_id)
    if produto is None:
        return "", "", None, None, None, gr.skip()
    return (produto["codigo"], produto["nome"], produto["categoria"], produto["preco"],
            produto["estoque_minimo"],
            nota(f"Editando '{produto['nome']}'.",
                 "Altere os campos e clique em Salvar alterações, ou em Descartar alterações para voltar."))


def acao_editar_produto(produto_id, codigo, nome, categoria, preco, minimo):
    try:
        if produto_id is None:
            raise db.ErroDeNegocio("Escolha na lista o produto que deseja editar.")
        db.editar_produto(produto_id, codigo, nome, categoria, preco, minimo)
        return sucesso("Alterações salvas.", "A tabela de produtos já mostra os novos dados.")
    except Exception as e:
        return erro(e)


def acao_selecionar_produto_tabela(evt: gr.SelectData):
    """Clique em uma linha da tabela de produtos: abre o produto para edição."""
    produto = db.obter_produto_por_codigo(evt.row_value[0])
    if produto is None:
        return gr.skip(), gr.skip()
    return produto["id"], gr.Accordion(open=True)


def pedir_exclusao_produto(produto_id):
    """Passo 1 da exclusão: mostra um resumo e pede confirmação."""
    fechado = gr.Group(visible=False)
    if produto_id is None:
        return erro(db.ErroDeNegocio("Escolha na lista o produto que deseja excluir.")), fechado, "", None
    produto = db.obter_produto(produto_id)
    if produto is None:
        return erro(db.ErroDeNegocio("Produto não encontrado. Atualize a tela e tente novamente.")), fechado, "", None
    if db.produto_tem_pedidos(produto_id):
        return (aviso(f"'{produto['nome']}' não pode ser excluído porque já aparece em pedidos.",
                      "Para parar de vender, registre uma saída até o estoque chegar a zero."),
                fechado, "", None)
    texto = mensagem(
        "aviso", f"Excluir '{produto['nome']}' (código {produto['codigo']})?",
        f"Hoje há {produto['quantidade']} unidade(s) em estoque. O histórico de movimentações "
        "deste produto também será apagado. Esta ação não pode ser desfeita.", com_hora=False)
    return "", gr.Group(visible=True), texto, {"produto_id": produto_id}


def executar_exclusao_produto(pendente):
    """Passo 2 da exclusão: só acontece depois do 'Sim, excluir'."""
    fechado = gr.Group(visible=False)
    if not pendente:
        return aviso("Nenhuma exclusão pendente."), fechado, None
    try:
        nome = db.excluir_produto(pendente["produto_id"])
        return sucesso(f"Produto '{nome}' excluído."), fechado, None
    except Exception as e:
        return erro(e), fechado, None


def cancelar_exclusao_produto():
    return nota("Exclusão cancelada. Nada foi alterado."), gr.Group(visible=False), None


def fechar_painel_exclusao():
    return gr.Group(visible=False), None


# ---------------------------------------------------------------------------
# Ações: Estoque
# ---------------------------------------------------------------------------
def acao_movimentar_estoque(produto_id, tipo, quantidade, motivo):
    try:
        nova_quantidade = db.registrar_movimentacao(produto_id, tipo, quantidade, motivo)
    except Exception as e:
        return erro(e), gr.skip()
    return (sucesso(f"{tipo} registrada. Estoque atual do produto: {nova_quantidade} unidade(s).",
                    "Registrou errado? Corrija lançando a movimentação contrária (entrada ↔ saída)."),
            "")


def acao_abrir_reposicao(evt: gr.SelectData):
    """Clique em um produto de estoque baixo (Dashboard): vai direto para a entrada de estoque."""
    produto = db.obter_produto_por_codigo(evt.row_value[0])
    if produto is None:
        return gr.skip(), gr.skip(), gr.skip()
    return gr.Tabs(selected="aba_estoque"), produto["id"], "Entrada"


# ---------------------------------------------------------------------------
# Ações: Pedidos (montagem do carrinho)
# ---------------------------------------------------------------------------
def visao_carrinho(carrinho):
    """Tabela do pedido em montagem, texto do total e lista de itens removíveis."""
    linhas, remover, total = [], [], 0.0
    for item in carrinho:
        produto = db.obter_produto(item["produto_id"])
        if produto is None:
            continue
        subtotal = round(produto["preco"] * item["quantidade"], 2)
        total += subtotal
        linhas.append([produto["codigo"], produto["nome"], item["quantidade"], brl(produto["preco"]), brl(subtotal)])
        remover.append((f"{produto['nome']} × {item['quantidade']}", item["produto_id"]))
    tabela = pd.DataFrame(linhas, columns=COLUNAS_ITENS)
    return tabela, f"### Total do pedido: {brl(total)}", gr.Dropdown(choices=remover, value=None)


def acao_adicionar_item(carrinho, produto_id, quantidade):
    carrinho = [dict(item) for item in carrinho]
    try:
        if produto_id is None:
            raise db.ErroDeNegocio("Escolha um produto na lista antes de adicionar.")
        quantidade = db.numero_inteiro(quantidade, "Quantidade", 1)
        produto = db.obter_produto(produto_id)
        if produto is None:
            raise db.ErroDeNegocio("Produto não encontrado. Atualize a tela e tente novamente.")
        for item in carrinho:
            if item["produto_id"] == produto_id:
                item["quantidade"] += quantidade
                break
        else:
            carrinho.append({"produto_id": produto_id, "quantidade": quantidade})
        total_item = next(i["quantidade"] for i in carrinho if i["produto_id"] == produto_id)
        if total_item > produto["quantidade"]:
            texto = aviso(f"'{produto['nome']}' adicionado, mas o estoque atual é de {produto['quantidade']} unidade(s).",
                          "Você pode criar o pedido, porém só poderá confirmá-lo quando houver estoque suficiente.")
        else:
            texto = sucesso(f"'{produto['nome']}' adicionado ao pedido.")
    except Exception as e:
        texto = erro(e)
    tabela, total, remover = visao_carrinho(carrinho)
    return carrinho, tabela, total, remover, texto


def acao_remover_item(carrinho, produto_id):
    if produto_id is None:
        tabela, total, remover = visao_carrinho(carrinho)
        return carrinho, tabela, total, remover, aviso("Escolha na lista qual item deseja remover.")
    carrinho = [dict(i) for i in carrinho if i["produto_id"] != produto_id]
    tabela, total, remover = visao_carrinho(carrinho)
    return carrinho, tabela, total, remover, sucesso("Item removido do pedido.")


def acao_limpar_carrinho():
    tabela, total, remover = visao_carrinho([])
    return [], tabela, total, remover, nota("Pedido em branco. Você pode começar de novo.")


def acao_criar_pedido(cliente, carrinho):
    try:
        pedido_id = db.criar_pedido(cliente, carrinho)
    except Exception as e:
        tabela, total, remover = visao_carrinho(carrinho)
        return carrinho, tabela, total, remover, erro(e), gr.skip()
    tabela, total, remover = visao_carrinho([])
    texto = sucesso(f"Pedido #{pedido_id} criado como Pendente. O estoque ainda não foi alterado.",
                    "Próximo passo: abra a aba 'Pedidos feitos', escolha o pedido e clique em Confirmar pedido.")
    return [], tabela, total, remover, texto, ""


# ---------------------------------------------------------------------------
# Ações: Pedidos (confirmar e cancelar, sempre com confirmação)
# ---------------------------------------------------------------------------
def pedir_confirmacao_pedido(pedido_id, acao):
    """
    Passo 1: valida e mostra o que vai acontecer com o estoque.
    Só depois do 'Sim' (passo 2) a operação é realmente executada.
    """
    fechado = gr.Group(visible=False)
    botao_padrao = gr.Button(value="Sim, continuar")
    try:
        if pedido_id is None:
            raise db.ErroDeNegocio("Escolha um pedido na lista (ou clique em uma linha do histórico).")
        pedido, itens = db.detalhe_pedido(pedido_id)
        status = pedido["status"]
        if acao == "confirmar" and status != "Pendente":
            raise db.ErroDeNegocio(f"O pedido #{pedido_id} está '{status}' e não pode ser confirmado.")
        if acao == "cancelar" and status == "Cancelado":
            raise db.ErroDeNegocio(f"O pedido #{pedido_id} já está cancelado.")

        linhas = []
        if acao == "confirmar":
            faltas = [f"{l.nome} (pedido: {l.quantidade}, disponível: {l.disponivel})"
                      for l in itens.itertuples() if l.quantidade > l.disponivel]
            if faltas:
                raise db.ErroDeNegocio("Estoque insuficiente para: " + "; ".join(faltas)
                                       + ". Registre uma entrada na aba Estoque e tente de novo.")
            for l in itens.itertuples():
                linhas.append(f"<li>{html.escape(l.nome)}: estoque {l.disponivel} → {l.disponivel - l.quantidade}</li>")
            titulo = f"Confirmar o pedido #{pedido_id}?"
            detalhe = f"Cliente: {pedido['cliente']} · Total: {brl(pedido['valor_total'])}. O estoque será atualizado agora:"
            botao = gr.Button(value="Sim, confirmar pedido", variant="primary")
        else:
            if status == "Confirmado":
                for l in itens.itertuples():
                    linhas.append(f"<li>{html.escape(l.nome)}: estoque {l.disponivel} → {l.disponivel + l.quantidade}</li>")
                detalhe = "Os produtos voltarão ao estoque. Esta ação não pode ser desfeita:"
            else:
                detalhe = "O pedido ainda não deu baixa no estoque, então nada será devolvido. Esta ação não pode ser desfeita."
            titulo = f"Cancelar o pedido #{pedido_id} ({pedido['cliente']})?"
            botao = gr.Button(value="Sim, cancelar pedido", variant="stop")
        texto = mensagem("aviso", titulo, detalhe, com_hora=False,
                         html_extra=f"<ul>{''.join(linhas)}</ul>" if linhas else "")
    except Exception as e:
        return erro(e), fechado, "", None, botao_padrao
    return "", gr.Group(visible=True), texto, {"acao": acao, "pedido_id": pedido_id}, botao


def pedir_confirmar_pedido(pedido_id):
    return pedir_confirmacao_pedido(pedido_id, "confirmar")


def pedir_cancelar_pedido(pedido_id):
    return pedir_confirmacao_pedido(pedido_id, "cancelar")


def executar_acao_pedido(pendente):
    """Passo 2: executa a ação que o usuário acabou de confirmar."""
    fechado = gr.Group(visible=False)
    if not pendente:
        return aviso("Nenhuma ação pendente."), fechado, None
    pedido_id = pendente["pedido_id"]
    try:
        if pendente["acao"] == "confirmar":
            db.confirmar_pedido(pedido_id)
            texto = sucesso(f"Pedido #{pedido_id} confirmado. O estoque foi atualizado.")
        else:
            restaurado = db.cancelar_pedido(pedido_id)
            texto = sucesso(f"Pedido #{pedido_id} cancelado.",
                            "Os produtos voltaram ao estoque." if restaurado
                            else "O estoque não foi alterado (o pedido estava pendente).")
    except Exception as e:
        texto = erro(e)
    return texto, fechado, None


def voltar_acao_pedido():
    return nota("Ação cancelada. Nada foi alterado."), gr.Group(visible=False), None


def fechar_painel_pedido():
    return gr.Group(visible=False), None


def acao_selecionar_pedido_tabela(evt: gr.SelectData):
    """Clique em uma linha do histórico: seleciona o pedido para ver itens e agir sobre ele."""
    try:
        return int(evt.row_value[0])
    except (TypeError, ValueError):
        return gr.skip()


# ---------------------------------------------------------------------------
# Filtros rápidos (só atualizam a tabela correspondente)
# ---------------------------------------------------------------------------
def acao_filtrar_produtos(busca, so_baixo):
    total = len(db.buscar_produtos())
    produtos = produtos_filtrados(busca, so_baixo)
    return aviso_lista(total, len(produtos), "Nenhum produto cadastrado ainda."), tabela_produtos(produtos)


def acao_filtrar_pedidos(filtro_status):
    status = None if filtro_status == "Todos" else filtro_status
    total = len(db.listar_pedidos())
    pedidos = db.listar_pedidos(status)
    return aviso_lista(total, len(pedidos), "Nenhum pedido criado ainda."), tabela_pedidos(pedidos)


# ---------------------------------------------------------------------------
# Ações: Dashboard e Relatórios
# ---------------------------------------------------------------------------
def acao_carregar_demo():
    try:
        return sucesso(carregar_dados_demonstracao(),
                       "Explore o Dashboard, os Pedidos e os Relatórios. Para recomeçar do zero, apague o arquivo estoquefacil.db.")
    except Exception as e:
        return erro(e)


def acao_gerar_relatorios(data_inicio, data_fim):
    figura_estoque = relatorios.grafico_maior_estoque()
    figura_vendas = relatorios.grafico_mais_vendidos()
    baixo = tabela_estoque_baixo(db.produtos_estoque_baixo())
    try:
        tabela, figura_periodo, resumo = relatorios.relatorio_pedidos_periodo(data_inicio, data_fim)
    except Exception as e:
        return figura_estoque, figura_vendas, erro(e), gr.skip(), gr.skip(), baixo
    if not tabela.empty:
        tabela = formatar_moeda(tabela, ["Valor confirmado (R$)"]).rename(
            columns={"Valor confirmado (R$)": "Valor confirmado"})
    return figura_estoque, figura_vendas, nota(resumo), tabela, figura_periodo, baixo


# ---------------------------------------------------------------------------
# Texto da aba Ajuda
# ---------------------------------------------------------------------------
AJUDA_PASSOS = """
## Como usar o EstoqueFácil

1. **Cadastre seus produtos** na aba **Produtos** (código, nome, preço, quantidade e estoque mínimo).
2. **Atualize o estoque** na aba **Estoque** quando chegar mercadoria (*Entrada*) ou houver perda/uso (*Saída*).
3. **Registre uma venda** na aba **Pedidos → Novo pedido**: escolha os produtos, a quantidade e clique em **Criar pedido**.
4. **Confirme o pedido** em **Pedidos → Pedidos feitos**. É nesse momento que o estoque diminui.
5. **Acompanhe** o **Dashboard** e os **Relatórios** para saber o que vende mais e o que está acabando.

**Atalhos úteis:** clique em uma linha da tabela de produtos para editá-lo · clique em um produto
com estoque baixo no Dashboard para registrar uma entrada · clique em um pedido do histórico para ver os itens.
"""

AJUDA_GLOSSARIO = """
| Termo | Significado |
|---|---|
| **Estoque mínimo** | Quantidade a partir da qual o sistema avisa que o produto está acabando. Cada produto tem o seu. |
| **Estoque baixo** | Produto com quantidade igual ou menor que o estoque mínimo. |
| **Entrada** | Mercadoria que chegou (compra, reposição). Aumenta o estoque. |
| **Saída** | Mercadoria que saiu sem ser por pedido (perda, avaria, uso próprio). Diminui o estoque. |
| **Pedido Pendente** | Pedido anotado, mas que ainda não mexeu no estoque. |
| **Pedido Confirmado** | Venda concluída: o estoque já foi atualizado. |
| **Pedido Cancelado** | Pedido encerrado. Se estava confirmado, os produtos voltam ao estoque. |
"""

AJUDA_PERGUNTAS = """
**Lancei uma entrada ou saída errada. Como corrijo?**
Registre a movimentação contrária (se lançou uma entrada de 10 por engano, lance uma saída de 10). O histórico guarda as duas.

**Confirmei ou cancelei um pedido por engano.**
O sistema pede confirmação antes, mas depois de feito não há como desfazer. Para uma venda cancelada sem querer, crie e confirme um novo pedido.

**Por que não consigo excluir um produto?**
Produtos que já aparecem em pedidos ficam guardados para manter o histórico de vendas correto. Para parar de vender, deixe o estoque em zero.

**Por que não consigo confirmar um pedido?**
Algum produto não tem estoque suficiente. A mensagem mostra qual. Registre uma entrada na aba Estoque e confirme de novo.

**Onde ficam meus dados?**
No arquivo `estoquefacil.db`, na pasta do programa. Faça cópias dele de vez em quando para ter um backup.
"""


# ---------------------------------------------------------------------------
# Montagem da interface
# ---------------------------------------------------------------------------
def criar_interface():
    hoje = datetime.now()
    inicio_padrao = (hoje - timedelta(days=30)).strftime("%d/%m/%Y")
    fim_padrao = hoje.strftime("%d/%m/%Y")

    with gr.Blocks(title="EstoqueFácil") as demo:
        gr.Markdown("# 📦 EstoqueFácil\nControle de estoque e pedidos para pequenas lojas")
        carrinho = gr.State([])               # itens do pedido que está sendo montado
        estado_exclusao = gr.State(None)      # produto aguardando confirmação de exclusão
        estado_pedido = gr.State(None)        # ação sobre pedido aguardando confirmação

        with gr.Tabs() as abas:
            # ------------------------- DASHBOARD -------------------------
            with gr.Tab("📊 Dashboard", id="aba_dashboard"):
                boas_vindas = gr.HTML()
                cartoes = gr.HTML()
                gr.Markdown("### Produtos com estoque baixo")
                resumo_baixo_dash = gr.HTML()
                tabela_baixo_dash = gr.Dataframe(interactive=False, wrap=True)
                with gr.Accordion("Dados de demonstração (fictícios)", open=False):
                    gr.Markdown("Carrega produtos e pedidos de exemplo para conhecer o sistema. "
                                "Só funciona se não houver produtos cadastrados.")
                    botao_demo = gr.Button("Carregar dados de demonstração")
                    msg_demo = gr.HTML()

            # ------------------------- PRODUTOS -------------------------
            with gr.Tab("🏷️ Produtos", id="aba_produtos"):
                gr.Markdown("### Cadastrar produto")
                with gr.Row():
                    with gr.Column():
                        cad_codigo = gr.Textbox(label="Código", placeholder="Ex.: P013",
                                                info="Cada produto precisa de um código diferente.")
                        dica_cod = gr.HTML()
                    cad_nome = gr.Textbox(label="Nome", placeholder="Ex.: Leite 1L")
                    cad_categoria = gr.Dropdown(CATEGORIAS, value="Alimentos", allow_custom_value=True,
                                                label="Categoria", info="Escolha na lista ou digite uma nova.")
                with gr.Row():
                    cad_preco = gr.Number(label="Preço de venda (R$)", value=None, step=0.01,
                                          info="Valor de cada unidade. Ex.: 5.50")
                    cad_quantidade = gr.Number(label="Quantidade em estoque", value=0, step=1,
                                               info="Quantas unidades você tem agora. Pode ser 0.")
                    cad_minimo = gr.Number(label="Estoque mínimo", value=5, step=1,
                                           info="O sistema avisa quando o estoque chegar a este número ou menos.")
                botao_cadastrar = gr.Button("Cadastrar produto", variant="primary")
                msg_cadastro = gr.HTML()

                gr.Markdown("### Produtos cadastrados")
                with gr.Row():
                    busca_produto = gr.Textbox(label="Pesquisar", placeholder="Digite parte do nome ou do código...",
                                               scale=3)
                    so_baixo = gr.Checkbox(label="Mostrar só estoque baixo", scale=1)
                aviso_produtos = gr.HTML()
                tabela_prod = gr.Dataframe(interactive=False, wrap=True)
                gr.Markdown("Clique em uma linha da tabela para editar o produto.")

                with gr.Accordion("Editar ou excluir produto", open=False) as acordeao_editar:
                    sel_editar = gr.Dropdown(label="Produto", choices=[],
                                             info="Escolha na lista ou clique em uma linha da tabela acima.")
                    with gr.Row():
                        ed_codigo = gr.Textbox(label="Código")
                        ed_nome = gr.Textbox(label="Nome")
                        ed_categoria = gr.Dropdown(CATEGORIAS, allow_custom_value=True, label="Categoria")
                    with gr.Row():
                        ed_preco = gr.Number(label="Preço de venda (R$)", step=0.01)
                        ed_minimo = gr.Number(label="Estoque mínimo", step=1)
                    gr.Markdown("A quantidade em estoque é alterada apenas na aba **Estoque** ou por pedidos, "
                                "para o histórico ficar correto.")
                    with gr.Row():
                        botao_salvar = gr.Button("Salvar alterações", variant="primary")
                        botao_descartar = gr.Button("Descartar alterações")
                        botao_excluir = gr.Button("Excluir produto", variant="stop")
                    with gr.Group(visible=False) as painel_exclusao:
                        texto_exclusao = gr.HTML()
                        with gr.Row():
                            botao_sim_excluir = gr.Button("Sim, excluir produto", variant="stop")
                            botao_nao_excluir = gr.Button("Não, voltar")
                    msg_edicao = gr.HTML()

            # ------------------------- ESTOQUE -------------------------
            with gr.Tab("📥 Estoque", id="aba_estoque"):
                gr.Markdown("### Registrar entrada ou saída de mercadoria")
                with gr.Row():
                    sel_estoque = gr.Dropdown(label="Produto", choices=[], scale=3)
                    tipo_mov = gr.Radio(["Entrada", "Saída"], value="Entrada", label="Tipo",
                                        info="Entrada aumenta o estoque; saída diminui.")
                    qtd_mov = gr.Number(label="Quantidade", value=1, step=1)
                dica_mov = gr.HTML(nota("Escolha um produto para ver o estoque atual."))
                motivo_mov = gr.Textbox(label="Motivo (opcional)",
                                        placeholder="Ex.: compra do fornecedor, produto vencido, avaria...")
                botao_mov = gr.Button("Registrar movimentação", variant="primary")
                msg_mov = gr.HTML()
                gr.Markdown("### Produtos com estoque baixo")
                resumo_baixo_estoque = gr.HTML()
                tabela_baixo_estoque = gr.Dataframe(interactive=False, wrap=True)
                gr.Markdown("### Histórico de movimentações")
                tabela_mov = gr.Dataframe(interactive=False, wrap=True)

            # ------------------------- PEDIDOS -------------------------
            with gr.Tab("🧾 Pedidos", id="aba_pedidos"):
                with gr.Tabs():
                    with gr.Tab("Novo pedido"):
                        gr.Markdown("### Montar pedido")
                        with gr.Row():
                            cliente = gr.Textbox(label="Cliente (opcional)", placeholder="Ex.: Maria",
                                                 info="Pode deixar em branco.", scale=2)
                            sel_produto_pedido = gr.Dropdown(label="Produto", choices=[], scale=3,
                                                             info="A lista mostra preço e estoque de cada produto.")
                            qtd_pedido = gr.Number(label="Quantidade", value=1, step=1)
                        botao_adicionar = gr.Button("Adicionar item")
                        tabela_carrinho = gr.Dataframe(interactive=False, wrap=True)
                        total_pedido = gr.Markdown("### Total do pedido: R$ 0,00")
                        with gr.Row():
                            sel_remover = gr.Dropdown(label="Item para remover", choices=[], scale=3)
                            botao_remover = gr.Button("Remover item", scale=1)
                            botao_limpar = gr.Button("Limpar pedido", scale=1)
                        botao_criar = gr.Button("Criar pedido", variant="primary")
                        msg_novo = gr.HTML()

                    with gr.Tab("Pedidos feitos"):
                        gr.Markdown("### Confirmar ou cancelar pedido")
                        sel_pedido = gr.Dropdown(label="Pedido", choices=[],
                                                 info="Escolha na lista ou clique em uma linha do histórico abaixo.")
                        resumo_pedido = gr.HTML()
                        tabela_itens = gr.Dataframe(label="Itens do pedido", interactive=False, wrap=True)
                        with gr.Row():
                            botao_confirmar = gr.Button("Confirmar pedido", variant="primary")
                            botao_cancelar = gr.Button("Cancelar pedido", variant="stop")
                        with gr.Group(visible=False) as painel_pedido:
                            texto_pedido = gr.HTML()
                            with gr.Row():
                                botao_sim_pedido = gr.Button("Sim, continuar")
                                botao_nao_pedido = gr.Button("Não, voltar")
                        msg_gerenciar = gr.HTML()

                        gr.Markdown("### Histórico de pedidos")
                        filtro_status = gr.Dropdown(FILTROS_STATUS, value="Todos", label="Mostrar pedidos")
                        aviso_pedidos = gr.HTML()
                        tabela_ped = gr.Dataframe(interactive=False, wrap=True)

            # ------------------------- RELATÓRIOS -------------------------
            with gr.Tab("📈 Relatórios", id="aba_relatorios") as aba_relatorios:
                botao_relatorios = gr.Button("Atualizar relatórios", variant="primary")
                with gr.Row():
                    grafico_estoque = gr.Plot(label="Maior estoque")
                    grafico_vendas = gr.Plot(label="Mais vendidos")
                gr.Markdown("### Pedidos por período")
                with gr.Row():
                    rel_inicio = gr.Textbox(label="Data inicial", value=inicio_padrao, info="Formato DD/MM/AAAA")
                    rel_fim = gr.Textbox(label="Data final", value=fim_padrao, info="Formato DD/MM/AAAA")
                resumo_periodo = gr.HTML()
                with gr.Row():
                    tabela_periodo = gr.Dataframe(interactive=False, wrap=True)
                    grafico_periodo = gr.Plot(label="Valor por dia")
                gr.Markdown("### Produtos com estoque baixo")
                tabela_baixo_rel = gr.Dataframe(interactive=False, wrap=True)

            # ------------------------- AJUDA -------------------------
            with gr.Tab("❓ Ajuda", id="aba_ajuda"):
                gr.Markdown(AJUDA_PASSOS)
                with gr.Accordion("Significado dos termos", open=False):
                    gr.Markdown(AJUDA_GLOSSARIO)
                with gr.Accordion("Perguntas frequentes", open=False):
                    gr.Markdown(AJUDA_PERGUNTAS)

        # ====================== LIGAÇÃO DOS EVENTOS ======================
        entradas_gerais = [busca_produto, so_baixo, filtro_status, sel_editar, sel_estoque,
                           sel_produto_pedido, sel_pedido]
        saidas_gerais = [cartoes, boas_vindas, resumo_baixo_dash, tabela_baixo_dash,
                         aviso_produtos, tabela_prod, sel_editar, sel_estoque, tabela_mov,
                         resumo_baixo_estoque, tabela_baixo_estoque, sel_produto_pedido,
                         sel_pedido, aviso_pedidos, tabela_ped, resumo_pedido, tabela_itens]

        def e_depois_atualiza(evento):
            """Depois da ação, atualiza dashboard, tabelas e listas."""
            return evento.then(atualizar_tudo, entradas_gerais, saidas_gerais)

        demo.load(atualizar_tudo, entradas_gerais, saidas_gerais)

        # Dashboard
        e_depois_atualiza(botao_demo.click(acao_carregar_demo, None, msg_demo))
        tabela_baixo_dash.select(acao_abrir_reposicao, None, [abas, sel_estoque, tipo_mov])

        # Produtos: cadastro (botão ou Enter no último campo)
        cad_codigo.change(dica_codigo, cad_codigo, dica_cod)
        for gatilho in (botao_cadastrar.click, cad_minimo.submit):
            e_depois_atualiza(gatilho(
                acao_cadastrar_produto,
                [cad_codigo, cad_nome, cad_categoria, cad_preco, cad_quantidade, cad_minimo],
                [msg_cadastro, cad_codigo, cad_nome, cad_preco, cad_quantidade, cad_minimo]))

        # Produtos: pesquisa, filtro e seleção por clique
        for gatilho in (busca_produto.change, so_baixo.change):
            gatilho(acao_filtrar_produtos, [busca_produto, so_baixo], [aviso_produtos, tabela_prod])
        tabela_prod.select(acao_selecionar_produto_tabela, None, [sel_editar, acordeao_editar])

        # Produtos: edição
        saidas_form_edicao = [ed_codigo, ed_nome, ed_categoria, ed_preco, ed_minimo, msg_edicao]
        sel_editar.change(acao_carregar_produto, sel_editar, saidas_form_edicao)
        sel_editar.change(fechar_painel_exclusao, None, [painel_exclusao, estado_exclusao])
        botao_descartar.click(acao_carregar_produto, sel_editar, saidas_form_edicao)
        e_depois_atualiza(botao_salvar.click(
            acao_editar_produto,
            [sel_editar, ed_codigo, ed_nome, ed_categoria, ed_preco, ed_minimo], msg_edicao))

        # Produtos: exclusão em dois passos
        botao_excluir.click(pedir_exclusao_produto, sel_editar,
                            [msg_edicao, painel_exclusao, texto_exclusao, estado_exclusao])
        e_depois_atualiza(botao_sim_excluir.click(
            executar_exclusao_produto, estado_exclusao, [msg_edicao, painel_exclusao, estado_exclusao]))
        botao_nao_excluir.click(cancelar_exclusao_produto, None,
                                [msg_edicao, painel_exclusao, estado_exclusao])

        # Estoque
        entradas_dica_mov = [sel_estoque, tipo_mov, qtd_mov]
        for componente in (sel_estoque, tipo_mov, qtd_mov):
            componente.change(dica_movimentacao, entradas_dica_mov, dica_mov)
        for gatilho in (botao_mov.click, motivo_mov.submit):
            e_depois_atualiza(gatilho(
                acao_movimentar_estoque, [sel_estoque, tipo_mov, qtd_mov, motivo_mov],
                [msg_mov, motivo_mov])).then(dica_movimentacao, entradas_dica_mov, dica_mov)

        # Pedidos: montagem do carrinho
        saidas_carrinho = [carrinho, tabela_carrinho, total_pedido, sel_remover, msg_novo]
        for gatilho in (botao_adicionar.click, qtd_pedido.submit):
            gatilho(acao_adicionar_item, [carrinho, sel_produto_pedido, qtd_pedido], saidas_carrinho)
        botao_remover.click(acao_remover_item, [carrinho, sel_remover], saidas_carrinho)
        botao_limpar.click(acao_limpar_carrinho, None, saidas_carrinho)
        e_depois_atualiza(botao_criar.click(
            acao_criar_pedido, [cliente, carrinho], saidas_carrinho + [cliente]))

        # Pedidos: consulta, seleção por clique e confirmação em dois passos
        sel_pedido.change(detalhar_pedido, sel_pedido, [resumo_pedido, tabela_itens])
        sel_pedido.change(fechar_painel_pedido, None, [painel_pedido, estado_pedido])
        tabela_ped.select(acao_selecionar_pedido_tabela, None, sel_pedido)
        saidas_pedir = [msg_gerenciar, painel_pedido, texto_pedido, estado_pedido, botao_sim_pedido]
        botao_confirmar.click(pedir_confirmar_pedido, sel_pedido, saidas_pedir)
        botao_cancelar.click(pedir_cancelar_pedido, sel_pedido, saidas_pedir)
        e_depois_atualiza(botao_sim_pedido.click(
            executar_acao_pedido, estado_pedido, [msg_gerenciar, painel_pedido, estado_pedido]))
        botao_nao_pedido.click(voltar_acao_pedido, None, [msg_gerenciar, painel_pedido, estado_pedido])
        filtro_status.change(acao_filtrar_pedidos, filtro_status, [aviso_pedidos, tabela_ped])

        # Relatórios (também atualizam ao abrir a aba)
        saidas_relatorios = [grafico_estoque, grafico_vendas, resumo_periodo,
                             tabela_periodo, grafico_periodo, tabela_baixo_rel]
        for gatilho in (botao_relatorios.click, aba_relatorios.select, rel_inicio.submit, rel_fim.submit):
            gatilho(acao_gerar_relatorios, [rel_inicio, rel_fim], saidas_relatorios)

    return demo


if __name__ == "__main__":
    db.criar_banco()  # cria o arquivo estoquefacil.db na primeira execução
    interface = criar_interface()
    interface.launch(inbrowser=True, theme=gr.themes.Soft(), css=CSS)

"""
testes_interface.py — Testa as telas e mensagens do EstoqueFácil (sem abrir o navegador).

Como rodar (na pasta do projeto, com o ambiente virtual ativado):
    python testes_interface.py

Cada linha mostra OK ou FALHA. Usa um banco TEMPORÁRIO: o seu estoquefacil.db NÃO é alterado.
O clique em linhas de tabela é simulado; o comportamento no navegador deve ser conferido
manualmente (veja a lista de testes manuais no README).
"""
import re
import sys
import tempfile
import types
from pathlib import Path

import gradio as gr

import database as db

_pasta_temporaria = tempfile.TemporaryDirectory()
db.CAMINHO_BANCO = Path(_pasta_temporaria.name) / "teste_interface.db"

import app  # noqa: E402  (importado depois de apontar para o banco temporário)

db.criar_banco()
demo = app.criar_interface()
_, url, _ = demo.launch(prevent_thread_lock=True, theme=gr.themes.Soft(), css=app.CSS, quiet=True)
from gradio_client import Client
c = Client(url, verbose=False)
eps = c.view_api(return_format="dict")["named_endpoints"]
def ep(n): return [k for k in eps if k.startswith("/"+n)][0]
txt = lambda h: re.sub(r"<[^>]+>", " ", h)
falhas = []
def ok(cond, nome):
    print(("OK   " if cond else "FALHA"), nome)
    if not cond:
        falhas.append(nome)

# banco vazio: boas-vindas + avisos de lista vazia
r = c.predict("", False, "Todos", None, None, None, None, api_name="/atualizar_tudo")
ok("Bem-vindo" in r[1], "boas-vindas com banco vazio")
ok("Nenhum produto cadastrado" in r[4], "aviso de lista de produtos vazia")
ok("Nenhum pedido criado" in r[13], "aviso de lista de pedidos vazia")
ok("tudo certo" in txt(r[2]).lower() or "Tudo certo" in r[2], "resumo estoque baixo vazio")

# decimal agora é rejeitado (antes arredondava em silêncio)
m = c.predict("Q1","Decimal","Outros",3,2.5,1, api_name=ep("acao_cadastrar_produto"))[0]
ok("inteiro" in m and "msg-erro" in m and db.buscar_produtos("Q1").empty, "quantidade 2.5 recusada com explicação")
m = c.predict("Q1","Neg","Outros",-3,1,1, api_name=ep("acao_cadastrar_produto"))[0]
ok("negativo" in m and "Digite 0" in m, "preço negativo recusado com como resolver")
m = c.predict("Q1","Ok","Outros",3,4,1, api_name=ep("acao_cadastrar_produto"))[0]
ok("msg-sucesso" in m and "Estoque inicial: 4" in m, "cadastro com sucesso + próximo passo")
m = c.predict("q1","Dup","Outros",3,4,1, api_name=ep("acao_cadastrar_produto"))[0]
ok("msg-erro" in m and "edite o produto existente" in m, "código duplicado orienta o que fazer")
ok("já pertence" in c.predict("q1", api_name=ep("dica_codigo")), "dica em tempo real de código duplicado")
ok("disponível" in c.predict("ZZ9", api_name=ep("dica_codigo")), "dica: código disponível")

pid = db.buscar_produtos("Q1").iloc[0]["id"].item()
c.predict("", False, "Todos", None, None, None, None, api_name="/atualizar_tudo")  # atualiza as listas da sessão, como a tela faz
d = lambda *a: txt(c.predict(*a, api_name=ep("dica_movimentacao")))
ok("depois da saída: 1" in d(pid,"Saída",3), "prévia da saída (4 → 1)")
ok("não será permitida" in d(pid,"Saída",9), "aviso antes de saída maior que o estoque")
ok("depois da entrada: 9" in d(pid,"Entrada",5), "prévia da entrada (4 → 9)")
ok("inteira" in d(pid,"Entrada",1.5), "prévia recusa decimal")

# Pedido + confirmação em dois passos (chamando os handlers diretamente)
car, tab, tot, rem, msg = app.acao_adicionar_item([], pid, 3)
ok("msg-sucesso" in msg, "adicionar item")
car, tab, tot, rem, msg = app.acao_adicionar_item(car, pid, 3)   # 6 > 4
ok("msg-aviso" in msg and "só poderá confirmá-lo" in msg, "aviso de estoque ao adicionar")
car, tab, tot, rem, msg = app.acao_remover_item(car, None)
ok("msg-aviso" in msg, "remover sem escolher item avisa")
car, tab, tot, rem, msg = app.acao_remover_item(car, pid)
ok(car == [] and "msg-sucesso" in msg, "remover item específico")
car, *_ = app.acao_adicionar_item([], pid, 3)
car, tab, tot, rem, msg, cli = app.acao_criar_pedido("Maria", car)
ped = int(db.listar_pedidos().iloc[0]["id"])
ok("Pendente" in msg and "Pedidos feitos" in msg, "criar pedido orienta próximo passo")

msg, painel, texto, estado, botao = app.pedir_confirmar_pedido(ped)
ok(estado == {"acao":"confirmar","pedido_id":ped} and "estoque 4 → 1" in txt(texto), "passo 1: resumo mostra 4 → 1")
ok(db.obter_produto(pid)["quantidade"] == 4, "passo 1 NÃO altera o estoque")
m2, _, est2 = app.voltar_acao_pedido()
ok("Nada foi alterado" in m2 and est2 is None and db.obter_produto(pid)["quantidade"] == 4, "'Não, voltar' não altera nada")
msg, painel, texto, estado, botao = app.pedir_confirmar_pedido(ped)
m3, _, _ = app.executar_acao_pedido(estado)
ok("confirmado" in m3 and db.obter_produto(pid)["quantidade"] == 1, "passo 2: confirma e baixa estoque")
m4, *_ = app.executar_acao_pedido(estado)   # clique repetido com o mesmo estado
ok("msg-erro" in m4 and db.obter_produto(pid)["quantidade"] == 1, "clique repetido não baixa de novo")
msg, painel, texto, estado, botao = app.pedir_confirmar_pedido(ped)
ok("msg-erro" in msg and estado is None, "pedido já confirmado nem abre painel de confirmar")

msg, painel, texto, estado, botao = app.pedir_cancelar_pedido(ped)
ok("estoque 1 → 4" in txt(texto) and "não pode ser desfeita" in txt(texto), "cancelar mostra devolução 1 → 4 e alerta")
ok(db.obter_produto(pid)["quantidade"] == 1, "abrir cancelamento não altera estoque")
m5, *_ = app.executar_acao_pedido(estado)
ok(db.obter_produto(pid)["quantidade"] == 4 and "voltaram ao estoque" in m5, "cancelamento restaura estoque")

# Pedido sem estoque: não abre painel e explica
car, *_ = app.acao_adicionar_item([], pid, 99)
car, *_x = app.acao_criar_pedido("João", car)
ped2 = int(db.listar_pedidos().iloc[0]["id"])
msg, painel, texto, estado, botao = app.pedir_confirmar_pedido(ped2)
ok("Estoque insuficiente" in msg and "aba Estoque" in msg and estado is None, "sem estoque: explica e orienta")

# Exclusão em dois passos
novo = db.cadastrar_produto("DEL1","Descartável","Outros",1,0,0)
msg, painel, texto, estado = app.pedir_exclusao_produto(novo)
ok(estado == {"produto_id": novo} and db.obter_produto(novo) is not None, "excluir passo 1: pede confirmação, nada apagado")
m6, *_ = app.cancelar_exclusao_produto()
ok(db.obter_produto(novo) is not None, "'Não, voltar' mantém o produto")
m7, *_ = app.executar_exclusao_produto(estado)
ok(db.obter_produto(novo) is None and "excluído" in m7, "excluir passo 2 apaga")
msg, painel, texto, estado = app.pedir_exclusao_produto(pid)
ok("msg-aviso" in msg and estado is None, "produto com pedidos: avisa antes de pedir confirmação")

# Cliques em linhas (SelectData simulado)
ev = types.SimpleNamespace(row_value=["Q1"])
sel, acord = app.acao_selecionar_produto_tabela(ev)
ok(sel == pid, "clique na tabela de produtos seleciona o produto")
abas, sel2, tipo = app.acao_abrir_reposicao(ev)
ok(sel2 == pid and tipo == "Entrada", "clique no estoque baixo abre entrada de estoque")
ok(app.acao_selecionar_pedido_tabela(types.SimpleNamespace(row_value=[ped])) == ped, "clique em pedido do histórico")

# Edição: carregar e descartar
r = app.acao_carregar_produto(pid)
ok(r[0] == "Q1" and "Editando" in r[5], "carregar produto para edição avisa o que está editando")

# Tabelas em formato brasileiro
t = app.tabela_produtos(db.buscar_produtos())
ok(t.iloc[0]["Preço"].startswith("R$ 3,00") and "ID" not in t.columns, "tabela: R$ 3,00 e sem coluna ID técnica")

# Filtro 'só estoque baixo' e demo
db.registrar_movimentacao(pid, "Saída", 4)
aviso_l, tab_l = app.acao_filtrar_produtos("", True)
ok(len(tab_l) == 1, "filtro só estoque baixo")
r = c.predict("", False, "Todos", None, None, None, None, api_name="/atualizar_tudo")
ok(len(r) == 17, "atualizar_tudo devolve 17 saídas")

# Relatórios via API e erro de data
r = c.predict("01/10/2026", "04/11/2026", api_name=ep("acao_gerar_relatorios"))
ok(r[3] is not None, "relatórios geram")
r = c.predict("xx", "04/11/2026", api_name=ep("acao_gerar_relatorios"))
ok("msg-erro" in r[2] and "DD/MM/AAAA" in r[2], "data inválida explica o formato")
demo.close()
_pasta_temporaria.cleanup()
print()
print("TODOS OS TESTES PASSARAM" if not falhas else f"{len(falhas)} TESTE(S) FALHARAM")
sys.exit(1 if falhas else 0)

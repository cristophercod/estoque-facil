"""
testes_automaticos.py — Testa as regras de produtos, estoque e pedidos.

Como rodar (na pasta do projeto, com o ambiente virtual ativado):
    python testes_automaticos.py

Os testes usam um banco TEMPORÁRIO: o seu estoquefacil.db NÃO é alterado.
"""

import tempfile
import unittest
from pathlib import Path

import database as db
import relatorios
from dados_demo import carregar_dados_demonstracao


class TestesEstoqueFacil(unittest.TestCase):
    def setUp(self):
        # Cada teste começa com um banco novo e vazio
        self.pasta = tempfile.TemporaryDirectory()
        db.CAMINHO_BANCO = Path(self.pasta.name) / "teste.db"
        db.criar_banco()

    def tearDown(self):
        self.pasta.cleanup()

    def estoque(self, produto_id):
        return db.obter_produto(produto_id)["quantidade"]

    def novo_produto(self, codigo="A1", quantidade=10, preco=5.0, minimo=2):
        return db.cadastrar_produto(codigo, f"Produto {codigo}", "Teste", preco, quantidade, minimo)

    # ---------------- Produtos ----------------
    def test_cadastro_e_busca(self):
        self.novo_produto("ARROZ1")
        self.assertEqual(len(db.buscar_produtos("arroz")), 1)
        self.assertEqual(len(db.buscar_produtos("xyz")), 0)

    def test_codigo_duplicado_e_recusado(self):
        self.novo_produto("A1")
        with self.assertRaises(db.ErroDeNegocio):
            self.novo_produto("a1")  # mesmo código, minúsculo

    def test_preco_negativo_e_quantidade_invalida(self):
        with self.assertRaises(db.ErroDeNegocio):
            db.cadastrar_produto("B1", "X", "T", -1, 1, 1)
        with self.assertRaises(db.ErroDeNegocio):
            db.cadastrar_produto("B2", "X", "T", 1, -5, 1)
        with self.assertRaises(db.ErroDeNegocio):
            db.cadastrar_produto("B3", "X", "T", 1, 2.5, 1)
        with self.assertRaises(db.ErroDeNegocio):
            db.cadastrar_produto("B4", "X", "T", 1, None, 1)
        self.assertTrue(db.buscar_produtos().empty)

    def test_editar_e_excluir(self):
        pid = self.novo_produto("A1")
        db.editar_produto(pid, "A9", "Novo nome", "Outra", 7.5, 3)
        self.assertEqual(db.obter_produto(pid)["codigo"], "A9")
        db.excluir_produto(pid)
        self.assertIsNone(db.obter_produto(pid))

    def test_nao_exclui_produto_com_pedido(self):
        pid = self.novo_produto("A1")
        db.criar_pedido("Cliente", [{"produto_id": pid, "quantidade": 1}])
        with self.assertRaises(db.ErroDeNegocio):
            db.excluir_produto(pid)

    # ---------------- Estoque ----------------
    def test_entrada_e_saida(self):
        pid = self.novo_produto(quantidade=10)
        db.registrar_movimentacao(pid, "Entrada", 5, "Compra")
        self.assertEqual(self.estoque(pid), 15)
        db.registrar_movimentacao(pid, "Saída", 4, "Venda")
        self.assertEqual(self.estoque(pid), 11)
        # estoque inicial + entrada + saída
        self.assertEqual(len(db.historico_movimentacoes()), 3)

    def test_saida_maior_que_estoque_e_recusada(self):
        pid = self.novo_produto(quantidade=3)
        with self.assertRaises(db.ErroDeNegocio):
            db.registrar_movimentacao(pid, "Saída", 4)
        self.assertEqual(self.estoque(pid), 3)

    def test_estoque_baixo_usa_limite_de_cada_produto(self):
        self.novo_produto("A1", quantidade=5, minimo=5)    # no limite -> baixo
        self.novo_produto("A2", quantidade=6, minimo=5)    # acima -> ok
        self.novo_produto("A3", quantidade=0, minimo=0)    # zerado -> baixo
        baixo = db.produtos_estoque_baixo()
        self.assertEqual(sorted(baixo["codigo"]), ["A1", "A3"])

    # ---------------- Pedidos ----------------
    def test_pedido_calcula_total_e_nao_mexe_no_estoque_ate_confirmar(self):
        p1 = self.novo_produto("A1", 10, 5.00)
        p2 = self.novo_produto("A2", 10, 2.50)
        pedido = db.criar_pedido("Cliente", [
            {"produto_id": p1, "quantidade": 2}, {"produto_id": p2, "quantidade": 4},
        ])
        self.assertEqual(db.listar_pedidos().iloc[0]["valor_total"], 20.0)
        self.assertEqual(self.estoque(p1), 10)  # ainda não mudou
        self.assertEqual(db.listar_pedidos().iloc[0]["status"], "Pendente")
        self.assertIsNotNone(pedido)

    def test_confirmar_baixa_estoque(self):
        pid = self.novo_produto(quantidade=10)
        pedido = db.criar_pedido("Cliente", [{"produto_id": pid, "quantidade": 4}])
        db.confirmar_pedido(pedido)
        self.assertEqual(self.estoque(pid), 6)

    def test_nao_confirma_duas_vezes(self):
        pid = self.novo_produto(quantidade=10)
        pedido = db.criar_pedido("Cliente", [{"produto_id": pid, "quantidade": 4}])
        db.confirmar_pedido(pedido)
        with self.assertRaises(db.ErroDeNegocio):
            db.confirmar_pedido(pedido)
        self.assertEqual(self.estoque(pid), 6)  # baixou só uma vez

    def test_confirmacao_sem_estoque_nao_altera_nada(self):
        p1 = self.novo_produto("A1", 10)
        p2 = self.novo_produto("A2", 1)
        pedido = db.criar_pedido("Cliente", [
            {"produto_id": p1, "quantidade": 5}, {"produto_id": p2, "quantidade": 3},
        ])
        with self.assertRaises(db.ErroDeNegocio):
            db.confirmar_pedido(pedido)
        self.assertEqual(self.estoque(p1), 10)  # nenhum item foi baixado
        self.assertEqual(self.estoque(p2), 1)
        self.assertEqual(db.listar_pedidos().iloc[0]["status"], "Pendente")

    def test_cancelar_confirmado_restaura_estoque_uma_unica_vez(self):
        pid = self.novo_produto(quantidade=10)
        pedido = db.criar_pedido("Cliente", [{"produto_id": pid, "quantidade": 4}])
        db.confirmar_pedido(pedido)
        self.assertTrue(db.cancelar_pedido(pedido))
        self.assertEqual(self.estoque(pid), 10)
        with self.assertRaises(db.ErroDeNegocio):
            db.cancelar_pedido(pedido)  # segundo cancelamento
        self.assertEqual(self.estoque(pid), 10)
        with self.assertRaises(db.ErroDeNegocio):
            db.confirmar_pedido(pedido)  # cancelado não confirma

    def test_cancelar_pendente_nao_mexe_no_estoque(self):
        pid = self.novo_produto(quantidade=10)
        pedido = db.criar_pedido("Cliente", [{"produto_id": pid, "quantidade": 4}])
        self.assertFalse(db.cancelar_pedido(pedido))
        self.assertEqual(self.estoque(pid), 10)

    def test_pedido_sem_itens_ou_quantidade_invalida(self):
        pid = self.novo_produto()
        with self.assertRaises(db.ErroDeNegocio):
            db.criar_pedido("Cliente", [])
        with self.assertRaises(db.ErroDeNegocio):
            db.criar_pedido("Cliente", [{"produto_id": pid, "quantidade": 0}])

    # ---------------- Indicadores, demonstração e relatórios ----------------
    def test_indicadores_com_banco_vazio(self):
        ind = db.calcular_indicadores()
        self.assertEqual(ind["total_produtos"], 0)
        self.assertEqual(ind["valor_confirmado"], 0)
        self.assertTrue(db.produtos_estoque_baixo().empty)

    def test_indicadores_e_relatorios_com_dados(self):
        pid = self.novo_produto(quantidade=10, preco=5.0)
        pedido = db.criar_pedido("Cliente", [{"produto_id": pid, "quantidade": 2}])
        db.confirmar_pedido(pedido)
        ind = db.calcular_indicadores()
        self.assertEqual(ind["total_unidades"], 8)
        self.assertEqual(ind["valor_confirmado"], 10.0)
        self.assertEqual(relatorios.tabela_mais_vendidos().iloc[0]["unidades"], 2)
        tabela, figura, _ = relatorios.relatorio_pedidos_periodo("01/01/2000", "31/12/2999")
        self.assertEqual(int(tabela.iloc[0]["Confirmados"]), 1)
        self.assertIsNotNone(figura)

    def test_dados_de_demonstracao(self):
        carregar_dados_demonstracao()
        ind = db.calcular_indicadores()
        self.assertEqual(ind["total_produtos"], 12)
        self.assertEqual(ind["total_pedidos"], 10)
        self.assertEqual(ind["pedidos_confirmados"], 8)
        self.assertGreater(ind["estoque_baixo"], 0)
        with self.assertRaises(db.ErroDeNegocio):
            carregar_dados_demonstracao()  # não carrega duas vezes

    # ---------------- Funções de leitura usadas pela interface ----------------
    def test_funcoes_de_leitura_da_interface(self):
        pid = self.novo_produto("ab1", quantidade=5)
        self.assertEqual(db.obter_produto_por_codigo(" AB1 ")["id"], pid)  # ignora espaços e maiúsculas
        self.assertIsNone(db.obter_produto_por_codigo("nao-existe"))
        self.assertFalse(db.produto_tem_pedidos(pid))
        pedido = db.criar_pedido("Cliente", [{"produto_id": pid, "quantidade": 2}])
        self.assertTrue(db.produto_tem_pedidos(pid))
        dados, itens = db.detalhe_pedido(pedido)
        self.assertEqual(dados["status"], "Pendente")
        self.assertEqual(int(itens.iloc[0]["disponivel"]), 5)
        with self.assertRaises(db.ErroDeNegocio):
            db.detalhe_pedido(9999)

    def test_mensagens_de_erro_dizem_como_resolver(self):
        self.novo_produto("A1", quantidade=3)
        with self.assertRaises(db.ErroDeNegocio) as erro:
            self.novo_produto("A1")
        self.assertIn("edite o produto existente", str(erro.exception))

    def test_periodo_invalido(self):
        with self.assertRaises(db.ErroDeNegocio):
            relatorios.relatorio_pedidos_periodo("abc", "01/01/2025")
        with self.assertRaises(db.ErroDeNegocio):
            relatorios.relatorio_pedidos_periodo("02/01/2025", "01/01/2025")


if __name__ == "__main__":
    unittest.main(verbosity=2)

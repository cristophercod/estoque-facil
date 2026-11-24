# EstoqueFácil — Explicação Acadêmica

Matemática Computacional Aplicada · ADS · 2º semestre · UniCuritiba

## 1. Qual problema real o EstoqueFácil resolve?

Muitas pequenas lojas controlam produtos e pedidos em **cadernos ou planilhas**. Isso causa:

- erros de digitação e contas feitas à mão;
- informações perdidas ou desatualizadas;
- produtos que acabam sem ninguém perceber;
- dificuldade para saber o que mais vende e quanto foi vendido.

O EstoqueFácil junta tudo em um só lugar: cadastra produtos, atualiza o estoque sozinho a cada venda, avisa quando um produto está acabando e mostra gráficos e totais.

## 2. Público-alvo

Donos e atendentes de pequenos comércios (mercearias, papelarias, lojas de bairro) que não têm conhecimento técnico e precisam de uma ferramenta simples, gratuita e que funcione no próprio computador.

## 3. Como o sistema funciona (visão geral)

```
 Navegador (Gradio)  ──►  app.py  ──►  database.py  ──►  estoquefacil.db (SQLite)
   telas e botões          chama        regras e SQL          dados salvos
                            │
                            └────►  relatorios.py  (Pandas + Matplotlib)
```

1. O usuário clica em um botão na tela (**Gradio**).
2. O `app.py` chama uma função do `database.py` (ou do `relatorios.py`).
3. A função valida os dados, grava/lê no **SQLite** e devolve o resultado.
4. O `app.py` mostra a mensagem, as tabelas e os cartões atualizados.

## 4. Como cada tecnologia é usada

**Python** — linguagem de todo o projeto. Usamos funções pequenas (cada uma faz uma coisa), listas, dicionários, `try/except` para tratar erros e uma exceção própria (`ErroDeNegocio`) para mensagens como "estoque insuficiente".

**Gradio** — cria a interface web sem precisar escrever HTML. `gr.Blocks` é a página; `gr.Tab` cria as abas; `gr.Textbox`, `gr.Number` e `gr.Dropdown` são os campos; `gr.Button` são os botões; `gr.Dataframe` mostra tabelas e `gr.Plot` mostra gráficos. Cada botão é ligado a uma função com `botao.click(funcao, entradas, saidas)`: os valores dos campos de *entrada* vão para a função, e o retorno dela preenche os componentes de *saída*. Depois de cada ação, `.then(atualizar_tudo, ...)` recarrega dashboard, tabelas e listas — por isso os indicadores atualizam sozinhos.

**SQLite** — banco de dados em um único arquivo (`estoquefacil.db`), criado automaticamente. Possui 4 tabelas:

| Tabela | Guarda | Relacionamento |
|---|---|---|
| `produtos` | código (único), nome, categoria, preço, quantidade, estoque mínimo | — |
| `pedidos` | cliente, status, valor total, datas | — |
| `itens_pedido` | produto, quantidade e preço de cada item | `pedido_id` → `pedidos`; `produto_id` → `produtos` |
| `movimentacoes` | entradas e saídas de estoque (histórico) | `produto_id` → `produtos`; `pedido_id` → `pedidos` |

As regras `CHECK` do banco (`preco >= 0`, `quantidade >= 0`) são uma segunda barreira contra dados inválidos. Todas as consultas usam **parâmetros** (`WHERE id = ?`), nunca texto colado no SQL, o que evita *SQL Injection*.

**Pandas** — as consultas de leitura viram **DataFrames** (`pd.read_sql_query`). Com eles:
- filtramos produtos com estoque baixo: `df[df["quantidade"] <= df["estoque_minimo"]]`;
- calculamos indicadores: `.sum()`, `len()`;
- somamos vendas por produto: `groupby(...).agg(...)`;
- montamos o relatório por período com `pivot_table` (contagem de pedidos por dia e status);
- pegamos os maiores estoques com `nlargest`.

**Matplotlib** — gera os três gráficos a partir dos DataFrames: barras horizontais de maior estoque, barras horizontais de mais vendidos e barras verticais do valor confirmado por dia. Os dados são sempre os do banco, nunca valores fixos; se não houver dados, aparece um aviso no lugar do gráfico.

## 5. Principais funções do código

| Arquivo | Função | O que faz |
|---|---|---|
| `database.py` | `criar_banco()` | Cria as tabelas na primeira execução |
| | `transacao()` | Garante "tudo ou nada" nas operações de escrita |
| | `consultar(sql, params)` | Executa um SELECT e devolve um DataFrame |
| | `cadastrar_produto / editar_produto / excluir_produto` | CRUD de produtos com validações |
| | `buscar_produtos(termo)` | Pesquisa por nome ou código |
| | `registrar_movimentacao(...)` | Entrada/saída de estoque (recusa saída maior que o saldo) |
| | `produtos_estoque_baixo()` | Filtra com Pandas os produtos no limite ou abaixo do mínimo |
| | `criar_pedido / confirmar_pedido / cancelar_pedido` | Ciclo de vida do pedido |
| | `calcular_indicadores()` | Números do dashboard |
| `relatorios.py` | `grafico_maior_estoque()`, `grafico_mais_vendidos()` | Gráficos de barras |
| | `relatorio_pedidos_periodo(inicio, fim)` | Tabela e gráfico por período |
| `app.py` | `criar_interface()` | Monta abas, campos, botões e liga os eventos |
| | `atualizar_tudo(...)` | Recarrega a tela inteira após cada operação |

## 6. Como o estoque é atualizado após um pedido

Um pedido passa por três situações: **Pendente → Confirmado → Cancelado**.

**Criar pedido:** grava o pedido e seus itens como *Pendente*, com o preço do produto naquele momento. O estoque **não** muda.

**Confirmar pedido** (`confirmar_pedido`), tudo dentro de **uma transação**:
1. Confere se o pedido está *Pendente* (senão, recusa).
2. Confere **todos** os itens: se algum tem quantidade maior que o estoque, recusa o pedido inteiro, sem baixar nada.
3. Muda o status para *Confirmado* usando `UPDATE ... WHERE id = ? AND status = 'Pendente'`.
4. Para cada item, subtrai do estoque e grava uma *Saída* no histórico.
5. Se qualquer passo falhar, o `ROLLBACK` desfaz tudo.

**Cancelar pedido** (`cancelar_pedido`):
- se estava *Confirmado*: devolve cada item ao estoque e grava uma *Entrada* ("Cancelamento do pedido #N");
- se estava *Pendente*: apenas muda o status (o estoque nunca foi alterado);
- se já estava *Cancelado*: recusa.

**Por que o estoque nunca é atualizado duas vezes?** A troca de status só acontece se o pedido ainda estiver no status esperado, e isso é feito dentro da transação. A segunda tentativa de confirmar (ou cancelar) encontra um status diferente, é recusada, e o estoque permanece correto. Os testes `test_nao_confirma_duas_vezes` e `test_cancelar_confirmado_restaura_estoque_uma_unica_vez` verificam isso.

## 7. Conteúdos da disciplina aplicados (e onde aparecem)

| Conteúdo | Onde aparece no sistema | Como funciona |
|---|---|---|
| **Banco de dados** | `database.py` (tabelas, `INSERT`/`UPDATE`/`SELECT`/`DELETE`, `JOIN`, transações) | Guarda produtos, pedidos, itens e movimentações de forma permanente e relacionada. Usa chaves primárias, chaves estrangeiras, restrições `CHECK` e consultas parametrizadas. |
| **DataFrames com Pandas** | `buscar_produtos`, `produtos_estoque_baixo`, `calcular_indicadores`, `itens_do_pedido`, `tabela_mais_vendidos`, `relatorio_pedidos_periodo` | Os resultados do banco viram tabelas em memória, que filtramos (`df[condição]`), somamos (`.sum()`), agrupamos (`groupby`), reorganizamos (`pivot_table`) e ordenamos (`nlargest`, `sort_values`). |
| **Gráficos com Matplotlib** | `relatorios.py` e aba **Relatórios** | Transforma os DataFrames em gráficos de barras (maior estoque, mais vendidos, valor por dia) que mudam conforme os dados cadastrados. |

Além desses três, o projeto usa **estruturas de dados** (listas e dicionários para o carrinho de pedido) e **cálculos matemáticos** (subtotal = quantidade × preço, total do pedido, somas e contagens).

## 8. Possíveis melhorias futuras (não implementadas, para manter o projeto simples)

Login de usuários, cadastro de clientes e fornecedores, exportação para Excel/PDF, leitura de código de barras.

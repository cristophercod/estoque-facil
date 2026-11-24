# EstoqueFácil — Avaliação de Usabilidade (10 heurísticas de Nielsen)

Método: leitura do código (`app.py`, `database.py`) + testes na interface rodando (via API do Gradio) antes de qualquer mudança.
Escala: **Aplicada** · **Parcialmente aplicada** · **Não aplicada**.

## Etapa 1 — Avaliação ANTES das melhorias

| # | Heurística | Status | Onde aparece | Problema encontrado | Melhoria recomendada |
|---|---|---|---|---|---|
| 1 | Visibilidade do estado do sistema | Parcial | Mensagens `✅`/`❌` em texto simples após cada ação; cartões do Dashboard atualizados por `atualizar_tudo` | Mensagens sem cor nem hora (não dá para saber se são novas); "Último item removido." e "Pedido em branco." sem ícone; sem estoque atual antes de movimentar; sem resumo do pedido selecionado; tabelas vazias sem texto algum | Caixas de mensagem padronizadas com ícone e hora; prévia do estoque; resumo do pedido; textos de estado vazio |
| 2 | Correspondência com o mundo real | Parcial | Termos Entrada/Saída, Pendente/Confirmado, Unidades | Coluna **ID** técnica na tabela de produtos; valores como `12.50` (tabelas e lista de pedidos) em vez de `R$ 12,50`; "Pendente" não é explicado em lugar nenhum | Remover ID; formato brasileiro de moeda; glossário |
| 3 | Controle e liberdade | Parcial | "Remover último item", "Limpar pedido", editar produto, cancelar pedido | **Cancelar pedido** (irreversível) executava na hora; só dava para remover o *último* item; sem "descartar" na edição; sem como desfazer uma movimentação | Confirmação ao cancelar; remover item específico; descartar alterações; orientar a correção por movimento contrário |
| 4 | Consistência e padrões | Parcial | Rótulos dos botões | Emojis em 3 de 12 botões; mensagens com e sem ícone; títulos misturados (`⚠️`, `1)`, sem marcador); dinheiro em dois formatos | Um padrão único de botões, mensagens, títulos e moeda |
| 5 | Prevenção de erros | Parcial | Validações em `database.py` (CHECK, saída ≤ estoque, status do pedido) — **confirmadas pelos testes** | Tudo era bloqueado só **depois** do clique; campo de quantidade com `precision=0` **arredondava 2.5 para 2 sem avisar** (comprovado: produto foi cadastrado com 2); confirmar pedido sem nenhuma confirmação; código duplicado só detectado ao enviar | Dicas em tempo real; confirmação com resumo; recusar decimais com explicação |
| 6 | Reconhecimento em vez de memorização | Parcial | Listas mostram código, nome e estoque; pedidos mostram cliente, status e total | Lista de produtos do pedido não mostrava o preço; para editar era preciso achar o produto na lista, sem clicar na tabela | Preço na lista de pedido; clique na linha para editar/selecionar |
| 7 | Flexibilidade e eficiência | Parcial | Pesquisa por nome/código; filtro de status de pedidos | Sem filtro de estoque baixo na lista; sem Enter para enviar; repor um produto com estoque baixo exigia navegar e procurar o produto | Filtro "só estoque baixo"; Enter nos campos finais; clique no estoque baixo abre a entrada de estoque |
| 8 | Estética e design minimalista | Parcial | Abas, acordeões (edição e demonstração) | Aba Pedidos com 3 seções numa página só; coluna ID; textos de seção com marcadores diferentes | Dividir Pedidos em duas sub-abas; remover ID; padronizar títulos |
| 9 | Ajuda para diagnosticar e corrigir erros | Parcial | Mensagens de `ErroDeNegocio` | Várias mensagens diziam o quê, mas não **como resolver**; erro inesperado genérico sem orientação | Acrescentar o próximo passo às mensagens; orientação no erro inesperado |
| 10 | Ajuda e documentação | **Não aplicada** (na tela) | Só o README, fora do programa | Nenhum texto de apoio no app: 0 campos com `info=`, sem aba de ajuda, sem orientação para o primeiro uso | Aba Ajuda, textos de apoio nos campos, boas-vindas |

## Etapa 2 — O que foi alterado

### `app.py` (reescrito, mesmas funcionalidades)
- **Mensagens padronizadas** (`mensagem`, `sucesso`, `aviso`, `nota`, `erro`): caixa colorida com ícone, hora e texto de próximo passo; erros e avisos com `role="alert"`.
- **Confirmação em dois passos** para excluir produto, confirmar pedido e cancelar pedido: aparece um resumo (ex.: *estoque 4 → 1*) e só o botão "Sim, …" executa. "Não, voltar" não altera nada. A confirmação guarda o pedido/produto mostrado no resumo, então trocar a seleção fecha o painel e não dá para confirmar o item errado.
- **Dicas em tempo real:** código duplicado ao digitar; estoque atual e estoque resultante antes de registrar entrada/saída.
- **Textos de apoio** (`info=`) nos campos, **estados vazios** ("Nenhum produto cadastrado ainda…"), contador "Mostrando X de Y" e **boas-vindas** quando não há produtos.
- **Aba Ajuda:** passo a passo, glossário e perguntas frequentes.
- **Consistência:** botões "Verbo + objeto" sem emojis (azul = principal, vermelho = destrutivo); títulos padronizados; moeda `R$ 1.234,50` em tabelas, listas, cartões e relatórios; coluna técnica **ID** removida.
- **Controle:** remover item específico do pedido, "Descartar alterações" na edição.
- **Eficiência:** filtro "Mostrar só estoque baixo"; Enter envia o cadastro, o item do pedido e a movimentação; clique em linha para editar produto, selecionar pedido e repor produto com estoque baixo.
- **Organização:** Pedidos dividido nas sub-abas *Novo pedido* e *Pedidos feitos*; preço e estoque na lista de produtos do pedido.
- **Quantidades inteiras:** campos numéricos sem `precision=0`, para que decimais sejam recusados com explicação em vez de arredondados em silêncio.

### `database.py` — **nenhuma regra de estoque, pedido ou transação foi alterada**
- Mensagens de erro: apenas **texto** (acrescentado o que fazer a seguir).
- 3 funções novas, **somente leitura**: `obter_produto_por_codigo`, `produto_tem_pedidos`, `detalhe_pedido` (alimentam dicas e resumos).
- `_numero_inteiro` renomeada para `numero_inteiro` (já havia ocorrido antes) e usada pela interface.

### `relatorios.py`
- Resumo do período em texto simples (a interface agora monta a caixa de mensagem).

### Testes
- `testes_automaticos.py`: de 19 para **21** testes (funções de leitura e mensagens).
- `testes_interface.py` (novo): 40+ verificações das telas, mensagens, dicas e confirmações.
- `README.md`: lista de testes manuais ampliada para 31 itens e **correção do teste de quantidade decimal**, que antes descrevia um comportamento que o sistema não tinha.

## Etapa 3 — Como cada melhoria atende as heurísticas

| # | Heurística | Status depois | Como é atendida |
|---|---|---|---|
| 1 | Visibilidade | **Aplicada** | Toda ação mostra caixa com ícone, cor e hora; prévia do estoque; resumo do pedido selecionado; contador de resultados; estados vazios; cartões atualizam sozinhos |
| 2 | Mundo real | **Aplicada** | Reais no formato brasileiro, sem ID técnico, glossário na Ajuda, mensagens em linguagem de loja |
| 3 | Controle e liberdade | **Parcial** | Confirmações com "Não, voltar", remover item específico, limpar pedido, descartar alterações. Falta desfazer de verdade (ver abaixo) |
| 4 | Consistência | **Aplicada** | Mesmo padrão de botões, mensagens, títulos e moeda em todas as abas |
| 5 | Prevenção de erros | **Parcial** | Dicas antes do clique, confirmações, decimais recusados, bloqueios do banco mantidos. Falta destacar o campo com problema (ver abaixo) |
| 6 | Reconhecimento | **Aplicada** | Listas com código, nome, preço e estoque; clique na linha em vez de procurar na lista; resumo do que será alterado antes de confirmar |
| 7 | Flexibilidade | **Aplicada** | Pesquisa, filtro de estoque baixo, filtro de status, Enter, repor com um clique |
| 8 | Minimalismo | **Parcial** | Pedidos em sub-abas, ID removido. A tabela de estoque baixo continua em 3 abas (ver abaixo) |
| 9 | Diagnóstico de erros | **Aplicada** | Mensagens dizem o que houve e o próximo passo; erro inesperado orienta a tentar de novo |
| 10 | Ajuda | **Aplicada** | Aba Ajuda, textos de apoio nos campos, boas-vindas no primeiro uso |

## Heurísticas ainda não totalmente atendidas (e por quê)

- **3 — Controle e liberdade:** não existe "desfazer" real para movimentações de estoque, confirmação ou cancelamento de pedido. Criar um estorno/reabertura de pedido mudaria as regras de estoque e pedidos, que você pediu para não alterar sem necessidade. Mitigação atual: confirmação com resumo antes de agir e orientação na Ajuda (corrigir com a movimentação contrária).
- **5 — Prevenção de erros:** os campos numéricos ainda aceitam digitar valores inválidos (ex.: negativo); o bloqueio e a explicação vêm ao clicar, e o campo com problema não é destacado em vermelho. O Gradio não oferece validação por campo sem JavaScript personalizado, o que complicaria o projeto.
- **8 — Minimalismo:** a tabela de estoque baixo aparece no Dashboard, em Estoque e em Relatórios. Isso é intencional, porque o enunciado do trabalho pede essa informação nos três contextos (indicador, consulta de estoque e relatório).

## O que NÃO foi verificado

- Os testes automáticos cobrem regras, mensagens e fluxos, mas **não abrem navegador**. O clique em linhas de tabela foi testado simulando o evento do Gradio; confirme no navegador (testes manuais 8, 17 e 26 do README).
- Aparência visual (cores das caixas em tema claro/escuro, espaçamentos) e uso com leitor de tela não foram testados.
- Não foi feito teste com usuários reais; esta é uma avaliação heurística, não um teste de usabilidade com pessoas.

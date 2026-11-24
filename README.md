# 📦 EstoqueFácil — Controle de Estoque e Pedidos para Pequena Loja

Projeto da disciplina **Matemática Computacional Aplicada** — ADS, 2º semestre, UniCuritiba (Amostra A3 / ExpoUniCuritiba).

Sistema web que roda **localmente** para cadastrar produtos, controlar estoque, registrar pedidos e gerar relatórios.
Tecnologias: **Python, Gradio, SQLite, Pandas, Matplotlib** (sem Flask, Django ou Streamlit).

## Estrutura

```
estoquefacil/
├── app.py                  # Interface Gradio (abas, formulários, botões)
├── database.py             # SQLite: tabelas, regras de produtos, estoque e pedidos
├── relatorios.py           # Pandas + Matplotlib: análises e gráficos
├── dados_demo.py           # Dados fictícios para demonstração
├── testes_automaticos.py   # 21 testes das regras de negócio
├── testes_interface.py     # testes das telas, mensagens e confirmações
├── requirements.txt
├── README.md
├── EXPLICACAO_ACADEMICA.md # Explicação para o trabalho/apresentação
├── AVALIACAO_USABILIDADE.md # Avaliação com as 10 heurísticas de Nielsen
└── .gitignore
```
O arquivo `estoquefacil.db` é criado **automaticamente** na primeira execução.

## Instalação no Windows

1. Instale o **Python 3.10 ou superior** em https://www.python.org/downloads/ — na primeira tela do instalador, marque **"Add python.exe to PATH"**.
2. Abra a pasta `estoquefacil` no terminal (PowerShell) e execute:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

> Se o PowerShell bloquear a ativação do ambiente virtual, execute uma vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo.
> (No Prompt de Comando use `.venv\Scripts\activate.bat`.)

O navegador abre sozinho em **http://127.0.0.1:7860**. Para encerrar, pressione `Ctrl + C` no terminal.

## Executando no Visual Studio Code

1. **File → Open Folder…** e escolha a pasta `estoquefacil`.
2. Instale a extensão **Python** (Microsoft), se ainda não tiver.
3. **Terminal → New Terminal** e rode os comandos da seção anterior (`python -m venv .venv`, ativar, `pip install -r requirements.txt`).
4. Se o VS Code perguntar sobre o novo ambiente, clique em **Yes**. Ou use `Ctrl+Shift+P` → *Python: Select Interpreter* → escolha o `.venv`.
5. Abra o `app.py` e clique em ▶ **Run Python File**, ou digite `python app.py` no terminal.

## Demonstração rápida 

**Opção A — dados prontos:** aba **Dashboard → Dados de demonstração → Carregar dados de demonstração**. Cria 12 produtos e 10 pedidos fictícios (alguns com estoque baixo).

**Opção B — passo a passo do zero:**

1. **Produtos → Cadastrar:** Código `P100`, Nome `Leite 1L`, Categoria `Alimentos`, Preço `5,50`, Quantidade `20`, Estoque mínimo `5` → **Cadastrar produto**.
2. **Pedidos → Novo pedido:** Cliente `Maria`, produto `P100 — Leite 1L`, quantidade `3` → **Adicionar item** → **Criar pedido** (fica *Pendente*; o estoque ainda é 20).
3. **Pedidos → Pedidos feitos:** escolha o pedido criado → **Confirmar pedido** → leia o resumo (*estoque 20 → 17*) → **Sim, confirmar pedido**. O estoque cai para 17 e aparece uma *Saída* no histórico (aba **Estoque**).
4. **Cancelar pedido** (com o mesmo pedido selecionado) → **Sim, cancelar pedido**: o estoque volta para 20 e aparece uma *Entrada* "Cancelamento do pedido".
5. Confira o **Dashboard** e a aba **Relatórios**.

## Testes

**Automáticos** (usam um banco temporário, seus dados não são afetados). Com o ambiente virtual ativado:

```powershell
python testes_automaticos.py
python testes_interface.py
```
- `testes_automaticos.py`: regras de produtos, estoque e pedidos. Esperado: `Ran 21 tests ... OK`.
- `testes_interface.py`: telas, mensagens, dicas e confirmações em dois passos. Esperado: todas as linhas `OK` e `TODOS OS TESTES PASSARAM`.

**Manuais** (marque cada item ao testar na interface):

| # | Teste | Resultado esperado |
|---|-------|--------------------|
| 1 | Abrir o app com a pasta sem `.db` | Arquivo `estoquefacil.db` é criado; Dashboard mostra zeros e o aviso de boas-vindas |
| 2 | Cadastrar produto válido | Caixa verde com hora; aparece na tabela e nas listas de seleção; formulário é limpo |
| 3 | Digitar no campo Código um código já existente | Aviso aparece na hora, antes de clicar em Cadastrar |
| 4 | Cadastrar com código repetido (ex.: `p100` e `P100`) | Caixa vermelha explicando e como resolver; nada é cadastrado |
| 5 | Cadastrar com preço negativo | Caixa vermelha; nada é cadastrado |
| 6 | Cadastrar com quantidade negativa ou decimal (2.5) | Caixa vermelha ("deve ser um número inteiro"); **não** arredonda em silêncio |
| 7 | Pesquisar por parte do nome/código e marcar "Mostrar só estoque baixo" | Tabela filtra e mostra "Mostrando X de Y" |
| 8 | Clicar em uma linha da tabela de produtos | A área "Editar ou excluir produto" abre com o produto carregado |
| 9 | Editar nome/preço/mínimo → Salvar alterações | Caixa verde; alteração aparece na tabela |
| 10 | Editar campos e clicar em Descartar alterações | Campos voltam aos valores salvos |
| 11 | Excluir produto → **Não, voltar** | Nada é excluído |
| 12 | Excluir produto sem pedidos → **Sim, excluir produto** | Produto removido |
| 13 | Excluir produto que está em pedido | Aviso explicando; nem pede confirmação |
| 14 | Estoque: escolher produto, tipo Saída, quantidade maior que o estoque | Aviso aparece na hora; ao clicar, erro e estoque não muda |
| 15 | Estoque: entrada de 5 unidades | Prévia "estoque atual → depois da entrada"; estoque soma 5; linha "Entrada" no histórico |
| 16 | Deixar um produto com quantidade ≤ estoque mínimo | Aparece em "estoque baixo" (Dashboard, Estoque, Relatórios) |
| 17 | Dashboard: clicar em um produto da tabela de estoque baixo | Abre a aba Estoque com o produto e "Entrada" já escolhidos |
| 18 | Novo pedido com 2 produtos; remover um item pela lista "Item para remover" | Total recalcula; status *Pendente*; estoque inalterado |
| 19 | Pedidos feitos → Confirmar pedido | Mostra resumo (*estoque X → Y*); estoque só muda após **Sim, confirmar pedido** |
| 20 | Confirmar pedido → **Não, voltar** | Nada muda |
| 21 | Confirmar pedido com quantidade maior que o estoque | Mensagem lista o produto e orienta; nenhum item é baixado |
| 22 | Tentar confirmar de novo um pedido já confirmado | Mensagem de erro; estoque **não** diminui de novo |
| 23 | Cancelar pedido *Confirmado* → **Sim, cancelar pedido** | Estoque restaurado; "Entrada" no histórico |
| 24 | Cancelar o mesmo pedido de novo | Mensagem de erro; estoque não muda |
| 25 | Cancelar pedido *Pendente* | Resumo diz que o estoque não será alterado; status *Cancelado* |
| 26 | Clicar em uma linha do histórico de pedidos | O pedido é selecionado e os itens aparecem |
| 27 | Dashboard após cada operação | Cartões atualizados automaticamente |
| 28 | Relatórios (com dados) | Gráficos e tabelas refletem os dados cadastrados |
| 29 | Relatórios com período inválido (ex.: `abc`) | Erro explicando o formato DD/MM/AAAA; gráficos principais continuam |
| 30 | Aba Ajuda | Passo a passo, glossário e perguntas frequentes |
| 31 | Fechar o app (`Ctrl+C`) e abrir de novo | Todos os dados continuam salvos |

## Dados fictícios e privacidade
Todos os dados de demonstração são inventados. Não use dados pessoais reais de clientes.

## Problemas comuns
- **`python` não é reconhecido:** reinstale o Python marcando *Add to PATH* ou use `py app.py`.
- **Porta 7860 ocupada:** feche o outro app ou altere `launch(...)` no final do `app.py` para `launch(server_port=7870, ...)`.
- **Quero zerar tudo:** feche o app e apague o arquivo `estoquefacil.db`.

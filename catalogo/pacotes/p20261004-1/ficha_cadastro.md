# Ficha do produto: Guia Prático de Finanças Pessoais: Do Zero à Organização Mensal

Produto do catálogo `p20261004-1`.

Se a criação por API estiver ligada (`FABRICA_DRY_RUN=false`), o produto já foi criado na Cakto com estes dados e está em `waiting_config`. Se não, cadastre-o na Cakto com estes dados.

**O NOME precisa ficar exatamente assim**: o robô encontra o produto pelo nome (sem diferença de acento ou maiúscula) e então libera o anúncio sozinho.

- Nome: Guia Prático de Finanças Pessoais: Do Zero à Organização Mensal
- Preço: R$ 8,90
- Tipo de entrega: arquivo digital (PDF)
- Arquivo da entrega: `guia-pratico-de-financas-pessoais-do-zero-a-organizacao-mens.pdf` (nesta mesma pasta)

## Descrição da oferta (copie e cole)

Este guia prático em PDF foi elaborado para quem deseja dar os primeiros passos na organização do próprio dinheiro de forma simples e direta. Sem planilhas complicadas ou termos difíceis, você vai aprender a registrar seus gastos com clareza, diferenciar necessidades básicas de despesas supérfluas, planejar uma reserva financeira básica para imprevistos e estabelecer limites semanais de consumo. Cada capítulo traz orientações passo a passo, exemplos práticos do cotidiano e mini-exercícios para colocar o conteúdo em prática imediatamente no seu dia a dia.

## O que vem dentro

- Mapeamento completo das entradas e saídas financeiras
- Separação entre despesas essenciais e estilo de vida
- Construção passo a passo da reserva para imprevistos
- Definição de limites de gastos e rotina de revisão semanal

## Para liberar o anúncio

1. Se o relatório da execução disser que o PDF foi hospedado no Drive, o produto já foi criado ativo e com a entrega configurada: pule para o passo 2. Se não, no painel da Cakto abra o produto, configure a entrega com o PDF acima e **ative** o produto.
2. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos), ou espere a verificação automática de 6 em 6 horas. O robô só libera se o produto estiver **ativo** e a API devolver o link.
3. Se a API não devolver o link, copie o link de compra do painel e rode a ação `definir-link` com o id `p20261004-1` e o link.
4. Só depois disso os robôs de anúncio passam a divulgar o produto.

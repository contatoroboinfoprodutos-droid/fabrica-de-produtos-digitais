# Ficha do produto: Guia Prático de Receitas Fit e Alimentação Saudável – Cardápio e Marmitas

Produto do catálogo `p20261006-1`.

Se a criação por API estiver ligada (`FABRICA_DRY_RUN=false`), o produto já foi criado na Cakto com estes dados e está em `waiting_config`. Se não, cadastre-o na Cakto com estes dados.

**O NOME precisa ficar exatamente assim**: o robô encontra o produto pelo nome (sem diferença de acento ou maiúscula) e então libera o anúncio sozinho.

- Nome: Guia Prático de Receitas Fit e Alimentação Saudável – Cardápio e Marmitas
- Preço: R$ 8,90
- Tipo de entrega: arquivo digital (PDF)
- Arquivo da entrega: `guia-pratico-de-receitas-fit-e-alimentacao-saudavel-cardapio.pdf` (nesta mesma pasta)

## Descrição da oferta (copie e cole)

Um guia de texto simples, dividido em quatro capítulos, que ensina passo a passo como organizar seu cardápio semanal, escolher técnicas de cozimento que preservam nutrientes, substituir ingredientes por opções mais leves e montar marmitas nutritivas para a rotina. Ideal para quem busca praticidade sem abrir mão do sabor e da saúde.

## O que vem dentro

- Planejamento de cardápio semanal fit
- Técnicas de preparo rápido e saudável
- Substituições inteligentes para reduzir calorias
- Montagem de marmitas balanceadas para a semana

## Para liberar o anúncio

1. Se o relatório da execução disser que o PDF foi hospedado no Drive, o produto já foi criado ativo e com a entrega configurada: pule para o passo 2. Se não, no painel da Cakto abra o produto, configure a entrega com o PDF acima e **ative** o produto.
2. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos), ou espere a verificação automática de 6 em 6 horas. O robô só libera se o produto estiver **ativo** e a API devolver o link.
3. Se a API não devolver o link, copie o link de compra do painel e rode a ação `definir-link` com o id `p20261006-1` e o link.
4. Só depois disso os robôs de anúncio passam a divulgar o produto.

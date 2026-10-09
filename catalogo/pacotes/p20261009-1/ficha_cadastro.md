# Ficha do produto: Guia Prático de Inglês para o Dia a Dia

Produto do catálogo `p20261009-1`.

Se a criação por API estiver ligada (`FABRICA_DRY_RUN=false`), o produto já foi criado na Cakto com estes dados e está em `waiting_config`. Se não, cadastre-o na Cakto com estes dados.

**O NOME precisa ficar exatamente assim**: o robô encontra o produto pelo nome (sem diferença de acento ou maiúscula) e então libera o anúncio sozinho.

- Nome: Guia Prático de Inglês para o Dia a Dia
- Preço: R$ 8,90
- Tipo de entrega: arquivo digital (PDF)
- Arquivo da entrega: `guia-pratico-de-ingles-para-o-dia-a-dia.pdf` (nesta mesma pasta)

## Descrição da oferta (copie e cole)

Um guia enxuto, dividido em cinco capítulos, que ensina, passo a passo, as expressões mais usadas no dia a dia em inglês. Cada capítulo traz instruções claras, um exemplo prático e um mini‑exercício para você praticar imediatamente. Ideal para quem quer ganhar confiança ao conversar em situações reais, como cumprimentar, pedir informações, comprar, comer fora ou falar ao telefone. Tudo em texto simples, pronto para download em PDF por apenas R$ 8,90.

## O que vem dentro

- Cumprimentos e apresentações
- Pedindo informações e direções
- Fazendo compras
- No restaurante
- Conversas telefônicas e mensagens

## Para liberar o anúncio

1. Se o relatório da execução disser que o PDF foi hospedado no Drive, o produto já foi criado ativo e com a entrega configurada: pule para o passo 2. Se não, no painel da Cakto abra o produto, configure a entrega com o PDF acima e **ative** o produto.
2. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos), ou espere a verificação automática de 6 em 6 horas. O robô só libera se o produto estiver **ativo** e a API devolver o link.
3. Se a API não devolver o link, copie o link de compra do painel e rode a ação `definir-link` com o id `p20261009-1` e o link.
4. Só depois disso os robôs de anúncio passam a divulgar o produto.

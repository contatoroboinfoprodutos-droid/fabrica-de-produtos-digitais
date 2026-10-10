# Ficha do produto: Manual do Orçamento Familiar: Da Despesa à Rotina

Produto do catálogo `p20261010-3`.

Se a criação por API estiver ligada (`FABRICA_DRY_RUN=false`), o produto já foi criado na Cakto com estes dados e está em `waiting_config`. Se não, cadastre-o na Cakto com estes dados.

**O NOME precisa ficar exatamente assim**: o robô encontra o produto pelo nome (sem diferença de acento ou maiúscula) e então libera o anúncio sozinho.

- Nome: Manual do Orçamento Familiar: Da Despesa à Rotina
- Preço: R$ 19,90
- Tipo de entrega: arquivo digital (PDF)
- Arquivo da entrega: `manual-do-orcamento-familiar-da-despesa-a-rotina.pdf` (nesta mesma pasta)

## Descrição da oferta (copie e cole)

Este guia prático em formato de texto oferece um passo a passo objetivo para organizar as finanças da sua casa. Ao longo de cinco capítulos, você aprenderá a catalogar contas fixas e variáveis, definir critérios justos para dividir despesas entre moradores, estabelecer limites claros por categoria, conduzir reuniões semanais rápidas de alinhamento e planejar manutenções domésticas sem surpresas no fim do mês. Um conteúdo direto, com exemplos aplicáveis e exercícios rápidos para trazer previsibilidade e tranquilidade à rotina financeira da família.

## O que vem dentro

- Mapeamento das despesas fixas e variáveis da casa
- Definição de modelo de divisão de contas no lar
- Criação do teto de gastos por categoria doméstica
- Rotina semanal de conferência e ajustes de despesas
- Planejamento de compras periódicas e reserva doméstica

## Para liberar o anúncio

1. Se o relatório da execução disser que o PDF foi hospedado no Drive, o produto já foi criado ativo e com a entrega configurada: pule para o passo 2. Se não, no painel da Cakto abra o produto, configure a entrega com o PDF acima e **ative** o produto.
2. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos), ou espere a verificação automática de 6 em 6 horas. O robô só libera se o produto estiver **ativo** e a API devolver o link.
3. Se a API não devolver o link, copie o link de compra do painel e rode a ação `definir-link` com o id `p20261010-3` e o link.
4. Só depois disso os robôs de anúncio passam a divulgar o produto.

# Ficha do produto: Guia Prático de Redação e Copywriting Direto

Produto do catálogo `p20261009-3`.

Se a criação por API estiver ligada (`FABRICA_DRY_RUN=false`), o produto já foi criado na Cakto com estes dados e está em `waiting_config`. Se não, cadastre-o na Cakto com estes dados.

**O NOME precisa ficar exatamente assim**: o robô encontra o produto pelo nome (sem diferença de acento ou maiúscula) e então libera o anúncio sozinho.

- Nome: Guia Prático de Redação e Copywriting Direto
- Preço: R$ 27,90
- Tipo de entrega: arquivo digital (PDF)
- Arquivo da entrega: `guia-pratico-de-redacao-e-copywriting-direto.pdf` (nesta mesma pasta)

## Descrição da oferta (copie e cole)

Este combo premium em formato textual apresenta um roteiro completo para aprimorar sua comunicação escrita. Ao longo de cinco capítulos detalhados, você conhecerá métodos estruturados para eliminar termos vagos, prender a atenção com títulos funcionais, aplicar a estrutura clássica AIDA, compor chamadas claras para ação e realizar cortes precisos na revisão final. Um material direto ao ponto, com explicações práticas, modelos de aplicação e exercícios imediatos para organizar seu processo criativo diário.

## O que vem dentro

- Fundamentos da escrita persuasiva e clareza textual
- Estruturação de títulos e ganchos de atenção
- Aplicação prática do modelo AIDA em textos curtos
- Redação de chamadas para ação objetivas
- Revisão técnica, corte de excessos e polimento final

## Para liberar o anúncio

1. Se o relatório da execução disser que o PDF foi hospedado no Drive, o produto já foi criado ativo e com a entrega configurada: pule para o passo 2. Se não, no painel da Cakto abra o produto, configure a entrega com o PDF acima e **ative** o produto.
2. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos), ou espere a verificação automática de 6 em 6 horas. O robô só libera se o produto estiver **ativo** e a API devolver o link.
3. Se a API não devolver o link, copie o link de compra do painel e rode a ação `definir-link` com o id `p20261009-3` e o link.
4. Só depois disso os robôs de anúncio passam a divulgar o produto.

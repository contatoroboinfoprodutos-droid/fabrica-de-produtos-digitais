# Ficha do produto: Guia de Marketing Digital para Pequenos Negócios

Produto do catálogo `p20261009-2`.

Se a criação por API estiver ligada (`FABRICA_DRY_RUN=false`), o produto já foi criado na Cakto com estes dados e está em `waiting_config`. Se não, cadastre-o na Cakto com estes dados.

**O NOME precisa ficar exatamente assim**: o robô encontra o produto pelo nome (sem diferença de acento ou maiúscula) e então libera o anúncio sozinho.

- Nome: Guia de Marketing Digital para Pequenos Negócios
- Preço: R$ 19,90
- Tipo de entrega: arquivo digital (PDF)
- Arquivo da entrega: `guia-de-marketing-digital-para-pequenos-negocios.pdf` (nesta mesma pasta)

## Descrição da oferta (copie e cole)

Este guia oferece um passo a passo estruturado para pequenos comerciantes e autônomos organizarem suas ações de marketing na internet. Você aprenderá a configurar sua ficha nos mapas, criar um calendário de postagens claro, padronizar respostas rápidas no aplicativo de mensagens, subir anúncios voltados para sua região e acompanhar métricas básicas semanais. Sem termos difíceis ou fórmulas mágicas, o material foca na organização de rotinas reais e práticas de comunicação para o seu dia a dia profissional.

## O que vem dentro

- Otimização da presença em mapas e buscas locais
- Planejamento e produção de conteúdo simples para redes sociais
- Padronização do atendimento rápido no WhatsApp profissional
- Criação de campanhas de anúncios locais com orçamento enxuto
- Rotina semanal de monitoramento e ajuste de métricas básicas

## Para liberar o anúncio

1. Se o relatório da execução disser que o PDF foi hospedado no Drive, o produto já foi criado ativo e com a entrega configurada: pule para o passo 2. Se não, no painel da Cakto abra o produto, configure a entrega com o PDF acima e **ative** o produto.
2. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos), ou espere a verificação automática de 6 em 6 horas. O robô só libera se o produto estiver **ativo** e a API devolver o link.
3. Se a API não devolver o link, copie o link de compra do painel e rode a ação `definir-link` com o id `p20261009-2` e o link.
4. Só depois disso os robôs de anúncio passam a divulgar o produto.

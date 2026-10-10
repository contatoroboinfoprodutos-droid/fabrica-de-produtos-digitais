# Ficha do produto: Guia Prático de Estudos: Foco e Retenção Diária

Produto do catálogo `p20261010-1`.

Se a criação por API estiver ligada (`FABRICA_DRY_RUN=false`), o produto já foi criado na Cakto com estes dados e está em `waiting_config`. Se não, cadastre-o na Cakto com estes dados.

**O NOME precisa ficar exatamente assim**: o robô encontra o produto pelo nome (sem diferença de acento ou maiúscula) e então libera o anúncio sozinho.

- Nome: Guia Prático de Estudos: Foco e Retenção Diária
- Preço: R$ 8,90
- Tipo de entrega: arquivo digital (PDF)
- Arquivo da entrega: `guia-pratico-de-estudos-foco-e-retencao-diaria.pdf` (nesta mesma pasta)

## Descrição da oferta (copie e cole)

Este guia prático ensina passos diretos para estruturar sua rotina de estudos e manter a concentração no dia a dia. Você aprenderá a preparar um ambiente livre de interrupções, dividir matérias em blocos realistas, fazer anotações eficientes com suas próprias palavras e aplicar exercícios de recuperação de memória para fixar o conteúdo lido. Sem fórmulas mágicas, o material traz instruções claras, exemplos de rotina e pequenos exercícios para você aplicar imediatamente no seu caderno ou computador.

## O que vem dentro

- Organização do ambiente físico e digital livre de distrações
- Planejamento de blocos de estudo com pausas programadas
- Técnica de anotações ativas e síntese com suas próprias palavras
- Recuperação ativa da memória sem consultar o material
- Construção de um cronograma semanal simples e sustentável

## Para liberar o anúncio

1. Se o relatório da execução disser que o PDF foi hospedado no Drive, o produto já foi criado ativo e com a entrega configurada: pule para o passo 2. Se não, no painel da Cakto abra o produto, configure a entrega com o PDF acima e **ative** o produto.
2. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos), ou espere a verificação automática de 6 em 6 horas. O robô só libera se o produto estiver **ativo** e a API devolver o link.
3. Se a API não devolver o link, copie o link de compra do painel e rode a ação `definir-link` com o id `p20261010-1` e o link.
4. Só depois disso os robôs de anúncio passam a divulgar o produto.

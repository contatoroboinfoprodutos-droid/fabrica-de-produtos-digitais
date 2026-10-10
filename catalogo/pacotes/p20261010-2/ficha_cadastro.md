# Ficha do produto: Guia Prático de Organização do Home Office

Produto do catálogo `p20261010-2`.

Se a criação por API estiver ligada (`FABRICA_DRY_RUN=false`), o produto já foi criado na Cakto com estes dados e está em `waiting_config`. Se não, cadastre-o na Cakto com estes dados.

**O NOME precisa ficar exatamente assim**: o robô encontra o produto pelo nome (sem diferença de acento ou maiúscula) e então libera o anúncio sozinho.

- Nome: Guia Prático de Organização do Home Office
- Preço: R$ 8,90
- Tipo de entrega: arquivo digital (PDF)
- Arquivo da entrega: `guia-pratico-de-organizacao-do-home-office.pdf` (nesta mesma pasta)

## Descrição da oferta (copie e cole)

O Guia Prático de Organização do Home Office é um manual direto em texto para quem precisa transformar o ambiente de trabalho em casa. O material aborda desde ajustes de ergonomia e redução de bagunça na mesa até gerenciamento de fios, organização de pastas no computador e criação de limites claros entre expediente e vida pessoal. Cada capítulo traz orientações objetivas, exemplos simples com itens comuns do dia a dia e exercícios rápidos de aplicação imediata para deixar sua rotina mais prática.

## O que vem dentro

- Delimitação do espaço físico e ergonomia essencial
- Organização da mesa e descarte de itens desnecessários
- Gestão de cabos, equipamentos e materiais de apoio
- Organização digital de arquivos e área de trabalho
- Rituais de abertura e encerramento da jornada de trabalho

## Para liberar o anúncio

1. Se o relatório da execução disser que o PDF foi hospedado no Drive, o produto já foi criado ativo e com a entrega configurada: pule para o passo 2. Se não, no painel da Cakto abra o produto, configure a entrega com o PDF acima e **ative** o produto.
2. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos), ou espere a verificação automática de 6 em 6 horas. O robô só libera se o produto estiver **ativo** e a API devolver o link.
3. Se a API não devolver o link, copie o link de compra do painel e rode a ação `definir-link` com o id `p20261010-2` e o link.
4. Só depois disso os robôs de anúncio passam a divulgar o produto.

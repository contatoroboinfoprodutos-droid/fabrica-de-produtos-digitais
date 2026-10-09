# Fábrica de produtos

Cria, revisa e libera os produtos que os dois robôs de anúncio divulgam. Tudo roda no GitHub Actions
(`.github/workflows/produto.yml`) e o resultado fica em `catalogo/catalogo.json`.

## Como funciona

```
criador (CrewAI) → orientador (outro modelo) → criador corrige → travas em código
        → aprovado → registrador → aguardando_cadastro → (link encontrado) → pronto → anúncios
```

- **Criador**: escreve o guia completo (3 a 5 capítulos) e o texto da oferta.
- **Orientador**: usa um provedor de IA diferente do criador sempre que houver mais de uma chave
  (Gemini, Groq, OpenRouter). Não reescreve: diz o que mudar e como. Promessa proibida ele manda **remover**.
- **Travas em código** (`travas.py`): o bloqueio de verdade, que nenhum modelo contorna. Preço na faixa,
  quantidade mínima de conteúdo, termos proibidos (primeira venda, lucro, testado, garantido...),
  link igual ao do catálogo, preço do texto igual ao do catálogo, produto com status `pronto`.
- **Saída de reserva**: depois de `FABRICA_MAX_RODADAS` (3), o código **remove** os trechos proibidos
  (nunca troca por promessa parecida) e o orientador confere de novo. Se ainda falhar, o produto fica
  `reprovado` e nada é anunciado.
- **Registrador**: gera o PDF e a ficha (`catalogo/pacotes/<id>/`), cria o produto na **Cakto** por API
  (a Cakto já gera a oferta, o checkout e o link `pay.cakto.com.br/<oferta>`) e só libera o anúncio quando o
  produto está **ativo** e o link foi recebido. Criar de novo após um erro de rede nunca duplica: ele procura
  pelo nome antes de criar.

## O que está confirmado e o que NÃO está

| Item | Situação |
|---|---|
| Criador, orientador, travas, catálogo, PDF, limites, cliente da Cakto | Testado (88 testes). IA e rede **simuladas** |
| API real do CrewAI/Gemini/Groq | **Não testado aqui.** Valide na 1ª execução no Actions |
| API da Cakto (token, listar, criar, obter) | Implementada conforme docs.cakto.com.br. **Não testada com a sua conta** |
| Montagem do link `pay.cakto.com.br/<id da oferta>` | Vem da documentação. Confirme comprando/abrindo o link de um produto de teste |
| Hospedagem do PDF no Google Drive e entrega na Cakto (`PUT` do produto) | Implementada, rede **simulada**. **Não testada com a sua conta.** Sem Drive configurado (ou se o envio falhar), o produto nasce `waiting_config` como antes |
| **Conta de serviço grava em Meu Drive pessoal?** | **Não.** Ela não tem cota de armazenamento. Só funciona com pasta em **Drive compartilhado** (Google Workspace). Em Gmail comum use o modo OAuth abaixo. A ação `sondar` avisa antes de qualquer envio |

A ação `sondar` (somente leitura) mostra no log se o login funciona, quantos produtos existem e quais campos
a sua conta devolve. Rode-a primeiro.

## Antes de ligar: crie a chave de API e os Secrets

1. Na Cakto: **Integrações → Cakto API → Criar chave de API**. Marque os escopos `read`, `write`, `products` e
   `offers`. O `client_secret` aparece **uma única vez**: copie na hora.
2. No GitHub (Settings → Secrets and variables → Actions → **Secrets**) crie:
   - `CAKTO_CLIENT_ID`
   - `CAKTO_CLIENT_SECRET`
3. Opcional, em **Variables**: `CAKTO_SALES_PAGE` (URL da página de vendas, se a Cakto exigir ao criar).
4. A IA continua com os Secrets que você já usa: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`.

### Hospedagem do PDF (Google Drive)

A Cakto entrega o produto por um link enviado por e-mail; esse link precisa abrir o PDF. O robô envia o PDF
para uma pasta do Drive, libera a leitura **por link** (quem tem o link abre; é o link que o comprador recebe)
e grava esse link na entrega do produto. Reenviar nunca duplica: ele procura o arquivo pelo nome na pasta.

Variável da pasta: `GDRIVE_FOLDER_ID` (o trecho final da URL da pasta), em **Variables** ou **Secrets**.

**Modo A, conta de serviço** (Secret `GDRIVE_SERVICE_ACCOUNT_JSON` ou `GDRIVE_CREDENTIALS_JSON`): só funciona se a pasta estiver num
**Drive compartilhado** do Google Workspace e a conta de serviço (o `client_email` do JSON) for membro com
permissão de Gerente de conteúdo ou Editor. Numa pasta do Meu Drive de conta pessoal o Google recusa o envio
com `storageQuotaExceeded`.

**Modo B, OAuth da sua conta Google** (para Gmail comum; usa a cota do seu Drive). Secrets:
`GDRIVE_OAUTH_CLIENT_ID`, `GDRIVE_OAUTH_CLIENT_SECRET`, `GDRIVE_OAUTH_REFRESH_TOKEN`. Crie o cliente OAuth
(tipo "Aplicativo da Web" ou "Desktop") no Google Cloud Console, com a API do Drive ativada, e gere o
refresh token uma vez com o escopo `https://www.googleapis.com/auth/drive.file`. Nunca cole esses valores no chat.

Se os dois modos estiverem configurados, vale a conta de serviço. Rode `acao = sondar`: o resumo mostra o modo,
se a pasta é acessível e, no modo A, se ela está num Drive compartilhado.


## Interruptores (Settings → Secrets and variables → Actions → **Variables**)

| Variável | Padrão | Efeito |
|---|---|---|
| `FABRICA_DRY_RUN` | `true` | `true`: não cria nada nas plataformas. Leitura continua |
| `FABRICA_PAUSADA` | `false` | `true`: a fábrica não cria produto novo |
| `FABRICA_MAX_POR_DIA` | `1` | Máximo de produtos novos por dia |
| `FABRICA_MAX_RODADAS` | `3` | Rodadas de correção antes da saída de reserva |

## Primeiros passos

1. Rode **Actions → Fabrica de Produtos → Run workflow** com `acao = sondar`. Leia o resumo da execução.
2. Rode com `acao = criar`. O resumo mostra cada decisão do orientador e das travas.
3. Com `FABRICA_DRY_RUN=false` e o Drive funcionando, o robô hospeda o PDF e cria o produto já **ativo**, com
   a entrega por e-mail apontando para o PDF; um produto que já exista em `waiting_config` com o mesmo nome
   é atualizado (entrega + ativação). Sem Drive (ou se o envio falhar), o produto nasce em `waiting_config`:
   baixe o pacote (artefato `pacotes-de-produto`), configure a entrega com o PDF no painel e **ative** o
   produto. Mantenha o nome exato da ficha.
4. A cada 6 horas (ou com `acao = verificar`) o robô procura o produto e o libera se estiver ativo. Se a API
   não devolver o link, rode `acao = definir-link` com o `produto_id` e o `link_compra`.
5. Só então os robôs de anúncio passam a divulgar. Antes disso, o post de oferta é bloqueado em modo real.

## Efeito nos robôs de anúncio

- **lowticket**: preço e link vêm do produto `pronto` do catálogo; `LT_OFFER_LINK` só vale se não houver
  produto. A legenda e o texto do card passam pelas travas antes de publicar.
- **principal** (`main.py`): deixa de inventar um produto por rodada. Divulga o produto do catálogo e, em
  modo real, não publica nada se não houver produto `pronto`.
- Em `DRY_RUN`, os dois robôs continuam simulando e mostram no log o que as travas ajustaram.

## Termos de uso

Acessar o painel da Cakto de forma automatizada (navegador) pode violar os termos dela e suspender a conta.
Esta versão **não** faz isso: usa só a API oficial.

## Tentar de novo sem postar em duplicidade

Os dois robôs de anúncio (Low Ticket e Executar Fabrica de Infoprodutos) tentam até 3 vezes por execução,
inclusive em modo real, trocando de provedor de IA se um falhar (se houver menos provedores que tentativas, a
lista recomeça). O que impede o post duplicado são as **marcas de publicação** (`fabrica_produtos/marcas.py`):

- cada rede (Facebook, Instagram) que a Meta aceita deixa uma marca; uma nova tentativa **nunca repete uma rede
  já publicada** e, se só o Instagram falhou, refaz só o Instagram, sem enviar a foto de novo ao Facebook;
- a execução só termina com sucesso quando as **duas** redes publicaram. Se a IA termina "bem" mas esquece de
  publicar, isso conta como falha e a tentativa é repetida;
- **bloqueio definitivo** (post de oferta sem produto pronto, credenciais da Meta ausentes) encerra na hora com
  aviso, sem gastar tokens em tentativas inúteis;
- se, depois das 3 tentativas, só uma rede tiver publicado, a execução fica vermelha com a mensagem
  "Só uma das redes publicou": confira as duas antes de rodar de novo à mão.

Em simulação (DRY_RUN) nada disso é gravado e o comportamento é o de antes.

## Guardião (diagnóstico de falhas)

O workflow `guardiao.yml` dispara quando Low Ticket, Executar Fabrica de Infoprodutos, Fabrica de Produtos ou
Renovar token da Meta falham. Ele lê o log, reconhece a causa por regras fixas (sem IA, para funcionar mesmo com
a IA fora do ar) e abre uma Issue com o rótulo `falha-automatica`, com a causa e o passo a passo da correção
(a Issue chega por e-mail). Falha repetida pela mesma causa comenta na mesma Issue, não abre outra. Segredos
são removidos do trecho de log. **Só diagnostica**: não reexecuta robôs de anúncio (poderia duplicar post) e não
altera código nem Secrets. Regras em `fabrica_produtos/guardiao.py`; para a causa "não reconhecida", leia o log.

## Imagens da marca (perfil e capa)

`python -m tools.gerar_perfil` gera `assets/perfil.png` (1080x1080, iniciais do nome da marca, com folga para o
recorte redondo) e `python -m tools.gerar_capa` gera `assets/capa_facebook.png` (1640x856, texto na zona segura do
computador e do celular). O nome vem de `LT_BRAND_NAME` (padrão: Fábrica de Produtos Digitais). Os cartões dos
posts usam `LT_BRAND_HANDLE` no rodapé (ex.: `@seuperfil`); sem ele, usam o nome da marca.

A troca das fotos e os textos do perfil são **manuais**: o Instagram não oferece isso pela API e nenhum robô
daqui altera bio, descrição ou botão das páginas.

## Link na bio e roteiros de Reels (agente_link_hub e agente_roteiro_reels)

Os dois leem só o catálogo real (`catalogo/catalogo.json`): nada de público, segmentação, produto ou link inventado.

- **Hub** (`python -m fabrica_produtos hub`, sem IA): gera `docs/link-na-bio.html` com um card por produto `pronto` que tenha link de compra
  (título, promessa do catálogo, preço e botão "Comprar agora" para o `link_compra` real). Produto sem link não aparece.
- **Reels** (`python -m fabrica_produtos reels`, usa o CrewAI): para cada produto `pronto` sem roteiro, grava em
  `catalogo/roteiros_reels.json` `{id_produto, gancho_3s, roteiro_15s, legenda, cta}`. O modelo só escreve gancho, dor/solução e legenda;
  CTA fixo ("Link na bio - todos os guias lá") e preço vêm do código. Termos proibidos, links, @ e preço escrito pelo modelo reprovam o roteiro.
  Roteiro existente nunca é reescrito; falha numa rodada é tentada de novo na próxima.
- Rodam em `produto.yml` depois de `criar`/`verificar` (06:00 e a cada 6 h) e fazem commit de `catalogo` e `docs`.
  Manualmente: Actions > Fabrica de Produtos > Run workflow > acao `reels` ou `hub`.
- **GitHub Pages**: Settings > Pages > Source "Deploy from a branch", branch `main`, pasta `/docs`.
  URL: https://contatoroboinfoprodutos-droid.github.io/robo-infoprodutos/link-na-bio.html
  (repositório privado só publica Pages em plano pago; no plano grátis o repositório precisa ser público.)

## Preços por nível e validação do catálogo

- A fábrica escolhe o nível de cada produto em rodízio de 6 (guia, guia, pacote, guia, pacote, combo) e **o preço é fixo em código**:
  guia R$ 8,90 · pacote R$ 19,90 · combo premium R$ 27,90. A IA não decide preço nem tipo. O prompt pede o volume do nível e
  `travas.palavras_minimas` barra produto curto (600 / 1400 / 2200 palavras). O mesmo preço vai para a Cakto, para o catálogo e para a página.
- `FABRICA_TIPOS=guia` (Variable ou Secret) volta tudo para R$ 8,90. `FABRICA_PRECO_MIN/MAX` ainda limitam a faixa.
- `link_hub.validar_catalogo()` confere: link da Cakto (`https://pay.cakto.com.br/...`), `preco_texto` no formato `R$ 8,90` e igual a `preco`,
  e `nome` com menos de 60 caracteres. O comando `hub` mostra os avisos no resumo da execução (não bloqueia). Produto novo com nome de 60+ é barrado na criação.
- `index.html` mostra só produtos `pronto` com link da Cakto e escapa o texto vindo do catálogo.

## Reels em vídeo (manual, orgânico)

`python scripts/generate_reels.py [--max 10] [--only slug]` gera `reels/<slug>.mp4` (1080x1920, 8 s, 30 fps) e `reels/legendas.txt`
para os produtos `pronto` com link da Cakto. Pillow desenha os quadros (fundo #121212, logo FPD ⚡, título, selo de preço, CTA nos
últimos 2 s, zoom leve, fade in) e o ffmpeg grava o vídeo. Música opcional em `assets/music/{happy,lofi,corporate}.mp3` (volume 0,15);
sem o arquivo o vídeo sai sem áudio. Rodar no GitHub: Actions > Gerar Reels (manual) > baixar o artifact `reels`.
Os mp4 não são commitados (ficam só no artifact, 14 dias). Link do CTA: `REELS_LINK` (Variable) ou padrão `bit.ly/4rWbLt5`.

`scripts/fetch_music.py` tenta baixar `happy/lofi/corporate.mp3` com a chave `PIXABAY_API_KEY` (Secret). Nunca quebra o fluxo e não sobrescreve
um mp3 válido já existente em `assets/music/`. A documentação pública da Pixabay só lista APIs de imagens e vídeos; se o endpoint de música
não existir, o script avisa e pula. O jeito garantido é commitar os 3 mp3 em `assets/music/`.

Música dos Reels, jeito garantido: coloque `happy.mp3`, `lofi.mp3` e `corporate.mp3` em `assets/music/` e faça commit (mp3 não é ignorado).
O gerador escolhe pelo título (receita/marmita/fit/comida = happy; finanças/dinheiro/produtividade/renda/investimento = corporate; resto = lofi, ou a
categoria do produto) e mixa a 0,15. O resumo da execução diz, por vídeo, "Música usada: happy.mp3 (0.15)" ou "Sem música: arquivo ausente/corrompido".

## Legendas por rede: hashtags em 3 camadas e CTA

`travas.finalizar_para_rede` (em código, não pelo modelo) troca as hashtags do fim da legenda por 3 camadas do tema do produto
(amplas, do tema e de nicho) e acrescenta o CTA do canal: Instagram `Link na bio: <LINK_BIO_INSTAGRAM>`, Facebook `Veja todos os guias: <LINK_FACEBOOK>`.
Os dois links são Variables/Secrets opcionais (`LINK_BIO_INSTAGRAM`, `LINK_FACEBOOK`); os padrões são o site do GitHub Pages e `bit.ly/4ibGb7a`.
Esses dois links são liberados na trava de links; qualquer outro link inventado continua sendo trocado pelo link do catálogo.
`#rendaextra` só entra quando o produto é de renda extra. Os agentes são instruídos a NÃO escrever hashtags nem links.
Reels: se o mp3 da categoria falta ou está corrompido, o gerador usa outro mp3 válido de `assets/music/` e registra no log.

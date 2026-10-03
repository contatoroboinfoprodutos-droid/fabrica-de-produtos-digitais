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
| Criador, orientador, travas, catálogo, PDF, limites, cliente da Cakto | Testado (74 testes). IA e rede **simuladas** |
| API real do CrewAI/Gemini/Groq | **Não testado aqui.** Valide na 1ª execução no Actions |
| API da Cakto (token, listar, criar, obter) | Implementada conforme docs.cakto.com.br. **Não testada com a sua conta** |
| Montagem do link `pay.cakto.com.br/<id da oferta>` | Vem da documentação. Confirme comprando/abrindo o link de um produto de teste |
| **Hospedagem do PDF para a entrega** | **Não implementada.** Hoje o produto nasce `waiting_config` e você configura a entrega no painel |

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
3. Com `FABRICA_DRY_RUN=false` o robô cria o produto na Cakto em `waiting_config` (não pode ser vendido sem
   entrega). Baixe o pacote (artefato `pacotes-de-produto`), configure a entrega com o PDF no painel e
   **ative** o produto. Mantenha o nome exato da ficha.
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

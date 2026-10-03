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
- **Registrador**: gera o PDF e a ficha de cadastro (`catalogo/pacotes/<id>/`), depois procura o produto
  pelo **nome exato** nas APIs da Kiwify e da Hotmart e libera sozinho quando a API devolve o link.

## O que está confirmado e o que NÃO está

| Item | Situação |
|---|---|
| Criador, orientador, travas, catálogo, PDF, limites | Testado (59 testes). A IA foi simulada nos testes |
| API real do CrewAI/Gemini/Groq | **Não testado aqui.** Valide na 1ª execução no Actions |
| Login e listagem de produtos na Kiwify e Hotmart | **Não validado.** Endereços e campos vêm da documentação como eu a conheço |
| **Criar produto por API** | **Não implementado**: não confirmei que Kiwify ou Hotmart oferecem esse endpoint |

Por isso existe a ação `sondar` (somente leitura): ela mostra no log se o login funciona, quantos produtos
existem e quais campos a API devolve. Rode-a primeiro.

## Antes de ligar: confira estes Secrets

O workflow lê estes **nomes** (os valores você já tem no GitHub). Se os seus têm outro nome, troque no
`produto.yml` (seção `env`) ou crie Secrets com estes nomes:

- `KIWIFY_CLIENT_ID`, `KIWIFY_CLIENT_SECRET`, `KIWIFY_ACCOUNT_ID`
- `HOTMART_CLIENT_ID`, `HOTMART_CLIENT_SECRET` (opcional: `HOTMART_BASIC`)
- IA, os mesmos que você já usa: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`

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
3. Baixe o pacote (artefato `pacotes-de-produto`), cadastre o produto na plataforma **com o nome exato**
   da ficha e envie o PDF.
4. A cada 6 horas (ou com `acao = verificar`) o robô procura o produto e o libera. Se a API não devolver
   o link, rode `acao = definir-link` com o `produto_id` e o `link_compra`.
5. Só então os robôs de anúncio passam a divulgar. Antes disso, o post de oferta é bloqueado em modo real.

## Efeito nos robôs de anúncio

- **lowticket**: preço e link vêm do produto `pronto` do catálogo; `LT_OFFER_LINK` só vale se não houver
  produto. A legenda e o texto do card passam pelas travas antes de publicar.
- **principal** (`main.py`): deixa de inventar um produto por rodada. Divulga o produto do catálogo e, em
  modo real, não publica nada se não houver produto `pronto`.
- Em `DRY_RUN`, os dois robôs continuam simulando e mostram no log o que as travas ajustaram.

## Termos de uso

Acessar o painel da Kiwify ou da Hotmart de forma automatizada (navegador) pode violar os termos delas e
suspender a conta. Esta versão **não** faz isso: usa só as APIs oficiais.

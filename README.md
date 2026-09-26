# Infoproduct Factory

Sistema autônomo baseado em agentes CrewAI para criação, formatação e
distribuição automatizada de infoprodutos e conteúdo no Facebook e no
Instagram, usando Groq (Llama 3.3 70B) como LLM e a Meta Graph API v26.0
para publicação.

## ⚠️ Segurança — leia antes de tudo

Se você já colou `META_APP_SECRET`, `META_LONG_LIVED_TOKEN` ou outros
valores reais em algum chat, documento ou repositório público,
**rotacione-os agora** em https://developers.facebook.com/apps (App
Settings → Basic → Reset App Secret; e gere um novo token de usuário).
Nunca commite o arquivo `.env` real — apenas `.env.example` deve ir para
o controle de versão.

## Arquitetura

```
infoproduct_factory/
├── .env.example              # Template de variáveis de ambiente (sem segredos reais)
├── config.py                 # Carrega e valida o .env via pydantic-settings
├── crew.py                   # Monta o Crew (agentes + tasks, execução sequencial)
├── main.py                   # CLI de entrada
├── requirements.txt
├── agents_pkg/
│   └── agents.py              # 4 agentes: Estrategista, Redator, Diretor Criativo, Publicador
├── tasks_pkg/
│   └── tasks.py                # 4 tasks encadeadas via `context`
└── tools/
    ├── meta_graph_api.py      # Cliente puro da Meta Graph API (sem depender do CrewAI)
    └── crewai_meta_tools.py   # Tools do CrewAI que envolvem o cliente acima
```

### Pipeline de agentes

1. **Estrategista de Conteúdo** — recebe o tema e gera um outline (promessa,
   público, bullets, CTA).
2. **Copywriter Sênior** — transforma o outline em descrição do
   infoproduto + post de Facebook + legenda de Instagram.
3. **Diretor(a) Criativo(a)** — define o briefing visual e confirma a URL
   de imagem final a ser usada (a partir de um asset já hospedado que
   você fornece).
4. **Gestor de Publicação** — chama as tools `publish_to_facebook` e
   `publish_to_instagram`, que usam a Meta Graph API de verdade.

### Fluxo de publicação (Meta Graph API)

- **Autenticação:** o `META_LONG_LIVED_TOKEN` (token de usuário) é trocado
  automaticamente por um **Page Access Token** via `GET /me/accounts`,
  necessário para publicar tanto na Página do Facebook quanto na conta do
  Instagram vinculada a ela.
- **Facebook:** `POST /{FB_PAGE_ID}/feed` (texto) ou `POST /{FB_PAGE_ID}/photos`
  (imagem + legenda).
- **Instagram:** fluxo de dois passos —
  `POST /{INSTAGRAM_ACCOUNT_ID}/media` (cria o container com `image_url` +
  `caption`) e depois `POST /{INSTAGRAM_ACCOUNT_ID}/media_publish`
  (publica o container).

## Setup

```bash
cd infoproduct_factory
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edite .env com suas chaves reais (nunca commite este arquivo)
```

Permissões necessárias no app da Meta (via Graph API Explorer ou fluxo
OAuth): `pages_show_list`, `pages_manage_posts`, `pages_read_engagement`,
`instagram_basic`, `instagram_content_publish`.

## Uso

```bash
python main.py "Como organizar finanças pessoais em 30 dias" \
    --image-url https://meusite.com/assets/capa.jpg
```

Para testar sem publicar de verdade, defina `DRY_RUN=true` no `.env` — as
tools vão logar a chamada e retornar um `post_id` fake, sem chamar a Meta
Graph API.

## Próximos passos sugeridos

- Adicionar um agente/tool de geração de imagem (ex.: DALL·E, Stable
  Diffusion) para não depender de um asset já hospedado.
- Persistir os resultados de cada publicação (post_id, timestamp) em um
  banco de dados ou planilha para métricas.
- Adicionar retry/backoff nas chamadas HTTP (`requests`) para lidar com
  rate limiting da Graph API.
- Agendamento: rodar `main.py` via cron ou um agente adicional que decida
  o melhor horário de publicação.

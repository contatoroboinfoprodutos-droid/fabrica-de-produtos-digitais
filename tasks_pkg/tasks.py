"""
Definição das tasks da Infoproduct Factory, encadeadas via `context`
para que cada etapa receba o output das anteriores.
"""
from crewai import Agent, Task


def build_tasks(agents: dict[str, Agent], topic: str, image_asset_url: str) -> list[Task]:
    strategy_task = Task(
        description=(
            f"Tema fornecido pelo usuário: '{topic}'.\n"
            "Crie um outline estratégico para um infoproduto e/ou post de divulgação "
            "sobre esse tema, contendo: (1) promessa central em uma frase, "
            "(2) público-alvo, (3) 3 a 5 bullets com os principais pontos a abordar, "
            "(4) call-to-action sugerido."
        ),
        expected_output=(
            "Um outline estruturado em markdown com as 4 seções descritas."
        ),
        agent=agents["content_strategist"],
    )

    copywriting_task = Task(
        description=(
            "Com base no outline estratégico, escreva:\n"
            "1. Uma descrição curta do infoproduto/conteúdo (3-4 frases).\n"
            "2. Um POST DE FACEBOOK completo (pode ser mais longo, tom conversacional, "
            "com quebras de linha e um CTA claro no final).\n"
            "3. Uma LEGENDA DE INSTAGRAM (mais curta, direta, com emojis moderados e "
            "de 5 a 8 hashtags relevantes ao final).\n"
            "Separe claramente as três partes com os cabeçalhos "
            "'### DESCRICAO', '### POST_FACEBOOK' e '### LEGENDA_INSTAGRAM'."
        ),
        expected_output=(
            "Texto em markdown com as três seções claramente separadas pelos "
            "cabeçalhos indicados."
        ),
        agent=agents["copywriter"],
        context=[strategy_task],
    )

    creative_task = Task(
        description=(
            "Com base no post e na legenda gerados, escreva um briefing visual curto "
            "(estilo, paleta de cores, elementos que devem aparecer na imagem) para "
            f"acompanhar a publicação. Em seguida, use como URL final de imagem o "
            f"asset já hospedado informado pelo usuário: {image_asset_url}\n"
            "Retorne claramente: '### BRIEFING_VISUAL' e '### IMAGE_URL'."
        ),
        expected_output=(
            "Texto em markdown com o briefing visual e a URL final da imagem a ser "
            "usada nas publicações."
        ),
        agent=agents["creative_director"],
        context=[copywriting_task],
    )

    publishing_task = Task(
        description=(
            "Usando o POST_FACEBOOK, a LEGENDA_INSTAGRAM e a IMAGE_URL definidos nas "
            "etapas anteriores:\n"
            "1. Chame a tool publish_to_facebook com message=POST_FACEBOOK e "
            "image_url=IMAGE_URL.\n"
            "2. Chame a tool publish_to_instagram com image_url=IMAGE_URL e "
            "caption=LEGENDA_INSTAGRAM.\n"
            "Reporte o resultado (sucesso com post_id, ou erro) de cada chamada, "
            "exatamente como retornado pelas tools — não invente IDs."
        ),
        expected_output=(
            "Um relatório final com o status de publicação no Facebook e no "
            "Instagram, incluindo os post_id retornados ou a mensagem de erro."
        ),
        agent=agents["social_publisher"],
        context=[copywriting_task, creative_task],
    )

    return [strategy_task, copywriting_task, creative_task, publishing_task]

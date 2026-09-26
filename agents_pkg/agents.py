"""
Definição dos agentes da Infoproduct Factory.

Pipeline: Estrategista -> Redator -> Diretor Criativo -> Publicador Social.
Todos usam o mesmo LLM (Groq / llama-3.3-70b-versatile), configurado uma
única vez em get_llm().
"""
import litellm
from crewai import LLM, Agent

from config import get_settings
from tools.crewai_meta_tools import PublishToFacebookTool, PublishToInstagramTool

# ---------------------------------------------------------------------------
# Compatibilidade CrewAI 1.15.x + Groq (issue conhecida do CrewAI: #5886)
# ---------------------------------------------------------------------------
# O executor do agente chama mark_cache_breakpoint() incondicionalmente para
# QUALQUER provider (não só Anthropic), injetando a chave "cache_breakpoint"
# diretamente no dict da mensagem *antes* de ela chegar ao LiteLLM. Como o
# campo já está dentro da mensagem (não é um parâmetro de request), o
# `litellm.drop_params` não tem efeito aqui — ele só descarta parâmetros de
# nível superior da chamada, não chaves arbitrárias dentro de `messages`.
#
# Correções oficiais existem (PRs #5887, #6188, #6314), mas ainda não estão
# presentes na 1.15.22. Contorno: sobrescrever mark_cache_breakpoint como
# no-op nos três lugares que a importam por referência (from ... import ...),
# já que patchear só o módulo de origem não afeta os nomes já vinculados nos
# executores. Isso é seguro: só desativa a marcação de prompt-caching (que o
# Groq não usa mesmo) e não afeta a lógica de negócio dos agentes.
try:
    import crewai.llms.cache as _crewai_cache

    def _noop_mark_cache_breakpoint(message, *args, **kwargs):
        return message

    _crewai_cache.mark_cache_breakpoint = _noop_mark_cache_breakpoint

    try:
        import crewai.agents.crew_agent_executor as _crew_agent_executor

        _crew_agent_executor.mark_cache_breakpoint = _noop_mark_cache_breakpoint
    except ImportError:
        pass

    try:
        import crewai.experimental.agent_executor as _experimental_agent_executor

        _experimental_agent_executor.mark_cache_breakpoint = _noop_mark_cache_breakpoint
    except ImportError:
        pass
except ImportError:
    # Versão do CrewAI sem esse módulo (bug já corrigido ou API diferente) —
    # nada a fazer.
    pass

# Mantido como segunda camada de defesa para outros parâmetros não suportados
# pelo Groq que possam ser injetados no nível da chamada HTTP (não resolve o
# cache_breakpoint por si só, ver comentário acima).
litellm.drop_params = True


def get_llm() -> LLM:
    settings = get_settings()
    return LLM(
        model=settings.model,
        api_key=settings.groq_api_key,
        temperature=0.7,
    )


def build_agents() -> dict[str, Agent]:
    llm = get_llm()

    content_strategist = Agent(
        role="Estrategista de Conteúdo e Infoprodutos",
        goal=(
            "Definir o ângulo, a promessa central e a estrutura (outline) de um "
            "infoproduto ou peça de conteúdo com base no tema fornecido pelo usuário, "
            "maximizando clareza e potencial de conversão."
        ),
        backstory=(
            "Você é um estrategista digital com anos de experiência lançando "
            "infoprodutos (ebooks, mini-cursos, guias) para o mercado brasileiro. "
            "Você entende de copywriting, jornada do cliente e como transformar um "
            "tema genérico em uma oferta com posicionamento claro."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        cache=False,  # evita o gatilho de prompt-caching problemático com Groq (ver nota acima)
    )

    copywriter = Agent(
        role="Redator (Copywriter) Sênior",
        goal=(
            "Transformar o outline estratégico em textos finais: descrição do "
            "infoproduto, e um post de Facebook e uma legenda de Instagram prontos "
            "para publicação, no tom de voz definido."
        ),
        backstory=(
            "Você é um copywriter especializado em redes sociais e lançamentos "
            "digitais, com domínio de gatilhos mentais, storytelling curto e "
            "adaptação de linguagem para cada plataforma (Facebook vs. Instagram)."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        cache=False,  # evita o gatilho de prompt-caching problemático com Groq (ver nota acima)
    )

    creative_director = Agent(
        role="Diretor(a) Criativo(a)",
        goal=(
            "Definir o briefing visual do post (composição, paleta, estilo) e "
            "produzir uma URL de imagem final pronta para ser usada na publicação "
            "(a partir de um asset já hospedado, informado pelo usuário)."
        ),
        backstory=(
            "Você é diretor de arte digital, especialista em criar peças visuais "
            "que combinam com o texto do copywriter e seguem as boas práticas de "
            "aspect ratio e legibilidade do Facebook e do Instagram."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        cache=False,  # evita o gatilho de prompt-caching problemático com Groq (ver nota acima)
    )

    social_publisher = Agent(
        role="Gestor de Publicação em Redes Sociais",
        goal=(
            "Publicar o conteúdo final aprovado no Facebook e no Instagram usando "
            "exclusivamente as tools oficiais de integração com a Meta Graph API, "
            "reportando o resultado (sucesso ou erro) de cada publicação."
        ),
        backstory=(
            "Você é responsável pela operação de social media de uma fábrica de "
            "infoprodutos. Você nunca inventa IDs de post — você só reporta o que "
            "as tools de publicação retornam."
        ),
        llm=llm,
        tools=[PublishToFacebookTool(), PublishToInstagramTool()],
        verbose=True,
        allow_delegation=False,
        cache=False,  # evita o gatilho de prompt-caching problemático com Groq (ver nota acima)
    )

    return {
        "content_strategist": content_strategist,
        "copywriter": copywriter,
        "creative_director": creative_director,
        "social_publisher": social_publisher,
    }

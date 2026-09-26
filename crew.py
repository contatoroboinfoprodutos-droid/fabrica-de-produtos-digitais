"""
Monta o Crew da Infoproduct Factory a partir de config/agents.yaml e
config/tasks.yaml (padrão @CrewBase do CrewAI) — 5 agentes, 5 tasks,
execução sequencial, terminando na publicação real via Meta Graph API.
"""
import time

import litellm
from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

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

# Segunda camada de defesa para outros parâmetros não suportados pelo Groq
# que possam ser injetados no nível da chamada HTTP.
litellm.drop_params = True


# ---------------------------------------------------------------------------
# Pausa entre tasks para respeitar o limite de tokens por minuto (TPM) da Groq
# ---------------------------------------------------------------------------
# O plano gratuito ("on_demand") da Groq limita o uso a poucos milhares de
# tokens por minuto. Como as 5 tasks rodam em sequência e cada uma consome
# uma fatia desse orçamento, o total acumulado em menos de 60s costuma
# estourar o limite antes mesmo de chegar à última task (RateLimitError).
# Esta função, usada como `callback` de cada task (exceto a última, que não
# precisa esperar por nada depois dela), pausa a execução por tempo
# suficiente para a "janela" de limite da Groq resetar antes da próxima
# chamada ao LLM.
#
# Nota: 65s não foi suficiente em testes — a janela da Groq parece resetar
# em intervalos fixos (ex.: a cada minuto-relógio), não exatamente 60s a
# partir da última chamada. 90s dá uma margem de segurança mais confiável
# para cobrir esse desalinhamento, mesmo com o pipeline rodando um pouco
# mais devagar como consequência.
_PAUSA_ENTRE_TASKS_SEGUNDOS = 90


def _aguardar_reset_rate_limit(output):
    time.sleep(_PAUSA_ENTRE_TASKS_SEGUNDOS)


def get_llm() -> LLM:
    settings = get_settings()
    return LLM(
        model=settings.model,
        api_key=settings.groq_api_key,
        temperature=0.7,
        # ------------------------------------------------------------------
        # Retry automático para o rate limit (TPM) do plano gratuito da Groq
        # ------------------------------------------------------------------
        # A Groq (plano on_demand) limita o uso a poucos milhares de tokens
        # por minuto. Como o Crew roda 5 agentes em sequência, é comum que
        # uma chamada individual estoure esse limite temporário e receba
        # litellm.RateLimitError. O parâmetro reconhecido pelo LiteLLM para
        # tentar novamente automaticamente (com espera/backoff) é
        # `num_retries` — NÃO `max_retries` (esse nome não existe na função
        # de completion do LiteLLM e é descartado silenciosamente pelo
        # `litellm.drop_params = True` já configurado acima, o que explica
        # por que uma tentativa anterior com `max_retries` não teve efeito).
        num_retries=5,
    )


@CrewBase
class InfoprodutoFactoryCrew:
    """Crew completo: estratégia -> roteiro -> visual -> segmentação -> publicação."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # -- Agentes -------------------------------------------------------- #
    @agent
    def conteudo_estrategista(self) -> Agent:
        return Agent(
            config=self.agents_config["conteudo_estrategista"],
            llm=get_llm(),
            verbose=True,
            allow_delegation=False,
            cache=False,  # evita o gatilho de prompt-caching problemático com Groq (ver nota acima)
        )

    @agent
    def redator_senior(self) -> Agent:
        return Agent(
            config=self.agents_config["redator_senior"],
            llm=get_llm(),
            verbose=True,
            allow_delegation=False,
            cache=False,
        )

    @agent
    def diretor_criativo(self) -> Agent:
        return Agent(
            config=self.agents_config["diretor_criativo"],
            llm=get_llm(),
            verbose=True,
            allow_delegation=False,
            cache=False,
        )

    @agent
    def segmentador_publicos(self) -> Agent:
        return Agent(
            config=self.agents_config["segmentador_publicos"],
            llm=get_llm(),
            verbose=True,
            allow_delegation=False,
            cache=False,
        )

    @agent
    def publicador_redes(self) -> Agent:
        return Agent(
            config=self.agents_config["publicador_redes"],
            llm=get_llm(),
            tools=[PublishToFacebookTool(), PublishToInstagramTool()],
            verbose=True,
            allow_delegation=False,
            cache=False,
        )

    # -- Tasks ------------------------------------------------------------ #
    @task
    def planejar_campanha(self) -> Task:
        return Task(
            config=self.tasks_config["planejar_campanha"],
            callback=_aguardar_reset_rate_limit,
        )

    @task
    def criar_roteiro_e_legenda(self) -> Task:
        return Task(
            config=self.tasks_config["criar_roteiro_e_legenda"],
            callback=_aguardar_reset_rate_limit,
        )

    @task
    def desenvolver_diretrizes_visuais(self) -> Task:
        return Task(
            config=self.tasks_config["desenvolver_diretrizes_visuais"],
            callback=_aguardar_reset_rate_limit,
        )

    @task
    def direcionar_para_grupos(self) -> Task:
        return Task(
            config=self.tasks_config["direcionar_para_grupos"],
            callback=_aguardar_reset_rate_limit,
        )

    @task
    def publicar_no_facebook_e_instagram(self) -> Task:
        return Task(config=self.tasks_config["publicar_no_facebook_e_instagram"])

    # -- Crew ------------------------------------------------------------- #
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

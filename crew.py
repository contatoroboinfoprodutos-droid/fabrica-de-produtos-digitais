"""
Monta o Crew da Infoproduct Factory a partir de config/agents.yaml e
config/tasks.yaml (padrão @CrewBase do CrewAI) — integrando com o Groq
e gerenciando os limites de TPM (Rate Limit).
"""
import re
import time
import logging
from typing import ClassVar

import litellm
from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from config import get_settings
from tools.crewai_meta_tools import PublishToFacebookTool, PublishToInstagramTool

logger = logging.getLogger(__name__)


# Função de pausa entre tarefas para respeitar o limite de tokens por minuto (TPM) da Groq
def _aguardar_reset_rate_limit(output):
    time.sleep(20)  # Pausa de 20 segundos entre tarefas para resetar a janela de TPM


class GroqRateLimitAwareLLM(LLM):
    """
    Subclasse de crewai.LLM que intercepta RateLimitError da Groq,
    extrai o tempo de espera exato sugerido pela API ("try again in Xs")
    e aguarda antes de tentar novamente.
    """

    MAX_ATTEMPTS: ClassVar[int] = 6
    FALLBACK_BASE_DELAY: ClassVar[float] = 8.0

    def call(self, *args, **kwargs):
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                return super().call(*args, **kwargs)
            except litellm.exceptions.RateLimitError as e:
                wait_time = self._extract_wait_time(str(e))
                if wait_time is None:
                    wait_time = self.FALLBACK_BASE_DELAY * (2 ** (attempt - 1))

                logger.warning(
                    "[Groq RateLimit] Tentativa %d/%d — aguardando %.1fs antes de retomar.",
                    attempt, self.MAX_ATTEMPTS, wait_time,
                )
                time.sleep(wait_time + 0.5)

                if attempt == self.MAX_ATTEMPTS:
                    logger.error("Rate limit da Groq persistiu após %d tentativas.", attempt)
                    raise
        raise RuntimeError("Não foi possível completar a chamada à Groq.")

    @staticmethod
    def _extract_wait_time(error_message: str):
        match = re.search(r"try again in ([\d.]+)s", error_message)
        return float(match.group(1)) if match else None


def get_llm() -> LLM:
    settings = get_settings()
    return GroqRateLimitAwareLLM(
        model=settings.model,
        api_key=settings.groq_api_key,
        temperature=0.7,
        max_tokens=1024,   # limita o tamanho de cada resposta, ajuda a não estourar o TPM
        num_retries=5,     # retry nativo do litellm como primeira camada
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
            cache=False,
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
            max_rpm=6,   # throttle adicional no nível da crew inteira
            verbose=True,
        )

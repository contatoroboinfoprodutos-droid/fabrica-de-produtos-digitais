"""
Monta o Crew da Infoproduct Factory a partir de config/agents.yaml e
config/tasks.yaml (padrão @CrewBase do CrewAI) — integrando com o Groq
e gerenciando os limites de TPM (Rate Limit).
"""
import time
from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from config import get_settings
from tools.crewai_meta_tools import PublishToFacebookTool, PublishToInstagramTool


# Função de pausa entre tarefas para respeitar o limite de tokens por minuto (TPM) da Groq
def _aguardar_reset_rate_limit(output):
    time.sleep(20)  # Pausa de 20 segundos entre tarefas para resetar a janela de TPM


def get_llm() -> LLM:
    settings = get_settings()
    return LLM(
        model=settings.model,
        api_key=settings.groq_api_key,
        temperature=0.7,
        # Retry automático caso ocorra RateLimitError temporário
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
            verbose=True,
        )

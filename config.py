"""
Monta o Crew da Infoproduct Factory a partir de config/agents.yaml e
config/tasks.yaml (padrão @CrewBase do CrewAI) — integrando com o Google Gemini via LiteLLM.
"""
from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from config import get_settings
from tools.crewai_meta_tools import PublishToFacebookTool, PublishToInstagramTool


def get_llm() -> LLM:
    settings = get_settings()
    return LLM(
        model=settings.model,
        api_key=settings.gemini_api_key,
        temperature=0.7,
        provider="litellm",  # Força o uso do LiteLLM para o Gemini, evitando dependências extras
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
        )

    @agent
    def redator_senior(self) -> Agent:
        return Agent(
            config=self.agents_config["redator_senior"],
            llm=get_llm(),
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def diretor_criativo(self) -> Agent:
        return Agent(
            config=self.agents_config["diretor_criativo"],
            llm=get_llm(),
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def segmentador_publicos(self) -> Agent:
        return Agent(
            config=self.agents_config["segmentador_publicos"],
            llm=get_llm(),
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def publicador_redes(self) -> Agent:
        return Agent(
            config=self.agents_config["publicador_redes"],
            llm=get_llm(),
            tools=[PublishToFacebookTool(), PublishToInstagramTool()],
            verbose=True,
            allow_delegation=False,
        )

    # -- Tasks ------------------------------------------------------------ #
    @task
    def planejar_campanha(self) -> Task:
        return Task(config=self.tasks_config["planejar_campanha"])

    @task
    def criar_roteiro_e_legenda(self) -> Task:
        return Task(config=self.tasks_config["criar_roteiro_e_legenda"])

    @task
    def desenvolver_diretrizes_visuais(self) -> Task:
        return Task(config=self.tasks_config["desenvolver_diretrizes_visuais"])

    @task
    def direcionar_para_grupos(self) -> Task:
        return Task(config=self.tasks_config["direcionar_para_grupos"])

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

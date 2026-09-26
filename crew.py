"""
Monta o Crew da Infoproduct Factory: 4 agentes, 4 tasks, execução sequencial.
"""
from crewai import Crew, Process

from agents_pkg.agents import build_agents
from tasks_pkg.tasks import build_tasks


def build_crew(topic: str, image_asset_url: str) -> Crew:
    agents = build_agents()
    tasks = build_tasks(agents, topic=topic, image_asset_url=image_asset_url)

    return Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

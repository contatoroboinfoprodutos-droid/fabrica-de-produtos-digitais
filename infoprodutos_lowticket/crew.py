from crewai import Crew, Process
from . import config_lt as cfg
from .agents import (trend_scout_agent, copywriter_lowticket_agent,
                     visual_director_agent, publisher_infoproduto_agent)
from .tasks import build_lt_tasks


def crew_infoprodutos_lowticket(slot: str = "manha") -> Crew:
    """slot: 'manha' (valor/autoridade) ou 'tarde' (oferta R$7)."""
    if slot not in cfg.SLOTS:
        raise ValueError(f"slot inválido: {slot}. Use {list(cfg.SLOTS)}")
    return Crew(
        agents=[trend_scout_agent, copywriter_lowticket_agent,
                visual_director_agent, publisher_infoproduto_agent],
        tasks=build_lt_tasks(slot),
        process=Process.sequential, verbose=True)


def run_lowticket(slot: str = "manha"):
    return crew_infoprodutos_lowticket(slot).kickoff()

"""Substitutos mínimos de crewai e config para testar a lógica sem instalar o CrewAI.

ATENÇÃO: isto NÃO prova que a API real do CrewAI funciona; só exercita o encadeamento do nosso código.
A validação real acontece na primeira execução no GitHub Actions.
"""
import sys
import types

from pydantic import BaseModel


class FakeLLM:
    """Responde com `respostas` em ordem; se um item for Exception, levanta."""

    def __init__(self, respostas=None, provedor=""):
        self.respostas = list(respostas or [])
        self.provedor = provedor
        self.chamadas = []

    def call(self, prompt, *a, **k):
        self.chamadas.append(prompt)
        item = self.respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _Agent:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Task:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Out:
    def __init__(self, raw):
        self.raw = raw


class _Crew:
    def __init__(self, agents=None, tasks=None, **kw):
        self.agents, self.tasks = agents, tasks

    def kickoff(self, inputs=None):
        t = self.tasks[0]
        return _Out(t.agent.llm.call(t.description))


def instalar():
    crewai = types.ModuleType("crewai")
    crewai.Agent, crewai.Task, crewai.Crew = _Agent, _Task, _Crew
    crewai.Process = types.SimpleNamespace(sequential="sequential")
    crewai.LLM = lambda **kw: FakeLLM(provedor=kw.get("model", ""))
    tools = types.ModuleType("crewai.tools")
    tools.tool = lambda nome: (lambda f: f)  # o decorador real devolve uma Tool; aqui a função fica chamável
    tools.BaseTool = BaseModel
    crewai.tools = tools
    sys.modules["crewai"] = crewai
    sys.modules["crewai.tools"] = tools


def instalar_config(dry_run=True):
    """Troca o módulo `config` do projeto (pydantic-settings) por um objeto simples."""
    cfg = types.ModuleType("config")
    cfg.get_settings = lambda: types.SimpleNamespace(dry_run=cfg.DRY, meta_configurada=False)
    cfg.DRY = dry_run
    sys.modules["config"] = cfg
    return cfg

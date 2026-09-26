import os
import re
import time
import logging
import litellm
from crewai import Agent, Crew, Process, Task
from crewai import LLM

logger = logging.getLogger(__name__)

# --- Camada 1: retry nativo do LiteLLM como rede de segurança global ---
# Isso faz o litellm tentar novamente automaticamente em erros transitórios
# (rate limit, timeout, erro 5xx) antes mesmo de chegar no seu código.
litellm.num_retries = 5
litellm.request_timeout = 120


class GroqRateLimitAwareLLM(LLM):
    """
    Subclasse de crewai.LLM que intercepta RateLimitError da Groq,
    extrai o tempo de espera exato sugerido pela API ("try again in Xs")
    e aguarda antes de tentar novamente — em vez de um backoff genérico.
    """

    MAX_ATTEMPTS = 6
    FALLBACK_BASE_DELAY = 8  # segundos, usado se não conseguir parsear a mensagem

    def call(self, *args, **kwargs):
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                return super().call(*args, **kwargs)
            except litellm.exceptions.RateLimitError as e:
                wait_time = self._extract_wait_time(str(e))
                if wait_time is None:
                    # backoff exponencial com jitter como fallback
                    wait_time = self.FALLBACK_BASE_DELAY * (2 ** (attempt - 1))

                logger.warning(
                    "[Groq RateLimit] Tentativa %d/%d — aguardando %.1fs antes de retomar.",
                    attempt, self.MAX_ATTEMPTS, wait_time,
                )
                time.sleep(wait_time + 0.5)  # pequena margem de segurança

                if attempt == self.MAX_ATTEMPTS:
                    logger.error("Rate limit da Groq persistiu após %d tentativas.", attempt)
                    raise
        raise RuntimeError("Não foi possível completar a chamada à Groq.")

    @staticmethod
    def _extract_wait_time(error_message: str) -> float | None:
        match = re.search(r"try again in ([\d.]+)s", error_message)
        return float(match.group(1)) if match else None


# --- Instanciação do LLM ---
groq_llm = GroqRateLimitAwareLLM(
    model="groq/openai/gpt-oss-120b",
    api_key=os.environ["GROQ_API_KEY"],
    temperature=0.3,
    max_tokens=1024,       # <- crítico: corta o "Requested" por chamada
)

# --- Camada 3: throttle no nível do Crew ---
# max_rpm limita requisições/minuto para toda a crew (sobrepõe o dos agentes),
# dando tempo para a janela de TPM da Groq "esvaziar" entre chamadas.
crew = Crew(
    agents=[...],   # seus agentes, cada um usando llm=groq_llm
    tasks=[...],
    process=Process.sequential,
    max_rpm=6,        # ajuste conforme o tamanho médio dos seus prompts
    cache=True,       # evita reprocessar chamadas idênticas
    verbose=True,
)

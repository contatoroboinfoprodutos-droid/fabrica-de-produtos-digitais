from typing import ClassVar
import re
import time
import logging
import litellm
from crewai import LLM

logger = logging.getLogger(__name__)


class GroqRateLimitAwareLLM(LLM):
    """
    Subclasse de crewai.LLM que intercepta RateLimitError da Groq,
    extrai o tempo de espera exato sugerido pela API ("try again in Xs")
    e aguarda antes de tentar novamente.
    """

    # Precisam ser ClassVar porque LLM é um modelo Pydantic —
    # sem isso, Pydantic tenta tratá-los como campos do modelo.
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
    def _extract_wait_time(error_message: str) -> float | None:
        match = re.search(r"try again in ([\d.]+)s", error_message)
        return float(match.group(1)) if match else None

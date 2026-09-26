"""
Configuração central do projeto Infoproduct Factory.

Carrega e valida todas as variáveis de ambiente necessárias (.env) usando
pydantic-settings. Nenhum segredo é hardcoded aqui — tudo vem do ambiente.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM / Groq ---
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    model: str = Field("groq/llama-3.3-70b-versatile", alias="MODEL")

    # --- Meta / Graph API ---
    meta_app_id: str = Field(..., alias="META_APP_ID")
    meta_app_secret: str = Field(..., alias="META_APP_SECRET")
    meta_long_lived_token: str = Field(..., alias="META_LONG_LIVED_TOKEN")
    meta_graph_api_version: str = Field("v26.0", alias="META_GRAPH_API_VERSION")

    fb_page_id: str = Field(..., alias="FB_PAGE_ID")
    instagram_account_id: str = Field(..., alias="INSTAGRAM_ACCOUNT_ID")
    business_portfolio_id: str = Field(..., alias="BUSINESS_PORTFOLIO_ID")

    dry_run: bool = Field(False, alias="DRY_RUN")

    @property
    def graph_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.meta_graph_api_version}"


@lru_cache
def get_settings() -> "Settings":
    """Retorna uma instância cacheada das settings (singleton por processo)."""
    return Settings()

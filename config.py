"""
Configuração central do projeto Infoproduct Factory.
Carrega e valida as variáveis de ambiente usando pydantic-settings.
"""
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM / Groq (primário) ---
    groq_api_key: Optional[str] = Field(None, alias="GROQ_API_KEY")
    llm_provider: str = Field("groq", alias="LLM_PROVIDER")  # "groq" ou "gemini"
    model: str = Field("groq/openai/gpt-oss-120b", alias="MODEL")

    # --- LLM / Gemini (fallback) ---
    gemini_api_key: Optional[str] = Field(None, alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini/gemini-2.5-flash", alias="GEMINI_MODEL")

    # --- Meta / Graph API (opcionais) ---
    meta_app_id: Optional[str] = Field(None, alias="META_APP_ID")
    meta_app_secret: Optional[str] = Field(None, alias="META_APP_SECRET")
    meta_long_lived_token: Optional[str] = Field(None, alias="META_LONG_LIVED_TOKEN")
    meta_graph_api_version: str = Field("v26.0", alias="META_GRAPH_API_VERSION")

    fb_page_id: Optional[str] = Field(None, alias="FB_PAGE_ID")
    instagram_account_id: Optional[str] = Field(None, alias="INSTAGRAM_ACCOUNT_ID")
    business_portfolio_id: Optional[str] = Field(None, alias="BUSINESS_PORTFOLIO_ID")

    dry_run: bool = Field(False, alias="DRY_RUN")

    # --- Entradas da campanha ---
    produto_topico: str = Field(
        "Produto em destaque do catálogo desta semana", alias="PRODUTO_TOPICO"
    )
    imagem_padrao_url: Optional[str] = Field(None, alias="IMAGEM_PADRAO_URL")

    @field_validator("model", mode="before")
    @classmethod
    def _default_se_vazio_model(cls, v):
        return v if v and str(v).strip() else "groq/openai/gpt-oss-120b"

    @field_validator("gemini_model", mode="before")
    @classmethod
    def _default_se_vazio_gemini_model(cls, v):
        return v if v and str(v).strip() else "gemini/gemini-2.5-flash"

    @field_validator("produto_topico", mode="before")
    @classmethod
    def _default_se_vazio_topico(cls, v):
        return v if v and str(v).strip() else "Produto em destaque do catálogo desta semana"

    @field_validator("dry_run", mode="before")
    @classmethod
    def _vazio_vira_false(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "t", "yes", "y")
        return bool(v)

    @field_validator(
        "imagem_padrao_url",
        "meta_app_id",
        "meta_app_secret",
        "meta_long_lived_token",
        "fb_page_id",
        "instagram_account_id",
        "business_portfolio_id",
        mode="before",
    )
    @classmethod
    def _vazio_vira_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _gemini_key_vazia_vira_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @property
    def graph_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.meta_graph_api_version}"

    @property
    def meta_configurada(self) -> bool:
        return bool(self.meta_long_lived_token and self.fb_page_id and self.instagram_account_id)


@lru_cache
def get_settings() -> "Settings":
    """Retorna uma instância cacheada das settings (singleton por processo)."""
    return Settings()

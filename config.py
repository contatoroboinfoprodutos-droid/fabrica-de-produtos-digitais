"""
Configuração central do projeto Infoproduct Factory.

Carrega e valida as variáveis de ambiente (.env em local, Secrets no GitHub
Actions) usando pydantic-settings.

IMPORTANTE — duas correções em relação à versão anterior:

1. O default de MODEL era "groq/llama-3.3-70b-versatile", que a Groq
   descontinuou (retorna 404 "model_not_found"). O default agora é
   "groq/openai/gpt-oss-120b". Ajuste via variável de ambiente MODEL se
   quiser usar outro.

2. Os campos da Meta (META_APP_ID, META_LONG_LIVED_TOKEN, FB_PAGE_ID etc.)
   eram obrigatórios (Field(...)) — se qualquer um faltasse, o simples
   `Settings()` já lançava ValidationError e derrubava TODO o pipeline
   antes mesmo da geração de conteúdo começar. Agora são opcionais: se não
   configurados, as tools de publicação apenas reportam "não configurado"
   (ver tools/meta_graph_api.py) em vez de quebrar a execução inteira.
"""
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM / Groq ---
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    model: str = Field("groq/openai/gpt-oss-120b", alias="MODEL")

    # --- Meta / Graph API (opcionais — publicação é pulada com aviso se ausentes) ---
    meta_app_id: Optional[str] = Field(None, alias="META_APP_ID")
    meta_app_secret: Optional[str] = Field(None, alias="META_APP_SECRET")
    meta_long_lived_token: Optional[str] = Field(None, alias="META_LONG_LIVED_TOKEN")
    meta_graph_api_version: str = Field("v26.0", alias="META_GRAPH_API_VERSION")

    fb_page_id: Optional[str] = Field(None, alias="FB_PAGE_ID")
    instagram_account_id: Optional[str] = Field(None, alias="INSTAGRAM_ACCOUNT_ID")
    business_portfolio_id: Optional[str] = Field(None, alias="BUSINESS_PORTFOLIO_ID")

    dry_run: bool = Field(False, alias="DRY_RUN")

    # --- Entradas da campanha (permitem rodar via cron/workflow_dispatch,
    #     sem precisar de argumentos de linha de comando) ---
    produto_topico: str = Field(
        "Produto em destaque do catálogo desta semana", alias="PRODUTO_TOPICO"
    )
    imagem_padrao_url: Optional[str] = Field(None, alias="IMAGEM_PADRAO_URL")

    # No GitHub Actions, um `${{ secrets.X }}` referente a um secret que NÃO
    # existe é injetado como STRING VAZIA em `env:` — não como variável
    # ausente. Isso faz o default do pydantic ser ignorado (o default só
    # entra quando a chave está ausente do ambiente, não quando está vazia).
    # Os validators abaixo tratam string vazia como "não configurado",
    # aplicando o valor padrão real ou None, conforme o campo.
    @field_validator("model", mode="before")
    @classmethod
    def _default_se_vazio_model(cls, v):
        return v if v and str(v).strip() else "groq/openai/gpt-oss-120b"

    @field_validator("produto_topico", mode="before")
    @classmethod
    def _default_se_vazio_topico(cls, v):
        return v if v and str(v).strip() else "Produto em destaque do catálogo desta semana"

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

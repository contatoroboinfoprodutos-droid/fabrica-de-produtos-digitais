"""
Tools do CrewAI que expõem o MetaGraphAPI aos agentes.

Cada tool tem um schema de argumentos explícito (pydantic) para que o LLM
saiba exatamente quais campos preencher ao chamá-la.
"""
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from tools.meta_graph_api import MetaGraphAPI, MetaGraphAPIError


# ---------------------------------------------------------------------- #
# Facebook
# ---------------------------------------------------------------------- #
class FacebookPostInput(BaseModel):
    message: str = Field(..., description="Texto completo do post a ser publicado no Facebook.")
    link: Optional[str] = Field(
        None, description="URL opcional a ser anexada ao post (ex.: link do infoproduto)."
    )
    image_url: Optional[str] = Field(
        None,
        description="URL pública de uma imagem para publicar como foto com legenda. "
        "Se omitido, publica um post de texto simples.",
    )


class PublishToFacebookTool(BaseTool):
    name: str = "publish_to_facebook"
    description: str = (
        "Publica um post no feed da Página do Facebook configurada. "
        "Use para divulgar o infoproduto ou o conteúdo final aprovado."
    )
    args_schema: Type[BaseModel] = FacebookPostInput

    def _run(self, message: str, link: Optional[str] = None, image_url: Optional[str] = None) -> str:
        api = MetaGraphAPI()
        try:
            result = api.publish_facebook_post(message=message, link=link, image_url=image_url)
            return f"Publicado no Facebook com sucesso. post_id={result.post_id}"
        except MetaGraphAPIError as exc:
            return f"ERRO ao publicar no Facebook: {exc}"


# ---------------------------------------------------------------------- #
# Instagram
# ---------------------------------------------------------------------- #
class InstagramPostInput(BaseModel):
    image_url: str = Field(
        ..., description="URL pública e acessível da imagem a ser publicada no Instagram."
    )
    caption: str = Field(..., description="Legenda completa do post, incluindo hashtags.")


class PublishToInstagramTool(BaseTool):
    name: str = "publish_to_instagram"
    description: str = (
        "Publica uma imagem com legenda na conta comercial do Instagram configurada, "
        "usando o fluxo de container (media -> media_publish) da Graph API."
    )
    args_schema: Type[BaseModel] = InstagramPostInput

    def _run(self, image_url: str, caption: str) -> str:
        api = MetaGraphAPI()
        try:
            result = api.publish_instagram_post(image_url=image_url, caption=caption)
            return f"Publicado no Instagram com sucesso. post_id={result.post_id}"
        except MetaGraphAPIError as exc:
            return f"ERRO ao publicar no Instagram: {exc}"

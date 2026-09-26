"""
Cliente de baixo nível para a Meta Graph API (v26.0).

Responsável por:
  1. Trocar o token de usuário de longa duração por um Page Access Token
     (necessário para publicar em Páginas do Facebook e em contas do
     Instagram vinculadas a elas).
  2. Publicar posts no feed da Página do Facebook.
  3. Publicar mídia (imagem + legenda) no Instagram via fluxo de
     container (media -> media_publish).

Este módulo não depende do CrewAI — é testável isoladamente. As tools do
CrewAI (em tools/crewai_meta_tools.py) apenas envolvem estas funções.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from config import get_settings

logger = logging.getLogger(__name__)


class MetaGraphAPIError(RuntimeError):
    """Erro genérico ao chamar a Meta Graph API, com corpo da resposta anexado."""

    def __init__(self, message: str, response_body: Optional[dict] = None):
        super().__init__(message)
        self.response_body = response_body or {}


@dataclass
class PublishResult:
    platform: str
    post_id: str
    raw_response: dict


class MetaGraphAPI:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.graph_base_url
        self._page_access_token_cache: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Autenticação
    # ------------------------------------------------------------------ #
    def get_page_access_token(self, force_refresh: bool = False) -> str:
        """
        Troca o token de usuário/longa duração por um Page Access Token
        específico da FB_PAGE_ID configurada, via GET /me/accounts.

        O Page Access Token retornado herda a duração do token de usuário
        (não expira enquanto o token de usuário for válido e o app tiver
        permissões pages_show_list / pages_manage_posts / instagram_basic /
        instagram_content_publish concedidas).
        """
        if self._page_access_token_cache and not force_refresh:
            return self._page_access_token_cache

        url = f"{self.base_url}/me/accounts"
        params = {"access_token": self.settings.meta_long_lived_token}
        resp = requests.get(url, params=params, timeout=30)
        data = self._handle_response(resp)

        for page in data.get("data", []):
            if page.get("id") == self.settings.fb_page_id:
                self._page_access_token_cache = page["access_token"]
                return self._page_access_token_cache

        raise MetaGraphAPIError(
            f"Página {self.settings.fb_page_id} não encontrada entre as páginas "
            "gerenciadas por este token. Verifique permissões e FB_PAGE_ID.",
            response_body=data,
        )

    # ------------------------------------------------------------------ #
    # Facebook
    # ------------------------------------------------------------------ #
    def publish_facebook_post(
        self,
        message: str,
        link: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> PublishResult:
        """
        Publica no feed da Página. Se image_url for informado, usa o
        endpoint /photos (imagem + legenda); caso contrário publica em
        /feed (texto, com link opcional).
        """
        page_token = self.get_page_access_token()

        if self.settings.dry_run:
            logger.info("[DRY_RUN] Facebook post: %s", message[:80])
            return PublishResult("facebook", "dry-run-id", {"dry_run": True})

        if image_url:
            url = f"{self.base_url}/{self.settings.fb_page_id}/photos"
            payload = {
                "url": image_url,
                "caption": message,
                "access_token": page_token,
            }
        else:
            url = f"{self.base_url}/{self.settings.fb_page_id}/feed"
            payload = {"message": message, "access_token": page_token}
            if link:
                payload["link"] = link

        resp = requests.post(url, data=payload, timeout=60)
        data = self._handle_response(resp)
        post_id = data.get("post_id") or data.get("id")
        return PublishResult("facebook", post_id, data)

    # ------------------------------------------------------------------ #
    # Instagram (fluxo de dois passos: media -> media_publish)
    # ------------------------------------------------------------------ #
    def publish_instagram_post(self, image_url: str, caption: str) -> PublishResult:
        page_token = self.get_page_access_token()

        if self.settings.dry_run:
            logger.info("[DRY_RUN] Instagram post: %s", caption[:80])
            return PublishResult("instagram", "dry-run-id", {"dry_run": True})

        creation_id = self._create_instagram_media_container(image_url, caption, page_token)
        return self._publish_instagram_container(creation_id, page_token)

    def _create_instagram_media_container(
        self, image_url: str, caption: str, page_token: str
    ) -> str:
        url = f"{self.base_url}/{self.settings.instagram_account_id}/media"
        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": page_token,
        }
        resp = requests.post(url, data=payload, timeout=60)
        data = self._handle_response(resp)
        creation_id = data.get("id")
        if not creation_id:
            raise MetaGraphAPIError("Falha ao criar container de mídia do Instagram.", data)
        return creation_id

    def _publish_instagram_container(self, creation_id: str, page_token: str) -> PublishResult:
        url = f"{self.base_url}/{self.settings.instagram_account_id}/media_publish"
        payload = {"creation_id": creation_id, "access_token": page_token}
        resp = requests.post(url, data=payload, timeout=60)
        data = self._handle_response(resp)
        post_id = data.get("id")
        return PublishResult("instagram", post_id, data)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _handle_response(resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except ValueError:
            resp.raise_for_status()
            return {}

        if resp.status_code >= 400 or "error" in data:
            error = data.get("error", {})
            raise MetaGraphAPIError(
                f"Meta Graph API error {resp.status_code}: "
                f"{error.get('message', 'erro desconhecido')} "
                f"(type={error.get('type')}, code={error.get('code')})",
                response_body=data,
            )
        return data

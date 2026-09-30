"""Ferramentas dedicadas (prefixo lt_) — independentes de tools/ do projeto."""
import os
import textwrap
import requests
from crewai.tools import tool
from PIL import Image, ImageDraw, ImageFont
from . import config_lt as cfg


def _font(size):
    for path in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


@tool("lt_render_card")
def lt_render_card(filename: str, headline: str, subline: str = "") -> str:
    """Gera uma imagem fixa 1080x1350 (feed IG/TikTok foto) com título e subtítulo.
    Args: filename (ex: post_manha.png), headline (texto principal curto), subline (opcional)."""
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    img = Image.new("RGB", (1080, 1350), (15, 23, 42))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 1020, 70], fill=(250, 204, 21))
    y = 300
    for line in textwrap.wrap(headline, width=20):
        d.text((80, y), line, font=_font(84), fill=(255, 255, 255))
        y += 105
    y += 40
    for line in textwrap.wrap(subline, width=34):
        d.text((80, y), line, font=_font(46), fill=(203, 213, 225))
        y += 60
    d.text((80, 1240), cfg.BRAND_HANDLE, font=_font(44), fill=(250, 204, 21))
    path = os.path.join(cfg.OUTPUT_DIR, filename)
    img.save(path)
    return f"Imagem salva: {path}"


@tool("lt_publicar_instagram")
def lt_publicar_instagram(filename: str, caption: str) -> str:
    """Publica foto no Instagram (Graph API). filename = arquivo gerado por lt_render_card."""
    if cfg.DRY_RUN:
        return f"[DRY_RUN] Instagram não publicado. Arquivo={filename}\nLegenda:\n{caption}"
    if not (cfg.IG_USER_ID and cfg.IG_ACCESS_TOKEN and cfg.PUBLIC_IMAGE_BASE_URL):
        return "ERRO: defina LT_IG_USER_ID, LT_IG_ACCESS_TOKEN e LT_PUBLIC_IMAGE_BASE_URL."
    base = f"https://graph.facebook.com/v21.0/{cfg.IG_USER_ID}"
    r = requests.post(f"{base}/media", data={
        "image_url": f"{cfg.PUBLIC_IMAGE_BASE_URL}/{filename}",
        "caption": caption, "access_token": cfg.IG_ACCESS_TOKEN}, timeout=60)
    if r.status_code != 200:
        return f"ERRO container IG: {r.text}"
    r2 = requests.post(f"{base}/media_publish", data={
        "creation_id": r.json()["id"], "access_token": cfg.IG_ACCESS_TOKEN}, timeout=60)
    return f"Instagram: {r2.status_code} {r2.text}"


@tool("lt_publicar_tiktok")
def lt_publicar_tiktok(filename: str, caption: str) -> str:
    """Publica post de foto no TikTok (Content Posting API). Requer app auditado pelo TikTok;
    sem auditoria, os posts saem como privados."""
    if cfg.DRY_RUN:
        return f"[DRY_RUN] TikTok não publicado. Arquivo={filename}"
    if not (cfg.TIKTOK_ACCESS_TOKEN and cfg.PUBLIC_IMAGE_BASE_URL):
        return "ERRO: defina LT_TIKTOK_ACCESS_TOKEN e LT_PUBLIC_IMAGE_BASE_URL."
    r = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/content/init/",
        headers={"Authorization": f"Bearer {cfg.TIKTOK_ACCESS_TOKEN}",
                 "Content-Type": "application/json; charset=UTF-8"},
        json={"post_info": {"title": caption[:90], "description": caption[:4000],
                            "privacy_level": "PUBLIC_TO_EVERYONE"},
              "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0,
                              "photo_images": [f"{cfg.PUBLIC_IMAGE_BASE_URL}/{filename}"]},
              "post_mode": "DIRECT_POST", "media_type": "PHOTO"}, timeout=60)
    return f"TikTok: {r.status_code} {r.text}"

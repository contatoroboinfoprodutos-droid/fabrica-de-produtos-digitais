"""Ferramentas dedicadas (prefixo lt_) — independentes de tools/ do projeto."""
import io
import logging
import os
import random
import re
import textwrap
import time

import requests
from crewai.tools import tool
from PIL import Image, ImageDraw, ImageFont
from fabrica_produtos import marcas, travas
from . import config_lt as cfg

logger = logging.getLogger("lowticket")
W, H = 1080, 1350
PLACEHOLDER_LINK = "SEU-LINK-DE-CHECKOUT"


def _font(size):
    for path in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _foto_unsplash(consulta):
    """Baixa uma foto do Unsplash (1080x1350). Devolve None se não houver chave ou se falhar."""
    if not cfg.UNSPLASH_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": consulta or cfg.UNSPLASH_QUERY_PADRAO, "per_page": 10,
                    "orientation": "portrait"},
            headers={"Authorization": f"Client-ID {cfg.UNSPLASH_API_KEY}"}, timeout=20)
        r.raise_for_status()
        resultados = r.json().get("results", [])
        if not resultados:
            return None
        url = random.choice(resultados)["urls"]["raw"] + f"&w={W}&h={H}&fit=crop&fm=jpg&q=80"
        foto = requests.get(url, timeout=30)
        foto.raise_for_status()
        return Image.open(io.BytesIO(foto.content)).convert("RGB").resize((W, H))
    except Exception as e:
        logger.warning("Unsplash falhou: %s", e)
        return None


def _quebrar(d, texto, fonte, largura_max):
    """Quebra o texto em linhas medindo a largura REAL em pixels (não em nº de caracteres)."""
    linhas, atual = [], ""
    for palavra in (texto or "").split():
        teste = f"{atual} {palavra}".strip()
        if not atual or d.textlength(teste, font=fonte) <= largura_max:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _slot_do_arquivo(filename):
    """post_tarde.png -> 'tarde'."""
    nome = os.path.splitext(os.path.basename(filename))[0]
    return nome.replace("post_", "", 1)


def _tipo_do_arquivo(filename):
    return cfg.SLOTS.get(_slot_do_arquivo(filename), {}).get("tipo", "VALOR")


def _texto_card_seguro(headline, subline, tipo):
    """Tira markdown e termos proibidos do texto do card; se sobrar pouco, usa o texto do catálogo."""
    h = travas.sanear_texto(travas.limpar_markdown(headline))
    s = travas.sanear_texto(travas.limpar_markdown(subline))
    if len(h) < 5:
        h_modelo, s_modelo = travas.card_modelo(cfg.PRODUTO, tipo)
        h, s = h_modelo, (s or s_modelo)
    return h, s


@tool("lt_render_card")
def lt_render_card(filename: str, headline: str, subline: str = "", tema_imagem: str = "") -> str:
    """Gera uma imagem 1080x1350 (feed IG/FB) com foto de fundo e título/subtítulo por cima.
    Nos posts de oferta (post_tarde) o card também mostra o selo com o preço.
    Args: filename (ex: post_manha.png), headline (texto principal curto), subline (opcional),
    tema_imagem (2 a 4 palavras EM INGLÊS descrevendo a foto de fundo, ex: 'woman studying laptop')."""
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    headline, subline = _texto_card_seguro(headline, subline, _tipo_do_arquivo(filename))
    fundo = Image.new("RGB", (W, H), (15, 23, 42))
    foto = _foto_unsplash(tema_imagem)
    if foto is not None:
        img = Image.blend(foto, fundo, 0.62)  # escurece para o texto ficar legível
    else:
        img = fundo
    d = ImageDraw.Draw(img)
    margem = 80
    largura_max = W - 2 * margem  # nenhuma linha passa daqui
    d.rectangle([60, 60, 1020, 70], fill=(250, 204, 21))

    # Título: reduz a fonte se precisar para caber em no máximo 4 linhas
    y = 300
    for tam in (84, 74, 64):
        fonte_t = _font(tam)
        linhas_t = _quebrar(d, headline, fonte_t, largura_max)
        if len(linhas_t) <= 4:
            break
    for line in linhas_t:
        d.text((margem, y), line, font=fonte_t, fill=(255, 255, 255))
        y += int(tam * 1.25)
    y += 40
    fonte_s = _font(46)
    for line in _quebrar(d, subline, fonte_s, largura_max):
        d.text((margem, y), line, font=fonte_s, fill=(226, 232, 240))
        y += 60

    # Selo de preço, só no post de oferta
    slot = _slot_do_arquivo(filename)
    if cfg.SLOTS.get(slot, {}).get("tipo") == "OFERTA":
        x0, y0, x1, y1 = 600, 1110, 1000, 1290
        d.rounded_rectangle([x0, y0, x1, y1], radius=32, fill=(250, 204, 21))
        escuro = (15, 23, 42)
        f_preco, f_cta = _font(72), _font(32)
        preco = cfg.OFFER_PRICE
        d.text(((x0 + x1) / 2, y0 + 70), preco, font=f_preco, fill=escuro, anchor="mm")
        d.text(((x0 + x1) / 2, y0 + 138), "LINK NA BIO", font=f_cta, fill=escuro, anchor="mm")

    rodape = cfg.BRAND_HANDLE or cfg.BRAND_NAME
    oferta = cfg.SLOTS.get(slot, {}).get("tipo") == "OFERTA"
    limite_rodape = 500 if oferta else largura_max  # na oferta o selo de preço ocupa a direita
    for tam_rodape in (44, 38, 32, 28, 24):
        fonte_rodape = _font(tam_rodape)
        if d.textlength(rodape, font=fonte_rodape) <= limite_rodape:
            break
    d.text((margem, 1240), rodape, font=fonte_rodape, fill=(250, 204, 21))
    path = os.path.join(cfg.OUTPUT_DIR, filename)
    img.save(path, "JPEG" if path.lower().endswith((".jpg", ".jpeg")) else "PNG")
    origem = "com foto do Unsplash" if foto is not None else "fundo liso (sem foto)"
    return f"Imagem salva: {path} ({origem})"


# ----------------------------------------------------------------------------
# Meta: Facebook (página) + Instagram, sem precisar hospedar a imagem
# ----------------------------------------------------------------------------
def _graph(caminho):
    return f"https://graph.facebook.com/{cfg.GRAPH_VERSION}/{caminho}"


def _page_token():
    r = requests.get(_graph("me/accounts"), params={
        "access_token": cfg.META_TOKEN, "fields": "id,name,access_token", "limit": 100}, timeout=30)
    r.raise_for_status()
    for p in r.json().get("data", []):
        if str(p.get("id")) == str(cfg.FB_PAGE_ID):
            return p["access_token"]
    raise RuntimeError("FB_PAGE_ID não encontrado nas páginas do token (confira o ID e as permissões).")


def _limpar_legenda(texto):
    """Facebook/Instagram não entendem markdown: remove os asteriscos (**negrito**, *itálico*)."""
    return re.sub(r"\*+", "", texto or "").strip()


def _problema_do_link(filename, caption):
    """Em posts de OFERTA a legenda precisa conter o link real (LT_OFFER_LINK). Devolve o motivo ou ''."""
    if cfg.SLOTS.get(_slot_do_arquivo(filename), {}).get("tipo") != "OFERTA":
        return ""
    if PLACEHOLDER_LINK in cfg.OFFER_LINK or not cfg.OFFER_LINK.startswith("http"):
        return "a variável LT_OFFER_LINK não está definida com o link real de compra."
    if cfg.OFFER_LINK not in caption:
        return "a legenda não contém o link real (LT_OFFER_LINK); o agente pode ter inventado outro link."
    return ""


def _payload_facebook(caption: str) -> dict:
    """Corpo do POST /photos (sem o token). Sem nenhum campo de segmentação: o post é público para todos."""
    return {"caption": caption, "published": "true"}


def _payload_instagram(image_url: str, caption: str) -> dict:
    """Corpo do POST /media (sem o token). Sem nenhum campo de segmentação."""
    return {"image_url": image_url, "caption": caption}


@tool("lt_publicar_meta")
def lt_publicar_meta(filename: str, caption: str) -> str:
    """Publica a imagem gerada por lt_render_card na página do Facebook e no Instagram.
    Args: filename (arquivo gerado, ex: post_manha.png), caption (legenda final)."""
    caption = _limpar_legenda(caption)
    # Travas em código (fabrica_produtos/travas.py): corrigem o que dá sem inventar nada e bloqueiam o resto.
    caption, acoes, travas_problemas = travas.preparar_legenda(cfg.PRODUTO, caption, _tipo_do_arquivo(filename))
    problemas = list(travas_problemas)
    problema_link = _problema_do_link(filename, caption)
    if problema_link and problema_link not in problemas:
        problemas.append(problema_link)
    problema = "; ".join(problemas)
    # Uma legenda por rede: CTA do canal + hashtags em 3 camadas, feitos em código (travas.finalizar_para_rede)
    tipo_post = _tipo_do_arquivo(filename)
    caption_fb = travas.finalizar_para_rede(cfg.PRODUTO, caption, "facebook", tipo_post)
    caption_ig = travas.finalizar_para_rede(cfg.PRODUTO, caption, "instagram", tipo_post)
    payload_fb, payload_ig = _payload_facebook(caption_fb), _payload_instagram("(URL pública da foto)", caption_ig)
    if cfg.DRY_RUN:
        trava_info = f"\n[TRAVAS] ajustes automáticos: {'; '.join(acoes)}" if acoes else ""
        aviso = f"\n[AVISO] Em modo real esta publicação seria BLOQUEADA: {problema}" if problema else ""
        return (f"[DRY_RUN] Facebook e Instagram NÃO publicados. Arquivo={filename}\n"
                f"Público: {travas.rotulo_publico(payload_fb, payload_ig)}\n"
                f"Legenda Facebook:\n{caption_fb}\n\n"
                f"Legenda Instagram:\n{caption_ig}{trava_info}{aviso}")
    if marcas.ja_publicado("facebook") and marcas.ja_publicado("instagram"):
        return "Já publicado nesta execução no Facebook e no Instagram. Nada a repetir: finalize."
    if PLACEHOLDER_LINK in caption:
        return "ERRO: a legenda contém o link de exemplo. Defina a variável LT_OFFER_LINK com o link real."
    if problema:
        if cfg.PRODUTO is None and cfg.SLOTS.get(_slot_do_arquivo(filename), {}).get("tipo") == "OFERTA":
            marcas.marcar_bloqueio("post de oferta sem produto pronto no catálogo")  # repetir não resolve
        return f"ERRO: publicação bloqueada: {problema}"
    if not cfg.META_CONFIGURADA:
        marcas.marcar_bloqueio("credenciais da Meta ausentes")
        return "ERRO: defina META_LONG_LIVED_TOKEN, FB_PAGE_ID e INSTAGRAM_ACCOUNT_ID."
    path = os.path.join(cfg.OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return f"ERRO: arquivo {path} não encontrado (rode lt_render_card antes)."

    resultado = []
    # 1) Facebook: envia o arquivo direto para a página (se uma tentativa anterior já publicou, não repete)
    try:
        token = _page_token()
        anterior = marcas.lido("facebook")
        if anterior:
            foto_id = anterior.get("photo_id")
            resultado.append("Facebook: já publicado antes nesta execução (não repete)")
        else:
            with open(path, "rb") as f:
                r = requests.post(_graph(f"{cfg.FB_PAGE_ID}/photos"),
                                  data={**payload_fb, "access_token": token},
                                  files={"source": f}, timeout=120)
            if r.status_code != 200:
                return f"Facebook: ERRO {r.status_code} {r.text}\nInstagram: não tentado (sem imagem pública)."
            foto_id = r.json().get("id")
            marcas.marcar("facebook", {"photo_id": foto_id})
            resultado.append(f"Facebook: publicado (photo_id={foto_id}, post_id={r.json().get('post_id')})")
    except Exception as e:
        return f"Facebook: ERRO {e}\nInstagram: não tentado."
    if not foto_id:
        return "\n".join(resultado + ["Instagram: não tentado (sem o id da foto do Facebook)."])

    # 2) Instagram: usa a URL pública que o Facebook gerou para a mesma foto
    if marcas.ja_publicado("instagram"):
        resultado.append("Instagram: já publicado antes nesta execução (não repete)")
        return "\n".join(resultado)
    try:
        info = requests.get(_graph(foto_id), params={"fields": "images", "access_token": token}, timeout=30)
        info.raise_for_status()
        imagem_url = info.json()["images"][0]["source"]
        c = requests.post(_graph(f"{cfg.IG_ACCOUNT_ID}/media"), data={
            **_payload_instagram(imagem_url, caption_ig), "access_token": token}, timeout=60)
        if c.status_code != 200:
            resultado.append(f"Instagram: ERRO container {c.status_code} {c.text}")
            return "\n".join(resultado)
        container = c.json()["id"]
        for _ in range(10):  # espera o container ficar pronto
            st = requests.get(_graph(container), params={"fields": "status_code", "access_token": token},
                              timeout=30).json().get("status_code")
            if st == "FINISHED":
                break
            if st == "ERROR":
                resultado.append("Instagram: ERRO ao processar a imagem")
                return "\n".join(resultado)
            time.sleep(3)
        p = requests.post(_graph(f"{cfg.IG_ACCOUNT_ID}/media_publish"), data={
            "creation_id": container, "access_token": token}, timeout=60)
        if p.status_code == 200:
            marcas.marcar("instagram", {"media_id": p.json().get("id")})
            resultado.append(f"Instagram: publicado (media_id={p.json().get('id')})")
        else:
            resultado.append(f"Instagram: ERRO {p.status_code} {p.text}")
    except Exception as e:
        resultado.append(f"Instagram: ERRO {e}")
    return "\n".join(resultado)


# ----------------------------------------------------------------------------
# Ferramentas antigas (mantidas por compatibilidade; o Instagram direto exige hospedagem própria)
# ----------------------------------------------------------------------------
@tool("lt_publicar_instagram")
def lt_publicar_instagram(filename: str, caption: str) -> str:
    """(Legado) Publica foto no Instagram a partir de URL pública própria. Prefira lt_publicar_meta."""
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

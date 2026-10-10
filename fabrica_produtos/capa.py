"""Capa do produto (PNG 1280x720, 16:9: é o recorte que a vitrine da Cakto mostra) feita em código com Pillow.

Cada tema tem a sua cor, então os produtos não ficam todos iguais. Não mostra preço (preço muda no catálogo, a capa não).
"""
import os

from . import config_fabrica as cfg, travas
from .texto import sem_acentos

LARGURA, ALTURA = 1280, 720
PASTA_PADRAO = os.getenv("FABRICA_CAPAS", "").strip() or "docs/capas"
FONTES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
# (cor de destaque, selo)
CORES = {
    "receitas": ("#22C55E", "RECEITAS"), "financas": ("#F5B83D", "FINANÇAS"), "renda": ("#F97316", "RENDA EXTRA"),
    "casa": ("#14B8A6", "CASA"), "produtividade": ("#8B5CF6", "PRODUTIVIDADE"),
}


# palavra no título -> (cor, selo); vem antes do tema, que só distingue 5 assuntos
SELOS_POR_PALAVRA = [
    ("marketing", ("#EC4899", "MARKETING")), ("ingles", ("#38BDF8", "INGLÊS")),
    ("redacao|copywriting", ("#EAB308", "REDAÇÃO")), ("estudo|concentra", ("#6366F1", "ESTUDOS")),
    ("home office", ("#06B6D4", "HOME OFFICE")),
]


def _cor_e_selo(produto: dict) -> tuple[str, str]:
    import re
    base = sem_acentos(str(produto.get("nome") or "")).lower()
    for padrao, valor in SELOS_POR_PALAVRA:
        if re.search(padrao, base):
            return valor
    return CORES.get(travas.tema_da_legenda(produto, "", None), CORES["produtividade"])


def caminho_da_capa(produto: dict, pasta: str | None = None) -> str:
    return os.path.join(pasta or PASTA_PADRAO, f"{produto['id']}.png")


def _fonte(tamanho: int):
    from PIL import ImageFont
    for f in FONTES:
        if os.path.isfile(f):
            return ImageFont.truetype(f, tamanho)
    return ImageFont.load_default(tamanho)


def _quebrar(texto: str, fnt, largura: int, d) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if d.textlength(teste, font=fnt) <= largura or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    return linhas + ([atual] if atual else [])


def titulo_curto(produto: dict) -> str:
    """'Guia Prático de Finanças Pessoais: Do Zero à Organização' -> 'Finanças Pessoais: Do Zero à Organização'."""
    t = " ".join(str(produto.get("nome") or "").split())
    for prefixo in ("Guia Prático de ", "Guia Prático para ", "Guia de ", "Guia para "):
        if t.lower().startswith(prefixo.lower()):
            return t[len(prefixo):] or t
    return t


def gerar_capa(produto: dict, caminho: str | None = None) -> str:
    from PIL import Image, ImageDraw

    caminho = caminho or caminho_da_capa(produto)
    cor, selo = _cor_e_selo(produto)
    img = Image.new("RGB", (LARGURA, ALTURA), "#121212")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 24, ALTURA], fill=cor)                       # faixa lateral na cor do tema
    d.ellipse([LARGURA - 420, -220, LARGURA + 120, 320], fill="#1c1c1c")  # detalhe de fundo
    d.rounded_rectangle([80, 70, 80 + d.textlength(selo, font=_fonte(30)) + 56, 130], 30, fill=cor)
    d.text((108, 78), selo, font=_fonte(30), fill="#121212")
    titulo = titulo_curto(produto)
    for tamanho in (84, 74, 64, 56, 48):
        fnt = _fonte(tamanho)
        linhas = _quebrar(titulo, fnt, LARGURA - 200, d)
        if len(linhas) <= 4:
            break
    y = 190
    for linha in linhas[:4]:
        d.text((80, y), linha, font=fnt, fill="#FFFFFF")
        y += int(tamanho * 1.18)
    d.text((80, ALTURA - 150), "Guia em PDF  •  entrega por e-mail", font=_fonte(34), fill=cor)
    d.text((80, ALTURA - 90), cfg.MARCA, font=_fonte(30), fill="#9ca3af")
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    img.save(caminho, "PNG", optimize=True)
    return caminho

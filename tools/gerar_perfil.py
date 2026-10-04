"""Gera a imagem de perfil (1080x1080) da marca, com as cores dos cartões do Low Ticket.

Uso: python -m tools.gerar_perfil [saida.png] [INICIAIS]
O nome da marca vem de LT_BRAND_NAME (padrão: Fábrica de Produtos Digitais) e as iniciais saem dele (FPD).
Instagram e Facebook recortam em círculo: tudo fica dentro de um círculo central, com folga nas bordas.
"""
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

LADO = 1080
AZUL = (15, 23, 42)
AMARELO = (250, 204, 21)
_LIGACOES = {"de", "da", "do", "das", "dos", "e", "a", "o"}


def marca() -> str:
    from fabrica_produtos import config_fabrica
    return config_fabrica.MARCA


def iniciais_da_marca(nome: str) -> str:
    """'Fábrica de Produtos Digitais' -> 'FPD' (ignora 'de', 'da', 'e'...; no máximo 3 letras)."""
    palavras = [p for p in re.split(r"\s+", nome.strip()) if p and p.lower() not in _LIGACOES]
    return "".join(p[0].upper() for p in palavras)[:3] or "?"


def _fonte(tamanho: int):
    for caminho in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "C:/Windows/Fonts/arialbd.ttf"):
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def gerar(saida: str = "assets/perfil.png", iniciais: str | None = None) -> str:
    iniciais = iniciais or iniciais_da_marca(marca())
    img = Image.new("RGB", (LADO, LADO), AZUL)
    d = ImageDraw.Draw(img)
    c = LADO // 2
    # anel fino e disco amarelo (cabem num círculo de ~86% do lado)
    d.ellipse([c - 450, c - 450, c + 450, c + 450], outline=AMARELO, width=10)
    d.ellipse([c - 380, c - 380, c + 380, c + 380], fill=AMARELO)
    # iniciais em azul sobre o disco amarelo
    tamanho = {1: 380, 2: 330}.get(len(iniciais), 255)  # 3 letras: menor, para caber no disco
    d.text((c, c - 55), iniciais, font=_fonte(tamanho), fill=AZUL, anchor="mm")
    # raio pequeno embaixo: ideia de "rápido"
    x, y, k = c, c + 175, 1.0
    raio = [(x + 38, y - 95), (x - 62, y + 10), (x - 5, y + 10), (x - 38, y + 95), (x + 62, y - 10), (x + 5, y - 10)]
    d.polygon(raio, fill=AZUL)
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    img.save(saida, "PNG")
    return saida


if __name__ == "__main__":
    print(gerar(sys.argv[1] if len(sys.argv) > 1 else "assets/perfil.png",
                sys.argv[2] if len(sys.argv) > 2 else None))

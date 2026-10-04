"""Gera a imagem de perfil (1080x1080) da marca, com as cores dos cartões do Low Ticket.

Uso: python -m tools.gerar_perfil [saida.png]
Marca e cores vêm do config do Low Ticket (LT_BRAND_NAME). Instagram e Facebook recortam em círculo: tudo
fica dentro de um círculo central, com folga nas bordas.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

LADO = 1080
AZUL = (15, 23, 42)
AMARELO = (250, 204, 21)


def _fonte(tamanho: int):
    for caminho in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "C:/Windows/Fonts/arialbd.ttf"):
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def gerar(saida: str = "assets/perfil_digital_rapido.png", iniciais: str = "DR") -> str:
    img = Image.new("RGB", (LADO, LADO), AZUL)
    d = ImageDraw.Draw(img)
    c = LADO // 2
    # anel fino e disco amarelo (cabem num círculo de ~86% do lado)
    d.ellipse([c - 450, c - 450, c + 450, c + 450], outline=AMARELO, width=10)
    d.ellipse([c - 380, c - 380, c + 380, c + 380], fill=AMARELO)
    # iniciais em azul sobre o disco amarelo
    d.text((c, c - 55), iniciais, font=_fonte(330), fill=AZUL, anchor="mm")
    # raio pequeno embaixo: ideia de "rápido"
    x, y, k = c, c + 175, 1.0
    raio = [(x + 38, y - 95), (x - 62, y + 10), (x - 5, y + 10), (x - 38, y + 95), (x + 62, y - 10), (x + 5, y - 10)]
    d.polygon(raio, fill=AZUL)
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    img.save(saida, "PNG")
    return saida


if __name__ == "__main__":
    print(gerar(sys.argv[1] if len(sys.argv) > 1 else "assets/perfil_digital_rapido.png"))

"""Gera a foto de capa (1640x856) da página do Facebook, no mesmo estilo da foto de perfil.

Uso: python -m tools.gerar_capa [saida.png]
O nome vem de LT_BRAND_NAME (padrão: Fábrica de Produtos Digitais). Zona segura: o Facebook mostra só o miolo
(computador ~1640x624, celular ~1520x856), então o texto fica no centro e a foto de perfil, que cobre o canto
inferior esquerdo no computador, não encosta nele.
"""
import os
import sys

from PIL import Image, ImageDraw

from .gerar_perfil import AMARELO, AZUL, _fonte, marca

LARGURA, ALTURA = 1640, 856
SUBTITULO = "Guias em PDF, curtos e práticos"
_AZUL_CLARO = (28, 40, 68)  # raios decorativos, quase imperceptíveis


def _raio(d, x, y, escala, cor):
    pts = [(38, -95), (-62, 10), (-5, 10), (-38, 95), (62, -10), (5, -10)]
    d.polygon([(x + px * escala, y + py * escala) for px, py in pts], fill=cor)


def _ajustar(d, texto, maximo, tamanhos):
    for t in tamanhos:
        f = _fonte(t)
        if d.textlength(texto, font=f) <= maximo:
            return f
    return _fonte(tamanhos[-1])


def _linhas_do_nome(d, nome, maximo=1180):
    """(linhas, fonte): uma linha se couber em fonte >= 64; senão duas, divididas perto do meio."""
    for t in (96, 88, 80, 72, 64):
        f = _fonte(t)
        if d.textlength(nome, font=f) <= maximo:
            return [nome], f
    palavras = nome.split()
    melhor = min(range(1, len(palavras)), key=lambda i: abs(len(" ".join(palavras[:i])) - len(" ".join(palavras[i:]))),
                 default=0)
    linhas = [" ".join(palavras[:melhor]), " ".join(palavras[melhor:])] if melhor else [nome]
    for t in (72, 64, 56, 48, 40, 32):
        f = _fonte(t)
        if all(d.textlength(ln, font=f) <= maximo for ln in linhas):
            return linhas, f
    return linhas, _fonte(32)


def gerar(saida: str = "assets/capa_facebook.png", nome: str | None = None) -> str:
    nome = nome or marca()
    img = Image.new("RGB", (LARGURA, ALTURA), AZUL)
    d = ImageDraw.Draw(img)
    # decoração nas bordas (fora da zona segura do celular, pode ser cortada)
    for x, y, k in ((120, 250, 3.2), (1520, 600, 3.2), (330, 700, 1.6), (1310, 170, 1.6)):
        _raio(d, x, y, k, _AZUL_CLARO)
    d.rectangle([0, 0, LARGURA, 14], fill=AMARELO)
    d.rectangle([0, ALTURA - 14, LARGURA, ALTURA], fill=AMARELO)
    cx, cy = LARGURA // 2, ALTURA // 2
    linhas, f_nome = _linhas_do_nome(d, nome)
    f_sub = _ajustar(d, SUBTITULO, 1000, (46, 42, 38))
    altura = f_nome.size * 1.15
    topo = cy - 40 - (len(linhas) - 1) * altura / 2
    for i, ln in enumerate(linhas):
        d.text((cx, topo + i * altura), ln, font=f_nome, fill=(255, 255, 255), anchor="mm")
    base = topo + (len(linhas) - 1) * altura
    d.rectangle([cx - 90, base + 68, cx + 90, base + 78], fill=AMARELO)
    d.text((cx, base + 130), SUBTITULO, font=f_sub, fill=AMARELO, anchor="mm")
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    img.save(saida, "PNG")
    return saida


if __name__ == "__main__":
    print(gerar(sys.argv[1] if len(sys.argv) > 1 else "assets/capa_facebook.png"))

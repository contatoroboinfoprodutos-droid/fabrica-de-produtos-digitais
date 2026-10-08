#!/usr/bin/env python3
"""Gera Reels verticais (1080x1920, 8 s, 30 fps) e as legendas, a partir do catálogo de produtos.

Uso:  python scripts/generate_reels.py [--max 10] [--only slug] [--saida reels]

- Lê (na ordem) data/produtos.json, produtos.json ou catalogo/catalogo.json. Aceita lista ou {"produtos": [...]}.
  Campos: titulo|nome, descricao|promessa, preco_texto|preco, capa (opcional), categoria (opcional).
  Se o item tem "status", só entram os "pronto"; se tem "link_compra", só link da Cakto.
- Desenha cada quadro com Pillow (fundo #121212 + capa com blur leve, logo FPD, título, selo de preço, CTA nos
  últimos 2 s, zoom leve e fade in) e entrega ao ffmpeg, que grava o mp4. Só bibliotecas gratuitas.
- Música: assets/music/{happy,lofi,corporate}.mp3 em volume 0.15 (corte 0-8 s). Sem o arquivo, o vídeo sai sem áudio.
- Grava reels/<slug>.mp4 e reels/legendas.txt.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, DURACAO = 1080, 1920, 30, 8
AMARELO = (255, 214, 10)   # #FFD60A
FUNDO = (18, 18, 18)       # #121212
BRANCO = (255, 255, 255)
LINK = os.getenv("REELS_LINK", "").strip() or "bit.ly/4rWbLt5"
PRECO_PADRAO = "A partir de R$ 8,90"
SUBTITULO = "Guias em PDF, curtos e práticos"
VOLUME = 0.15
PASTA_MUSICA = os.getenv("REELS_MUSICA", "").strip() or "assets/music"
FONTES_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
CAMINHOS_CATALOGO = ["data/produtos.json", "produtos.json", "catalogo/catalogo.json"]

MUSICA_POR_CATEGORIA = {"receitas": "happy", "rotina": "lofi", "financas": "corporate",
                        "foco": "lofi", "produtividade": "corporate", "estudos": "lofi"}
HASHTAGS = {
    "receitas": "#receitas #marmita #fit",
    "financas": "#financas #organizacao #rotina",
    "produtividade": "#produtividade #organizacao #rotina",
    "foco": "#foco #produtividade #rotina",
    "estudos": "#estudos #foco #rotina",
    "rotina": "#rotina #organizacao #produtividade",
}
# ordem importa: "Produtividade e Organização da Rotina" deve cair em produtividade, não em rotina
PALAVRAS_CATEGORIA = [
    ("receitas", ("receita", "marmit", "cardapio", "aliment", "culinar")),
    ("financas", ("financ", "dinheiro", "orcamento", "gastos")),
    ("produtividade", ("produtiv", "organiza")),
    ("foco", ("foco", "interrup", "concentra")),
    ("estudos", ("estud", "aprend")),
    ("rotina", ("rotina",)),
]


# ----------------------------------------------------------------------------
# Dados
# ----------------------------------------------------------------------------
def sem_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c))


def slug(texto: str, limite: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", sem_acentos(texto).lower()).strip("-")
    return (s[:limite].strip("-")) or "produto"


def carregar_produtos(caminho: str | None = None) -> list[dict]:
    caminhos = [caminho] if caminho else CAMINHOS_CATALOGO
    for c in caminhos:
        if c and os.path.isfile(c):
            with open(c, encoding="utf-8") as f:
                dados = json.load(f)
            lista = dados if isinstance(dados, list) else (dados.get("produtos") or dados.get("pacotes") or [])
            return [p for p in lista if isinstance(p, dict)]
    return []


def link_cakto(link: str) -> bool:
    return bool(re.match(r"^https://pay\.cakto\.com\.br/\S+$", str(link or "").strip()))


def titulo_de(p: dict) -> str:
    return " ".join(str(p.get("titulo") or p.get("nome") or "").split())


def selecionar(produtos: list[dict], maximo: int | None = None, so: str | None = None) -> list[dict]:
    """Só produto vendável: 'pronto' (se houver status) e link da Cakto (se houver link). Mais novos primeiro."""
    ok = []
    for p in produtos:
        if not titulo_de(p):
            continue
        if "status" in p and p.get("status") != "pronto":
            continue
        if "link_compra" in p and not link_cakto(p.get("link_compra")):
            continue
        ok.append(p)
    ok.sort(key=lambda p: str(p.get("criado_em") or ""), reverse=True)
    if so:
        ok = [p for p in ok if slug(titulo_de(p)) == so]
    return ok[:maximo] if maximo else ok


def categoria_de(p: dict) -> str:
    explicita = slug(str(p.get("categoria") or "")).replace("-", "")
    if explicita in MUSICA_POR_CATEGORIA:
        return explicita
    texto = sem_acentos(" ".join(str(p.get(k) or "") for k in ("categoria", "titulo", "nome", "promessa", "descricao"))).lower()
    for cat, palavras in PALAVRAS_CATEGORIA:
        if any(x in texto for x in palavras):
            return cat
    return "rotina"


def preco_de(p: dict) -> str:
    t = str(p.get("preco_texto") or "").strip()
    if t:
        return t
    try:
        v = float(str(p.get("preco")).replace(",", "."))
        return "R$ " + f"{v:.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return PRECO_PADRAO


def descricao_curta(p: dict, limite: int = 120) -> str:
    t = " ".join(str(p.get("descricao") or p.get("promessa") or p.get("descricao_oferta") or "").split())
    t = re.split(r"(?<=[.!?])\s", t)[0] if t else ""
    if len(t) > limite:
        t = t[:limite].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return t


def legenda_de(p: dict) -> str:
    linhas = [titulo_de(p), descricao_curta(p), HASHTAGS[categoria_de(p)], f"Link na bio: {LINK}"]
    return "\n".join(l for l in linhas if l)


def escolher_musica(titulo: str, categoria: str | None = None) -> str:
    """happy (comida), corporate (dinheiro/produtividade) ou lofi (resto), pelo título; sem palavra-chave usa a categoria."""
    t = sem_acentos(titulo).lower()
    if re.search(r"marmit|receit|\bfit\b|comida", t):
        return "happy"
    if re.search(r"finan|dinheiro|produtiv", t):
        return "corporate"
    return MUSICA_POR_CATEGORIA.get(categoria or "", "lofi")


def musica_de(p: dict, pasta: str | None = None) -> str | None:
    """Caminho do mp3 escolhido, ou None se não existir/estiver vazio (o vídeo sai sem áudio)."""
    arq = os.path.join(pasta or PASTA_MUSICA, escolher_musica(titulo_de(p), categoria_de(p)) + ".mp3")
    return arq if os.path.isfile(arq) and os.path.getsize(arq) > 1000 else None


# ----------------------------------------------------------------------------
# Desenho
# ----------------------------------------------------------------------------
def fonte(tamanho: int):
    for f in FONTES_BOLD:
        if os.path.isfile(f):
            return ImageFont.truetype(f, tamanho)
    return ImageFont.load_default(tamanho)


def quebrar(texto: str, fnt, largura: int) -> list[str]:
    d = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if d.textlength(teste, font=fnt) <= largura or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    return linhas + ([atual] if atual else [])


def ajustar_titulo(texto: str, largura: int = 900) -> tuple[list[str], "ImageFont.FreeTypeFont"]:
    """Maior fonte em que o título cabe em 2 linhas; só se não couber usa 3 (e fonte menor)."""
    for max_linhas, tamanhos in ((2, range(110, 63, -4)), (3, range(88, 47, -4)), (4, range(60, 39, -4))):
        for t in tamanhos:
            f = fonte(t)
            ls = quebrar(texto, f, largura)
            if len(ls) <= max_linhas:
                return ls, f
    f = fonte(40)
    return quebrar(texto, f, largura)[:5], f


def raio(d: ImageDraw.ImageDraw, x: int, y: int, h: int, cor) -> None:
    """Raio ⚡ desenhado como polígono (não depende de a fonte ter o emoji)."""
    pts = [(0.62, 0.0), (0.12, 0.56), (0.48, 0.56), (0.30, 1.0), (0.88, 0.40), (0.52, 0.40)]
    d.polygon([(x + px * h * 0.8, y + py * h) for px, py in pts], fill=cor)


def fundo_base(capa: str | None, escala: float = 1.12) -> Image.Image:
    """Fundo maior que o vídeo (para o zoom): #121212 + brilho amarelo suave, ou a capa com blur leve."""
    bw, bh = int(W * escala), int(H * escala)
    img = Image.new("RGB", (bw, bh), FUNDO)
    if capa and os.path.isfile(capa):
        try:
            c = Image.open(capa).convert("RGB")
            r = max(bw / c.width, bh / c.height)
            c = c.resize((int(c.width * r) + 1, int(c.height * r) + 1), Image.LANCZOS)
            l, t = (c.width - bw) // 2, (c.height - bh) // 2
            c = c.crop((l, t, l + bw, t + bh)).filter(ImageFilter.GaussianBlur(6))
            return Image.blend(img, c, 0.55)
        except OSError:
            pass
    brilho = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(brilho).ellipse((bw * 0.1, bh * 0.28, bw * 0.9, bh * 0.62), fill=70)
    brilho = brilho.filter(ImageFilter.GaussianBlur(160))
    return Image.composite(Image.new("RGB", (bw, bh), AMARELO), img, brilho)


class Camada:
    """Elemento estático RGBA, guardado só na sua caixa (rápido de compor por quadro)."""

    def __init__(self, img: Image.Image):
        self.box = img.getchannel("A").getbbox() or (0, 0, 1, 1)
        rec = img.crop(self.box)
        self.rgb = np.asarray(rec.convert("RGB"), dtype=np.float32)
        self.alpha = np.asarray(rec.getchannel("A"), dtype=np.float32)[..., None] / 255.0

    def compor(self, quadro: np.ndarray, k: float) -> None:
        if k <= 0:
            return
        l, t, r, b = self.box
        a = self.alpha * min(1.0, k)
        reg = quadro[t:b, l:r]
        reg += (self.rgb - reg) * a


def camada_logo() -> Camada:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = fonte(64)
    d.rounded_rectangle((60, 90, 60 + 330, 90 + 120), radius=28, fill=AMARELO)
    d.text((60 + 38, 90 + 60), "FPD", font=f, fill=(0, 0, 0), anchor="lm")
    raio(d, 60 + 208, 90 + 24, 72, (0, 0, 0))
    return Camada(img)


def camada_titulo(titulo: str) -> Camada:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    linhas, f = ajustar_titulo(titulo)
    altura = int(f.size * 1.18)
    y = H // 2 - (len(linhas) * altura) // 2 - 60
    for i, l in enumerate(linhas):
        yy = y + i * altura
        d.text((W // 2 + 4, yy + 5), l, font=f, fill=(0, 0, 0, 170), anchor="mt")   # sombra
        d.text((W // 2, yy), l, font=f, fill=BRANCO, anchor="mt")
    fs = fonte(42)
    d.text((W // 2, y + len(linhas) * altura + 50), SUBTITULO, font=fs, fill=(210, 210, 205), anchor="mt")
    return Camada(img)


def camada_preco(preco: str) -> Camada:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = fonte(74)
    for tam in range(74, 40, -4):
        f = fonte(tam)
        if d.textlength(preco, font=f) <= 780:
            break
    larg = int(d.textlength(preco, font=f)) + 120
    x0, y0 = (W - larg) // 2, 1580
    d.rounded_rectangle((x0, y0, x0 + larg, y0 + 150), radius=75, fill=AMARELO)
    d.text((W // 2, y0 + 75), preco, font=f, fill=(0, 0, 0), anchor="mm")
    return Camada(img)


def camada_cta() -> Camada:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    texto = f"Link na bio - {LINK}"
    f = fonte(52)
    for tam in range(52, 30, -2):
        f = fonte(tam)
        if d.textlength(texto, font=f) <= 900:
            break
    larg = int(d.textlength(texto, font=f)) + 90
    x0, y0 = (W - larg) // 2, 1380
    d.rounded_rectangle((x0, y0, x0 + larg, y0 + 120), radius=60, fill=(18, 18, 18, 235), outline=AMARELO, width=5)
    d.text((W // 2, y0 + 60), texto, font=f, fill=BRANCO, anchor="mm")
    return Camada(img)


def montar_quadros(p: dict, duracao: float | None = None):
    """Gerador de quadros (numpy uint8 HxWx3), um por 1/FPS s. Zoom 0→8 %, fade in do texto, CTA nos últimos 2 s."""
    duracao = duracao or DURACAO
    bg = fundo_base(p.get("capa"))
    bw, bh = bg.size
    logo, titulo, preco, cta = camada_logo(), camada_titulo(titulo_de(p)), camada_preco(preco_de(p)), camada_cta()
    total = int(round(duracao * FPS))
    cta_ini = max(0.0, duracao - 2.0)
    for i in range(total):
        t = i / FPS
        zoom = 1.0 + 0.08 * (t / duracao)
        vw, vh = bw / zoom, bh / zoom
        l, tp = (bw - vw) / 2, (bh - vh) / 2
        base = bg.resize((W, H), Image.BILINEAR, box=(l, tp, l + vw, tp + vh))
        q = np.asarray(base, dtype=np.float32).copy()
        fade = t / 0.8
        logo.compor(q, fade)
        titulo.compor(q, (t - 0.2) / 0.8)
        preco.compor(q, (t - 0.5) / 0.8)
        cta.compor(q, (t - cta_ini) / 0.5)
        yield np.clip(q, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------
# Vídeo (ffmpeg)
# ----------------------------------------------------------------------------
def _ffmpeg(saida: str, quadros, duracao: float, musica: str | None) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    if musica:  # repete se o mp3 for curto; volume 0.15; corta em 0-8 s; some no fim
        cmd += ["-stream_loop", "-1", "-i", musica, "-map", "0:v", "-map", "1:a",
                "-af", f"volume={VOLUME},afade=t=out:st={max(0.0, duracao - 0.6):.2f}:d=0.6", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-t", f"{duracao:g}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
            "-movflags", "+faststart", saida]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for q in quadros:
            proc.stdin.write(q.tobytes())
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
    erro = proc.stderr.read().decode("utf-8", "replace")
    proc.stderr.close()
    proc.wait()
    return subprocess.CompletedProcess(cmd, proc.returncode, "", erro)


def gerar_video(p: dict, saida: str, duracao: float | None = None, pasta_musica: str | None = None) -> dict:
    """Grava o mp4. Se a música falhar, regrava sem áudio (nunca quebra por causa do mp3)."""
    duracao = duracao or DURACAO
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg não encontrado")
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    musica = musica_de(p, pasta_musica)
    r = _ffmpeg(saida, montar_quadros(p, duracao), duracao, musica)
    if r.returncode != 0 and musica:
        print(f"  aviso: música {musica} falhou ({r.stderr.strip()[:120]}); gerando sem áudio")
        musica = None
        r = _ffmpeg(saida, montar_quadros(p, duracao), duracao, None)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {r.stderr.strip()[:300]}")
    return {"arquivo": saida, "musica": musica}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogo", default="")
    ap.add_argument("--saida", default="reels")
    ap.add_argument("--max", type=int, default=int(os.getenv("REELS_MAX", "10") or 10), help="0 = todos")
    ap.add_argument("--only", default="", help="slug de um produto")
    a = ap.parse_args(argv)

    produtos = selecionar(carregar_produtos(a.catalogo or None), a.max or None, a.only or None)
    if not produtos:
        print("Nenhum produto pronto com link da Cakto: nada a gerar.")
        return 0
    os.makedirs(a.saida, exist_ok=True)
    legendas, falhas = [], 0
    for p in produtos:
        nome = slug(titulo_de(p))
        destino = os.path.join(a.saida, nome + ".mp4")
        print(f"→ {titulo_de(p)}  [{categoria_de(p)}]  {preco_de(p)}")
        try:
            r = gerar_video(p, destino)
            print(f"  ok: {destino} ({'com música ' + os.path.basename(r['musica']) if r['musica'] else 'sem áudio'})")
            legendas.append(f"=== {nome}.mp4 ===\n{legenda_de(p)}\n")
        except Exception as e:  # um produto com erro não derruba os outros
            falhas += 1
            print(f"  FALHOU: {e}")
    with open(os.path.join(a.saida, "legendas.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(legendas))
    print(f"{len(legendas)} vídeo(s) gerado(s), {falhas} falha(s).")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())

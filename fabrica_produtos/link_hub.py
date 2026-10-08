"""agente_link_hub: gera a página única "link na bio" a partir do catálogo REAL.

Sem LLM de propósito: a página só pode conter o que está no catálogo (nome, promessa, preço e link de compra
de produtos com status 'pronto'). Nada de produto ou link inventado, nada de segmentação de público.
Saída padrão: docs/link-na-bio.html (publicada pelo GitHub Pages).
"""
import html
import logging
import os

from . import catalogo, config_fabrica as cfg, travas

logger = logging.getLogger("fabrica")

SAIDA_PADRAO = os.getenv("FABRICA_HUB_SAIDA", "").strip() or "docs/link-na-bio.html"
TITULO = "Fábrica de Produtos Digitais"
SUBTITULO = "Escolha seu guia abaixo 👇"
SELO = "Todos em PDF imediato"
MAX_DESC = 140


def produtos_do_hub(caminho: str | None = None) -> list[dict]:
    """Só produtos 'pronto' com link de compra válido, do mais novo para o mais antigo."""
    ps = [p for p in catalogo.carregar(caminho)["produtos"]
          if p.get("status") == "pronto" and travas.link_ok(p.get("link_compra", ""))]
    return list(reversed(ps))


def descricao_curta(p: dict) -> str:
    """Usa a promessa que já está no catálogo (nada é inventado), sem termos proibidos, em até MAX_DESC letras."""
    texto = travas.sanear_texto(str(p.get("promessa") or "").strip())
    if len(texto) > MAX_DESC:
        texto = texto[:MAX_DESC].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return texto


def _card(p: dict) -> str:
    e = html.escape
    desc = descricao_curta(p)
    return (
        '<article class="card">'
        f'<h3><a href="{e(p["link_compra"], quote=True)}" target="_blank" rel="noopener">{e(p["nome"])}</a></h3>'
        + (f'<p class="desc">{e(desc)}</p>' if desc else "")
        + f'<span class="badge">{e(p.get("preco_texto") or "")}</span>'
        f'<a class="btn" href="{e(p["link_compra"], quote=True)}" target="_blank" rel="noopener">Comprar agora</a>'
        "</article>"
    )


CSS = """
:root{--bg:#0a0a0a;--surface:#141414;--surface-2:#1e1e1e;--yellow:#ffd600;--yellow-hover:#f5cc00;--text:#f6f4ef;--muted:#9e9e98;--border:#2e2e2e}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:440px;margin:0 auto;padding:32px 20px 40px}
.logo{display:inline-flex;align-items:center;gap:8px}
.fpd{width:32px;height:32px;border-radius:8px;background:var(--yellow);color:#000;font-weight:900;font-size:12px;display:flex;align-items:center;justify-content:center}
.pill{display:inline-block;margin-top:20px;padding:6px 12px;border-radius:999px;background:var(--yellow);color:#000;font-size:10px;font-weight:900;letter-spacing:.14em;text-transform:uppercase}
h1{margin:20px 0 0;font-size:32px;line-height:.95;letter-spacing:-.04em;font-weight:900;text-transform:uppercase}
h1 span{color:var(--yellow)}
.sub{margin:14px 0 24px;font-size:15px;font-weight:700;color:var(--text)}
.card{position:relative;margin-bottom:14px;padding:16px;border-radius:18px;background:var(--surface);border:1px solid var(--border)}
.card h3{margin:0;font-size:16px;line-height:1.2;letter-spacing:-.02em;font-weight:900;padding-right:84px}
.card h3 a{color:var(--text);text-decoration:none}
.desc{margin:8px 0 0;font-size:13px;line-height:1.4;color:var(--muted)}
.badge{position:absolute;top:14px;right:14px;padding:4px 10px;border-radius:999px;background:var(--surface-2);border:1px solid var(--yellow);color:var(--yellow);font-size:12px;font-weight:900}
.btn{display:flex;align-items:center;justify-content:center;height:44px;margin-top:16px;border-radius:999px;background:var(--yellow);color:#000;font-weight:900;font-size:13px;letter-spacing:.04em;text-transform:uppercase;text-decoration:none}
.btn:hover{background:var(--yellow-hover)}
.vazio{padding:20px;border-radius:18px;background:var(--surface);border:1px solid var(--border);color:var(--muted);font-size:14px}
footer{margin-top:28px;display:flex;justify-content:center;align-items:center;gap:8px;font-size:11px;font-weight:900;letter-spacing:.14em;text-transform:uppercase}
footer .fpd{width:24px;height:24px;font-size:9px;border-radius:6px}
"""


def gerar_html(produtos: list[dict]) -> str:
    cards = "".join(_card(p) for p in produtos) or '<div class="vazio">Novos guias em breve.</div>'
    return (
        '<!DOCTYPE html>\n<html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{TITULO}</title>"
        f'<meta name="description" content="{html.escape(SUBTITULO + " " + SELO, quote=True)}">'
        f"<style>{CSS}</style></head><body><main>"
        '<div class="logo"><div class="fpd">FPD</div></div>'
        '<h1>Fábrica de <br><span>Produtos</span> Digitais</h1>'
        f'<p class="sub">{html.escape(SUBTITULO)}<br><span style="color:var(--muted);font-weight:500">{html.escape(SELO)}</span></p>'
        f"<section>{cards}</section>"
        f'<footer><div class="fpd">FPD</div><span>{TITULO}</span></footer>'
        "</main></body></html>\n"
    )


def atualizar(caminho_catalogo: str | None = None, saida: str | None = None) -> dict:
    """Gera a página. Só grava se o conteúdo mudou. Devolve {'arquivo', 'produtos', 'mudou'}."""
    saida = saida or SAIDA_PADRAO
    ps = produtos_do_hub(caminho_catalogo)
    novo = gerar_html(ps)
    try:
        with open(saida, encoding="utf-8") as f:
            antigo = f.read()
    except OSError:
        antigo = None
    mudou = novo != antigo
    if mudou:
        os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
        with open(saida, "w", encoding="utf-8") as f:
            f.write(novo)
    return {"arquivo": saida, "produtos": len(ps), "mudou": mudou}

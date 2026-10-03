"""Travas em código (biblioteca padrão apenas).

Tudo aqui é verificado por regra, não por LLM: nenhum modelo consegue "convencer" estas funções.
- verificar_produto: o produto tem entrega real e respeita as regras de preço e de linguagem?
- verificar_anuncio / preparar_legenda: o texto do anúncio só afirma o que está no catálogo?
"""
import copy
import re

from . import config_fabrica as cfg
from .texto import contar_palavras, formatar_preco, parse_preco, sem_acentos

PLACEHOLDER = "SEU-LINK-DE-CHECKOUT"

# Escritos SEM acento: o texto é normalizado antes de comparar.
_PADROES_PROIBIDOS = [
    r"primeira\s*venda",
    r"lucr\w*",
    r"testad[oa]s?",
    r"garantid[oa]s?",
    r"garanti[ae]\s+de\s+(?:ganho|lucro|resultado)s?",
    r"enriquec\w*",
    r"milion\w*",
    r"fique\s*rico",
    r"sem\s*esforco",
    r"dinheiro\s*facil",
    r"ganhe\s*dinheiro",
    r"resultados?\s*(?:rapidos?|imediatos?)",
    r"comprovad[oa]s?",
    r"\bcur(?:a|ar|am)\b",
    r"100\s*%",
]
_RE_PROIBIDOS = re.compile("|".join(f"(?:{p})" for p in _PADROES_PROIBIDOS))
_RE_URL = re.compile(r"https?://\S+")
_RE_PRECO = re.compile(r"R\$\s*\d+(?:[.,]\d{1,2})?")


# ----------------------------------------------------------------------------
# Termos proibidos
# ----------------------------------------------------------------------------
def encontrar_termos(texto: str) -> list[str]:
    """Devolve os termos proibidos encontrados (sem repetição, em minúsculas e sem acento)."""
    achados = [m.group(0) for m in _RE_PROIBIDOS.finditer(sem_acentos(texto or "").lower())]
    return list(dict.fromkeys(achados))


def _sanear_linha(linha: str) -> str:
    partes = [p for p in linha.split(" ") if not (p.startswith("#") and encontrar_termos(p))]
    linha = " ".join(partes)
    frases = re.split(r"(?<=[.!?])\s+", linha)
    return " ".join(f for f in frases if not encontrar_termos(f)).strip()


def sanear_texto(texto: str) -> str:
    """Remove (não reescreve) as frases e hashtags que contêm termos proibidos."""
    linhas = [_sanear_linha(l) for l in (texto or "").split("\n")]
    limpo = "\n".join(linhas)
    return re.sub(r"\n{3,}", "\n\n", limpo).strip()


def limpar_markdown(texto: str) -> str:
    """Facebook e Instagram não entendem markdown: tira asteriscos e crases."""
    return re.sub(r"[*`]+", "", texto or "").strip()


# ----------------------------------------------------------------------------
# Link
# ----------------------------------------------------------------------------
def link_ok(link: str) -> bool:
    link = (link or "").strip()
    if PLACEHOLDER.lower() in link.lower():
        return False
    return bool(re.fullmatch(r"https://[^\s/]+\.[^\s/]+\S*", link))


def _urls(texto: str) -> list[str]:
    return [u.rstrip(".,;:!?)\"'") for u in _RE_URL.findall(texto or "")]


# ----------------------------------------------------------------------------
# Produto
# ----------------------------------------------------------------------------
def palavras_minimas(preco: float | None) -> int:
    """Quanto conteúdo o comprador precisa receber, no mínimo, para cada faixa de preço."""
    if preco is None or preco <= 9.90:
        return 600
    if preco <= 19.90:
        return 1400
    return 2200


def _capitulos(p: dict) -> list[dict]:
    return [c for c in (p.get("capitulos") or []) if isinstance(c, dict)]


def campos_de_texto(p: dict):
    """(nome_do_campo, texto) de tudo o que o comprador ou o anúncio vão ler."""
    for campo in ("nome", "promessa", "publico", "descricao_oferta"):
        yield campo, str(p.get(campo) or "")
    for i, c in enumerate(p.get("conteudos") or []):
        yield f"conteudos[{i}]", str(c)
    for i, cap in enumerate(_capitulos(p)):
        yield f"capitulos[{i}].titulo", str(cap.get("titulo") or "")
        yield f"capitulos[{i}].texto", str(cap.get("texto") or "")


def verificar_produto(p: dict) -> list[str]:
    """Lista de problemas que impedem aprovar o produto (vazia = passou nas travas)."""
    problemas = []
    nome = str(p.get("nome") or "").strip()
    if not nome:
        problemas.append("nome vazio")
    elif len(nome) > 80:
        problemas.append("nome com mais de 80 caracteres")

    preco = parse_preco(p.get("preco"))
    if preco is None:
        problemas.append("preço ausente ou inválido")
    elif not (cfg.PRECO_MIN <= preco <= cfg.PRECO_MAX):
        problemas.append(f"preço {formatar_preco(preco)} fora da faixa "
                         f"{formatar_preco(cfg.PRECO_MIN)} a {formatar_preco(cfg.PRECO_MAX)}")

    conteudos = [c for c in (p.get("conteudos") or []) if str(c).strip()]
    if not (cfg.MIN_CONTEUDOS <= len(conteudos) <= cfg.MAX_CONTEUDOS):
        problemas.append(f"o produto precisa listar de {cfg.MIN_CONTEUDOS} a {cfg.MAX_CONTEUDOS} conteúdos "
                         f"(veio {len(conteudos)})")

    caps = _capitulos(p)
    if len(caps) < cfg.MIN_CONTEUDOS:
        problemas.append(f"o produto precisa ter pelo menos {cfg.MIN_CONTEUDOS} capítulos escritos "
                         f"(veio {len(caps)})")
    palavras = sum(contar_palavras(f"{c.get('titulo', '')} {c.get('texto', '')}") for c in caps)
    minimo = palavras_minimas(preco)
    if palavras < minimo:
        problemas.append(f"conteúdo curto demais para a entrega: {palavras} palavras nos capítulos, "
                         f"mínimo {minimo} para esse preço")

    for campo, texto in campos_de_texto(p):
        termos = encontrar_termos(texto)
        if termos:
            problemas.append(f"termo proibido em {campo}: {', '.join(termos)}")
    return problemas


def sanear_produto(p: dict) -> tuple[dict, list[str]]:
    """Saída de reserva: remove (não reescreve) o que tem termo proibido. O nome nunca é alterado."""
    novo = copy.deepcopy(p)
    acoes = []
    for campo in ("promessa", "publico", "descricao_oferta"):
        antes = str(novo.get(campo) or "")
        if encontrar_termos(antes):
            novo[campo] = sanear_texto(antes)
            acoes.append(f"removeu trechos de {campo}")
    conteudos = list(novo.get("conteudos") or [])
    mantidos = [c for c in conteudos if not encontrar_termos(str(c))]
    if len(mantidos) != len(conteudos):
        novo["conteudos"] = mantidos
        acoes.append(f"removeu {len(conteudos) - len(mantidos)} item(ns) de conteudos")
    for i, cap in enumerate(novo.get("capitulos") or []):
        if not isinstance(cap, dict):
            continue
        for chave in ("titulo", "texto"):
            antes = str(cap.get(chave) or "")
            if encontrar_termos(antes):
                cap[chave] = sanear_texto(antes)
                acoes.append(f"removeu trechos de capitulos[{i}].{chave}")
    return novo, acoes


# ----------------------------------------------------------------------------
# Anúncio
# ----------------------------------------------------------------------------
def verificar_anuncio(produto: dict | None, texto: str, tipo: str) -> list[str]:
    """tipo: OFERTA (link obrigatório no texto), VITRINE (link opcional) ou VALOR (sem venda).
    Devolve os problemas que impedem publicar (vazia = pode publicar)."""
    problemas = []
    texto = texto or ""
    termos = encontrar_termos(texto)
    if termos:
        problemas.append(f"termo proibido no texto: {', '.join(termos)}")
    if "**" in texto:
        problemas.append("texto com markdown (asteriscos)")

    if tipo == "VALOR" and produto is None:
        return problemas
    if produto is None:
        return problemas + ["não há produto 'pronto' no catálogo"]
    if tipo != "VALOR" and produto.get("status") != "pronto":
        problemas.append(f"o produto não está 'pronto' no catálogo (status: {produto.get('status')})")

    link = str(produto.get("link_compra") or "").strip()
    if tipo in ("OFERTA", "VITRINE") or _urls(texto):
        for u in _urls(texto):
            if u != link:
                problemas.append(f"link no texto diferente do catálogo: {u}")
    if tipo == "OFERTA":
        if not link_ok(link):
            problemas.append("o produto não tem link de compra válido no catálogo")
        elif link not in texto:
            problemas.append("o texto da oferta não contém o link do catálogo")

    preco = parse_preco(produto.get("preco"))
    for achado in _RE_PRECO.findall(texto):
        if preco is not None and abs((parse_preco(achado) or -1) - preco) > 0.001:
            problemas.append(f"preço no texto ({achado}) diferente do catálogo ({formatar_preco(preco)})")
    return problemas


_HASHTAGS = "#infoprodutos #guiapratico #aprendizado #conteudodigital #dicaspraticas"


def texto_modelo_seguro(produto: dict | None, tipo: str) -> str:
    """Texto montado só com dados do catálogo. É a saída de reserva do anúncio."""
    if produto is None or tipo == "VALOR":
        dica = ""
        if produto and produto.get("conteudos"):
            dica = f" Hoje: {str(produto['conteudos'][0]).rstrip('.')}."
        return ("Uma dica prática de cada vez: organize um passo pequeno hoje e repita amanhã."
                f"{dica} Salve este post para consultar depois e siga para ver mais.\n\n{_HASHTAGS}")
    itens = "\n".join(f"- {c}" for c in (produto.get("conteudos") or [])[:4])
    preco = formatar_preco(parse_preco(produto.get("preco")) or 0)
    fim = (f"Por {preco}. Acesse: {produto.get('link_compra')}" if tipo == "OFERTA"
           else f"Por {preco}. Link na bio.")
    return (f"{produto.get('nome')}\n\n{produto.get('promessa')}\n\nO que você encontra dentro:\n{itens}\n\n"
            f"{fim}\n\nMaterial digital criado com ajuda de IA.\n\n{_HASHTAGS}")


def _truncar(texto: str, limite: int) -> str:
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rsplit(" ", 1)[0].rstrip(" ,;:.") + "…"


def card_modelo(produto: dict | None, tipo: str) -> tuple[str, str]:
    """(headline até 60, subline até 100) para o card, montados só com dados do catálogo."""
    if produto is None or tipo == "VALOR":
        sub = _truncar(str(produto["conteudos"][0]), 100) if produto and produto.get("conteudos") else \
            "Um passo de cada vez."
        return "Uma dica prática para hoje", sub
    return _truncar(str(produto.get("nome")), 60), _truncar(str(produto.get("promessa")), 100)


def preparar_legenda(produto: dict | None, texto: str, tipo: str) -> tuple[str, list[str], list[str]]:
    """Corrige o que dá para corrigir sem inventar nada e devolve (legenda, ações, problemas_restantes).
    problemas_restantes não vazio = NÃO publicar em modo real."""
    acoes = []
    original = (texto or "").strip()
    t = limpar_markdown(original)
    if t != original:
        acoes.append("removeu markdown")

    termos = encontrar_termos(t)
    if termos:
        t = sanear_texto(t)
        acoes.append(f"removeu trechos com termos proibidos ({', '.join(termos)})")

    if len(_RE_URL.sub("", t).strip()) < 30:
        t = texto_modelo_seguro(produto, tipo)
        acoes.append("texto vazio após a limpeza: usou o texto-modelo do catálogo")

    if produto is not None and (tipo in ("OFERTA", "VITRINE") or _urls(t)):
        link = str(produto.get("link_compra") or "").strip()
        if link_ok(link):
            for u in dict.fromkeys(_urls(t)):
                if u != link:
                    t = t.replace(u, link)
                    acoes.append(f"trocou o link {u} pelo link do catálogo")
        preco = parse_preco(produto.get("preco"))
        if preco is not None:
            for achado in dict.fromkeys(_RE_PRECO.findall(t)):
                if abs((parse_preco(achado) or -1) - preco) > 0.001:
                    t = t.replace(achado, formatar_preco(preco))
                    acoes.append(f"trocou o preço {achado} pelo preço do catálogo")
        if tipo == "OFERTA" and link_ok(link) and link not in t:
            t = f"{t}\n\nAcesse: {link}".strip()
            acoes.append("acrescentou o link do catálogo")

    return t, acoes, verificar_anuncio(produto, t, tipo)

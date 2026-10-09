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
    elif len(nome) >= 60:
        problemas.append("nome com 60 caracteres ou mais (precisa caber no card da página)")

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
            if u != link and not link_de_cta(u):
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


# ----------------------------------------------------------------------------
# Legenda por rede: 20 hashtags em 3 camadas + CTA do canal. Feito em código: o modelo não escolhe hashtag nem link.
#   camada 1 (amplas, 8, iguais em todo post) + camada 2 (do tema, 7) + camada 3 (do nicho, 5) = 20 (máx. 25).
# "prioridade" são as 5 mais fortes do tema: entram primeiro, então se uma rede limitar (Instagram vem reduzindo
# o teto de hashtags por legenda) ou o robô precisar cortar, são as que sobram.
# ----------------------------------------------------------------------------
HASHTAGS_AMPLAS = ("#dicas", "#rotina", "#organizacao", "#saude", "#bemestar", "#vidasaudavel", "#motivacao",
                   "#lifestyle")
HASHTAGS_TEMAS = {
    "receitas": {
        "prioridade": ("#marmitafit", "#alimentacaosaudavel", "#receitasfit", "#marmitas", "#cardapiosemanal"),
        "tema": ("#alimentacaosaudavel", "#receitasfit", "#comidasaudavel", "#reeducacaoalimentar", "#nutricao",
                 "#comidafit", "#marmitafitness"),
        "nicho": ("#marmitafit", "#marmitas", "#cardapiosemanal", "#marmitando", "#receitafitfacil"),
    },
    "financas": {
        "prioridade": ("#financaspessoais", "#educacaofinanceira", "#orcamentofamiliar", "#controlefinanceiro",
                       "#financasdomesticas"),
        "tema": ("#financaspessoais", "#educacaofinanceira", "#controlefinanceiro", "#dinheiro", "#economizar",
                 "#planejamentofinanceiro", "#organizacaofinanceira"),
        "nicho": ("#orcamentofamiliar", "#financasdomesticas", "#planilhafinanceira", "#contasemdia",
                  "#economiadomestica"),
    },
    "renda": {
        "prioridade": ("#rendaextra", "#trabalhoonline", "#freelancer", "#habilidades", "#trabalharemcasa"),
        "tema": ("#rendaextra", "#trabalhoonline", "#freelancer", "#empreendedorismo", "#autonomo", "#aprendizado",
                 "#habilidades"),
        "nicho": ("#trabalharemcasa", "#servicosonline", "#freelancers", "#rendaextraonline", "#profissaodigital"),
    },
    "casa": {
        "prioridade": ("#organizacaodacasa", "#casaorganizada", "#rotinadecasa", "#limpezadacasa", "#donadecasa"),
        "tema": ("#organizacaodacasa", "#casaorganizada", "#limpeza", "#faxina", "#lar", "#vidadecasa",
                 "#minimalismo"),
        "nicho": ("#rotinadecasa", "#limpezadacasa", "#donadecasa", "#cronogramadelimpeza", "#casaemordem"),
    },
    "produtividade": {
        "prioridade": ("#produtividade", "#foco", "#gestaodotempo", "#organizacaopessoal", "#habitos"),
        "tema": ("#produtividade", "#foco", "#gestaodotempo", "#planejamento", "#habitos", "#disciplina", "#metas"),
        "nicho": ("#organizacaopessoal", "#rotinaprodutiva", "#focoedisciplina", "#produtividadepessoal",
                  "#desenvolvimentopessoal"),
    },
}
_PALAVRAS_TEMA = [("renda", r"renda extra"), ("receitas", r"marmit|receit|cardapio|aliment"),
                  ("financas", r"financ|orcament"), ("casa", r"organizacao da casa|da casa|limpeza|faxina")]
_RE_SO_HASHTAGS = re.compile(r"(?:\s*#\w+)+\s*")
MAX_HASHTAGS = 25
INSTAGRAM_LIMITE_CARACTERES = 2200


def _tema_em(texto: str) -> str | None:
    base = sem_acentos(texto or "").lower()
    for tema, padrao in _PALAVRAS_TEMA:
        if re.search(padrao, base):
            return tema
    return None


def tema_da_legenda(produto: dict | None, texto: str = "", tipo: str | None = None) -> str:
    """O tema vem do texto; se o texto não diz, do produto (menos em post de VALOR, que é dica geral e não vende o produto)."""
    tema = _tema_em(texto)
    if tema is None and produto and tipo != "VALOR":
        tema = _tema_em(f"{produto.get('nome') or ''} {produto.get('promessa') or ''}")
    return tema or "produtividade"


def _quantidade(rede: str | None) -> int:
    n = cfg.HASHTAGS_INSTAGRAM if rede == "instagram" else cfg.HASHTAGS_FACEBOOK
    return max(1, min(int(n), MAX_HASHTAGS))


def lista_de_hashtags(produto: dict | None, texto: str = "", tipo: str | None = None, quantidade: int = 20) -> list[str]:
    """Hashtags únicas, na ordem: 5 de prioridade do tema, amplas, resto do tema, resto do nicho. Corta em `quantidade`."""
    t = HASHTAGS_TEMAS[tema_da_legenda(produto, texto, tipo)]
    vistas, saida = set(), []
    for h in (*t["prioridade"], *HASHTAGS_AMPLAS, *t["tema"], *t["nicho"]):
        if h not in vistas and not encontrar_termos(h):
            vistas.add(h)
            saida.append(h)
    return saida[:max(1, min(quantidade, MAX_HASHTAGS))]


def hashtags_em_camadas(produto: dict | None, texto: str = "", tipo: str | None = None, rede: str | None = None) -> str:
    return " ".join(lista_de_hashtags(produto, texto, tipo, _quantidade(rede)))


def reduzir_hashtags(legenda: str, n: int = 5) -> str:
    """Mantém só as `n` primeiras hashtags do bloco final (as de prioridade): plano B se a rede recusar muitas."""
    linhas = (legenda or "").rstrip().split("\n")
    if linhas and _RE_SO_HASHTAGS.fullmatch(linhas[-1]):
        linhas[-1] = " ".join(linhas[-1].split()[:max(0, n)])
    return "\n".join(linhas).rstrip()


def erro_de_hashtag(mensagem: str) -> bool:
    return bool(re.search(r"hashtag", str(mensagem or ""), re.I))


def _sem_hashtags_no_fim(texto: str) -> str:
    linhas = (texto or "").rstrip().split("\n")
    while linhas and (not linhas[-1].strip() or _RE_SO_HASHTAGS.fullmatch(linhas[-1])):
        linhas.pop()
    return "\n".join(linhas).rstrip()


def _norm_link(u: str) -> str:
    return re.sub(r"^https?://", "", str(u or "").strip().lower()).rstrip("/")


def link_de_cta(u: str) -> bool:
    """True para os links de chamada configurados (bio do Instagram e Facebook): não são 'link inventado'."""
    return _norm_link(u) in {_norm_link(cfg.LINK_BIO_INSTAGRAM), _norm_link(cfg.LINK_FACEBOOK)}


def cta_da_rede(rede: str) -> str:
    if rede == "instagram":
        return f"Link na bio: {cfg.LINK_BIO_INSTAGRAM}"
    return f"Veja todos os guias: {cfg.LINK_FACEBOOK}"


def finalizar_para_rede(produto: dict | None, texto: str, rede: str, tipo: str | None = None) -> str:
    """Legenda final da rede ('instagram' ou 'facebook'): texto + CTA do canal + 20 hashtags em 3 camadas.
    Troca as hashtags que o modelo escreveu no fim do texto; não mexe no resto."""
    t = _sem_hashtags_no_fim(texto)
    alvo = cfg.LINK_BIO_INSTAGRAM if rede == "instagram" else cfg.LINK_FACEBOOK
    if _norm_link(alvo) not in _norm_link(t):
        t = f"{t}\n\n{cta_da_rede(rede)}".strip()
    legenda = f"{t}\n\n{hashtags_em_camadas(produto, texto, tipo, rede)}"
    if rede == "instagram" and len(legenda) > INSTAGRAM_LIMITE_CARACTERES:
        legenda = reduzir_hashtags(legenda, 5)
    return legenda


# Publicação orgânica na Meta é pública por padrão. Segmentar (idade, gênero, local, interesse) exigiria parâmetros
# explícitos que o robô NUNCA envia; o rótulo abaixo só sai se o payload realmente não tiver nenhum deles.
CHAVES_DE_SEGMENTACAO = ("targeting", "feed_targeting", "audience", "custom_audiences", "age_min", "age_max",
                         "geo_locations", "countries", "genders", "interests", "privacy", "audience_restrictions")
PUBLICO_GERAL = "para todos os públicos (publicação orgânica pública, sem segmentação de idade, gênero, local ou interesse)"


def rotulo_publico(*payloads: dict) -> str:
    achadas = sorted({k for p in payloads for k in (p or {}) if k in CHAVES_DE_SEGMENTACAO})
    return f"SEGMENTADO ({', '.join(achadas)})" if achadas else PUBLICO_GERAL


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


def preparar_legenda(produto: dict | None, texto: str, tipo: str,
                     rede: str | None = None) -> tuple[str, list[str], list[str]]:
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
                if u != link and not link_de_cta(u):
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

    if rede in ("instagram", "facebook"):
        t = finalizar_para_rede(produto, t, rede, tipo)
        acoes.append(f"acrescentou CTA e hashtags em 3 camadas ({rede})")
    return t, acoes, verificar_anuncio(produto, t, tipo)

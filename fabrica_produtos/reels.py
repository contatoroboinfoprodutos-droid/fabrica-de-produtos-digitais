"""agente_roteiro_reels: um roteiro de Reels de 15 s para cada produto do catálogo que ainda não tem.

O LLM só escreve o gancho, a dor/solução e a legenda. O que não pode errar é montado em código:
CTA fixo, preço (do catálogo) e a estrutura [0-3s] [3-10s] [10-15s]. Termos proibidos, links e preços
escritos pelo modelo reprovam o roteiro. Saída: catalogo/roteiros_reels.json (idempotente por id_produto).
"""
import json
import logging
import os

from . import catalogo, travas
from .texto import sem_acentos

logger = logging.getLogger("fabrica")

SAIDA_PADRAO = os.getenv("FABRICA_REELS_SAIDA", "").strip() or "catalogo/roteiros_reels.json"
CTA = "Link na bio - todos os guias lá"
AGENTE = dict(
    role="Roteirista de Reels de 15 segundos",
    goal="Escrever roteiros curtos, visuais e honestos para um guia em PDF, sempre a partir dos dados do catálogo.",
    backstory=("Editor de vídeos curtos. Abre com um gancho forte baseado no título do produto, mostra a dor e a "
               "solução em uma cena visual e nunca inventa números, resultados, depoimentos ou promessa de ganho."),
)
SAIDA_LLM = "Somente um objeto JSON válido com as chaves gancho_3s, dor_solucao_10s e legenda, sem cercas de código."


def carregar(caminho: str | None = None) -> list[dict]:
    try:
        with open(caminho or SAIDA_PADRAO, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def salvar(roteiros: list[dict], caminho: str | None = None) -> None:
    caminho = caminho or SAIDA_PADRAO
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(roteiros, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, caminho)


def pendentes(caminho_catalogo: str | None = None, caminho_saida: str | None = None) -> list[dict]:
    feitos = {r.get("id_produto") for r in carregar(caminho_saida)}
    return [p for p in catalogo.carregar(caminho_catalogo)["produtos"]
            if p.get("status") == "pronto" and travas.link_ok(p.get("link_compra", "")) and p["id"] not in feitos]


def _sem_chaves(t: str) -> str:
    return str(t).replace("{", "(").replace("}", ")")


def prompt(p: dict, anterior: list[str] | None = None) -> str:
    extra = ("\n\nA tentativa anterior foi reprovada pelos motivos: " + "; ".join(anterior) + ". Corrija.") if anterior else ""
    return _sem_chaves(
        "Escreva o roteiro de um Reels de 15 segundos em português do Brasil para este guia em PDF.\n"
        f"TITULO: {p['nome']}\nPROMESSA: {p.get('promessa', '')}\nCONTEUDOS: " + " | ".join(p.get("conteudos") or [])
        + "\n\nRegras:\n"
        "- gancho_3s: UMA pergunta ou frase visual de até 12 palavras, baseada no título (ex.: 'Você é interrompido a cada 5 minutos?'). "
        "Só use número se ele estiver nos dados acima.\n"
        "- dor_solucao_10s: o que aparece na tela e o que o guia ensina, em até 35 palavras, usando só os conteúdos acima "
        "(ex.: 'Mostra tela bagunçada > mostra o método de blocos de foco do PDF').\n"
        "- legenda: 2 a 3 linhas curtas, terminando com 'Link na bio 👇'.\n"
        "- NÃO escreva preço, links, @, hashtags, depoimentos, resultados, 'lucro', 'testado', 'garantido' nem promessa de ganho.\n"
        "- NÃO escreva a chamada final: ela é adicionada pelo sistema." + extra)


def montar(p: dict, bruto: dict) -> dict:
    gancho = " ".join(str(bruto.get("gancho_3s") or "").split())
    dor = " ".join(str(bruto.get("dor_solucao_10s") or "").split())
    legenda = str(bruto.get("legenda") or "").strip()
    preco = p.get("preco_texto") or ""
    return {
        "id_produto": p["id"],
        "gancho_3s": gancho,
        "roteiro_15s": f"[0-3s] {gancho} [3-10s] {dor} [10-15s] Em PDF por {preco}. {CTA}",
        "legenda": legenda,
        "cta": CTA,
    }


def validar(r: dict, bruto: dict) -> list[str]:
    erros = []
    for campo in ("gancho_3s", "dor_solucao_10s", "legenda"):
        if not str(bruto.get(campo) or "").strip():
            erros.append(f"{campo} vazio")
    if erros:
        return erros
    texto = " ".join(str(bruto[c]) for c in ("gancho_3s", "dor_solucao_10s", "legenda"))
    if (t := travas.encontrar_termos(texto)):
        erros.append("termos proibidos: " + ", ".join(t))
    if "http" in texto.lower() or "www." in texto.lower() or "@" in texto:
        erros.append("não pode ter link nem @")
    if "R$" in texto or "reais" in sem_acentos(texto).lower():
        erros.append("o preço é adicionado pelo sistema")
    if len(str(bruto["gancho_3s"]).split()) > 14:
        erros.append("gancho longo demais (máx. 12 palavras)")
    if len(str(bruto["dor_solucao_10s"]).split()) > 40:
        erros.append("dor_solucao_10s longa demais (máx. 35 palavras)")
    return erros


def gerar_para(p: dict, executor=None, tentativas: int = 2) -> dict:
    """Devolve o roteiro validado de UM produto. Levanta ValueError se nenhuma tentativa passar."""
    if executor is None:
        from . import fabrica
        fabrica.AGENTES.setdefault("roteirista", AGENTE)
        executor = lambda d: fabrica.executar_com_reserva("roteirista", d, SAIDA_LLM)[0]  # noqa: E731
    from .fabrica import extrair_json

    motivos: list[str] = []
    for _ in range(tentativas):
        bruto = extrair_json(executor(prompt(p, motivos or None)))
        if not bruto:
            motivos = ["resposta não era JSON"]
            continue
        r = montar(p, bruto)
        motivos = validar(r, bruto)
        if not motivos:
            return r
    raise ValueError("; ".join(motivos))


def atualizar(caminho_catalogo: str | None = None, caminho_saida: str | None = None, executor=None) -> dict:
    """Gera os roteiros que faltam. Nunca reescreve um já existente. Uma falha não derruba as demais."""
    roteiros = carregar(caminho_saida)
    novos, falhas = [], []
    for p in pendentes(caminho_catalogo, caminho_saida):
        try:
            roteiros.append(gerar_para(p, executor))
            novos.append(p["id"])
        except Exception as e:  # noqa: BLE001 - cai no próximo produto; tenta de novo na próxima execução
            falhas.append(f"{p['id']}: {e}")
            logger.warning("reels: %s falhou: %s", p["id"], e)
    if novos:
        salvar(roteiros, caminho_saida)
    return {"novos": novos, "falhas": falhas, "total": len(roteiros)}

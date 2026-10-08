"""Fábrica de produtos: criador -> orientador -> criador (correção) -> travas em código.

O orientador NÃO reescreve e NÃO é a última palavra: ele aponta o que corrigir e como. Quem decide
o que é regra dura são as travas em código (travas.py). Se depois de todas as rodadas ainda restar
termo proibido, a saída de reserva REMOVE o trecho (nunca troca por promessa parecida).
"""
import json
import logging
import os
import re
import time

from . import catalogo, config_fabrica as cfg, llms, travas
from .texto import formatar_preco, parse_preco

logger = logging.getLogger("fabrica")

ESPERA_RETRY = float(os.getenv("FABRICA_ESPERA_RETRY", "20") or 0)  # segundos entre tentativas (429/503)

AGENTES = {
    "criador": dict(
        role="Criador de infoprodutos digitais",
        goal="Escrever guias práticos de verdade, com conteúdo útil e promessa realista, em português do Brasil.",
        backstory=("Autor de materiais didáticos curtos. Entrega conteúdo concreto (passos, exemplos, exercícios), "
                   "nunca inventa dados, estudos ou depoimentos e nunca promete ganho financeiro."),
    ),
    "orientador": dict(
        role="Orientador de qualidade e conformidade",
        goal="Dizer ao criador, com precisão, o que precisa mudar para o produto poder ser vendido com honestidade.",
        backstory=("Editor e revisor de conformidade. Não reescreve o texto do criador: aponta o problema, "
                   "diz onde está e como corrigir. Quando algo é promessa proibida, manda remover."),
    ),
}

SAIDA_CRIADOR = "Somente um objeto JSON válido, sem texto antes ou depois e sem cercas de código."
SAIDA_ORIENTADOR = "Somente um objeto JSON válido com as chaves problemas_graves e ajustes."


# ----------------------------------------------------------------------------
# Execução de uma tarefa no CrewAI (com reserva entre provedores)
# ----------------------------------------------------------------------------
def executar_tarefa(papel: str, descricao: str, saida: str, llm) -> str:
    from crewai import Agent, Crew, Process, Task

    llms.aplicar_workaround_groq()
    ag = AGENTES[papel]
    agente = Agent(role=ag["role"], goal=ag["goal"], backstory=ag["backstory"], llm=llm,
                   allow_delegation=False, verbose=False)
    tarefa = Task(description=descricao, expected_output=saida, agent=agente)
    out = Crew(agents=[agente], tasks=[tarefa], process=Process.sequential, verbose=False).kickoff()
    return getattr(out, "raw", None) or str(out)


def executar_com_reserva(papel: str, descricao: str, saida: str, evitar: str | None = None) -> tuple[str, str]:
    """Roda a tarefa no primeiro provedor que responder. Devolve (texto, provedor)."""
    erros = []
    for c in llms.candidatos(papel, evitar):
        for tentativa in (1, 2):
            try:
                texto = executar_tarefa(papel, descricao, saida, llms.construir_llm(c["provedor"], c["modelo"]))
                if texto and texto.strip():
                    return texto, c["provedor"]
                erros.append(f"{c['provedor']}: resposta vazia")
            except Exception as e:  # 429/503/timeout etc.: tenta de novo e depois troca de provedor
                erros.append(f"{c['provedor']}: {type(e).__name__}")
                logger.warning("%s (%s) falhou na tentativa %d: %s", papel, c["provedor"], tentativa,
                               type(e).__name__)
            if tentativa == 1 and ESPERA_RETRY:
                time.sleep(ESPERA_RETRY)
    raise RuntimeError("todos os provedores falharam: " + "; ".join(erros))


# ----------------------------------------------------------------------------
# JSON e formatação
# ----------------------------------------------------------------------------
def extrair_json(texto: str) -> dict | None:
    """Acha o primeiro objeto JSON no texto (aceita cercas ```json e texto em volta)."""
    if not texto:
        return None
    texto = re.sub(r"```(?:json)?", "", texto)
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", texto):
        try:
            obj, _ = dec.raw_decode(texto[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def normalizar_candidato(d: dict | None) -> dict | None:
    """Mantém só as chaves conhecidas e exige os campos essenciais. None = resposta inutilizável."""
    if not isinstance(d, dict):
        return None
    nome = str(d.get("nome") or "").strip()
    caps = []
    for c in d.get("capitulos") or []:
        if isinstance(c, dict) and str(c.get("texto") or "").strip():
            caps.append({"titulo": str(c.get("titulo") or "").strip(), "texto": str(c["texto"]).strip()})
    if not nome or not caps:
        return None
    return {
        "nome": nome,
        "tipo": str(d.get("tipo") or "guia").strip(),
        "preco": parse_preco(d.get("preco")),
        "promessa": str(d.get("promessa") or "").strip(),
        "publico": str(d.get("publico") or "").strip(),
        "conteudos": [str(c).strip() for c in (d.get("conteudos") or []) if str(c).strip()],
        "descricao_oferta": str(d.get("descricao_oferta") or "").strip(),
        "capitulos": caps,
    }


def _sem_chaves(texto: str) -> str:
    """O CrewAI interpreta {texto} em descrições; troca as chaves por parênteses nos textos embutidos."""
    return str(texto).replace("{", "(").replace("}", ")")


def produto_em_texto(p: dict) -> str:
    linhas = [f"NOME: {p.get('nome')}", f"TIPO: {p.get('tipo')}",
              f"PRECO: {formatar_preco(parse_preco(p.get('preco')) or 0)}",
              f"PROMESSA: {p.get('promessa')}", f"PUBLICO: {p.get('publico')}",
              "CONTEUDOS: " + " | ".join(p.get("conteudos") or []),
              f"DESCRICAO_OFERTA: {p.get('descricao_oferta')}"]
    for i, c in enumerate(p.get("capitulos") or [], 1):
        linhas += [f"CAPITULO {i} - {c.get('titulo')}", c.get("texto", "")]
    return _sem_chaves("\n".join(linhas))


# ----------------------------------------------------------------------------
# Prompts (sem chaves {} de propósito)
# ----------------------------------------------------------------------------
def tipo_da_rodada(n: int | None = None) -> str:
    """Nível do próximo produto (guia, pacote ou combo), por rodízio sobre o tamanho do catálogo.
    Respeita FABRICA_TIPOS: nível desligado cai para 'guia' (ou o primeiro ativo)."""
    if n is None:
        n = len(catalogo.carregar()["produtos"])
    t = cfg.ROTACAO[n % len(cfg.ROTACAO)]
    return t if t in cfg.TIPOS_ATIVOS else ("guia" if "guia" in cfg.TIPOS_ATIVOS else cfg.TIPOS_ATIVOS[0])


def prompt_criador(tema: str, existentes: list[str], feedback: list[str] | None, anterior: dict | None,
                   tipo: str | None = None) -> str:
    tipo = tipo if tipo in cfg.TIPOS else "guia"
    preco = cfg.TIPOS[tipo]
    minimo = int(travas.palavras_minimas(preco) * 1.25)
    por_cap = minimo // cfg.MAX_CONTEUDOS
    partes = [
        f"Crie UM infoproduto digital NOVO sobre o tema: {_sem_chaves(tema)}.",
        "Formato: guia prático em texto, que será entregue em PDF. Nada de vídeo, planilha ou curso em vídeo.",
        f"Nível do produto: {cfg.ROTULOS[tipo]}. Preço FIXO (chave preco): {preco:.2f}. Use tipo=\"{tipo}\".",
        f"Conteúdo REAL e útil: {cfg.MAX_CONTEUDOS} capítulos, um para cada item de "
        f"conteudos, na mesma ordem. Cada capítulo com {por_cap} a {por_cap + 100} palavras, passos concretos, "
        f"um exemplo e um mini-exercício. No total, pelo menos {minimo} palavras nos capítulos, porque o "
        f"comprador paga por esse volume.",
        "Não invente dados, estatísticas, estudos, depoimentos, nem nomes de pessoas ou empresas.",
        "É PROIBIDO prometer ganho financeiro, falar em lucro, primeira venda, resultado garantido, cura, "
        "ou dizer que o método é testado ou comprovado. A promessa deve ser realista (tempo economizado, "
        "organização, aprendizado) e só pode dizer o que os capítulos entregam.",
        "Chaves do objeto JSON: nome (até 55 caracteres), tipo, preco, promessa (uma frase), publico (uma frase), "
        "conteudos (lista de textos curtos), descricao_oferta (até 600 caracteres, texto simples, sem markdown), "
        "capitulos (lista de objetos, cada um com as chaves titulo e texto).",
    ]
    if existentes:
        partes.append("Estes produtos já existem, NÃO repita nome nem tema: "
                      + "; ".join(_sem_chaves(n) for n in existentes[-15:] if n) + ".")
    if feedback:
        partes.append("CORREÇÕES OBRIGATÓRIAS apontadas pelo orientador e pelas travas de código. Reescreva o "
                      "produto COMPLETO aplicando todas. Onde for apontado termo ou promessa proibida, REMOVA "
                      "o trecho; não troque por uma promessa parecida:")
        partes += [f"- {_sem_chaves(f)}" for f in feedback]
    if anterior:
        partes.append("PRODUTO ANTERIOR (para você corrigir):\n" + produto_em_texto(anterior))
    partes.append("Responda SOMENTE com o objeto JSON.")
    return "\n".join(partes)


def prompt_orientador(produto: dict, problemas_codigo: list[str]) -> str:
    partes = [
        "Você é o orientador de qualidade. Avalie o produto abaixo. NÃO reescreva o produto.",
        "PROBLEMAS GRAVES (lista problemas_graves), qualquer um destes impede a venda: "
        "1) falta conteúdo real ou entrega (capítulos vazios, genéricos ou repetitivos); "
        "2) a promessa ou a descrição afirma algo que os capítulos não entregam; "
        "3) promessa de ganho financeiro, lucro, primeira venda, resultado garantido, ou dizer que é "
        "testado ou comprovado; "
        "4) dados, estatísticas, depoimentos ou nomes inventados; "
        "5) conteúdo perigoso ou enganoso.",
        "AJUSTES (lista ajustes): melhorias de clareza ou estilo que não impedem a venda.",
        "Para cada problema grave, diga EXATAMENTE o que mudar: qual trecho remover ou o que acrescentar e em "
        "qual capítulo. Se for promessa proibida, mande REMOVER, não reformular.",
    ]
    if problemas_codigo:
        partes.append("As travas automáticas já encontraram estes problemas (inclua no seu relatório o como "
                      "corrigir): " + "; ".join(_sem_chaves(p) for p in problemas_codigo))
    partes.append("Responda SOMENTE com um objeto JSON com as chaves problemas_graves (lista de textos, vazia "
                  "se não houver) e ajustes (lista de textos).")
    partes.append("PRODUTO:\n" + produto_em_texto(produto))
    return "\n".join(partes)


def parse_orientacao(bruto: str) -> dict:
    """graves: lista (vazia = aprovado) ou None se o orientador não respondeu em JSON utilizável."""
    d = extrair_json(bruto)
    if not isinstance(d, dict) or "problemas_graves" not in d:
        return {"graves": None, "ajustes": []}
    graves = [str(x).strip() for x in (d.get("problemas_graves") or []) if str(x).strip()]
    ajustes = [str(x).strip() for x in (d.get("ajustes") or []) if str(x).strip()]
    return {"graves": graves, "ajustes": ajustes}


# ----------------------------------------------------------------------------
# Fluxo principal
# ----------------------------------------------------------------------------
def _avaliar(executor, produto: dict, prov_criador: str | None):
    probs = travas.verificar_produto(produto)
    if catalogo.nome_ja_existe(produto["nome"]):
        probs.append("já existe um produto com esse nome no catálogo; escolha outro nome")
    try:
        bruto, prov = executor("orientador", prompt_orientador(produto, probs), SAIDA_ORIENTADOR, prov_criador)
        orient = parse_orientacao(bruto)
        orient["provedor"] = prov
    except RuntimeError as e:
        logger.warning("Orientador indisponível: %s", e)
        orient = {"graves": None, "ajustes": [], "provedor": None}
    return probs, orient


def fabricar(tema: str, max_rodadas: int | None = None, executor=None, tipo: str | None = None) -> dict:
    """Devolve {status, produto, motivo, aprovado_por, rodadas}.
    status: 'aprovado' | 'reprovado' | 'adiado' (nenhum provedor de IA respondeu; tenta de novo na próxima)."""
    executor = executor or executar_com_reserva
    max_rodadas = max_rodadas or cfg.MAX_RODADAS
    existentes = catalogo.nomes_existentes()
    rodadas, feedback, candidato, ultimo, prov_criador = [], None, None, None, None

    for n in range(1, max_rodadas + 1):
        try:
            bruto, prov_criador = executor("criador", prompt_criador(tema, existentes, feedback, candidato, tipo),
                                           SAIDA_CRIADOR, None)
        except RuntimeError as e:
            return {"status": "adiado", "produto": None, "rodadas": rodadas, "aprovado_por": "",
                    "motivo": f"nenhum provedor de IA respondeu ({e}); a fábrica tenta de novo na próxima execução"}
        novo = normalizar_candidato(extrair_json(bruto))
        reg = {"rodada": n, "criador": prov_criador}
        if novo is None:
            reg["resultado"] = "resposta do criador não era um JSON utilizável"
            rodadas.append(reg)
            feedback = ["A resposta anterior não era um objeto JSON válido com nome e capitulos. "
                        "Responda somente com o JSON completo."]
            continue
        if tipo in cfg.TIPOS:  # nível e preço são decididos em código, nunca pela IA
            novo["tipo"], novo["preco"] = cfg.ROTULOS[tipo], cfg.TIPOS[tipo]
        candidato = novo
        probs, orient = _avaliar(executor, candidato, prov_criador)
        ultimo = orient
        reg.update({"orientador": orient.get("provedor"), "travas": probs,
                    "graves": orient["graves"], "ajustes": orient["ajustes"]})
        if not probs and orient["graves"] == []:
            reg["resultado"] = "aprovado"
            rodadas.append(reg)
            return {"status": "aprovado", "produto": candidato, "rodadas": rodadas,
                    "aprovado_por": "orientador + travas de código", "motivo": ""}
        reg["resultado"] = "correção pedida"
        rodadas.append(reg)
        feedback = probs + (orient["graves"] or []) + orient["ajustes"]

    if candidato is None:
        return {"status": "reprovado", "produto": None, "rodadas": rodadas, "aprovado_por": "",
                "motivo": f"nenhuma resposta utilizável do criador em {max_rodadas} rodadas"}

    # Saída de reserva: remove (não reescreve) o que as travas pegam e pede uma conferência final.
    sanado, acoes = travas.sanear_produto(candidato)
    probs, orient = _avaliar(executor, sanado, prov_criador)
    rodadas.append({"rodada": "reserva", "acoes": acoes, "travas": probs, "orientador": orient.get("provedor"),
                    "graves": orient["graves"], "ajustes": orient["ajustes"]})
    if probs:
        return {"status": "reprovado", "produto": sanado, "rodadas": rodadas, "aprovado_por": "",
                "motivo": "mesmo após a limpeza, as travas de código ainda bloqueiam: " + "; ".join(probs)}
    if orient["graves"]:
        return {"status": "reprovado", "produto": sanado, "rodadas": rodadas, "aprovado_por": "",
                "motivo": "o orientador manteve problemas graves após " + f"{max_rodadas} rodadas: "
                          + "; ".join(orient["graves"])}
    houve_graves = any(r.get("graves") for r in rodadas)
    if orient["graves"] is None and houve_graves:
        return {"status": "reprovado", "produto": sanado, "rodadas": rodadas, "aprovado_por": "",
                "motivo": "o orientador tinha apontado problemas graves e não foi possível reconferir "
                          "o produto corrigido"}
    por = ("travas de código após limpeza (orientador indisponível)" if orient["graves"] is None
           else "orientador + travas de código após limpeza de reserva")
    return {"status": "aprovado", "produto": sanado, "rodadas": rodadas, "aprovado_por": por, "motivo": ""}


def tema_da_rodada(topico: str = "") -> str:
    """Usa PRODUTO_TOPICO se existir; senão o rodízio de nichos, evitando repetir o último produto."""
    topico = (topico or "").strip()
    if topico and topico != "Produto em destaque do catálogo desta semana":
        return topico
    n = len(catalogo.carregar()["produtos"])
    return cfg.NICHOS[n % len(cfg.NICHOS)]


def criar_e_guardar(tema: str, executor=None, tipo: str | None = None) -> dict:
    """Fabrica um produto e registra o resultado no catálogo (aprovado ou reprovado)."""
    res = fabricar(tema, executor=executor, tipo=tipo or tipo_da_rodada())
    if res["status"] == "aprovado":
        reg = catalogo.adicionar(res["produto"], "aprovado",
                                 f"aprovado por {res['aprovado_por']} em {len(res['rodadas'])} rodada(s)")
        res["registro"] = reg
    elif res["status"] == "reprovado" and res["produto"]:
        reg = catalogo.adicionar(res["produto"], "reprovado", f"reprovado: {res['motivo']}")
        res["registro"] = reg
    return res


def resumo_markdown(res: dict) -> str:
    """Relatório de cada decisão do orientador, para o resumo da execução no GitHub."""
    linhas = [f"### Fábrica de produtos: {res['status'].upper()}"]
    if res.get("registro"):
        r = res["registro"]
        linhas.append(f"Produto **{r['nome']}** ({r['preco_texto']}), id `{r['id']}`.")
    if res.get("aprovado_por"):
        linhas.append(f"Aprovado por: {res['aprovado_por']}.")
    if res.get("motivo"):
        linhas.append(f"Motivo: {res['motivo']}")
    for r in res["rodadas"]:
        linhas.append(f"\n**Rodada {r['rodada']}**: criador `{r.get('criador', '-')}`, "
                      f"orientador `{r.get('orientador') or '-'}`. Resultado: {r.get('resultado', '-')}")
        if r.get("acoes"):
            linhas.append("- Limpeza de reserva: " + "; ".join(r["acoes"]))
        for t in r.get("travas") or []:
            linhas.append(f"- Trava de código: {t}")
        for g in r.get("graves") or []:
            linhas.append(f"- Orientador (grave): {g}")
        for a in r.get("ajustes") or []:
            linhas.append(f"- Orientador (ajuste): {a}")
    return "\n".join(linhas)

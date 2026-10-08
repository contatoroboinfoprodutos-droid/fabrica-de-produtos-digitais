"""Linha de comando da fábrica.

  python -m fabrica_produtos criar                 cria, revisa e registra UM produto (respeita pausa e limite diário)
  python -m fabrica_produtos verificar             procura os produtos pendentes nas plataformas e libera os que têm link
  python -m fabrica_produtos definir-link --id ID --link URL [--plataforma cakto]
  python -m fabrica_produtos sondar                relatório (somente leitura) do que as APIs aceitam
  python -m fabrica_produtos status                lista o catálogo
  python -m fabrica_produtos hub                   gera docs/link-na-bio.html a partir do catálogo
  python -m fabrica_produtos reels                 gera o roteiro de Reels dos produtos que ainda não têm
"""
import argparse
import logging
import os
import sys

from . import catalogo, config_fabrica as cfg


def _saida(texto: str) -> None:
    """Imprime e, no GitHub Actions, acrescenta ao resumo da execução."""
    print(texto)
    destino = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n\n")


def cmd_criar() -> int:
    if cfg.PAUSADA:
        _saida("### Fábrica pausada (FABRICA_PAUSADA=true): nenhum produto novo foi criado.")
        return 0
    feitos = catalogo.criados_hoje()
    if feitos >= cfg.MAX_PRODUTOS_POR_DIA:
        _saida(f"### Limite diário atingido ({feitos}/{cfg.MAX_PRODUTOS_POR_DIA}): nenhum produto novo hoje.")
        return 0
    from . import fabrica, registrador  # import tardio: só aqui o CrewAI é necessário

    tema = fabrica.tema_da_rodada(os.getenv("PRODUTO_TOPICO", ""))
    _saida(f"Tema da rodada: {tema}  |  simulação (FABRICA_DRY_RUN): {cfg.DRY_RUN}")
    res = fabrica.criar_e_guardar(tema)
    texto = fabrica.resumo_markdown(res)
    if res["status"] == "aprovado":
        linhas = registrador.registrar_produto(res["registro"]["id"])
        texto += "\n\n### Registro\n" + "\n".join(f"- {l}" for l in linhas)
    _saida(texto)
    return 0


def cmd_verificar() -> int:
    from . import registrador

    _saida("### Verificação de links\n" + "\n".join(f"- {l}" for l in registrador.verificar_links()))
    return 0


def cmd_definir_link(args) -> int:
    from . import registrador

    _saida(registrador.definir_link(args.id, args.link, args.plataforma))
    return 0


def cmd_sondar() -> int:
    from . import plataformas

    linhas = ["# Sondagem das plataformas (somente leitura)"]
    from .drive import Drive

    for plat in plataformas.instanciar(cfg.PLATAFORMAS_ALVO):
        linhas += plat.sondar() + [""]
    linhas += Drive().sondar() + [""]
    _saida("\n".join(linhas))
    return 0


def cmd_status() -> int:
    ps = catalogo.carregar()["produtos"]
    if not ps:
        _saida("Catálogo vazio.")
        return 0
    _saida("\n".join(f"{p['id']}  {p['status']:<20} {p.get('preco_texto', ''):<9} "
                     f"{p.get('plataforma') or '-':<8} {p['nome']}" for p in ps))
    return 0


def cmd_marcas() -> int:
    """Imprime UMA palavra para o workflow decidir se repete a tentativa: completo, bloqueado, parcial ou nada.
    (parcial = só uma rede publicou; nada = ainda nada publicou.) Não usa rede nem credencial."""
    from . import marcas

    redes = tuple(r.strip() for r in os.getenv("POST_REDES", "facebook,instagram").split(",") if r.strip())
    print(marcas.estado(redes or marcas.REDES))
    motivo = marcas.bloqueio()
    if motivo:
        print(f"motivo do bloqueio: {motivo}", file=sys.stderr)
    return 0


def cmd_guardiao(args) -> int:
    """Lê o log de uma execução que falhou e grava o título e o corpo da issue (sem segredos)."""
    from . import guardiao

    try:
        with open(args.log, encoding="utf-8", errors="replace") as f:
            log = f.read()
    except OSError:
        log = ""
    titulo, corpo = guardiao.montar_issue(args.workflow, args.run_url, log)
    with open(args.saida_titulo, "w", encoding="utf-8") as f:
        f.write(titulo)
    with open(args.saida_corpo, "w", encoding="utf-8") as f:
        f.write(corpo)
    print(titulo)
    return 0


def cmd_hub() -> int:
    from . import link_hub

    r = link_hub.atualizar()
    _saida(f"### Link na bio\n- {r['arquivo']}: {r['produtos']} produto(s) do catálogo; "
           + ("página atualizada" if r["mudou"] else "sem mudanças"))
    return 0


def cmd_reels() -> int:
    from . import reels

    r = reels.atualizar()
    linhas = [f"- roteiro criado: {i}" for i in r["novos"]] + [f"- FALHOU (tenta de novo na próxima): {f}" for f in r["falhas"]]
    _saida("### Roteiros de Reels\n" + ("\n".join(linhas) or "- nenhum produto novo sem roteiro") + f"\n- total: {r['total']}")
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="fabrica_produtos")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("criar", "verificar", "sondar", "status", "marcas", "hub", "reels"):
        sub.add_parser(nome)
    g = sub.add_parser("guardiao")
    for flag in ("--workflow", "--run-url", "--log", "--saida-titulo", "--saida-corpo"):
        g.add_argument(flag, required=True)
    d = sub.add_parser("definir-link")
    d.add_argument("--id", required=True)
    d.add_argument("--link", required=True)
    d.add_argument("--plataforma", default="")
    args = ap.parse_args(argv)
    return {"criar": cmd_criar, "verificar": cmd_verificar, "sondar": cmd_sondar, "status": cmd_status, "marcas": cmd_marcas, "hub": cmd_hub, "reels": cmd_reels, "guardiao": lambda: cmd_guardiao(args),
            "definir-link": lambda: cmd_definir_link(args)}[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())

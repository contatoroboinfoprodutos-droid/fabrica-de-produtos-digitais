"""Linha de comando da fábrica.

  python -m fabrica_produtos criar                 cria, revisa e registra UM produto (respeita pausa e limite diário)
  python -m fabrica_produtos verificar             procura os produtos pendentes nas plataformas e libera os que têm link
  python -m fabrica_produtos definir-link --id ID --link URL [--plataforma kiwify|hotmart]
  python -m fabrica_produtos sondar                relatório (somente leitura) do que as APIs aceitam
  python -m fabrica_produtos status                lista o catálogo
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
    for plat in plataformas.instanciar(cfg.PLATAFORMAS_ALVO):
        linhas += plat.sondar() + [""]
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


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="fabrica_produtos")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("criar", "verificar", "sondar", "status"):
        sub.add_parser(nome)
    d = sub.add_parser("definir-link")
    d.add_argument("--id", required=True)
    d.add_argument("--link", required=True)
    d.add_argument("--plataforma", default="")
    args = ap.parse_args(argv)
    return {"criar": cmd_criar, "verificar": cmd_verificar, "sondar": cmd_sondar, "status": cmd_status,
            "definir-link": lambda: cmd_definir_link(args)}[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())

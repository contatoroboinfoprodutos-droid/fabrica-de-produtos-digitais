"""Registrador: leva o produto aprovado até o status 'pronto' (com link de compra válido).

Caminhos, nesta ordem, sem nunca travar o fluxo:
  1. tenta criar o produto na plataforma por API (hoje: nenhuma confirmada, ver plataformas.py);
  2. gera o PACOTE (PDF + ficha de cadastro) e deixa o produto em 'aguardando_cadastro';
  3. a cada execução, procura o produto pelo NOME EXATO nas APIs e, se achar com link, libera ('pronto');
  4. se a API não devolver o link, `definir-link` grava o link manualmente.
Falha de uma plataforma nunca derruba as outras nem os outros produtos.
"""
import logging
import os
import re

from . import catalogo, config_fabrica as cfg, plataformas
from .pdf_produto import gerar_pdf
from .texto import normalizar
from .travas import link_ok

logger = logging.getLogger("fabrica")


def _slug(nome: str) -> str:
    return re.sub(r"\s+", "-", normalizar(nome))[:60] or "produto"


def pacote_dir(produto: dict) -> str:
    return os.path.join(cfg.PACOTES_DIR, produto["id"])


def _ficha(produto: dict, pdf_nome: str) -> str:
    itens = "\n".join(f"- {c}" for c in produto.get("conteudos") or [])
    return (
        f"# Ficha de cadastro: {produto['nome']}\n\n"
        f"Produto do catálogo `{produto['id']}`. Cadastre nas plataformas com os dados abaixo.\n\n"
        f"**Use exatamente este NOME**: o robô encontra o produto pelo nome, sem diferença de acento ou "
        f"maiúscula, e então libera o anúncio sozinho.\n\n"
        f"- Nome: {produto['nome']}\n"
        f"- Preço: {produto['preco_texto']}\n"
        f"- Tipo de entrega: arquivo digital (PDF)\n"
        f"- Arquivo para enviar à plataforma: `{pdf_nome}` (nesta mesma pasta)\n\n"
        f"## Descrição da oferta (copie e cole)\n\n{produto.get('descricao_oferta', '')}\n\n"
        f"## O que vem dentro\n\n{itens}\n\n"
        f"## Depois de cadastrar\n\n"
        f"1. Rode a ação `verificar` no GitHub (Actions → Fábrica de Produtos). O robô procura o produto pelo "
        f"nome e, se a API devolver o link, libera o produto.\n"
        f"2. Se a API não devolver o link, copie o link de compra da plataforma e rode a ação `definir-link` "
        f"com o id `{produto['id']}` e o link.\n"
        f"3. Só depois disso os robôs de anúncio passam a divulgar o produto.\n"
    )


def gerar_pacote(produto: dict) -> dict:
    pasta = pacote_dir(produto)
    os.makedirs(pasta, exist_ok=True)
    pdf_nome = f"{_slug(produto['nome'])}.pdf"
    pdf = gerar_pdf(produto, os.path.join(pasta, pdf_nome))
    ficha = os.path.join(pasta, "ficha_cadastro.md")
    with open(ficha, "w", encoding="utf-8") as f:
        f.write(_ficha(produto, pdf_nome))
    return {"pasta": pasta, "pdf": pdf, "ficha": ficha}


def registrar_produto(produto_id: str, dry_run: bool | None = None, nomes: list[str] | None = None) -> list[str]:
    """Devolve as linhas do relatório. Não levanta exceção por falha de plataforma."""
    dry_run = cfg.DRY_RUN if dry_run is None else dry_run
    p = catalogo.obter(produto_id)
    if not p or p.get("status") != "aprovado":
        return [f"produto {produto_id}: nada a registrar (status {p.get('status') if p else 'inexistente'})"]
    pacote = gerar_pacote(p)
    linhas = [f"pacote gerado em {pacote['pasta']}"]
    criado = None

    if dry_run:
        linhas.append("DRY_RUN: nenhuma criação foi feita nas plataformas (leitura continua permitida)")
    else:
        for plat in plataformas.instanciar(nomes or cfg.PLATAFORMAS_ALVO):
            if not plat.configurada():
                linhas.append(f"{plat.nome}: pulada (faltam variáveis: {', '.join(plat.faltando())})")
                continue
            for tentativa in (1, 2):
                try:
                    r = plat.criar_produto(p, pacote["pdf"])
                    linhas.append(f"{plat.nome}: produto criado (id {r.get('id', '?')})")
                    if criado is None and link_ok(r.get("link", "")):
                        criado = (plat.nome, r["link"])
                    break
                except plataformas.NaoSuportado as e:
                    linhas.append(str(e))
                    break
                except plataformas.ErroPlataforma as e:
                    linhas.append(f"{plat.nome}: erro na tentativa {tentativa}: {e}")

    if criado:
        catalogo.atualizar(p["id"], f"registrado na {criado[0]} por API; link recebido", status="pronto",
                           plataforma=criado[0], link_compra=criado[1])
        linhas.append(f"produto liberado (pronto) com o link da {criado[0]}")
    else:
        catalogo.atualizar(p["id"], "pacote pronto; aguardando cadastro na plataforma",
                           status="aguardando_cadastro")
        linhas.append("status: aguardando_cadastro (cadastre pelo pacote ou aguarde a criação por API)")
    linhas += verificar_links(nomes)
    return linhas


def verificar_links(nomes: list[str] | None = None) -> list[str]:
    """Somente leitura nas plataformas: procura cada produto pendente pelo nome e libera se achar o link."""
    linhas = []
    pendentes = catalogo.por_status("aguardando_cadastro")
    if not pendentes:
        return ["nenhum produto aguardando cadastro"]
    ativas = [pl for pl in plataformas.instanciar(nomes or cfg.PLATAFORMAS_ALVO) if pl.configurada()]
    if not ativas:
        return ["nenhuma plataforma configurada: defina os Secrets da Kiwify e/ou Hotmart"]
    for p in pendentes:
        liberado = False
        for plat in ativas:
            try:
                achado = plat.buscar_por_nome(p["nome"])
            except plataformas.ErroPlataforma as e:
                linhas.append(f"{p['id']} / {plat.nome}: não consegui consultar ({e})")
                continue
            if not achado:
                linhas.append(f"{p['id']} / {plat.nome}: produto ainda não encontrado pelo nome")
                continue
            if link_ok(achado.get("link", "")):
                catalogo.atualizar(p["id"], f"encontrado na {plat.nome}; link de compra recebido pela API",
                                   status="pronto", plataforma=plat.nome, link_compra=achado["link"])
                linhas.append(f"{p['id']}: LIBERADO com o link da {plat.nome}")
                liberado = True
                break
            aviso = f"encontrado na {plat.nome}, mas a API não devolveu o link: use definir-link"
            if not p.get("historico") or p["historico"][-1].get("evento") != aviso:
                catalogo.atualizar(p["id"], aviso)
            linhas.append(f"{p['id']}: {aviso}")
        if liberado:
            continue
    return linhas


def definir_link(produto_id: str, link: str, plataforma: str = "") -> str:
    """Grava o link de compra copiado do painel da plataforma e libera o produto."""
    link = (link or "").strip()
    if not link_ok(link):
        raise ValueError("link inválido: precisa começar com https:// e não pode ser o link de exemplo")
    p = catalogo.obter(produto_id)
    if not p:
        raise KeyError(f"produto {produto_id} não existe no catálogo")
    if p.get("status") not in ("aprovado", "aguardando_cadastro", "pronto"):
        raise ValueError(f"produto {produto_id} está '{p.get('status')}' e não pode ser liberado")
    catalogo.atualizar(produto_id, "link de compra definido manualmente; produto liberado", status="pronto",
                       plataforma=plataforma or p.get("plataforma", ""), link_compra=link)
    return f"{produto_id} liberado com o link informado"

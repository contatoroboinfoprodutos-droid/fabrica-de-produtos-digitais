"""Publicação diária de Reels no Facebook e no Instagram (biblioteca padrão + requests).

Fluxo de uma execução (`python -m fabrica_produtos.reels_publicar`):
  1. escolhe o produto: o mais novo que ainda não tem Reel; se todos já têm, o menos postado em Reels (rodízio);
  2. gera o vídeo (scripts/generate_reels.py, música livre de assets/music);
  3. monta a legenda de cada rede em código (travas.finalizar_para_rede: CTA da rede + 5 hashtags);
  4. publica nas duas redes com retry 3x; só a rede que falhou é repetida, nunca a que já saiu;
  5. grava catalogo/reels_publicados.json (o workflow faz o commit).

Meta: Facebook Reels = upload em 3 fases (start -> envio do arquivo -> finish). Instagram Reels = container
media_type=REELS com video_url público (a URL do próprio vídeo já hospedado no Facebook) ou, se ela não vier,
envio direto do arquivo (upload resumível). Os campos da API são os da documentação da Meta, mas só a primeira
execução real confirma que a conta/permissões aceitam: o resultado e o erro aparecem no resumo da execução.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
import time

import requests

from . import catalogo, config_fabrica as cfg, travas

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO_PADRAO = os.getenv("FABRICA_REELS_ESTADO", "").strip() or "catalogo/reels_publicados.json"
HASHTAGS_REEL = 5
GRAPH_VERSION = os.getenv("META_GRAPH_API_VERSION", "").strip() or "v26.0"
REDES = ("facebook", "instagram")


def _graph(caminho: str) -> str:
    return f"https://graph.facebook.com/{GRAPH_VERSION}/{caminho}"


def _agora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _log(msg: str) -> None:
    print(msg, flush=True)


# ----------------------------------------------------------------------------
# Estado (quais produtos já tiveram Reel, em quais redes)
# ----------------------------------------------------------------------------
def carregar_estado(caminho: str | None = None) -> list[dict]:
    try:
        with open(caminho or ESTADO_PADRAO, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("reels", []) if isinstance(d, dict) else []
    except (OSError, ValueError):
        return []


def salvar_estado(reels: list[dict], caminho: str | None = None) -> None:
    caminho = caminho or ESTADO_PADRAO
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"reels": reels}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, caminho)


def _completo(r: dict) -> bool:
    return all(r.get(rede) for rede in REDES)


def escolher_produto(produtos: list[dict], reels: list[dict], so: str | None = None):
    """(produto, registro_pendente). Prioridade: 1) Reel de hoje que ficou sem uma rede (completa só a que falta);
    2) produto novo sem nenhum Reel (mais novo primeiro); 3) o menos postado em Reels, o mais antigo primeiro."""
    por_id = {p["id"]: p for p in produtos}
    hoje = _agora().date().isoformat()
    for r in reversed(reels):
        if r.get("data") == hoje and not _completo(r) and r.get("id_produto") in por_id and not so:
            return por_id[r["id_produto"]], r
    if so:
        produtos = [p for p in produtos if p["id"] == so]
    if not produtos:
        return None, None
    postados = {}
    for r in reels:
        if _completo(r) or r.get("facebook") or r.get("instagram"):
            postados.setdefault(r.get("id_produto"), []).append(r.get("data", ""))
    sem_reel = [p for p in produtos if p["id"] not in postados]
    if sem_reel:
        return sorted(sem_reel, key=lambda p: str(p.get("criado_em") or ""), reverse=True)[0], None
    escolhido = min(produtos, key=lambda p: (len(postados[p["id"]]), max(postados[p["id"]]), str(p.get("criado_em") or "")))
    return escolhido, None


def produtos_vendaveis(caminho: str | None = None) -> list[dict]:
    return [p for p in catalogo.carregar(caminho)["produtos"]
            if p.get("status") == "pronto" and travas.link_ok(p.get("link_compra", ""))]


# ----------------------------------------------------------------------------
# Legenda
# ----------------------------------------------------------------------------
def texto_base(produto: dict, roteiros: list[dict] | None = None) -> str:
    """Texto do Reel: a legenda do roteiro (se existir) sem o CTA do roteiro; senão título + promessa do catálogo."""
    rot = next((r for r in (roteiros or []) if r.get("id_produto") == produto["id"]), None)
    if rot and rot.get("legenda"):
        linhas = [l for l in str(rot["legenda"]).splitlines() if l.strip() and not re.search(r"link na bio", l, re.I)]
        texto = "\n".join(linhas)
    else:
        texto = f"{produto.get('nome', '')}\n{produto.get('promessa') or ''}".strip()
    return travas.sanear_texto(travas.limpar_markdown(texto))


def legenda_da_rede(produto: dict, rede: str, roteiros: list[dict] | None = None) -> str:
    base = texto_base(produto, roteiros)
    preco = produto.get("preco_texto")
    if preco and preco not in base:
        base = f"{base}\n\nGuia em PDF por {preco}."
    return travas.reduzir_hashtags(travas.finalizar_para_rede(produto, base, rede, "VITRINE"), HASHTAGS_REEL)


# ----------------------------------------------------------------------------
# Meta
# ----------------------------------------------------------------------------
def com_tentativas(chamada, tentativas: int = 3, espera: float = 4.0):
    """Repete em erro de rede, 429 ou 5xx (espera 4 s, 8 s). 4xx volta na hora: repetir não resolve."""
    for i in range(tentativas):
        try:
            r = chamada()
        except requests.RequestException:
            if i == tentativas - 1:
                raise
        else:
            if r.status_code != 429 and r.status_code < 500:
                return r
            if i == tentativas - 1:
                return r
        time.sleep(espera * (i + 1))


class ErroMeta(RuntimeError):
    pass


def _ok(r, o_que: str) -> dict:
    if r.status_code >= 400:
        raise ErroMeta(f"{o_que}: HTTP {r.status_code} {str(r.text)[:300]}")
    try:
        return r.json()
    except ValueError:
        return {}


def token_da_pagina(token: str, page_id: str) -> str:
    r = com_tentativas(lambda: requests.get(_graph("me/accounts"), params={
        "access_token": token, "fields": "id,name,access_token", "limit": 100}, timeout=30))
    for p in _ok(r, "me/accounts").get("data", []):
        if str(p.get("id")) == str(page_id):
            return p["access_token"]
    raise ErroMeta("FB_PAGE_ID não encontrado nas páginas do token")


def publicar_facebook(video: str, descricao: str, token_pagina: str, page_id: str, esperar=time.sleep) -> dict:
    """Reel da Página: start -> envia o arquivo -> finish (PUBLISHED). Devolve {id, source?}."""
    tam = os.path.getsize(video)
    ini = _ok(com_tentativas(lambda: requests.post(_graph(f"{page_id}/video_reels"), data={
        "upload_phase": "start", "access_token": token_pagina}, timeout=60)), "Facebook start")
    vid, url = ini.get("video_id"), ini.get("upload_url") or f"https://rupload.facebook.com/video-upload/{GRAPH_VERSION}/{ini.get('video_id')}"
    if not vid:
        raise ErroMeta("Facebook start sem video_id")

    def enviar():
        with open(video, "rb") as f:
            return requests.post(url, data=f, timeout=300, headers={
                "Authorization": f"OAuth {token_pagina}", "offset": "0", "file_size": str(tam)})
    _ok(com_tentativas(enviar), "Facebook envio do vídeo")
    fim = _ok(com_tentativas(lambda: requests.post(_graph(f"{page_id}/video_reels"), data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED", "description": descricao,
        "access_token": token_pagina}, timeout=60)), "Facebook finish")
    if fim.get("success") is False:
        raise ErroMeta(f"Facebook finish recusado: {fim}")
    return {"id": vid, "source": _url_do_video(vid, token_pagina, esperar)}


def _url_do_video(vid: str, token_pagina: str, esperar=time.sleep, tentativas: int = 10) -> str | None:
    """URL pública do mp4 hospedado pelo Facebook (o Instagram baixa por ela). None se a API não entregar."""
    for _ in range(tentativas):
        try:
            r = requests.get(_graph(vid), params={"fields": "source,status", "access_token": token_pagina}, timeout=30)
            if r.status_code == 200 and r.json().get("source"):
                return r.json()["source"]
        except requests.RequestException:
            pass
        esperar(6)
    return None


def publicar_instagram(video: str, video_url: str | None, legenda: str, token: str, ig_id: str,
                       esperar=time.sleep, tentativas_status: int = 40) -> dict:
    """Reel do Instagram. Com URL pública usa video_url; sem ela, upload resumível do arquivo."""
    dados = {"media_type": "REELS", "caption": legenda, "share_to_feed": "true", "access_token": token}
    resumivel = not video_url
    if resumivel:
        dados["upload_type"] = "resumable"
    else:
        dados["video_url"] = video_url

    def criar(d):
        return com_tentativas(lambda: requests.post(_graph(f"{ig_id}/media"), data=d, timeout=90))
    r = criar(dados)
    if r.status_code >= 400 and travas.erro_de_hashtag(r.text):
        dados["caption"] = travas.reduzir_hashtags(legenda, 5)
        r = criar(dados)
    c = _ok(r, "Instagram container")
    cid = c.get("id")
    if not cid:
        raise ErroMeta("Instagram container sem id")
    if resumivel:
        uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{GRAPH_VERSION}/{cid}"

        def enviar():
            with open(video, "rb") as f:
                return requests.post(uri, data=f, timeout=300, headers={
                    "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(os.path.getsize(video))})
        _ok(com_tentativas(enviar), "Instagram envio do vídeo")
    for _ in range(tentativas_status):  # vídeo leva de segundos a minutos para ficar FINISHED
        st = requests.get(_graph(cid), params={"fields": "status_code", "access_token": token}, timeout=30).json().get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise ErroMeta(f"Instagram não processou o vídeo (status {st})")
        esperar(8)
    else:
        raise ErroMeta("Instagram: vídeo não ficou pronto a tempo")
    p = _ok(com_tentativas(lambda: requests.post(_graph(f"{ig_id}/media_publish"), data={
        "creation_id": cid, "access_token": token}, timeout=90)), "Instagram publicação")
    return {"id": p.get("id")}


# ----------------------------------------------------------------------------
# Execução
# ----------------------------------------------------------------------------
def _gerador():
    spec = importlib.util.spec_from_file_location("generate_reels", os.path.join(RAIZ, "scripts", "generate_reels.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _roteiros() -> list[dict]:
    from . import reels
    return reels.carregar()


def executar(dry_run: bool = True, so: str | None = None, pasta: str = "reels", estado: str | None = None,
             gerar=None, publicar_fb=publicar_facebook, publicar_ig=publicar_instagram) -> int:
    """0 = nada a fazer ou tudo certo; 1 = alguma rede falhou (o workflow marca vermelho para você ver)."""
    produtos = produtos_vendaveis()
    reels_estado = carregar_estado(estado)
    produto, pendente = escolher_produto(produtos, reels_estado, so)
    if not produto:
        _log("Nenhum produto pronto com link da Cakto: nada a publicar.")
        return 0
    roteiros = _roteiros()
    _log(f"Produto: {produto['nome']} ({produto['id']})" + (" [completando a rede que faltou hoje]" if pendente else ""))
    legendas = {rede: legenda_da_rede(produto, rede, roteiros) for rede in REDES}
    if dry_run:
        _log(f"[DRY_RUN] Nada foi gerado nem publicado.\nPúblico: {travas.rotulo_publico()}")
        for rede in REDES:
            _log(f"Legenda {rede.capitalize()}:\n{legendas[rede]}\n")
        return 0

    token, page_id, ig_id = (os.getenv("META_LONG_LIVED_TOKEN", ""), os.getenv("FB_PAGE_ID", ""),
                             os.getenv("INSTAGRAM_ACCOUNT_ID", ""))
    if not (token and page_id and ig_id):
        _log("ERRO: defina META_LONG_LIVED_TOKEN, FB_PAGE_ID e INSTAGRAM_ACCOUNT_ID.")
        return 1
    gr = gerar or _gerador()
    video = os.path.join(pasta, gr.slug(gr.titulo_de({"nome": produto["nome"]})) + ".mp4")
    info = gr.gerar_video({**produto, "titulo": produto["nome"]}, video)
    _log(f"Vídeo: {video}  música: {os.path.basename(info['musica']) if info.get('musica') else 'nenhuma (' + str(info.get('motivo')) + ')'}")

    registro = pendente or {"id_produto": produto["id"], "nome": produto["nome"], "data": _agora().date().isoformat(),
                            "facebook": None, "instagram": None}
    if not pendente:
        reels_estado.append(registro)
    erros = []
    try:
        token_pagina = token_da_pagina(token, page_id)
    except Exception as e:
        erros.append(f"Facebook/token: {e}")
        token_pagina = None
    video_url = registro.get("video_url")
    if token_pagina and not registro.get("facebook"):
        try:
            r = publicar_fb(video, legendas["facebook"], token_pagina, page_id)
            registro["facebook"] = r["id"]
            video_url = r.get("source")
            _log(f"Facebook: Reel publicado ({r['id']})")
        except Exception as e:
            erros.append(f"Facebook: {e}")
    if token_pagina and not registro.get("instagram"):
        try:
            r = publicar_ig(video, video_url, legendas["instagram"], token_pagina, ig_id)
            registro["instagram"] = r["id"]
            _log(f"Instagram: Reel publicado ({r['id']})")
        except Exception as e:
            erros.append(f"Instagram: {e}")
    if not (registro.get("facebook") or registro.get("instagram")):
        reels_estado.remove(registro) if registro in reels_estado else None  # nada saiu: não conta como postado
    salvar_estado(reels_estado, estado)
    for e in erros:
        _log(f"ERRO {e}")
    return 1 if erros else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", default="", help="id de um produto (ex.: p20261005-1)")
    ap.add_argument("--pasta", default="reels")
    ap.add_argument("--dry-run", action="store_true", default=None)
    a = ap.parse_args(argv)
    dry = a.dry_run if a.dry_run is not None else os.getenv("REELS_DRY_RUN", "true").strip().lower() != "false"
    return executar(dry_run=dry, so=a.so or None, pasta=a.pasta)


if __name__ == "__main__":
    sys.exit(main())

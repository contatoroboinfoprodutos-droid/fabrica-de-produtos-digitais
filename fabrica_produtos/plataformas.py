"""Cliente da Cakto (única plataforma de venda desta fábrica).

Baseado na documentação pública da Cakto (docs.cakto.com.br):
  - token:   POST /public_api/token/ (formulário com client_id e client_secret)
  - listar:  GET  /public_api/products/   (search, status, limit, page; resposta com count/next/results)
  - obter:   GET  /public_api/products/{id}/
  - criar:   POST /public_api/products/   ("já gera a oferta padrão, o checkout e o link de pagamento")
  - link:    https://pay.cakto.com.br/{id_da_oferta}   (montado a partir de offers[].id)

NÃO foi testado contra uma conta real. Os endereços podem ser trocados por variáveis de ambiente e o
comando `sondar` (somente leitura) mostra no log o que a sua conta aceita de verdade.
Nenhuma função aqui imprime credencial, token ou o corpo da resposta de autenticação.
"""
import logging
import os
import time

import requests

from .texto import formatar_preco, normalizar, parse_preco
from .travas import link_ok

logger = logging.getLogger("fabrica")
TIMEOUT = 30
MAX_ESPERA_429 = 60  # segundos


class NaoSuportado(Exception):
    """A plataforma não oferece (ou não confirmamos) essa operação por API."""


class ErroPlataforma(Exception):
    """Falha de comunicação ou resposta inesperada (a mensagem nunca contém segredos)."""

    def __init__(self, mensagem: str = "", codigo: int | None = None):
        super().__init__(mensagem)
        self.codigo = codigo


def _env(nome: str) -> str:
    return os.getenv(nome, "").strip()


def _espera(resposta) -> float:
    try:
        return max(1.0, min(float(resposta.headers.get("Retry-After", "5")), MAX_ESPERA_429))
    except (TypeError, ValueError):
        return 5.0


def dados_obrigatorios(produto: dict) -> dict:
    """name/description/price que a Cakto exige em todo PUT (um PUT só com `image` volta 400 'obrigatório')."""
    preco = parse_preco(produto.get("preco"))
    d = {"name": produto["nome"], "description": produto.get("descricao_oferta") or produto.get("promessa") or produto["nome"]}
    if preco is not None:
        d["price"] = f"{preco:.2f}"
    return d


class Cakto:
    nome = "cakto"
    variaveis = ("CAKTO_CLIENT_ID", "CAKTO_CLIENT_SECRET")  # só os NOMES aparecem em relatórios

    def __init__(self):
        self.base = (_env("CAKTO_BASE_URL") or "https://api.cakto.com.br").rstrip("/")
        self.pay_base = (_env("CAKTO_PAY_BASE") or "https://pay.cakto.com.br").rstrip("/")
        self._token = ""

    # -- credenciais --
    def faltando(self) -> list[str]:
        return [v for v in self.variaveis if not _env(v)]

    def configurada(self) -> bool:
        return not self.faltando()

    # -- HTTP --
    def _autenticar(self) -> None:
        try:
            r = requests.request("POST", f"{self.base}/public_api/token/", timeout=TIMEOUT,
                                 data={"client_id": _env("CAKTO_CLIENT_ID"),
                                       "client_secret": _env("CAKTO_CLIENT_SECRET")})
        except requests.RequestException as e:
            raise ErroPlataforma(f"cakto: falha de rede na autenticação ({type(e).__name__})")
        if r.status_code not in (200, 201):
            raise ErroPlataforma(f"cakto: autenticação recusada (HTTP {r.status_code})")
        try:
            self._token = str(r.json().get("access_token") or "")
        except ValueError:
            self._token = ""
        if not self._token:
            raise ErroPlataforma("cakto: a resposta de autenticação não trouxe token")

    def _req(self, metodo: str, caminho: str, **kw):
        """Reaproveita o token, renova se vier 401 e respeita o Retry-After do 429."""
        for tentativa in (1, 2, 3):
            if not self._token:
                self._autenticar()
            try:
                r = requests.request(metodo, self.base + caminho, timeout=TIMEOUT,
                                     headers={"Authorization": f"Bearer {self._token}"}, **kw)
            except requests.RequestException as e:
                raise ErroPlataforma(f"cakto: falha de rede em {metodo} {caminho} ({type(e).__name__})")
            if r.status_code == 401 and tentativa == 1:
                self._token = ""
                continue
            if r.status_code == 429 and tentativa < 3:
                time.sleep(_espera(r))
                continue
            if r.status_code in (200, 201):
                try:
                    return r.json()
                except ValueError:
                    raise ErroPlataforma(f"cakto: {metodo} {caminho} devolveu resposta que não é JSON")
            detalhe = f": {r.text[:300]}" if r.status_code in (400, 403, 404, 409, 422) else ""
            raise ErroPlataforma(f"cakto: {metodo} {caminho} recusado (HTTP {r.status_code}){detalhe}", r.status_code)
        raise ErroPlataforma(f"cakto: {metodo} {caminho} sem sucesso após 3 tentativas")

    # -- produtos --
    def _resumo(self, p: dict) -> dict:
        """Normaliza um produto da API: id, nome, status, ativo e o link de compra (da oferta padrão)."""
        ofertas = [o for o in (p.get("offers") or []) if isinstance(o, dict)]
        oferta = next((o for o in ofertas if o.get("default")), ofertas[0] if ofertas else None)
        link = f"{self.pay_base}/{oferta['id']}" if oferta and oferta.get("id") else ""
        ativo = p.get("status") == "active" and (oferta is None or oferta.get("status") in (None, "active"))
        return {"id": str(p.get("id") or ""), "nome": str(p.get("name") or ""), "status": p.get("status"),
                "ativo": bool(ativo), "link": link if link_ok(link) else "",
                "imagem": str(p.get("image") or ""), "entrega": bool(p.get("emailAccessLink"))}

    def listar_por_nome(self, nome: str) -> list[dict]:
        """Produtos cujo nome contém `nome` (até 5 páginas), sem os apagados."""
        achados = []
        for pagina in range(1, 6):
            j = self._req("GET", "/public_api/products/",
                          params={"search": nome, "limit": 50, "page": pagina,
                                  "status": "active,waiting_config,blocked"})
            achados += [p for p in (j.get("results") or []) if isinstance(p, dict)]
            if not j.get("next"):
                break
        return achados

    def buscar_por_nome(self, nome: str) -> dict | None:
        alvo = normalizar(nome)
        for p in self.listar_por_nome(nome):
            if normalizar(str(p.get("name") or "")) == alvo:
                return self._resumo(self._req("GET", f"/public_api/products/{p['id']}/"))
        return None

    def criar_produto(self, produto: dict, pdf_path: str, url_entrega: str | None = None,
                      urls_imagem: list[str] | None = None, capa_path: str | None = None) -> dict:
        """Cria o produto (que já nasce com oferta, checkout e link). Se já existir um com o mesmo nome,
        reaproveita: assim uma nova tentativa depois de um erro de rede nunca duplica o produto.

        Com `url_entrega` o produto recebe a entrega por e-mail (emailAccess) apontando para o PDF. Ele só vira 'active'
        depois de tentar a capa. Com CAKTO_EXIGE_IMAGEM=true (padrão: false até a imagem ser confirmada na Cakto) ele só
        é ativado se a capa subir; senão fica em 'waiting_config'. O erro CAKTO_IMAGEM_ERROR aparece no log e o comando
        `capas` tenta de novo depois. Sem `url_entrega` o produto fica em 'waiting_config' (não pode ser vendido vazio)."""
        existente = self.buscar_por_nome(produto["nome"])
        if existente:
            existente["existente"] = True
            if url_entrega and existente.get("status") == "waiting_config":
                self._entrega(existente["id"], url_entrega)
                existente = self.finalizar(existente["id"], urls_imagem, capa_path, produto) | {"existente": True}
            elif not existente.get("imagem") and (urls_imagem or capa_path):
                existente = self.finalizar(existente["id"], urls_imagem, capa_path, produto) | {"existente": True}
            return existente
        preco = parse_preco(produto.get("preco"))
        if preco is None:
            raise ErroPlataforma("cakto: produto sem preço válido")
        corpo = {"name": produto["nome"], "description": produto.get("descricao_oferta") or produto["promessa"],
                 "price": f"{preco:.2f}", "currency": "BRL", "type": "unique", "status": "waiting_config"}
        if url_entrega:
            corpo.update({"contentDeliveries": ["emailAccess"], "emailAccessLink": url_entrega})
        if _env("CAKTO_SALES_PAGE"):
            corpo["salesPage"] = _env("CAKTO_SALES_PAGE")
        r = self._resumo(self._req("POST", "/public_api/products/", json=corpo))
        r["existente"] = False
        if url_entrega and r["id"]:
            r = self.finalizar(r["id"], urls_imagem, capa_path, produto) | {"existente": False}
        return r

    def enviar_imagem(self, produto_id: str, urls: list[str] | None = None, capa_path: str | None = None,
                      produto: dict | None = None) -> str:
        """Põe a capa no produto. `image` é URL pública (PUT /products/{id}/). O PUT exige name, description e price
        (a execução real devolveu 400 'obrigatório' só com `image`): `produto` (catálogo) fornece esses dados e eles vão
        junto em cada tentativa. Tenta cada URL; se todas forem recusadas e houver o arquivo, tenta o PNG em multipart.
        Só devolve se o produto realmente passou a ter `image`. Falha = ErroPlataforma com o código HTTP."""
        erros = []
        base = dados_obrigatorios(produto) if produto else {}
        for url in urls or []:
            try:
                self._req("PUT", f"/public_api/products/{produto_id}/", json={**base, "image": url})
                if self._resumo(self._req("GET", f"/public_api/products/{produto_id}/"))["imagem"]:
                    return url
                erros.append(ErroPlataforma(f"cakto: PUT aceito mas o produto continua sem imagem ({url[:60]})", 200))
            except ErroPlataforma as e:
                erros.append(e)
        if capa_path and os.path.isfile(capa_path):
            try:
                with open(capa_path, "rb") as f:
                    self._req("PUT", f"/public_api/products/{produto_id}/", data=base,
                              files={"image": (os.path.basename(capa_path), f.read(), "image/png")})
                if self._resumo(self._req("GET", f"/public_api/products/{produto_id}/"))["imagem"]:
                    return "multipart"
                erros.append(ErroPlataforma("cakto: envio multipart aceito mas o produto continua sem imagem", 200))
            except ErroPlataforma as e:
                erros.append(e)
        ultimo = erros[-1] if erros else ErroPlataforma("cakto: nenhuma URL nem arquivo de capa para enviar")
        raise ErroPlataforma(f"{ultimo} (tentativas: {len(erros)})", getattr(ultimo, "codigo", None))

    def _entrega(self, produto_id: str, url_entrega: str) -> None:
        self._req("PUT", f"/public_api/products/{produto_id}/",
                  json={"contentDeliveries": ["emailAccess"], "emailAccessLink": url_entrega})

    def ativar(self, produto_id: str) -> dict:
        self._req("PUT", f"/public_api/products/{produto_id}/", json={"status": "active"})
        return self._resumo(self._req("GET", f"/public_api/products/{produto_id}/"))

    def finalizar(self, produto_id: str, urls_imagem=None, capa_path=None, produto: dict | None = None) -> dict:
        """Capa primeiro, ativação depois. Falha na capa: log CAKTO_IMAGEM_ERROR e o produto fica em 'waiting_config'
        (só se CAKTO_EXIGE_IMAGEM=true; o padrão ativa mesmo assim). Nunca levanta por causa da imagem."""
        imagem_erro = ""
        try:
            self.enviar_imagem(produto_id, urls_imagem, capa_path, produto)
        except ErroPlataforma as e:
            imagem_erro = str(e)
            logger.error("CAKTO_IMAGEM_ERROR produto=%s http=%s detalhe=%s", produto_id, e.codigo or "-", e)
            print(f"CAKTO_IMAGEM_ERROR produto={produto_id} http={e.codigo or '-'} {e}", flush=True)
        if imagem_erro and _env("CAKTO_EXIGE_IMAGEM").lower() == "true":
            r = self._resumo(self._req("GET", f"/public_api/products/{produto_id}/"))
        else:
            r = self.ativar(produto_id)
        r["imagem_erro"] = imagem_erro
        return r

    def configurar_entrega(self, produto_id: str, url_entrega: str) -> dict:
        """Aponta a entrega por e-mail para o PDF e ativa o produto (PUT é atualização parcial na Cakto).
        Só mexe em produto que está em 'waiting_config'; quem chama garante isso."""
        self._req("PUT", f"/public_api/products/{produto_id}/",
                  json={"contentDeliveries": ["emailAccess"], "emailAccessLink": url_entrega,
                        "status": "active"})
        return self._resumo(self._req("GET", f"/public_api/products/{produto_id}/"))

    # -- sondagem (somente leitura) --
    def sondar(self) -> list[str]:
        linhas = [f"## {self.nome}"]
        falta = self.faltando()
        if falta:
            linhas.append(f"- credenciais: FALTAM as variáveis {', '.join(falta)}")
            return linhas
        linhas.append("- credenciais: todas as variáveis esperadas estão presentes")
        try:
            self._autenticar()
            linhas.append("- autenticação: OK")
            j = self._req("GET", "/public_api/products/", params={"limit": 5})
            itens = [p for p in (j.get("results") or []) if isinstance(p, dict)]
            linhas.append(f"- listagem: OK, {j.get('count', len(itens))} produto(s) na conta")
            linhas.append(f"- chaves da resposta: {sorted(j.keys())}")
            if itens:
                linhas.append(f"- chaves de um produto: {sorted(itens[0].keys())}")
        except ErroPlataforma as e:
            linhas.append(f"- autenticação/listagem: FALHOU ({e})")
        linhas.append("- criar produto: implementado conforme a documentação, NÃO testado (a sondagem é "
                      "somente leitura). Sem hospedagem do PDF, o produto nasce em 'waiting_config'.")
        linhas.append(f"- escopos da chave de API necessários: read, write, products, offers")
        return linhas


REGISTRO = {"cakto": Cakto}


def instanciar(nomes: list[str]) -> list:
    return [REGISTRO[n]() for n in nomes if n in REGISTRO]

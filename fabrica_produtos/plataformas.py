"""Clientes das plataformas de venda (Kiwify e Hotmart).

IMPORTANTE: os endereços e campos abaixo vêm da documentação pública como eu a conheço e NÃO foram
validados contra as suas contas. Por isso:
  - todos os endereços podem ser trocados por variável de ambiente;
  - o comando `sondar` (somente leitura) mostra no log o que cada API aceita e o formato real da resposta;
  - criar produto por API só será implementado depois que a sondagem confirmar um endpoint de criação
    (inventar o formato do pedido seria chute). Até lá, criar_produto levanta NaoSuportado e o
    registrador cai no fluxo "pacote pronto + busca do link pela API".
Nenhuma função aqui imprime credencial, token ou o corpo da resposta de autenticação.
"""
import base64
import logging
import os

import requests

from .texto import normalizar
from .travas import link_ok

logger = logging.getLogger("fabrica")
TIMEOUT = 30


class NaoSuportado(Exception):
    """A plataforma não oferece (ou não confirmamos) essa operação por API."""


class ErroPlataforma(Exception):
    """Falha de comunicação ou resposta inesperada (a mensagem nunca contém segredos)."""


def _env(*nomes: str) -> str:
    for n in nomes:
        v = os.getenv(n, "").strip()
        if v:
            return v
    return ""


def _itens(resposta_json) -> list:
    """Extrai a lista de itens de formatos comuns de resposta paginada."""
    if isinstance(resposta_json, list):
        return resposta_json
    if isinstance(resposta_json, dict):
        for chave in ("data", "items", "products", "results"):
            if isinstance(resposta_json.get(chave), list):
                return resposta_json[chave]
    return []


def _achar_link(item: dict) -> str:
    for chave in ("checkout_link", "payment_link", "checkout_url", "link", "url", "sales_page"):
        v = item.get(chave)
        if isinstance(v, str) and link_ok(v):
            return v.strip()
    return ""


class Plataforma:
    nome = ""
    variaveis: tuple = ()  # nomes das variáveis exigidas (só os nomes aparecem em relatórios)

    def faltando(self) -> list[str]:
        return [v for v in self.variaveis if not _env(v)]

    def configurada(self) -> bool:
        return not self.faltando()

    # -- a implementar em cada plataforma --
    def _pedir_pagina(self, pagina_token):
        raise NotImplementedError

    def listar_produtos(self) -> list[dict]:
        """Lista normalizada: [{'id','nome','link'}]. Para depois de 10 páginas."""
        vistos, saida, token = set(), [], None
        for _ in range(10):
            j = self._pedir_pagina(token)
            novos = 0
            for it in _itens(j):
                if not isinstance(it, dict):
                    continue
                pid = str(it.get("id") or it.get("uuid") or it.get("ucode") or "")
                if pid in vistos:
                    continue
                vistos.add(pid)
                novos += 1
                saida.append({"id": pid, "nome": str(it.get("name") or it.get("title") or it.get("nome") or ""),
                              "link": _achar_link(it)})
            token = self._proximo_token(j)
            if not token or not novos:
                break
        return saida

    def _proximo_token(self, j):
        return None

    def buscar_por_nome(self, nome: str) -> dict | None:
        alvo = normalizar(nome)
        return next((p for p in self.listar_produtos() if normalizar(p["nome"]) == alvo), None)

    def criar_produto(self, produto: dict, pdf_path: str) -> dict:
        raise NaoSuportado(f"{self.nome}: criação de produto por API não confirmada (rode `sondar`).")

    def sondar(self) -> list[str]:
        """Relatório de capacidades (somente leitura). Não imprime valores de credenciais."""
        linhas = [f"## {self.nome}"]
        falta = self.faltando()
        if falta:
            linhas.append(f"- credenciais: FALTAM as variáveis {', '.join(falta)}")
            return linhas
        linhas.append("- credenciais: todas as variáveis esperadas estão presentes")
        try:
            j = self._pedir_pagina(None)
            itens = _itens(j)
            linhas.append(f"- autenticação e listagem: OK, {len(itens)} produto(s) na primeira página")
            if isinstance(j, dict):
                linhas.append(f"- chaves da resposta: {sorted(j.keys())}")
            if itens and isinstance(itens[0], dict):
                linhas.append(f"- chaves de um produto: {sorted(itens[0].keys())}")
                linhas.append(f"- link de compra aparece na listagem: {'sim' if _achar_link(itens[0]) else 'não'}")
        except ErroPlataforma as e:
            linhas.append(f"- autenticação/listagem: FALHOU ({e})")
        linhas.append("- criar produto: NÃO testado (a sondagem é somente leitura). Nenhum endpoint de "
                      "criação está implementado; o registrador usa o pacote pronto + busca do link.")
        return linhas


class Kiwify(Plataforma):
    nome = "kiwify"
    variaveis = ("KIWIFY_CLIENT_ID", "KIWIFY_CLIENT_SECRET", "KIWIFY_ACCOUNT_ID")

    def __init__(self):
        self.base = _env("KIWIFY_BASE_URL") or "https://public-api.kiwify.com/v1"
        self._token = ""

    def _autenticar(self) -> None:
        try:
            r = requests.post(self.base + "/oauth/token", timeout=TIMEOUT,
                              data={"client_id": _env("KIWIFY_CLIENT_ID"),
                                    "client_secret": _env("KIWIFY_CLIENT_SECRET")})
        except requests.RequestException as e:
            raise ErroPlataforma(f"kiwify: falha de rede na autenticação ({type(e).__name__})")
        if r.status_code != 200:
            raise ErroPlataforma(f"kiwify: autenticação recusada (HTTP {r.status_code})")
        self._token = str(r.json().get("access_token") or "")
        if not self._token:
            raise ErroPlataforma("kiwify: a resposta de autenticação não trouxe token")

    def _pedir_pagina(self, pagina_token):
        if not self._token:
            self._autenticar()
        try:
            r = requests.get(self.base + "/products", timeout=TIMEOUT,
                             params={"page_size": 100, "page_number": pagina_token or 1},
                             headers={"Authorization": f"Bearer {self._token}",
                                      "x-kiwify-account-id": _env("KIWIFY_ACCOUNT_ID")})
        except requests.RequestException as e:
            raise ErroPlataforma(f"kiwify: falha de rede ({type(e).__name__})")
        if r.status_code != 200:
            raise ErroPlataforma(f"kiwify: listagem recusada (HTTP {r.status_code})")
        return r.json()

    def _proximo_token(self, j):
        # Sem metadado de paginação confiável: a próxima página só é pedida se esta veio cheia.
        itens = _itens(j)
        if len(itens) < 100:
            return None
        self._pagina = getattr(self, "_pagina", 1) + 1
        return self._pagina


class Hotmart(Plataforma):
    nome = "hotmart"
    variaveis = ("HOTMART_CLIENT_ID", "HOTMART_CLIENT_SECRET")

    def __init__(self):
        self.auth_url = _env("HOTMART_AUTH_URL") or "https://api-sec-vlc.hotmart.com/security/oauth/token"
        self.base = _env("HOTMART_BASE_URL") or "https://developers.hotmart.com/products/api/v1"
        self._token = ""

    def _basic(self) -> str:
        pronto = _env("HOTMART_BASIC")
        if pronto:
            return pronto.removeprefix("Basic ").strip()
        par = f"{_env('HOTMART_CLIENT_ID')}:{_env('HOTMART_CLIENT_SECRET')}"
        return base64.b64encode(par.encode()).decode()

    def _autenticar(self) -> None:
        try:
            r = requests.post(self.auth_url, timeout=TIMEOUT,
                              params={"grant_type": "client_credentials",
                                      "client_id": _env("HOTMART_CLIENT_ID"),
                                      "client_secret": _env("HOTMART_CLIENT_SECRET")},
                              headers={"Authorization": f"Basic {self._basic()}"})
        except requests.RequestException as e:
            raise ErroPlataforma(f"hotmart: falha de rede na autenticação ({type(e).__name__})")
        if r.status_code != 200:
            raise ErroPlataforma(f"hotmart: autenticação recusada (HTTP {r.status_code})")
        self._token = str(r.json().get("access_token") or "")
        if not self._token:
            raise ErroPlataforma("hotmart: a resposta de autenticação não trouxe token")

    def _pedir_pagina(self, pagina_token):
        if not self._token:
            self._autenticar()
        params = {"max_results": 100}
        if pagina_token:
            params["page_token"] = pagina_token
        try:
            r = requests.get(self.base + "/products", timeout=TIMEOUT, params=params,
                             headers={"Authorization": f"Bearer {self._token}"})
        except requests.RequestException as e:
            raise ErroPlataforma(f"hotmart: falha de rede ({type(e).__name__})")
        if r.status_code != 200:
            raise ErroPlataforma(f"hotmart: listagem recusada (HTTP {r.status_code})")
        return r.json()

    def _proximo_token(self, j):
        info = j.get("page_info") if isinstance(j, dict) else None
        return (info or {}).get("next_page_token") or None


REGISTRO = {"kiwify": Kiwify, "hotmart": Hotmart}


def instanciar(nomes: list[str]) -> list[Plataforma]:
    return [REGISTRO[n]() for n in nomes if n in REGISTRO]

"""Hospedagem do PDF no Google Drive (a Cakto entrega o produto por um link que aponta para o PDF).

Dois modos de autenticação, escolhidos pelos Secrets presentes:
  - conta de serviço: GDRIVE_SERVICE_ACCOUNT_JSON ou GDRIVE_CREDENTIALS_JSON (+ GDRIVE_FOLDER_ID)
  - OAuth da sua conta Google: GDRIVE_OAUTH_CLIENT_ID, GDRIVE_OAUTH_CLIENT_SECRET, GDRIVE_OAUTH_REFRESH_TOKEN
    (+ GDRIVE_FOLDER_ID)

LIMITAÇÃO IMPORTANTE da conta de serviço: ela não tem cota de armazenamento e não consegue ser dona de
arquivo numa pasta do "Meu Drive" de uma conta pessoal. O envio só funciona se a pasta estiver num Drive
COMPARTILHADO (Google Workspace) e a conta de serviço for membro dele. Em conta Gmail comum use o modo OAuth.
A ação `sondar` detecta esse problema antes de qualquer envio (somente leitura).

NÃO foi testado contra uma conta real. Nenhuma função imprime o JSON da conta de serviço, token ou segredo.
"""
import json
import logging
import os
import uuid

import requests

logger = logging.getLogger("fabrica")
TIMEOUT = 60
API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ESCOPO = "https://www.googleapis.com/auth/drive"

VARS_SA = ("GDRIVE_SERVICE_ACCOUNT_JSON", "GDRIVE_CREDENTIALS_JSON")  # aceita os dois nomes do Secret
VARS_OAUTH = ("GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET", "GDRIVE_OAUTH_REFRESH_TOKEN")

AVISO_COTA = ("o Google recusou o envio por falta de cota: contas de serviço não têm armazenamento e não "
              "gravam no Meu Drive de uma conta pessoal. Use uma pasta num Drive compartilhado (Workspace) "
              "ou o modo OAuth (GDRIVE_OAUTH_*)")


class ErroDrive(Exception):
    """Falha ao falar com o Drive (a mensagem nunca contém segredos)."""


def _env(nome: str) -> str:
    return os.getenv(nome, "").strip()


def _json_conta() -> str:
    """JSON da conta de serviço, em qualquer um dos nomes de Secret aceitos."""
    return next((v for v in (_env(n) for n in VARS_SA) if v), "")


def _motivo(r) -> str:
    """Extrai só o código de motivo e a mensagem curta do erro do Google."""
    try:
        e = r.json().get("error", {})
        motivos = ",".join(str(x.get("reason", "")) for x in e.get("errors", []) if isinstance(x, dict))
        return f"{motivos or e.get('status', '')}: {str(e.get('message', ''))[:160]}".strip(": ")
    except (ValueError, AttributeError):
        return ""


class Drive:
    nome = "drive"

    def __init__(self):
        self.pasta = _env("GDRIVE_FOLDER_ID")
        self._token = ""

    # -- credenciais --
    def modo(self) -> str:
        if _json_conta():
            return "conta_de_servico"
        if all(_env(v) for v in VARS_OAUTH):
            return "oauth"
        return ""

    def faltando(self) -> list[str]:
        falta = [] if self.pasta else ["GDRIVE_FOLDER_ID"]
        if not self.modo():
            falta += ["GDRIVE_SERVICE_ACCOUNT_JSON ou GDRIVE_CREDENTIALS_JSON (ou as três GDRIVE_OAUTH_*)"]
        return falta

    def configurada(self) -> bool:
        return not self.faltando()

    # -- autenticação --
    def _obter_token(self) -> str:
        if self.modo() == "oauth":
            try:
                r = requests.post(TOKEN_URL, timeout=TIMEOUT, data={
                    "client_id": _env("GDRIVE_OAUTH_CLIENT_ID"), "client_secret": _env("GDRIVE_OAUTH_CLIENT_SECRET"),
                    "refresh_token": _env("GDRIVE_OAUTH_REFRESH_TOKEN"), "grant_type": "refresh_token"})
            except requests.RequestException as e:
                raise ErroDrive(f"drive: falha de rede na autenticação ({type(e).__name__})")
            if r.status_code != 200:
                raise ErroDrive(f"drive: autenticação OAuth recusada (HTTP {r.status_code})")
            try:
                return str(r.json().get("access_token") or "")
            except ValueError:
                return ""
        try:  # conta de serviço: importado aqui para não exigir a biblioteca nos outros comandos
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account

            info = json.loads(_json_conta())
            cred = service_account.Credentials.from_service_account_info(info, scopes=[ESCOPO])
            cred.refresh(Request())
            return str(cred.token or "")
        except ImportError:
            raise ErroDrive("drive: falta a biblioteca google-auth (pip install google-auth)")
        except (ValueError, KeyError, TypeError):
            raise ErroDrive("drive: o JSON da conta de serviço é inválido")
        except Exception as e:  # erro de rede/assinatura: só o tipo, nunca o conteúdo
            raise ErroDrive(f"drive: autenticação da conta de serviço falhou ({type(e).__name__})")

    def _req(self, metodo: str, url: str, **kw):
        extras = kw.pop("headers", {})
        for tentativa in (1, 2):
            if not self._token:
                self._token = self._obter_token()
                if not self._token:
                    raise ErroDrive("drive: a autenticação não devolveu token")
            headers = {"Authorization": f"Bearer {self._token}", **extras}
            try:
                r = requests.request(metodo, url, timeout=TIMEOUT, headers=headers, **kw)
            except requests.RequestException as e:
                raise ErroDrive(f"drive: falha de rede ({type(e).__name__})")
            if r.status_code == 401 and tentativa == 1:
                self._token = ""
                continue
            if r.status_code in (200, 201):
                try:
                    return r.json()
                except ValueError:
                    raise ErroDrive("drive: resposta que não é JSON")
            motivo = _motivo(r)
            if "storageQuotaExceeded" in motivo:
                raise ErroDrive(f"drive: {AVISO_COTA}")
            raise ErroDrive(f"drive: {metodo} recusado (HTTP {r.status_code}) {motivo}".strip())
        raise ErroDrive("drive: sem sucesso após renovar o token")

    # -- operações --
    def _achar(self, nome: str) -> str:
        """Id de um arquivo com esse nome na pasta (para não duplicar em nova tentativa), ou ''."""
        seguro = nome.replace("\\", "\\\\").replace("'", "\\'")
        j = self._req("GET", f"{API}/files", params={
            "q": f"name = '{seguro}' and '{self.pasta}' in parents and trashed = false",
            "fields": "files(id)", "pageSize": 1, "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true"})
        arquivos = j.get("files") or []
        return str(arquivos[0]["id"]) if arquivos else ""

    def _enviar(self, caminho: str, nome: str, mime: str = "application/pdf") -> str:
        meta = json.dumps({"name": nome, "parents": [self.pasta], "mimeType": mime})
        with open(caminho, "rb") as f:
            conteudo = f.read()
        fronteira = uuid.uuid4().hex
        corpo = (f"--{fronteira}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                 f"--{fronteira}\r\nContent-Type: {mime}\r\n\r\n").encode() + conteudo + \
                f"\r\n--{fronteira}--".encode()
        j = self._req("POST", UPLOAD, params={"uploadType": "multipart", "supportsAllDrives": "true",
                                              "fields": "id"},
                      headers={"Content-Type": f"multipart/related; boundary={fronteira}"}, data=corpo)
        if not j.get("id"):
            raise ErroDrive("drive: o envio não devolveu o id do arquivo")
        return str(j["id"])

    def _liberar_link(self, arquivo_id: str) -> None:
        self._req("POST", f"{API}/files/{arquivo_id}/permissions", params={"supportsAllDrives": "true"},
                  json={"role": "reader", "type": "anyone"})

    def publicar_pdf(self, caminho: str, nome: str) -> str:
        """Envia o PDF (ou reaproveita o de mesmo nome), libera leitura por link e devolve o link de acesso.
        Quem tiver o link consegue abrir o PDF: é o link que a Cakto manda por e-mail ao comprador."""
        arquivo_id = self._achar(nome) or self._enviar(caminho, nome)
        self._liberar_link(arquivo_id)
        return f"https://drive.google.com/file/d/{arquivo_id}/view"

    def publicar_imagem(self, caminho: str, nome: str) -> str:
        """Envia a capa (PNG), libera leitura por link e devolve uma URL que serve a imagem direto (para <img>/Cakto)."""
        arquivo_id = self._achar(nome) or self._enviar(caminho, nome, "image/png")
        self._liberar_link(arquivo_id)
        return f"https://drive.google.com/thumbnail?id={arquivo_id}&sz=w1280"

    # -- sondagem (somente leitura) --
    def sondar(self) -> list[str]:
        linhas = [f"## {self.nome}"]
        falta = self.faltando()
        if falta:
            linhas.append(f"- credenciais: FALTAM {', '.join(falta)}")
            return linhas
        linhas.append(f"- modo de autenticação: {self.modo()}")
        try:
            j = self._req("GET", f"{API}/files/{self.pasta}", params={
                "fields": "id,name,mimeType,driveId,capabilities(canAddChildren)", "supportsAllDrives": "true"})
        except ErroDrive as e:
            linhas.append(f"- pasta: FALHOU ({e})")
            return linhas
        linhas.append("- autenticação e acesso à pasta: OK")
        if j.get("mimeType") != "application/vnd.google-apps.folder":
            linhas.append("- ATENÇÃO: o GDRIVE_FOLDER_ID não é uma pasta")
        if not (j.get("capabilities") or {}).get("canAddChildren", False):
            linhas.append("- ATENÇÃO: sem permissão para criar arquivos na pasta (compartilhe como Editor)")
        if self.modo() == "conta_de_servico":
            if j.get("driveId"):
                linhas.append("- pasta em Drive compartilhado: OK, o envio pela conta de serviço deve funcionar")
            else:
                linhas.append("- ATENÇÃO: a pasta está no Meu Drive; " + AVISO_COTA)
        else:
            linhas.append("- pasta usa a cota da sua própria conta (modo OAuth)")
        return linhas

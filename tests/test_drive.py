"""Drive e entrega do PDF com a rede simulada (nenhuma chamada real é feita)."""
import json
import os
import tempfile
import unittest
from unittest import mock

from fabrica_produtos import catalogo, config_fabrica as cfg, drive, plataformas, registrador
from tests.fixtures import produto_bom
from tests.test_cakto import Resp, cliente, produto_api

VARS = ("GDRIVE_SERVICE_ACCOUNT_JSON", "GDRIVE_FOLDER_ID", "GDRIVE_OAUTH_CLIENT_ID",
        "GDRIVE_OAUTH_CLIENT_SECRET", "GDRIVE_OAUTH_REFRESH_TOKEN")


class Google:
    """Simula o Drive: guarda as chamadas e responde por (metodo, trecho da url)."""

    def __init__(self, rotas):
        self.rotas, self.chamadas = rotas, []

    def __call__(self, metodo, url, **kw):
        self.chamadas.append((metodo, url, kw))
        for (m, trecho), item in self.rotas.items():
            if m == metodo and trecho in url:
                if isinstance(item, list):
                    item = item.pop(0)
                return item(kw) if callable(item) else item
        raise AssertionError(f"rota não prevista: {metodo} {url}")


def erro_google(status, motivo, msg="x"):
    return Resp(status, {"error": {"code": status, "message": msg, "errors": [{"reason": motivo}]}})


class BaseDrive(unittest.TestCase):
    def setUp(self):
        for k in VARS:
            self.addCleanup(os.environ.pop, k, None)
            os.environ.pop(k, None)
        os.environ["GDRIVE_OAUTH_CLIENT_ID"] = "cid"
        os.environ["GDRIVE_OAUTH_CLIENT_SECRET"] = "csegredo"
        os.environ["GDRIVE_OAUTH_REFRESH_TOKEN"] = "refresh"
        os.environ["GDRIVE_FOLDER_ID"] = "PASTA1"
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = os.path.join(self.tmp.name, "guia.pdf")
        with open(self.pdf, "wb") as f:
            f.write(b"%PDF-1.4 conteudo")
        # o token vem do endpoint OAuth (requests.post), o resto de requests.request
        p = mock.patch.object(drive.requests, "post", return_value=Resp(200, {"access_token": "tok"}))
        p.start()
        self.addCleanup(p.stop)

    def usar(self, srv):
        p = mock.patch.object(drive.requests, "request", srv)
        p.start()
        self.addCleanup(p.stop)


class ClienteDrive(BaseDrive):
    def test_modos_e_credenciais_faltando(self):
        self.assertEqual(drive.Drive().modo(), "oauth")
        for k in VARS:
            os.environ.pop(k, None)
        d = drive.Drive()
        self.assertFalse(d.configurada())
        self.assertIn("GDRIVE_FOLDER_ID", d.faltando())
        os.environ["GDRIVE_SERVICE_ACCOUNT_JSON"] = "{}"
        os.environ["GDRIVE_FOLDER_ID"] = "P"
        self.assertEqual(drive.Drive().modo(), "conta_de_servico")
        self.assertTrue(drive.Drive().configurada())

    def test_envia_libera_e_devolve_link(self):
        srv = Google({("GET", "/files"): Resp(200, {"files": []}),
                      ("POST", "upload/drive"): Resp(200, {"id": "ARQ9"}),
                      ("POST", "/permissions"): Resp(200, {"id": "p"})})
        self.usar(srv)
        link = drive.Drive().publicar_pdf(self.pdf, "p1-guia.pdf")
        self.assertEqual(link, "https://drive.google.com/file/d/ARQ9/view")
        envio = next(c for c in srv.chamadas if "upload/drive" in c[1])
        self.assertIn(b"%PDF-1.4 conteudo", envio[2]["data"])
        self.assertIn(b'"parents": ["PASTA1"]', envio[2]["data"])
        self.assertTrue(envio[2]["headers"]["Content-Type"].startswith("multipart/related; boundary="))
        perm = next(c for c in srv.chamadas if "/permissions" in c[1])
        self.assertEqual(perm[2]["json"], {"role": "reader", "type": "anyone"})

    def test_nao_duplica_arquivo_existente(self):
        srv = Google({("GET", "/files"): Resp(200, {"files": [{"id": "JA1"}]}),
                      ("POST", "/permissions"): Resp(200, {})})
        self.usar(srv)
        self.assertEqual(drive.Drive().publicar_pdf(self.pdf, "p1-guia.pdf"),
                         "https://drive.google.com/file/d/JA1/view")
        self.assertFalse(any("upload/drive" in c[1] for c in srv.chamadas))

    def test_nome_com_aspas_e_escapado_na_busca(self):
        srv = Google({("GET", "/files"): Resp(200, {"files": [{"id": "X"}]}),
                      ("POST", "/permissions"): Resp(200, {})})
        self.usar(srv)
        drive.Drive().publicar_pdf(self.pdf, "o'guia.pdf")
        self.assertIn("name = 'o\\'guia.pdf'", srv.chamadas[0][2]["params"]["q"])

    def test_erro_de_cota_tem_mensagem_clara_e_sem_segredo(self):
        srv = Google({("GET", "/files"): Resp(200, {"files": []}),
                      ("POST", "upload/drive"): erro_google(403, "storageQuotaExceeded")})
        self.usar(srv)
        with self.assertRaises(drive.ErroDrive) as c:
            drive.Drive().publicar_pdf(self.pdf, "a.pdf")
        msg = str(c.exception)
        self.assertIn("Drive compartilhado", msg)
        for segredo in ("csegredo", "refresh", "tok"):
            self.assertNotIn(segredo, msg)

    def test_401_renova_o_token_uma_vez(self):
        srv = Google({("GET", "/files"): [Resp(401, {}), Resp(200, {"files": [{"id": "A"}]})],
                      ("POST", "/permissions"): Resp(200, {})})
        self.usar(srv)
        self.assertTrue(drive.Drive().publicar_pdf(self.pdf, "a.pdf").endswith("/A/view"))
        self.assertEqual(drive.requests.post.call_count, 2)

    def test_oauth_recusado_nao_vaza_resposta(self):
        drive.requests.post.return_value = Resp(400, {"error": "invalid_grant", "detalhe": "refresh"})
        with self.assertRaises(drive.ErroDrive) as c:
            drive.Drive().publicar_pdf(self.pdf, "a.pdf")
        self.assertNotIn("invalid_grant", str(c.exception))

    def test_sondar_avisa_pasta_no_meu_drive_com_conta_de_servico(self):
        for k in ("GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET", "GDRIVE_OAUTH_REFRESH_TOKEN"):
            os.environ.pop(k, None)
        os.environ["GDRIVE_SERVICE_ACCOUNT_JSON"] = "{}"
        pasta = {"id": "PASTA1", "mimeType": "application/vnd.google-apps.folder",
                 "capabilities": {"canAddChildren": True}}
        d = drive.Drive()
        d._token = "tok"
        for resposta, esperado in (({**pasta}, "ATENÇÃO: a pasta está no Meu Drive"),
                                   ({**pasta, "driveId": "D1"}, "Drive compartilhado: OK")):
            self.usar(Google({("GET", "/files/PASTA1"): Resp(200, resposta)}))
            self.assertTrue(any(esperado in l for l in d.sondar()), esperado)


class FakeCakto:
    nome = "cakto"

    def __init__(self):
        self.recebido = None

    def configurada(self):
        return True

    def faltando(self):
        return []

    def buscar_por_nome(self, nome):
        return None

    def criar_produto(self, p, pdf, url_entrega=None):
        self.recebido = url_entrega
        ativo = bool(url_entrega)
        return {"id": "u1", "status": "active" if ativo else "waiting_config", "ativo": ativo,
                "link": "https://pay.cakto.com.br/ABC" if ativo else "", "existente": False}


class RegistradorComDrive(BaseDrive):
    def setUp(self):
        super().setUp()
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        cfg.PACOTES_DIR = os.path.join(self.tmp.name, "pacotes")
        self.cakto = FakeCakto()
        orig = plataformas.instanciar
        plataformas.instanciar = lambda nomes: [self.cakto]
        self.addCleanup(lambda: setattr(plataformas, "instanciar", orig))

    def _rodar(self):
        r = catalogo.adicionar(produto_bom(), "aprovado", "x")
        return r, registrador.registrar_produto(r["id"], dry_run=False)

    def test_com_drive_o_produto_nasce_ativo_e_fica_pronto(self):
        self.usar(Google({("GET", "/files"): Resp(200, {"files": []}),
                          ("POST", "upload/drive"): Resp(200, {"id": "ARQ9"}),
                          ("POST", "/permissions"): Resp(200, {})}))
        r, linhas = self._rodar()
        self.assertEqual(self.cakto.recebido, "https://drive.google.com/file/d/ARQ9/view")
        p = catalogo.obter(r["id"])
        self.assertEqual((p["status"], p["link_compra"]), ("pronto", "https://pay.cakto.com.br/ABC"))
        self.assertTrue(any("PDF hospedado" in l for l in linhas))

    def test_falha_do_drive_nao_derruba_o_fluxo(self):
        self.usar(Google({("GET", "/files"): Resp(200, {"files": []}),
                          ("POST", "upload/drive"): erro_google(403, "storageQuotaExceeded")}))
        r, linhas = self._rodar()
        self.assertIsNone(self.cakto.recebido)
        self.assertEqual(catalogo.obter(r["id"])["status"], "aguardando_cadastro")
        self.assertTrue(any("waiting_config" in l for l in linhas))

    def test_sem_drive_configurado_segue_como_antes(self):
        for k in VARS:
            os.environ.pop(k, None)
        r, linhas = self._rodar()
        self.assertIsNone(self.cakto.recebido)
        self.assertTrue(any("drive: não configurado" in l for l in linhas))
        self.assertEqual(catalogo.obter(r["id"])["status"], "aguardando_cadastro")

    def test_dry_run_nao_envia_nada_ao_drive(self):
        srv = Google({})
        self.usar(srv)
        r = catalogo.adicionar(produto_bom(), "aprovado", "x")
        registrador.registrar_produto(r["id"], dry_run=True)
        self.assertEqual(srv.chamadas, [])


class CaktoEntrega(unittest.TestCase):
    def setUp(self):
        for k in ("CAKTO_CLIENT_ID", "CAKTO_CLIENT_SECRET"):
            self.addCleanup(os.environ.pop, k, None)
        p = mock.patch.object(plataformas.time, "sleep")
        p.start()
        self.addCleanup(p.stop)

    def usar(self, srv):
        p = mock.patch.object(plataformas.requests, "request", srv)
        p.start()
        self.addCleanup(p.stop)

    def test_produto_existente_em_waiting_config_recebe_entrega_e_ativa(self):
        nome = produto_bom()["nome"]
        c, srv = cliente({
            ("GET", "/public_api/products/"): Resp(200, {"count": 1, "next": None, "results": [
                {"id": "u1", "name": nome}]}),
            ("GET", "/public_api/products/u1/"): [Resp(200, produto_api(nome, status="waiting_config", pid="u1")),
                                                  Resp(200, produto_api(nome, status="active", pid="u1"))],
            ("PUT", "/public_api/products/u1/"): Resp(200, {}),
        })
        self.usar(srv)
        r = c.criar_produto(produto_bom(), "x.pdf", "https://drive.google.com/file/d/A/view")
        put = next(ch for ch in srv.chamadas if ch[0] == "PUT")
        self.assertEqual(put[2]["json"], {"contentDeliveries": ["emailAccess"],
                                          "emailAccessLink": "https://drive.google.com/file/d/A/view",
                                          "status": "active"})
        self.assertTrue(r["ativo"] and r["existente"])
        self.assertEqual(r["link"], "https://pay.cakto.com.br/77BcHrY")

    def test_produto_ativo_ou_bloqueado_nao_e_alterado(self):
        nome = produto_bom()["nome"]
        for status in ("active", "blocked"):
            c, srv = cliente({
                ("GET", "/public_api/products/"): Resp(200, {"count": 1, "next": None, "results": [
                    {"id": "u1", "name": nome}]}),
                ("GET", "/public_api/products/u1/"): Resp(200, produto_api(nome, status=status, pid="u1"))})
            self.usar(srv)
            c.criar_produto(produto_bom(), "x.pdf", "https://drive.google.com/file/d/A/view")
            self.assertFalse(any(ch[0] == "PUT" for ch in srv.chamadas), status)


if __name__ == "__main__":
    unittest.main()

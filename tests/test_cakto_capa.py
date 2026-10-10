"""Capa do produto na Cakto: gerar, hospedar, enviar por `image` (URL; multipart como plano B) e só ativar depois."""
import io
import os
import tempfile
import unittest
from unittest import mock

from tests import stubs
stubs.instalar()

from fabrica_produtos import capa, catalogo, config_fabrica as cfg, plataformas, registrador  # noqa: E402
from tests.fixtures import produto_bom  # noqa: E402
from tests.test_cakto import Resp, cliente, produto_api  # noqa: E402

NOME = produto_bom()["nome"]


class Base(unittest.TestCase):
    def setUp(self):
        for k in ("CAKTO_CLIENT_ID", "CAKTO_CLIENT_SECRET", "CAKTO_EXIGE_IMAGEM"):
            self.addCleanup(os.environ.pop, k, None)
        p = mock.patch.object(plataformas.time, "sleep")
        p.start()
        self.addCleanup(p.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def usar(self, srv):
        p = mock.patch.object(plataformas.requests, "request", srv)
        p.start()
        self.addCleanup(p.stop)

    def rotas(self, put, get_final):
        return {("GET", "/public_api/products/"): Resp(200, {"results": []}),
                ("POST", "/public_api/products/"): Resp(201, produto_api(NOME, status="waiting_config", pid="u1")),
                ("PUT", "/public_api/products/u1/"): put,
                ("GET", "/public_api/products/u1/"): get_final}


class Capa(Base):
    def test_gera_png_16_9_com_cor_do_tema_e_titulo_sem_prefixo(self):
        from PIL import Image
        p = {"id": "p1", "nome": "Guia Prático de Receitas Fit e Marmitas"}
        arq = capa.gerar_capa(p, os.path.join(self.tmp.name, "p1.png"))
        img = Image.open(arq)
        self.assertEqual(img.size, (1280, 720))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(capa.titulo_curto(p), "Receitas Fit e Marmitas")
        self.assertEqual(capa._cor_e_selo(p)[1], "RECEITAS")
        self.assertEqual(capa._cor_e_selo({"nome": "Guia de Marketing Digital"})[1], "MARKETING")

    def test_produtos_diferentes_geram_capas_diferentes(self):
        a = capa.gerar_capa({"id": "a", "nome": "Guia de Receitas Fit"}, os.path.join(self.tmp.name, "a.png"))
        b = capa.gerar_capa({"id": "b", "nome": "Guia de Finanças Pessoais"}, os.path.join(self.tmp.name, "b.png"))
        self.assertNotEqual(open(a, "rb").read(), open(b, "rb").read())


class EnvioDaImagem(Base):
    def test_image_vai_por_url_e_so_depois_o_status_active(self):
        com = {**produto_api(NOME, pid="u1"), "image": "https://c/capa.png"}
        c, srv = cliente(self.rotas(Resp(200, {}), [Resp(200, com), Resp(200, com)]))
        self.usar(srv)
        r = c.finalizar("u1", ["https://c/capa.png"], None, {**produto_bom(), "preco": 8.9})
        puts = [kw["json"] for m, u, kw in srv.chamadas if m == "PUT"]
        self.assertEqual(puts, [{"name": NOME, "description": produto_bom()["descricao_oferta"], "price": "8.90",
                                 "image": "https://c/capa.png"}, {"status": "active"}])   # PUT com os dados obrigatórios
        self.assertEqual(r["imagem_erro"], "")
        self.assertTrue(r["ativo"])

    def test_tenta_a_proxima_url_se_a_primeira_for_recusada(self):
        com = {**produto_api(NOME, pid="u1"), "image": "https://b/capa.png"}
        puts = [Resp(400, {}, "image invalid"), Resp(200, {}), Resp(200, {})]
        c, srv = cliente(self.rotas(lambda kw: puts.pop(0), [Resp(200, com), Resp(200, com)]))
        self.usar(srv)
        self.assertEqual(c.enviar_imagem("u1", ["https://a/capa.png", "https://b/capa.png"]), "https://b/capa.png")

    def test_se_a_url_nao_pega_tenta_multipart_com_o_arquivo(self):
        arq = capa.gerar_capa({"id": "x", "nome": "Guia de Receitas"}, os.path.join(self.tmp.name, "x.png"))
        com = {**produto_api(NOME, pid="u1"), "image": "https://cdn/x.png"}
        vistos = []

        def put(kw):
            vistos.append(kw)
            return Resp(400, {}, "bad") if "json" in kw else Resp(200, {})
        c, srv = cliente(self.rotas(put, [Resp(200, com)]))
        self.usar(srv)
        self.assertEqual(c.enviar_imagem("u1", ["https://a/x.png"], arq), "multipart")
        self.assertIn("image", vistos[-1]["files"])
        self.assertEqual(vistos[-1]["files"]["image"][2], "image/png")

    def test_falha_loga_CAKTO_IMAGEM_ERROR_com_codigo_e_nao_ativa_quando_exige(self):
        os.environ["CAKTO_EXIGE_IMAGEM"] = "true"
        sem = produto_api(NOME, status="waiting_config", pid="u1")
        c, srv = cliente(self.rotas(Resp(403, {}, "forbidden"), [Resp(200, sem)]))
        self.usar(srv)
        with self.assertLogs("fabrica", "ERROR") as logs, mock.patch("builtins.print") as pr:
            r = c.finalizar("u1", ["https://a/x.png"], None)
        self.assertTrue(any("CAKTO_IMAGEM_ERROR" in m and "http=403" in m for m in logs.output))
        self.assertIn("CAKTO_IMAGEM_ERROR", pr.call_args[0][0])
        self.assertIn("HTTP 403", r["imagem_erro"])
        self.assertFalse(r["ativo"])
        self.assertFalse(any(kw.get("json") == {"status": "active"} for m, u, kw in srv.chamadas if m == "PUT"))

    def test_put_aceito_mas_sem_imagem_no_produto_conta_como_falha(self):
        sem = produto_api(NOME, status="waiting_config", pid="u1")
        c, srv = cliente(self.rotas(Resp(200, {}), [Resp(200, sem)]))
        self.usar(srv)
        with self.assertRaises(plataformas.ErroPlataforma):
            c.enviar_imagem("u1", ["https://a/x.png"])

    def test_padrao_nao_exige_imagem_e_ativa_mesmo_sem_capa(self):
        os.environ.pop("CAKTO_EXIGE_IMAGEM", None)
        ativo = produto_api(NOME, status="active", pid="u1")
        c, srv = cliente(self.rotas(lambda kw: Resp(403, {}, "x") if "image" in kw["json"] else Resp(200, {}),
                                    [Resp(200, ativo)]))
        self.usar(srv)
        with self.assertLogs("fabrica", "ERROR"):
            r = c.finalizar("u1", ["https://a/x.png"], None)
        self.assertTrue(r["ativo"])

    def test_sem_url_e_sem_arquivo_e_erro_claro(self):
        c, srv = cliente({})
        self.usar(srv)
        with self.assertRaises(plataformas.ErroPlataforma):
            c.enviar_imagem("u1", [], None)


class Reparo(Base):
    """`capas`: produtos que já estão na Cakto 'Sem imagem' (os 5 do dashboard) ganham capa e, se estavam esperando só
    por ela, são ativados."""

    def setUp(self):
        super().setUp()
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        r = catalogo.adicionar(produto_bom(), "aprovado", "x")
        catalogo.atualizar(r["id"], "ok", status="pronto", link_compra="https://pay.cakto.com.br/abc", plataforma="cakto")
        self.id = r["id"]
        os.environ["CAKTO_CLIENT_ID"], os.environ["CAKTO_CLIENT_SECRET"] = "a", "b"
        p = mock.patch.object(capa, "PASTA_PADRAO", self.tmp.name)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(registrador, "_acessivel", lambda u: True)
        p.start()
        self.addCleanup(p.stop)
        os.environ["GITHUB_REPOSITORY"] = "o/r"
        self.addCleanup(os.environ.pop, "GITHUB_REPOSITORY", None)

    def test_produto_sem_imagem_recebe_capa_pela_url_do_github(self):
        sem = produto_api(NOME, pid="u1")
        com = {**sem, "image": "https://raw/x.png"}
        c, srv = cliente({("GET", "/public_api/products/"): Resp(200, {"results": [{"id": "u1", "name": NOME}]}),
                          ("GET", "/public_api/products/u1/"): [Resp(200, sem), Resp(200, com)],
                          ("PUT", "/public_api/products/u1/"): Resp(200, {})})
        self.usar(srv)
        with mock.patch.object(plataformas, "instanciar", return_value=[c]):
            linhas = registrador.enviar_capas()
        put = next(kw["json"] for m, u, kw in srv.chamadas if m == "PUT")
        self.assertEqual(put, {"name": NOME, "description": produto_bom()["descricao_oferta"], "price": "7.00",
                               "image": f"https://raw.githubusercontent.com/o/r/main/docs/capas/{self.id}.png"})
        self.assertTrue(any("capa enviada" in l for l in linhas))
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, f"{self.id}.png")))

    def test_produto_que_ja_tem_imagem_e_pulado(self):
        com = {**produto_api(NOME, pid="u1"), "image": "https://x/y.png"}
        c, srv = cliente({("GET", "/public_api/products/"): Resp(200, {"results": [{"id": "u1", "name": NOME}]}),
                          ("GET", "/public_api/products/u1/"): Resp(200, com)})
        self.usar(srv)
        with mock.patch.object(plataformas, "instanciar", return_value=[c]):
            linhas = registrador.enviar_capas()
        self.assertTrue(any("já tem imagem" in l for l in linhas))
        self.assertFalse(any(m == "PUT" for m, u, kw in srv.chamadas))

    def test_waiting_config_com_entrega_e_ativado_depois_da_capa(self):
        sem = {**produto_api(NOME, status="waiting_config", pid="u1"), "emailAccessLink": "https://drive/x"}
        com = {**sem, "image": "https://raw/x.png"}
        ativo = {**com, "status": "active"}
        c, srv = cliente({("GET", "/public_api/products/"): Resp(200, {"results": [{"id": "u1", "name": NOME}]}),
                          ("GET", "/public_api/products/u1/"): [Resp(200, sem), Resp(200, com), Resp(200, ativo)],
                          ("PUT", "/public_api/products/u1/"): Resp(200, {})})
        self.usar(srv)
        with mock.patch.object(plataformas, "instanciar", return_value=[c]):
            linhas = registrador.enviar_capas()
        puts = [kw["json"] for m, u, kw in srv.chamadas if m == "PUT"]
        self.assertEqual(puts[-1], {"status": "active"})
        self.assertTrue(any("ativado" in l for l in linhas))

    def test_falha_vira_linha_CAKTO_IMAGEM_ERROR_sem_derrubar(self):
        sem = produto_api(NOME, pid="u1")
        c, srv = cliente({("GET", "/public_api/products/"): Resp(200, {"results": [{"id": "u1", "name": NOME}]}),
                          ("GET", "/public_api/products/u1/"): Resp(200, sem),
                          ("PUT", "/public_api/products/u1/"): Resp(422, {}, "image: invalid")})
        self.usar(srv)
        with mock.patch.object(plataformas, "instanciar", return_value=[c]), mock.patch("builtins.print"):
            linhas = registrador.enviar_capas()
        self.assertTrue(any("CAKTO_IMAGEM_ERROR" in l and "http=422" in l for l in linhas))


class UrlAcessivel(unittest.TestCase):
    def test_so_aceita_200_com_content_type_de_imagem(self):
        def resp(status, tipo):
            return mock.Mock(status_code=status, headers={"Content-Type": tipo}, close=lambda: None)
        with mock.patch("requests.get", return_value=resp(200, "image/png")):
            self.assertTrue(registrador._acessivel("https://x/a.png"))
        with mock.patch("requests.get", return_value=resp(404, "text/html")):
            self.assertFalse(registrador._acessivel("https://x/a.png"))
        with mock.patch("requests.get", return_value=resp(200, "text/html")):
            self.assertFalse(registrador._acessivel("https://x/a.png"))

    def test_url_do_github_fora_do_ar_nao_vira_candidata(self):
        linhas = []
        with mock.patch.object(registrador, "_acessivel", lambda u: False), mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "o/r"}):
            self.assertEqual(registrador.urls_da_capa({"id": "p1"}, "/tmp/x.png", linhas), [])
        self.assertTrue(linhas)

    def test_nunca_usa_o_drive_para_imagem_e_o_repo_padrao_e_o_do_projeto(self):
        with mock.patch.object(registrador, "_acessivel", lambda u: True), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_REPOSITORY", None)
            os.environ.pop("GITHUB_REF_NAME", None)
            urls = registrador.urls_da_capa({"id": "p20261005-1"}, None, [])
        self.assertEqual(urls, ["https://raw.githubusercontent.com/fabricadeprodutosdigitais/fabrica-de-produtos-digitais/"
                                "main/docs/capas/p20261005-1.png"])
        self.assertFalse(hasattr(__import__("fabrica_produtos.drive", fromlist=["Drive"]).Drive, "publicar_imagem"))


class Workflow(unittest.TestCase):
    def test_produto_yml_tem_passo_e_acao_capas(self):
        t = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".github/workflows/produto.yml"), encoding="utf-8").read()
        self.assertIn("python -m fabrica_produtos capas", t)
        self.assertIn("reels | capas", t)


if __name__ == "__main__":
    unittest.main()

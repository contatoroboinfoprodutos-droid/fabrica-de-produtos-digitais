"""Integração dos robôs de anúncio com o catálogo (CrewAI simulado)."""
import importlib
import os
import sys
import tempfile
import unittest

from tests import stubs
stubs.instalar()

from fabrica_produtos import catalogo, config_fabrica as cfg  # noqa: E402
from tests.fixtures import produto_bom  # noqa: E402

LINK = "https://pay.exemplo.com.br/abc123"


def carregar_lowticket(dry_run: str):
    os.environ["LT_DRY_RUN"] = dry_run
    os.environ.setdefault("GEMINI_API_KEY", "chave-falsa-de-teste")  # agents.py exige alguma chave
    for m in [m for m in sys.modules if m.startswith("infoprodutos_lowticket")]:
        del sys.modules[m]
    cfg_lt = importlib.import_module("infoprodutos_lowticket.config_lt")
    tools = importlib.import_module("infoprodutos_lowticket.tools_lt")
    return cfg_lt, tools


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        self.addCleanup(lambda: os.environ.pop("LT_DRY_RUN", None))

    def liberar(self):
        r = catalogo.adicionar(produto_bom(), "aprovado", "x")
        catalogo.atualizar(r["id"], "ok", status="pronto", link_compra=LINK, plataforma="kiwify")


class Lowticket(Base):
    def test_sem_produto_pronto_oferta_e_bloqueada_em_modo_real(self):
        cfg_lt, tools = carregar_lowticket("false")
        self.assertIsNone(cfg_lt.PRODUTO)
        r = tools.lt_publicar_meta("post_tarde.png", "Compre o guia por R$ 7,00 https://SEU-LINK-DE-CHECKOUT")
        self.assertTrue(r.startswith("ERRO"), r)

    def test_dry_run_avisa_e_corrige(self):
        self.liberar()
        cfg_lt, tools = carregar_lowticket("true")
        self.assertEqual(cfg_lt.OFFER_LINK, LINK)
        self.assertEqual(cfg_lt.OFFER_PRICE, "R$ 7,00")
        r = tools.lt_publicar_meta("post_tarde.png",
                                   "**Guia** por R$ 27,00 com a primeira venda! https://SEU-LINK-DE-CHECKOUT")
        self.assertIn("[DRY_RUN]", r)
        self.assertIn(LINK, r)
        legenda = r.split("Legenda:\n")[1].split("\n[TRAVAS]")[0]  # a nota de auditoria cita o termo removido
        self.assertNotIn("SEU-LINK", legenda)
        self.assertNotIn("primeira venda", legenda)
        self.assertIn("[TRAVAS]", r)
        self.assertNotIn("BLOQUEADA", r)

    def test_modo_real_com_produto_pronto_passa_pelas_travas_e_para_na_meta(self):
        self.liberar()
        _, tools = carregar_lowticket("false")
        r = tools.lt_publicar_meta("post_tarde.png", f"Guia de rotina por R$ 7,00. Acesse {LINK}")
        self.assertIn("META_LONG_LIVED_TOKEN", r)  # passou nas travas; só falta a credencial da Meta

    def test_post_de_valor_nao_exige_produto(self):
        _, tools = carregar_lowticket("false")
        r = tools.lt_publicar_meta("post_manha.png", "Uma dica prática: organize o dia em blocos pequenos.")
        self.assertNotIn("bloqueada", r.lower())
        r2 = tools.lt_publicar_meta("post_manha.png", "Dica para a sua primeira venda rápida.")
        self.assertNotIn("primeira venda", r2)  # termo removido antes de qualquer envio

    def test_card_nao_estampa_termo_proibido(self):
        self.liberar()
        cfg_lt, tools = carregar_lowticket("true")
        cfg_lt.OUTPUT_DIR = os.path.join(self.tmp.name, "out")
        tools.cfg.OUTPUT_DIR = cfg_lt.OUTPUT_DIR
        h, s = tools._texto_card_seguro("Sua primeira venda garantida", "Método testado", "OFERTA")
        self.assertEqual(h, "Guia Prático de Rotina em 7 Dias")
        # a subline tinha termo proibido, foi removida e cai na promessa do catálogo
        self.assertEqual(s, produto_bom()["promessa"])


class Principal(Base):
    def setUp(self):
        super().setUp()
        for m in ("tools.crewai_meta_tools", "tools"):
            sys.modules.pop(m, None)
        self.conf = stubs.instalar_config(dry_run=False)
        sys.modules.pop("tools.meta_graph_api", None)
        import types
        api = types.ModuleType("tools.meta_graph_api")
        api.MetaGraphAPI = type("MetaGraphAPI", (), {})
        api.MetaGraphAPIError = RuntimeError
        sys.modules["tools.meta_graph_api"] = api
        self.mod = importlib.import_module("tools.crewai_meta_tools")

    def test_sem_produto_pronto_nao_publica(self):
        r = self.mod.PublishToFacebookTool.model_construct()._run(message="Compre agora", image_url="https://x.com/a.jpg")
        self.assertTrue(r.startswith("ERRO"), r)
        r = self.mod.PublishToInstagramTool.model_construct()._run(image_url="https://x.com/a.jpg", caption="Compre")
        self.assertTrue(r.startswith("ERRO"), r)

    def test_dry_run_mostra_texto_corrigido(self):
        self.liberar()
        self.conf.DRY = True
        r = self.mod.PublishToFacebookTool.model_construct()._run(
            message="Guia por R$ 9,00 com lucro rápido! Link na bio", image_url="https://x.com/a.jpg")
        self.assertIn("[DRY_RUN]", r)
        self.assertIn("R$ 7,00", r)
        mensagem = r.split("message=")[1].split("[TRAVAS]")[0]  # a nota de auditoria cita o termo removido
        self.assertNotIn("lucro", mensagem)


if __name__ == "__main__":
    unittest.main()

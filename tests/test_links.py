"""Link de compra e aviso de link na bio em todo post; produto fixo para o link da bio não mudar."""
import os
import tempfile
import unittest
from unittest import mock

from tests import stubs
stubs.instalar()

from fabrica_produtos import catalogo, config_fabrica as cfg, travas  # noqa: E402
from tests.fixtures import produto_bom, produto_pronto  # noqa: E402
from tests.test_integracao import carregar_lowticket  # noqa: E402

LINK = "https://pay.cakto.com.br/gjfmbn3"
OUTRO = "https://pay.cakto.com.br/v93eacj"
TEXTO = "Quantas vezes você é interrompido e perde o foco? O guia ajuda a organizar o seu tempo, com passos práticos."


class GarantirLink(unittest.TestCase):
    def setUp(self):
        self.p = produto_pronto(link=LINK)

    def test_acrescenta_link_e_aviso_da_bio(self):
        t, mexeu = travas.garantir_link(self.p, TEXTO)
        self.assertTrue(mexeu)
        self.assertIn(f"Link de compra: {LINK}", t)
        self.assertTrue(t.endswith("Link também na bio."))

    def test_entra_antes_das_hashtags_finais(self):
        t, _ = travas.garantir_link(self.p, TEXTO + "\n\n#Produtividade #Foco #Rotina #GestãoDeTempo")
        self.assertLess(t.index(LINK), t.index("#Produtividade"))
        self.assertTrue(t.rstrip().endswith("#GestãoDeTempo"))

    def test_nao_duplica(self):
        t1, _ = travas.garantir_link(self.p, TEXTO)
        t2, mexeu = travas.garantir_link(self.p, t1)
        self.assertEqual((t1, mexeu), (t2, False))
        self.assertEqual(t2.count(LINK), 1)

    def test_link_ja_no_texto_so_acrescenta_o_aviso_da_bio(self):
        t, mexeu = travas.garantir_link(self.p, f"{TEXTO} Adquira por R$ 7,00. {LINK}")
        self.assertTrue(mexeu)
        self.assertEqual(t.count(LINK), 1)
        self.assertIn("Link também na bio.", t)

    def test_bio_ja_citada_nao_repete_o_aviso(self):
        t, _ = travas.garantir_link(self.p, f"{TEXTO} Link também na bio")
        self.assertEqual(t.lower().count("na bio"), 1)
        self.assertIn(LINK, t)

    def test_sem_produto_pronto_nao_mexe(self):
        self.assertEqual(travas.garantir_link(None, TEXTO), (TEXTO, False))
        p = dict(self.p, status="aguardando_cadastro")
        self.assertEqual(travas.garantir_link(p, TEXTO), (TEXTO, False))
        self.assertEqual(travas.garantir_link(dict(self.p, link_compra=""), TEXTO), (TEXTO, False))


class PrepararLegendaComLink(unittest.TestCase):
    def test_todos_os_tipos_levam_o_link_e_passam_na_verificacao(self):
        p = produto_pronto(link=LINK)
        for tipo in ("VALOR", "VITRINE", "OFERTA"):
            t, acoes, problemas = travas.preparar_legenda_com_link(p, TEXTO, tipo)
            self.assertIn(LINK, t, tipo)
            self.assertEqual(problemas, [], (tipo, problemas))

    def test_termo_proibido_continua_sendo_removido(self):
        p = produto_pronto(link=LINK)
        t, _, problemas = travas.preparar_legenda_com_link(p, TEXTO + " Faça a sua primeira venda hoje.", "VITRINE")
        self.assertNotIn("primeira venda", t)
        self.assertEqual(problemas, [])

    def test_link_errado_do_modelo_vira_o_do_catalogo(self):
        p = produto_pronto(link=LINK)
        t, _, problemas = travas.preparar_legenda_com_link(p, TEXTO + " Compre em https://exemplo.com/falso", "OFERTA")
        self.assertNotIn("exemplo.com", t)
        self.assertEqual(problemas, [])

    def test_sem_produto_post_de_valor_continua_valendo(self):
        t, acoes, problemas = travas.preparar_legenda_com_link(None, TEXTO, "VALOR")
        self.assertNotIn("http", t)
        self.assertEqual(problemas, [])


class ProdutoFixo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        self.addCleanup(os.environ.pop, "FABRICA_PRODUTO_FIXO", None)
        os.environ.pop("FABRICA_PRODUTO_FIXO", None)
        self.a = catalogo.adicionar(produto_bom("Guia A"), "aprovado", "x")
        catalogo.atualizar(self.a["id"], "ok", status="pronto", link_compra=LINK, plataforma="cakto")
        self.b = catalogo.adicionar(produto_bom("Guia B"), "aprovado", "x")
        catalogo.atualizar(self.b["id"], "ok", status="pronto", link_compra=OUTRO, plataforma="cakto")

    def test_sem_fixo_vale_o_mais_recente(self):
        self.assertEqual(catalogo.produto_ativo()["link_compra"], OUTRO)

    def test_fixo_mantem_o_mesmo_produto_e_link(self):
        os.environ["FABRICA_PRODUTO_FIXO"] = self.a["id"]
        self.assertEqual(catalogo.produto_ativo()["link_compra"], LINK)
        c = catalogo.adicionar(produto_bom("Guia C"), "aprovado", "x")  # um produto novo não muda o anunciado
        catalogo.atualizar(c["id"], "ok", status="pronto", link_compra="https://pay.cakto.com.br/zzz", plataforma="cakto")
        self.assertEqual(catalogo.produto_ativo()["id"], self.a["id"])

    def test_fixo_invalido_cai_no_mais_recente_com_aviso(self):
        os.environ["FABRICA_PRODUTO_FIXO"] = "p00000000-9"
        with self.assertLogs("fabrica", level="WARNING"):
            self.assertEqual(catalogo.produto_ativo()["link_compra"], OUTRO)

    def test_fixo_ainda_nao_pronto_cai_no_mais_recente(self):
        c = catalogo.adicionar(produto_bom("Guia C"), "aprovado", "x")
        os.environ["FABRICA_PRODUTO_FIXO"] = c["id"]
        with self.assertLogs("fabrica", level="WARNING"):
            self.assertEqual(catalogo.produto_ativo()["link_compra"], OUTRO)


class PostsReais(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        os.environ.pop("FABRICA_PRODUTO_FIXO", None)
        r = catalogo.adicionar(produto_bom(), "aprovado", "x")
        catalogo.atualizar(r["id"], "ok", status="pronto", link_compra=LINK, plataforma="cakto")
        self.addCleanup(lambda: os.environ.pop("LT_DRY_RUN", None))

    def test_low_ticket_post_de_valor_mostra_o_link_na_legenda(self):
        _, tools = carregar_lowticket("true")
        r = tools.lt_publicar_meta("post_manha.png", "Uma dica prática: organize o dia em blocos pequenos e revise.")
        self.assertIn(LINK, r)
        self.assertIn("Link também na bio", r)
        self.assertNotIn("BLOQUEADA", r)

    def test_robo_principal_instagram_envia_legenda_com_link(self):
        stubs.instalar_config(dry_run=False)
        import importlib
        import sys
        sys.modules.pop("tools.crewai_meta_tools", None)
        mod = importlib.import_module("tools.crewai_meta_tools")
        api = mock.MagicMock()
        api.publish_instagram_post.return_value = mock.Mock(post_id="IG1")
        with mock.patch.object(mod, "MetaGraphAPI", return_value=api):
            mod.PublishToInstagramTool()._run(image_url="https://img/x.jpg", caption=TEXTO + "\n\n#Foco #Rotina #Produtividade")
        enviada = api.publish_instagram_post.call_args.kwargs["caption"]
        self.assertIn(LINK, enviada)
        self.assertIn("Link também na bio", enviada)
        self.assertLess(enviada.index(LINK), enviada.index("#Foco"))


if __name__ == "__main__":
    unittest.main()

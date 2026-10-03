import os
import tempfile
import unittest

from fabrica_produtos import catalogo, registrador, config_fabrica as cfg
from tests.fixtures import produto_bom

LINK = "https://pay.exemplo.com.br/abc123"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        cfg.PACOTES_DIR = os.path.join(self.tmp.name, "pacotes")


class Catalogo(Base):
    def test_ciclo_e_produto_ativo(self):
        self.assertIsNone(catalogo.produto_ativo())
        r = catalogo.adicionar(produto_bom(), "aprovado", "teste")
        self.assertEqual(r["preco_texto"], "R$ 7,00")
        self.assertIsNone(catalogo.produto_ativo())  # aprovado ainda não é anunciável
        catalogo.atualizar(r["id"], "liberado", status="pronto", link_compra="https://SEU-LINK-DE-CHECKOUT")
        self.assertIsNone(catalogo.produto_ativo())  # pronto com link de exemplo também não
        catalogo.atualizar(r["id"], "link certo", link_compra=LINK)
        self.assertEqual(catalogo.produto_ativo()["id"], r["id"])

    def test_ids_unicos_e_nome_repetido(self):
        a = catalogo.adicionar(produto_bom("Guia A"), "aprovado", "x")
        b = catalogo.adicionar(produto_bom("Guia B"), "aprovado", "x")
        self.assertNotEqual(a["id"], b["id"])
        self.assertTrue(catalogo.nome_ja_existe("guia   a"))
        self.assertTrue(catalogo.nome_ja_existe("GUIA Á"))
        self.assertFalse(catalogo.nome_ja_existe("Guia C"))

    def test_limite_diario_ignora_reprovados(self):
        catalogo.adicionar(produto_bom("R"), "reprovado", "x")
        self.assertEqual(catalogo.criados_hoje(), 0)
        catalogo.adicionar(produto_bom("A"), "aprovado", "x")
        self.assertEqual(catalogo.criados_hoje(), 1)

    def test_arquivo_sempre_json_valido(self):
        catalogo.adicionar(produto_bom(), "aprovado", "x")
        import json
        with open(cfg.CATALOGO_PATH, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["produtos"]), 1)


class FakePlat:
    def __init__(self, nome, achado=None, erro=None, configurada=True):
        self.nome, self._achado, self._erro, self._conf = nome, achado, erro, configurada

    def configurada(self):
        return self._conf

    def faltando(self):
        return [] if self._conf else ["X"]

    def buscar_por_nome(self, nome):
        from fabrica_produtos import plataformas
        if self._erro:
            raise plataformas.ErroPlataforma(self._erro)
        return self._achado

    def criar_produto(self, p, pdf):
        from fabrica_produtos import plataformas
        raise plataformas.NaoSuportado(f"{self.nome}: criação não confirmada")


class Registrador(Base):
    def _plats(self, *fakes):
        from fabrica_produtos import plataformas
        self._orig = plataformas.instanciar
        plataformas.instanciar = lambda nomes: list(fakes)
        self.addCleanup(lambda: setattr(plataformas, "instanciar", self._orig))

    def test_pacote_e_aguardando_cadastro(self):
        self._plats(FakePlat("plat_a"), FakePlat("plat_b"))
        r = catalogo.adicionar(produto_bom(), "aprovado", "x")
        linhas = registrador.registrar_produto(r["id"], dry_run=False)
        p = catalogo.obter(r["id"])
        self.assertEqual(p["status"], "aguardando_cadastro")
        pasta = registrador.pacote_dir(p)
        self.assertTrue(os.path.getsize(os.path.join(pasta, "ficha_cadastro.md")) > 100)
        pdfs = [f for f in os.listdir(pasta) if f.endswith(".pdf")]
        self.assertEqual(len(pdfs), 1)
        with open(os.path.join(pasta, pdfs[0]), "rb") as f:
            self.assertEqual(f.read(4), b"%PDF")
        self.assertTrue(any("não confirmada" in l for l in linhas))

    def test_verificar_libera_quando_acha_com_link(self):
        r = catalogo.adicionar(produto_bom(), "aguardando_cadastro", "x")
        self._plats(FakePlat("plat_a", achado={"id": "1", "nome": r["nome"], "link": LINK, "ativo": True}))
        registrador.verificar_links()
        p = catalogo.obter(r["id"])
        self.assertEqual((p["status"], p["link_compra"], p["plataforma"]), ("pronto", LINK, "plat_a"))

    def test_verificar_nao_libera_sem_link_nem_com_erro(self):
        r = catalogo.adicionar(produto_bom(), "aguardando_cadastro", "x")
        self._plats(FakePlat("plat_a", achado={"id": "1", "nome": r["nome"], "link": "", "ativo": True}),
                    FakePlat("plat_b", erro="HTTP 401"))
        linhas = registrador.verificar_links()
        self.assertEqual(catalogo.obter(r["id"])["status"], "aguardando_cadastro")
        self.assertTrue(any("definir-link" in l for l in linhas))
        self.assertTrue(any("não consegui consultar" in l for l in linhas))

    def test_erro_em_uma_plataforma_nao_barra_a_outra(self):
        r = catalogo.adicionar(produto_bom(), "aguardando_cadastro", "x")
        self._plats(FakePlat("plat_a", erro="HTTP 500"),
                    FakePlat("plat_b", achado={"id": "9", "nome": r["nome"], "link": LINK, "ativo": True}))
        registrador.verificar_links()
        self.assertEqual(catalogo.obter(r["id"])["plataforma"], "plat_b")

    def test_definir_link(self):
        r = catalogo.adicionar(produto_bom(), "aguardando_cadastro", "x")
        with self.assertRaises(ValueError):
            registrador.definir_link(r["id"], "https://SEU-LINK-DE-CHECKOUT")
        with self.assertRaises(ValueError):
            registrador.definir_link(r["id"], "http://inseguro.com/x")
        registrador.definir_link(r["id"], LINK, "plat_b")
        self.assertEqual(catalogo.produto_ativo()["link_compra"], LINK)

    def test_nao_registra_produto_reprovado(self):
        r = catalogo.adicionar(produto_bom(), "reprovado", "x")
        linhas = registrador.registrar_produto(r["id"], dry_run=True)
        self.assertEqual(catalogo.obter(r["id"])["status"], "reprovado")
        self.assertIn("nada a registrar", linhas[0])


if __name__ == "__main__":
    unittest.main()

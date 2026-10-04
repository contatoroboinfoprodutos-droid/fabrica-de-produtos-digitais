"""Identidade visual (perfil e capa), nome da marca e interruptores que aceitam Secrets."""
import os
import tempfile
import unittest

from PIL import Image

from tests import stubs
stubs.instalar()

from fabrica_produtos import config_fabrica  # noqa: E402
from tools import gerar_capa, gerar_perfil  # noqa: E402
from tests.test_integracao import carregar_lowticket  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Iniciais(unittest.TestCase):
    def test_iniciais_ignoram_ligacoes(self):
        self.assertEqual(gerar_perfil.iniciais_da_marca("Fábrica de Produtos Digitais"), "FPD")
        self.assertEqual(gerar_perfil.iniciais_da_marca("Digital Rápido"), "DR")
        self.assertEqual(gerar_perfil.iniciais_da_marca("  casa da   rotina e foco "), "CRF")
        self.assertEqual(gerar_perfil.iniciais_da_marca("Uma Marca Com Nome Longo"), "UMC")
        self.assertEqual(gerar_perfil.iniciais_da_marca(""), "?")


class Imagens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_perfil_quadrado_1080(self):
        caminho = gerar_perfil.gerar(os.path.join(self.tmp.name, "p.png"), "FPD")
        self.assertEqual(Image.open(caminho).size, (1080, 1080))

    def test_perfil_cantos_ficam_vazios_para_o_recorte_redondo(self):
        im = Image.open(gerar_perfil.gerar(os.path.join(self.tmp.name, "p.png"), "FPD")).convert("RGB")
        for xy in ((5, 5), (1074, 5), (5, 1074), (1074, 1074)):
            self.assertEqual(im.getpixel(xy), gerar_perfil.AZUL)

    def test_capa_tamanho_e_canto_da_foto_de_perfil_sem_texto(self):
        im = Image.open(gerar_capa.gerar(os.path.join(self.tmp.name, "c.png"), "Fábrica de Produtos Digitais"))
        self.assertEqual(im.size, (1640, 856))
        im = im.convert("RGB")
        # canto inferior esquerdo: no computador a foto de perfil cobre essa área, então nada de texto ali
        for x in range(40, 380, 4):
            for y in range(560, 740, 4):
                r, g, b = im.getpixel((x, y))
                self.assertFalse(r > 200 and g > 150, f"texto/cor forte em {(x, y)}")

    def test_capa_nome_longo_cabe_na_zona_segura(self):
        im = Image.open(gerar_capa.gerar(os.path.join(self.tmp.name, "c.png"),
                                         "Fábrica de Produtos Digitais e Guias Práticos do Dia a Dia")).convert("RGB")
        brancos = [x for x in range(im.width) for y in range(250, 480, 6) if im.getpixel((x, y)) == (255, 255, 255)]
        self.assertTrue(brancos)
        self.assertGreaterEqual(min(brancos), 60)             # não passa do recorte do celular (esquerda)
        self.assertLessEqual(max(brancos), 1640 - 60)         # nem da direita


class Marca(unittest.TestCase):
    def test_padrao_e_o_nome_real_da_pagina(self):
        if os.getenv("LT_BRAND_NAME"):
            self.skipTest("LT_BRAND_NAME definido no ambiente")
        self.assertEqual(config_fabrica.MARCA, "Fábrica de Produtos Digitais")

    def test_sem_handle_o_cartao_usa_o_nome_da_marca(self):
        if os.getenv("LT_BRAND_HANDLE"):
            self.skipTest("LT_BRAND_HANDLE definido no ambiente")
        cfg_lt, tools = carregar_lowticket("true")
        self.assertEqual(cfg_lt.BRAND_HANDLE, "")
        self.assertEqual(cfg_lt.BRAND_NAME, "Fábrica de Produtos Digitais")
        with tempfile.TemporaryDirectory() as d:
            cfg_lt.OUTPUT_DIR = d
            for nome in ("post_manha.png", "post_tarde.png"):
                self.assertIn("Imagem salva", tools.lt_render_card(nome, "Organize o dia em blocos", "Passo a passo"))


class InterruptoresAceitamSecrets(unittest.TestCase):
    def test_workflows_leem_variables_e_secrets(self):
        casos = {"produto.yml": ("FABRICA_DRY_RUN", "FABRICA_PAUSADA"), "lowticket.yml": ("LT_DRY_RUN",)}
        for arq, nomes in casos.items():
            with open(os.path.join(RAIZ, ".github", "workflows", arq), encoding="utf-8") as f:
                texto = f.read()
            for n in nomes:
                self.assertIn(f"vars.{n} || secrets.{n}", texto, f"{arq}: {n}")


if __name__ == "__main__":
    unittest.main()

"""Preço por nível: fixo em código, com o conteúdo que cada nível promete."""
import json
import os
import tempfile
import unittest

from tests import stubs
stubs.instalar()

from fabrica_produtos import catalogo, config_fabrica as cfg, fabrica, travas  # noqa: E402
from tests.fixtures import capitulo, json_do_produto, produto_bom  # noqa: E402

OK = json.dumps({"problemas_graves": [], "ajustes": []})


class Executor:
    def __init__(self, *r):
        self.r, self.prompts = list(r), []

    def __call__(self, papel, descricao, saida, evitar):
        self.prompts.append(descricao)
        return self.r.pop(0), "gemini"


def grande(palavras_por_cap, **kw):
    p = produto_bom(preco=1.0, **kw)
    p["capitulos"] = [capitulo(f"Capítulo {i}", repeticoes=palavras_por_cap // 7 + 1) for i in range(1, 6)]
    p["conteudos"] = [f"Item {i}" for i in range(1, 6)]
    return p


class Niveis(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.antigo = cfg.CATALOGO_PATH
        cfg.CATALOGO_PATH = os.path.join(self.d, "c.json")

    def tearDown(self):
        cfg.CATALOGO_PATH = self.antigo

    def test_rodizio_e_precos(self):
        self.assertEqual([fabrica.tipo_da_rodada(n) for n in range(6)],
                         ["guia", "guia", "pacote", "guia", "pacote", "combo"])
        self.assertEqual(cfg.TIPOS, {"guia": 8.90, "pacote": 19.90, "combo": 27.90})

    def test_tipo_desligado_cai_para_guia(self):
        antigo = cfg.TIPOS_ATIVOS
        cfg.TIPOS_ATIVOS = ["guia"]
        try:
            self.assertEqual({fabrica.tipo_da_rodada(n) for n in range(12)}, {"guia"})
        finally:
            cfg.TIPOS_ATIVOS = antigo

    def test_prompt_pede_preco_e_volume_do_nivel(self):
        g = fabrica.prompt_criador("x", [], None, None, "guia")
        c = fabrica.prompt_criador("x", [], None, None, "combo")
        self.assertIn("27.90", c)
        self.assertIn("Combo premium", c)
        self.assertIn("pelo menos 2750 palavras", c)
        self.assertIn("pelo menos 750 palavras", g)
        self.assertIn("8.90", g)

    def test_preco_e_tipo_vem_do_codigo_nao_da_ia(self):
        ex = Executor(json_do_produto(produto_bom(preco=9.0, tipo="qualquer")), OK)
        res = fabrica.fabricar("Rotina", executor=ex, tipo="guia")
        self.assertEqual((res["produto"]["preco"], res["produto"]["tipo"]), (8.90, "Guia"))

    def test_combo_curto_e_reprovado_e_combo_completo_passa(self):
        # 4 capítulos curtos com preço de combo: as travas exigem o volume do nível
        curto = Executor(*[json_do_produto(produto_bom())] * 3, *[OK] * 6)
        res = fabrica.fabricar("Rotina", executor=curto, tipo="combo", max_rodadas=1)
        self.assertEqual(res["status"], "reprovado")
        self.assertIn("mínimo 2200", res["motivo"])
        p = grande(480)
        self.assertEqual([x for x in travas.verificar_produto({**p, "preco": 27.90}) if "curto" in x], [])

    def test_catalogo_guarda_preco_texto_do_nivel(self):
        ex = Executor(json_do_produto(produto_bom()), OK)
        res = fabrica.criar_e_guardar("Rotina", executor=ex)
        self.assertEqual(res["registro"]["preco_texto"], "R$ 8,90")
        self.assertEqual(res["registro"]["tipo"], "Guia")

    def test_nome_precisa_ter_menos_de_60(self):
        self.assertTrue(any("60" in x for x in travas.verificar_produto(produto_bom(nome="x" * 60))))
        self.assertFalse(any("60" in x for x in travas.verificar_produto(produto_bom(nome="x" * 59))))


if __name__ == "__main__":
    unittest.main()

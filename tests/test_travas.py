import unittest

from fabrica_produtos import travas
from tests.fixtures import capitulo, produto_bom, produto_pronto

LINK = "https://pay.exemplo.com.br/abc123"


class TermosProibidos(unittest.TestCase):
    def test_pega_variacoes(self):
        for texto in ["Sua PRIMEIRA venda chegou", "#primeiravenda", "Método testado e aprovado",
                      "ganho garantido", "É lucrativo", "#lucro", "Resultados rápidos", "Isso cura tudo",
                      "Fique rico", "sem esforço", "método comprovado", "100% garantido"]:
            self.assertTrue(travas.encontrar_termos(texto), texto)

    def test_nao_pega_texto_normal(self):
        for texto in ["Guia de organização financeira", "garantia de 7 dias", "curso rápido", "Ela procura um guia",
                      "Revise o resultado da semana", "primeiro passo"]:
            self.assertEqual(travas.encontrar_termos(texto), [], texto)

    def test_sanear_remove_so_o_que_precisa(self):
        entrada = "Aprenda a organizar o dia. Você terá a primeira venda rápido! Revise toda semana.\n#rotina #lucro"
        saida = travas.sanear_texto(entrada)
        self.assertIn("Aprenda a organizar o dia.", saida)
        self.assertIn("Revise toda semana.", saida)
        self.assertIn("#rotina", saida)
        self.assertEqual(travas.encontrar_termos(saida), [])


class Link(unittest.TestCase):
    def test_link_ok(self):
        self.assertTrue(travas.link_ok(LINK))
        for ruim in ["", "http://x.com/a", "https://SEU-LINK-DE-CHECKOUT", "texto solto", "https://semponto"]:
            self.assertFalse(travas.link_ok(ruim), ruim)


class Produto(unittest.TestCase):
    def test_produto_bom_passa(self):
        self.assertEqual(travas.verificar_produto(produto_bom()), [])

    def test_preco_fora_da_faixa(self):
        self.assertTrue(any("preço" in p for p in travas.verificar_produto(produto_bom(preco=47))))

    def test_conteudo_curto(self):
        p = produto_bom(capitulos=[capitulo(f"C{i}", 1) for i in range(3)])
        self.assertTrue(any("curto demais" in x for x in travas.verificar_produto(p)))

    def test_poucos_capitulos(self):
        p = produto_bom(capitulos=[capitulo("so um", 60)])
        self.assertTrue(any("capítulos" in x for x in travas.verificar_produto(p)))

    def test_termo_proibido_em_qualquer_campo(self):
        p = produto_bom(promessa="Faça a sua primeira venda em 7 dias")
        self.assertTrue(any("promessa" in x for x in travas.verificar_produto(p)))
        p = produto_bom()
        p["capitulos"][1]["texto"] += " Método testado por muita gente."
        self.assertTrue(any("capitulos[1].texto" in x for x in travas.verificar_produto(p)))

    def test_sanear_produto_remove_e_passa(self):
        p = produto_bom(promessa="Organize a rotina. Garanta a primeira venda rápido.")
        p["capitulos"][0]["texto"] += " Este método é testado."
        novo, acoes = travas.sanear_produto(p)
        self.assertTrue(acoes)
        self.assertEqual(travas.verificar_produto(novo), [])
        self.assertIn("Organize a rotina.", novo["promessa"])
        self.assertIn("primeira venda", p["promessa"])  # o original não é alterado

    def test_nome_com_termo_nao_e_saneado(self):
        novo, _ = travas.sanear_produto(produto_bom(nome="Primeira venda garantida"))
        self.assertTrue(travas.verificar_produto(novo))


class Anuncio(unittest.TestCase):
    def test_oferta_correta(self):
        texto = f"Guia de rotina por R$ 7,00. Acesse: {LINK}"
        self.assertEqual(travas.verificar_anuncio(produto_pronto(), texto, "OFERTA"), [])

    def test_link_diferente(self):
        r = travas.verificar_anuncio(produto_pronto(), "R$ 7,00 https://outro.com/x", "OFERTA")
        self.assertTrue(any("diferente do catálogo" in p for p in r))

    def test_oferta_sem_link(self):
        r = travas.verificar_anuncio(produto_pronto(), "Guia por R$ 7,00", "OFERTA")
        self.assertTrue(any("não contém o link" in p for p in r))

    def test_preco_diferente(self):
        r = travas.verificar_anuncio(produto_pronto(), f"Por R$ 5,00 {LINK}", "OFERTA")
        self.assertTrue(any("preço" in p for p in r))

    def test_produto_nao_pronto(self):
        p = produto_pronto()
        p["status"] = "aguardando_cadastro"
        r = travas.verificar_anuncio(p, f"R$ 7,00 {LINK}", "OFERTA")
        self.assertTrue(any("não está 'pronto'" in x for x in r))

    def test_valor_sem_produto_so_checa_termos(self):
        self.assertEqual(travas.verificar_anuncio(None, "Dica prática de hoje.", "VALOR"), [])
        self.assertTrue(travas.verificar_anuncio(None, "Dica para o lucro.", "VALOR"))

    def test_oferta_sem_produto_bloqueia(self):
        self.assertTrue(travas.verificar_anuncio(None, "Compre", "OFERTA"))


class PrepararLegenda(unittest.TestCase):
    def test_corrige_placeholder_preco_markdown_e_termos(self):
        texto = ("**Guia de rotina** por R$ 9,00! Você terá a primeira venda rápido. "
                 "Garanta já: https://SEU-LINK-DE-CHECKOUT #rotina #lucro")
        legenda, acoes, problemas = travas.preparar_legenda(produto_pronto(), texto, "OFERTA")
        self.assertEqual(problemas, [])
        self.assertIn(LINK, legenda)
        self.assertNotIn("SEU-LINK", legenda)
        self.assertIn("R$ 7,00", legenda)
        self.assertNotIn("**", legenda)
        self.assertEqual(travas.encontrar_termos(legenda), [])
        self.assertTrue(acoes)

    def test_acrescenta_link_que_faltava(self):
        legenda, _, problemas = travas.preparar_legenda(produto_pronto(), "Guia de rotina por R$ 7,00 hoje mesmo.", "OFERTA")
        self.assertEqual(problemas, [])
        self.assertIn(LINK, legenda)

    def test_texto_vazio_usa_modelo_do_catalogo(self):
        legenda, acoes, problemas = travas.preparar_legenda(produto_pronto(), "primeira venda!", "OFERTA")
        self.assertEqual(problemas, [])
        self.assertIn("Guia Prático de Rotina em 7 Dias", legenda)
        self.assertTrue(any("texto-modelo" in a for a in acoes))

    def test_sem_produto_oferta_continua_bloqueada(self):
        _, _, problemas = travas.preparar_legenda(None, "Compre agora por R$ 7,00", "OFERTA")
        self.assertTrue(problemas)

    def test_produto_nao_pronto_nao_e_corrigivel(self):
        p = produto_pronto()
        p["status"] = "aprovado"
        _, _, problemas = travas.preparar_legenda(p, f"R$ 7,00 {LINK}", "OFERTA")
        self.assertTrue(problemas)

    def test_modelos_seguros_sempre_passam(self):
        p = produto_pronto()
        for tipo in ("OFERTA", "VITRINE", "VALOR"):
            texto = travas.texto_modelo_seguro(p, tipo)
            self.assertEqual(travas.verificar_anuncio(p, texto, tipo), [], tipo)
        self.assertEqual(travas.verificar_anuncio(None, travas.texto_modelo_seguro(None, "VALOR"), "VALOR"), [])

    def test_card_modelo_respeita_limites(self):
        h, s = travas.card_modelo(produto_pronto(nome="N" * 70 + " fim"), "OFERTA")
        self.assertLessEqual(len(h), 60)
        self.assertLessEqual(len(s), 100)


if __name__ == "__main__":
    unittest.main()

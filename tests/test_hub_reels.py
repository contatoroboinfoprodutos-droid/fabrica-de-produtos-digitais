import json
import os
import tempfile
import unittest

from tests import stubs
stubs.instalar()

from fabrica_produtos import __main__ as cli, link_hub, reels  # noqa: E402


def prod(i, nome, status="pronto", link="https://pay.cakto.com.br/abc", promessa="Organize sua rotina."):
    return {"id": i, "nome": nome, "status": status, "link_compra": link, "preco_texto": "R$ 8,90",
            "promessa": promessa, "conteudos": ["Blocos de foco"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cat = os.path.join(self.d, "catalogo.json")
        self.out = os.path.join(self.d, "r.json")
        self.html = os.path.join(self.d, "docs", "link-na-bio.html")
        self.grava([prod("a", "Guia A"), prod("b", "Guia B", link="https://pay.cakto.com.br/xyz")])

    def grava(self, ps):
        with open(self.cat, "w", encoding="utf-8") as f:
            json.dump({"produtos": ps}, f)


class Hub(Base):
    def test_so_produtos_prontos_com_link_real(self):
        self.grava([prod("a", "Guia A"), prod("b", "Sem link", link=""), prod("c", "Aguardando", status="aguardando_cadastro")])
        r = link_hub.atualizar(self.cat, self.html)
        t = open(self.html, encoding="utf-8").read()
        self.assertEqual(r["produtos"], 1)
        self.assertIn("Guia A", t)
        self.assertNotIn("Sem link", t)
        self.assertNotIn("Aguardando", t)

    def test_cards_usam_titulo_preco_e_link_do_catalogo(self):
        link_hub.atualizar(self.cat, self.html)
        t = open(self.html, encoding="utf-8").read()
        for x in ("Fábrica de", "Escolha seu guia abaixo 👇", "Todos em PDF imediato", "R$ 8,90", "Comprar agora",
                  'href="https://pay.cakto.com.br/abc"', 'href="https://pay.cakto.com.br/xyz"', "#ffd600"):
            self.assertIn(x, t)
        self.assertEqual(t.count('class="card"'), 2)

    def test_escapa_html_e_remove_termos_proibidos(self):
        self.grava([prod("a", "<b>x</b>", promessa="Método testado. Organize seu dia.")])
        link_hub.atualizar(self.cat, self.html)
        t = open(self.html, encoding="utf-8").read()
        self.assertNotIn("<b>x</b>", t)
        self.assertNotIn("testado", t)
        self.assertIn("Organize seu dia.", t)

    def test_idempotente_e_catalogo_vazio(self):
        self.assertTrue(link_hub.atualizar(self.cat, self.html)["mudou"])
        self.assertFalse(link_hub.atualizar(self.cat, self.html)["mudou"])
        self.grava([])
        link_hub.atualizar(self.cat, self.html)
        self.assertIn("em breve", open(self.html, encoding="utf-8").read())

    def test_cli(self):
        os.environ["FABRICA_CATALOGO"] = self.cat
        try:
            self.assertEqual(cli.main(["hub"]), 0)
        finally:
            os.environ.pop("FABRICA_CATALOGO")


BOM = json.dumps({"gancho_3s": "Você é interrompido a cada 5 minutos?",
                  "dor_solucao_10s": "Mostra tela bagunçada > mostra o método de blocos de foco do PDF",
                  "legenda": "Quantas vezes você perde o foco?\nLink na bio 👇"})


class Reels(Base):
    def test_gera_so_para_quem_nao_tem_e_monta_cta_e_preco(self):
        chamadas = []
        ex = lambda d: chamadas.append(d) or BOM  # noqa: E731
        r = reels.atualizar(self.cat, self.out, ex)
        self.assertEqual(r["novos"], ["a", "b"])
        rs = json.load(open(self.out, encoding="utf-8"))
        self.assertEqual(set(rs[0]), {"id_produto", "gancho_3s", "roteiro_15s", "legenda", "cta"})
        self.assertEqual(rs[0]["cta"], "Link na bio - todos os guias lá")
        self.assertTrue(rs[0]["roteiro_15s"].startswith("[0-3s] Você é interrompido"))
        self.assertIn("[3-10s]", rs[0]["roteiro_15s"])
        self.assertTrue(rs[0]["roteiro_15s"].endswith("[10-15s] Guia em PDF por R$ 8,90. Link na bio - todos os guias lá"))
        # sétimo produto: só o novo é gerado; os antigos não são reescritos
        self.grava([prod("a", "Guia A"), prod("b", "Guia B"), prod("c", "Guia C")])
        chamadas.clear()
        r = reels.atualizar(self.cat, self.out, ex)
        self.assertEqual(r["novos"], ["c"])
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(r["total"], 3)
        self.assertEqual(reels.atualizar(self.cat, self.out, ex)["novos"], [])

    def test_reprova_termo_proibido_link_preco_e_json_ruim(self):
        ruim = [json.dumps({"gancho_3s": "Lucro garantido?", "dor_solucao_10s": "x", "legenda": "y"}),
                json.dumps({"gancho_3s": "Foco?", "dor_solucao_10s": "Compre em https://x.com", "legenda": "y"}),
                json.dumps({"gancho_3s": "Foco?", "dor_solucao_10s": "Só R$ 5", "legenda": "y"}),
                "isto não é json"]
        for texto in ruim:
            r = reels.atualizar(self.cat, self.out, lambda d, t=texto: t)
            self.assertEqual(r["novos"], [], texto)
            self.assertEqual(len(r["falhas"]), 2)
        self.assertFalse(os.path.exists(self.out))

    def test_corrige_na_segunda_tentativa_e_falha_isolada(self):
        respostas = iter(["lixo", BOM, "lixo", "lixo"])
        r = reels.atualizar(self.cat, self.out, lambda d: next(respostas))
        self.assertEqual(r["novos"], ["a"])
        self.assertEqual(len(r["falhas"]), 1)

    def test_ignora_produto_sem_link_ou_nao_pronto(self):
        self.grava([prod("a", "A", link=""), prod("b", "B", status="reprovado")])
        self.assertEqual(reels.pendentes(self.cat, self.out), [])


if __name__ == "__main__":
    unittest.main()

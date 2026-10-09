"""Legenda por rede: hashtags em 3 camadas, CTA do canal e links de CTA liberados na trava de links."""
import importlib.util
import os
import tempfile
import re
import unittest

from fabrica_produtos import config_fabrica as cfg, travas

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("generate_reels", os.path.join(RAIZ, "scripts", "generate_reels.py"))
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)

IG = "https://fabricadeprodutosdigitais.github.io/fabrica-de-produtos-digitais/"
FB = "bit.ly/4ibGb7a"
LINK = "https://pay.cakto.com.br/abc"


def prod(nome="Guia Prático de Produtividade", promessa="Organize sua rotina.", **kw):
    p = {"nome": nome, "promessa": promessa, "status": "pronto", "preco": 8.9, "preco_texto": "R$ 8,90",
         "link_compra": LINK, "conteudos": ["Blocos de foco"]}
    p.update(kw)
    return p


class Legenda(unittest.TestCase):
    def test_links_padrao(self):
        self.assertEqual(cfg.LINK_BIO_INSTAGRAM, IG)
        self.assertEqual(cfg.LINK_FACEBOOK, FB)

    def test_instagram_e_facebook_recebem_cta_diferente_e_3_camadas(self):
        base = "Pare de perder tempo.\n\n#qualquer #coisa"
        ig = travas.finalizar_para_rede(prod(), base, "instagram")
        fb = travas.finalizar_para_rede(prod(), base, "facebook")
        self.assertIn(f"Link na bio: {IG}", ig)
        self.assertNotIn(FB, ig)
        self.assertIn(f"Veja todos os guias: {FB}", fb)
        self.assertNotIn("github.io", fb)
        for h in ("#produtividade", "#organizacao", "#rotina", "#foco", "#gestaodotempo", "#habitos", "#disciplina"):
            self.assertIn(h, ig)
        self.assertEqual(len(re.findall(r"#\w+", ig.splitlines()[-1])), 20)
        self.assertNotIn("#qualquer", ig)                     # hashtags do modelo no fim são trocadas
        self.assertTrue(ig.rstrip().splitlines()[-1].startswith("#produtividade #foco #gestaodotempo"))  # hashtags por último

    def test_hashtags_seguem_o_tema_do_produto(self):
        self.assertIn("#marmitafit", travas.hashtags_em_camadas(prod("Receitas Fit e Marmitas")))
        self.assertNotIn("#rendaextra", travas.hashtags_em_camadas(prod("Receitas Fit e Marmitas")))
        self.assertIn("#financaspessoais", travas.hashtags_em_camadas(prod("Finanças Pessoais do Zero")))
        self.assertIn("#rendaextra", travas.hashtags_em_camadas(prod("Renda extra com habilidades online")))
        self.assertIn("#produtividade", travas.hashtags_em_camadas(None, "dica do dia"))
        todas = " ".join(" ".join(t["prioridade"] + t["tema"] + t["nicho"]) for t in travas.HASHTAGS_TEMAS.values())
        self.assertEqual(travas.encontrar_termos(todas + " " + " ".join(travas.HASHTAGS_AMPLAS)), [])

    def test_20_hashtags_unicas_por_tema_e_amplas_iguais(self):
        amplas = None
        for tema in travas.HASHTAGS_TEMAS:
            lista = travas.lista_de_hashtags(None, {"receitas": "marmita", "financas": "financas", "renda": "renda extra",
                                                    "casa": "organizacao da casa", "produtividade": "foco"}[tema])
            self.assertEqual(len(lista), 20, tema)
            self.assertEqual(len(set(lista)), 20, tema)
            self.assertLessEqual(len(lista), travas.MAX_HASHTAGS)
            fixas = [h for h in lista if h in travas.HASHTAGS_AMPLAS]
            self.assertEqual(len(fixas), 8, tema)
            amplas = amplas or fixas
            self.assertEqual(sorted(fixas), sorted(amplas))

    def test_marmita_mantem_as_5_boas_nas_primeiras_posicoes(self):
        lista = travas.lista_de_hashtags(prod("Receitas Fit e Marmitas"), "marmita")
        self.assertEqual(lista[:5], ["#marmitafit", "#alimentacaosaudavel", "#receitasfit", "#marmitas", "#cardapiosemanal"])
        for h in ("#comidasaudavel", "#reeducacaoalimentar", "#nutricao", "#comidafit", "#marmitafitness",
                  "#marmitando", "#receitafitfacil", "#dicas", "#lifestyle"):
            self.assertIn(h, lista)

    def test_reduzir_para_5_mantem_as_principais_e_o_cta(self):
        ig = travas.finalizar_para_rede(prod("Receitas Fit e Marmitas"), "Marmita da semana.", "instagram")
        curta = travas.reduzir_hashtags(ig, 5)
        self.assertEqual(curta.splitlines()[-1], "#marmitafit #alimentacaosaudavel #receitasfit #marmitas #cardapiosemanal")
        self.assertIn(IG, curta)

    def test_quantidade_por_variavel_respeita_teto_25(self):
        antigo = cfg.HASHTAGS_INSTAGRAM
        try:
            cfg.HASHTAGS_INSTAGRAM = 99
            self.assertEqual(len(re.findall(r"#\w+", travas.finalizar_para_rede(prod(), "x", "instagram").splitlines()[-1])), 20)
            cfg.HASHTAGS_INSTAGRAM = 10
            self.assertEqual(len(re.findall(r"#\w+", travas.finalizar_para_rede(prod(), "x", "instagram").splitlines()[-1])), 10)
        finally:
            cfg.HASHTAGS_INSTAGRAM = antigo

    def test_post_de_valor_usa_o_tema_do_texto_e_nao_o_do_produto(self):
        receitas = prod("Receitas Fit e Marmitas")
        valor = travas.hashtags_em_camadas(receitas, "Escolha UMA tarefa por dia e proteja 25 minutos.", "VALOR")
        self.assertIn("#produtividade", valor)
        self.assertNotIn("#marmitafit", valor)
        self.assertIn("#marmitafit", travas.hashtags_em_camadas(receitas, "Texto sem tema.", "OFERTA"))
        self.assertIn("#marmitafit", travas.hashtags_em_camadas(receitas, "Hoje: marmita da semana.", "VALOR"))

    def test_nao_duplica_cta_se_o_texto_ja_tem_o_link(self):
        t = travas.finalizar_para_rede(prod(), f"Texto.\nLink na bio: {IG}", "instagram")
        self.assertEqual(t.count(IG), 1)

    def test_preparar_legenda_aceita_os_links_de_cta_e_ainda_barra_link_inventado(self):
        t, acoes, problemas = travas.preparar_legenda(prod(), f"Guia por R$ 8,90 {LINK}", "VITRINE", "instagram")
        self.assertEqual(problemas, [])
        self.assertIn(IG, t)
        t, _, problemas = travas.preparar_legenda(prod(), "Veja https://golpe.com/x por R$ 8,90", "VITRINE", "facebook")
        self.assertNotIn("golpe.com", t)                    # trocado pelo link do catálogo
        self.assertEqual(problemas, [])
        self.assertTrue(travas.verificar_anuncio(prod(), "Veja https://golpe.com/x", "VITRINE"))
        self.assertEqual(travas.verificar_anuncio(prod(), f"Veja {IG} e https://{FB}", "VITRINE"), [])

    def test_sem_rede_nao_muda_o_comportamento_antigo(self):
        t, acoes, _ = travas.preparar_legenda(prod(), "Texto com mais de trinta caracteres, certo? #a #b", "VITRINE")
        self.assertNotIn("github.io", t)

    def test_termo_proibido_continua_sendo_removido(self):
        t, _, problemas = travas.preparar_legenda(prod(), "Método testado e comprovado para você. Organize seu dia hoje.",
                                                  "VITRINE", "instagram")
        self.assertEqual(travas.encontrar_termos(t), [])
        self.assertEqual(problemas, [])


class MusicaPlanoB(unittest.TestCase):
    def mp3(self, d, nome, valido=True):
        with open(os.path.join(d, nome + ".mp3"), "wb") as f:
            f.write((b"ID3" if valido else b"lixo") + b"\0" * 3000)

    def test_usa_outro_mp3_valido_quando_o_da_categoria_falha(self):
        with tempfile.TemporaryDirectory() as d:
            p = {"nome": "Marmita Fit", "status": "pronto"}            # categoria -> happy
            self.mp3(d, "happy", valido=False)
            self.mp3(d, "corporate")
            arq, motivo = gr.diagnostico_musica(p, d)
            self.assertEqual(os.path.basename(arq), "corporate.mp3")
            self.assertIn("happy.mp3", motivo)
            self.assertIn("corrompido", motivo)
            self.mp3(d, "lofi")
            self.assertEqual(os.path.basename(gr.diagnostico_musica(p, d)[0]), "lofi.mp3")   # lofi primeiro
            self.mp3(d, "happy")                                         # o da categoria válido: sem aviso
            self.assertEqual(gr.diagnostico_musica(p, d), (os.path.join(d, "happy.mp3"), ""))

    def test_nenhum_valido_fica_sem_audio(self):
        with tempfile.TemporaryDirectory() as d:
            self.mp3(d, "lofi", valido=False)
            arq, motivo = gr.diagnostico_musica({"nome": "Marmita Fit", "status": "pronto"}, d)
            self.assertIsNone(arq)
            self.assertIn("ausente", motivo)


if __name__ == "__main__":
    unittest.main()

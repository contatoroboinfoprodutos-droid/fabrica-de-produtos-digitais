"""scripts/generate_reels.py: seleção, categoria, legenda, quadros e vídeo (ffmpeg real, curto)."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("generate_reels", os.path.join(RAIZ, "scripts", "generate_reels.py"))
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)

CAKTO = "https://pay.cakto.com.br/abc"


def prod(nome, **kw):
    p = {"nome": nome, "status": "pronto", "link_compra": CAKTO, "preco_texto": "R$ 19,90",
         "promessa": "Organize o seu dia. Segunda frase.", "criado_em": "2026-10-05T06:00:00-03:00"}
    p.update(kw)
    return p


class Dados(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(gr.slug("Guia Prático: Receitas Fit – Marmitas!"), "guia-pratico-receitas-fit-marmitas")
        self.assertEqual(gr.slug("???"), "produto")
        self.assertLessEqual(len(gr.slug("a " * 100)), 60)

    def test_so_produto_pronto_com_link_cakto_mais_novo_primeiro(self):
        ps = [prod("A", criado_em="2026-10-01"), prod("B", criado_em="2026-10-03"), prod("C", status="aguardando_cadastro"),
              prod("D", link_compra=""), prod("E", link_compra="https://outro.com/x"), {"nome": ""}]
        self.assertEqual([gr.titulo_de(p) for p in gr.selecionar(ps)], ["B", "A"])
        self.assertEqual(len(gr.selecionar(ps, maximo=1)), 1)
        self.assertEqual(gr.selecionar(ps, so="a")[0]["nome"], "A")

    def test_formato_simples_sem_status_nem_link(self):
        ps = [{"titulo": "Guia X", "descricao": "d", "preco": 8.9, "categoria": "Receitas"}]
        self.assertEqual(len(gr.selecionar(ps)), 1)
        self.assertEqual(gr.preco_de(ps[0]), "R$ 8,90")
        self.assertEqual(gr.preco_de({"titulo": "x"}), "A partir de R$ 8,90")

    def test_categorias_e_musica(self):
        c = lambda n, **k: gr.categoria_de(prod(n, promessa="", **k))  # noqa: E731
        self.assertEqual(c("Guia de Receitas Fit e Marmitas"), "receitas")
        self.assertEqual(c("Guia de Produtividade e Organização da Rotina"), "produtividade")
        self.assertEqual(c("Finanças Pessoais do Zero"), "financas")
        self.assertEqual(c("Pare de ser interrompido e recupere o foco"), "foco")
        self.assertEqual(c("Qualquer coisa"), "rotina")
        self.assertEqual(c("x", categoria="Estudos"), "estudos")
        self.assertEqual(gr.MUSICA_POR_CATEGORIA, {"receitas": "happy", "rotina": "lofi", "financas": "corporate",
                                                   "foco": "lofi", "produtividade": "corporate", "estudos": "lofi"})

    def test_legenda(self):
        l = gr.legenda_de(prod("Marmita Fit Variada", promessa="Monte sem caloria extra. Mais um texto.", categoria="receitas"))
        self.assertEqual(l.splitlines(), ["Marmita Fit Variada", "Monte sem caloria extra.", "#receitas #marmita #fit",
                                          "Link na bio: bit.ly/4rWbLt5"])

    def test_pasta_de_musica_vazia_ou_inexistente_nao_quebra(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(gr.musica_de(prod("X"), d))
            self.assertIsNone(gr.musica_de(prod("X"), os.path.join(d, "nao-existe")))


class Quadros(unittest.TestCase):
    def test_tamanho_cta_so_no_fim_e_titulo_em_2_linhas(self):
        gr_dur = 3.0
        qs = {}
        for i, q in enumerate(gr.montar_quadros(prod("Pare de ser interrompido e recupere seu foco"), gr_dur)):
            qs[i] = q
        self.assertEqual(len(qs), 90)
        self.assertEqual(qs[0].shape, (1920, 1080, 3))
        faixa = lambda q: q[1380:1500, 100:980].astype(int)  # noqa: E731  região do CTA
        self.assertLess(abs(faixa(qs[10]) - faixa(qs[0])).mean(), 3)       # antes dos 2 s finais: sem CTA
        self.assertGreater(abs(faixa(qs[85]) - faixa(qs[10])).mean(), 10)  # depois: CTA visível
        self.assertGreater(abs(qs[45] - qs[0]).mean(), 1)                  # texto aparece (fade in)
        self.assertLessEqual(len(gr.ajustar_titulo("Recupere seu foco")[0]), 2)
        self.assertLessEqual(len(gr.ajustar_titulo("Pare de ser interrompido e recupere seu foco")[0]), 3)

    def test_titulo_enorme_nao_estoura(self):
        linhas, f = gr.ajustar_titulo("palavra " * 30)
        self.assertLessEqual(len(linhas), 5)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg ausente")
class Video(unittest.TestCase):
    def sonda(self, arq):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                              "-of", "json", arq], capture_output=True, text=True).stdout
        return json.loads(out)["streams"]

    def test_sem_musica_gera_video_sem_audio(self):
        with tempfile.TemporaryDirectory() as d:
            r = gr.gerar_video(prod("Guia X"), os.path.join(d, "a.mp4"), duracao=1.0, pasta_musica=os.path.join(d, "vazia"))
            self.assertIsNone(r["musica"])
            s = self.sonda(r["arquivo"])
            self.assertEqual([x["codec_type"] for x in s], ["video"])
            self.assertEqual((s[0]["width"], s[0]["height"]), (1080, 1920))

    def test_com_musica_curta_e_com_mp3_invalido(self):
        with tempfile.TemporaryDirectory() as d:
            mus = os.path.join(d, "mus")
            os.makedirs(mus)
            p = prod("Guia X", categoria="foco")  # foco -> lofi.mp3
            gen = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
                                  "-c:a", "libmp3lame", os.path.join(mus, "lofi.mp3")])
            if gen.returncode != 0:
                self.skipTest("sem libmp3lame")
            r = gr.gerar_video(p, os.path.join(d, "b.mp4"), duracao=1.0, pasta_musica=mus)
            self.assertEqual(os.path.basename(r["musica"]), "lofi.mp3")
            self.assertIn("audio", [x["codec_type"] for x in self.sonda(r["arquivo"])])
            with open(os.path.join(mus, "lofi.mp3"), "wb") as f:   # arquivo corrompido: cai para sem áudio
                f.write(b"nao e mp3" * 400)
            r = gr.gerar_video(p, os.path.join(d, "c.mp4"), duracao=1.0, pasta_musica=mus)
            self.assertIsNone(r["musica"])
            self.assertTrue(os.path.getsize(r["arquivo"]) > 1000)

    def test_main_gera_mp4_e_legendas_e_catalogo_vazio_nao_falha(self):
        with tempfile.TemporaryDirectory() as d:
            cat = os.path.join(d, "c.json")
            with open(cat, "w", encoding="utf-8") as f:
                json.dump({"produtos": []}, f)
            self.assertEqual(gr.main(["--catalogo", cat, "--saida", os.path.join(d, "r")]), 0)
            antigo = gr.DURACAO
            gr.DURACAO = 1.0
            try:
                with open(cat, "w", encoding="utf-8") as f:
                    json.dump({"produtos": [prod("Guia de Receitas Fit")]}, f)
                self.assertEqual(gr.main(["--catalogo", cat, "--saida", os.path.join(d, "r")]), 0)
            finally:
                gr.DURACAO = antigo
            self.assertTrue(os.path.isfile(os.path.join(d, "r", "guia-de-receitas-fit.mp4")))
            leg = open(os.path.join(d, "r", "legendas.txt"), encoding="utf-8").read()
            self.assertIn("#receitas #marmita #fit", leg)


if __name__ == "__main__":
    unittest.main()

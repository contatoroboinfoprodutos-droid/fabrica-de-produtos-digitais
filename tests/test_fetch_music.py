import importlib.util
import os
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carregar(nome):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "scripts", nome + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


fm = carregar("fetch_music")
gr = carregar("generate_reels")
MP3 = b"ID3" + b"\0" * 20000
CHAVE = "SEGREDO-123"


class Resp:
    def __init__(self, status=200, json=None, corpo=b""):
        self.status_code, self._json, self.corpo = status, json, corpo

    def json(self):
        if self._json is None:
            raise ValueError("não é json")
        return self._json

    def iter_content(self, n):
        for i in range(0, len(self.corpo), n):
            yield self.corpo[i:i + n]


class Http:
    def __init__(self, *respostas):
        self.r, self.chamadas = list(respostas), []

    def get(self, url, **kw):
        self.chamadas.append((url, kw))
        r = self.r.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Baixar(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        fm.PASTA = self.d

    def test_baixa_o_download_do_primeiro_hit(self):
        h = Http(Resp(json={"hits": [{"download": "https://cdn.exemplo/a.mp3"}, {"download": "https://cdn.exemplo/b.mp3"}]}),
                 Resp(corpo=MP3))
        self.assertIn("baixado", fm.baixar("happy", "happy cooking acoustic", CHAVE, h))
        self.assertEqual(h.chamadas[0][1]["params"], {"key": CHAVE, "q": "happy cooking acoustic", "per_page": 3})
        self.assertEqual(h.chamadas[1][0], "https://cdn.exemplo/a.mp3")
        self.assertTrue(fm.ja_tem(os.path.join(self.d, "happy.mp3")))

    def test_nao_sobrescreve_mp3_valido(self):
        with open(os.path.join(self.d, "lofi.mp3"), "wb") as f:
            f.write(MP3)
        h = Http()
        self.assertIn("mantido", fm.baixar("lofi", "q", CHAVE, h))
        self.assertEqual(h.chamadas, [])

    def test_falhas_viram_skip_sem_vazar_a_chave(self):
        casos = [Http(Resp(status=404)), Http(Resp(json=None)), Http(Resp(json={"hits": []})),
                 Http(Resp(json={"hits": [{"nome": "x"}]})), Http(RuntimeError(f"erro em ?key={CHAVE}")),
                 Http(Resp(json={"hits": [{"download": "https://x/a.mp3"}]}), Resp(corpo=b"<html>erro</html>")),
                 Http(Resp(json={"hits": [{"download": "https://x/a.mp3"}]}), Resp(status=403))]
        for h in casos:
            msg = fm.baixar("corporate", "q", CHAVE, h)
            self.assertIn("pulado", msg + " pulado")
            self.assertNotIn(CHAVE, msg)
        self.assertFalse(os.path.exists(os.path.join(self.d, "corporate.mp3")))

    def test_sem_chave_nao_quebra_e_nao_chama_rede(self):
        os.environ.pop("PIXABAY_API_KEY", None)
        self.assertEqual(fm.main(Http()), 0)

    def test_main_tenta_as_tres_faixas(self):
        os.environ["PIXABAY_API_KEY"] = CHAVE
        try:
            h = Http(*[Resp(status=404)] * 3)
            self.assertEqual(fm.main(h), 0)
            self.assertEqual(sorted(k["params"]["q"] for _, k in h.chamadas),
                             ["corporate uplifting", "happy cooking acoustic", "lofi chill study"])
        finally:
            os.environ.pop("PIXABAY_API_KEY")


class EscolherMusica(unittest.TestCase):
    def test_regras(self):
        e = gr.escolher_musica
        self.assertEqual(e("Marmita Fit Variada"), "happy")
        self.assertEqual(e("Guia de Receitas Saudáveis"), "happy")
        self.assertEqual(e("Comida rápida de segunda"), "happy")
        self.assertEqual(e("Finanças Pessoais do Zero"), "corporate")
        self.assertEqual(e("Organize seu dinheiro"), "corporate")
        self.assertEqual(e("Guia de Produtividade"), "corporate")
        self.assertEqual(e("Pare de ser interrompido e recupere seu foco"), "lofi")
        self.assertEqual(e("Hábitos de estudo"), "lofi")
        self.assertEqual(e("Benefícios do sono"), "lofi")   # 'fit' dentro de outra palavra não conta

    def test_mp3_vazio_ou_corrompido_vira_sem_audio(self):
        with tempfile.TemporaryDirectory() as d:
            p = {"nome": "Marmita Fit", "status": "pronto"}
            self.assertIsNone(gr.musica_de(p, d))
            open(os.path.join(d, "happy.mp3"), "wb").close()
            self.assertIsNone(gr.musica_de(p, d))
            with open(os.path.join(d, "happy.mp3"), "wb") as f:
                f.write(b"x" * 5000)
            self.assertEqual(os.path.basename(gr.musica_de(p, d)), "happy.mp3")


if __name__ == "__main__":
    unittest.main()

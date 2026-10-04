"""Marcas de publicação: tentar de novo sem nunca postar em duplicidade."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

from tests import stubs
stubs.instalar()

from fabrica_produtos import catalogo, config_fabrica as cfg, marcas  # noqa: E402
from tests.test_integracao import LINK, carregar_lowticket  # noqa: E402
from tests.fixtures import produto_bom  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Resp:
    def __init__(self, status=200, corpo=None):
        self.status_code, self._corpo, self.text = status, corpo or {}, str(corpo)

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Marcas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["POST_MARKER_DIR"] = os.path.join(self.tmp.name, "m")
        self.addCleanup(os.environ.pop, "POST_MARKER_DIR", None)

    def test_inativa_sem_pasta_nao_grava_nada(self):
        os.environ.pop("POST_MARKER_DIR")
        marcas.marcar("facebook")
        marcas.marcar_bloqueio("x")
        self.assertFalse(marcas.ativa())
        self.assertEqual(marcas.estado(), "nada")

    def test_estados(self):
        self.assertEqual(marcas.estado(), "nada")
        marcas.marcar("facebook", {"photo_id": "f1"})
        self.assertEqual(marcas.estado(), "parcial")
        self.assertEqual(marcas.lido("facebook")["photo_id"], "f1")
        marcas.marcar("instagram")
        self.assertEqual(marcas.estado(), "completo")

    def test_bloqueio_vale_ate_completar(self):
        marcas.marcar_bloqueio("sem produto")
        self.assertEqual((marcas.estado(), marcas.bloqueio()), ("bloqueado", "sem produto"))

    def test_so_as_redes_pedidas_contam(self):
        marcas.marcar("facebook")
        self.assertEqual(marcas.estado(("facebook",)), "completo")


class PublicadorLowTicket(unittest.TestCase):
    """lt_publicar_meta com a rede simulada: Facebook primeiro, depois Instagram com a foto do Facebook."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.saida = os.path.join(self.tmp.name, "out")
        os.makedirs(self.saida)
        with open(os.path.join(self.saida, "post_manha.png"), "wb") as f:
            f.write(b"png")
        env = {"POST_MARKER_DIR": os.path.join(self.tmp.name, "m"), "LT_OUTPUT_DIR": self.saida,
               "META_LONG_LIVED_TOKEN": "tok-falso", "FB_PAGE_ID": "PAG1", "INSTAGRAM_ACCOUNT_ID": "IG1"}
        for k, v in env.items():
            os.environ[k] = v
            self.addCleanup(os.environ.pop, k, None)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        self.addCleanup(lambda: os.environ.pop("LT_DRY_RUN", None))
        self.chamadas = []
        self.ig_publica = 200

    def usar(self, tools):
        def get(url, **kw):
            self.chamadas.append(("GET", url))
            if url.endswith("/me/accounts"):
                return Resp(200, {"data": [{"id": "PAG1", "access_token": "tok-pag"}]})
            if url.endswith("/foto1"):
                return Resp(200, {"images": [{"source": "https://img/foto1.jpg"}]})
            return Resp(200, {"status_code": "FINISHED"})

        def post(url, **kw):
            self.chamadas.append(("POST", url))
            if url.endswith("/PAG1/photos"):
                return Resp(200, {"id": "foto1", "post_id": "PAG1_1"})
            if url.endswith("/IG1/media"):
                return Resp(200, {"id": "cont1"})
            if url.endswith("/IG1/media_publish"):
                return Resp(self.ig_publica, {"id": "m1"} if self.ig_publica == 200 else {"error": "x"})
            raise AssertionError(url)

        for nome, f in (("get", get), ("post", post)):
            p = mock.patch.object(tools.requests, nome, f)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(tools.time, "sleep")
        p.start()
        self.addCleanup(p.stop)

    def contar(self, sufixo):
        return sum(1 for m, u in self.chamadas if m == "POST" and u.endswith(sufixo))

    def test_publica_nas_duas_redes_e_nao_repete(self):
        _, tools = carregar_lowticket("false")
        self.usar(tools)
        legenda = "Uma dica prática: organize o dia em blocos pequenos e revise ao final da semana."
        r1 = tools.lt_publicar_meta("post_manha.png", legenda)
        self.assertIn("Facebook: publicado", r1)
        self.assertIn("Instagram: publicado", r1)
        self.assertEqual(marcas.estado(), "completo")
        r2 = tools.lt_publicar_meta("post_manha.png", legenda)
        self.assertIn("Já publicado", r2)
        self.assertEqual((self.contar("/PAG1/photos"), self.contar("/IG1/media_publish")), (1, 1))

    def test_facebook_ok_instagram_falhou_a_nova_tentativa_so_faz_o_instagram(self):
        _, tools = carregar_lowticket("false")
        self.usar(tools)
        legenda = "Uma dica prática: organize o dia em blocos pequenos e revise ao final da semana."
        self.ig_publica = 400
        r1 = tools.lt_publicar_meta("post_manha.png", legenda)
        self.assertIn("Instagram: ERRO", r1)
        self.assertEqual(marcas.estado(), "parcial")
        self.ig_publica = 200
        r2 = tools.lt_publicar_meta("post_manha.png", legenda)
        self.assertIn("Facebook: já publicado antes", r2)
        self.assertIn("Instagram: publicado", r2)
        self.assertEqual(self.contar("/PAG1/photos"), 1)  # a foto NÃO foi enviada de novo
        self.assertEqual(marcas.estado(), "completo")

    def test_oferta_sem_produto_pronto_e_bloqueio_definitivo(self):
        _, tools = carregar_lowticket("false")
        self.usar(tools)
        r = tools.lt_publicar_meta("post_tarde.png", "Compre o guia por R$ 7,00 https://SEU-LINK-DE-CHECKOUT")
        self.assertTrue(r.startswith("ERRO"), r)
        self.assertEqual(marcas.estado(), "bloqueado")
        self.assertEqual(self.chamadas, [])  # nada chegou à Meta

    def test_credenciais_da_meta_ausentes_e_bloqueio_definitivo(self):
        os.environ.pop("META_LONG_LIVED_TOKEN")
        _, tools = carregar_lowticket("false")
        r = tools.lt_publicar_meta("post_manha.png", "Uma dica prática: organize o dia em blocos pequenos.")
        self.assertIn("META_LONG_LIVED_TOKEN", r)
        self.assertEqual(marcas.estado(), "bloqueado")

    def test_simulacao_nao_grava_marcas(self):
        _, tools = carregar_lowticket("true")
        r = tools.lt_publicar_meta("post_manha.png", "Uma dica prática: organize o dia em blocos pequenos.")
        self.assertIn("[DRY_RUN]", r)
        self.assertEqual(marcas.estado(), "nada")


class FerramentasDoRoboPrincipal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        os.environ["POST_MARKER_DIR"] = os.path.join(self.tmp.name, "m")
        self.addCleanup(os.environ.pop, "POST_MARKER_DIR", None)
        stubs.instalar_config(dry_run=False)
        import importlib
        import sys
        sys.modules.pop("tools.crewai_meta_tools", None)
        self.mod = importlib.import_module("tools.crewai_meta_tools")

    def test_sem_produto_pronto_vira_bloqueio_definitivo(self):
        r = self.mod.PublishToFacebookTool()._run(message="Conheça o guia, com passos práticos para a rotina.")
        self.assertTrue(r.startswith("ERRO"), r)
        self.assertEqual(marcas.estado(), "bloqueado")

    def test_facebook_publicado_nao_e_repetido(self):
        r = catalogo.adicionar(produto_bom(), "aprovado", "x")
        catalogo.atualizar(r["id"], "ok", status="pronto", link_compra=LINK, plataforma="cakto")
        api = mock.MagicMock()
        api.publish_facebook_post.return_value = mock.Mock(post_id="FB1")
        with mock.patch.object(self.mod, "MetaGraphAPI", return_value=api):
            t = self.mod.PublishToFacebookTool()
            r1 = t._run(message="Guia de rotina em PDF por R$ 7,00, com passos práticos para o dia a dia.")
            r2 = t._run(message="Guia de rotina em PDF por R$ 7,00, com passos práticos para o dia a dia.")
        self.assertIn("sucesso", r1)
        self.assertIn("já publicado", r2)
        self.assertEqual(api.publish_facebook_post.call_count, 1)
        self.assertEqual(marcas.estado(("facebook",)), "completo")


FALSO_PYTHON = """#!/bin/bash
# Faz o papel de `python` dentro do script do workflow: cada tentativa do robô segue o CENARIO.
case "$*" in
  *marcas*) cd "$RAIZ" && exec python3 -m fabrica_produtos marcas ;;
esac
n=$(cat "$CONTA" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$CONTA"
cd "$RAIZ"
case "$CENARIO:$n" in
  parcial:1)  python3 -c "from fabrica_produtos import marcas; marcas.marcar('facebook')"; exit 1 ;;
  parcial:2)  python3 -c "from fabrica_produtos import marcas; marcas.marcar('instagram')"; exit 0 ;;
  bloqueio:*) python3 -c "from fabrica_produtos import marcas; marcas.marcar_bloqueio('sem produto')"; exit 0 ;;
  falha_total:*) exit 1 ;;
  esquece:*)  exit 0 ;;  # a IA terminou "bem" mas não chamou a ferramenta de publicar
  so_facebook:*) python3 -c "from fabrica_produtos import marcas; marcas.marcar('facebook')"; exit 0 ;;
esac
"""


def _roteiro(arquivo, passo):
    import yaml
    with open(os.path.join(RAIZ, ".github", "workflows", arquivo), encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    for job in wf["jobs"].values():
        for st in job["steps"]:
            if st.get("name") == passo:
                return st["run"]
    raise KeyError(passo)


try:
    import yaml  # noqa: F401
    TEM_YAML = True
except ImportError:
    TEM_YAML = False


@unittest.skipUnless(TEM_YAML and shutil.which("bash"), "precisa de bash e PyYAML")
class LacoDeTentativasDoWorkflow(unittest.TestCase):
    """Executa o script REAL dos workflows com um `python` falso, sem rede e sem esperar de verdade."""

    def rodar(self, arquivo, passo, cenario, dry_run="false", extra_env=None):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        bin_ = os.path.join(tmp, "bin")
        os.makedirs(bin_)
        for nome, corpo in (("python", FALSO_PYTHON), ("sleep", "#!/bin/bash\nexit 0\n")):
            caminho = os.path.join(bin_, nome)
            with open(caminho, "w") as f:
                f.write(corpo)
            os.chmod(caminho, os.stat(caminho).st_mode | stat.S_IEXEC)
        script = os.path.join(tmp, "roteiro.sh")
        with open(script, "w") as f:
            f.write(_roteiro(arquivo, passo))
        env = {"PATH": bin_ + os.pathsep + os.environ["PATH"], "RAIZ": RAIZ, "RUNNER_TEMP": tmp,
               "CONTA": os.path.join(tmp, "conta"), "CENARIO": cenario, "GROQ_API_KEY": "x",
               "LT_LLM_PROVIDER": "gemini", "LT_LLM_MODEL": "gemini/gemini-3.8-flash", "LT_DRY_RUN": dry_run,
               "SLOT": "manha", "LLM_PROVIDER": "gemini", "DRY_RUN": dry_run, "PYTHONPATH": RAIZ,
               **(extra_env or {})}
        r = subprocess.run(["bash", "-e", script], env=env, cwd=RAIZ, capture_output=True, text=True, timeout=60)
        conta = os.path.join(tmp, "conta")
        tentativas = 0
        if os.path.exists(conta):
            with open(conta) as f:
                tentativas = int(f.read())
        return r.returncode, tentativas, r.stdout + r.stderr

    ROTEIROS = (("lowticket.yml", "Executa o robô"), ("main.yml", "Executar Pipeline Principal"))

    def test_facebook_na_1a_tentativa_instagram_na_2a_termina_certo(self):
        for arq, passo in self.ROTEIROS:
            rc, n, _ = self.rodar(arq, passo, "parcial")
            self.assertEqual((rc, n), (0, 2), arq)

    def test_bloqueio_definitivo_nao_gasta_novas_tentativas(self):
        for arq, passo in self.ROTEIROS:
            rc, n, saida = self.rodar(arq, passo, "bloqueio")
            self.assertEqual((rc, n), (0, 1), arq)
            self.assertIn("bloqueada de propósito", saida)

    def test_ia_que_termina_sem_publicar_e_repetida_e_depois_falha(self):
        for arq, passo in self.ROTEIROS:
            rc, n, _ = self.rodar(arq, passo, "esquece")
            self.assertEqual((rc, n), (1, 3), arq)

    def test_falha_total_tenta_tres_vezes_e_falha(self):
        for arq, passo in self.ROTEIROS:
            rc, n, _ = self.rodar(arq, passo, "falha_total")
            self.assertEqual((rc, n), (1, 3), arq)

    def test_so_uma_rede_publicada_ao_final_avisa_e_falha(self):
        for arq, passo in self.ROTEIROS:
            rc, n, saida = self.rodar(arq, passo, "so_facebook")
            self.assertEqual((rc, n), (1, 3), arq)
            self.assertIn("Só uma das redes publicou", saida)

    def test_simulacao_continua_valendo_exit_zero(self):
        for arq, passo in self.ROTEIROS:
            rc, n, _ = self.rodar(arq, passo, "esquece", dry_run="true")
            self.assertEqual((rc, n), (0, 1), arq)


if __name__ == "__main__":
    unittest.main()

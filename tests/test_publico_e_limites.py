"""Público geral (sem segmentação), limite diário configurável e limites de tempo contra travamento."""
import os
import re
import sys
import tempfile
import unittest

from tests import stubs
stubs.instalar()

from fabrica_produtos import __main__ as cli, catalogo, config_fabrica as cfg, travas  # noqa: E402
from tests.test_integracao import Base, carregar_lowticket  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Publico(Base):
    def test_dry_run_marca_para_todos_os_publicos_e_traz_as_duas_legendas(self):
        self.liberar()
        _, tools = carregar_lowticket("true")
        r = tools.lt_publicar_meta("post_tarde.png", "Guia de rotina por R$ 7,00. Organize o seu dia.")
        self.assertIn("Público: para todos os públicos", r)
        self.assertIn("Legenda Facebook:", r)
        self.assertIn("Legenda Instagram:", r)
        fb, ig = r.split("Legenda Facebook:\n")[1].split("\n\nLegenda Instagram:\n")
        self.assertIn("Veja todos os guias: bit.ly/4ibGb7a", fb)
        self.assertIn("Link na bio: https://fabricadeprodutosdigitais.github.io/fabrica-de-produtos-digitais/", ig)
        for legenda in (fb, ig):
            linha = next(l for l in legenda.splitlines() if l.startswith("#"))   # (a nota [TRAVAS] vem depois)
            self.assertEqual(len(re.findall(r"#\w+", linha)), 7)               # ampla (2) + tema (3) + nicho (2)

    def test_payloads_reais_nao_tem_nenhum_campo_de_segmentacao(self):
        _, tools = carregar_lowticket("true")
        for payload in (tools._payload_facebook("x"), tools._payload_instagram("https://u/i.jpg", "x")):
            self.assertEqual(set(payload) & set(travas.CHAVES_DE_SEGMENTACAO), set())
            self.assertEqual(travas.rotulo_publico(payload), travas.PUBLICO_GERAL)

    def test_rotulo_nao_mente_se_aparecer_segmentacao(self):
        self.assertIn("SEGMENTADO", travas.rotulo_publico({"caption": "x", "targeting": {"age_min": 25}}))

    def test_codigo_dos_robos_nunca_envia_campo_de_segmentacao(self):
        proibidas = [k for k in travas.CHAVES_DE_SEGMENTACAO if k != "privacy"]
        for pasta in ("tools", "infoprodutos_lowticket"):
            for nome in os.listdir(os.path.join(RAIZ, pasta)):
                if nome.endswith(".py"):
                    src = open(os.path.join(RAIZ, pasta, nome), encoding="utf-8").read()
                    for k in proibidas:
                        self.assertNotRegex(src, rf"[\"']{k}[\"']\s*:", f"{pasta}/{nome} usa {k}")


class Limites(Base):
    def test_teto_diario_padrao_e_5_e_so_conta_o_dia_de_hoje(self):
        self.assertEqual(cfg.MAX_PRODUTOS_POR_DIA, 5)
        self.assertEqual(cfg.LLM_TIMEOUT, 240)
        saida = []
        antigo = cli._saida
        cli._saida = saida.append
        antigo_max, cfg.MAX_PRODUTOS_POR_DIA = cfg.MAX_PRODUTOS_POR_DIA, 2
        try:
            for i in range(2):
                catalogo.adicionar({"nome": f"Produto {i}", "preco": 8.9, "preco_texto": "R$ 8,90"}, "aprovado", "x")
            self.assertEqual(cli.cmd_criar(), 0)
            self.assertIn("Limite diário atingido (2/2)", saida[-1])
        finally:
            cli._saida = antigo
            cfg.MAX_PRODUTOS_POR_DIA = antigo_max

    def test_workflows_tem_limite_de_tempo_e_criar_roda_3_vezes_por_dia(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML ausente")
        wf = os.path.join(RAIZ, ".github", "workflows")
        for arq, job in (("produto.yml", "fabrica"), ("lowticket.yml", "lowticket"), ("main.yml", "run-crew")):
            d = yaml.safe_load(open(os.path.join(wf, arq), encoding="utf-8"))
            self.assertLessEqual(d["jobs"][job]["timeout-minutes"], 40, arq)
        d = yaml.safe_load(open(os.path.join(wf, "produto.yml"), encoding="utf-8"))
        crons = [c["cron"] for c in d[True]["schedule"]]
        self.assertEqual(sorted(crons), sorted(["0 9 * * *", "0 15 * * *", "0 21 * * *", "30 */6 * * *"]))
        passo = next(s for s in d["jobs"]["fabrica"]["steps"] if s.get("name") == "Executa a fabrica")["run"]
        for c in ("0 9 * * *", "0 15 * * *", "0 21 * * *"):
            self.assertIn(c, passo)
        self.assertEqual(d["jobs"]["fabrica"]["env"]["FABRICA_MAX_POR_DIA"],
                         "${{ vars.FABRICA_MAX_POR_DIA || secrets.FABRICA_MAX_POR_DIA || '5' }}")

    def test_chamadas_de_ia_da_fabrica_tem_timeout(self):
        os.environ["GEMINI_API_KEY"] = "k"
        from fabrica_produtos import llms
        capturado = {}
        antigo = sys.modules["crewai"].LLM
        sys.modules["crewai"].LLM = lambda **kw: capturado.update(kw) or object()
        try:
            for prov in ("gemini", "groq", "openrouter"):
                capturado.clear()
                llms.construir_llm(prov, "modelo")
                self.assertEqual(capturado.get("timeout"), 240, prov)
            llms.construir_llm("groq", "modelo", timeout=30)
            self.assertEqual(capturado["timeout"], 30)
        finally:
            sys.modules["crewai"].LLM = antigo


if __name__ == "__main__":
    unittest.main()

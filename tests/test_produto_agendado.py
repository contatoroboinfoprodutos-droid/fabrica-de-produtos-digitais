"""produto.yml agendado: 06:00 BRT cria os produtos do dia em lote (até FABRICA_MAX_POR_DIA), manual cria 1."""
import os
import tempfile
import unittest
from unittest import mock

import yaml

from tests import stubs
stubs.instalar()

from fabrica_produtos import __main__ as cli, catalogo, config_fabrica as cfg  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(RAIZ, ".github", "workflows", "produto.yml")


class Lote(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        self.saida = []
        for alvo, valor in ((cli, None),):
            pass
        p = mock.patch.object(cli, "_saida", self.saida.append)
        p.start()
        self.addCleanup(p.stop)
        self.antigo = (cfg.MAX_PRODUTOS_POR_DIA, cfg.PAUSADA, cfg.LOTE_MINUTOS)
        cfg.MAX_PRODUTOS_POR_DIA, cfg.PAUSADA, cfg.LOTE_MINUTOS = 3, False, 32
        self.addCleanup(lambda: (setattr(cfg, "MAX_PRODUTOS_POR_DIA", self.antigo[0]),
                                 setattr(cfg, "PAUSADA", self.antigo[1]), setattr(cfg, "LOTE_MINUTOS", self.antigo[2])))

    def aprovar(self, n=[0]):
        n[0] += 1
        return catalogo.adicionar({"nome": f"Produto {n[0]}", "preco": 8.9, "preco_texto": "R$ 8,90"}, "aprovado", "x")

    def test_lote_cria_ate_o_teto_e_so_isso(self):
        um = mock.Mock(side_effect=lambda: self.aprovar())
        with mock.patch.object(cli, "_criar_um", um):
            self.assertEqual(cli.cmd_criar(lote=True), 0)
        self.assertEqual(um.call_count, 3)
        self.assertEqual(catalogo.criados_hoje(), 3)
        self.assertIn("Lote concluído: 3/3", self.saida[-1])

    def test_manual_cria_so_um(self):
        um = mock.Mock(side_effect=lambda: self.aprovar())
        with mock.patch.object(cli, "_criar_um", um):
            self.assertEqual(cli.cmd_criar(), 0)
        self.assertEqual(um.call_count, 1)

    def test_teto_atingido_sai_verde_sem_criar(self):
        for _ in range(3):
            self.aprovar()
        um = mock.Mock()
        with mock.patch.object(cli, "_criar_um", um):
            self.assertEqual(cli.cmd_criar(lote=True), 0)
        um.assert_not_called()
        self.assertIn("Limite diário atingido (3/3)", self.saida[-1])

    def test_segundo_horario_completa_so_o_que_faltou(self):
        self.aprovar()
        um = mock.Mock(side_effect=lambda: self.aprovar())
        with mock.patch.object(cli, "_criar_um", um):
            cli.cmd_criar(lote=True)
        self.assertEqual(um.call_count, 2)

    def test_rodada_que_falha_nao_derruba_as_outras_e_tentativas_sao_limitadas(self):
        chamadas = []

        def um():
            chamadas.append(1)
            if len(chamadas) == 1:
                raise RuntimeError("IA fora do ar")
            return self.aprovar()
        with mock.patch.object(cli, "_criar_um", side_effect=um):
            self.assertEqual(cli.cmd_criar(lote=True), 0)       # nunca vermelho por uma rodada ruim
        self.assertEqual(catalogo.criados_hoje(), 3)
        self.assertTrue(any("Rodada falhou: RuntimeError" in s for s in self.saida))
        chamadas.clear()
        cfg.MAX_PRODUTOS_POR_DIA = 5
        with mock.patch.object(cli, "_criar_um", side_effect=lambda: (_ for _ in ()).throw(RuntimeError("x"))) as m:
            self.assertEqual(cli.cmd_criar(lote=True), 0)
        self.assertEqual(m.call_count, 5 - catalogo.criados_hoje() + 2)   # não gira para sempre

    def test_pausada_nao_cria(self):
        cfg.PAUSADA = True
        um = mock.Mock()
        with mock.patch.object(cli, "_criar_um", um):
            self.assertEqual(cli.cmd_criar(lote=True), 0)
        um.assert_not_called()

    def test_orcamento_de_tempo_para_o_lote(self):
        cfg.LOTE_MINUTOS = 0
        um = mock.Mock(side_effect=lambda: self.aprovar())
        with mock.patch.object(cli, "_criar_um", um):
            self.assertEqual(cli.cmd_criar(lote=True), 0)
        um.assert_not_called()
        self.assertTrue(any("Tempo do lote esgotado" in s for s in self.saida))

    def test_cli_aceita_flag_lote(self):
        with mock.patch.object(cli, "cmd_criar", return_value=0) as m:
            cli.main(["criar", "--lote"])
            m.assert_called_with(True)
            cli.main(["criar"])
            m.assert_called_with(False)


class Workflow(unittest.TestCase):
    def setUp(self):
        self.texto = open(WF, encoding="utf-8").read()
        self.w = yaml.safe_load(self.texto)

    def test_cron_das_6h_brasilia_e_manual_com_todas_as_acoes(self):
        on = self.w.get("on") or self.w.get(True)
        crons = [c["cron"] for c in on["schedule"]]
        self.assertIn("0 9 * * *", crons)                       # 09:00 UTC = 06:00 BRT
        self.assertIn("workflow_dispatch", on)
        desc = on["workflow_dispatch"]["inputs"]["acao"]["description"]
        for a in ("criar", "verificar", "sondar", "definir-link", "status", "hub", "reels"):
            self.assertIn(a, desc)

    def test_agendado_usa_lote_e_manual_nao(self):
        self.assertIn('LOTE="--lote"', self.texto)
        self.assertIn('${LOTE:-}', self.texto)
        linha_manual = next(l for l in self.texto.splitlines() if 'EVENTO" = "workflow_dispatch"' in l)
        self.assertNotIn("lote", linha_manual)

    def test_variaveis_repassadas_e_tempo_limite(self):
        env = self.w["jobs"]["fabrica"]["env"]
        for k in ("FABRICA_HASHTAGS_INSTAGRAM", "FABRICA_HASHTAGS_FACEBOOK", "FABRICA_MAX_POR_DIA", "OPENROUTER_MODEL"):
            self.assertIn(k, env)
        self.assertLessEqual(self.w["jobs"]["fabrica"]["timeout-minutes"], 45)
        self.assertGreater(self.w["jobs"]["fabrica"]["timeout-minutes"] * 60, cfg.LOTE_MINUTOS * 60)


if __name__ == "__main__":
    unittest.main()

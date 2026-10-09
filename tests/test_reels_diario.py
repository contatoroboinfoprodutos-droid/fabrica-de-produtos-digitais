"""Reels diários: escolha do produto (novo, depois rodízio), legendas com 5 hashtags, retry por rede,
agendamento do workflow e o get_llm do robô principal sem OPENROUTER_MODEL."""
import datetime as dt
import importlib
import os
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

import requests
import yaml

from tests import stubs
stubs.instalar()

from agents import model_healer as mh  # noqa: E402
from fabrica_produtos import catalogo, config_fabrica as cfg, reels_publicar as rp, travas  # noqa: E402
from tests.fixtures import produto_bom  # noqa: E402
from tests.test_model_healer_e_retry import Resp, Sessao  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOJE = dt.datetime.now(dt.timezone.utc).date().isoformat()


def prod(i, criado, nome=None):
    return {"id": i, "nome": nome or f"Guia {i}", "criado_em": criado, "preco_texto": "R$ 8,90", "status": "pronto",
            "link_compra": "https://pay.cakto.com.br/abc"}


class Escolha(unittest.TestCase):
    def test_pega_o_produto_novo_sem_reel_mais_recente_primeiro(self):
        ps = [prod("a", "2026-10-01"), prod("b", "2026-10-05"), prod("c", "2026-10-03")]
        p, pend = rp.escolher_produto(ps, [{"id_produto": "b", "data": "2026-10-06", "facebook": "1", "instagram": "2"}])
        self.assertEqual(p["id"], "c")
        self.assertIsNone(pend)

    def test_sem_produto_novo_usa_o_menos_postado_e_depois_o_mais_antigo(self):
        ps = [prod("a", "2026-10-01"), prod("b", "2026-10-05")]
        feitos = [{"id_produto": "a", "data": "2026-10-06", "facebook": "1", "instagram": "2"},
                  {"id_produto": "a", "data": "2026-10-07", "facebook": "1", "instagram": "2"},
                  {"id_produto": "b", "data": "2026-10-08", "facebook": "1", "instagram": "2"}]
        self.assertEqual(rp.escolher_produto(ps, feitos)[0]["id"], "b")      # a tem 2 Reels, b tem 1
        feitos.append({"id_produto": "b", "data": "2026-10-09", "facebook": "1", "instagram": "2"})
        self.assertEqual(rp.escolher_produto(ps, feitos)[0]["id"], "a")      # empate: o postado há mais tempo

    def test_completa_so_a_rede_que_faltou_hoje(self):
        ps = [prod("a", "2026-10-01"), prod("b", "2026-10-05")]
        feitos = [{"id_produto": "a", "data": HOJE, "facebook": "FB1", "instagram": None}]
        p, pend = rp.escolher_produto(ps, feitos)
        self.assertEqual(p["id"], "a")
        self.assertIs(pend, feitos[0])

    def test_sem_produtos(self):
        self.assertEqual(rp.escolher_produto([], []), (None, None))


class Legenda(unittest.TestCase):
    def test_cta_por_rede_5_hashtags_e_so_do_catalogo(self):
        p = prod("a", "2026-10-01", "Guia Prático de Receitas Fit e Marmitas")
        roteiros = [{"id_produto": "a", "legenda": "Marmita da semana sem complicação.\nLink na bio 👇"}]
        ig, fb = rp.legenda_da_rede(p, "instagram", roteiros), rp.legenda_da_rede(p, "facebook", roteiros)
        self.assertIn(f"Link na bio: {cfg.LINK_BIO_INSTAGRAM}", ig)
        self.assertNotIn("bit.ly", ig)
        self.assertIn(f"Veja todos os guias: {cfg.LINK_FACEBOOK}", fb)
        self.assertNotIn("github.io", fb)
        for leg in (ig, fb):
            self.assertEqual(len(re.findall(r"#\w+", leg.splitlines()[-1])), 5)
            self.assertTrue(leg.splitlines()[-1].startswith("#marmitafit #alimentacaosaudavel"))
            self.assertIn("R$ 8,90", leg)
            self.assertNotIn("👇", leg)
            self.assertEqual(travas.encontrar_termos(leg), [])


class Execucao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")
        self.estado = os.path.join(self.tmp.name, "reels.json")
        r = catalogo.adicionar(produto_bom(), "aprovado", "x")
        catalogo.atualizar(r["id"], "ok", status="pronto", link_compra="https://pay.cakto.com.br/abc", plataforma="cakto")
        self.id = r["id"]
        for k in ("META_LONG_LIVED_TOKEN", "FB_PAGE_ID", "INSTAGRAM_ACCOUNT_ID"):
            os.environ[k] = "x"
            self.addCleanup(os.environ.pop, k, None)
        self.gr = types.SimpleNamespace(slug=lambda t: "video", titulo_de=lambda p: p["nome"],
                                        gerar_video=lambda p, saida: {"arquivo": saida, "musica": None, "motivo": "teste"})
        p = mock.patch.object(rp, "token_da_pagina", return_value="TP")
        p.start()
        self.addCleanup(p.stop)

    def roda(self, fb, ig, **k):
        return rp.executar(dry_run=False, pasta=self.tmp.name, estado=self.estado, gerar=self.gr,
                           publicar_fb=fb, publicar_ig=ig, **k)

    def test_dry_run_nao_gera_nem_publica_e_mostra_publico_geral(self):
        fb, ig = mock.Mock(), mock.Mock()
        with mock.patch("builtins.print") as pr:
            rc = rp.executar(dry_run=True, estado=self.estado, gerar=mock.Mock(), publicar_fb=fb, publicar_ig=ig)
        saida = "\n".join(str(c.args[0]) for c in pr.call_args_list)
        self.assertEqual(rc, 0)
        self.assertIn("Público: para todos os públicos", saida)
        self.assertIn("Legenda Facebook", saida)
        fb.assert_not_called()
        self.assertFalse(os.path.exists(self.estado))

    def test_publica_nas_duas_redes_e_registra(self):
        fb = mock.Mock(return_value={"id": "FB1", "source": "https://cdn/v.mp4"})
        ig = mock.Mock(return_value={"id": "IG1"})
        self.assertEqual(self.roda(fb, ig), 0)
        self.assertEqual(ig.call_args[0][1], "https://cdn/v.mp4")           # o Instagram usa a URL do vídeo no Facebook
        reg = rp.carregar_estado(self.estado)
        self.assertEqual((reg[0]["id_produto"], reg[0]["facebook"], reg[0]["instagram"]), (self.id, "FB1", "IG1"))

    def test_se_o_instagram_falha_a_proxima_execucao_so_repete_o_instagram(self):
        fb = mock.Mock(return_value={"id": "FB1", "source": None})
        self.assertEqual(self.roda(fb, mock.Mock(side_effect=rp.ErroMeta("HTTP 500"))), 1)
        self.assertEqual(rp.carregar_estado(self.estado)[0]["instagram"], None)
        fb2, ig2 = mock.Mock(), mock.Mock(return_value={"id": "IG1"})
        self.assertEqual(self.roda(fb2, ig2), 0)
        fb2.assert_not_called()                                              # Facebook NUNCA duplica
        self.assertEqual(len(rp.carregar_estado(self.estado)), 1)
        self.assertEqual(rp.carregar_estado(self.estado)[0]["instagram"], "IG1")

    def test_nada_saiu_nao_conta_como_postado(self):
        bad = mock.Mock(side_effect=rp.ErroMeta("x"))
        self.assertEqual(self.roda(bad, bad), 1)
        self.assertEqual(rp.carregar_estado(self.estado), [])

    def test_sem_credenciais_da_meta(self):
        os.environ.pop("FB_PAGE_ID")
        self.assertEqual(self.roda(mock.Mock(), mock.Mock()), 1)


class Meta(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(rp.time, "sleep")
        p.start()
        self.addCleanup(p.stop)
        self.arq = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        self.arq.write(b"0" * 100)
        self.arq.close()
        self.addCleanup(os.remove, self.arq.name)

    def test_retry_3x_em_5xx(self):
        resp = [Resp(500), Resp(502), Resp(200, {"ok": 1})]
        self.assertEqual(rp.com_tentativas(lambda: resp.pop(0)).status_code, 200)

    def test_instagram_container_publica_e_cai_para_5_hashtags_se_recusado(self):
        chamadas = []

        def post(url, data=None, **k):
            chamadas.append((url, dict(data or {})))
            if url.endswith("/media") and len(re.findall(r"#\w+", data["caption"])) > 5:
                return Resp(400, {}, "Error: too many hashtags")
            return Resp(200, {"id": "C1"})
        leg = "Texto\n\n#a #b #c #d #e #f #g"
        with mock.patch.object(rp.requests, "post", side_effect=post), \
                mock.patch.object(rp.requests, "get", return_value=Resp(200, {"status_code": "FINISHED"})):
            r = rp.publicar_instagram(self.arq.name, "https://cdn/v.mp4", leg, "T", "IG")
        self.assertEqual(r, {"id": "C1"})
        medias = [d for u, d in chamadas if u.endswith("/media")]
        self.assertEqual(medias[0]["media_type"], "REELS")
        self.assertEqual(medias[0]["video_url"], "https://cdn/v.mp4")
        self.assertEqual(len(re.findall(r"#\w+", medias[-1]["caption"])), 5)

    def test_instagram_sem_url_usa_upload_resumivel(self):
        urls = []

        def post(url, data=None, headers=None, **k):
            urls.append(url)
            return Resp(200, {"id": "C1", "uri": "https://rupload/x"})
        with mock.patch.object(rp.requests, "post", side_effect=post), \
                mock.patch.object(rp.requests, "get", return_value=Resp(200, {"status_code": "FINISHED"})):
            rp.publicar_instagram(self.arq.name, None, "x", "T", "IG")
        self.assertIn("https://rupload/x", urls)

    def test_instagram_erro_de_processamento_levanta(self):
        with mock.patch.object(rp.requests, "post", return_value=Resp(200, {"id": "C1"})), \
                mock.patch.object(rp.requests, "get", return_value=Resp(200, {"status_code": "ERROR"})):
            with self.assertRaises(rp.ErroMeta):
                rp.publicar_instagram(self.arq.name, "https://cdn/v.mp4", "x", "T", "IG")

    def test_facebook_tres_fases(self):
        fases = []

        def post(url, data=None, headers=None, **k):
            if "rupload" in url:
                fases.append("envio")
                return Resp(200, {"success": True})
            fases.append(data["upload_phase"])
            return Resp(200, {"video_id": "V1", "upload_url": "https://rupload/v"} if data["upload_phase"] == "start"
                        else {"success": True})
        with mock.patch.object(rp.requests, "post", side_effect=post), \
                mock.patch.object(rp.requests, "get", return_value=Resp(200, {"source": "https://cdn/v.mp4"})):
            r = rp.publicar_facebook(self.arq.name, "desc", "TP", "PG", esperar=lambda s: None)
        self.assertEqual(fases, ["start", "envio", "finish"])
        self.assertEqual(r, {"id": "V1", "source": "https://cdn/v.mp4"})


class Workflow(unittest.TestCase):
    def test_reels_yml_agendado_e_manual(self):
        w = yaml.safe_load(open(os.path.join(RAIZ, ".github/workflows/reels.yml"), encoding="utf-8"))
        gatilhos = w.get("on") or w.get(True)
        self.assertEqual(gatilhos["schedule"], [{"cron": "0 18 * * *"}])
        self.assertIn("workflow_dispatch", gatilhos)
        self.assertEqual(w["permissions"]["contents"], "write")
        texto = open(os.path.join(RAIZ, ".github/workflows/reels.yml"), encoding="utf-8").read()
        self.assertIn("reels_publicar", texto)
        self.assertIn("OPENROUTER_MODEL", texto)

    def test_hashtags_chegam_aos_workflows_que_publicam(self):
        for f in ("main", "lowticket", "reels"):
            self.assertIn("FABRICA_HASHTAGS_INSTAGRAM", open(os.path.join(RAIZ, f".github/workflows/{f}.yml"), encoding="utf-8").read(), f)


class GetLlmSemVariable(unittest.TestCase):
    """main.yml com OPENROUTER_MODEL apagado: o Actions entrega '' e o modelo padrão antigo está morto."""

    def carregar_crew(self, **cfgs):
        class LLM:
            def __init__(self, **kw):
                self.__dict__.update(kw)
        crewai = types.ModuleType("crewai")
        crewai.LLM, crewai.Agent, crewai.Crew, crewai.Process, crewai.Task = LLM, object, object, object, object
        proj = types.ModuleType("crewai.project")
        proj.CrewBase = lambda c: c
        proj.agent = proj.crew = proj.task = lambda f: f
        lit = types.ModuleType("litellm")
        lit.exceptions = types.SimpleNamespace(RateLimitError=Exception, APIConnectionError=Exception,
                                               ServiceUnavailableError=Exception, Timeout=Exception)
        cfg_mod = types.ModuleType("config")
        base = dict(llm_provider="openrouter", openrouter_api_key="K", openrouter_model="", groq_api_key=None,
                    gemini_api_key=None, gemini_model="gemini/x", model="m", dry_run=True)
        base.update(cfgs)
        cfg_mod.get_settings = lambda: types.SimpleNamespace(**base)
        tools = types.ModuleType("tools.crewai_meta_tools")
        tools.PublishToFacebookTool = tools.PublishToInstagramTool = object
        mods = {"crewai": crewai, "crewai.project": proj, "litellm": lit, "config": cfg_mod,
                "tools.crewai_meta_tools": tools}
        p = mock.patch.dict(sys.modules, mods)
        p.start()
        self.addCleanup(p.stop)
        sys.modules.pop("crew", None)
        self.addCleanup(sys.modules.pop, "crew", None)
        return importlib.import_module("crew")

    def test_variable_vazia_usa_modelo_gratuito_que_responde(self):
        crew = self.carregar_crew()
        with mock.patch.object(mh, "get_free_model", return_value="google/gemini-2.0-flash-exp:free"):
            llm = crew.get_llm()
        self.assertEqual(llm.model, "openai/google/gemini-2.0-flash-exp:free")

    def test_modelo_antigo_404_e_trocado(self):
        crew = self.carregar_crew(openrouter_model="qwen/qwen3-coder:free")
        s = Sessao(ok={"google/gemini-2.0-flash-exp:free"},
                   status_modelo={"qwen/qwen3-coder:free": (404, {}, "unavailable for free")})
        with mock.patch.object(mh, "CACHE_ARQUIVO", os.path.join(tempfile.gettempdir(), "x_nao_existe.json")), \
                mock.patch.object(mh.requests, "post", side_effect=s.post), mock.patch.object(mh.requests, "get", side_effect=s.get):
            llm = crew.get_llm()
        self.assertEqual(llm.model, "openai/google/gemini-2.0-flash-exp:free")

    def test_sem_gratuito_cai_para_gemini(self):
        crew = self.carregar_crew(gemini_api_key="G")
        with mock.patch.object(mh, "resolver_modelo", return_value=None):
            llm = crew.get_llm()
        self.assertEqual(llm.model, "gemini/x")

    def test_sem_gratuito_e_sem_outra_chave_para_com_erro_claro(self):
        crew = self.carregar_crew()
        with mock.patch.object(mh, "resolver_modelo", return_value=None):
            with self.assertRaises(RuntimeError):
                crew.get_llm()


if __name__ == "__main__":
    unittest.main()

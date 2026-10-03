import json
import os
import tempfile
import unittest

from tests import stubs
stubs.instalar()

from fabrica_produtos import catalogo, fabrica, config_fabrica as cfg  # noqa: E402
from tests.fixtures import capitulo, json_do_produto, produto_bom  # noqa: E402

OK = json.dumps({"problemas_graves": [], "ajustes": []})


class Roteiro:
    """Executor falso: devolve respostas na ordem e guarda os prompts recebidos."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, papel, descricao, saida, evitar):
        self.chamadas.append((papel, descricao, evitar))
        item = self.respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, ("gemini" if papel == "criador" else "groq")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg.CATALOGO_PATH = os.path.join(self.tmp.name, "catalogo.json")


class Fluxo(Base):
    def test_aprova_de_primeira(self):
        ex = Roteiro(json_do_produto(), OK)
        res = fabrica.fabricar("Rotina", executor=ex)
        self.assertEqual(res["status"], "aprovado")
        self.assertEqual(len(res["rodadas"]), 1)
        self.assertEqual([c[0] for c in ex.chamadas], ["criador", "orientador"])
        self.assertEqual(ex.chamadas[1][2], "gemini")  # orientador deve evitar o provedor do criador

    def test_orientador_pede_correcao_e_criador_corrige(self):
        ruim = produto_bom(promessa="Faça a sua primeira venda em 7 dias")
        ex = Roteiro(json_do_produto(ruim), json.dumps({"problemas_graves": ["Remova a promessa de venda"],
                                                       "ajustes": []}),
                     json_do_produto(), OK)
        res = fabrica.fabricar("Rotina", executor=ex)
        self.assertEqual(res["status"], "aprovado")
        self.assertEqual(len(res["rodadas"]), 2)
        # a 2ª chamada ao criador recebe o feedback do orientador E o da trava de código
        prompt_correcao = ex.chamadas[2][1]
        self.assertIn("Remova a promessa de venda", prompt_correcao)
        self.assertIn("termo proibido", prompt_correcao)

    def test_orientador_aprovando_nao_vence_a_trava_de_codigo(self):
        ruim = produto_bom(promessa="Ganhe lucro rápido")
        ex = Roteiro(json_do_produto(ruim), OK, json_do_produto(ruim), OK, json_do_produto(ruim), OK,
                     OK)  # a última OK é a conferência da saída de reserva
        res = fabrica.fabricar("Rotina", executor=ex)
        # as travas pegam nas 3 rodadas; a reserva remove o trecho e aprova
        self.assertEqual(res["status"], "aprovado")
        self.assertEqual(res["rodadas"][-1]["rodada"], "reserva")
        self.assertNotIn("lucro", res["produto"]["promessa"].lower())

    def test_reserva_reprova_quando_nao_da_para_sanear(self):
        ruim = produto_bom(nome="Primeira venda garantida")
        ex = Roteiro(*([json_do_produto(ruim), OK] * 3 + [OK]))
        res = fabrica.fabricar("Rotina", executor=ex)
        self.assertEqual(res["status"], "reprovado")
        self.assertIn("travas de código", res["motivo"])

    def test_resposta_do_criador_nao_json_gasta_rodada_e_recupera(self):
        ex = Roteiro("desculpe, não consegui", json_do_produto(), OK)
        res = fabrica.fabricar("Rotina", executor=ex)
        self.assertEqual(res["status"], "aprovado")
        self.assertIn("JSON", ex.chamadas[1][1])  # o feedback pede JSON válido

    def test_sem_provedor_adia_sem_reprovar(self):
        res = fabrica.fabricar("Rotina", executor=Roteiro(RuntimeError("todos falharam")))
        self.assertEqual(res["status"], "adiado")
        self.assertIsNone(res["produto"])

    def test_orientador_fora_do_ar_nao_trava_se_nunca_houve_problema_grave(self):
        ex = Roteiro(json_do_produto(), RuntimeError("fora"), json_do_produto(), RuntimeError("fora"),
                     json_do_produto(), RuntimeError("fora"), RuntimeError("fora"))
        res = fabrica.fabricar("Rotina", executor=ex)
        self.assertEqual(res["status"], "aprovado")
        self.assertIn("orientador indisponível", res["aprovado_por"])

    def test_orientador_fora_do_ar_depois_de_apontar_grave_reprova(self):
        grave = json.dumps({"problemas_graves": ["capítulo 2 está vazio de conteúdo real"], "ajustes": []})
        ex = Roteiro(json_do_produto(), grave, json_do_produto(), grave, json_do_produto(), grave,
                     RuntimeError("fora"))
        res = fabrica.fabricar("Rotina", executor=ex)
        self.assertEqual(res["status"], "reprovado")

    def test_nome_repetido_exige_outro(self):
        catalogo.adicionar(produto_bom(), "aprovado", "x")
        ex = Roteiro(json_do_produto(), OK, json_do_produto(produto_bom("Outro Guia Diferente")), OK)
        res = fabrica.fabricar("Rotina", executor=ex)
        self.assertEqual(res["produto"]["nome"], "Outro Guia Diferente")

    def test_criar_e_guardar_registra_no_catalogo(self):
        res = fabrica.criar_e_guardar("Rotina", executor=Roteiro(json_do_produto(), OK))
        self.assertEqual(catalogo.obter(res["registro"]["id"])["status"], "aprovado")
        self.assertIn("Fábrica de produtos: APROVADO", fabrica.resumo_markdown(res))

    def test_adiado_nao_grava_nada(self):
        fabrica.criar_e_guardar("Rotina", executor=Roteiro(RuntimeError("x")))
        self.assertEqual(catalogo.carregar()["produtos"], [])


class Parsing(unittest.TestCase):
    def test_extrair_json_com_cercas_e_texto(self):
        d = fabrica.extrair_json('Claro!\n```json\n{"a": {"b": 1}, "c": "x"}\n```\nPronto.')
        self.assertEqual(d["a"]["b"], 1)

    def test_extrair_json_invalido(self):
        self.assertIsNone(fabrica.extrair_json("sem json aqui { quebrado"))

    def test_normalizar_exige_nome_e_capitulos(self):
        self.assertIsNone(fabrica.normalizar_candidato({"nome": "x"}))
        self.assertIsNone(fabrica.normalizar_candidato({"capitulos": [{"texto": "a"}]}))
        n = fabrica.normalizar_candidato({"nome": "G", "preco": "R$ 7,00", "capitulos": [capitulo("a")]})
        self.assertEqual(n["preco"], 7.0)

    def test_prompts_nao_tem_chaves_que_o_crewai_interpretaria(self):
        p = produto_bom(promessa="Texto com {chave} dentro")
        self.assertNotIn("{", fabrica.produto_em_texto(p))
        self.assertNotIn("{", fabrica.prompt_criador("tema {x}", ["Nome {y}"], ["fb {z}"], p))

    def test_parse_orientacao(self):
        self.assertEqual(fabrica.parse_orientacao(OK)["graves"], [])
        self.assertIsNone(fabrica.parse_orientacao("texto solto")["graves"])


class Modelos(unittest.TestCase):
    def test_orientador_evita_provedor_do_criador(self):
        from fabrica_produtos import llms
        antigo = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(antigo)))
        for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        os.environ["GEMINI_API_KEY"] = "x"
        os.environ["GROQ_API_KEY"] = "y"
        c = llms.candidatos("orientador", evitar="gemini")
        self.assertEqual(c[0]["provedor"], "groq")
        self.assertEqual(c[-1]["provedor"], "gemini")
        self.assertNotEqual(c[-1]["modelo"], llms.modelo_padrao("gemini"))  # modelo alternativo na última reserva
        del os.environ["GROQ_API_KEY"]
        self.assertEqual([x["provedor"] for x in llms.candidatos("orientador", evitar="gemini")], ["gemini"])
        del os.environ["GEMINI_API_KEY"]
        with self.assertRaises(RuntimeError):
            llms.candidatos("criador")


if __name__ == "__main__":
    unittest.main()

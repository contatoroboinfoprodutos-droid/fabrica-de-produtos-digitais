"""Guardião: reconhece a causa nos logs (mensagens reais dos robôs) e nunca vaza segredo."""
import os
import tempfile
import unittest

from fabrica_produtos import __main__ as cli, guardiao

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def principal(log):
    achados = guardiao.diagnosticar(log)
    return achados[0]["id"] if achados else None


class Diagnostico(unittest.TestCase):
    def test_causas_reconhecidas_com_mensagens_reais(self):
        casos = {
            "meta_token": "A Meta recusou o token (código 190: Error validating access token: Session has expired on "
                          "Friday, 25-Sep-26 22:00:00 PDT.). Token expirado não pode ser renovado",
            "uma_rede": "::error::Só uma das redes publicou (Facebook ou Instagram). Confira as duas",
            "gh_secret": "Não consegui gravar o Secret. O token do GitHub (GH_SECRETS_TOKEN / GH_MODELS_KEY) precisa",
            "sem_produto": "Nenhum produto 'pronto' no catálogo: sem produto real não há o que anunciar.",
            "sem_imagem": "Sem imagem. Defina UNSPLASH_API_KEY (busca automática)",
            "drive_cota": "drive: o Google recusou o envio por falta de cota: contas de serviço não têm armazenamento",
            "drive_pasta": "drive: GET recusado (HTTP 404) notFound: File not found: PASTA1",
            "drive_credencial": "drive: o JSON da conta de serviço é inválido",
            "cakto_auth": "cakto: autenticação recusada (HTTP 401)",
            "cakto_escopo": "cakto: POST /public_api/products/ recusado (HTTP 403)",
            "cakto_dados": "cakto: POST /public_api/products/ recusado (HTTP 422): {\"price\": [\"inválido\"]}",
            "cakto_rede": "cakto: falha de rede em GET /public_api/products/ (ConnectTimeout)",
            "ia_limite": "litellm.RateLimitError: GeminiException - 429 RESOURCE_EXHAUSTED",
            "ia_indisponivel": "Modelo gemini-3.8-flash respondeu HTTP 503",
            "dependencias": "ModuleNotFoundError: No module named 'reportlab'",
        }
        for esperado, log in casos.items():
            self.assertEqual(principal(log), esperado, esperado)

    def test_prioridade_token_meta_antes_do_resto(self):
        log = "HTTP 429 rate limit\nA Meta recusou o token (código 190: Session has expired)"
        self.assertEqual(principal(log), "meta_token")

    def test_causa_nao_reconhecida(self):
        self.assertEqual(guardiao.diagnosticar("tudo certo mas algo estranho aconteceu"), [])
        titulo, corpo = guardiao.montar_issue("Robô X", "https://exemplo/run/1", "linha qualquer\nError: boom")
        self.assertIn("causa não reconhecida", titulo)
        self.assertIn("Error: boom", corpo)

    def test_transitoria_so_para_causas_passageiras(self):
        self.assertTrue(guardiao.diagnosticar("HTTP 503")[0]["transitoria"])
        self.assertFalse(guardiao.diagnosticar("código 190")[0]["transitoria"])


class Segredos(unittest.TestCase):
    def test_limpar_remove_chaves_e_tokens(self):
        sujo = ("access_token=EAAGm0PX4ZCpsBAKexemplo1234567890abcdef Authorization: Bearer abcdef1234567890ABCDEF "
                "GEMINI=AIzaSyA1234567890abcdefghijklmnopqrstuv gsk_abcdefghijklmnopqrstuvwx "
                "ghp_abcdefghijklmnopqrstuvwxyz0123 client_secret: s3cr3tvalor-longo sk-abcdefghijklmnopqrstuv")
        limpo = guardiao.limpar(sujo)
        for pedaco in ("EAAGm0PX4", "abcdef1234567890ABCDEF", "AIzaSyA12345", "gsk_abcdef", "ghp_abcdef",
                       "s3cr3tvalor", "sk-abcdefghij"):
            self.assertNotIn(pedaco, limpo, pedaco)

    def test_issue_nunca_contem_segredo(self):
        log = "2026-10-04T03:44:47.1Z Error: HTTP 401 access_token=EAAGm0PX4ZCpsBAKexemplo1234567890abcdef\n"
        titulo, corpo = guardiao.montar_issue("Robô X", "https://exemplo/run/1", log)
        self.assertNotIn("EAAGm0PX4", corpo + titulo)
        self.assertNotIn("2026-10-04T03:44", corpo)  # prefixo de data removido do trecho


class Issue(unittest.TestCase):
    def test_titulo_estavel_para_nao_duplicar_issue(self):
        log = "Modelo gemini-3.8-flash respondeu HTTP 503"
        t1, _ = guardiao.montar_issue("Low Ticket (2 posts/dia)", "https://exemplo/run/1", log)
        t2, _ = guardiao.montar_issue("Low Ticket (2 posts/dia)", "https://exemplo/run/2", log)
        self.assertEqual(t1, t2)
        self.assertEqual(t1, "Falha: Low Ticket (2 posts/dia) — Provedor de IA temporariamente indisponível")

    def test_corpo_explica_o_que_foi_e_o_que_nao_foi_feito(self):
        _, corpo = guardiao.montar_issue("Renovar token da Meta", "https://exemplo/run/9", "código 190")
        self.assertIn("## Como corrigir", corpo)
        self.assertIn("META_SHORT_LIVED_TOKEN", corpo)
        self.assertIn("Só diagnosticou", corpo)
        self.assertIn("https://exemplo/run/9", corpo)

    def test_trecho_do_erro_e_limitado(self):
        log = "\n".join(f"linha normal {i}" for i in range(500)) + "\nError: final"
        trecho = guardiao.trecho_do_erro(log)
        self.assertIn("Error: final", trecho)
        self.assertLessEqual(len(trecho.splitlines()), 25)

    def test_comando_grava_titulo_e_corpo(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "log.txt")
            with open(log, "w", encoding="utf-8") as f:
                f.write("cakto: autenticação recusada (HTTP 401)\n")
            rc = cli.main(["guardiao", "--workflow", "Fabrica de Produtos", "--run-url", "https://x/1",
                           "--log", log, "--saida-titulo", os.path.join(d, "t"), "--saida-corpo", os.path.join(d, "c")])
            self.assertEqual(rc, 0)
            with open(os.path.join(d, "t"), encoding="utf-8") as f:
                self.assertIn("Cakto recusou o login", f.read())

    def test_comando_com_log_ausente_nao_quebra(self):
        with tempfile.TemporaryDirectory() as d:
            rc = cli.main(["guardiao", "--workflow", "X", "--run-url", "https://x/1",
                           "--log", os.path.join(d, "nao-existe.txt"),
                           "--saida-titulo", os.path.join(d, "t"), "--saida-corpo", os.path.join(d, "c")])
            self.assertEqual(rc, 0)


class WorkflowDoGuardiao(unittest.TestCase):
    def test_vigia_exatamente_os_workflows_que_existem(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML ausente")
        pasta = os.path.join(RAIZ, ".github", "workflows")
        nomes = {}
        for arq in os.listdir(pasta):
            with open(os.path.join(pasta, arq), encoding="utf-8") as f:
                nomes[arq] = yaml.safe_load(f)["name"]
        with open(os.path.join(pasta, "guardiao.yml"), encoding="utf-8") as f:
            vigiados = set(yaml.safe_load(f)[True]["workflow_run"]["workflows"])
        esperados = {nomes[a] for a in ("lowticket.yml", "main.yml", "produto.yml", "renew-meta-token.yml")}
        self.assertEqual(vigiados, esperados)
        self.assertNotIn(nomes["guardiao.yml"], vigiados)  # o guardião não vigia a si mesmo (evita laço)


if __name__ == "__main__":
    unittest.main()

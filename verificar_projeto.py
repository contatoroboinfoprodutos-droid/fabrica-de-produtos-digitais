"""Verifica a estrutura e os arquivos do projeto (somente leitura, não altera nada).
Uso (na pasta do projeto, com o venv ativo):  python verificar_projeto.py"""
import ast
import os
import re
import sys

RAIZ = os.getcwd()
IGNORAR = {"venv", ".venv", ".git", "__pycache__", "node_modules", "output_lowticket"}
ok_count = fail_count = warn_count = 0


def ok(msg):
    global ok_count
    ok_count += 1
    print(f"  [OK]    {msg}")


def falha(msg):
    global fail_count
    fail_count += 1
    print(f"  [FALHA] {msg}")


def aviso(msg):
    global warn_count
    warn_count += 1
    print(f"  [AVISO] {msg}")


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def existe(rel):
    return os.path.exists(os.path.join(RAIZ, rel))


def todos_arquivos():
    for base, dirs, files in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for n in files:
            yield os.path.relpath(os.path.join(base, n), RAIZ).replace("\\", "/")


arquivos = list(todos_arquivos())

print("\n1) Estrutura esperada")
esperados = [
    "main.py", "crew.py", "config.py", "requirements.txt",
    "config/agents.yaml", "config/tasks.yaml",
    "tools/__init__.py", "tools/crewai_meta_tools.py", "tools/meta_graph_api.py",
    ".github/workflows/main.yml", ".github/workflows/lowticket.yml",
    "infoprodutos_lowticket/__init__.py", "infoprodutos_lowticket/config_lt.py",
    "infoprodutos_lowticket/tools_lt.py", "infoprodutos_lowticket/agents.py",
    "infoprodutos_lowticket/tasks.py", "infoprodutos_lowticket/crew.py",
    "infoprodutos_lowticket/run_lowticket.py", "infoprodutos_lowticket/requirements_lowticket.txt",
]
for e in esperados:
    ok(e) if existe(e) else falha(f"faltando: {e}")

print("\n2) Arquivos soltos / fora do lugar")
permitidos_raiz = {"main.py", "crew.py", "config.py", "requirements.txt", "README.md", ".gitignore",
                   ".env", ".env.example", "verificar_projeto.py", "aplicar_gemini.py"}
soltos = [a for a in arquivos if "/" not in a and a not in permitidos_raiz
          and not a.endswith((".bak", ".txt", ".log", ".yml", ".yaml"))]
extras_txt = [a for a in arquivos if "/" not in a and a.endswith((".txt", ".log", ".bak"))
              and a != "requirements.txt"]
if soltos:
    for s in soltos:
        falha(f"arquivo solto na raiz (deveria estar em pasta): {s}")
else:
    ok("nenhum arquivo de código solto na raiz")
for s in extras_txt:
    aviso(f"arquivo auxiliar na raiz (não deve ir para o Git): {s}")
for a in arquivos:
    if "/" not in a and a.endswith((".yml", ".yaml")):
        falha(f"{a} está na raiz (yaml do robô vai em config/, workflows em .github/workflows/)")

print("\n3) Sintaxe dos arquivos Python")
arvores = {}
erros_sintaxe = 0
for a in arquivos:
    if a.endswith(".py"):
        try:
            arvores[a] = ast.parse(ler(a))
        except SyntaxError as e:
            erros_sintaxe += 1
            falha(f"{a}: erro de sintaxe linha {e.lineno}: {e.msg}")
if erros_sintaxe == 0:
    ok(f"{len(arvores)} arquivos .py sem erro de sintaxe")

print("\n4) Isolamento do crew novo")
MODULOS_RAIZ = {"config", "crew", "main", "tools"}
for a, arv in arvores.items():
    if not a.startswith("infoprodutos_lowticket/"):
        continue
    for n in ast.walk(arv):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            if n.module.split(".")[0] in MODULOS_RAIZ:
                falha(f"{a} importa módulo do projeto original: {n.module}")
        if isinstance(n, ast.Import):
            for al in n.names:
                if al.name.split(".")[0] in MODULOS_RAIZ:
                    falha(f"{a} importa módulo do projeto original: {al.name}")
for a, arv in arvores.items():
    if "/" in a:
        continue
    for n in ast.walk(arv):
        mod = getattr(n, "module", None) or ""
        nomes = [x.name for x in getattr(n, "names", [])] if isinstance(n, ast.Import) else []
        if "infoprodutos_lowticket" in mod or any("infoprodutos_lowticket" in x for x in nomes):
            aviso(f"{a} usa o crew novo (ok se intencional; mantenha desacoplado)")
if existe("crew.py") and "class InfoprodutoFactoryCrew" in ler("crew.py"):
    ok("crew.py da raiz é o do robô original (InfoprodutoFactoryCrew)")
elif existe("crew.py"):
    falha("crew.py da raiz NÃO contém InfoprodutoFactoryCrew (foi sobrescrito?)")
if existe("infoprodutos_lowticket/crew.py") and "crew_infoprodutos_lowticket" in ler("infoprodutos_lowticket/crew.py"):
    ok("crew novo contém crew_infoprodutos_lowticket")
else:
    falha("infoprodutos_lowticket/crew.py sem crew_infoprodutos_lowticket")

print("\n5) Agents, tasks e tools do crew novo (nomes únicos)")
if existe("infoprodutos_lowticket/agents.py"):
    txt = ler("infoprodutos_lowticket/agents.py")
    for nome in ["trend_scout_agent", "copywriter_lowticket_agent",
                 "visual_director_agent", "publisher_infoproduto_agent"]:
        ok(nome) if re.search(rf"^{nome}\s*=", txt, re.M) else falha(f"agent ausente: {nome}")
orig = set()
if existe("crew.py"):
    orig |= set(re.findall(r"def (\w+)\(self\) -> (?:Agent|Task)", ler("crew.py")))
novos = set()
for f in ("infoprodutos_lowticket/agents.py", "infoprodutos_lowticket/tasks.py"):
    if existe(f):
        novos |= set(re.findall(r"^(\w+)\s*=\s*(?:Agent|Task)\(", ler(f), re.M))
colisao = orig & novos
falha(f"nomes repetidos entre crews: {sorted(colisao)}") if colisao else ok("nenhum nome de agent/task repetido")
tools_orig = set()
if existe("tools/crewai_meta_tools.py"):
    tools_orig = set(re.findall(r'name:\s*str\s*=\s*"(\w+)"', ler("tools/crewai_meta_tools.py")))
tools_novas = set(re.findall(r'@tool\("(\w+)"\)', ler("infoprodutos_lowticket/tools_lt.py"))) \
    if existe("infoprodutos_lowticket/tools_lt.py") else set()
c2 = tools_orig & tools_novas
falha(f"tools com nome repetido: {sorted(c2)}") if c2 else ok(f"tools únicas: {sorted(tools_novas)}")

print("\n6) YAML do robô original x crew.py")
try:
    import yaml
except ImportError:
    yaml = None
    aviso("PyYAML não instalado; pulando conferência dos yamls")
if yaml and existe("crew.py") and existe("config/agents.yaml") and existe("config/tasks.yaml"):
    ag = yaml.safe_load(ler("config/agents.yaml")) or {}
    tk = yaml.safe_load(ler("config/tasks.yaml")) or {}
    c = ler("crew.py")
    for k in re.findall(r'self\.agents_config\["(\w+)"\]', c):
        ok(f"agents.yaml tem '{k}'") if k in ag else falha(f"agents.yaml sem a chave '{k}'")
    for k in re.findall(r'self\.tasks_config\["(\w+)"\]', c):
        ok(f"tasks.yaml tem '{k}'") if k in tk else falha(f"tasks.yaml sem a chave '{k}'")

print("\n7) Correção do Gemini (aplicar_gemini.py)")
if existe("config.py") and "llm_provider" in ler("config.py"):
    ok("config.py com LLM_PROVIDER")
else:
    falha("config.py sem LLM_PROVIDER (rode: python aplicar_gemini.py)")
if existe("crew.py") and "settings.llm_provider" in ler("crew.py"):
    ok("crew.py escolhe o LLM pelo provedor")
else:
    falha("crew.py sem a escolha de provedor (rode: python aplicar_gemini.py)")
if existe(".github/workflows/main.yml") and "GEMINI_API_KEY" in ler(".github/workflows/main.yml"):
    ok("main.yml passa GEMINI_API_KEY")
else:
    falha("main.yml sem GEMINI_API_KEY")

print("\n8) Segredos e .gitignore")
padroes = [r"gsk_[A-Za-z0-9]{20,}", r"AIza[0-9A-Za-z_\-]{30,}", r"EAA[A-Za-z0-9]{30,}",
           r"ghp_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}"]
achou = False
for a in arquivos:
    if a.endswith((".py", ".yml", ".yaml", ".md", ".txt", ".json")) and a not in ("verificar_projeto.py",):
        try:
            t = ler(a)
        except OSError:
            continue
        for p in padroes:
            if re.search(p, t):
                falha(f"possível chave real em {a}")
                achou = True
if not achou:
    ok("nenhuma chave real encontrada nos arquivos")
gi = ler(".gitignore").splitlines() if existe(".gitignore") else []
gi = [x.strip() for x in gi]
for item in [".env", "venv/"]:
    if item in gi or item.rstrip("/") in gi:
        ok(f".gitignore ignora {item}")
    else:
        falha(f".gitignore NÃO ignora {item}")

print("\n9) Workflows")
if existe(".github/workflows/lowticket.yml"):
    w = ler(".github/workflows/lowticket.yml")
    ok("lowticket.yml tem cron") if "cron" in w else falha("lowticket.yml sem cron")
    ok("lowticket.yml usa o módulo do crew novo") if "infoprodutos_lowticket.run_lowticket" in w else falha("lowticket.yml não chama run_lowticket")

print("\n" + "=" * 60)
print(f"Resultado: {ok_count} OK | {warn_count} avisos | {fail_count} falhas")
print("PROJETO OK" if fail_count == 0 else "CORRIJA AS FALHAS ACIMA ANTES DE ENVIAR AO GITHUB")
sys.exit(1 if fail_count else 0)

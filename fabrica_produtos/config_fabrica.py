"""Configuração da fábrica de produtos. Tudo vem de variáveis de ambiente (nunca de valores fixos
de segredo). Padrões seguros: simulação ligada e fábrica ativa."""
import os


def _bool(nome: str, padrao: bool) -> bool:
    v = os.getenv(nome, "").strip().lower()
    if not v:
        return padrao
    return v in ("1", "true", "t", "yes", "y", "sim")


def _num(nome: str, padrao: float) -> float:
    try:
        return float(os.getenv(nome, "").strip().replace(",", "."))
    except ValueError:
        return padrao


# --- Interruptores ---
DRY_RUN = _bool("FABRICA_DRY_RUN", True)      # True: não cria nada nas plataformas (só lê)
PAUSADA = _bool("FABRICA_PAUSADA", False)     # True: a fábrica não cria produto novo
MAX_PRODUTOS_POR_DIA = int(_num("FABRICA_MAX_POR_DIA", 1))
MAX_RODADAS = max(1, int(_num("FABRICA_MAX_RODADAS", 3)))

# --- Onde ficam os dados (versionados no repositório) ---
CATALOGO_PATH = os.getenv("FABRICA_CATALOGO", "").strip() or "catalogo/catalogo.json"
PACOTES_DIR = os.getenv("FABRICA_PACOTES", "").strip() or "catalogo/pacotes"

# --- Regras do produto ---
PRECO_MIN = _num("FABRICA_PRECO_MIN", 7.00)
PRECO_MAX = _num("FABRICA_PRECO_MAX", 9.90)   # linha de entrada; suba só se o conteúdo crescer
MIN_CONTEUDOS = 3
MAX_CONTEUDOS = 5

# --- Plataformas onde o registrador atua ---
PLATAFORMAS_ALVO = [p.strip().lower() for p in
                    (os.getenv("FABRICA_PLATAFORMAS", "").strip() or "kiwify,hotmart").split(",")
                    if p.strip()]

# --- Marca (para o PDF) ---
MARCA = os.getenv("LT_BRAND_NAME", "").strip() or "Digital Rápido"

# --- Temas em rodízio quando ninguém define PRODUTO_TOPICO ---
NICHOS = [
    "Finanças pessoais para iniciantes",
    "Produtividade e organização da rotina",
    "Receitas fit e alimentação saudável",
    "Inglês para o dia a dia",
    "Marketing digital para pequenos negócios",
    "Redação e copywriting",
    "Estudos e concentração",
    "Organização do home office",
]

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
MAX_PRODUTOS_POR_DIA = int(_num("FABRICA_MAX_POR_DIA", 5))   # teto por dia; cada execução "criar" faz 1 produto
LLM_TIMEOUT = _num("FABRICA_LLM_TIMEOUT", 240)                # segundos por chamada de IA (sem isso uma chamada pode travar por horas)
MAX_RODADAS = max(1, int(_num("FABRICA_MAX_RODADAS", 3)))

# --- Onde ficam os dados (versionados no repositório) ---
CATALOGO_PATH = os.getenv("FABRICA_CATALOGO", "").strip() or "catalogo/catalogo.json"
PACOTES_DIR = os.getenv("FABRICA_PACOTES", "").strip() or "catalogo/pacotes"

# --- Regras do produto ---
PRECO_MIN = _num("FABRICA_PRECO_MIN", 7.00)
PRECO_MAX = _num("FABRICA_PRECO_MAX", 27.90)  # teto: vale o do combo; o conteúdo mínimo cresce com o preço (travas.palavras_minimas)
# Níveis de produto: o preço é FIXO por nível e definido em código (a IA não escolhe preço).
TIPOS = {"guia": 8.90, "pacote": 19.90, "combo": 27.90}
ROTULOS = {"guia": "Guia", "pacote": "Pacote", "combo": "Combo premium"}
ROTACAO = ("guia", "guia", "pacote", "guia", "pacote", "combo")   # ciclo de 6 produtos
# FABRICA_TIPOS=guia deixa tudo em R$ 8,90 (volta ao comportamento antigo); aceita "guia,pacote,combo".
TIPOS_ATIVOS = [t.strip().lower() for t in (os.getenv("FABRICA_TIPOS", "").strip() or "guia,pacote,combo").split(",")
                if t.strip().lower() in TIPOS] or ["guia"]
MIN_CONTEUDOS = 3
MAX_CONTEUDOS = 5

# --- Links de chamada (CTA) das legendas: um por rede. O Instagram não abre link na legenda, mas o texto mostra o endereço da bio. ---
LINK_BIO_INSTAGRAM = os.getenv("LINK_BIO_INSTAGRAM", "").strip() or "https://fabricadeprodutosdigitais.github.io/fabrica-de-produtos-digitais/"
LINK_FACEBOOK = os.getenv("LINK_FACEBOOK", "").strip() or "bit.ly/4ibGb7a"

# --- Plataformas onde o registrador atua ---
PLATAFORMAS_ALVO = [p.strip().lower() for p in
                    (os.getenv("FABRICA_PLATAFORMAS", "").strip() or "cakto").split(",")
                    if p.strip()]

# --- Marca (para o PDF) ---
MARCA = os.getenv("LT_BRAND_NAME", "").strip() or "Fábrica de Produtos Digitais"

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

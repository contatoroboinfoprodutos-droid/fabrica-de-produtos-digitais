"""Utilitários de texto (biblioteca padrão apenas)."""
import re
import unicodedata


def sem_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def normalizar(s: str) -> str:
    """minúsculas, sem acentos, só letras/números separados por um espaço (para comparar nomes)."""
    s = sem_acentos(s).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def contar_palavras(s: str) -> int:
    return len(re.findall(r"\w+", s or "", flags=re.UNICODE))


def parse_preco(valor) -> float | None:
    """Aceita 7, 7.0, '7,00', 'R$ 7,00', 'R$7' e devolve float (ou None)."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)", str(valor or "").replace(" ", ""))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def formatar_preco(valor: float) -> str:
    return "R$ " + f"{valor:.2f}".replace(".", ",")

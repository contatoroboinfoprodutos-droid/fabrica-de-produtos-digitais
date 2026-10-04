"""Marcas de publicação: permitem repetir a execução de um robô de anúncio sem NUNCA postar em duplicidade.

Como funciona: quando a variável POST_MARKER_DIR aponta para uma pasta (o workflow usa uma pasta nova a cada
execução), cada publicação que a Meta aceitou grava ali uma marca por rede ("facebook", "instagram").
  - uma nova tentativa não repete a rede que já tem marca (as ferramentas respondem "já publicado");
  - o workflow só repete a tentativa se ainda faltar rede e não houver bloqueio definitivo;
  - bloqueio definitivo (ex.: não há produto pronto) encerra sem gastar mais tokens com tentativas inúteis.
Sem POST_MARKER_DIR (uso local, testes, simulação) nada disso é gravado. Biblioteca padrão apenas.
"""
import json
import os
import tempfile

REDES = ("facebook", "instagram")


def _pasta() -> str | None:
    return os.getenv("POST_MARKER_DIR", "").strip() or None


def ativa() -> bool:
    return _pasta() is not None


def _escrever(nome: str, dados: dict) -> None:
    pasta = _pasta()
    if not pasta:
        return
    os.makedirs(pasta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=pasta, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(pasta, nome + ".json"))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _ler(nome: str) -> dict | None:
    pasta = _pasta()
    if not pasta:
        return None
    try:
        with open(os.path.join(pasta, nome + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def marcar(rede: str, dados: dict | None = None) -> None:
    """Registra que a rede aceitou a publicação (`dados` guarda o que a próxima tentativa precisar)."""
    _escrever(f"publicado_{rede}", dados or {"ok": True})


def lido(rede: str) -> dict | None:
    return _ler(f"publicado_{rede}")


def ja_publicado(rede: str) -> bool:
    return lido(rede) is not None


def marcar_bloqueio(motivo: str) -> None:
    """Bloqueio que repetir não resolve (sem produto pronto, credenciais ausentes...)."""
    _escrever("bloqueio", {"motivo": motivo})


def bloqueio() -> str | None:
    d = _ler("bloqueio")
    return str(d.get("motivo", "")) if d else None


def estado(redes: tuple[str, ...] = REDES) -> str:
    """'completo' (todas as redes publicadas), 'bloqueado', 'parcial' (só algumas) ou 'nada'."""
    feitas = [r for r in redes if ja_publicado(r)]
    if len(feitas) == len(redes):
        return "completo"
    if bloqueio() is not None:
        return "bloqueado"
    return "parcial" if feitas else "nada"

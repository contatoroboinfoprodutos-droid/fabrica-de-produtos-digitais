#!/usr/bin/env python3
"""Tenta baixar 3 músicas de fundo (happy, lofi, corporate) para assets/music/ usando a API da Pixabay.

Nunca quebra o fluxo: sem PIXABAY_API_KEY, sem resultado, erro de rede ou arquivo que não seja áudio => pula e avisa.
Não sobrescreve um mp3 que já exista e seja válido (o que você colocar à mão em assets/music/ vale mais).

ATENÇÃO: a documentação pública da Pixabay (pixabay.com/api/docs/) descreve só os endpoints de imagens e de vídeos.
O endpoint de música abaixo não está documentado; se ele não existir, este script avisa e pula, e os Reels saem sem áudio
até você colocar os mp3 em assets/music/.
"""
import os
import sys

SEM_API = "Pixabay Music sem API - usando mp3 manuais de assets/music/"
ENDPOINT = os.getenv("PIXABAY_MUSIC_ENDPOINT", "").strip() or "https://pixabay.com/api/music/"
PASTA = os.getenv("REELS_MUSICA", "").strip() or "assets/music"
FAIXAS = {
    "happy": "happy cooking acoustic",
    "lofi": "lofi chill study",
    "corporate": "corporate uplifting",
}
LIMITE_BYTES = 15 * 1024 * 1024
MIN_BYTES = 10 * 1024


def parece_mp3(dados: bytes) -> bool:
    """ID3 no começo, ou quadro MPEG (0xFF 0xE0+). Barra HTML de erro e arquivo cortado."""
    return len(dados) >= MIN_BYTES and (dados[:3] == b"ID3" or (dados[0] == 0xFF and (dados[1] & 0xE0) == 0xE0))


def ja_tem(arq: str) -> bool:
    try:
        with open(arq, "rb") as f:
            return parece_mp3(f.read(MIN_BYTES))
    except OSError:
        return False


def link_do_hit(hit: dict) -> str | None:
    for chave in ("download", "audio", "url", "downloadURL"):
        v = hit.get(chave) if isinstance(hit, dict) else None
        if isinstance(v, dict):
            v = v.get("url") or v.get("mp3")
        if isinstance(v, str) and v.startswith("https://"):
            return v
    return None


def baixar(nome: str, consulta: str, chave: str, http=None) -> str:
    """Devolve uma frase de status (nunca levanta). A chave nunca aparece nas mensagens."""
    destino = os.path.join(PASTA, nome + ".mp3")
    if ja_tem(destino):
        return f"{nome}.mp3: já existe, mantido"
    try:
        http = http or __import__("requests")
        r = http.get(ENDPOINT, params={"key": chave, "q": consulta, "per_page": 3}, timeout=30)
        if r.status_code in (404, 405, 410):
            return f"{nome}.mp3: {SEM_API}"
        if r.status_code != 200:
            return f"{nome}.mp3: a Pixabay respondeu HTTP {r.status_code}; pulado ({SEM_API})"
        try:
            hits = r.json().get("hits") or []
        except (ValueError, AttributeError):
            return f"{nome}.mp3: {SEM_API}"
        url = link_do_hit(hits[0]) if hits else None
        if not url:
            return f"{nome}.mp3: nenhum resultado com link de download para '{consulta}'; pulado"
        a = http.get(url, timeout=60, stream=True)
        if a.status_code != 200:
            return f"{nome}.mp3: download recusado (HTTP {a.status_code}); pulado"
        dados = b""
        for pedaco in a.iter_content(65536):
            dados += pedaco
            if len(dados) > LIMITE_BYTES:
                return f"{nome}.mp3: arquivo maior que 15 MB; pulado"
        if not parece_mp3(dados):
            return f"{nome}.mp3: o que veio não é um mp3 válido; pulado"
        os.makedirs(PASTA, exist_ok=True)
        with open(destino + ".tmp", "wb") as f:
            f.write(dados)
        os.replace(destino + ".tmp", destino)
        return f"{nome}.mp3: baixado ({len(dados) // 1024} KB)"
    except Exception as e:  # noqa: BLE001 - rede, SSL, disco: nada disso pode derrubar o workflow
        return f"{nome}.mp3: falhou ({type(e).__name__}); pulado"


def main(http=None) -> int:
    chave = os.getenv("PIXABAY_API_KEY", "").strip()
    if not chave:
        print("PIXABAY_API_KEY não definida: " + SEM_API)
        return 0
    for nome, consulta in FAIXAS.items():
        print(baixar(nome, consulta, chave, http))
    return 0


if __name__ == "__main__":
    sys.exit(main())

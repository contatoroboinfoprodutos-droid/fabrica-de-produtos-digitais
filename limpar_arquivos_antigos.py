"""
Remove as pastas obsoletas do repositorio (agents_pkg/ e tasks_pkg/), que
foram substituidas pelo crew.py unificado (padrao @CrewBase, le
config/agents.yaml e config/tasks.yaml diretamente).

Uso:
    1. Copie este arquivo para a RAIZ do repositorio clonado localmente
       (a mesma pasta onde estao main.py, crew.py, config.py).
    2. Rode:  python limpar_arquivos_antigos.py
    3. Confira o resumo impresso e responda "s" para confirmar o commit/push.

Se voce nao tiver o repositorio clonado localmente (so usa o site do
GitHub), veja a alternativa manual no final deste arquivo (comentario).
"""
import subprocess
import shutil
import sys
from pathlib import Path

# Pastas/arquivos que NAO sao mais usados pelo projeto atual.
# (crew.py agora importa direto de "config" e "tools", nao mais de
#  "agents_pkg.agents" nem "tasks_pkg.tasks")
ALVOS_PARA_REMOVER = [
    "agents_pkg",
    "tasks_pkg",
    "__pycache__",
]


def encontrar_alvos(raiz: Path) -> list[Path]:
    encontrados = []
    for nome in ALVOS_PARA_REMOVER:
        # busca em qualquer nivel do repositorio (ex.: tools/__pycache__)
        encontrados.extend(raiz.rglob(nome))
    # remove duplicatas mantendo ordem, e ignora .git/
    vistos = set()
    resultado = []
    for caminho in encontrados:
        if ".git" in caminho.parts:
            continue
        chave = str(caminho.resolve())
        if chave not in vistos:
            vistos.add(chave)
            resultado.append(caminho)
    return resultado


def main() -> None:
    raiz = Path.cwd()

    if not (raiz / ".git").exists():
        print(
            "ERRO: nenhuma pasta .git encontrada aqui. Rode este script na "
            "RAIZ do repositorio clonado (onde ficam main.py, crew.py, .git)."
        )
        sys.exit(1)

    alvos = encontrar_alvos(raiz)

    if not alvos:
        print("Nada para remover — o repositorio ja esta limpo.")
        return

    print("Os seguintes itens serao REMOVIDOS permanentemente:\n")
    for caminho in alvos:
        tipo = "pasta" if caminho.is_dir() else "arquivo"
        print(f"  - [{tipo}] {caminho.relative_to(raiz)}")

    resposta = input("\nConfirma a remocao e o commit/push dessas mudancas? (s/N): ").strip().lower()
    if resposta != "s":
        print("Cancelado. Nada foi alterado.")
        return

    for caminho in alvos:
        if caminho.is_dir():
            shutil.rmtree(caminho, ignore_errors=True)
        else:
            caminho.unlink(missing_ok=True)

    print("\nArquivos removidos localmente. Preparando commit...")

    subprocess.run(["git", "add", "-A"], check=True)
    resultado_status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"]
    )
    if resultado_status.returncode == 0:
        print("Nada novo para commitar (os arquivos ja nao estavam versionados).")
        return

    subprocess.run(
        [
            "git", "commit", "-m",
            "Remove agents_pkg/ e tasks_pkg/ (substituidos pelo crew.py unificado)",
        ],
        check=True,
    )

    resposta_push = input("Commit criado. Enviar (git push) agora? (s/N): ").strip().lower()
    if resposta_push == "s":
        subprocess.run(["git", "push"], check=True)
        print("Concluido: pastas removidas e enviadas ao GitHub.")
    else:
        print("Commit criado localmente, mas NAO enviado. Rode 'git push' quando quiser.")


if __name__ == "__main__":
    main()

# -----------------------------------------------------------------------
# ALTERNATIVA MANUAL (sem terminal/git local), direto pelo site do GitHub:
#   1. Abra agents_pkg/agents.py no repositorio -> icone de lixeira (Delete
#      this file) -> "Commit changes".
#   2. Repita para todo arquivo dentro de agents_pkg/ e de tasks_pkg/.
#   3. Quando a pasta ficar vazia, ela some sozinha da listagem (o GitHub
#      nao versiona pastas vazias).
# -----------------------------------------------------------------------

"""Faz o robô existente usar o Gemini como LLM principal (sem mexer no crew low ticket).
Uso (na pasta do projeto):  python aplicar_gemini.py
Cria backups .bak antes de alterar config.py, crew.py e .github/workflows/main.yml."""
import shutil

def patch(path, edits):
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    if all(new in txt for _, new in edits):
        print(f"{path}: já estava aplicado, nada a fazer.")
        return
    for old, new in edits:
        if old not in txt:
            raise SystemExit(f"ERRO: trecho esperado não encontrado em {path}:\n{old}\n"
                             "O arquivo foi alterado? Nada foi modificado neste arquivo.")
        txt = txt.replace(old, new, 1)
    shutil.copy(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"{path}: atualizado (backup em {path}.bak)")

patch("config.py", [
    ('groq_api_key: str = Field(..., alias="GROQ_API_KEY")',
     'groq_api_key: Optional[str] = Field(None, alias="GROQ_API_KEY")\n'
     '    llm_provider: str = Field("groq", alias="LLM_PROVIDER")  # "groq" ou "gemini"'),
])

patch("crew.py", [
    ("def get_llm() -> LLM:\n    settings = get_settings()\n",
     "def get_llm() -> LLM:\n    settings = get_settings()\n"
     "    if (settings.llm_provider or '').strip().lower() == 'gemini' or not settings.groq_api_key:\n"
     "        if not settings.gemini_api_key:\n"
     "            raise RuntimeError('GEMINI_API_KEY não configurada (LLM_PROVIDER=gemini).')\n"
     "        return LLM(\n"
     "            model=settings.gemini_model,\n"
     "            api_key=settings.gemini_api_key,\n"
     "            temperature=0.7,\n"
     "            max_tokens=2048,\n"
     "        )\n"),
])

patch(".github/workflows/main.yml", [
    ("          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}\n",
     "          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}\n"
     "          LLM_PROVIDER: ${{ secrets.LLM_PROVIDER }}\n"
     "          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}\n"
     "          GEMINI_MODEL: ${{ secrets.GEMINI_MODEL }}\n"),
])

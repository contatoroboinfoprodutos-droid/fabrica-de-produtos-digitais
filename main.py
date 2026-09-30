"""
Ponto de entrada da Infoproduct Factory.

Uso automático (GitHub Actions, cron ou workflow_dispatch sem inputs):
    python main.py
    -> usa PRODUTO_TOPICO e IMAGEM_PADRAO_URL definidos em .env/Secrets.

Uso manual local, sobrepondo os valores padrão só nesta execução:
    python main.py --topic "Como organizar finanças pessoais em 30 dias" \
        --image-url https://meusite.com/assets/capa.jpg

Requer um arquivo .env válido na raiz do projeto (veja .env.example) ou as
mesmas variáveis definidas como Secrets do GitHub Actions.
"""
import argparse
import logging
import sys

from dotenv import load_dotenv

# --- WORKAROUND PARA O GROQ ---
# Evita que o CrewAI injete 'cache_breakpoint' nas mensagens do sistema,
# o que gera BadRequestError na API do Groq.
try:
    import crewai.llms.cache as _crewai_cache
    _crewai_cache.mark_cache_breakpoint = lambda msg: msg
except (ImportError, AttributeError):
    pass
# -----------------------------

from config import get_settings
from crew import InfoprodutoFactoryCrew


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("infoproduct_factory")

    settings = get_settings()

    # --topic/--image-url são OPCIONAIS: servem só para testes manuais.
    # Sem eles (caso do cron/workflow_dispatch), os valores vêm do .env/Secrets
    # (PRODUTO_TOPICO / IMAGEM_PADRAO_URL) — por isso não são "required".
    parser = argparse.ArgumentParser(description="Infoproduct Factory - CrewAI")
    parser.add_argument(
        "--topic",
        type=str,
        default=settings.produto_topico,
        help="Tema/produto do infoproduto a gerar (default: PRODUTO_TOPICO do .env/Secrets).",
    )
    parser.add_argument(
        "--image-url",
        type=str,
        default=settings.imagem_padrao_url,
        help="URL pública de uma imagem já hospedada (default: IMAGEM_PADRAO_URL do .env/Secrets).",
    )
    args = parser.parse_args()

    if not args.image_url:
        logger.error(
            "Nenhuma imagem configurada. Defina IMAGEM_PADRAO_URL no .env/Secrets "
            "ou passe --image-url manualmente. A Meta Graph API exige uma URL pública "
            "e real de imagem para publicar."
        )
        sys.exit(1)

    if not settings.meta_configurada:
        logger.warning(
            "Credenciais da Meta (META_LONG_LIVED_TOKEN/FB_PAGE_ID/INSTAGRAM_ACCOUNT_ID) "
            "incompletas. O conteúdo será gerado normalmente, mas a etapa de publicação "
            "vai reportar 'não configurado' em vez de publicar de verdade."
        )

    logger.info(f"Gerando campanha para: {args.topic}")

    resultado = InfoprodutoFactoryCrew().crew().kickoff(
        inputs={"produto_topico": args.topic, "imagem_padrao_url": args.image_url}
    )

    print("\n" + "=" * 80)
    print("RESULTADO FINAL")
    print("=" * 80)
    print(resultado)


if __name__ == "__main__":
    main()

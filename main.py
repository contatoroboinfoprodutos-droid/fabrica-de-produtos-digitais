"""
Ponto de entrada da Infoproduct Factory.

Uso:
    python main.py "Como organizar finanças pessoais em 30 dias" \
        --image-url https://meusite.com/assets/capa.jpg

Requer um arquivo .env válido na raiz do projeto (veja .env.example).
"""
import argparse
import logging

from dotenv import load_dotenv

from crew import build_crew


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Infoproduct Factory - CrewAI")
    parser.add_argument("topic", type=str, help="Tema do infoproduto/conteúdo a gerar.")
    parser.add_argument(
        "--image-url",
        type=str,
        required=True,
        help="URL pública de uma imagem já hospedada, usada nas publicações.",
    )
    args = parser.parse_args()

    crew = build_crew(topic=args.topic, image_asset_url=args.image_url)
    result = crew.kickoff()

    print("\n" + "=" * 80)
    print("RESULTADO FINAL")
    print("=" * 80)
    print(result)


if __name__ == "__main__":
    main()

from crewai import Task
from . import config_lt as cfg
from .agents import (trend_scout_agent, copywriter_lowticket_agent,
                     visual_director_agent, publisher_infoproduto_agent)


def _contexto_produto() -> str:
    """Dados REAIS do produto do catálogo. O anúncio só pode afirmar o que está aqui."""
    p = cfg.PRODUTO
    if not p:
        return ""
    txt = (f"\nPRODUTO REAL DO CATÁLOGO (fale SOMENTE do que está aqui; não invente benefícios, bônus, "
           f"garantias, números nem depoimentos): nome '{p['nome']}'; promessa '{p['promessa']}'; "
           f"o que vem dentro: {'; '.join(p['conteudos'])}.")
    return txt.replace("{", "(").replace("}", ")")  # o CrewAI interpreta chaves em descrições


def build_lt_tasks(slot: str):
    s = cfg.SLOTS[slot]
    lt_task_pesquisa = Task(
        description=(f"Post {s['tipo']} ({slot}). Marca: {cfg.BRAND_NAME}. Nicho: {cfg.NICHE}.\n"
                     f"Objetivo: {s['descricao']}{_contexto_produto()}\n"
                     "Entregue 3 dores/ganchos e escolha o melhor."),
        expected_output="Lista de 3 ganchos e o escolhido, com justificativa de 1 linha.",
        agent=trend_scout_agent)

    extra = (f"Inclua o link {cfg.OFFER_LINK} e o preço {cfg.OFFER_PRICE} na legenda "
             "(o link funciona no Facebook) e termine com 'Link também na bio'."
             if s["tipo"] == "OFERTA"
             else "Sem link de venda; CTA para salvar/seguir.")
    lt_task_copy = Task(
        description=(f"Com o gancho escolhido, escreva:\n1) HEADLINE do card (máx 60 caracteres)\n"
                     f"2) SUBLINE (máx 100 caracteres)\n3) LEGENDA (até 800 caracteres, SEM hashtags e SEM link de catálogo: o sistema acrescenta hashtags em 3 camadas e o CTA de cada rede)\n"
                     "4) TEMA_IMAGEM: 2 a 4 palavras EM INGLÊS que descrevam uma foto de fundo "
                     "relacionada ao tema (ex.: 'woman studying laptop'). Evite pessoas famosas, marcas e textos.\n"
                     f"{extra}{_contexto_produto()}\nSem promessa de ganho garantido. "
                     "Nunca use as expressões: primeira venda, lucro, testado, comprovado, garantido. "
                     "A LEGENDA deve ser texto puro: sem markdown (nada de ** ou *), sem colchetes e sem links inventados."),
        expected_output="HEADLINE, SUBLINE, LEGENDA e TEMA_IMAGEM rotulados.",
        agent=copywriter_lowticket_agent, context=[lt_task_pesquisa])

    filename = f"post_{slot}.png"
    lt_task_visual = Task(
        description=(f"Use a ferramenta lt_render_card com filename='{filename}', usando HEADLINE e SUBLINE do copy "
                     "e passando o TEMA_IMAGEM no parâmetro tema_imagem. "
                     "Devolva o nome do arquivo e a LEGENDA final, sem alterá-la."),
        expected_output=f"Confirmação do arquivo {filename} e a LEGENDA.",
        agent=visual_director_agent, context=[lt_task_copy])

    plataformas = ("lt_publicar_meta (publica no Facebook e no Instagram de uma vez)"
                   + (" e depois lt_publicar_tiktok" if cfg.TIKTOK_ATIVO else ""))
    lt_task_publicacao = Task(
        description=(f"Publique '{filename}' com a LEGENDA recebida usando {plataformas}. "
                     "Reporte o resultado de cada plataforma exatamente como as ferramentas retornaram; "
                     "não invente IDs nem resultados."),
        expected_output="Status de publicação no Facebook e no Instagram"
                        + (" e no TikTok." if cfg.TIKTOK_ATIVO else "."),
        agent=publisher_infoproduto_agent, context=[lt_task_visual])

    return [lt_task_pesquisa, lt_task_copy, lt_task_visual, lt_task_publicacao]

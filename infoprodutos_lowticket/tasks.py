from crewai import Task
from . import config_lt as cfg
from .agents import (trend_scout_agent, copywriter_lowticket_agent,
                     visual_director_agent, publisher_infoproduto_agent)


def build_lt_tasks(slot: str):
    s = cfg.SLOTS[slot]
    lt_task_pesquisa = Task(
        description=(f"Post {s['tipo']} ({slot}). Marca: {cfg.BRAND_NAME}. Nicho: {cfg.NICHE}.\n"
                     f"Objetivo: {s['descricao']}\nEntregue 3 dores/ganchos e escolha o melhor."),
        expected_output="Lista de 3 ganchos e o escolhido, com justificativa de 1 linha.",
        agent=trend_scout_agent)

    extra = (f"Inclua o link {cfg.OFFER_LINK} e o preço {cfg.OFFER_PRICE} na legenda "
             "(o link funciona no Facebook) e termine com 'Link também na bio'."
             if s["tipo"] == "OFERTA"
             else "Sem link de venda; CTA para salvar/seguir.")
    lt_task_copy = Task(
        description=(f"Com o gancho escolhido, escreva:\n1) HEADLINE do card (máx 60 caracteres)\n"
                     f"2) SUBLINE (máx 100 caracteres)\n3) LEGENDA (até 900 caracteres, com 5 hashtags)\n"
                     "4) TEMA_IMAGEM: 2 a 4 palavras EM INGLÊS que descrevam uma foto de fundo "
                     "relacionada ao tema (ex.: 'woman studying laptop'). Evite pessoas famosas, marcas e textos.\n"
                     f"{extra}\nSem promessa de ganho garantido."),
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

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

    extra = (f"Inclua o link {cfg.OFFER_LINK} e o preço {cfg.OFFER_PRICE}." if s["tipo"] == "OFERTA"
             else "Sem link de venda; CTA para salvar/seguir.")
    lt_task_copy = Task(
        description=(f"Com o gancho escolhido, escreva:\n1) HEADLINE do card (máx 60 caracteres)\n"
                     f"2) SUBLINE (máx 100 caracteres)\n3) LEGENDA (até 900 caracteres, com 5 hashtags)\n{extra}\n"
                     "Sem promessa de ganho garantido."),
        expected_output="HEADLINE, SUBLINE e LEGENDA rotulados.",
        agent=copywriter_lowticket_agent, context=[lt_task_pesquisa])

    filename = f"post_{slot}.png"
    lt_task_visual = Task(
        description=(f"Use a ferramenta lt_render_card com filename='{filename}', usando HEADLINE e SUBLINE do copy. "
                     "Devolva o nome do arquivo e a LEGENDA final."),
        expected_output=f"Confirmação do arquivo {filename} e a LEGENDA.",
        agent=visual_director_agent, context=[lt_task_copy])

    lt_task_publicacao = Task(
        description=(f"Publique '{filename}' com a LEGENDA recebida usando lt_publicar_instagram e depois "
                     "lt_publicar_tiktok. Reporte o resultado de cada plataforma."),
        expected_output="Status de publicação Instagram e TikTok.",
        agent=publisher_infoproduto_agent, context=[lt_task_visual])

    return [lt_task_pesquisa, lt_task_copy, lt_task_visual, lt_task_publicacao]

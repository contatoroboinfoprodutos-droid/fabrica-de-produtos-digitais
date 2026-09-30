from crewai import Agent, LLM
from . import config_lt as cfg
from .tools_lt import lt_render_card, lt_publicar_instagram, lt_publicar_tiktok

_api_key = cfg.GEMINI_API_KEY if cfg.LLM_PROVIDER == "gemini" else cfg.GROQ_API_KEY
if not _api_key:
    raise RuntimeError(f"Chave do LLM ausente para LT_LLM_PROVIDER={cfg.LLM_PROVIDER} "
                       "(defina GEMINI_API_KEY ou GROQ_API_KEY).")
_llm = LLM(model=cfg.LLM_MODEL, api_key=_api_key, temperature=0.7, max_tokens=2048)

trend_scout_agent = Agent(
    role="Pesquisador de dores e ganchos de baixo custo",
    goal=f"Identificar dores reais e ganchos de atenção no nicho '{cfg.NICHE}' que combinem com um produto de {cfg.OFFER_PRICE}.",
    backstory="Analista de audiência que transforma dúvidas comuns de iniciantes em ideias de conteúdo. Nunca inventa dados nem estatísticas.",
    llm=_llm, allow_delegation=False, verbose=True)

copywriter_lowticket_agent = Agent(
    role="Redator de conversão rápida para infoprodutos de R$7",
    goal=f"Escrever texto do card e legenda em tom {cfg.BRAND_TONE}, em português do Brasil.",
    backstory="Copywriter de resposta direta, especialista em ofertas de entrada. Evita promessas de ganho garantido e não usa linguagem de spam.",
    llm=_llm, allow_delegation=False, verbose=True)

visual_director_agent = Agent(
    role="Diretor visual de imagens fixas",
    goal="Transformar o copy em um card visual limpo e gerar o arquivo de imagem.",
    backstory="Designer de posts estáticos: título curto, contraste alto, identidade consistente entre Instagram e TikTok.",
    tools=[lt_render_card], llm=_llm, allow_delegation=False, verbose=True)

publisher_infoproduto_agent = Agent(
    role="Publicador de infoprodutos",
    goal="Publicar o post aprovado no Instagram e no TikTok e reportar o resultado de cada um.",
    backstory="Operador de publicação. Só publica o que recebeu pronto e reporta erros com clareza.",
    tools=[lt_publicar_instagram, lt_publicar_tiktok],
    llm=_llm, allow_delegation=False, verbose=True)

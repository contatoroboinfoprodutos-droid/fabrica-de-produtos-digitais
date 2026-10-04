"""Guardião: lê o log de uma execução que falhou, reconhece a causa e escreve um diagnóstico em português
com o passo a passo da correção. Regras fixas (sem IA): precisa funcionar justamente quando a IA está fora.

O que o guardião NÃO faz, de propósito:
  - não reexecuta robôs de anúncio (as marcas de publicação são por execução; repetir sozinho poderia duplicar post);
  - não altera código, workflows nem Secrets (um agente com poder de editar o que publica nas suas redes é risco).
Ele só diagnostica e avisa (uma Issue no GitHub, que também chega por e-mail). Biblioteca padrão apenas.
"""
import re

# (id, prioridade, padrão, título, causa, correção, transitória)
# Prioridade menor = mais importante. A primeira regra que casar é a "causa principal".
REGRAS = [
    ("meta_token", 1, r"código 190|Session has expired|Error validating access token|OAuthException[^\n]*190",
     "O token da Meta expirou ou é inválido",
     "A Meta recusou o token (erro 190). Token expirado não pode ser renovado.",
     ["Gere um token novo no Graph API Explorer (permissões de páginas e Instagram).",
      "Crie o Secret META_SHORT_LIVED_TOKEN com ele (não cole o valor em chat).",
      "Rode a ação 'Renovar token da Meta' em seguida: ela troca por um token de ~60 dias e grava o Secret."],
     False),
    ("uma_rede", 2, r"Só uma das redes publicou",
     "Só o Facebook ou só o Instagram publicou",
     "Depois de todas as tentativas, uma das redes ficou sem o post.",
     ["Abra a página do Facebook e o perfil do Instagram e veja qual rede publicou.",
      "Se faltou uma, publique à mão ou rode o robô de novo SOMENTE depois de conferir (rodar às cegas pode duplicar).",
      "Veja no log da execução o erro da rede que falhou (permissão, imagem recusada ou token)."],
     False),
    ("gh_secret", 3, r"Não consegui gravar o Secret|GH_SECRETS_TOKEN",
     "O GitHub não deixou gravar o Secret do token",
     "O token pessoal do GitHub usado para gravar Secrets não tem permissão de escrita.",
     ["Crie um token com 'Secrets: Read and write' neste repositório (fine-grained) ou escopo 'repo' (classic).",
      "Guarde-o no Secret GH_SECRETS_TOKEN e rode 'Renovar token da Meta' de novo."],
     False),
    ("meta_permissao", 4, r"\(#(?:10|200|283)\)|FB_PAGE_ID não encontrado|não encontrada entre as páginas",
     "A Meta recusou por falta de permissão ou página errada",
     "O token não tem a permissão necessária ou o FB_PAGE_ID/INSTAGRAM_ACCOUNT_ID não é desta página.",
     ["Confirme que FB_PAGE_ID e INSTAGRAM_ACCOUNT_ID são da página e do perfil corretos.",
      "Gere o token de novo marcando as permissões de páginas e Instagram e a página certa."],
     False),
    ("sem_produto", 5, r"sem produto (?:'?pronto'?|real)|Nenhum produto 'pronto'",
     "Não há produto pronto para anunciar",
     "Em modo real os robôs só anunciam produto com status 'pronto' (ativo e com link de compra).",
     ["Rode 'Fabrica de Produtos' com a ação 'verificar' (ou 'criar').",
      "Se o produto já está ativo na Cakto mas não liberou, use 'definir-link' com o link de compra.",
      "Veja o status com a ação 'status'."],
     False),
    ("sem_imagem", 6, r"Sem imagem\.|IMAGEM_PADRAO_URL",
     "O robô não encontrou imagem para publicar",
     "A Meta exige uma imagem pública e não há UNSPLASH_API_KEY nem IMAGEM_PADRAO_URL.",
     ["Crie o Secret UNSPLASH_API_KEY (busca automática) ou IMAGEM_PADRAO_URL (imagem fixa)."],
     False),
    ("drive_cota", 7, r"storageQuotaExceeded|falta de cota",
     "O Google Drive recusou o envio do PDF por falta de cota",
     "Conta de serviço não tem armazenamento e não grava no Meu Drive de conta pessoal.",
     ["Use uma pasta num Drive compartilhado (Workspace) com a conta de serviço como membro, ou",
      "use o modo OAuth da sua conta (Secrets GDRIVE_OAUTH_*; veja fabrica_produtos/README.md).",
      "A ação 'sondar' mostra se a pasta está no Meu Drive."],
     False),
    ("drive_pasta", 8, r"drive: \w+ recusado \(HTTP (?:403|404)\)|sem permissão para criar arquivos",
     "O robô não acessa a pasta do Google Drive",
     "A pasta não existe com esse ID ou não foi compartilhada com a conta de serviço como Editor.",
     ["Confira o GDRIVE_FOLDER_ID (trecho final da URL da pasta).",
      "Compartilhe a pasta com o e-mail da conta de serviço (client_email do JSON) como Editor."],
     False),
    ("drive_credencial", 9, r"JSON da conta de serviço é inválido|falta a biblioteca google-auth|drive: autenticação",
     "A credencial do Google Drive não funcionou",
     "O JSON da conta de serviço (ou o OAuth) está inválido, incompleto ou vencido.",
     ["Recrie o Secret com o JSON inteiro da conta de serviço (GDRIVE_SERVICE_ACCOUNT_JSON ou GDRIVE_CREDENTIALS_JSON).",
      "Confirme que a API do Google Drive está ativada no projeto do Google Cloud."],
     False),
    ("cakto_auth", 10, r"cakto: autenticação recusada|cakto: [^\n]*\(HTTP 401\)",
     "A Cakto recusou o login da API",
     "CAKTO_CLIENT_ID/CAKTO_CLIENT_SECRET incorretos, vencidos ou revogados.",
     ["Na Cakto: Integrações → Cakto API → crie uma chave nova (escopos read, write, products, offers).",
      "Atualize os Secrets CAKTO_CLIENT_ID e CAKTO_CLIENT_SECRET (o secret aparece uma única vez)."],
     False),
    ("cakto_escopo", 11, r"cakto: [^\n]*recusado \(HTTP 403\)",
     "A chave da Cakto não tem permissão para esta operação",
     "Faltam escopos na chave de API.",
     ["Crie a chave com os escopos read, write, products e offers e atualize os Secrets."],
     False),
    ("cakto_dados", 12, r"cakto: [^\n]*recusado \(HTTP (?:400|409|422)\)",
     "A Cakto recusou os dados do produto",
     "Algum campo do pedido é inválido (a mensagem da Cakto vem no log).",
     ["Leia o detalhe da Cakto no trecho do log abaixo e ajuste o campo indicado.",
      "Se o produto já existe com outro estado, abra-o no painel da Cakto."],
     False),
    ("cakto_rede", 13, r"cakto: falha de rede",
     "Falha de rede ao falar com a Cakto",
     "A Cakto não respondeu a tempo.",
     ["Normalmente passa sozinha: rode de novo ou espere a próxima execução agendada."],
     True),
    ("ia_chave", 14, r"API key not valid|invalid_api_key|Incorrect API key|Nenhuma chave de LLM",
     "Chave de IA ausente ou inválida",
     "Nenhum provedor de IA aceitou a chave (GEMINI_API_KEY, GROQ_API_KEY ou OPENROUTER_API_KEY).",
     ["Confira os Secrets das chaves de IA e renove a que foi recusada."],
     False),
    ("ia_limite", 15, r"\b429\b|RESOURCE_EXHAUSTED|rate.?limit|quota exceeded|Too Many Requests",
     "Limite gratuito da IA atingido",
     "O provedor de IA bloqueou por excesso de uso (limite por minuto ou por dia).",
     ["O robô já troca de provedor sozinho. Se falhar sempre, cadastre uma segunda chave (GROQ_API_KEY ou OPENROUTER_API_KEY).",
      "Se for limite diário, ele volta no dia seguinte."],
     True),
    ("ia_indisponivel", 16, r"\b503\b|UNAVAILABLE|overloaded|Service Unavailable",
     "Provedor de IA temporariamente indisponível",
     "O provedor respondeu 503 (sobrecarga). É passageiro.",
     ["Nada a fazer: o robô troca de provedor e tenta de novo; a próxima execução costuma passar."],
     True),
    ("dependencias", 17, r"ModuleNotFoundError|No matching distribution|Could not find a version|ImportError",
     "Falha ao instalar ou carregar uma dependência",
     "Uma biblioteca Python não instalou ou mudou.",
     ["Veja a linha do erro no trecho do log e o arquivo requirements do robô correspondente."],
     False),
]

_SEGREDOS = [
    (re.compile(r"EAA[A-Za-z0-9]{20,}"), "[token-meta]"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "[chave-google]"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}"), "[chave-groq]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "[chave-api]"),
    (re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"), "[token-github]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"), r"\1[removido]"),
    (re.compile(r"(?i)((?:access_token|client_secret|refresh_token|api_key|private_key)\W{1,4})[^\s\"'&,}]{6,}"),
     r"\1[removido]"),
]
_RE_ERRO = re.compile(r"(?i)error|erro|falhou|falha|traceback|exception|recusad|bloquead|::error|expired|http [45]\d\d")
_RE_PREFIXO_DATA = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z\s?")


def limpar(texto: str) -> str:
    """Remove segredos e o prefixo de data de cada linha. Nunca devolve token, chave ou secret."""
    for padrao, troca in _SEGREDOS:
        texto = padrao.sub(troca, texto)
    return "\n".join(_RE_PREFIXO_DATA.sub("", ln) for ln in texto.splitlines())


def diagnosticar(log: str) -> list[dict]:
    """Causas reconhecidas no log, da mais importante para a menos. Vazio = causa não reconhecida."""
    achados = []
    for rid, prio, padrao, titulo, causa, correcao, transitoria in sorted(REGRAS, key=lambda r: r[1]):
        if re.search(padrao, log, flags=re.IGNORECASE):
            achados.append({"id": rid, "titulo": titulo, "causa": causa, "correcao": correcao,
                            "transitoria": transitoria})
    return achados


def trecho_do_erro(log: str, maximo: int = 25) -> str:
    """Últimas linhas com cara de erro (já sem segredos); se não houver, o final do log."""
    linhas = [ln.rstrip() for ln in limpar(log).splitlines() if ln.strip()]
    erros = [ln for ln in linhas if _RE_ERRO.search(ln)]
    return "\n".join((erros or linhas)[-maximo:])[:6000]


def montar_issue(workflow: str, url_execucao: str, log: str) -> tuple[str, str]:
    """(título, corpo em markdown). O título é estável por workflow+causa, para não abrir issue repetida."""
    achados = diagnosticar(log)
    principal = achados[0] if achados else None
    titulo = f"Falha: {workflow} — {principal['titulo'] if principal else 'causa não reconhecida'}"
    corpo = [f"A execução de **{workflow}** falhou. [Ver execução]({url_execucao})", ""]
    if principal:
        corpo += ["## Causa provável", f"**{principal['titulo']}**. {principal['causa']}", "",
                  "## Como corrigir", *[f"{i}. {p}" for i, p in enumerate(principal["correcao"], 1)], ""]
        if principal["transitoria"]:
            corpo += ["_Costuma ser passageira: se a próxima execução passar, pode fechar esta issue._", ""]
        for outro in achados[1:3]:
            corpo += [f"Também apareceu no log: {outro['titulo']}."]
        if len(achados) > 1:
            corpo += [""]
    else:
        corpo += ["## Causa não reconhecida",
                  "Nenhuma regra conhecida casou com este log. Leia o trecho abaixo ou abra a execução.", ""]
    corpo += ["## O que o guardião fez",
              "Só diagnosticou. Não reexecutou nada, não mudou código nem Secrets (reexecutar um robô de anúncio "
              "sozinho poderia duplicar uma postagem).", "",
              "## Trecho do log (segredos removidos)", "```", trecho_do_erro(log) or "(log vazio)", "```"]
    return titulo, "\n".join(corpo) + "\n"

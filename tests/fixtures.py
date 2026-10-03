"""Dados de teste compartilhados."""
import json

FRASE = "Organize o seu dia em blocos pequenos e revise o resultado ao final da semana com calma."


def capitulo(titulo, repeticoes=12):
    return {"titulo": titulo, "texto": " ".join([FRASE] * repeticoes)}


def produto_bom(nome="Guia Prático de Rotina em 7 Dias", preco=7.0, **extra):
    p = {
        "nome": nome,
        "tipo": "guia",
        "preco": preco,
        "promessa": "Um passo a passo curto para organizar a sua rotina com blocos de tempo.",
        "publico": "Pessoas que querem organizar a rotina.",
        "conteudos": ["Blocos de tempo", "Lista das três tarefas do dia", "Revisão semanal", "Modelo de agenda"],
        "descricao_oferta": "Guia em PDF com passos práticos, exemplos e exercícios para organizar a rotina.",
        "capitulos": [capitulo(f"Capítulo {i}") for i in range(1, 5)],
    }
    p.update(extra)
    return p


def produto_pronto(nome="Guia Prático de Rotina em 7 Dias", link="https://pay.exemplo.com.br/abc123"):
    p = produto_bom(nome)
    p.update({"id": "p20261003-1", "status": "pronto", "preco": 7.0, "preco_texto": "R$ 7,00",
              "link_compra": link, "plataforma": "kiwify"})
    return p


def json_do_produto(p=None):
    return json.dumps(p or produto_bom(), ensure_ascii=False)

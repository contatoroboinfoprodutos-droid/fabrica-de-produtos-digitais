"""Gera o PDF de entrega do produto a partir do JSON aprovado (reportlab)."""
import os
from xml.sax.saxutils import escape

from . import config_fabrica as cfg
from .texto import formatar_preco, parse_preco


def _pdf_texto(texto: str) -> str:
    """As fontes padrão do PDF só têm Latin-1/cp1252: troca o que não existe por '?' em vez de quebrar."""
    return escape(str(texto or "").encode("cp1252", errors="replace").decode("cp1252"))


def gerar_pdf(produto: dict, caminho: str) -> str:
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    base = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=base["Title"], fontSize=26, leading=32, alignment=TA_LEFT, spaceAfter=14)
    sub = ParagraphStyle("s", parent=base["Normal"], fontSize=14, leading=20, textColor="#444444", spaceAfter=24)
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontSize=18, leading=24, spaceBefore=6, spaceAfter=10)
    corpo = ParagraphStyle("c", parent=base["Normal"], fontSize=11.5, leading=17, spaceAfter=9)
    item = ParagraphStyle("i", parent=corpo, leftIndent=14, bulletIndent=2)
    nota = ParagraphStyle("n", parent=base["Normal"], fontSize=9, leading=13, textColor="#666666")

    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2.2 * cm, bottomMargin=2.2 * cm,
                            title=str(produto.get("nome", "")), author=cfg.MARCA)
    f = [Spacer(1, 4 * cm), Paragraph(_pdf_texto(produto.get("nome")), titulo),
         Paragraph(_pdf_texto(produto.get("promessa")), sub),
         Paragraph("O que você vai encontrar aqui", h1)]
    for c in produto.get("conteudos") or []:
        f.append(Paragraph(_pdf_texto(c), item, bulletText="•"))
    f.append(Spacer(1, 2 * cm))
    f.append(Paragraph(_pdf_texto(cfg.MARCA), nota))
    f.append(PageBreak())

    for i, cap in enumerate(c for c in (produto.get("capitulos") or []) if isinstance(c, dict)):
        f.append(Paragraph(_pdf_texto(f"{i + 1}. {cap.get('titulo', '')}"), h1))
        for par in str(cap.get("texto") or "").split("\n"):
            if par.strip():
                f.append(Paragraph(_pdf_texto(par.strip()), corpo))
        f.append(Spacer(1, 0.6 * cm))

    f.append(PageBreak())
    f.append(Paragraph("Sobre este material", h1))
    f.append(Paragraph(_pdf_texto(
        "Este material foi criado com apoio de inteligência artificial e passou por revisão automatizada. "
        "Ele tem caráter informativo e educativo e não promete resultado financeiro nem substitui "
        "orientação profissional."), corpo))
    preco = parse_preco(produto.get("preco"))
    if preco is not None:
        f.append(Paragraph(_pdf_texto(f"Valor de referência: {formatar_preco(preco)}"), nota))
    doc.build(f)
    return caminho

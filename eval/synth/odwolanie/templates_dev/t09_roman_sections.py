"""Roman-numbered sections (I. Strony ... VI. Uzasadnienie), roman-month dates."""

from .. import blocks as B
from ..core import build_simple, esc, fmt_date

NAME = "dev_t09_roman_sections"
OVERRIDES = {}


def render(case, ctx, path):
    ctx.date_body = ctx.rng.choice(["roman", "dots_r", "words"])
    s = []
    if case.data:
        s.append(ctx.P(f"{esc(case.miejscowosc)}, {fmt_date(case.data, ctx.rng.choice(['roman', 'roman_dots']))}", "right"))
    s.append(ctx.P("ODWOŁANIE", "title"))
    s.append(ctx.P("wnoszone do Krajowej Izby Odwoławczej przy Prezesie Urzędu Zamówień Publicznych", "center"))
    s.append(ctx.P("I. STRONY POSTĘPOWANIA ODWOŁAWCZEGO", "h"))
    s.append(ctx.P("1. Odwołujący", "bold"))
    s.append(ctx.P("<br/>".join(B.odw_block_lines(case, ctx)), "body", leftIndent=16))
    if case.attorneys:
        s.append(ctx.P("2. Pełnomocnik Odwołującego", "bold"))
        s.append(ctx.P("<br/>".join(B.attorney_lines(case, ctx, lead="")), "body", leftIndent=16))
    s.append(ctx.P(f"{3 if case.attorneys else 2}. Zamawiający", "bold"))
    s.append(ctx.P("<br/>".join(B.zam_block_lines(case, ctx)), "body", leftIndent=16))
    s.append(ctx.P("II. PRZEDMIOT ZAMÓWIENIA", "h"))
    s.append(ctx.P("Odwołanie dotyczy " + B.proc_sentence(case, ctx) + ".", "just"))
    s.append(ctx.P("III. ZASKARŻONE CZYNNOŚCI", "h"))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s.append(ctx.P("IV. ZARZUTY", "h"))
    s += B.zarzuty_flow(case, ctx, numbering="{r}.{i}")
    s.append(ctx.P("V. ŻĄDANIA", "h"))
    s += B.requests_flow(case, ctx, title="Odwołujący wnosi o:")
    s.append(ctx.P("VI. UZASADNIENIE", "h"))
    s += B.justification(case, ctx, title="", n_fill=6)[1:]
    s.append(ctx.P("VII. TERMIN I WPIS", "h"))
    s.append(ctx.P(f"Odwołanie wniesiono z zachowaniem terminu. Wpis w wysokości {case.wpis} uiszczono.", "just"))
    s += B.signature(case, ctx)
    s += B.attachments(case, ctx)
    build_simple(path, s, ctx, footer="Strona {p}/{n}", footer_align="right", margins=(25, 20, 20, 22))

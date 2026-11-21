"""Letterhead stationery: law firm (or the appellant company) banner drawn on canvas."""

from reportlab.lib import colors
from reportlab.lib.units import mm

from .. import blocks as B
from ..core import build_simple, esc

NAME = "dev_t06_letterhead"
OVERRIDES = {"no_attorney": 0.2}


def render(case, ctx, path):
    col = colors.HexColor(ctx.rng.choice(["#1f3a5f", "#5b1a1a", "#2e4d2e", "#333333"]))
    if case.attorneys:
        head1, head2 = case.firm_nazwa, f"{case.firm_address} | tel. {case.firm_phone} | {case.firm_mail}"
    else:
        o = case.odw[0]
        head1 = o.nazwa
        head2 = " | ".join([o.address] + ctx.id_parts(o))

    def on_page(c, doc):
        w, h = doc.pagesize
        c.saveState()
        c.setFillColor(col)
        c.rect(0, h - 26 * mm, w, 26 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(ctx.bold, ctx.size + 3)
        c.drawString(18 * mm, h - 13 * mm, head1[:80])
        c.setFont(ctx.font, ctx.size - 2.5)
        c.drawString(18 * mm, h - 20 * mm, head2[:130])
        c.restoreState()

    s = []
    ref = f"Nasz znak: {ctx.rng.choice(['KZP', 'ODW', 'ZP'])}/{ctx.rng.randint(10, 999)}/{(case.data or case.extra_dates[0]).year}"
    if not case.nr:
        # GT numer_postepowania is null: do not print the sender's own reference, which could be
        # read as a procurement number (rng calls above are kept so other docs stay unchanged).
        ref = ""
    pd = B.place_date(case, ctx)
    s.append(ctx.table([[ref, esc(pd)]], grid=False))
    s.append(ctx.gap(5))
    s.append(ctx.P("<br/>".join(B.kio_lines(ctx)), "bold", leftIndent=250))
    s.append(ctx.gap(5))
    if case.attorneys:
        a0 = case.attorneys[0]
        others = case.attorneys[1:]
        intro = (f"Pełnomocnik Odwołującego: <b>{esc(a0.with_title('long'))}</b>"
                 + (" (oraz " + ", ".join(esc(x.with_title('long')) for x in others) + ")" if others else "")
                 + f", {esc(case.firm_nazwa)}, adres e-mail do korespondencji: {case.firm_mail}")
        s.append(ctx.P(intro, "just"))
    s.append(ctx.P("<b>Odwołujący</b>, w imieniu którego wnoszone jest odwołanie:", "body"))
    s.append(ctx.P("<br/>".join(B.odw_block_lines(case, ctx)), "body", leftIndent=14))
    s.append(ctx.P("<b>Zamawiający</b>:", "body"))
    s.append(ctx.P("<br/>".join(B.zam_block_lines(case, ctx)), "body", leftIndent=14))
    s.append(ctx.P("Odwołanie", "title", alignment=0))
    s.append(ctx.P("od czynności i zaniechań Zamawiającego w " + B.proc_sentence(case, ctx)
                   .replace("postępowania", "postępowaniu", 1), "just"))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s += B.zarzuty_flow(case, ctx, numbering="{i}.")
    s += B.requests_flow(case, ctx, title="Odwołujący wnosi o:")
    s += B.justification(case, ctx, n_fill=5)
    s += B.signature(case, ctx)
    build_simple(path, s, ctx, margins=(18, 18, 34, 20), on_page=on_page, footer="{p}/{n}", footer_align="right")

"""Running header with KIO signature / case number on every page, caps labels."""

from reportlab.lib.units import mm

from .. import blocks as B
from ..core import build_simple, esc

NAME = "dev_t03_kio_sygn_header"
OVERRIDES = {"kio_sygn": 0.85}


def render(case, ctx, path):
    sygn = f"Sygn. akt: {case.kio_sygn}" if case.kio_sygn else "Sygn. akt: ............ (nadaje Izba)"
    run = f"Odwołanie – postępowanie nr {case.nr}" if case.nr else "Odwołanie do KIO"

    def on_page(c, doc):
        c.saveState()
        c.setFont(ctx.font, ctx.size - 2)
        w, h = doc.pagesize
        c.drawString(20 * mm, h - 12 * mm, run)
        c.drawRightString(w - 20 * mm, h - 12 * mm, sygn)
        c.line(20 * mm, h - 14 * mm, w - 20 * mm, h - 14 * mm)
        c.restoreState()

    s = []
    pd = B.place_date(case, ctx)
    if pd:
        s.append(ctx.P(esc(pd), ctx.rng.choice(["body", "right"])))
        s.append(ctx.gap(3))
    s.append(ctx.P("<br/>".join(B.kio_lines(ctx)), "right"))
    s.append(ctx.gap(4))
    s.append(ctx.P("ODWOŁUJĄCY:", "h"))
    s.append(ctx.P("<br/>".join(B.odw_block_lines(case, ctx)), "body", leftIndent=12))
    if case.attorneys:
        s.append(ctx.P("PEŁNOMOCNICY ODWOŁUJĄCEGO:" if len(case.attorneys) > 1 else "PEŁNOMOCNIK ODWOŁUJĄCEGO:", "h"))
        lines = [esc(a.with_title(ctx.rng.choice(["short", "long"]))) for a in case.attorneys]
        lines += [esc(case.firm_nazwa), esc(case.firm_address), f"adres e-mail: {case.firm_mail}"]
        s.append(ctx.P("<br/>".join(lines), "body", leftIndent=12))
    s.append(ctx.P("ZAMAWIAJĄCY:", "h"))
    s.append(ctx.P("<br/>".join(B.zam_block_lines(case, ctx)), "body", leftIndent=12))
    s.append(ctx.gap(2))
    s.append(ctx.P(f"Wartość zamówienia: {ctx.rng.choice(['powyżej', 'poniżej'])} progów unijnych<br/>"
                   f"Wpis od odwołania: {case.wpis}", "small"))
    s.append(ctx.P("ODWOŁANIE", "title"))
    s.append(ctx.P("w " + B.proc_sentence(case, ctx).replace("postępowania", "postępowaniu", 1), "just"))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s += B.zarzuty_flow(case, ctx, numbering="Zarzut nr {i}")
    s += B.requests_flow(case, ctx)
    s += B.justification(case, ctx, n_fill=6)
    s += B.signature(case, ctx)
    s += B.attachments(case, ctx)
    build_simple(path, s, ctx, on_page=on_page, margins=(20, 20, 22, 20), footer="Strona {p} z {n}",
                 footer_align="right")

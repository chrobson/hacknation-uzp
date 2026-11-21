"""Boxed executive summary on top ('Zaskarżona czynność ... z dnia ...'), § numbered pleas,
attorney mentioned in the instrumental/genitive case."""

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle

from .. import blocks as B
from ..core import build_simple, esc, fmt_date

NAME = "dev_t11_summary_box"
OVERRIDES = {}


def render(case, ctx, path):
    ctx.date_body = ctx.rng.choice(["words", "words_roku"])
    s = []
    if case.data:
        s.append(ctx.P(f"{esc(case.miejscowosc)}, dnia {fmt_date(case.data, ctx.rng.choice(['words', 'words_roku', 'words_bare']))}", "right"))
    s.append(ctx.P("<br/>".join(B.kio_lines(ctx)), "body"))
    s.append(ctx.gap(3))
    summ = [f"<b>Odwołanie</b> w sprawie: „{esc(case.tytul)}”"]
    if case.first.date:
        summ.append(f"Zaskarżona czynność: {ctx.zarzut(case.first, 'action', dated=False)}, z dnia {ctx.d(case.first.date)}")
    else:
        summ.append(f"Zaskarżona czynność: {ctx.zarzut(case.first, 'action', dated=False)}")
    if len(case.zarzuty) > 1:
        summ.append(f"Pozostałe zarzuty: {len(case.zarzuty) - 1}")
    summ.append(f"Wpis: {case.wpis}")
    box = Table([[ctx.P("<br/>".join(summ), "body")]], colWidths=[170 * mm])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.2, colors.black),
                             ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafae6")),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    s.append(box)
    s.append(ctx.gap(4))
    lead = case.odw[0]
    ids = ", ".join(ctx.id_parts(lead))
    if case.consortium:
        txt = (f"<b>Odwołujący:</b> konsorcjum, którego liderem jest {esc(lead.nazwa)}, {esc(lead.address)}"
               + (f" ({ids})" if ids else "") + "; członkowie konsorcjum: "
               + "; ".join(f"{esc(e.nazwa)} ({', '.join(ctx.id_parts(e))})" for e in case.odw[1:]))
    else:
        txt = f"<b>Odwołujący:</b> {esc(lead.nazwa)}, {esc(lead.address)}" + (f", {ids}" if ids else "")
    s.append(ctx.P(txt, "just"))
    if case.attorneys:
        a0 = case.attorneys[0]
        more = ""
        if len(case.attorneys) > 1:
            more = ", a także " + ", ".join(esc(a.inflected("inst")) for a in case.attorneys[1:])
        s.append(ctx.P(f"Odwołujący działa wraz z pełnomocnikiem – {esc(a0.inflected('inst'))}{more} "
                       f"({esc(case.firm_nazwa)}, {esc(case.firm_address)}; e-mail: {case.firm_mail}).", "just"))
    for z in case.zams:
        ids = ", ".join(ctx.id_parts(z))
        tag = ""
        if len(case.zams) > 1:
            tag = " – zamawiający prowadzący postępowanie" if z.prowadzacy else " – zamawiający wspólny"
        s.append(ctx.P(f"<b>Zamawiający:</b> {esc(z.nazwa)}{tag}, {esc(z.address)}" + (f", {ids}" if ids else ""), "just"))
    pp = ctx.proc_parts(case)
    lab = {"nr": "nr postępowania", "bzp": "nr ogłoszenia BZP", "ted": "nr ogłoszenia TED"}
    if pp:
        s.append(ctx.P("Oznaczenie postępowania: " + "; ".join(f"{lab[k]} {esc(v)}" for k, v in pp), "body"))
    s.append(ctx.gap(3))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s += B.zarzuty_flow(case, ctx, numbering="§ {i}.")
    s += B.requests_flow(case, ctx)
    s += B.justification(case, ctx, n_fill=5)
    s += B.signature(case, ctx)
    build_simple(path, s, ctx, footer="Strona {p} z {n}")

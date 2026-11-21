"""Terse appeal: no header date (mostly), parties as one-line 'Label – value; value' rows."""

from .. import blocks as B
from ..core import build_simple, esc

NAME = "dev_t10_terse_inline"
OVERRIDES = {"data_null": 0.6, "no_attorney": 0.25, "multi_attorney": 0.2}


def _line(e, ctx):
    ids = "; ".join(ctx.id_parts(e, sep=" "))
    return f"{esc(e.nazwa)}; {esc(e.address)}" + (f"; {ids}" if ids else "")


def render(case, ctx, path):
    s = []
    s.append(ctx.P("ODWOŁANIE", "title", alignment=0))
    pd = B.place_date(case, ctx)
    if pd:
        s.append(ctx.P(esc(pd), "body"))
    s.append(ctx.P("Adresat: Prezes Krajowej Izby Odwoławczej, ul. Postępu 17A, 02-676 Warszawa", "small"))
    s.append(ctx.gap(3))
    if case.consortium:
        s.append(ctx.P(f"<b>Odwołujący (lider konsorcjum)</b> – {_line(case.odw[0], ctx)}", "just"))
        for e in case.odw[1:]:
            s.append(ctx.P(f"<b>Członek konsorcjum</b> – {_line(e, ctx)}", "just"))
    else:
        s.append(ctx.P(f"<b>Odwołujący</b> – {_line(case.odw[0], ctx)}", "just"))
    if case.attorneys:
        s.append(ctx.P(f"<b>Pełnomocnik</b> – {esc(ctx.attorneys_line(case))}; {esc(case.firm_nazwa)}; "
                       f"{case.firm_mail}", "just"))
    for z in case.zams:
        tag = ""
        if len(case.zams) > 1:
            tag = " (prowadzący postępowanie)" if z.prowadzacy else ""
        s.append(ctx.P(f"<b>Zamawiający{tag}</b> – {_line(z, ctx)}", "just"))
    s.append(ctx.P(f"<b>Zamówienie</b> – „{esc(case.tytul)}”" + "".join(f"; {esc(v)}" for _, v in ctx.proc_parts(case)), "just"))
    s.append(ctx.gap(3))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s += B.zarzuty_flow(case, ctx, numbering="{i})")
    s += B.requests_flow(case, ctx, title="Wnoszę o:")
    s += B.justification(case, ctx, title="Uzasadnienie", n_fill=2)
    s += B.signature(case, ctx, align="left")
    build_simple(path, s, ctx, footer=None, margins=(20, 20, 15, 15))

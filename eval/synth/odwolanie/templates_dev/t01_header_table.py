"""Two-column party table at the top (Odwołujący | Zamawiający), date top-right."""

from reportlab.lib.units import mm

from .. import blocks as B
from ..core import build_simple, esc

NAME = "dev_t01_header_table"
OVERRIDES = {}


def render(case, ctx, path):
    s = []
    pd = B.place_date(case, ctx)
    kio = "<br/>".join(B.kio_lines(ctx))
    s.append(ctx.table([[ctx.P(kio, "bold"), ctx.P(esc(pd), "right")]], widths=[95 * mm, 75 * mm], grid=False))
    s.append(ctx.gap(5))
    left = ["<b>ODWOŁUJĄCY</b>"] + B.odw_block_lines(case, ctx) + B.attorney_lines(case, ctx)
    right = ["<b>ZAMAWIAJĄCY</b>"] + B.zam_block_lines(case, ctx)
    s.append(ctx.table([["<br/>".join(left), "<br/>".join(right)]], widths=[85 * mm, 85 * mm],
                       grid=ctx.rng.random() < 0.6))
    s.append(ctx.P("ODWOŁANIE", "title"))
    s.append(ctx.P("dotyczy: " + B.proc_sentence(case, ctx), "just"))
    s.append(ctx.gap(3))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s.append(ctx.P("Zaskarżonym czynnościom zarzucam naruszenie:", "body"))
    s += B.zarzuty_flow(case, ctx)
    s += B.requests_flow(case, ctx)
    s += B.justification(case, ctx)
    s += B.signature(case, ctx)
    s += B.attachments(case, ctx)
    build_simple(path, s, ctx, footer=ctx.rng.choice(["Strona {p} z {n}", "{p}/{n}", None]))

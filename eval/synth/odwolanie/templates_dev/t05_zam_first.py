"""Title first, then Zamawiający before Odwołujący; procurement IDs as a bulleted list."""

from .. import blocks as B
from ..core import build_simple, esc

NAME = "dev_t05_zam_first"
OVERRIDES = {"multi_zam": 0.3}


def render(case, ctx, path):
    s = []
    pd = B.place_date(case, ctx)
    if pd:
        s.append(ctx.P(esc(pd), "right"))
    s.append(ctx.P("ODWOŁANIE", "title"))
    s.append(ctx.P("do Prezesa Krajowej Izby Odwoławczej, ul. Postępu 17A, 02-676 Warszawa", "center"))
    s.append(ctx.gap(4))
    lbl = "Zamawiający:" if len(case.zams) == 1 else "Zamawiający (wspólnie):"
    s.append(ctx.P(lbl, "h"))
    s.append(ctx.P("<br/>".join(B.zam_block_lines(case, ctx)), "body", leftIndent=18))
    s.append(ctx.P("Odwołujący:", "h"))
    s.append(ctx.P("<br/>".join(B.odw_block_lines(case, ctx)), "body", leftIndent=18))
    if case.attorneys:
        s.append(ctx.P("Pełnomocnik Odwołującego:", "h"))
        a = case.attorneys
        lines = [esc(x.with_title("short")) for x in a] + [esc(case.firm_nazwa), esc(case.firm_address),
                                                            f"e-mail: {case.firm_mail}", f"tel.: {case.firm_phone}"]
        s.append(ctx.P("<br/>".join(lines), "body", leftIndent=18))
    s.append(ctx.P("Postępowanie:", "h"))
    items = [f"nazwa zamówienia: „{esc(case.tytul)}”", f"tryb: {case.tryb}"]
    lab = {"nr": "oznaczenie sprawy", "bzp": "numer ogłoszenia w BZP", "ted": "numer ogłoszenia w Dz.Urz. UE (TED)"}
    items += [f"{lab[k]}: {esc(v)}" for k, v in ctx.proc_parts(case)]
    s += [ctx.P("• " + it, "body", leftIndent=18) for it in items]
    s.append(ctx.gap(3))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s.append(ctx.P("Powyższym czynnościom Odwołujący zarzuca:", "bold"))
    s += B.zarzuty_flow(case, ctx, numbering="{a})")
    s += B.requests_flow(case, ctx)
    s += B.justification(case, ctx, title="Uzasadnienie odwołania")
    s += B.attachments(case, ctx, title="W załączeniu:")
    s += B.signature(case, ctx)
    build_simple(path, s, ctx, footer=ctx.rng.choice(["{p}", "Strona {p}"]), margins=(24, 18, 20, 22))

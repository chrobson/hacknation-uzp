"""Transposed party matrix: columns = parties, rows = attributes; signature grid at the end."""

from reportlab.lib import colors
from reportlab.lib.units import mm

from .. import blocks as B
from ..core import build_simple, esc

NAME = "dev_t12_party_matrix"
OVERRIDES = {"multi_zam": 0.25, "consortium": 0.25}


def render(case, ctx, path):
    s = []
    top = [B.place_date(case, ctx) or "", "Prezes KIO, ul. Postępu 17A, 02-676 Warszawa"]
    s.append(ctx.table([[esc(top[0]), top[1]]], [85 * mm, 85 * mm], grid=False))
    s.append(ctx.P("ODWOŁANIE OD CZYNNOŚCI ZAMAWIAJĄCEGO", "title"))
    parties = []
    for i, e in enumerate(case.odw):
        parties.append(("Odwołujący" + ("" if not case.consortium else (" (Lider)" if i == 0 else " (Partner)")), e))
    for z in case.zams:
        parties.append(("Zamawiający" + ("" if len(case.zams) == 1 else (" (prowadzący)" if z.prowadzacy else "")), z))
    for k in range(0, len(parties), 3):
        chunk = parties[k:k + 3]
        head = ["Dane"] + [f"<b>{r}</b>" for r, _ in chunk]
        rows = [head, ["Nazwa"] + [esc(e.nazwa) for _, e in chunk],
                ["Siedziba"] + [esc(e.address) for _, e in chunk],
                ["KRS"] + [ctx.krs(e.krs) if e.krs else "–" for _, e in chunk],
                ["NIP"] + [ctx.nip(e.nip) if e.nip else "–" for _, e in chunk],
                ["REGON"] + [ctx.regon(e.regon) if e.regon else "–" for _, e in chunk]]
        w = (170 - 22) / len(chunk)
        s.append(ctx.table(rows, [22 * mm] + [w * mm] * len(chunk), header=True,
                           shade=colors.HexColor("#e6e6e6")))
        s.append(ctx.gap(2))
    s.append(ctx.gap(3))
    if case.attorneys:
        s.append(ctx.P(f"Odwołujący reprezentowany jest przez: {esc(ctx.attorneys_line(case, 'long'))} – "
                       f"{esc(case.firm_nazwa)}, {esc(case.firm_address)}, {case.firm_mail}.", "just"))
    s.append(ctx.P("Dotyczy " + B.proc_sentence(case, ctx) + ".", "just"))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s += B.zarzuty_flow(case, ctx, numbering="Zarzut {i}.")
    s += B.requests_flow(case, ctx)
    s += B.justification(case, ctx, n_fill=4)
    if case.attorneys:
        sig = [[esc(a.with_title("short")) for a in case.attorneys]]
    else:
        sig = [[f"{esc(case.signer)}<br/>{case.signer_role}"]]
    s.append(ctx.gap(8))
    s.append(ctx.table([["............................"] * len(sig[0])] + sig, grid=False))
    build_simple(path, s, ctx, footer="{p}")

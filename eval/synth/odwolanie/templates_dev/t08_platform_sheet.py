"""e-Zamówienia platform style: metadata box + parties as a multi-column grid."""

from reportlab.lib import colors
from reportlab.lib.units import mm

from .. import blocks as B
from ..core import build_simple, esc, fmt_date

NAME = "dev_t08_platform_sheet"
OVERRIDES = {"consortium": 0.25}


def render(case, ctx, path):
    s = []
    meta = [["Rodzaj dokumentu", "<b>Odwołanie do Prezesa Krajowej Izby Odwoławczej</b>"]]
    if case.data:
        meta.append(["Data dokumentu", fmt_date(case.data, ctx.rng.choice(["iso", "dots", "slash", "dash"]))])
        meta.append(["Miejsce sporządzenia", esc(case.miejscowosc)])
    meta.append(["Kanał wniesienia", ctx.rng.choice(["platforma e-Zamówienia", "ePUAP", "poczta elektroniczna"])])
    if case.nr:
        meta.append(["Identyfikator postępowania", esc(case.nr)])
    s.append(ctx.table(meta, [50 * mm, 120 * mm], shade=colors.HexColor("#f0f0f0")))
    s.append(ctx.gap(5))
    hdr = ["Rola", "Nazwa", "Identyfikatory", "Adres / kontakt"]
    rows = [hdr]
    for i, e in enumerate(case.odw):
        role = "Odwołujący" if not case.consortium else ("Odwołujący – Lider" if i == 0 else "Odwołujący – Partner")
        rows.append([role, esc(e.nazwa), "<br/>".join(ctx.id_parts(e)), esc(e.address)])
    for z in case.zams:
        role = "Zamawiający"
        if len(case.zams) > 1:
            role += " (prowadzący)" if z.prowadzacy else " (uczestnik)"
        rows.append([role, esc(z.nazwa), "<br/>".join(ctx.id_parts(z)), esc(z.address) + (f"<br/>{z.email}" if z.email else "")])
    if case.attorneys:
        rows.append(["Pełnomocnik", "<br/>".join(esc(a.with_title("short")) for a in case.attorneys),
                     esc(case.firm_nazwa), f"{esc(case.firm_address)}<br/>{case.firm_mail}"])
    s.append(ctx.table(rows, [26 * mm, 48 * mm, 38 * mm, 58 * mm], header=True))
    s.append(ctx.gap(4))
    s.append(ctx.P("Przedmiot postępowania", "h"))
    s.append(ctx.P(f"„{esc(case.tytul)}”", "bold"))
    lab = {"nr": "Znak", "bzp": "BZP", "ted": "TED"}
    pp = ctx.proc_parts(case)
    if pp:
        s.append(ctx.P(" | ".join(f"{lab[k]}: {esc(v)}" for k, v in pp)))
    s.append(ctx.P("Treść odwołania", "h"))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s += B.zarzuty_flow(case, ctx, numbering="Zarzut {r}")
    s += B.requests_flow(case, ctx, title="Żądania odwołania:")
    s += B.justification(case, ctx, title="Uzasadnienie faktyczne i prawne", n_fill=3)
    s += B.signature(case, ctx, align="left")
    build_simple(path, s, ctx, margins=(20, 20, 18, 20), footer=None)

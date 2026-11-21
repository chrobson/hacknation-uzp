"""Bilingual (EN/PL) label table, typical for foreign-owned appellants."""

from reportlab.lib import colors
from reportlab.lib.units import mm

from .. import blocks as B
from ..core import build_simple, esc, fmt_date

NAME = "dev_t07_bilingual"
OVERRIDES = {}


def _ent_rows(e, ctx, role_en, role_pl):
    rows = [[f"{role_en} / {role_pl}", f"<b>{esc(e.nazwa)}</b><br/>{esc(e.address)}"]]
    if e.krs:
        rows.append(["Court register no. / KRS", ctx.krs(e.krs)])
    if e.nip:
        rows.append(["Tax ID / NIP", ctx.nip(e.nip)])
    if e.regon:
        rows.append(["Statistical no. / REGON", ctx.regon(e.regon)])
    return rows


def render(case, ctx, path):
    W = [62 * mm, 108 * mm]
    s = []
    if case.data:
        s.append(ctx.P(f"{esc(case.miejscowosc)}, {fmt_date(case.data, ctx.rng.choice(['dots', 'iso', 'words', 'en']))}",
                       "right"))
    s.append(ctx.P("APPEAL / ODWOŁANIE", "title"))
    s.append(ctx.P("to the President of the National Appeal Chamber (Krajowa Izba Odwoławcza), "
                   "ul. Postępu 17A, 02-676 Warszawa", "center"))
    s.append(ctx.gap(3))
    rows = []
    for i, e in enumerate(case.odw):
        if case.consortium:
            rows += _ent_rows(e, ctx, "Appellant – consortium leader" if i == 0 else "Consortium member",
                              "Odwołujący – lider konsorcjum" if i == 0 else "Członek konsorcjum")
        else:
            rows += _ent_rows(e, ctx, "Appellant", "Odwołujący")
    if case.attorneys:
        rows.append(["Attorney(s) / Pełnomocnik(cy)", "<br/>".join(esc(a.with_title("short")) for a in case.attorneys)])
        rows.append(["Law firm / Kancelaria", esc(case.firm_nazwa) + "<br/>" + esc(case.firm_address)])
        rows.append(["E-mail for service / adres e-mail", case.firm_mail])
    for z in case.zams:
        role = "Contracting authority / Zamawiający"
        if len(case.zams) > 1:
            role += " (lead / prowadzący)" if z.prowadzacy else " (co-authority)"
        rows += _ent_rows(z, ctx, *role.split(" / ", 1))
    rows.append(["Contract title / Tytuł zamówienia", esc(case.tytul)])
    lab = {"nr": "Reference no. / Nr postępowania", "bzp": "BZP notice / Ogłoszenie BZP",
           "ted": "OJEU (TED) notice / Ogłoszenie TED"}
    rows += [[lab[k], esc(v)] for k, v in ctx.proc_parts(case)]
    if case.first.date:
        rows.append(["Date of contested act / Data czynności", fmt_date(case.first.date, ctx.rng.choice(["dots", "iso", "en"]))])
    s.append(ctx.table(rows, W, shade=colors.HexColor("#eef2f7")))
    s.append(ctx.gap(4))
    s.append(ctx.P("Contested acts / Zaskarżone czynności", "h"))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s.append(ctx.P("Pleas / Zarzuty", "h"))
    s += B.zarzuty_flow(case, ctx, numbering="Plea {i} / Zarzut {i}")
    s += B.requests_flow(case, ctx, title="Requests / Żądania:")
    s += B.justification(case, ctx, title="Statement of reasons / Uzasadnienie", n_fill=4)
    s += B.signature(case, ctx)
    s += B.attachments(case, ctx, title="Enclosures / Załączniki:")
    build_simple(path, s, ctx, footer="Page {p} of {n}")

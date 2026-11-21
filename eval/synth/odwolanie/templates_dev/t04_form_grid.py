"""Form-like document: numbered sections rendered as label|value grids."""

from reportlab.lib import colors
from reportlab.lib.units import mm

from .. import blocks as B
from ..core import build_simple, esc, fmt_date

NAME = "dev_t04_form_grid"
OVERRIDES = {}


def _rows_entity(e, ctx, prefix=""):
    rows = [[f"{prefix}Nazwa (firma)", f"<b>{esc(e.nazwa)}</b>"], [f"{prefix}Adres siedziby", esc(e.address)]]
    if e.krs:
        rows.append([f"{prefix}Numer KRS", ctx.krs(e.krs)])
    if e.nip:
        rows.append([f"{prefix}NIP", ctx.nip(e.nip)])
    if e.regon:
        rows.append([f"{prefix}REGON", ctx.regon(e.regon)])
    return rows


def render(case, ctx, path):
    W = [55 * mm, 115 * mm]
    shade = colors.HexColor(ctx.rng.choice(["#eeeeee", "#e8f0f8", "#f4efe2"]))
    s = [ctx.P("FORMULARZ ODWOŁANIA DO PREZESA KRAJOWEJ IZBY ODWOŁAWCZEJ", "title")]
    meta = []
    if case.data:
        meta.append(["Miejscowość", esc(case.miejscowosc)])
        meta.append(["Data sporządzenia", fmt_date(case.data, ctx.rng.choice(["iso", "dots", "dots_r", "slash"]))])
    if case.kio_sygn:
        meta.append(["Sygnatura (wypełnia KIO)", case.kio_sygn])
    if meta:
        s.append(ctx.table(meta, W, shade=shade))
    s.append(ctx.P("Część A. Odwołujący", "h"))
    if case.consortium:
        s.append(ctx.P("Wykonawcy wspólnie ubiegający się o udzielenie zamówienia – dane Lidera:", "small"))
    s.append(ctx.table(_rows_entity(case.odw[0], ctx), W, shade=shade))
    for i, e in enumerate(case.odw[1:], 2):
        s.append(ctx.P(f"Członek konsorcjum nr {i}", "small"))
        s.append(ctx.table(_rows_entity(e, ctx), W, shade=shade))
    s.append(ctx.P("Część B. Pełnomocnik", "h"))
    if case.attorneys:
        rows = [["Imię i nazwisko", "<br/>".join(esc(a.with_title("long")) for a in case.attorneys)],
                ["Kancelaria", esc(case.firm_nazwa)], ["Adres", esc(case.firm_address)],
                ["Adres e-mail", case.firm_mail], ["Telefon", case.firm_phone]]
    else:
        rows = [["Pełnomocnik", "nie ustanowiono – Odwołujący działa przez organ uprawniony do reprezentacji"]]
    s.append(ctx.table(rows, W, shade=shade))
    s.append(ctx.P("Część C. Zamawiający", "h"))
    for z in case.zams:
        rows = _rows_entity(z, ctx)
        if len(case.zams) > 1:
            rows.append(["Prowadzący postępowanie", "TAK" if z.prowadzacy else "NIE"])
        s.append(ctx.table(rows, W, shade=shade))
        s.append(ctx.gap(1))
    s.append(ctx.P("Część D. Postępowanie", "h"))
    rows = [["Nazwa zamówienia", esc(case.tytul)], ["Tryb", f"postępowanie w trybie {case.tryb}"]]
    labels = {"nr": "Numer referencyjny", "bzp": "Ogłoszenie BZP", "ted": "Ogłoszenie TED (Dz.Urz. UE)"}
    rows += [[labels[k], esc(v)] for k, v in ctx.proc_parts(case)]
    s.append(ctx.table(rows, W, shade=shade))
    s.append(ctx.P("Część E. Zaskarżone czynności / zaniechania", "h"))
    rows = [["Lp.", "Czynność lub zaniechanie", "Data"]]
    for i, z in enumerate(case.zarzuty, 1):
        rows.append([str(i), ctx.zarzut(z, "action", dated=False),
                     ctx.d(z.date, "dots") if z.date else "–"])
    s.append(ctx.table(rows, [12 * mm, 128 * mm, 30 * mm], header=True))
    s.append(ctx.P("Część F. Zarzuty", "h"))
    s += B.zarzuty_flow(case, ctx, numbering="F.{i}")
    s.append(ctx.P("Część G. Żądania", "h"))
    s += B.requests_flow(case, ctx, title="Odwołujący wnosi o:")
    s.append(ctx.P("Część H. Uzasadnienie", "h"))
    s += B.justification(case, ctx, title="", n_fill=3)[1:]
    s += B.signature(case, ctx)
    build_simple(path, s, ctx, footer="Formularz odwołania – str. {p}/{n}", margins=(20, 20, 18, 20))

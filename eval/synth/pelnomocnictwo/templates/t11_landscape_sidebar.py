"""Landscape page with a left sidebar holding identification data and the right column with prose."""
from eval.synth.pelnomocnictwo.lib import esc, join_pl, scope_items, title_str
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

ID = "dev_t11_landscape_sidebar"
PREFS = {}


def build(c):
    k, r = c.case, c.rng
    c.pagesize = landscape(A4)
    c.margins = (15, 15, 15, 15)
    side = []
    for i, p in enumerate(k.principals, 1):
        side.append(c.P(f"<b>{'Mocodawca' if len(k.principals)==1 else f'Mocodawca {i}'}</b>", "cell"))
        side.append(c.P(esc(p.nazwa), "cell"))
        side.append(c.P(esc(p.address), "cell"))
        if p.krs:
            side.append(c.P(f"KRS {p.krs}", "cell"))
        if p.nip:
            side.append(c.P(f"NIP {c.nip(p.nip)}", "cell"))
        side.append(c.sp(8))
    side.append(c.P(f"<b>Data:</b> {c.date()}", "cell"))
    side.append(c.P(f"<b>Miejsce:</b> {k.city}", "cell"))
    if k.kio_sygn:
        side.append(c.P(f"<b>Sprawa:</b> {esc(k.kio_sygn)}", "cell"))
    main = [c.P("PEŁNOMOCNICTWO", "title")]
    att = []
    for a in k.attorneys:
        t = title_str(r, a, "gen")
        att.append(f"{a.pan('gen')} {a.form('gen')}" + (f" – {t}" if t else "") + (f" (PESEL {a.pesel})" if a.pesel else ""))
    subj = "Mocodawca, wskazany w rubryce obok," if len(k.principals) == 1 else "Mocodawcy wskazani w rubryce obok, działając wspólnie,"
    main.append(c.P(f"{subj} ustanawia{'ją' if len(k.principals) > 1 else ''} w osobie {join_pl(att, ' oraz ')} "
                    f"pełnomocnika{'' if len(att)==1 else ' (każdego z osobna)'} do reprezentowania w postępowaniu odwoławczym "
                    f"dotyczącym zamówienia „{esc(k.procurement['tytul'])}”, prowadzonego przez {esc(k.procurement['zamawiajacy'])}."))
    main.append(c.P("Umocowanie obejmuje: " + "; ".join(scope_items(r, k=(4, 6))) + "."))
    main.append(c.sp(16))
    sigs = []
    for p in k.principals:
        for sg in p.signatories:
            sigs.append(c.P(f"<br/><br/>{c.sig_line()}<br/>{sg.full}" + (f"<br/>{esc(sg.role)}" if sg.role else "")
                            + (f"<br/>({esc(p.nazwa)})" if len(k.principals) > 1 else ""), "cell"))
    rows = [sigs[i:i + 3] for i in range(0, len(sigs), 3)]
    main.append(Table(rows, hAlign="LEFT"))
    t = Table([[side, main]], colWidths=[75 * mm, 185 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(r.choice(["#eeeeee", "#e8eef6", "#ffffff"]))),
                           ("LINEAFTER", (0, 0), (0, 0), 0.8, colors.grey), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    return [t]

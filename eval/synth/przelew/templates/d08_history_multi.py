"""Transaction-history export with several rows; only one is the KIO-related transfer."""
import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from eval.synth.common_przelew import (esc, fmt_amount, fmt_date, para_styles, pick_font,
                                       render_values)

NAME = "d08_history_multi"

OTHER = ["Opłata za prowadzenie rachunku", "Prowizja za przelew natychmiastowy",
         "Opłata za kartę debetową", "Przelew przychodzący – zapłata za FV/{n}/2026",
         "Zwrot nadpłaty – korekta FV/{n}/2026"]


def render(case, rng, path):
    font = pick_font(rng, allow_mono=False)
    st = para_styles(font, 8)
    ds = rng.choice(["iso", "dmy_dot", "dmy_slash"])
    v = render_values(case, rng, date_styles=[ds])
    rows = []
    for _ in range(rng.randint(2, 3)):
        d = case.date + dt.timedelta(days=rng.choice([-9, -5, -3, -1, 1, 2, 4]))
        txt = rng.choice(OTHER).format(n=rng.randint(10, 999))
        amt = round(rng.uniform(3, 4000), 2)
        sign = "" if txt.startswith(("Przelew przychodzący", "Zwrot")) else "-"
        rows.append((d, [fmt_date(d, ds), Paragraph(esc(txt), st["n"]), sign + fmt_amount(amt, "pl")]))
    desc = (f"Przelew wychodzący do: {esc(case.payee.name)}<br/>na rachunek {v.na}<br/>"
            f"tytuł: {esc(v.title)}")
    if v.ref:
        # always labelled, also when the title repeats it (otherwise numer_transakcji is ambiguous)
        desc += f"<br/>ref. {v.ref}"
    rows.append((case.date, [v.date, Paragraph(desc, st["n"]), "-" + fmt_amount(case.pb["kwota"], "pl")]))
    rows.sort(key=lambda r: r[0], reverse=rng.random() < 0.6)
    data = [[Paragraph("<b>Data</b>", st["n"]), Paragraph("<b>Opis</b>", st["n"]),
             Paragraph("<b>Kwota [PLN]</b>", st["n"])]] + [r[1] for r in rows]
    t = Table(data, colWidths=[24 * mm, 118 * mm, 28 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), font[0], 8),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.grey),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (2, 0), (2, -1), "RIGHT")]))
    story = [Paragraph(f"{esc(case.bank)} – Historia operacji", st["h2"]),
             Paragraph(f"Rachunek: {v.z} · {esc(case.payer.name)}", st["n"]),
             Paragraph(f"Zakres dat: {fmt_date(min(r[0] for r in rows), ds)} – "
                       f"{fmt_date(max(r[0] for r in rows), ds)}", st["n"]),
             Spacer(1, 4 * mm), t]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)

"""Dense e-banking export: pipe-separated label:value runs, small font."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from eval.synth.common_przelew import esc, fmt_date, para_styles, pick_font, render_values

NAME = "d06_pipes"


def render(case, rng, path):
    font = pick_font(rng)
    st = para_styles(font, rng.choice([8, 8.5, 9]))
    v = render_values(case, rng)
    sep = rng.choice([" | ", " · ", " ; "])
    l1 = sep.join([f"Data: {v.date}", f"Kwota: {v.amount}", "Waluta: PLN",
                   "Status: " + rng.choice(["Zaksięgowana", "Wykonana"])])
    l2 = sep.join([f"Z rachunku: {v.z}", f"Nadawca: {esc(case.payer.name)}"])
    l3 = sep.join([f"Na rachunek: {v.na}", f"Odbiorca: {esc(case.payee.name)}",
                   f"Adres: {esc(case.payee.address)}"])
    l4 = f"Tytuł: {esc(v.title)}"
    lines = [l1, l2, l3, l4]
    if v.ref:
        lines.append(f"ID: {v.ref}{sep}Kanał: internet")
    if rng.random() < 0.5:
        lines = [lines[1], lines[2], lines[0]] + lines[3:]
    story = [Paragraph(f"<b>{esc(case.bank)}</b> – bankowość internetowa", st["n"]),
             Paragraph(f"Szczegóły transakcji – eksport z dnia {fmt_date(case.gen_date, 'dmy_dot_time', rng)}", st["s"]),
             HRFlowable(width="100%"), Spacer(1, 2 * mm)]
    story += [Paragraph(x, st["n"]) for x in lines]
    story += [Spacer(1, 3 * mm), HRFlowable(width="100%"),
              Paragraph("Strona 1/1", st["s"])]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                      topMargin=12 * mm).build(story)

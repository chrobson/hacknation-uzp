"""Two pages: cover note with summary, details on page 2."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from eval.synth.common_przelew import (doc_number, esc, fmt_date, para_styles, pick_font,
                                       render_values)

NAME = "d09_two_page"


def render(case, rng, path):
    font = pick_font(rng)
    st = para_styles(font, 10)
    v = render_values(case, rng)
    no = doc_number(rng, case.gen_date)
    story = [Paragraph(esc(case.bank), st["h1"]),
             Paragraph(f"Pakiet dokumentów nr {no}", st["n"]), Spacer(1, 8 * mm),
             Paragraph("Zawartość:", st["b"]),
             Paragraph("1. Potwierdzenie wykonania przelewu (str. 2)", st["n"]),
             Spacer(1, 6 * mm),
             Paragraph(f"Klient: {esc(case.payer.name)}", st["n"]),
             Paragraph(f"Data wygenerowania: {fmt_date(case.gen_date, 'dmy_dot')}", st["n"]),
             PageBreak(),
             Paragraph("Potwierdzenie wykonania przelewu", st["h2"]), Spacer(1, 3 * mm)]
    rows = [["Zleceniodawca:", Paragraph(esc(case.payer.name), st["n"])],
            ["Rachunek zleceniodawcy:", v.z],
            ["Odbiorca:", Paragraph(esc(case.payee.name), st["n"])],
            ["Rachunek odbiorcy:", v.na],
            ["Kwota:", v.amount],
            ["Data operacji:", v.date],
            ["Tytuł:", Paragraph(esc(v.title), st["n"])]]
    if v.ref:
        rows.append(["Nr transakcji:", v.ref])
    t = Table(rows, colWidths=[50 * mm, 115 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), font[0], 10), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [t, Spacer(1, 6 * mm), Paragraph(f"Dokument nr {no}, strona 2 z 2", st["s"])]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)

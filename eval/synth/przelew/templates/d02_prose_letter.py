"""Formal letter from the bank confirming the transfer in running prose."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from eval.synth.common_przelew import (CITIES, doc_number, esc, fmt_date, para_styles,
                                       pick_font, render_values)

NAME = "d02_prose_letter"


def render(case, rng, path):
    font = pick_font(rng, allow_mono=False)
    st = para_styles(font, rng.choice([10, 10.5, 11]))
    v = render_values(case, rng, date_styles=["words_r", "dmy_dot_r", "words", "roman_r", "dmy_dot"])
    city = rng.choice(CITIES)[1]
    head = rng.choice(["POTWIERDZENIE WYKONANIA PRZELEWU", "Potwierdzenie realizacji dyspozycji",
                       "ZAŚWIADCZENIE O WYKONANIU PRZELEWU"])
    intro = rng.choice(["Uprzejmie informujemy, że", "Niniejszym potwierdzamy, że",
                        "Na wniosek Klienta potwierdzamy, iż"])
    body = (f"{intro} w dniu {v.date} z rachunku nr {v.z}, prowadzonego dla "
            f"{esc(case.payer.name)}, {esc(case.payer.address)}, została zrealizowana dyspozycja "
            f"przelewu w kwocie {v.amount} na rachunek nr {v.na}, którego posiadaczem jest "
            f"{esc(case.payee.name).rstrip('.')}. Tytuł przelewu: „{esc(v.title)}”.")
    story = [Paragraph(esc(case.bank), st["h2"]),
             Paragraph(f"Oddział w {city}", st["s"]),
             Spacer(1, 6 * mm),
             Paragraph(f"{city}, {fmt_date(case.gen_date, 'dmy_dot_r')}", st["r"]),
             Paragraph(f"Nasz znak: {doc_number(rng, case.gen_date)}", st["n"]),
             Spacer(1, 8 * mm),
             Paragraph(esc(case.payer.name), st["b"]), Paragraph(esc(case.payer.address), st["n"]),
             Spacer(1, 10 * mm), Paragraph(head, st["h2"]), Spacer(1, 4 * mm),
             Paragraph(body, st["j"])]
    if v.ref:
        story += [Spacer(1, 3 * mm),
                  Paragraph(rng.choice(["Numer referencyjny operacji: ", "Identyfikator transakcji: ",
                                        "Operacji nadano numer "]) + v.ref + ".", st["j"])]
    story += [Spacer(1, 3 * mm),
              Paragraph("Środki zostały przekazane za pośrednictwem systemu ELIXIR. "
                        "Prowizja za realizację przelewu: 0,00 zł.", st["j"]),
              Spacer(1, 14 * mm), Paragraph("Z poważaniem", st["r"]),
              Paragraph("Departament Obsługi Klienta", st["r"])]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm,
                      topMargin=20 * mm).build(story)

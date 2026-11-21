"""Full-grid two-column table with Polish synonym labels in random order."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from eval.synth.common_przelew import (FOOTERS_PL, esc, fmt_date, para_styles, pick_font,
                                       render_values)

NAME = "d05_grid_kv"


def render(case, rng, path):
    font = pick_font(rng)
    st = para_styles(font, 9)
    v = render_values(case, rng)
    L = lambda *opts: rng.choice(opts)
    core = [
        [L("Rachunek nadawcy", "Rachunek obciążony", "Numer rachunku zleceniodawcy"), v.z],
        [L("Nazwa nadawcy", "Zleceniodawca", "Dane zleceniodawcy"),
         Paragraph(f"{esc(case.payer.name)}, {esc(case.payer.address)}", st["n"])],
        [L("Rachunek odbiorcy", "Rachunek uznany", "Numer rachunku beneficjenta"), v.na],
        [L("Nazwa odbiorcy", "Beneficjent", "Dane odbiorcy"),
         Paragraph(f"{esc(case.payee.name)}, {esc(case.payee.address)}", st["n"])],
        [L("Kwota przelewu", "Kwota", "Kwota operacji"), v.amount],
        [L("Data księgowania", "Data wykonania", "Data operacji"), v.date],
        [L("Tytułem", "Tytuł przelewu", "Opis operacji"), Paragraph(esc(v.title), st["n"])],
    ]
    if v.ref:
        core.append([L("Identyfikator transakcji", "Nr referencyjny", "Numer operacji"), v.ref])
    head, rest = core[:4], core[4:]
    if rng.random() < 0.5:
        rng.shuffle(rest)
    else:
        rest, head = head, rest
    rows = head + rest + [["Rodzaj przelewu", L("ELIXIR", "Express ELIXIR", "SORBNET", "wewnętrzny")],
                          ["Status", L("Zrealizowany", "Zaksięgowany")]]
    t = Table(rows, colWidths=[55 * mm, 115 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (0, -1), font[1], 8.5),
                           ("FONT", (1, 0), (1, -1), font[0], 9),
                           ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story = [Paragraph(esc(case.bank), st["b"]),
             Paragraph(L("Potwierdzenie przelewu", "Szczegóły przelewu", "POTWIERDZENIE TRANSAKCJI"), st["h1"]),
             Spacer(1, 3 * mm), t, Spacer(1, 6 * mm),
             Paragraph(f"Data sporządzenia: {fmt_date(case.gen_date, 'iso')}", st["s"]),
             Paragraph(rng.choice(FOOTERS_PL), st["s"])]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)

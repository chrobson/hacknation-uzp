"""Bank statement ("wyciąg") with a single debit row in a table; amount negative."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from eval.synth.common_przelew import (MONTHS_NOM, esc, fmt_account, fmt_amount, fmt_date,
                                       para_styles, pick_font, render_values, FOOTERS_PL)

NAME = "d01_statement_single"


def render(case, rng, path):
    font = pick_font(rng, allow_mono=False)
    st = para_styles(font, rng.choice([8.5, 9, 9.5]))
    v = render_values(case, rng, date_styles=["dmy_dot", "iso", "dmy_slash"])
    pb = case.pb
    neg = fmt_amount(pb["kwota"], rng.choice(["pl", "pl_dot_thousands", "pl"])).replace(" PLN", "")
    neg = "-" + neg
    opening = rng.randint(20000, 900000) + rng.randint(0, 99) / 100
    closing = opening - pb["kwota"]
    d = case.date
    story = [
        Paragraph(esc(case.bank), st["h1"]),
        Paragraph(f"WYCIĄG Z RACHUNKU BANKOWEGO nr {rng.randint(1, 250)}/{d.year}", st["h2"]),
        Paragraph(f"Okres: {MONTHS_NOM[d.month - 1]} {d.year}", st["n"]),
        Spacer(1, 4 * mm),
        Paragraph(f"Posiadacz rachunku: <b>{esc(case.payer.name)}</b>", st["n"]),
        Paragraph(esc(case.payer.address), st["n"]),
        Paragraph(f"Numer rachunku: {v.z}", st["n"]),
        Paragraph("Waluta: PLN", st["n"]),
        Spacer(1, 5 * mm),
    ]
    desc = (f"PRZELEW WYCHODZĄCY<br/>Odbiorca: {esc(case.payee.name)}<br/>"
            f"Rachunek odbiorcy: {v.na}<br/>Tytuł: {esc(v.title)}")
    if v.ref and not case.ref_in_title:
        desc += f"<br/>Ref.: {v.ref}"
    elif v.ref:
        # the number is always shown under its own label: a number that sits only inside the
        # title makes numer_transakcji ambiguous (null vs the token), i.e. an unfair GT
        rng.random()  # keep the random stream identical to earlier runs
        desc += f"<br/>Nr transakcji: {v.ref}"
    hdr = ["Data księg.", "Data waluty", "Opis operacji", "Kwota", "Saldo"]
    rows = [[Paragraph(h, st["b"]) for h in hdr],
            ["", "", Paragraph("Saldo początkowe", st["n"]), "", fmt_amount(opening, "pl")],
            [v.date, v.date, Paragraph(desc, st["n"]), neg, fmt_amount(closing, "pl")],
            ["", "", Paragraph("Saldo końcowe", st["n"]), "", fmt_amount(closing, "pl")]]
    t = Table(rows, colWidths=[22 * mm, 22 * mm, 80 * mm, 25 * mm, 28 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font[0], st["n"].fontSize),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ecf2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),
    ]))
    story += [t, Spacer(1, 6 * mm),
              Paragraph(f"Liczba operacji: 1. Obciążenia: {neg[1:]} PLN. Uznania: 0,00 PLN.", st["s"]),
              Paragraph(f"Wygenerowano: {fmt_date(case.gen_date, 'dmy_dot')}. " + rng.choice(FOOTERS_PL), st["s"])]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(story)

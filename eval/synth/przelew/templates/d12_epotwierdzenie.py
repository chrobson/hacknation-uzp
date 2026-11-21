"""e-Potwierdzenie: right-aligned value column, QR placeholder, footnotes, timestamps."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from eval.synth.common_przelew import fmt_date, pick_font, render_values
import textwrap

NAME = "d12_epotwierdzenie"


def render(case, rng, path):
    font = pick_font(rng)
    v = render_values(case, rng, date_styles=["roman_r", "roman", "words_r", "dmy_dot_r", "iso"])
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont(font[1], 13)
    c.drawString(20 * mm, H - 25 * mm, "e-Potwierdzenie przelewu¹")
    c.setFont(font[0], 9)
    c.drawString(20 * mm, H - 31 * mm, case.bank)
    # QR-like placeholder
    qx, qy = W - 45 * mm, H - 45 * mm
    for i in range(10):
        for j in range(10):
            if rng.random() < 0.5:
                c.rect(qx + i * 2.5 * mm, qy + j * 2.5 * mm, 2.5 * mm, 2.5 * mm, stroke=0, fill=1)
    rows = [("Data i godzina zlecenia", fmt_date(case.date, "dmy_dot_time", rng)),
            ("Data realizacji²", v.date),
            ("Rachunek nadawcy", v.z), ("Nadawca", case.payer.name),
            ("Rachunek odbiorcy", v.na), ("Odbiorca", case.payee.name),
            ("Kwota", v.amount)]
    if v.ref:
        rows.append(("Numer transakcji", v.ref))
    y = H - 60 * mm
    for lab, val in rows:
        c.setFont(font[0], 9)
        c.setFillColor(colors.HexColor("#444444"))
        c.drawString(20 * mm, y, lab)
        c.setFillColor(colors.black)
        c.setFont(font[1], 9.5)
        lines = textwrap.wrap(val, 55)
        for ln in lines:
            c.drawRightString(W - 20 * mm, y, ln)
            y -= 4.8 * mm
        c.setStrokeColor(colors.HexColor("#dddddd"))
        c.line(20 * mm, y + 2.5 * mm, W - 20 * mm, y + 2.5 * mm)
        y -= 3 * mm
    c.setFont(font[0], 9)
    c.drawString(20 * mm, y - 2 * mm, "Tytuł przelewu:")
    y -= 8 * mm
    c.setFont(font[1], 9.5)
    for ln in textwrap.wrap(v.title, 85):
        c.drawString(20 * mm, y, ln)
        y -= 5 * mm
    c.setFont(font[0], 7)
    c.drawString(20 * mm, 22 * mm, "¹ Dokument elektroniczny wygenerowany w systemie bankowości internetowej.")
    c.drawString(20 * mm, 18 * mm, "² Data obciążenia rachunku nadawcy.")
    c.drawString(20 * mm, 14 * mm, f"Wydrukowano: {fmt_date(case.gen_date, 'dmy_dot')}")
    c.showPage()
    c.save()

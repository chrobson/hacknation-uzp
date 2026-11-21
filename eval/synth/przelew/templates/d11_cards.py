"""Card grid: grey header bars, small label above bold value (stacked)."""
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from eval.synth.common_przelew import fmt_date, pick_font, render_values

NAME = "d11_cards"


def render(case, rng, path):
    font = pick_font(rng, allow_mono=False)
    v = render_values(case, rng)
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    accent = rng.choice([colors.HexColor("#1f4e79"), colors.HexColor("#7a1f1f"), colors.HexColor("#25603a")])
    c.setFillColor(accent)
    c.rect(0, H - 28 * mm, W, 28 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(font[1], 16)
    c.drawString(18 * mm, H - 17 * mm, case.bank)
    c.setFont(font[0], 10)
    c.drawRightString(W - 18 * mm, H - 17 * mm, "Szczegóły przelewu")
    cards = [("Z RACHUNKU", [v.z, case.payer.name]), ("NA RACHUNEK", [v.na, case.payee.name]),
             ("KWOTA", [v.amount]), ("DATA", [v.date])]
    if v.ref:
        cards.append(("NUMER TRANSAKCJI", [v.ref]))
    cards.append(("STATUS", [rng.choice(["Wykonany", "Zrealizowany"])]))
    cw = (W - 46 * mm) / 2
    x0, y = 18 * mm, H - 40 * mm
    for i, (lab, vals) in enumerate(cards):
        x = x0 + (i % 2) * (cw + 10 * mm)
        if i and i % 2 == 0:
            y -= 26 * mm
        c.setFillColor(colors.HexColor("#e9e9e9"))
        c.rect(x, y - 3 * mm, cw, 6 * mm, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont(font[0], 7.5)
        c.drawString(x + 2 * mm, y - 1 * mm, lab)
        c.setFillColor(colors.black)
        yy = y - 9 * mm
        for j, val in enumerate(vals):
            c.setFont(font[1] if j == 0 else font[0], 10.5 if j == 0 else 8.5)
            for ln in textwrap.wrap(val, 48):
                c.drawString(x + 2 * mm, yy, ln)
                yy -= 4.5 * mm
    y -= 30 * mm
    c.setFillColor(colors.HexColor("#e9e9e9"))
    c.rect(x0, y - 3 * mm, W - 36 * mm, 6 * mm, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#555555"))
    c.setFont(font[0], 7.5)
    c.drawString(x0 + 2 * mm, y - 1 * mm, "TYTUŁ")
    c.setFillColor(colors.black)
    c.setFont(font[0], 10)
    yy = y - 9 * mm
    for ln in textwrap.wrap(v.title, 90):
        c.drawString(x0 + 2 * mm, yy, ln)
        yy -= 5 * mm
    c.setFont(font[0], 7)
    c.drawString(x0, 14 * mm, f"Wygenerowano {fmt_date(case.gen_date, 'dmy_dot_time', rng)}")
    c.showPage()
    c.save()

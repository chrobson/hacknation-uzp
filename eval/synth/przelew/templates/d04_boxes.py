"""Canvas layout: sender/recipient side-by-side boxes, big amount, title box below."""
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from eval.synth.common_przelew import fmt_date, pick_font, render_values

NAME = "d04_boxes"


def _box(c, x, y, w, h, title, lines, font, fill):
    c.setFillColor(fill)
    c.rect(x, y - h, w, h, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.setFont(font[1], 9)
    c.drawString(x + 3 * mm, y - 5 * mm, title)
    c.setFont(font[0], 9)
    yy = y - 11 * mm
    for ln in lines:
        c.drawString(x + 3 * mm, yy, ln)
        yy -= 4.6 * mm


def render(case, rng, path):
    font = pick_font(rng)
    v = render_values(case, rng, acct_styles=["pl_spaced", "spaced", "plain", "pl"])
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont(font[1], 15)
    c.drawString(20 * mm, H - 22 * mm, case.bank)
    c.setFont(font[0], 10)
    c.drawRightString(W - 20 * mm, H - 22 * mm, rng.choice(["Potwierdzenie przelewu",
                                                            "Potwierdzenie operacji"]))
    fill = rng.choice([colors.whitesmoke, colors.HexColor("#eef5ee"), colors.white])
    bw = (W - 45 * mm) / 2
    wrapw = 44 if font[0] != "Mono" else 38
    pn = textwrap.wrap(case.payer.name, wrapw)
    rn = textwrap.wrap(case.payee.name, wrapw)
    labels = rng.choice([("NADAWCA", "ODBIORCA"), ("Zleceniodawca", "Beneficjent"),
                         ("Z rachunku", "Na rachunek")])
    _box(c, 20 * mm, H - 32 * mm, bw, 40 * mm, labels[0],
         pn + [case.payer.street, case.payer.city, v.z], font, fill)
    _box(c, 25 * mm + bw, H - 32 * mm, bw, 40 * mm, labels[1],
         rn + [case.payee.street, case.payee.city, v.na], font, fill)
    y = H - 85 * mm
    c.setFont(font[0], 9)
    c.drawString(20 * mm, y, "Kwota")
    c.drawString(110 * mm, y, rng.choice(["Data operacji", "Data realizacji", "Data księgowania"]))
    c.setFont(font[1], 20)
    c.drawString(20 * mm, y - 9 * mm, v.amount)
    c.setFont(font[1], 13)
    c.drawString(110 * mm, y - 8 * mm, v.date)
    y -= 22 * mm
    c.setFont(font[0], 9)
    c.drawString(20 * mm, y, "Tytuł")
    lines = textwrap.wrap(v.title, 95 if font[0] != "Mono" else 80)
    c.rect(20 * mm, y - (len(lines) * 5 + 4) * mm, W - 40 * mm, (len(lines) * 5 + 2) * mm)
    yy = y - 6 * mm
    for ln in lines:
        c.drawString(23 * mm, yy, ln)
        yy -= 5 * mm
    yy -= 8 * mm
    if v.ref:
        c.drawString(20 * mm, yy, f"{rng.choice(['Nr referencyjny', 'ID operacji', 'Numer transakcji'])}: {v.ref}")
        yy -= 6 * mm
    c.drawString(20 * mm, yy, "Status: wykonany")
    c.setFont(font[0], 7)
    c.drawString(20 * mm, 15 * mm, f"Data wydruku: {fmt_date(case.gen_date, 'dmy_dot_time', rng)}  |  "
                                   f"{case.bank}, BIC {case.bic}")
    c.showPage()
    c.save()
